FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

EXPOSE 8014

CMD ["gunicorn", "--bind", "0.0.0.0:8014", "--workers", "2", "--threads", "2", "--access-logfile", "-", "--error-logfile", "-", "main:app"]