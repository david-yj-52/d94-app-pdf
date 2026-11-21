FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY pdfparser ./pdfparser
RUN pip install --no-cache-dir . && python -m spacy download en_core_web_sm
USER 10001:10001
EXPOSE 8080
CMD ["uvicorn", "pdfparser.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
