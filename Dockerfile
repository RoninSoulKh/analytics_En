FROM python:3.10-slim
WORKDIR /code
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt
COPY . .

# Створюємо папки, щоб докер не лаявся, якщо їх немає
RUN mkdir -p uploads downloads

# --- БЛОК БЕЗОПАСНОСТИ ---
RUN useradd -m diggyuser && chown -R diggyuser:diggyuser /code
USER diggyuser
# -------------------------

EXPOSE 8002
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]