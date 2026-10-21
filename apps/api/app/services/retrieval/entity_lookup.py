"""Cutoff-eligible subject lookup over visible names, aliases and identity links.

Everything comes from a reading-boundary `Narrative`, so a later alias or reveal
cannot resolve an earlier request. A surface whose visible mentions point at
more than one identity stays ambiguous instead of picking the likeliest one.
"""

import re
import unicodedata
import uuid
from dataclasses import dataclass

PRONOUNS = frozenset("""i me my mine myself he him his himself she her hers herself it its itself we us our ours
they them their theirs you your yours this that these those who whom whose one""".split())


@dataclass(frozen=True)
class Subject:
    """One identity at this cutoff; several entity ids when a visible `same_as` link joins them."""
    entity_ids: tuple[uuid.UUID, ...]
    kind: str
    label: str


@dataclass(frozen=True)
class Match:
    start: int
    end: int
    subjects: tuple[Subject, ...]


def fold(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold()


class SubjectLookup:
    def __init__(self, view):
        parent = {e: e for e in view.entities}

        def root(e):
            while parent[e] != e:
                parent[e] = parent[parent[e]]
                e = parent[e]
            return e

        for relation in view.relations:
            if relation.relation == "same_as":
                a, b = root(relation.subject_id), root(relation.object_id)
                parent[max(a, b)] = min(a, b)
        members: dict[uuid.UUID, list] = {}
        for entity_id in view.entities:
            members.setdefault(root(entity_id), []).append(entity_id)
        counts = {e: sum(e in view.candidates[m.id] for m in view.mentions) for e in view.entities}
        self._subject = {}
        for ids in members.values():
            head = min(sorted(ids), key=lambda e: -counts[e])
            subject = Subject(tuple(sorted(ids)), view.entities[head].kind, view.labels[head])
            for entity_id in ids:
                self._subject[entity_id] = subject

        self._surfaces: dict[str, set[Subject]] = {}
        self._capitalised: set[str] = set()
        for mention in view.mentions:
            text = view.passages[mention.passage_id][1][mention.start:mention.end]
            self._add(text, view.candidates[mention.id])
        for entity_id, label in view.labels.items():
            self._add(label, [entity_id])
        for alias in view.aliases:
            self._add(alias.label, [alias.entity_id])
        names = sorted(self._surfaces, key=len, reverse=True)
        self._pattern = re.compile(r"(?<!\w)(?:" + "|".join(map(re.escape, names)) + r")(?!\w)") if names else None
        # Capitalised words inside multiword names ("Captain" of "Captain Mira") for title-only requests.
        self._words: dict[str, set[Subject]] = {}
        for surface, subjects in self._surfaces.items():
            if " " in surface:
                for word in re.findall(r"\w+", surface):
                    self._words.setdefault(word, set()).update(subjects)

    def _add(self, text: str, entity_ids) -> None:
        key = fold(text).strip()
        if key and key not in PRONOUNS and entity_ids:
            self._surfaces.setdefault(key, set()).update(self._subject[e] for e in entity_ids)
            self._capitalised.update(fold(w) for w in re.findall(r"\w+", text) if w[:1].isupper())

    def subject(self, entity_id: uuid.UUID) -> Subject | None:
        return self._subject.get(entity_id)

    def find(self, query: str) -> list[Match]:
        """Named subjects in request order; falls back to title words when no full name matches."""
        text = fold(query)
        matches = [] if self._pattern is None else [
            Match(m.start(), m.end(), ordered(self._surfaces[m.group()])) for m in self._pattern.finditer(text)]
        if matches:
            return matches
        for word in re.finditer(r"\w+", text):
            key = word.group()
            if key not in PRONOUNS and key in self._capitalised and key in self._words:
                matches.append(Match(word.start(), word.end(), ordered(self._words[key])))
        return matches


def ordered(subjects) -> tuple[Subject, ...]:
    return tuple(sorted(subjects, key=lambda s: (fold(s.label), str(s.entity_ids[0]))))
