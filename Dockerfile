# Python + Playwright + Chromium
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

# Включаем access/error логи gunicorn, чтобы видеть запросы в Render → Logs
CMD ["bash", "-lc", "gunicorn app:app -b 0.0.0.0:$PORT --access-logfile - --error-logfile - --log-level info"]
