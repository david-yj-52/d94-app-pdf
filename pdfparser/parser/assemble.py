import pymupdf

from .headings import match_toc_headings
from .lines import extract_lines, remove_running_lines
from .model import FigureRegion, Line, OutBlock, OutSection, ParseError, ParseResult, TableRegion
from .regions import find_figure_regions, find_table_regions
from .text_blocks import build_text_blocks

MIN_CHARS_PER_PAGE = 20


def _inside(ln: Line, page: int, bbox) -> bool:
    cx, cy = (ln.x0 + ln.x1) / 2, (ln.y0 + ln.y1) / 2
    x0, y0, x1, y1 = bbox
    return ln.page == page and x0 - 1 <= cx <= x1 + 1 and y0 - 1 <= cy <= y1 + 1


def _open(data: bytes) -> pymupdf.Document:
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as e:
        raise ParseError("INVALID_PDF", "PDF 파일을 열 수 없습니다.") from e
    if doc.needs_pass:
        raise ParseError("ENCRYPTED", "암호가 걸린 PDF는 처리할 수 없습니다.")
    if doc.page_count == 0:
        raise ParseError("INVALID_PDF", "쪽이 없는 PDF입니다.")
    return doc


def parse_pdf(data: bytes, parser_version: str) -> ParseResult:
    doc = _open(data)
    raw = extract_lines(doc)
    if sum(len(ln.text) for ln in raw) < doc.page_count * MIN_CHARS_PER_PAGE:
        raise ParseError("NO_TEXT_LAYER", "텍스트를 추출할 수 없는 PDF입니다(스캔본은 지원하지 않습니다).")
    lines = remove_running_lines(raw, doc.page_count)

    tables: list[TableRegion] = []
    figures: list[FigureRegion] = []
    for page in doc:
        page_lines = [ln for ln in lines if ln.page == page.number + 1]
        tables += find_table_regions(page, page_lines)
        figures += find_figure_regions(page, page_lines)

    regions = [(r.page, r.bbox, r.caption) for r in tables] + [(r.page, r.bbox, r.caption) for r in figures]
    excluded = {
        i for i, ln in enumerate(lines)
        if any(_inside(ln, p, bb) or (ln.page == p and cap and ln.text == cap) for p, bb, cap in regions)
    }

    toc = [[lvl, title, min(max(page, 1), doc.page_count)] for lvl, title, page, *_ in doc.get_toc(simple=True)]
    matches = match_toc_headings(toc, lines, excluded)
    heading_lines = {i for m in matches for i in m.line_indices}

    # (page, y, 순서, 종류, 값) — 못 찾은 목차 제목은 그 쪽 맨 앞(y=-1)
    elements: list[tuple] = []
    for m in matches:
        y = lines[m.line_indices[0]].y0 if m.line_indices else -1.0
        elements.append((m.page, y, 0, "H", toc[m.toc_index]))
    body_idx = [i for i in range(len(lines)) if i not in excluded and i not in heading_lines]
    for tb in build_text_blocks(lines, body_idx):
        elements.append((tb.page, lines[tb.first_line].y0, 1, "T", tb))
    for r in tables:
        elements.append((r.page, r.bbox[1], 1, "TB", r))
    for r in figures:
        elements.append((r.page, r.bbox[1], 1, "F", r))
    elements.sort(key=lambda e: (e[0], e[1], e[2]))

    sections: list[OutSection] = []
    blocks: list[OutBlock] = []
    figure_pngs: list[tuple[str, bytes]] = []
    stack: list[tuple[int, str]] = []
    current: str | None = None

    def add(**kw) -> OutBlock:
        b = OutBlock(key=f"b{len(blocks) + 1:06d}", section_key=current, **kw)
        blocks.append(b)
        return b

    for page, _, _, kind, val in elements:
        if kind == "H":
            level, title, _ = val
            key = f"s{len(sections) + 1:04d}"
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent = stack[-1][1] if stack else None
            current = key
            b = add(parent_key=None, type="HEADING", level=level, text=title, page=page)
            sections.append(OutSection(key, parent, level, title, page, b.key))
            stack.append((level, key))
        elif kind == "T":
            add(parent_key=None, type=val.type, level=val.level if val.type == "LIST_ITEM" else None,
                text=val.text, page=page)
        elif kind == "TB":
            t = add(parent_key=None, type="TABLE", level=None, text=val.caption, page=page)
            for r, row in enumerate(val.cells):
                for c, text in enumerate(row):
                    add(parent_key=t.key, type="TABLE_CELL", level=None, text=text, page=page, row=r, col=c)
        else:
            f = add(parent_key=None, type="FIGURE", level=None, text=val.caption, page=page)
            figure_pngs.append((f.key, val.png))

    if not sections:
        sections.append(OutSection("s0001", None, 1, "본문", 1, blocks[0].key if blocks else ""))
    for b in blocks:  # 첫 목차 제목 앞의 블록은 첫 섹션에
        if b.section_key is None:
            b.section_key = sections[0].key

    return ParseResult(parser_version, (doc.metadata or {}).get("title") or "", doc.page_count,
                       sections, blocks, figure_pngs)
