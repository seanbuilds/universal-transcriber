"""Empirical Adversarial Test Suite for R2 and R3 Findings (v1).

Tests and reproduces:
1. Centroid hypersphere shrinkage and drift in diarize_v1.py (R2-02, R2-03, R2-06, R2-07, R2-08)
2. Disconnection of SpeakerDatabase from pipeline_v1.py (R2-01)
3. Absence of temporal gap bounds and healing flaws in healer_v1.py (R2-09, R2-10, R2-11, R2-13)
4. Unanchored substring matching and schema flaws in loader_v1.py and playbooks (R3-01, R3-03, R3-04, R3-05)
"""

import math
import tempfile
import unittest
import inspect
from pathlib import Path

from src.engine.diarize_v1 import SpeakerDatabase, cosine_similarity
from src.engine.healer_v1 import TurnCoalescer, deduplicate_overlap, clean_stutters
try:
    from src.engine.pipeline_v1 import TranscriptionPipeline
except ImportError:
    from src.engine.archive.pipeline_v1 import TranscriptionPipeline
from src.playbooks.loader_v1 import PlaybookLoader, Playbook


class TestAdversarialDiarizationR2(unittest.TestCase):
    """Adversarial stress-testing of SpeakerDatabase and cosine similarity."""

    def test_r2_02_centroid_hypersphere_shrinkage(self):
        """Verify that arithmetic rolling average causes centroid L2 norm to shrink below 1.0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "shrinkage_db.json"
            db = SpeakerDatabase(db_path=db_path, similarity_threshold=0.80)

            # Start with a unit vector along axis 0 in R^16
            d = 16
            v0 = [0.0] * d
            v0[0] = 1.0
            spk_id = db.match_or_register(v0, session_id="s1")
            self.assertEqual(spk_id, "Speaker_A")

            # Check initial norm
            initial_emb = db.data["profiles"][0]["embedding"]
            initial_norm = math.sqrt(sum(x * x for x in initial_emb))
            self.assertAlmostEqual(initial_norm, 1.0, places=5)

            # Sequentially add 25 distinct unit vectors within cosine threshold (~0.85 similarity)
            # Create vectors: v_k = normalize(v0 + 0.5 * e_k)
            for k in range(1, 26):
                axis = (k % (d - 1)) + 1
                raw_v = list(v0)
                raw_v[axis] = 0.5
                norm = math.sqrt(sum(x * x for x in raw_v))
                unit_v = [x / norm for x in raw_v]

                matched_id = db.match_or_register(unit_v, session_id=f"s_{k}")
                self.assertEqual(matched_id, "Speaker_A")

            final_emb = db.data["profiles"][0]["embedding"]
            final_norm = math.sqrt(sum(x * x for x in final_emb))

            # The stored centroid has shrunk strictly inside the hypersphere (< 1.0)
            print(f"\n[R2-02] Final centroid L2 norm after 25 updates: {final_norm:.6f} (< 1.0)")
            self.assertLess(final_norm, 0.96)
            self.assertGreater(final_norm, 0.5)

    def test_r2_03_centroid_hypersphere_drift_and_speaker_cannibalization(self):
        """Verify that arithmetic rolling average drifts toward a distinct speaker and cannibalizes it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "drift_db.json"
            # Configured threshold is 0.82
            db = SpeakerDatabase(db_path=db_path, similarity_threshold=0.82)

            d = 128
            # Speaker 1 true centroid mu1: unit vector along axis 0
            mu1 = [0.0] * d
            mu1[0] = 1.0

            # Speaker 2 true centroid mu2: vector at angle theta where cos(theta) = 0.750
            mu2 = [0.0] * d
            mu2[0] = 0.750
            mu2[1] = math.sqrt(1.0 - 0.750 ** 2)  # ~0.6614378

            initial_sim = cosine_similarity(mu1, mu2)
            self.assertAlmostEqual(initial_sim, 0.750, places=3)
            self.assertLess(initial_sim, 0.82, "Speakers 1 and 2 must initially be distinct")

            # Register Speaker 1
            spk1_id = db.match_or_register(mu1, session_id="s1")
            self.assertEqual(spk1_id, "Speaker_A")

            # Simulate 26 sequential utterances with slight natural drift toward mu2.
            # Each utterance is close to the current centroid (cos >= 0.85), but biased along the geodesic toward mu2.
            steps = 26
            for step in range(1, steps + 1):
                curr_centroid = db.data["profiles"][0]["embedding"]
                # Interpolate between current centroid and mu2
                # alpha controls step size along geodesic
                interp = [(1.0 - 0.08) * c + 0.08 * m for c, m in zip(curr_centroid, mu2)]
                norm_interp = math.sqrt(sum(x * x for x in interp))
                sample = [x / norm_interp for x in interp]

                sim_to_curr = cosine_similarity(sample, curr_centroid)
                self.assertGreaterEqual(sim_to_curr, 0.82, f"Step {step} must be accepted by Speaker_A")

                assigned = db.match_or_register(sample, session_id=f"step_{step}")
                self.assertEqual(assigned, "Speaker_A")

            # Now inspect the migrated centroid
            final_centroid = db.data["profiles"][0]["embedding"]
            sim_final_to_mu2 = cosine_similarity(final_centroid, mu2)
            print(f"\n[R2-03] Cosine similarity between drifted centroid and Speaker 2's voice: {sim_final_to_mu2:.4f}")
            self.assertGreater(sim_final_to_mu2, 0.82, "Centroid has drifted past the 0.82 threshold toward Speaker 2")

            # Catastrophic failure: Speaker 2 now speaks their ground truth voice mu2
            spk2_assigned = db.match_or_register(mu2, session_id="speaker_2_turn")
            print(f"[R2-03] Speaker 2 ground-truth voice classified as: {spk2_assigned}")
            # Speaker 2 is CANNIBALIZED into Speaker_A!
            self.assertEqual(spk2_assigned, "Speaker_A", "Speaker 2 must be falsely cannibalized into Speaker_A")

    def test_r2_06_silence_zero_vector_profile_proliferation(self):
        """Verify that silence zero vectors spawn a new speaker profile on every single segment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "silence_db.json"
            db = SpeakerDatabase(db_path=db_path, similarity_threshold=0.82)

            zero_vector = [0.0] * 128
            # 5 consecutive silent segments
            assigned_ids = [db.match_or_register(zero_vector, session_id="s1") for _ in range(5)]

            print(f"\n[R2-06] Silence zero vectors registered IDs: {assigned_ids}")
            self.assertEqual(assigned_ids, ["Speaker_A", "Speaker_B", "Speaker_C", "Speaker_D", "Speaker_E"])
            self.assertEqual(len(db.data["profiles"]), 5)

    def test_r2_07_synchronous_disk_writes_per_segment(self):
        """Verify that match_or_register executes synchronous disk save on every call."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "save_db.json"
            db = SpeakerDatabase(db_path=db_path, similarity_threshold=0.82)

            save_count = 0
            original_save = db.save

            def counting_save():
                nonlocal save_count
                save_count += 1
                original_save()

            db.save = counting_save

            v = [1.0] + [0.0] * 15
            for i in range(10):
                db.match_or_register(v, session_id=f"seg_{i}")

            print(f"\n[R2-07] save() called {save_count} times for 10 segments")
            self.assertEqual(save_count, 10, "save() was not called on every single segment")

    def test_r2_08_discontinuous_speaker_naming_scheme(self):
        """Verify discontinuous transition from Speaker_Z to Speaker_27."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "naming_db.json"
            db = SpeakerDatabase(db_path=db_path, similarity_threshold=0.99)

            d = 32
            ids = []
            for i in range(28):
                v = [0.0] * d
                v[i % d] = 1.0
                # ensure orthogonality so each is a new profile
                v_ortho = [0.0] * 35
                v_ortho[i] = 1.0
                spk = db.match_or_register(v_ortho)
                ids.append(spk)

            print(f"\n[R2-08] Profile 25: {ids[24]}, Profile 26: {ids[25]}, Profile 27: {ids[26]}")
            self.assertEqual(ids[25], "Speaker_Z")
            self.assertEqual(ids[26], "Speaker_27")  # abrupt switch from letter to integer


class TestAdversarialPipelineR2(unittest.TestCase):
    """Adversarial verification of the pipeline and diarization integration."""

    def test_r2_01_speaker_database_total_disconnection_from_pipeline(self):
        """Verify that SpeakerDatabase is initialized in pipeline_v1.py but never used in process()."""
        pipeline = TranscriptionPipeline()
        self.assertTrue(hasattr(pipeline, "speaker_db"))

        # Inspect source code of TranscriptionPipeline.process
        process_src = inspect.getsource(pipeline.process)

        # Check for any reference to self.speaker_db inside process()
        self.assertNotIn("speaker_db", process_src, "speaker_db should not appear in process() body")
        self.assertNotIn("match_or_register", process_src)
        self.assertNotIn("get_display_name", process_src)
        self.assertNotIn("list_speakers", process_src)
        print("\n[R2-01] Verified: TranscriptionPipeline.process contains 0 references to speaker_db.")


class TestAdversarialHealerR2(unittest.TestCase):
    """Adversarial verification of TurnCoalescer and healing heuristics in healer_v1.py."""

    def test_r2_09_absence_of_temporal_bounds_swallows_15_minute_recess(self):
        """Verify that segments separated by a 15-minute recess are merged into a single block."""
        pb = Playbook({
            "name": "test",
            "default_role": "Chair",
            "roles": ["Chair"],
            "cues": {}
        })
        coalescer = TurnCoalescer(playbook=pb)

        # Seg 1: Minute 5 (00:05:00), Chair declares recess
        # Seg 2: Minute 20 (00:20:00), 15 minutes later, Chair calls back to order
        segments = [
            {"ts": "00:05:00", "start": 300.0, "end": 310.0, "text": "The meeting will stand in recess for fifteen minutes."},
            {"ts": "00:20:00", "start": 1200.0, "end": 1215.0, "text": "The committee is now back in session."}
        ]

        healed = coalescer.heal_and_coalesce(segments)
        print(f"\n[R2-09] Healed block count across 15-min gap: {len(healed)}")
        # Because speaker string equals "Chair" and there are no temporal gap checks,
        # both segments are merged into 1 block!
        self.assertEqual(len(healed), 1, "Failed: 15-minute recess was NOT swallowed into 1 block")
        self.assertEqual(healed[0]["start"], 300.0)
        self.assertEqual(healed[0]["end"], 1215.0)
        self.assertEqual(healed[0]["ts"], "00:05:00")
        self.assertIn("fifteen minutes.", healed[0]["text"])
        self.assertIn("back in session.", healed[0]["text"])

    def test_r2_09_general_speech_monolith(self):
        """Verify that general_speech merges 100 separate turns across 2 hours into 1 block."""
        loader = PlaybookLoader()
        pb = loader.load("general_speech")
        coalescer = TurnCoalescer(playbook=pb)

        # 100 segments with 30-second gaps in between
        segments = []
        for i in range(100):
            start = i * 60.0
            end = start + 20.0
            segments.append({
                "ts": f"00:{i:02d}:00",
                "start": start,
                "end": end,
                "text": f"This is utterance number {i} spoken by an attendee."
            })

        healed = coalescer.heal_and_coalesce(segments)
        print(f"[R2-09] General speech: 100 turns collapsed into {len(healed)} block(s)")
        self.assertEqual(len(healed), 1, "100 turns across 100 minutes should collapse into exactly 1 monolith block")

    def test_r2_10_sticky_speaker_state_latching(self):
        """Verify that once a role is latched (e.g. Chair), subsequent speakers without cues are merged into Chair."""
        loader = PlaybookLoader()
        pb = loader.load("municipal_meetings")
        coalescer = TurnCoalescer(playbook=pb)

        segments = [
            {"ts": "00:01:00", "start": 60.0, "end": 70.0, "text": "I now call this meeting to order with a quorum."},
            {"ts": "00:01:15", "start": 75.0, "end": 85.0, "text": "Good evening, I am a citizen from Elm Street commenting on traffic."},
            {"ts": "00:01:30", "start": 90.0, "end": 100.0, "text": "I also agree with the previous neighbor about the speed bumps."}
        ]

        healed = coalescer.heal_and_coalesce(segments)
        print(f"\n[R2-10] Number of healed blocks: {len(healed)}, speaker: {healed[0]['speaker']}")
        # All three segments get attributed to Chair!
        self.assertEqual(len(healed), 1)
        self.assertEqual(healed[0]["speaker"], "Chair")
        self.assertIn("citizen from Elm Street", healed[0]["text"])
        self.assertIn("speed bumps", healed[0]["text"])

    def test_r2_11_greedy_regex_name_extraction(self):
        """Verify that yield regex greedily captures entire trailing sentence as speaker name."""
        loader = PlaybookLoader()
        pb = loader.load("municipal_meetings")
        coalescer = TurnCoalescer(playbook=pb)

        segments = [
            {"ts": "00:01:00", "start": 60.0, "end": 70.0, "text": "I will turn the floor over to Dr. Sarah Shannon to present the comprehensive district budget."},
            {"ts": "00:01:15", "start": 75.0, "end": 85.0, "text": "Thank you, our budget this year reflects substantial growth."}
        ]

        healed = coalescer.heal_and_coalesce(segments)
        print(f"\n[R2-11] Extracted speaker name: '{healed[1]['speaker']}'")
        self.assertEqual(
            healed[1]["speaker"],
            "Dr. Sarah Shannon To Present The Comprehensive District Budget"
        )

    def test_r2_12_roll_call_attribution_inversion(self):
        """Verify that Chair roll call question is attributed to member, and member response to Member Motion."""
        loader = PlaybookLoader()
        pb = loader.load("municipal_meetings")
        coalescer = TurnCoalescer(playbook=pb)

        segments = [
            {"ts": "00:01:00", "start": 60.0, "end": 64.0, "text": "Craig MacLellan, are you present?"},
            {"ts": "00:01:05", "start": 65.0, "end": 67.0, "text": "Present."}
        ]

        healed = coalescer.heal_and_coalesce(segments)
        print(f"\n[R2-12] Roll call question speaker: '{healed[0]['speaker']}', response speaker: '{healed[1]['speaker']}'")
        self.assertEqual(healed[0]["speaker"], "Craig MacLellan")  # Inverted: question asked by Chair assigned to member
        self.assertEqual(healed[1]["speaker"], "Member Motion")     # Response "Present." assigned to cue role

    def test_r2_14_grammatical_stutter_mutilation_and_comma_blindness(self):
        """Verify that clean_stutters mutilates legitimate doublings and misses comma-separated stutters."""
        t1 = "I know that that is true."
        t2 = "He had had a long day."
        t3 = "we, we will move forward."

        c1 = clean_stutters(t1)
        c2 = clean_stutters(t2)
        c3 = clean_stutters(t3)

        print(f"\n[R2-14] 'that that' -> '{c1}', 'had had' -> '{c2}', comma stutter -> '{c3}'")
        self.assertEqual(c1, "I know that is true.")  # Grammatical doubling deleted
        self.assertEqual(c2, "He had a long day.")    # Grammatical doubling deleted
        self.assertEqual(c3, "we, we will move forward.")  # Comma stutter missed

    def test_r2_13_overlap_deduplication_word_swallowing(self):
        """Verify destructive word swallowing when k=1 in deduplicate_overlap."""
        prev = "We have to consider the budget."
        nxt = "Budget considerations are important."
        cleaned = deduplicate_overlap(prev, nxt)
        print(f"\n[R2-13] Deduplicate overlap swallowed 'Budget': '{cleaned}'")
        self.assertEqual(cleaned, "considerations are important.")


class TestAdversarialPlaybooksR3(unittest.TestCase):
    """Adversarial verification of loader_v1.py and domain playbook JSON files."""

    def setUp(self):
        self.loader = PlaybookLoader()

    def test_r3_02_silent_fallback_on_corrupt_playbook(self):
        """Verify that syntax errors in a custom playbook cause silent fallback without warning or exception."""
        with tempfile.TemporaryDirectory() as tmpdir:
            p_dir = Path(tmpdir)
            (p_dir / "broken_v1.json").write_text("{ corrupt json: [ ", encoding="utf-8")
            (p_dir / "general_speech_v1.json").write_text("{\"name\": \"general_speech\", \"roles\": [\"Speaker\"]}", encoding="utf-8")

            loader = PlaybookLoader(playbooks_dir=p_dir)
            pb = loader.load("broken")
            print(f"\n[R3-02] Corrupt playbook loaded as: '{pb.name}'")
            self.assertEqual(pb.name, "general_speech")

    def test_r3_03_unanchored_substring_polysemy_collisions(self):
        """Verify that unanchored substring matching causes false positive role assignments."""
        pb_mun = self.loader.load("municipal_meetings")

        # In municipal_meetings: "second", "present", "aye" in member_motion
        # 1. "Wait a second"
        role1 = pb_mun.detect_role("Wait a second before voting.")
        print(f"\n[R3-03] 'Wait a second...' detected as: {role1}")
        self.assertEqual(role1, "Member Motion")

        # 2. "secondary school"
        role2 = pb_mun.detect_role("The secondary school enrollment has increased.")
        print(f"[R3-03] 'The secondary school...' detected as: {role2}")
        self.assertEqual(role2, "Member Motion")

        # 3. "presentation"
        role3 = pb_mun.detect_role("I will begin the presentation now.")
        print(f"[R3-03] 'I will begin the presentation now.' detected as: {role3}")
        self.assertEqual(role3, "Member Motion")

        # 4. "player" containing "aye"
        role4 = pb_mun.detect_role("He is an outstanding team player.")
        print(f"[R3-03] 'He is an outstanding team player.' detected as: {role4}")
        self.assertEqual(role4, "Member Motion")

        # In academic_lecture: "professor" and "what about" in student cues
        pb_acad = self.loader.load("academic_lecture")
        # 5. Lecturer says: "As a professor of physics, I welcome you."
        role5 = pb_acad.detect_role("As a professor of physics, I welcome you.")
        print(f"[R3-03] Lecturer saying 'As a professor...' detected as: {role5}")
        self.assertEqual(role5, "Student")

        # 6. Lecturer says: "What about the laws of thermodynamics?"
        role6 = pb_acad.detect_role("What about the laws of thermodynamics?")
        print(f"[R3-03] Lecturer asking 'What about...' detected as: {role6}")
        self.assertEqual(role6, "Student")

    def test_r3_04_schema_role_inconsistencies(self):
        """Verify that cue keys emit roles not declared in the playbook roles list."""
        pb_mun = self.loader.load("municipal_meetings")
        declared_roles_mun = set(pb_mun.roles)

        # "member_motion" cue emits "Member Motion"
        emitted_role_motion = pb_mun.detect_role("So moved. Motion to approve.")
        print(f"\n[R3-04] Emitted: '{emitted_role_motion}', Declared in schema: {declared_roles_mun}")
        self.assertNotIn(emitted_role_motion, declared_roles_mun)

        # "superintendent_or_manager" cue emits "Superintendent Or Manager"
        emitted_role_supt = pb_mun.detect_role("Here is the superintendent report.")
        print(f"[R3-04] Emitted: '{emitted_role_supt}', Declared in schema: {declared_roles_mun}")
        self.assertNotIn(emitted_role_supt, declared_roles_mun)

        # In corporate_meeting: declared roles are ["Meeting Leader", "Presenter", "Team Member"]
        pb_corp = self.loader.load("corporate_meeting")
        declared_roles_corp = set(pb_corp.roles)
        emitted_role_contrib = pb_corp.detect_role("A quick update from my end on this ticket.")
        print(f"[R3-04] Corporate emitted: '{emitted_role_contrib}', Declared: {declared_roles_corp}")
        self.assertNotIn(emitted_role_contrib, declared_roles_corp)

    def test_r3_05_fragile_roster_matching_on_common_words(self):
        """Verify that common English words matching a member's last name trigger false roster match."""
        pb_mun = self.loader.load("municipal_meetings")
        # Roster includes "Doran Hull". Last name is "Hull" (len 4 > 3).
        text = "The boat sustained damage to the hull during the storm."
        match = pb_mun.match_roster(text)
        print(f"\n[R3-05] Roster match for 'The boat sustained damage to the hull...': {match}")
        self.assertEqual(match, "Doran Hull")

    def test_r3_01_unvalidated_playbook_schema_failure(self):
        """Verify that invalid schema structures cause runtime crashes or catastrophic matching."""
        # 1. Cues as list raises AttributeError
        bad_pb_1 = Playbook({"cues": ["chair", "speaker"]})
        with self.assertRaises(AttributeError):
            bad_pb_1.detect_role("Call to order")

        # 2. Cue phrase as string instead of list of strings: iterates single characters!
        bad_pb_2 = Playbook({"cues": {"chair": "open"}})
        # 'o', 'p', 'e', 'n' are now individual phrase cues!
        # Any sentence containing 'e' matches "Chair"!
        role = bad_pb_2.detect_role("the cat sat")  # contains 'e'
        print(f"\n[R3-01] Single-character iteration match: {role}")
        self.assertEqual(role, "Chair")


if __name__ == "__main__":
    unittest.main()
