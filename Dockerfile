FROM python:3.12-slim-bookworm

# Tesseract OCR plus the "best" Armenian and Russian models (English ships with the package).
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*
ADD --chmod=644 https://github.com/tesseract-ocr/tessdata_best/raw/main/hye.traineddata \
    https://github.com/tesseract-ocr/tessdata_best/raw/main/rus.traineddata \
    /usr/share/tesseract-ocr/5/tessdata/

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data/glossaries ./data/glossaries
COPY samples ./samples

RUN useradd --create-home hyur && mkdir /data && chown hyur /data
USER hyur

# Menus and the restaurant's glossaries live in /data (mount a volume to keep them).
ENV HYUR_DATA_DIR=/data \
    OLLAMA_URL=http://host.docker.internal:11434 \
    PYTHONUNBUFFERED=1
VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/meta', timeout=4)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
