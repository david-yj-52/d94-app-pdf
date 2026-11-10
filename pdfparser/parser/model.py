from dataclasses import dataclass, field

BBox = tuple[float, float, float, float]


@dataclass
class Line:
    page: int  # 1부터
    text: str
    size: float
    bold: bool
    x0: float
    y0: float
    x1: float
    y1: float
    page_height: float
    block_no: int


@dataclass
class TableRegion:
    page: int
    bbox: BBox
    caption: str
    cells: list[list[str]]


@dataclass
class FigureRegion:
    page: int
    bbox: BBox
    caption: str
    png: bytes


@dataclass
class TextBlock:
    type: str  # PARAGRAPH | LIST_ITEM
    level: int
    text: str
    page: int
    first_line: int


@dataclass
class OutSection:
    key: str
    parent_key: str | None
    level: int
    title: str
    page: int
    anchor_block_key: str


@dataclass
class OutBlock:
    key: str
    section_key: str | None
    parent_key: str | None
    type: str
    level: int | None
    text: str
    page: int
    row: int | None = None
    col: int | None = None


@dataclass
class ParseResult:
    parser_version: str
    title: str
    page_count: int
    sections: list[OutSection]
    blocks: list[OutBlock]
    figures: list[tuple[str, bytes]] = field(default_factory=list)


class ParseError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message
