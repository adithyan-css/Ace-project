FROM python:3.11-slim

WORKDIR /app

COPY requirements_backend.txt /app/requirements_backend.txt
RUN pip install --no-cache-dir -r /app/requirements_backend.txt

COPY backend /app/backend
RUN mkdir -p /app/data
ENV PORT=8000
WORKDIR /app/backend

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]
