# AGENTS.md — d94-app-pdf (PDF 구조 파서)

> 모든 AI 도구가 공유하는 L1 가이드. 도구별 파일(`CLAUDE.md`)은 이 파일을 import 한다.

## 1. 서비스 요약

- PDF 바이트를 받아 학습 뷰어(d94-query `study`)가 쓰는 구조 JSON을 돌려주는 **상태 없는** FastAPI 서비스.
- 호출자는 d94-query 하나. 경로: d94-query → gateway(`Path=/pdf/**` → `http://d94-pdf-parser:8080`) → 이 서비스. Eureka 등록은 하지 않는다.
- DB·MinIO에 접근하지 않는다. 저장은 전부 d94-query가 한다.
- 흐름·알고리즘: [docs/architecture.md](docs/architecture.md). 설계: d94-note `docs/superpowers/specs/2026-11-09-pdf-study-viewer-design.md`.

## 2. 기술 스택과 명령

| 영역 | 기술 |
|---|---|
| 런타임·API | Python 3.12, FastAPI, Uvicorn |
| PDF | PyMuPDF (`pymupdf`) |
| 테스트 | pytest (테스트 PDF는 `tests/pdf_factory.py`로 생성) |

| 목적 | 명령 |
|---|---|
| 개발 설치 | `python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev]'` |
| 테스트 | `.venv/bin/pytest -q` |
| 실제 PDF 확인 | `STUDY_SAMPLE_PDF=/path/to.pdf .venv/bin/pytest -q -k cisa` |
| 로컬 실행 | `PDF_SERVICE_TOKEN=dev .venv/bin/uvicorn pdfparser.api.main:app --reload --port 8080` |
| 기동 (GHCR) | `docker compose --env-file .env pull && docker compose --env-file .env up -d` |
| 배포 | `deploy` 브랜치 push → Actions가 테스트 후 `ghcr.io/david-yj-52/d94-app-pdf:latest` 게시 |

## 3. 불변식

1. `PDF_SERVICE_TOKEN`이 비어 있으면 기동을 거부한다. `/actuator/health` 외 모든 경로는 `X-Service-Token` 일치가 필요하다(불일치 401).
2. 파일 상한 50MB(`PDF_MAX_FILE_BYTES`), 초과 413.
3. 처리할 수 없는 PDF는 422 `{code, message}` — `code`는 `ENCRYPTED` / `NO_TEXT_LAYER` / `INVALID_PDF`. `message`는 사용자에게 그대로 보여 줄 한국어.
4. 응답 JSON 키(camelCase)와 블록 type(`HEADING`, `PARAGRAPH`, `LIST_ITEM`, `TABLE`, `TABLE_CELL`, `FIGURE`)는 d94-query `ParserResponse`와 짝이다. 바꾸면 양쪽을 같이 바꾸고 `PDF_PARSER_VERSION`을 올린다.
5. 블록 키 `b000001`…, 섹션 키 `s0001`…은 문서 순서다. 저장된 마킹이 이 키를 참조한다.

## 4. 구조

| 파일 | 책임 |
|---|---|
| `pdfparser/api/app.py` | `create_app()`, 인증, 크기 검사, `to_response()` |
| `pdfparser/api/main.py` | 실행용 `app` |
| `pdfparser/parser/lines.py` | 줄 추출, 본문 폰트 크기, 머리말·꼬리말 제거 |
| `pdfparser/parser/regions.py` | 캡션 기반 표·그림 영역 |
| `pdfparser/parser/headings.py` | 목차 제목 ↔ 본문 줄 매칭 |
| `pdfparser/parser/text_blocks.py` | 문단·목록 항목 |
| `pdfparser/parser/assemble.py` | `parse_pdf()` — 단계 조립, 키 부여 |

## 5. 커밋

`type: 설명` (feat/fix/test/docs/chore).
