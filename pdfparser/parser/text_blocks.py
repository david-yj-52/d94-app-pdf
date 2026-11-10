import re

from .model import Line, TextBlock

BULLET = re.compile(r"^[•·◦▪–-]\s+")
SENTENCE_END = (".", "?", "!", ":")


def _join(a: str, b: str) -> str:
    if len(a) > 1 and a.endswith("-") and a[-2].isalpha() and b[:1].islower():
        return a[:-1] + b
    return a + " " + b


def build_text_blocks(lines: list[Line], line_indices: list[int]) -> list[TextBlock]:
    """제목·표·그림에 쓰인 줄을 뺀 인덱스(오름차순)로 문단·목록 항목을 만든다.

    ponytail: 목록 단계는 항상 1 — CISA는 홀짝 쪽 여백 차이로 x 좌표가 갈려 단계 판정이 틀림.
    """
    blocks: list[TextBlock] = []
    prev_i = -2
    for i in line_indices:
        ln = lines[i]
        m = BULLET.match(ln.text)
        if m:
            blocks.append(TextBlock("LIST_ITEM", 1, ln.text[m.end():].strip(), ln.page, i))
        elif blocks and i == prev_i + 1 and _continues(lines[prev_i], ln, blocks[-1]):
            blocks[-1].text = _join(blocks[-1].text, ln.text)
        else:
            blocks.append(TextBlock("PARAGRAPH", 1, ln.text, ln.page, i))
        prev_i = i
    return blocks


def _continues(prev: Line, ln: Line, cur: TextBlock) -> bool:
    if prev.page == ln.page:
        return prev.block_no == ln.block_no
    # 쪽 경계: 앞 블록이 문장부호로 끝나지 않고 다음 줄이 소문자로 시작하면 이어진다
    return not cur.text.endswith(SENTENCE_END) and ln.text[:1].islower()
