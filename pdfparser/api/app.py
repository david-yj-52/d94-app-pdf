import base64
import hmac

from fastapi import Depends, FastAPI, Header, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from pdfparser.config.settings import Settings
from pdfparser.parser.assemble import parse_pdf
from pdfparser.parser.model import ParseError, ParseResult

MULTIPART_OVERHEAD = 64 * 1024


def to_response(r: ParseResult) -> dict:
    return {
        "parserVersion": r.parser_version,
        "title": r.title,
        "pageCount": r.page_count,
        "sections": [
            {"key": s.key, "parentKey": s.parent_key, "level": s.level, "title": s.title,
             "page": s.page, "anchorBlockKey": s.anchor_block_key}
            for s in r.sections
        ],
        "blocks": [
            {"key": b.key, "sectionKey": b.section_key, "parentKey": b.parent_key, "type": b.type,
             "level": b.level, "text": b.text, "page": b.page, "row": b.row, "col": b.col}
            for b in r.blocks
        ],
        "figures": [{"blockKey": k, "pngBase64": base64.b64encode(png).decode()} for k, png in r.figures],
    }


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    if not settings.service_token:
        raise RuntimeError("PDF_SERVICE_TOKEN is required")

    def require_token(x_service_token: str = Header(default="")) -> None:
        if not hmac.compare_digest(x_service_token, settings.service_token):
            raise HTTPException(status_code=401, detail="invalid service token")

    app = FastAPI(title="d94-app-pdf")

    @app.get("/actuator/health")
    def health() -> dict:
        return {"status": "UP"}

    @app.post("/pdf/api/v1/parse", dependencies=[Depends(require_token)])
    async def parse(request: Request, file: UploadFile):
        too_large = JSONResponse({"code": "FILE_TOO_LARGE", "message": "50MB 이하 파일만 처리합니다."}, 413)
        if int(request.headers.get("content-length") or 0) > settings.max_file_bytes + MULTIPART_OVERHEAD:
            return too_large
        data = await file.read()
        if len(data) > settings.max_file_bytes:
            return too_large
        try:
            result = await run_in_threadpool(parse_pdf, data, settings.parser_version)
        except ParseError as e:
            return JSONResponse({"code": e.code, "message": e.message}, 422)
        return to_response(result)

    return app
