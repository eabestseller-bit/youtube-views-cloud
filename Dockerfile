# Готовый образ с Python + Playwright + Chromium
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

# Рабочая папка
WORKDIR /app

# Скопируем зависимости и установим
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Скопируем остальной код
COPY . /app

# Старт gunicorn на порту, который задаст Render ($PORT)
CMD ["bash", "-lc", "gunicorn app:app -b 0.0.0.0:$PORT"]
