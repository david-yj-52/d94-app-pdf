"""캡션("Table N.N:" / "Figure N.N:")이 있는 쪽에서만 표·그림 영역을 찾는다."""
import re

import pymupdf

from .model import FigureRegion, Line, TableRegion

CAPTION_TABLE = re.compile(r"^Table \d+\.\d+:")
CAPTION_FIGURE = re.compile(r"^Figure \d+\.\d+:")
FIGURE_DPI = 150


def find_table_regions(page: pymupdf.Page, page_lines: list[Line]) -> list[TableRegion]:
    captions = [ln for ln in page_lines if CAPTION_TABLE.match(ln.text)]
    if not captions:  # find_tables()는 쪽당 최대 2초라 캡션 있는 쪽만
        return []
    out = []
    for t in page.find_tables().tables:
        x0, y0, x1, y1 = t.bbox
        below = [c for c in captions if c.y0 >= y1 - 2]
        above = [c for c in captions if c.y1 <= y0 + 2]
        if below:
            caption = min(below, key=lambda c: c.y0 - y1).text
        elif above:
            caption = max(above, key=lambda c: c.y1).text
        else:
            caption = ""
        # extract()는 띄어쓰기를 잃으므로 셀 영역을 잘라 다시 읽는다
        cells = [
            [" ".join(page.get_text("text", clip=c).split()) if c else "" for c in row.cells]
            for row in t.rows
        ]
        out.append(TableRegion(page.number + 1, (x0, y0, x1, y1), caption, cells))
    # ponytail: 쪽을 넘어가는 표의 캡션 없는 앞부분은 문단으로 남는다. 자주 보이면 이어 붙이기 추가
    return out


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
