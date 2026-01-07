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
  <input name="url" style="width:500px" placeholder="Вставьте ссылку" required>
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
                if views:
                    result = f"YouTube просмотры: {views}"
                else:
                    result = "Не удалось получить просмотры YouTube"
            else:
                result = "Не удалось распознать ссылку YouTube"

        # Telegram
        elif "t.me" in url:
            result = "Telegram: просмотры доступны только через парсинг (в разработке)"

        # OK
        elif "ok.ru" in url:
            result = "OK: API требует отдельной авторизации (в разработке)"

        # RuTube
        elif "rutube.ru" in url:
            result = "RuTube: API ограничен (в разработке)"

        # Dzen
        elif "dzen.ru" in url or "zen.yandex.ru" in url:
            result = "Яндекс Дзен: API недоступен публично (в разработке)"

        else:
            result = "Платформа не распознана"

    return render_template_string(HTML, result=result)

if __name__ == "__main__":
    app.run()
