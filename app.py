import os
import re
import requests
from flask import Flask, request, render_template_string

app = Flask(__name__)

VK_TOKEN = os.environ.get("VK_TOKEN")
YT_KEY = os.environ.get("YOUTUBE_API_KEY")

HTML = """
<!doctype html>
<title>Просмотры</title>
<h2>Проверка просмотров</h2>
<form method="post">
  <input name="url" style="width:400px" placeholder="VK / YouTube" required>
  <button>Проверить</button>
</form>
{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
{% if views is not none %}<h3>Просмотры: {{ views }}</h3>{% endif %}
"""

# ------ VK ------
def vk_post_views(owner_id, post_id):
    try:
        r = requests.get("https://api.vk.com/method/wall.getById", params={
            "posts": f"{owner_id}_{post_id}",
            "access_token": VK_TOKEN,
            "v": "5.199"
        }).json()
        return r["response"][0]["views"]["count"]
    except:
        return None

def vk_video_views(owner_id, video_id):
    try:
        r = requests.get("https://api.vk.com/method/video.get", params={
            "videos": f"{owner_id}_{video_id}",
            "access_token": VK_TOKEN,
            "v": "5.199"
        }).json()
        return r["response"]["items"][0]["views"]
    except:
        return None

# ------ YOUTUBE ------
def youtube_views(video_id):
    try:
        r = requests.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={
                "part": "statistics",
                "id": video_id,
                "key": YT_KEY
            }
        ).json()
        return r["items"][0]["statistics"]["viewCount"]
    except:
        return None

# Extract YouTube video ID
def extract_youtube_id(url):
    # Shorts
    m = re.search(r"shorts/([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    # Regular watch?v=
    m = re.search(r"v=([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    return None


@app.route("/", methods=["GET", "POST"])
def index():
    views = None
    error = None

    if request.method == "POST":
        url = request.form["url"].strip()

        # VK patterns
        post = re.search(r"wall(-?\d+)_(\d+)", url)
        video = re.search(r"video(-?\d+)_(\d+)", url)

        # YouTube patterns
        yt = extract_youtube_id(url)

        if post:
            views = vk_post_views(post.group(1), post.group(2))
        elif video:
            views = vk_video_views(video.group(1), video.group(2))
        elif yt:
            views = youtube_views(yt)
        else:
            error = "Ссылка не распознана"

        if views is None and not error:
            error = "Не удалось получить просмотры"

    return render_template_string(HTML, views=views, error=error)


if __name__ == "__main__":
    app.run()
