import os
import re
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, render_template_string

app = Flask(__name__)

VK_TOKEN = os.environ.get("VK_TOKEN")
OK_COOKIE = os.environ.get("OK_COOKIE")

HTML = """
<!doctype html>
<title>Просмотры соцсетей</title>
<h2>Проверка просмотров</h2>
<form method="post">
  <input name="url" style="width:400px" placeholder="Вставьте ссылку" required>
  <button>Проверить</button>
</form>
{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
{% if views is not none %}<h3>Просмотры: {{ views }}</h3>{% endif %}
"""

# ---------------- VK ----------------

def get_vk_views(url):
    post = re.search(r"wall(-?\d+)_(\d+)", url)
    video = re.search(r"video(-?\d+)_(\d+)", url)

    if post:
        r = requests.get("https://api.vk.com/method/wall.getById", params={
            "posts": f"{post.group(1)}_{post.group(2)}",
            "access_token": VK_TOKEN,
            "v": "5.199"
        }).json()
        return r.get("response",[{}])[0].get("views",{}).get("count")

    if video:
        r = requests.get("https://api.vk.com/method/video.get", params={
            "videos": f"{video.group(1)}_{video.group(2)}",
            "access_token": VK_TOKEN,
            "v": "5.199"
        }).json()
        items = r.get("response",{}).get("items",[])
        return items[0].get("views") if items else None

    return None

# ---------------- YouTube ----------------

def get_youtube_views(url):
    try:
        r = requests.get("https://www.youtube.com/oembed",
                         params={"url": url, "format": "json"})
        if r.status_code != 200:
            return None
        # oEmbed не отдаёт просмотры — но если oEmbed работает, видео живое
        # возьмём HTML просмотры
        html = requests.get(url).text
        m = re.search(r'"viewCount":"(\d+)"', html)
        return int(m.group(1)) if m else None
    except:
        return None

# ---------------- ODNOKLASSNIKI ----------------

def get_ok_views(url):
    if not OK_COOKIE:
        return None
    try:
        headers = {"Cookie": OK_COOKIE, "User-Agent":"Mozilla/5.0"}
        html = requests.get(url, headers=headers).text
        soup = BeautifulSoup(html, "lxml")
        m = re.search(r'"count":"?(\d+)"?,?"text":"просмотров"', html)
        if m:
            return int(m.group(1))
        return None
    except:
        return None

# ---------------- RUTUBE ----------------

def get_rutube_views(url):
    try:
        html = requests.get(url).text
        m = re.search(r'"views":(\d+)', html)
        return int(m.group(1)) if m else None
    except:
        return None

# ---------------- TELEGRAM ----------------

def get_telegram_views(url):
    try:
        html = requests.get(url).text
        m = re.search(r'"views":(\d+)', html)
        return int(m.group(1)) if m else None
    except:
        return None

# ---------------- YANDEX.ZEN ----------------

def get_zen_views(url):
        try:
            html = requests.get(url).text
            m = re.search(r'"view_counter":(\d+)', html)
            return int(m.group(1)) if m else None
        except:
            return None

# ---------------- DISPATCH ----------------

@app.route("/", methods=["GET", "POST"])
def index():
    views = None
    error = None

    if request.method == "POST":
        url = request.form["url"].strip()

        if "vk.com" in url or "vkvideo.ru" in url:
            views = get_vk_views(url)
        elif "youtube" in url or "youtu.be" in url:
            views = get_youtube_views(url)
        elif "ok.ru" in url:
            views = get_ok_views(url)
        elif "rutube.ru" in url:
            views = get_rutube_views(url)
        elif "t.me" in url:
            views = get_telegram_views(url)
        elif "dzen.ru" in url:
            views = get_zen_views(url)
        else:
            error = "Платформа не распознана"

        if views is None and not error:
            error = "Не удалось определить просмотры"

    return render_template_string(HTML, views=views, error=error)


if __name__ == "__main__":
    app.run()
