import os
import re
import requests
from flask import Flask, request, render_template_string

app = Flask(__name__)

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")

HTML = """
<!doctype html>
<title>Views Checker</title>
<h2>Проверка просмотров</h2>

<form method="post">
  <input name="url" style="width:600px" placeholder="Вставьте ссылку" required>
  <button>Проверить</button>
</form>

{% if result %}
  <h3>Результат:</h3>
  <p>{{ result }}</p>
{% endif %}
"""

# ---------- YouTube ----------

def get_youtube_views(video_id):
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "statistics",
        "id": video_id,
        "key": YOUTUBE_API_KEY
    }
    r = requests.get(url, params=params).json()
    try:
        return r["items"][0]["statistics"]["viewCount"]
    except:
        return None

# ---------- Telegram ----------

def get_telegram_views(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers)
    html = r.text
    m = re.search(r'"views":\s*"([\d\s]+)"', html)
    if m:
        return m.group(1).replace(" ", "")
    return None

# ---------- OK ----------

def get_ok_views(url):
    oembed = "https://connect.ok.ru/oembed"
    r = requests.get(oembed, params={"url": url}).json()
    try:
        return r["like_count"]
    except:
        return None

# ---------- RuTube ----------

def get_rutube_views(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers)
    html = r.text
    m = re.search(r'"viewsCount":(\d+)', html)
    if m:
        return m.group(1)
    return None

# ---------- Dzen ----------

def get_dzen_views(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers)
    html = r.text
    m = re.search(r'"viewsCount":(\d+)', html)
    if m:
        return m.group(1)
    return None

# ---------- MAIN ----------

@app.route("/", methods=["GET", "POST"])
def index():
    result = None

    if request.method == "POST":
        url = request.form["url"].strip()

        # VK
        if "vk.com" in url:
            result = "VK не предоставляет данные о просмотрах через API"

        # YouTube
        elif "youtube.com" in url or "youtu.be" in url:
            yt = re.search(r"(v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url)
            if yt:
                views = get_youtube_views(yt.group(2))
                result = f"YouTube просмотры: {views}" if views else "YouTube: просмотры недоступны"
            else:
                result = "Некорректная ссылка YouTube"

        # Telegram
        elif "t.me" in url:
            views = get_telegram_views(url)
            result = f"Telegram просмотры: {views}" if views else "Telegram: просмотры недоступны"

        # OK
        elif "ok.ru" in url:
            views = get_ok_views(url)
            result = f"OK просмотры: {views}" if views else "OK: просмотры недоступны"

        # RuTube
        elif "rutube.ru" in url:
            views = get_rutube_views(url)
            result = f"RuTube просмотры: {views}" if views else "RuTube: просмотры недоступны"

        # Dzen
        elif "dzen.ru" in url or "zen.yandex.ru" in url:
            views = get_dzen_views(url)
            result = f"Яндекс Дзен просмотры: {views}" if views else "Дзен: просмотры недоступны"

        else:
            result = "Платформа не распознана"

    return render_template_string(HTML, result=result)

if __name__ == "__main__":
    app.run()
