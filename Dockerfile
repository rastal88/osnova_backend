FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --create-home app

# Install only the modules this image needs: base (minimal) or standard.
ARG REQUIREMENTS=base
COPY requirements/ requirements/
RUN pip install --upgrade pip && pip install -r requirements/${REQUIREMENTS}.txt

COPY . .
RUN chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /app/uploads \
    && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')" || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
