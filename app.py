import os
import re
import requests
from flask import Flask, request, render_template_string

app = Flask(__name__)

YT_API_KEY = os.environ.get("YT_API_KEY")

HTML = """
<!doctype html>
<title>YouTube Views</title>
<h2>YT просмотры</h2>
<form method="post">
  <input name="url" style="width:400px" placeholder="Ссылка на YouTube" required>
  <button>Проверить</button>
</form>

{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
{% if views is not none %}<h3>Просмотры: {{ views }}</h3>{% endif %}
"""

def get_youtube_id(url):
    # обычные видео
    match = re.search(r"v=([^&]+)", url)
    if match:
        return match.group(1)
    # shorts
    match = re.search(r"shorts/([^?&/]+)", url)
    if match:
        return match.group(1)
    return None

def get_youtube_views(video_id):
    r = requests.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={
            "part": "statistics",
            "id": video_id,
            "key": YT_API_KEY
        }
    ).json()

    try:
        return r["items"][0]["statistics"]["viewCount"]
    except:
        return None

@app.route("/", methods=["GET", "POST"])
def index():
    views = None
    error = None

    if request.method == "POST":
        url = request.form["url"]
        video_id = get_youtube_id(url)

        if not video_id:
            error = "Видео ID не найден"
        else:
            views = get_youtube_views(video_id)
            if views is None:
                error = "Не удалось получить просмотры"

    return render_template_string(HTML, views=views, error=error)

if __name__ == "__main__":
    app.run()
