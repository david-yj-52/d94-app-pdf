import re
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher

from .lines import body_font_size
from .model import Line

MAX_HEADING_LINES = 3
MIN_SIMILARITY = 0.8


@dataclass
class TocMatch:
    toc_index: int
    line_indices: list[int]  # 비어 있으면 본문에서 못 찾음
    page: int


def normalize_title(s: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", s.lower()).split())


def _title_variants(title: str) -> list[str]:
    t = normalize_title(title)
    stripped = re.sub(r"^chapter \d+ ", "", t)  # "Chapter 1: Audit Planning" 은 본문에 "Audit Planning"
    return [t] if stripped == t else [t, stripped]


def _similar(a: str, variants: list[str]) -> bool:
    return any(SequenceMatcher(None, a, v).ratio() >= MIN_SIMILARITY for v in variants)


def match_toc_headings(
    toc: list[list], lines: list[Line], excluded: set[int] = frozenset()
) -> list[TocMatch]:
    """목차 항목을 순서대로, 그 쪽에서 아직 안 쓴 큰/굵은 줄과 짝짓는다(최대 3줄 합쳐 비교).

    ponytail: 목차 쪽번호가 어긋난 경우(다음 쪽)는 찾지 않는다 — CISA 실측 0건.
    """
    body = body_font_size(lines)
    by_page: dict[int, list[int]] = defaultdict(list)
    for i, ln in enumerate(lines):
        if i not in excluded:
            by_page[ln.page].append(i)
    used: set[int] = set()
    result = []
    for ti, (_, title, page) in enumerate(toc):
        variants = _title_variants(title)
        idxs = by_page.get(page, [])
        found: list[int] = []
        for pos, i in enumerate(idxs):
            first = lines[i]
            if i in used or not (first.size > body + 0.5 or first.bold):
                continue
            group, text = [i], first.text
            while True:
                if _similar(normalize_title(text), variants):
                    found = group
                    break
                nxt_pos = pos + len(group)
                if len(group) >= MAX_HEADING_LINES or nxt_pos >= len(idxs):
                    break
                nxt = lines[idxs[nxt_pos]]
                if idxs[nxt_pos] in used or abs(nxt.size - first.size) > 0.3 or nxt.bold != first.bold:
                    break
                group.append(idxs[nxt_pos])
                text += " " + nxt.text
            if found:
                break
        used.update(found)
        result.append(TocMatch(ti, found, page))
    return result
