import os
import re
import requests
from flask import Flask, request, render_template_string

app = Flask(__name__)

# ===== API TOKENS =====
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
VK_TOKEN = os.environ.get("VK_TOKEN")

# ===== API ENDPOINTS =====
YOUTUBE_API = "https://www.googleapis.com/youtube/v3/videos"
VK_API = "https://api.vk.com/method"
VK_VERSION = "5.199"

# ===== HTML =====
HTML = """
<!doctype html>
<title>Просмотры Видео</title>
<h2>Проверка просмотров</h2>
<form method="post">
  <input name="url" style="width:420px" placeholder="Ссылка YouTube или VK" required>
  <button>Проверить</button>
</form>
{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
{% if platform %}<p><b>Платформа:</b> {{ platform }}</p>{% endif %}
{% if views is not none %}<h3>Просмотры: {{ views }}</h3>{% endif %}
"""

# ====== YOUTUBE ======

def get_youtube_id(url):
    patterns = [
        r"youtu\.be/([A-Za-z0-9_-]{5,})",
        r"youtube\.com/watch\?v=([A-Za-z0-9_-]{5,})",
        r"youtube\.com/shorts/([A-Za-z0-9_-]{5,})"
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None

def get_youtube_views(video_id):
    params = {
        "id": video_id,
        "part": "statistics",
        "key": YOUTUBE_API_KEY
    }
    r = requests.get(YOUTUBE_API, params=params).json()
    try:
        return int(r["items"][0]["statistics"]["viewCount"])
    except:
        return None

# ====== VK ======

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

# ===== ROUTE =====

@app.route("/", methods=["GET", "POST"])
def index():
    views = None
    platform = None
    error = None

    if request.method == "POST":
        url = request.form["url"].strip()

        # ---------------- YOUTUBE ----------------
        yt_id = get_youtube_id(url)
        if yt_id:
            platform = "YouTube"
            views = get_youtube_views(yt_id)

        # ---------------- VK ---------------------
        if views is None:
            match_post = re.search(r"wall(-?\d+)_(\d+)", url)
            match_video = re.search(r"video(-?\d+)_(\d+)", url)
            if match_post:
                platform = "VK пост"
                views = get_vk_post_views(match_post.group(1), match_post.group(2))
            elif match_video:
                platform = "VK видео"
                views = get_vk_video_views(match_video.group(1), match_video.group(2))

        # ---------------- ERRORS ------------------
        if platform is None:
            error = "Ссылка не распознана (только YouTube + VK)"
        elif views is None:
            error = f"{platform}: не удалось получить просмотры"

    return render_template_string(HTML,
                                  views=views,
                                  error=error,
                                  platform=platform)

if __name__ == "__main__":
    app.run()
