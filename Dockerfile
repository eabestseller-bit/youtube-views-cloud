# База с Python + Playwright + Chromium
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /app

# Ставим зависимости
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY . /app

# Запуск
CMD ["bash", "-lc", "gunicorn app:app -b 0.0.0.0:$PORT"]
