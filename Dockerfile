FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY . .

# Ensure required directories exist
RUN mkdir -p uploads downloads temp

# Set up non-root execution environment
RUN useradd -m appuser && chown -R appuser:appuser /code
USER appuser

EXPOSE 8002

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]