import os
import re
import requests
from flask import Flask, request, render_template_string

app = Flask(__name__)

YOUTUBE_KEY = os.environ.get("YOUTUBE_API_KEY")

HTML = """
<!doctype html>
<title>Проверка просмотров</title>
<h2>Проверка просмотров YouTube / Telegram / RuTube</h2>
<form method="post">
  <input name="url" style="width:400px" placeholder="Вставьте ссылку" required>
  <button>Проверить</button>
</form>
{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
{% if views is not none %}<h3>Просмотры: {{ views }}</h3>{% endif %}
"""

# --------------- YOUTUBE ---------------
def get_youtube_views(url):
    yt = re.search(r"(?:v=|/shorts/)([A-Za-z0-9_-]{6,})", url)
    if not yt:
        return None

    video_id = yt.group(1)

    r = requests.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={
            "id": video_id,
            "key": YOUTUBE_KEY,
            "part": "statistics"
        }
    ).json()

    try:
        return r["items"][0]["statistics"]["viewCount"]
    except:
        return None


# --------------- TELEGRAM ---------------
def get_telegram_views(url):
    # Pull post number
    post = re.search(r"t.me/[^/]+/(\d+)", url)
    if not post:
        return None

    try:
        # Public TG pages include views in og metadata!
        html = requests.get(url).text
        match = re.search(r'"views":(\d+)', html)
        if match:
            return match.group(1)

        # fallback: search plain text
        match = re.search(r'views"\s*:\s*(\d+)', html)
        if match:
            return match.group(1)

    except:
        return None

    return None


# --------------- RUTUBE ---------------
def get_rutube_views(url):
    video = re.search(r"rutube.ru/(?:video|shorts)/([A-Za-z0-9-]+)", url)
    if not video:
        return None

    video_id = video.group(1)

    api = f"https://rutube.ru/api/video/{video_id}/?format=json"

    try:
        r = requests.get(api).json()
        return r.get("hit", None)
    except:
        return None


# --------------- ROUTER ---------------
@app.route("/", methods=["GET", "POST"])
def index():
    views = None
    error = None

    if request.method == "POST":
        url = request.form["url"].strip()

        if "youtu" in url:
            views = get_youtube_views(url)
        elif "t.me" in url:
            views = get_telegram_views(url)
        elif "rutube.ru" in url:
            views = get_rutube_views(url)
        else:
            error = "Платформа не распознана: поддержка YouTube, Telegram, RuTube"

        if views is None and not error:
            error = "Не удалось определить просмотры"

    return render_template_string(HTML, views=views, error=error)


if __name__ == "__main__":
    app.run(host="0.0.0.0")
