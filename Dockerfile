FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

CMD ["sh", "-c", "gunicorn -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT:-8000} app.main:app"]
