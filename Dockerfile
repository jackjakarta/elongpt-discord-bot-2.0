FROM python:3.12-alpine AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN python -m venv --without-pip /opt/venv

COPY requirements.txt ./

RUN python -m pip --python /opt/venv/bin/python install \
        --no-cache-dir --only-binary=:all: -r requirements.txt

# botocore bundles API models for ~400 AWS services (~24MB); this bot only ever
# talks to DynamoDB. sts stays because botocore's default credential chain
# reaches for it (assume-role / web identity). Using another AWS service means
# adding its data directory here, or boto3 raises UnknownServiceError at runtime.
RUN find /opt/venv/lib/python3.12/site-packages/botocore/data \
        -mindepth 1 -maxdepth 1 -type d \
        ! -name dynamodb ! -name sts -exec rm -rf {} +

FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN adduser -D -u 10001 appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appuser . .

USER appuser

CMD ["python", "main.py"]
