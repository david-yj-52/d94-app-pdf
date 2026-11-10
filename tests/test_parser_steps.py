from pdf_factory import ImageSpec, T, TableSpec, make_pdf, open_pdf, page_lines

from pdfparser.parser.headings import match_toc_headings
from pdfparser.parser.lines import body_font_size, extract_lines, remove_running_lines
from pdfparser.parser.model import Line
from pdfparser.parser.regions import find_figure_regions, find_table_regions
from pdfparser.parser.text_blocks import build_text_blocks


def _line(text, size=10.0, page=1, block=0, y=200.0, x=72.0, bold=False):
    return Line(page, text, size, bold, x, y, x + 300, y + size, 842, block)


# ── 줄·본문 크기·머리말 ──────────────────────────────────────────
def test_extract_lines_reports_size_bold_page():
    ls = extract_lines(open_pdf(make_pdf([[T("Title", 100, 14.5, True), T("Body text", 130)]])))
    assert [(l.text, round(l.size, 1), l.bold, l.page) for l in ls] == [
        ("Title", 14.5, True, 1), ("Body text", 10.0, False, 1)]


def test_body_font_size_buckets_half_points():
    ls = [_line("x" * 10, s) for s in [9.8] * 30 + [10.0] * 40 + [10.2] * 30 + [14.5] * 5]
    assert body_font_size(ls) == 10.0


def test_running_header_and_page_number_removed():
    pages = [[T("Audit Planning", 40, 9), T(str(6 + i), 40, 9, x=500), T("Body", 200)] for i in range(4)]
    doc = open_pdf(make_pdf(pages))
    out = remove_running_lines(extract_lines(doc), 4)
    assert [l.text for l in out] == ["Body"] * 4


def test_non_repeating_top_line_kept():
    pages = [[T("Only once", 40, 9), T("Body", 200)]] + [[T("Body", 200)]] * 3
    doc = open_pdf(make_pdf(pages))
    assert "Only once" in [l.text for l in remove_running_lines(extract_lines(doc), 4)]


# ── 표·그림 ─────────────────────────────────────────────────────
ROWS = [["Questions", "Possible Answers"],
        ["What is the prime reason for the review?", "An organization chart is a diagram."]]


def test_two_column_table_cells_keep_spaces():
    doc = open_pdf(make_pdf([[T("Key Aspects", 80, 12.3, True)]],
                            tables={1: TableSpec(120, ROWS, "Table 1.2: Key aspects for the CISA exam")}))
    [r] = find_table_regions(doc[0], page_lines(doc, 1))
    assert r.caption == "Table 1.2: Key aspects for the CISA exam"
    assert r.cells[1][0] == "What is the prime reason for the review?"


def test_page_without_caption_skips_detection():
    doc = open_pdf(make_pdf([[T("x", 80)]], grids={1: TableSpec(120, ROWS, "")}))
    assert find_table_regions(doc[0], page_lines(doc, 1)) == []


def test_caption_without_detectable_table_keeps_lines():
    doc = open_pdf(make_pdf([[T("Table 1.3: Missing grid", 300, 9)]]))
    assert find_table_regions(doc[0], page_lines(doc, 1)) == []


def test_image_above_caption_becomes_png():
    doc = open_pdf(make_pdf([[T("Figure 1.4 summarizes the flow.", 100)]],
                            images={1: ImageSpec(150, 400, "Figure 1.4: Audit process flow")}))
    [f] = find_figure_regions(doc[0], page_lines(doc, 1))
    assert f.caption == "Figure 1.4: Audit process flow" and f.png[:8] == b"\x89PNG\r\n\x1a\n"
    assert 140 <= f.bbox[1] and f.bbox[3] <= 410


def test_sentence_mentioning_figure_is_not_caption():
    doc = open_pdf(make_pdf([[T("Figure 1.4 summarizes the flow.", 100)]]))
    assert find_figure_regions(doc[0], page_lines(doc, 1)) == []


# ── 목차 제목 매칭 ──────────────────────────────────────────────
def test_duplicate_titles_on_same_page_matched_in_order():
    doc = open_pdf(make_pdf([
        [T("Audit Process", 100, 12.3, True), T("Body " * 20, 130),
         T("Key Aspects for the CISA Exam", 300, 12.3, True), T("Body " * 20, 330)],
        [T("Key Aspects for the CISA Exam", 100, 12.3, True), T("Body " * 20, 130)],
    ]))
    ls = remove_running_lines(extract_lines(doc), 2)
    toc = [[3, "Audit Process", 1], [3, "Key Aspects for the CISA Exam", 1], [3, "Key Aspects for the CISA Exam", 2]]
    m = match_toc_headings(toc, ls)
    assert [ls[x.line_indices[0]].page for x in m] == [1, 1, 2]
    assert len({x.line_indices[0] for x in m}) == 3


def test_two_line_heading():
    doc = open_pdf(make_pdf([[T("The Difference Between Preventive and", 100, 12.3, True),
                              T("Deterrent Controls", 116, 12.3, True), T("Body " * 20, 150)]]))
    ls = extract_lines(doc)
    [m] = match_toc_headings([[3, "The Difference Between Preventive and Deterrent Controls", 1]], ls)
    assert len(m.line_indices) == 2


def test_chapter_prefix_and_unmatched_entry():
    doc = open_pdf(make_pdf([[T("Audit Planning", 100, 18, True), T("Body " * 20, 150)]]))
    ls = extract_lines(doc)
    m = match_toc_headings([[1, "Chapter 1: Audit Planning", 1], [2, "Not In Body", 1]], ls)
    assert ls[m[0].line_indices[0]].text == "Audit Planning"
    assert m[1].line_indices == [] and m[1].page == 1


def test_running_header_same_text_as_heading():
    pages = [[T("Audit Planning", 40, 9), T("Body " * 20, 200)] for _ in range(3)]
    pages[0].append(T("Audit Planning", 100, 14.5, True))
    doc = open_pdf(make_pdf(pages))
    ls = remove_running_lines(extract_lines(doc), 3)
    [m] = match_toc_headings([[2, "Audit Planning", 1]], ls)
    assert round(ls[m.line_indices[0]].size, 1) == 14.5


# ── 문단·목록 ───────────────────────────────────────────────────
def _blocks(ls):
    return build_text_blocks(ls, list(range(len(ls))))


def test_lines_in_same_block_join_and_dehyphenate():
    [b] = _blocks([_line("Audit planning is the ini-"), _line("tial stage.")])
    assert (b.type, b.text) == ("PARAGRAPH", "Audit planning is the initial stage.")


def test_bullets_become_list_items_with_continuation():
    bs = _blocks([_line("• Audit universe: An inventory", block=1), _line("of all functions.", block=1),
                  _line("• Risk factors: x.", block=2)])
    assert [(b.type, b.text) for b in bs] == [("LIST_ITEM", "Audit universe: An inventory of all functions."),
                                              ("LIST_ITEM", "Risk factors: x.")]


def test_paragraph_continues_across_page_only_without_period():
    assert len(_blocks([_line("ends with the audit", page=1), _line("process is next", page=2)])) == 1
    assert len(_blocks([_line("the report.", page=1), _line("next part", page=2)])) == 2


def test_list_item_continues_across_page():
    bs = _blocks([_line("• Focus on high-risk", page=1), _line("areas", page=2)])
    assert [(b.type, b.text) for b in bs] == [("LIST_ITEM", "Focus on high-risk areas")]
