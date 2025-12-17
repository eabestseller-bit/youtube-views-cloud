import os
import re
import requests
from flask import Flask, request, render_template_string

app = Flask(__name__)

VK_TOKEN = os.environ.get("VK_TOKEN")
VK_API = "https://api.vk.com/method"
VK_VERSION = "5.199"

HTML = """
<!doctype html>
<title>VK Views Checker</title>
<h2>VK просмотры</h2>
<form method="post">
  <input name="url" style="width:400px" placeholder="Ссылка на пост / видео / клип VK" required>
  <button>Проверить</button>
</form>
{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
{% if views is not none %}<h3>Просмотры: {{ views }}</h3>{% endif %}
"""

def get_post_views(owner_id, post_id):
    r = requests.get(f"{VK_API}/wall.getById", params={
        "posts": f"{owner_id}_{post_id}",
        "access_token": VK_TOKEN,
        "v": VK_VERSION
    }).json()
    try:
        return r["response"][0]["views"]["count"]
    except:
        return None

def get_video_views(owner_id, video_id):
    r = requests.get(f"{VK_API}/video.get", params={
        "videos": f"{owner_id}_{video_id}",
        "access_token": VK_TOKEN,
        "v": VK_VERSION
    }).json()
    try:
        return r["response"]["items"][0]["views"]
    except:
        return None

@app.route("/", methods=["GET", "POST"])
def index():
    views = None
    error = None

    if request.method == "POST":
        url = request.form["url"].strip()

        post = re.search(r"wall(-?\d+)_(\d+)", url)
        video = re.search(r"video(-?\d+)_(\d+)", url)

        if post:
            views = get_post_views(post.group(1), post.group(2))
        elif video:
            views = get_video_views(video.group(1), video.group(2))
        else:
            error = "Ссылка не распознана"

        if views is None and not error:
            error = "Не удалось получить просмотры"

    return render_template_string(HTML, views=views, error=error)

if __name__ == "__main__":
    app.run()
