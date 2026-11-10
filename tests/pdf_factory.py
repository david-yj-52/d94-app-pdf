"""테스트 안에서 PDF를 만든다. 쪽 크기 A4(595×842), y는 글자 기준선."""
from dataclasses import dataclass

import pymupdf

from pdfparser.parser.lines import extract_lines, remove_running_lines


@dataclass
class T:
    text: str
    y: float
    size: float = 10
    bold: bool = False
    x: float = 72


@dataclass
class TableSpec:
    y: float
    rows: list[list[str]]
    caption: str


@dataclass
class ImageSpec:
    y0: float
    y1: float
    caption: str


def make_pdf(pages, toc=None, tables=None, images=None, grids=None, encrypt=False, metadata_title=None) -> bytes:
    doc = pymupdf.open()
    for pi, items in enumerate(pages, 1):
        page = doc.new_page(width=595, height=842)
        for t in items:
            page.insert_text((t.x, t.y), t.text, fontsize=t.size, fontname="hebo" if t.bold else "helv")
        if tables and pi in tables:
            _table(page, tables[pi], with_grid=True)
        if grids and pi in grids:  # 캡션 없는 격자
            _table(page, grids[pi], with_grid=True, with_caption=False)
        if images and pi in images:
            im = images[pi]
            pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40), False)
            pix.clear_with(180)
            page.insert_image(pymupdf.Rect(150, im.y0, 450, im.y1), pixmap=pix)
            if im.caption:
                page.insert_text((72, im.y1 + 15), im.caption, fontsize=9, fontname="helv")
    if toc:
        doc.set_toc(toc)
    if metadata_title:
        doc.set_metadata({"title": metadata_title})
    if encrypt:
        return doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="u", owner_pw="o")
    return doc.tobytes()


def _table(page, ts: TableSpec, with_grid: bool, with_caption: bool = True):
    colw, rowh = 225, 30
    for r, row in enumerate(ts.rows):
        for c, cell in enumerate(row):
            rect = pymupdf.Rect(72 + c * colw, ts.y + r * rowh, 72 + (c + 1) * colw, ts.y + (r + 1) * rowh)
            if with_grid:
                page.draw_rect(rect, color=(0, 0, 0), width=0.8)
            page.insert_textbox(rect + (3, 3, -3, -3), cell, fontsize=9, fontname="helv")
    if with_caption:
        page.insert_text((72, ts.y + len(ts.rows) * rowh + 15), ts.caption, fontsize=9, fontname="helv")


def open_pdf(data: bytes) -> pymupdf.Document:
    return pymupdf.open(stream=data, filetype="pdf")


def page_lines(doc, page_no: int):
    lines = remove_running_lines(extract_lines(doc), doc.page_count)
    return [ln for ln in lines if ln.page == page_no]
