"""Validate the annotated corpus; these checks do not perform extraction."""

import hashlib
import json
import re
import unittest
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "narrative"


class NarrativeFixtureTests(unittest.TestCase):
    def test_source_identity_and_exact_codepoint_spans(self):
        story = (FIXTURE / "story.md").read_bytes()
        corpus = json.loads((FIXTURE / "expected.json").read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256(story).hexdigest(), corpus["source_sha256"])
        text = story.decode("utf-8")
        self.assertEqual(corpus["language"], "en")
        self.assertEqual(corpus["offset_unit"], "unicode_code_point")
        self.assertTrue(corpus["provenance"]["synthetic"])
        self.assertTrue(corpus["fixture_version"])
        passages = {p["id"]: p for p in corpus["passages"]}
        self.assertEqual(len(passages), len(corpus["passages"]))
        previous_end = 0
        for p in passages.values():
            with self.subTest(passage=p["id"]):
                self.assertLessEqual(previous_end, p["source_start"])
                self.assertEqual(text[p["source_start"] : p["source_end"]], p["text"])
                self.assertLess(p["source_start"], p["source_end"])
                headings = list(
                    re.finditer(r"^## Chapter (\d+)", text[: p["source_start"]], re.M)
                )
                self.assertEqual(p["chapter"], int(headings[-1].group(1)))
                previous_end = p["source_end"]
        spans = {s["id"]: s for s in corpus["spans"]}
        self.assertEqual(len(spans), len(corpus["spans"]))
        for span in spans.values():
            with self.subTest(span=span["id"]):
                passage = passages[span["passage_id"]]["text"]
                self.assertIs(type(span["start"]), int)
                self.assertIs(type(span["end"]), int)
                self.assertTrue(0 <= span["start"] < span["end"] <= len(passage))
                self.assertEqual(passage[span["start"] : span["end"]], span["quote"])
        # Supplementary and decomposed text must remain literal source content.
        self.assertIn("🦊", text)
        self.assertIn("Élodie", text)
        self.assertIn("e\u0301", text)

    def test_annotation_references_and_expected_matrix(self):
        corpus = json.loads((FIXTURE / "expected.json").read_text(encoding="utf-8"))
        collections = ("entities", "events", "facts", "scenes", "cases", "spans")
        ids = {}
        for group in collections:
            records = corpus[group]
            ids[group] = {r["id"] for r in records}
            self.assertEqual(len(ids[group]), len(records), group)
            self.assertTrue(records, group)

        def check_refs(values, group):
            self.assertTrue(set(values) <= ids[group], (values, group))

        for group in ("entities", "events", "facts", "scenes"):
            for record in corpus[group]:
                with self.subTest(group=group, record=record["id"]):
                    self.assertTrue(record["evidence"])
                    check_refs(record["evidence"], "spans")
        for entity in corpus["entities"]:
            for alias in entity.get("aliases", []):
                check_refs(alias["evidence"], "spans")
        for event in corpus["events"]:
            check_refs(event["participants"], "entities")
        for relation in corpus["temporal_relations"]:
            check_refs([relation["from"], relation["to"]], "events")
            check_refs(relation["evidence"], "spans")
            self.assertIn(relation["relation"], ("before", "overlaps", "unknown"))
        for fact in corpus["facts"]:
            check_refs([fact["subject"]], "entities")
            check_refs(fact["events"], "events")
            check_refs(fact.get("conflicts_with", []), "facts")
            self.assertIn(
                fact["support"],
                (
                    "explicit",
                    "inferred",
                    "rumor",
                    "metaphor",
                    "negated",
                    "dream",
                    "disputed",
                ),
            )
        for scene in corpus["scenes"]:
            check_refs(scene["participants"], "entities")
            check_refs(scene["objects"], "entities")
            check_refs(scene["excluded_participants"], "entities")
            check_refs(scene["excluded_objects"], "entities")
            self.assertTrue(
                set(scene["participants"]).isdisjoint(scene["excluded_participants"])
            )
            self.assertTrue(set(scene["objects"]).isdisjoint(scene["excluded_objects"]))
            check_refs([scene["event"]], "events")
        for case in corpus["cases"]:
            with self.subTest(case=case["id"]):
                if case["subject"] is None:
                    self.assertEqual(case["outcome"], "needs_context")
                    self.assertGreater(len(case["subject_candidates"]), 1)
                    check_refs(case["subject_candidates"], "entities")
                    check_refs(case["candidate_evidence"], "spans")
                else:
                    check_refs([case["subject"]], "entities")
                check_refs([case["event"]], "events")
                sets = [
                    set(case[key])
                    for key in ("canonical", "inferred", "excluded", "disputed")
                ]
                for index, values in enumerate(sets):
                    check_refs(values, "facts")
                    self.assertTrue(
                        all(values.isdisjoint(other) for other in sets[index + 1 :])
                    )
                for addition in case["creative_additions"]:
                    self.assertEqual(addition["support"], "creative")
                    self.assertTrue(addition["reason"])
                self.assertTrue(case["reason"])
                self.assertIn(
                    case["outcome"],
                    ("resolved", "needs_context", "insufficient_evidence"),
                )
        for rule in corpus["identity_rules"]:
            check_refs(rule["candidates"], "entities")
            check_refs(rule["evidence"], "spans")
            if rule["resolved_at_chapter"] is not None:
                self.assertLess(
                    rule["unresolved_through_chapter"], rule["resolved_at_chapter"]
                )
            else:
                self.assertTrue(rule["resolution"])

    def test_cutoff_dependencies_and_scope_categories(self):
        corpus = json.loads((FIXTURE / "expected.json").read_text(encoding="utf-8"))
        passages = {p["id"]: p for p in corpus["passages"]}
        spans = {s["id"]: s for s in corpus["spans"]}
        facts = {f["id"]: f for f in corpus["facts"]}
        for case in corpus["cases"]:
            for span_id in case.get("candidate_evidence", []):
                self.assertLessEqual(
                    passages[spans[span_id]["passage_id"]]["chapter"],
                    case["through_chapter"],
                )
            for key in ("canonical", "inferred", "disputed"):
                for fact_id in case[key]:
                    fact = facts[fact_id]
                    self.assertEqual(fact["subject"], case["subject"])
                    for span_id in fact["evidence"]:
                        chapter = passages[spans[span_id]["passage_id"]]["chapter"]
                        self.assertLessEqual(chapter, case["through_chapter"])
                    if key in ("inferred", "disputed"):
                        self.assertEqual(fact["support"], key)
                    if key == "canonical":
                        self.assertEqual(fact["support"], "explicit")
                        self.assertIn(case["event"], fact["events"])
        self.assertTrue(
            {
                "explicit",
                "inferred",
                "rumor",
                "metaphor",
                "negated",
                "dream",
                "disputed",
            }
            <= {f["support"] for f in facts.values()}
        )
        self.assertTrue(
            {"identity", "acquired", "interval", "scene"}
            <= {f["kind"] for f in facts.values()}
        )
        self.assertTrue(
            {"character", "place", "object"} <= {e["kind"] for e in corpus["entities"]}
        )
        for relation in corpus["temporal_relations"]:
            self.assertNotEqual(relation["from"], relation["to"])
        # Every body paragraph must be represented exactly once, with no omissions.
        story = (FIXTURE / "story.md").read_text(encoding="utf-8")
        paragraphs = [
            m.group()
            for m in re.finditer(r"[^\n]+(?:\n(?!\n)[^\n]+)*", story)
            if not m.group().startswith("#")
        ]
        self.assertEqual(paragraphs, [p["text"] for p in corpus["passages"]])


if __name__ == "__main__":
    unittest.main()
