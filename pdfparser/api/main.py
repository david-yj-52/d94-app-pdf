from pdfparser.api.app import create_app

app = create_app()  # PDF_SERVICE_TOKEN 이 없으면 여기서 기동 실패(의도)
