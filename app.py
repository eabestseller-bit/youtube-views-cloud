import os
import re
import requests
from flask import Flask, request, render_template_string

app = Flask(__name__)

VK_TOKEN = os.environ.get("VK_TOKEN")
VK_API = "https://api.vk.com/method"
VK_VERSION = "5.199"

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/videos"

HTML = """
<!doctype html>
<title>Views Checker</title>
<h2>Проверка просмотров</h2>
<form method="post">
  <input name="url" style="width:400px" placeholder="Вставьте ссылку" required>
  <button>Проверить</button>
</form>
{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
{% if views is not none %}<h3>Просмотры: {{ views }}</h3>{% endif %}
"""

# ---------------- YOUTUBE -----------------

def get_youtube_id(url):
    # ?v= видео
    match = re.search(r"v=([^&]+)", url)
    if match:
        return match.group(1)

    # youtu.be короткая ссылка
    match = re.search(r"youtu\.be/([^?]+)", url)
    if match:
        return match.group(1)

    # shorts
    match = re.search(r"shorts/([^/?&]+)", url)
    if match:
        return match.group(1)

    return None


def get_youtube_views(video_id):
    if not YOUTUBE_API_KEY:
        return None

    params = {
        "part": "statistics",
        "id": video_id,
        "key": YOUTUBE_API_KEY
    }

    r = requests.get(YOUTUBE_API_URL, params=params).json()

    try:
        return int(r["items"][0]["statistics"]["viewCount"])
    except:
        return None


# ---------------- VK -----------------

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


# ---------------- ROUTES -----------------

@app.route("/", methods=["GET", "POST"])
def index():
    views = None
    error = None

    if request.method == "POST":
        url = request.form["url"].strip()

        # YouTube
        youtube_id = get_youtube_id(url)
        if youtube_id:
            views = get_youtube_views(youtube_id)
            if views is None:
                error = "Не удалось получить просмотры YouTube"
            return render_template_string(HTML, views=views, error=error)

        # VK
        post = re.search(r"wall(-?\d+)_(\d+)", url)
        video = re.search(r"video(-?\d+)_(\d+)", url)

        if post:
            views = get_vk_post_views(post.group(1), post.group(2))
        elif video:
            views = get_vk_video_views(video.group(1), video.group(2))
        else:
            error = "Ссылка не распознана"

        if views is None and not error:
            error = "Не удалось получить просмотры"

    return render_template_string(HTML, views=views, error=error)


if __name__ == "__main__":
    app.run(host="0.0.0.0")
