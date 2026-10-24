import uuid

from app.services.retrieval.evidence import Candidate
from app.services.retrieval.fusion import (
    SOURCES,
    Budget,
    PassageInfo,
    categories,
    fuse,
    select,
)

TEXTS = {
    "scar": "Long after, a thin scar crossed his left cheek.",
    "armor": "He wore steel armor to the gate.",
    "armor-again": "He wore steel armor to the gate!",
    "roof": "Rain came through the broken roof.",
    "noise": "They talked about the harvest for an hour, and then they talked some more about it.",
}
IDS = {name: uuid.uuid5(uuid.NAMESPACE_URL, name) for name in TEXTS}
INFO = {IDS[name]: PassageInfo(i, text) for i, (name, text) in enumerate(TEXTS.items())}


def whole(name, protected=False, **paths):
    return Candidate(IDS[name], 0, len(TEXTS[name]), paths, protected=protected)


def names(selection):
    lookup = {v: k for k, v in IDS.items()}
    return [lookup[s.passage_id] for s in selection.passages]


def candidates():
    return [whole("noise", semantic=1, lexical=1), whole("armor", semantic=2), whole("armor-again", semantic=3),
            whole("roof", semantic=4), whole("scar", True, appearance=1), whole("scar", semantic=40)]


def test_fusion_merges_paths_per_passage_and_keeps_protection():
    ranked = fuse(candidates())
    assert [r.passage_id for r in ranked][0] == IDS["noise"]
    scar = next(r for r in ranked if r.passage_id == IDS["scar"])
    assert scar.paths == {"appearance": 1, "semantic": 40} and scar.protected == [(0, len(TEXTS["scar"]))]
    assert [r.passage_id for r in ranked][-1] == IDS["scar"]  # protection is not rank weight
    assert categories(TEXTS["scar"]) == {"body"} and categories(TEXTS["armor"]) == {"attire", "colour_material"}


def test_a_low_ranked_protected_fact_survives_a_tight_budget():
    ranked = fuse(candidates())
    selection = select(ranked, INFO, Budget(passages=2, characters=10_000))
    # The scar sentence is reserved despite its weak similarity, and new traits beat the top-ranked noise.
    assert names(selection) == ["armor", "roof", "scar"] and selection.protected_omitted == 0
    assert next(s for s in selection.passages if s.passage_id == IDS["scar"]).compressed
    assert (selection.outcome, selection.omitted) == ("truncated", 1)


def test_duplicates_do_not_crowd_out_distinct_traits():
    selection = select(fuse(candidates()), INFO, Budget(passages=4, characters=10_000))
    assert "armor-again" not in names(selection)
    assert {"armor", "roof", "scar"} <= set(names(selection))
    assert selection.categories == ["attire", "body", "colour_material", "structure"]


def test_protected_passages_compress_to_their_sentences_then_report_overflow():
    long = "The wind howled for pages. " * 20 + "Her eyes were grey."
    ids = {"long": uuid.uuid4(), "other": uuid.uuid4()}
    info = {ids["long"]: PassageInfo(0, long), ids["other"]: PassageInfo(1, "Her coat was red.")}
    start = long.index("Her eyes")
    items = [Candidate(ids["long"], start, len(long), {"appearance": 1}, protected=True),
             Candidate(ids["other"], 0, 17, {"appearance": 2}, protected=True),
             Candidate(ids["long"], 0, len(long), {"semantic": 1})]
    compressed = select(fuse(items), info, Budget(characters=60))
    kept = {s.passage_id: s for s in compressed.passages}
    assert kept[ids["long"]].spans == [(start, len(long))] and kept[ids["long"]].compressed
    assert (compressed.outcome, compressed.protected_omitted) == ("compressed", 0)
    overflow = select(fuse(items), info, Budget(characters=25))
    assert (overflow.outcome, overflow.protected_omitted) == ("protected_overflow", 1)
    assert select(fuse(items), info).outcome == "complete"


def test_many_protected_passages_never_exceed_the_provider_source_limit():
    # Pride and Prejudice: appearance cues in ~75 short passages produced 95 sources and a 500 at the envelope.
    ids = [uuid.uuid4() for _ in range(100)]
    info = {pid: PassageInfo(n, "Her eyes were grey.") for n, pid in enumerate(ids)}
    items = [Candidate(pid, 0, 19, {"semantic": n + 1}, protected=True) for n, pid in enumerate(ids)]
    selection = select(fuse(items), info)
    assert len(selection.passages) == SOURCES == 63
    assert (selection.outcome, selection.protected_omitted) == ("protected_overflow", 37)
    assert [s.passage_id for s in selection.passages] == ids[:63]  # the best-ranked protected evidence is kept
