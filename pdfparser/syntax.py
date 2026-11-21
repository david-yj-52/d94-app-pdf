"""Lightweight English sentence role spans for the study reader."""
from dataclasses import dataclass
from functools import cache
from importlib.metadata import PackageNotFoundError, version

import spacy

try:
    _MODEL_VERSION = version("en-core-web-sm")
except PackageNotFoundError:
    _MODEL_VERSION = "unavailable"
ANALYZER_VERSION = f"spacy-{spacy.__version__}-{_MODEL_VERSION}-1"


@dataclass(frozen=True)
class Span:
    block_key: str
    start: int
    end: int
    role: str


@cache
def _nlp():
    return spacy.load("en_core_web_sm")


def _subtree(key: str, token, role: str) -> Span:
    right = token.right_edge
    while right.is_punct and right.i > token.left_edge.i:
        right = right.doc[right.i - 1]
    return Span(key, token.left_edge.idx, right.idx + len(right), role)


def analyze(blocks: list[tuple[str, str]]) -> list[Span]:
    nlp = _nlp()
    blocks = [(k, t) for k, t in blocks if len(t.split()) >= 3]
    candidates: list[Span] = []
    for (key, _), doc in zip(blocks, nlp.pipe([t for _, t in blocks])):
        for token in doc:
            if token.dep_ in {"nsubj", "nsubjpass", "csubj"}:
                candidates.append(_subtree(key, token, "SUBJECT"))
            if token.dep_ in {"dobj", "obj", "attr", "oprd", "dative"}:
                candidates.append(_subtree(key, token, "OBJECT"))
            if token.dep_ in {"relcl", "advcl", "ccomp", "acl"}:
                candidates.append(_subtree(key, token, "CLAUSE"))
            if token.dep_ == "prep" and token.head.dep_ == "ROOT":
                candidates.append(_subtree(key, token, "PHRASE"))
            if token.pos_ in {"VERB", "AUX"} and token.dep_ in {"ROOT", "relcl", "advcl", "ccomp", "acl", "conj"}:
                group = sorted([token] + [c for c in token.children if c.dep_ in {"aux", "auxpass", "neg", "prt"}],
                               key=lambda g: g.i)
                run = [group[0]]
                for g in group[1:] + [None]:
                    if g is not None and g.i == run[-1].i + 1:
                        run.append(g)
                        continue
                    candidates.append(Span(key, run[0].idx, run[-1].idx + len(run[-1]), "VERB"))
                    run = [g]
    out = []
    for s in candidates:
        if s.end <= s.start:
            continue
        if any(o.block_key == s.block_key and o.role == s.role and o is not s
               and o.start <= s.start and s.end <= o.end and (o.start, o.end) != (s.start, s.end)
               for o in candidates):
            continue
        out.append(s)
    return sorted(set(out), key=lambda s: (s.block_key, s.start, s.end, s.role))
