"""Tests for Phase 3: Roll-Call Finite State Machine (FSM) & Advanced Playbooks (v3).
<!-- v3 – Comprehensive verification of roll-call inversion elimination and JSON Schema v7 validation -->
"""

import json
import tempfile
import unittest
from pathlib import Path

from src.playbooks.loader_v3 import PlaybookLoaderV3, PlaybookV3, PlaybookValidationError
from src.engine.healer_v3 import TurnCoalescerV3
from app_v3 import app


class TestPhase3RollCallFSM(unittest.TestCase):

    def setUp(self):
        self.loader = PlaybookLoaderV3()
        self.pb = self.loader.load("municipal_meetings")
        self.healer = TurnCoalescerV3(playbook=self.pb)

    def test_roll_call_inversion_eliminated(self):
        """Chair calling a member's name during roll call MUST remain attributed to the Chair."""
        segments = [
            {"ts": "00:01:00", "start": 60.0, "end": 64.0, "text": "We will now begin the roll call vote on the motion to approve."},
            {"ts": "00:01:05", "start": 65.0, "end": 67.0, "text": "Mr. MacLellan?"},
            {"ts": "00:01:08", "start": 68.0, "end": 70.0, "text": "Aye."},
            {"ts": "00:01:11", "start": 71.0, "end": 73.0, "text": "Jennifer Lesky?"},
            {"ts": "00:01:14", "start": 74.0, "end": 76.0, "text": "Present and in favor."},
            {"ts": "00:01:17", "start": 77.0, "end": 80.0, "text": "Thank you everyone. The motion carries 2-0."},
        ]

        blocks = self.healer.heal_and_coalesce(segments)

        # Verification of attributions
        # Block 0: Chair opens roll call and asks for Mr. MacLellan (coalesced within 3s gap)
        self.assertEqual(blocks[0]["speaker"], "Chair")
        self.assertIn("MacLellan", blocks[0]["text"])

        # Block 1: Craig MacLellan responds "Aye"
        self.assertEqual(blocks[1]["speaker"], "Craig MacLellan")
        self.assertEqual(blocks[1]["text"], "Aye.")

        # Block 2: Chair calls Jennifer Lesky
        self.assertEqual(blocks[2]["speaker"], "Chair")
        self.assertIn("Jennifer Lesky", blocks[2]["text"])

        # Block 3: Jennifer Lesky responds
        self.assertEqual(blocks[3]["speaker"], "Jennifer Lesky")
        self.assertIn("Present", blocks[3]["text"])

        # Block 4: Chair concludes
        self.assertEqual(blocks[4]["speaker"], "Chair")
        self.assertIn("motion carries", blocks[4]["text"])

    def test_roll_call_skipped_member_transition(self):
        """When a member is absent and the chair calls the next member, chair attribution is preserved."""
        segments = [
            {"ts": "00:00:10", "start": 10.0, "end": 14.0, "text": "Take the roll please."},
            {"ts": "00:00:15", "start": 15.0, "end": 18.0, "text": "Craig MacLellan?"},
            # No response from MacLellan; chair calls Kearney
            {"ts": "00:00:25", "start": 25.0, "end": 28.0, "text": "Paul Kearney?"},
            {"ts": "00:00:29", "start": 29.0, "end": 31.0, "text": "Aye."},
        ]

        blocks = self.healer.heal_and_coalesce(segments)
        # Verify Chair calls Kearney
        kearney_call = next(b for b in blocks if "Kearney" in b["text"] and "?" in b["text"])
        self.assertEqual(kearney_call["speaker"], "Chair")

        # Verify Kearney response
        kearney_resp = next(b for b in blocks if b["text"] == "Aye.")
        self.assertEqual(kearney_resp["speaker"], "Paul Kearney")

    def test_json_schema_v7_validation_success(self):
        """Valid playbook dict validates cleanly."""
        valid_data = {
            "name": "town_finance_committee",
            "version": "v1",
            "description": "Municipal finance advisory board",
            "default_role": "Committee Member",
            "roles": ["Chair", "Vice Chair", "Committee Member"],
            "cues": {
                "chair": ["call the finance meeting to order"]
            },
            "default_roster": ["Alice Finance", "Bob Advisor"],
        }
        is_valid, err = self.loader.validate_dict(valid_data)
        self.assertTrue(is_valid)
        self.assertIsNone(err)

    def test_json_schema_v7_rejects_missing_required_fields(self):
        """Missing required fields raises PlaybookValidationError."""
        # Missing 'default_role' and 'roles'
        invalid_data = {
            "name": "bad_playbook",
            "cues": {}
        }
        is_valid, err = self.loader.validate_dict(invalid_data)
        self.assertFalse(is_valid)
        self.assertIn("default_role", str(err))

    def test_json_schema_v7_rejects_invalid_types(self):
        """Invalid types (e.g. roles as string instead of list) are rejected."""
        invalid_data = {
            "name": "bad_types",
            "default_role": "Speaker",
            "roles": "Speaker",  # Invalid type: must be array
            "cues": {}
        }
        is_valid, err = self.loader.validate_dict(invalid_data)
        self.assertFalse(is_valid)
        self.assertIn("roles", str(err))

    def test_roll_call_lengthy_speech_response_attribution(self):
        """When a member speaks >15 words before stating their vote, attribution goes to the member, not the Chair."""
        segments = [
            {"ts": "00:01:00", "start": 60.0, "end": 64.0, "text": "We will now begin the roll call vote."},
            {"ts": "00:01:05", "start": 65.0, "end": 67.0, "text": "Mr. MacLellan?"},
            {"ts": "00:01:08", "start": 68.0, "end": 75.0, "text": "Thank you Mr. Chair. Given the recent changes to the zoning proposal, I vote aye."},
            {"ts": "00:01:16", "start": 76.0, "end": 78.0, "text": "Ms. Lesky?"},
            {"ts": "00:01:19", "start": 79.0, "end": 81.0, "text": "Present and voting yes."},
            {"ts": "00:01:22", "start": 82.0, "end": 85.0, "text": "The motion carries unanimously."},
        ]

        blocks = self.healer.heal_and_coalesce(segments)
        self.assertEqual(len(blocks), 5)
        # Block 0: Chair calling vote and MacLellan
        self.assertEqual(blocks[0]["speaker"], "Chair")
        # Block 1: Craig MacLellan's explanation and vote
        self.assertEqual(blocks[1]["speaker"], "Craig MacLellan")
        self.assertIn("zoning proposal, I vote aye", blocks[1]["text"])
        # Block 2: Chair calls Lesky
        self.assertEqual(blocks[2]["speaker"], "Chair")
        # Block 3: Jennifer Lesky votes
        self.assertEqual(blocks[3]["speaker"], "Jennifer Lesky")
        # Block 4: Chair announces result
        self.assertEqual(blocks[4]["speaker"], "Chair")

    def test_acoustic_diarization_clusters_preserved_in_coalescing(self):
        """Segments with distinct acoustic clusters (Speaker_01, Speaker_02) must not be collapsed into one speaker."""
        pb_gen = self.loader.load("general_speech")
        healer = TurnCoalescerV3(playbook=pb_gen)

        segments = [
            {"ts": "00:00:01", "start": 1.0, "end": 5.0, "speaker": "Speaker_01", "text": "Hello everyone, welcome to today session."},
            {"ts": "00:00:06", "start": 6.0, "end": 10.0, "speaker": "Speaker_02", "text": "Thank you, glad to be here with the team."},
            {"ts": "00:00:11", "start": 11.0, "end": 15.0, "speaker": "Speaker_01", "text": "Let us dive into the first agenda item."},
        ]
        blocks = healer.heal_and_coalesce(segments)
        self.assertEqual(len(blocks), 3)
        self.assertEqual(blocks[0]["speaker"], "Speaker_01")
        self.assertEqual(blocks[1]["speaker"], "Speaker_02")
        self.assertEqual(blocks[2]["speaker"], "Speaker_01")

    def test_api_playbooks_validate_endpoint(self):
        """POST /api/playbooks/validate correctly checks schemas."""
        client = app.test_client()

        # Valid payload
        resp_good = client.post("/api/playbooks/validate", json={
            "name": "planning_board",
            "default_role": "Board Member",
            "roles": ["Chair", "Board Member"],
            "cues": {"chair": ["open the hearing"]}
        })
        self.assertEqual(resp_good.status_code, 200)
        self.assertTrue(resp_good.get_json()["valid"])

        # Invalid payload
        resp_bad = client.post("/api/playbooks/validate", json={"name": "incomplete"})
        self.assertEqual(resp_bad.status_code, 400)
        self.assertFalse(resp_bad.get_json()["valid"])

    def test_playbook_loader_highest_version_resolution(self):
        """PlaybookLoader dynamically loads the highest versioned file (e.g. v2 > v1)."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            v1_data = {
                "name": "test_board",
                "version": "v1",
                "default_role": "Member",
                "roles": ["Member"],
                "cues": {"member": ["motion"]}
            }
            v2_data = {
                "name": "test_board",
                "version": "v2",
                "default_role": "Member",
                "roles": ["Member", "Chair"],
                "cues": {"member": ["motion"]}
            }
            (td_path / "test_board_v1.json").write_text(json.dumps(v1_data))
            (td_path / "test_board_v2.json").write_text(json.dumps(v2_data))

            custom_loader = PlaybookLoaderV3(playbooks_dir=td_path)
            pb = custom_loader.load("test_board")
            self.assertEqual(pb.version, "v2")
            self.assertIn("Chair", pb.roles)


if __name__ == "__main__":
    unittest.main()
