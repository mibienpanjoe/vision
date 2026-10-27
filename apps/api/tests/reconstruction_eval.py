"""Versioned, curated annotation matching for the synthetic corpus.

Match the subject, attribute/component and complete annotated value alternatives.
This is a deterministic benchmark matcher, not a general semantic judge. Unknown
paraphrases are unscored extras; historical word-overlap reports are not comparable.
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
SCORER_VERSION = "annotation-match-v3"
STOP = {"the", "and", "with", "still", "his", "her", "its", "possibly", "persists", "established", "ending"}


def words(value: str) -> set[str]:
    return {w for w in re.findall(r"[^\W\d_]{3,}", value.casefold()) if w not in STOP}


def query(case) -> str:
    subject = SUBJECT_TEXT.get(case["subject"], "the captain")
    return f"{subject} {MOMENT_TEXT[case['event']]}"


def members(spec) -> list[dict]:
    return [spec["subject"], *spec["participants"], *spec["world"]]


# Deliberately curated alternatives, rather than treating any shared word as a fact.
MATCHES = {
    "child-hair": (r"hair(?:_color|_colour)?", ["chestnut", "chestnut hair"]),
    "child-cheek": (r"left_cheek(?:_state|_condition|_mark(?:ed)?)?", ["unmarked", "unmarked left cheek"]),
    "late-child-cheek": (r"left_cheek(?:_state|_condition|_mark(?:ed)?)?", ["unmarked", "unmarked left cheek"]),
    "child-coat": (r"(?:attire|clothing|coat|coat_worn|worn_items)", ["blue wool coat"]),
    "war-scar": (r"left_cheek(?:_scar|_mark|_state|_condition)?", ["scar", "scarred", "left cheek scar"]),
    "home-scar": (r"left_cheek(?:_scar|_mark|_state|_condition)?", ["scar", "scarred", "scar still visible", "left cheek scar", "left cheek scar visible"]),
    "road-scar-inference": (r"left_cheek(?:_scar|_mark|_state|_condition)?", ["scar", "scar possibly persists; no ending established"]),
    "war-armor": (r"(?:attire|clothing|armor|armour|worn_items)", ["steel armor", "steel armour"]),
    "home-no-armor": (r"(?:attire|clothing|armor|armour|worn_items)", ["steel armor", "steel armour"]),
    "home-shirt": (r"(?:attire|clothing|shirt|worn_items)", ["plain linen shirt"]),
    "golden-eyes": (r"eye(?:s|_color|_colour)?", ["golden", "golden eyes"]),
    "eyes-green": (r"eye(?:s|_color|_colour)?", ["green", "green eyes"]),
    "eyes-blue": (r"eye(?:s|_color|_colour)?", ["blue", "blue eyes"]),
    "iron-body": (r"body(?:_appearance)?", ["wolf made of iron"]),
    "wings": (r"(?:body|wings)", ["wings"]),
    "roof-intact": (r"roof(?:_condition|_state)?", ["intact slate", "intact", "intact slate roof"]),
    "roof-destroyed": (r"roof(?:_condition|_state)?", ["destroyed", "destroyed slate roof"]),
    "roof-missing": (r"roof(?:_condition|_state)?", ["missing", "absent", "still missing"]),
    "roof-restored": (r"roof(?:_condition|_state)?", ["restored", "restored slate", "restored slate roof"]),
    "compass-brass": (r"(?:material|compass_material)", ["brass"]),
    "sword-silver": (r"(?:material|sword_material|blade_material)", ["silver"]),
    "mira-compass": (r"(?:held_object|holding|carried_object|carries)", ["compass", "brass compass"]),
    "home-compass": (r"(?:held_object(?:_at_dinner)?|holding|carried_object|carries)",
                     ["brass compass", "holding her brass compass", "holding a brass compass"]),
    "brann-sword": (r"(?:held_object|holding|carried_object|carries)", ["silver sword", "sword"]),
    "home-light": (r"(?:lighting|light)", ["warm candlelight"]),
}


def normalized(value):
    return " ".join(re.findall(r"[^\W\d_]+", value.casefold()))


def matches(fid, trait, value):
    attribute, alternatives = MATCHES[fid]
    component = bool(re.fullmatch(attribute, trait["attribute"]))
    if fid in {"war-scar", "home-scar"} and trait["attribute"] == "cheek_scar":
        component = normalized(value).startswith("left cheek ")
    return component and normalized(value) in {
        normalized(v) for v in alternatives}


def evaluate(case, body, passage_chapters: dict) -> dict:
    """Score output semantics against curated alternatives; evidence boundaries separately."""
    report = {"case": case["id"], "expected": case["outcome"], "outcome": body["outcome"], "missing": [],
              "incorrect": [], "extras": [], "disputed": [], "leaks": [], "unknown_kept": [],
              "inferred_missing": [], "canonicalized_inference": []}
    if body["outcome"] != "resolved":
        report["missing"] = list(case["canonical"])
        report["inferred_missing"] = list(case["inferred"])
        report["disputed"] = list(case["disputed"])
        return report
    spec = body["data"]
    label = LABELS.get(case["subject"], "")
    aliases = {label.casefold(), f"captain {label}".casefold()} if label else set()
    member = next((m for m in members(spec) if m["entity"]["label"].casefold() in aliases), None)
    traits = member["traits"] if member else []

    def has(fid, status):
        return any(matches(fid, t, v) for t in traits if t["status"] == status for v in t["values"])

    report["missing"] = [fid for fid in case["canonical"] if not has(fid, "canonical")]
    report["inferred_missing"] = [fid for fid in case["inferred"] if not has(fid, "inferred")]
    report["canonicalized_inference"] = [fid for fid in case["inferred"] if has(fid, "canonical")]
    report["disputed"] = [fid for fid in case["disputed"] if not has(fid, "disputed")]
    for trait in traits:
        if trait["status"] != "canonical":
            continue
        for value in trait["values"]:
            if any(matches(fid, trait, value) for fid in case["canonical"]):
                continue
            wrong = [fid for fid in case["excluded"] + case["disputed"] + case["inferred"]
                     if fid in MATCHES and FACTS[fid]["subject"] == case["subject"] and matches(fid, trait, value)]
            (report["incorrect"] if wrong else report["extras"]).append(
                {"attribute": trait["attribute"], "value": value, "matches": wrong})
    for m in members(spec):
        for trait in m["traits"]:
            for span in trait["evidence"]:
                chapter = passage_chapters.get(span["passage_id"])
                if chapter is None or case["through_chapter"] is not None and chapter > case["through_chapter"]:
                    report["leaks"].append(span["quote"])
    report["unknown_kept"] = [u for u in case["unknown"] if member and u in {"eyes", "attire", "adult_hair"}
                              and u.replace("adult_", "") in member["unknown"]]
    return report


def summary(reports: list[dict]) -> dict:
    expected = sum(len(next(c for c in DATA["cases"] if c["id"] == r["case"])["canonical"]) for r in reports)
    missing = sum(len(r["missing"]) for r in reports)
    return {"scorer_version": SCORER_VERSION, "cases": len(reports), "outcome_matches": sum(r["expected"] == r["outcome"] for r in reports),
            "expected_canonical": expected, "found_canonical": expected - missing, "missing": missing,
            "incorrect": sum(len(r["incorrect"]) for r in reports), "extras": sum(len(r["extras"]) for r in reports),
            "inferences_missed": sum(len(r["inferred_missing"]) for r in reports),
            "canonicalized_inferences": sum(len(r["canonicalized_inference"]) for r in reports),
            "disputes_missed": sum(len(r["disputed"]) for r in reports), "leaks": sum(len(r["leaks"]) for r in reports),
            "blocking": [r["case"] for r in reports if r["incorrect"] or r["leaks"]]}
