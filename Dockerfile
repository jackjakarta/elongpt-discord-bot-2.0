FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

FROM base AS builder

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

FROM base AS runner

CMD ["python", "main.py"]
