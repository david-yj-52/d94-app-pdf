"""표·그림 캡션과 표 언급을 이용해 PDF 영역을 찾는다."""
import re

import pymupdf

from .model import FigureRegion, Line, TableRegion

CAPTION_TABLE = re.compile(r"^Table \d+\.\d+:")
TABLE_REFERENCE = re.compile(r"\btable\b", re.IGNORECASE)
CAPTION_FIGURE = re.compile(r"^Figure \d+\.\d+:")
FIGURE_DPI = 150


def find_table_regions(page: pymupdf.Page, page_lines: list[Line]) -> list[TableRegion]:
    captions = [ln for ln in page_lines if CAPTION_TABLE.match(ln.text)]
    has_table_reference = any(TABLE_REFERENCE.search(ln.text) for ln in page_lines)
    out = []
    # 선이 그려진 표는 캡션·"table" 언급이 없어도(예: 한국어 단어장) 모든 쪽에서 찾는다.
    # 선 기반 감지는 벡터 선이 없는 쪽에서 바로 끝나 비용이 작다.
    found = page.find_tables().tables
    # 선이 없는 표는 텍스트 배치 기반 감지가 필요하지만 문단 오탐이 많으므로
    # 표 언급이 있는 쪽에서만 시도한다.
    if not found and has_table_reference:
        found = page.find_tables(strategy="text").tables
    matched_captions: set[int] = set()
    for t in found:
        x0, y0, x1, y1 = t.bbox
        below = [c for c in captions if c.y0 >= y1 - 2]
        above = [c for c in captions if c.y1 <= y0 + 2]
        if below:
            caption_line = min(below, key=lambda c: c.y0 - y1)
            matched_captions.add(id(caption_line))
            caption = caption_line.text
        elif above:
            caption_line = max(above, key=lambda c: c.y1)
            matched_captions.add(id(caption_line))
            caption = caption_line.text
        else:
            caption = ""
        # extract()는 띄어쓰기를 잃으므로 셀 영역을 잘라 다시 읽는다
        cells = [
            [" ".join(page.get_text("text", clip=c).split()) if c else "" for c in row.cells]
            for row in t.rows
        ]
        out.append(TableRegion(page.number + 1, (x0, y0, x1, y1), caption, cells))

    # 일부 PDF 표는 선 없이 두 열의 텍스트만 배치해 PyMuPDF가 감지하지 못한다.
    # 캡션과 맞는 감지 영역이 없는 경우, 바로 앞의 정렬된 두 열을 셀로 묶는다.
    for caption in captions:
        if id(caption) in matched_captions:
            continue
        region = _find_borderless_columns(page, page_lines, caption)
        if region:
            out.append(region)
    return out


def _find_borderless_columns(page: pymupdf.Page, page_lines: list[Line], caption: Line) -> TableRegion | None:
    candidates = [ln for ln in page_lines
                  if ln.y0 < caption.y0 and ln.y0 >= page.rect.height * 0.08
                  and ln.y1 <= page.rect.height * 0.92]
    xs = sorted(ln.x0 for ln in candidates)
    if len(xs) < 6:
        return None
    gaps = [(xs[i + 1] - xs[i], (xs[i] + xs[i + 1]) / 2) for i in range(len(xs) - 1)]
    gap, split = max(gaps, default=(0, 0))
    if gap < 45:
        return None

    before = sorted(candidates, key=lambda ln: (ln.y0, ln.x0))
    # 캡션에서 위로 연속해서 이어지는 두 열만 모아 앞 문단이 섞이지 않게 한다.
    selected: list[Line] = []
    cursor = caption.y0
    for ln in reversed(before):
        if cursor - ln.y1 > 28:
            break
        selected.append(ln)
        cursor = min(cursor, ln.y0)
    selected.sort(key=lambda ln: (ln.y0, ln.x0))
    left = [ln for ln in selected if ln.x0 < split]
    right = [ln for ln in selected if ln.x0 >= split]
    if len(left) < 3 or len(right) < 3:
        return None

    aligned = [(a, b) for a in left for b in right if abs(a.y0 - b.y0) <= 2]
    if not aligned:
        return None
    header_y = min(a.y0 for a, _ in aligned)
    left_header = min((ln for ln in left if abs(ln.y0 - header_y) <= 2), key=lambda ln: ln.x0)
    right_header = min((ln for ln in right if abs(ln.y0 - header_y) <= 2), key=lambda ln: ln.x0)

    def cell_text(lines: list[Line]) -> str:
        # 같은 PDF 텍스트 블록의 줄바꿈은 문장 연속으로 합치고, 블록 경계(예: 글머리표)는 보존한다.
        groups: dict[int, list[str]] = {}
        order: list[int] = []
        for ln in lines:
            if ln.y0 <= header_y + 2:
                continue
            if ln.block_no not in groups:
                groups[ln.block_no] = []
                order.append(ln.block_no)
            groups[ln.block_no].append(ln.text)
        return "\n".join(" ".join(groups[key]) for key in order)

    left_body, right_body = cell_text(left), cell_text(right)
    if not left_body or not right_body:
        return None
    x0 = min(ln.x0 for ln in selected) - 2
    y0 = min(ln.y0 for ln in selected) - 1
    x1 = max(ln.x1 for ln in selected) + 2
    y1 = max(ln.y1 for ln in selected) + 1
    cells = [[left_header.text, right_header.text], [left_body, right_body]]
    return TableRegion(page.number + 1, (x0, y0, x1, y1), caption.text, cells)


def find_figure_regions(page: pymupdf.Page, page_lines: list[Line]) -> list[FigureRegion]:
    captions = sorted((ln for ln in page_lines if CAPTION_FIGURE.match(ln.text)), key=lambda c: c.y0)
    if not captions:
        return []
    images = [pymupdf.Rect(b["bbox"]) for b in page.get_text("dict")["blocks"] if b["type"] == 1]
    out = []
    top = 0.0
    for cap in captions:
        # 이전 캡션과 이 캡션 사이의 이미지 조각을 합친다 (그림 하나가 여러 이미지로 나뉜 경우)
        parts = [r for r in images if r.y0 >= top - 2 and r.y1 <= cap.y0 + 2]
        top = cap.y1
        if not parts:
            # ponytail: 벡터 그림은 캡션만 남긴다. 벡터 그림 PDF가 생기면 get_drawings() 영역 추가
            continue
        rect = parts[0]
        for r in parts[1:]:
            rect |= r
        zoom = FIGURE_DPI / 72
        png = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=rect).tobytes("png")
        out.append(FigureRegion(page.number + 1, tuple(rect), cap.text, png))
    return out
