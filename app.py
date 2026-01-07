import os
import re
import json
import requests
from flask import Flask, request, render_template_string

app = Flask(__name__)

# ================= VK =================
VK_TOKEN = os.environ.get("VK_TOKEN")
VK_API = "https://api.vk.com/method"
VK_VERSION = "5.199"

# ================= HTML =================
HTML = """
<!doctype html>
<title>Views Checker</title>
<h2>Просмотры по ссылке</h2>
<form method="post">
  <input name="url" style="width:600px" placeholder="Вставь ссылку (VK / OK / YouTube)" required>
  <button>Проверить</button>
</form>

{% if error %}
<p style="color:red">Ошибка: {{ error }}</p>
{% endif %}

{% if views is not none %}
<h3>Просмотры: {{ views }}</h3>
{% endif %}
"""

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ================= VK =================
def get_vk_post_views(owner_id, post_id):
    r = requests.get(f"{VK_API}/wall.getById", params={
        "posts": f"{owner_id}_{post_id}",
        "access_token": VK_TOKEN,
        "v": VK_VERSION
    }).json()
    try:
        return r["response"][0]["views"]["count"]
    except Exception:
        return None

def get_vk_video_views(owner_id, video_id):
    r = requests.get(f"{VK_API}/video.get", params={
        "videos": f"{owner_id}_{video_id}",
        "access_token": VK_TOKEN,
        "v": VK_VERSION
    }).json()
    try:
        return r["response"]["items"][0]["views"]
    except Exception:
        return None

# ================= YOUTUBE =================
def get_youtube_views(url):
    try:
        oembed = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": url, "format": "json"},
            headers=HEADERS,
            timeout=10
        )
        if oembed.status_code != 200:
            return None

        html = requests.get(url, headers=HEADERS, timeout=10).text
        match = re.search(r'"viewCount":"(\d+)"', html)
        if match:
            return int(match.group(1))
    except Exception:
        return None

    return None

# ================= OK =================
def get_ok_views(url):
    try:
        html = requests.get(url, headers=HEADERS, timeout=10).text

        # способ, который работал раньше
        match = re.search(r'"viewsCount"\s*:\s*(\d+)', html)
        if match:
            return int(match.group(1))

        # запасной вариант
        match = re.search(r'"videoViews"\s*:\s*(\d+)', html)
        if match:
            return int(match.group(1))

    except Exception:
        return None

    return None

# ================= ROUTE =================
@app.route("/", methods=["GET", "POST"])
def index():
    views = None
    error = None

    if request.method == "POST":
        url = request.form["url"].strip()

        # VK post
        post = re.search(r"wall(-?\d+)_(\d+)", url)
        video = re.search(r"video(-?\d+)_(\d+)", url)

        if post:
            views = get_vk_post_views(post.group(1), post.group(2))

        elif video:
            views = get_vk_video_views(video.group(1), video.group(2))

        elif "ok.ru" in url:
            views = get_ok_views(url)

        elif "youtube.com" in url or "youtu.be" in url:
            views = get_youtube_views(url)

        else:
            error = "Ссылка не распознана"

        if views is None and not error:
            error = "Не удалось определить количество просмотров"

    return render_template_string(HTML, views=views, error=error)

if __name__ == "__main__":
    app.run()
