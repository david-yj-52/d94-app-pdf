# d94-app-pdf 아키텍처

## 요청

`POST /pdf/api/v1/parse` (multipart `file`, 헤더 `X-Service-Token`) → 200 JSON

```json
{"parserVersion": "1.0.0", "title": "...", "pageCount": 357,
 "sections": [{"key": "s0001", "parentKey": null, "level": 1, "title": "...", "page": 1, "anchorBlockKey": "b000001"}],
 "blocks": [{"key": "b000001", "sectionKey": "s0001", "parentKey": null, "type": "HEADING", "level": 1,
             "text": "...", "page": 1, "row": null, "col": null}],
 "figures": [{"blockKey": "b000438", "pngBase64": "..."}]}
```

`TABLE_CELL`은 `parentKey`(표 블록)·`row`·`col`(0부터)을 가진다. `TABLE`·`FIGURE`의 `text`는 캡션.

## 파싱 단계 (`assemble.parse_pdf`)

1. 열기 — 실패 `INVALID_PDF`, 암호 `ENCRYPTED`, 글자 수 < 쪽수×20 `NO_TEXT_LAYER`.
2. 줄 추출 — 크기·굵기는 줄에서 가장 긴 span 기준.
3. 머리말·꼬리말 제거 — 위·아래 8%에서 숫자만 있는 줄, 숫자를 지운 텍스트가 3쪽 이상 반복되는 줄.
4. 표 — "Table N.N:" 캡션이 있는 쪽에서만 `find_tables()`. 셀 텍스트는 셀 영역을 잘라 다시 읽는다(띄어쓰기 보존).
5. 그림 — "Figure N.N:" 캡션 위, 직전 캡션 아래의 이미지 조각을 합쳐 150dpi PNG. 벡터 그림은 캡션만 남는다.
6. 목차 매칭 — 목차 항목 순서대로, 그 쪽의 아직 안 쓴 큰/굵은 줄과 유사도 0.8 이상(최대 3줄 합침, "Chapter N:" 접두사 무시). 못 찾으면 그 쪽 맨 앞에 제목 블록을 넣는다.
7. 문단·목록 — 같은 PyMuPDF 블록의 연속 줄을 잇고(줄 끝 하이픈 합침), 쪽 경계는 문장부호로 안 끝나고 다음 줄이 소문자면 잇는다. 글머리표(`•·◦▪–-`) 줄은 `LIST_ITEM`(단계는 항상 1).
8. 조립 — (쪽, y) 순서로 정렬해 키를 붙이고 직전 목차 섹션에 배정. 목차가 없으면 섹션 1개("본문").

하지 않는 것: 목차 밖 소제목 감지(실측 오탐 약 1,600줄), 목록 들여쓰기 단계, 목차 쪽번호 어긋남 보정(실측 0건), OCR.

## 실측 (CISA Study Guide 3rd Ed., 11MB, 357쪽, 2026-11-09)

섹션 484, 블록 5,638 (HEADING 484 · PARAGRAPH 2,586 · LIST_ITEM 1,230 · TABLE 113 · TABLE_CELL 1,180 · FIGURE 45), 그림 PNG 합계 5.1MB, 약 24초.
