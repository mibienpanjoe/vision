"""Score stored specifications against the annotated corpus cases.

Missing and incorrect inclusions are kept apart. A canonical trait counts as an
expected fact when it is on that fact's subject and shares a content word with
its value; one that instead matches a fact the case excludes is incorrect, and
those (temporal, attribution, modality) plus any evidence beyond the reading
boundary are blocking. Canonical traits matching no annotation are reported as
unannotated extras, not scored.
"""

import json
import re
from pathlib import Path

DATA = json.loads((Path(__file__).parent / "fixtures/narrative/expected.json").read_text(encoding="utf-8"))
FACTS = {f["id"]: f for f in DATA["facts"]}
SUBJECT_TEXT = {"arthur": "Arthur", "house": "the house by the ash tree", "mira": "Mira", "compass": "the brass compass",
                "sword": "the silver sword", "wren": "Wren", "elodie": "Élodie", "brann": "Brann"}
LABELS = {"arthur": "Arthur", "house": "house by the ash tree", "mira": "Mira", "compass": "brass compass",
          "sword": "silver sword", "wren": "Wren", "elodie": "Élodie", "brann": "Brann"}
MOMENT_TEXT = {"child": "at ten", "war": "during the war", "journey": "travelling home after the war",
               "dinner": "at dinner after the war", "spring": "in the spring after the war"}
STOP = {"the", "and", "with", "still", "his", "her", "its", "possibly", "persists", "established", "ending"}


def words(value: str) -> set[str]:
    return {w for w in re.findall(r"[^\W\d_]{3,}", value.casefold()) if w not in STOP}


def query(case) -> str:
    subject = SUBJECT_TEXT.get(case["subject"], "the captain")
    return f"{subject} {MOMENT_TEXT[case['event']]}"


def members(spec) -> list[dict]:
    return [spec["subject"], *spec["participants"], *spec["world"]]


def evaluate(case, body, passage_chapters: dict) -> dict:
    """`passage_chapters` maps passage id -> chapter ordinal for the stored document."""
    report = {"case": case["id"], "expected": case["outcome"], "outcome": body["outcome"], "missing": [],
              "incorrect": [], "extras": [], "disputed": [], "leaks": [], "unknown_kept": []}
    if body["outcome"] != "resolved":
        report["missing"] = list(case["canonical"])
        return report
    spec = body["data"]
    by_label = {m["entity"]["label"]: m for m in members(spec)}
    member = by_label.get(LABELS.get(case["subject"], ""), spec["subject"])
    canonical = [t for t in member["traits"] if t["status"] == "canonical"]
    disputed = [t for t in member["traits"] if t["status"] == "disputed"]
    expected = [FACTS[f] for f in case["canonical"]] + [FACTS[f] for f in case["inferred"] if f in FACTS]
    for fid in case["canonical"]:
        if not any(words(FACTS[fid]["value"]) & words(v) for t in canonical for v in t["values"]):
            report["missing"].append(fid)
    for trait in canonical:
        for value in trait["values"]:
            if any(words(f["value"]) & words(value) for f in expected):
                continue
            wrong = [f for f in case["excluded"] + case["disputed"] if f in FACTS and FACTS[f]["subject"] == case["subject"]
                     and words(FACTS[f]["value"]) & words(value)]
            (report["incorrect"] if wrong else report["extras"]).append(
                {"attribute": trait["attribute"], "value": value, "matches": wrong})
    if case["disputed"]:
        values = {v.casefold() for t in disputed for v in t["values"]}
        report["disputed"] = [f for f in case["disputed"] if not words(FACTS[f]["value"]) & set().union(*map(words, values))]
    for m in members(spec):
        for trait in m["traits"]:
            for span in trait["evidence"]:
                chapter = passage_chapters.get(span["passage_id"])
                if case["through_chapter"] is not None and (chapter or 0) > case["through_chapter"]:
                    report["leaks"].append(span["quote"])
    report["unknown_kept"] = [u for u in case["unknown"] if u in {"eyes", "attire", "adult_hair"}
                              and (u.replace("adult_", "") in member["unknown"])]
    return report


def summary(reports: list[dict]) -> dict:
    expected = sum(len(next(c for c in DATA["cases"] if c["id"] == r["case"])["canonical"]) for r in reports)
    missing = sum(len(r["missing"]) for r in reports)
    return {"cases": len(reports), "outcome_matches": sum(r["expected"] == r["outcome"] for r in reports),
            "expected_canonical": expected, "found_canonical": expected - missing, "missing": missing,
            "incorrect": sum(len(r["incorrect"]) for r in reports), "extras": sum(len(r["extras"]) for r in reports),
            "disputes_missed": sum(len(r["disputed"]) for r in reports), "leaks": sum(len(r["leaks"]) for r in reports),
            "blocking": [r["case"] for r in reports if r["incorrect"] or r["leaks"]]}
