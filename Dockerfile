FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY slothsort ./slothsort
COPY frontend ./frontend

# Folders are mounted at /watch/*, the undo journal lives in a volume, and the model runs
# in Ollama on the host, so nothing in the image needs a GPU or your files.
ENV SLOTH_HOST=0.0.0.0 \
    SLOTH_WATCH=/watch/Desktop,/watch/Downloads \
    SLOTH_STATE_DIR=/state \
    OLLAMA_URL=http://host.docker.internal:11434 \
    PYTHONUNBUFFERED=1

EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/status', timeout=4)"

CMD ["python", "-m", "slothsort"]
