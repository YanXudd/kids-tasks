FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
COPY wheelhouse ./wheelhouse
RUN pip install --no-index --find-links=/app/wheelhouse -r requirements.txt

COPY . .
RUN mkdir -p /app/static/uploads

EXPOSE 8080

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8080", "app:app"]
