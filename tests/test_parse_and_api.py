import os
import time
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient
from pdf_factory import ImageSpec, T, TableSpec, make_pdf

from pdfparser.api.app import create_app
from pdfparser.config.settings import Settings
from pdfparser.parser.assemble import parse_pdf
from pdfparser.parser.model import OutSection, ParseError

BODY = "Body text " * 8


def _full_pdf(**kw):
    return make_pdf(
        [
            [T("Chapter One", 80, 14.5, True), T(BODY, 110), T("• First item", 140), T("• Second item", 160)],
            [T("Section A", 80, 12.3, True), T(BODY, 100)],
            [T(BODY, 60)],
        ],
        toc=[[1, "Chapter One", 1], [2, "Section A", 2]],
        tables={2: TableSpec(130, [["Q", "A"], ["What?", "That."]], "Table 1.1: Key aspects")},
        images={3: ImageSpec(150, 400, "Figure 1.1: Flow")},
        **kw,
    )


def test_full_document_structure():
    r = parse_pdf(_full_pdf(), "1.0.0")
    assert [s.key for s in r.sections] == ["s0001", "s0002"] and r.sections[1].parent_key == "s0001"
    assert r.blocks[0].key == "b000001" and r.sections[0].anchor_block_key == "b000001"
    assert [b.type for b in r.blocks] == ["HEADING", "PARAGRAPH", "LIST_ITEM", "LIST_ITEM", "HEADING",
                                          "PARAGRAPH", "TABLE", "TABLE_CELL", "TABLE_CELL", "TABLE_CELL",
                                          "TABLE_CELL", "PARAGRAPH", "FIGURE"]
    cell = r.blocks[7]
    assert cell.parent_key == r.blocks[6].key and (cell.row, cell.col) == (0, 0) and cell.text == "Q"
    assert r.blocks[6].text == "Table 1.1: Key aspects" and r.blocks[12].text == "Figure 1.1: Flow"
    assert r.figures[0][0] == r.blocks[12].key


def test_unmatched_toc_entry_inserts_heading_at_page_start():
    r = parse_pdf(make_pdf([[T(BODY, 100)], [T(BODY, 100)]], toc=[[1, "Intro", 1], [1, "Missing", 2]]), "1")
    page2 = [b for b in r.blocks if b.page == 2]
    assert (page2[0].type, page2[0].text) == ("HEADING", "Missing") and page2[1].section_key == "s0002"


def test_no_toc_single_section():
    r = parse_pdf(make_pdf([[T(BODY, 100)]]), "1.0.0")
    assert r.sections == [OutSection("s0001", None, 1, "본문", 1, "b000001")]
    assert all(b.section_key == "s0001" for b in r.blocks)


def test_title_from_metadata_else_empty():
    assert parse_pdf(make_pdf([[T(BODY, 100)]], metadata_title="CISA Guide"), "1").title == "CISA Guide"
    assert parse_pdf(make_pdf([[T(BODY, 100)]]), "1").title == ""


@pytest.mark.parametrize("data,code", [
    (make_pdf([[T(BODY, 100)]], encrypt=True), "ENCRYPTED"),
    (make_pdf([[], []], images={1: ImageSpec(100, 300, "")}), "NO_TEXT_LAYER"),
    (b"not a pdf", "INVALID_PDF"),
])
def test_parse_errors(data, code):
    with pytest.raises(ParseError) as e:
        parse_pdf(data, "1")
    assert e.value.code == code


# ── API ─────────────────────────────────────────────────────────
@pytest.fixture
def client():
    return TestClient(create_app(Settings(service_token="t")))


def _post(client, data, token="t"):
    return client.post("/pdf/api/v1/parse", files={"file": ("a.pdf", data, "application/pdf")},
                       headers={"X-Service-Token": token})


def test_health_needs_no_token(client):
    assert client.get("/actuator/health").json() == {"status": "UP"}


def test_parse_without_or_wrong_token_is_401(client):
    assert client.post("/pdf/api/v1/parse", files={"file": ("a.pdf", b"x")}).status_code == 401
    assert _post(client, b"x", token="wrong").status_code == 401


def test_create_app_without_token_refuses():
    with pytest.raises(RuntimeError):
        create_app(Settings(service_token=""))


def test_parse_returns_camel_case_json(client):
    body = _post(client, _full_pdf()).json()
    assert set(body) == {"parserVersion", "title", "pageCount", "sections", "blocks", "figures"}
    assert {"sectionKey", "parentKey", "row", "col"} <= set(body["blocks"][0])
    assert body["figures"][0]["pngBase64"]


def test_parse_422_body(client):
    res = _post(client, make_pdf([[T(BODY, 100)]], encrypt=True))
    assert res.status_code == 422 and res.json()["code"] == "ENCRYPTED"


def test_parse_over_limit_is_413():
    c = TestClient(create_app(Settings(service_token="t", max_file_bytes=1000)))
    assert _post(c, b"x" * 2000).status_code == 413


@pytest.mark.skipif(not os.environ.get("STUDY_SAMPLE_PDF"), reason="sample pdf not provided")
def test_cisa_sample():
    t = time.monotonic()
    r = parse_pdf(Path(os.environ["STUDY_SAMPLE_PDF"]).read_bytes(), "1.0.0")
    assert len(r.sections) == 484
    assert sum(b.type == "TABLE" for b in r.blocks) >= 100
    assert sum(b.type == "FIGURE" for b in r.blocks) >= 40
    assert time.monotonic() - t < 120


def test_pymupdf_available():  # 이미지 빌드에서 의존성 누락을 빨리 잡는다
    assert pymupdf.VersionBind
