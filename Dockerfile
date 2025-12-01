# --- Base image ---
FROM python:3.10-slim

# --- Install system dependencies (Tesseract + PDF libs) ---
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-fas \
    libtesseract-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# --- Install Python dependencies ---
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Copy source code ---
COPY . .

# --- Expose port ---
EXPOSE 8000

# --- Start command ---
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
