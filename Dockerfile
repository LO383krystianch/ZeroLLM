FROM python:3.13-slim

WORKDIR /app

# Zależności Pythona.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kod aplikacji.
COPY api ./api
COPY src ./src
COPY web ./web
COPY config ./config

EXPOSE 8000

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "/app"]
