FROM python:3.11-slim

WORKDIR /app

# Install dependency sistem yang dibutuhkan
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Salin seluruh kode dan install package holehe
COPY . .
RUN pip install --no-cache-dir .

# Railway meneruskan port dinamis via environment variable $PORT
ENV PORT=8080
EXPOSE 8080

# Jalankan Uvicorn server FastAPI
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}"]
