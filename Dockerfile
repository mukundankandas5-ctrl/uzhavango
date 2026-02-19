FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=wsgi:app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/instance /app/static/uploads

EXPOSE 5000
CMD ["sh", "-c", "python -c \"from app import create_app; from app.extensions import db; app=create_app(); app.app_context().push(); db.create_all(); print('tables ready')\" && exec python -m gunicorn -w 2 -b 0.0.0.0:${PORT:-5000} wsgi:app"]
