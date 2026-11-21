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
    blockKey: str
    start: int
    end: int
    role: str


@cache
def _nlp():
    return spacy.load("en_core_web_sm")


def analyze(blocks: list[tuple[str, str]]) -> list[Span]:
    out: list[Span] = []
    nlp = _nlp()
    candidates: list[Span] = []
    for (key, text), doc in zip(blocks, nlp.pipe([t for _, t in blocks])):
        if len(text.split()) < 3:
            continue
        for sent in doc.sents:
            tokens = list(sent)
            for token in tokens:
                if token.dep_ in {"nsubj", "nsubjpass", "csubj"}:
                    candidates.append(Span(key, token.left_edge.idx, token.right_edge.idx + len(token.right_edge), "SUBJECT"))
                if token.dep_ in {"dobj", "obj", "attr", "oprd", "dative"}:
                    candidates.append(Span(key, token.left_edge.idx, token.right_edge.idx + len(token.right_edge), "OBJECT"))
                if token.dep_ in {"relcl", "advcl", "ccomp", "acl"}:
                    candidates.append(Span(key, token.left_edge.idx, token.right_edge.idx + len(token.right_edge), "CLAUSE"))
                if token.dep_ == "prep" and token.head.dep_ == "ROOT":
                    candidates.append(Span(key, token.left_edge.idx, token.right_edge.idx + len(token.right_edge), "PHRASE"))
                if token.pos_ in {"VERB", "AUX"} and token.dep_ in {"ROOT", "relcl", "advcl", "ccomp", "acl", "conj"}:
                    group = [token] + [c for c in token.children if c.dep_ in {"aux", "auxpass", "neg", "prt"}]
                    candidates.append(Span(key, min(g.idx for g in group), max(g.idx + len(g) for g in group), "VERB"))
    for s in candidates:
        if s.end <= s.start:
            continue
        if any(o.blockKey == s.blockKey and o.role == s.role and o is not s
               and o.start <= s.start and s.end <= o.end and (o.start, o.end) != (s.start, s.end)
               for o in candidates):
            continue
        out.append(s)
    return sorted(set(out), key=lambda s: (s.blockKey, s.start, s.end, s.role))
