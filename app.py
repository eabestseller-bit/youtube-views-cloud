import os
import re
import requests
from flask import Flask, request, render_template_string

app = Flask(__name__)

# 🔐 токены из настроек Render
VK_TOKEN = os.environ.get("VK_TOKEN")
YT_KEY = os.environ.get("YOUTUBE_API_KEY")

VK_API = "https://api.vk.com/method"
VK_VERSION = "5.199"
YT_API = "https://www.googleapis.com/youtube/v3/videos"

HTML = """
<!doctype html>
<title>VK + YouTube</title>
<h2>Проверка просмотров VK и YouTube</h2>
<form method="post">
  <input name="url" style="width:450px" placeholder="Вставь ссылку на VK или YouTube" required>
  <button>Проверить</button>
</form>
{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
{% if views is not none %}<h3>Просмотры: {{ views }}</h3>{% endif %}
"""

# ==================== YOUTUBE ======================
def extract_youtube_id(url):
    patterns = [
        r"v=([A-Za-z0-9_-]{6,})",
        r"youtu\.be/([A-Za-z0-9_-]{6,})",
        r"shorts/([A-Za-z0-9_-]{6,})"
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None

def get_youtube_views(video_id):
    r = requests.get(YT_API, params={
        "id": video_id,
        "key": YT_KEY,
        "part": "statistics"
    }).json()

    try:
        return int(r["items"][0]["statistics"]["viewCount"])
    except:
        return None

# ====================== VK =========================
def get_vk_post_views(owner_id, post_id):
    r = requests.get(f"{VK_API}/wall.getById", params={
        "posts": f"{owner_id}_{post_id}",
        "access_token": VK_TOKEN,
        "v": VK_VERSION
    }).json()
    try:
        return r["response"][0]["views"]["count"]
    except:
        return None

def get_vk_video_views(owner_id, video_id):
    r = requests.get(f"{VK_API}/video.get", params={
        "videos": f"{owner_id}_{video_id}",
        "access_token": VK_TOKEN,
        "v": VK_VERSION
    }).json()
    try:
        return r["response"]["items"][0]["views"]
    except:
        return None

# ====================== ROUTE ======================
@app.route("/", methods=["GET", "POST"])
def index():
    views = None
    error = None

    if request.method == "POST":
        url = request.form["url"].strip()

        # YOUTUBE
        vid = extract_youtube_id(url)
        if vid:
            if not YT_KEY:
                error = "Нет YouTube API ключа"
            else:
                views = get_youtube_views(vid)
            if views is None:
                error = "Не удалось получить просмотры YouTube"
            return render_template_string(HTML, views=views, error=error)

        # VK post
        post = re.search(r"wall(-?\d+)_(\d+)", url)
        video = re.search(r"video(-?\d+)_(\d+)", url)

        if not VK_TOKEN:
            error = "Нет VK токена"

        elif post:
            views = get_vk_post_views(post.group(1), post.group(2))
            if views is None:
                error = "Не удалось получить просмотры VK поста"

        elif video:
            views = get_vk_video_views(video.group(1), video.group(2))
            if views is None:
                error = "Не удалось получить просмотры VK видео"

        else:
            error = "Ссылка не распознана"

    return render_template_string(HTML, views=views, error=error)

if __name__ == "__main__":
    app.run()
