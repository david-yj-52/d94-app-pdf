import re
from collections import Counter, defaultdict

import pymupdf

from .model import Line


def extract_lines(doc: pymupdf.Document) -> list[Line]:
    """쪽마다 PyMuPDF 읽기 순서대로 줄을 모은다. 크기·굵기는 글자 수가 가장 많은 span 기준."""
    out: list[Line] = []
    for pno, page in enumerate(doc, 1):
        height = page.rect.height
        for b in page.get_text("dict")["blocks"]:
            if b["type"] != 0:
                continue
            for ln in b["lines"]:
                text = " ".join("".join(s["text"] for s in ln["spans"]).split())
                if not text:
                    continue
                main = max(ln["spans"], key=lambda s: len(s["text"].strip()))
                bold = bool(main["flags"] & 16) or "bold" in main["font"].lower()
                x0, y0, x1, y1 = ln["bbox"]
                out.append(Line(pno, text, main["size"], bold, x0, y0, x1, y1, height, b["number"]))
    return out


def body_font_size(lines: list[Line]) -> float:
    """0.5pt 단위로 묶은 글자 수 가중 최빈값."""
    weights: Counter[float] = Counter()
    for ln in lines:
        weights[round(ln.size * 2) / 2] += len(ln.text)
    return weights.most_common(1)[0][0] if weights else 10.0


def _in_margin(ln: Line) -> bool:
    return ln.y0 < 0.08 * ln.page_height or ln.y1 > 0.92 * ln.page_height


def _margin_key(text: str) -> str:
    return re.sub(r"\d+", "", text).strip().lower()


def remove_running_lines(lines: list[Line], page_count: int) -> list[Line]:
    """위·아래 8% 영역에서 숫자만 있는 줄과, 숫자를 지운 텍스트가 3쪽 이상 반복되는 줄을 지운다.

    ponytail: 머리말이 챕터마다 바뀌는 책(CISA)이라 '전체 쪽의 절반' 대신 '3쪽 이상'으로 판정.
    """
    pages_by_key: dict[str, set[int]] = defaultdict(set)
    for ln in lines:
        if _in_margin(ln):
            pages_by_key[_margin_key(ln.text)].add(ln.page)
    threshold = min(3, max(2, page_count))
    out = []
    for ln in lines:
        if _in_margin(ln):
            key = _margin_key(ln.text)
            if re.fullmatch(r"\d+", ln.text) or (key and len(pages_by_key[key]) >= threshold):
                continue
        out.append(ln)
    return out
