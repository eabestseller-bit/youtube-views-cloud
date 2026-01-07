import os
import re
import requests
from flask import Flask, request, render_template_string

app = Flask(__name__)

VK_TOKEN = os.environ.get("VK_TOKEN")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")

VK_API = "https://api.vk.com/method"
VK_VERSION = "5.199"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"
}

HTML = """
<!doctype html>
<title>Social Views Checker</title>
<h2>Проверка просмотров</h2>
<form method="post">
  <input name="url" style="width:520px" placeholder="Вставьте ссылку" required>
  <button>Проверить</button>
</form>
{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
{% if result %}<h3>{{ result }}</h3>{% endif %}
"""

# ---------------- VK ----------------
def vk_post_views(owner_id, post_id):
    r = requests.get(f"{VK_API}/wall.getById", params={
        "posts": f"{owner_id}_{post_id}",
        "access_token": VK_TOKEN,
        "v": VK_VERSION
    }).json()
    try:
        return r["response"][0]["views"]["count"]
    except:
        return None

def vk_video_views(owner_id, video_id):
    r = requests.get(f"{VK_API}/video.get", params={
        "videos": f"{owner_id}_{video_id}",
        "access_token": VK_TOKEN,
        "v": VK_VERSION
    }).json()
    try:
        return r["response"]["items"][0]["views"]
    except:
        return None

# ---------------- YouTube ----------------
def youtube_views(url):
    m = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", url)
    if not m:
        return None

    video_id = m.group(1)

    r = requests.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={
            "part": "statistics",
            "id": video_id,
            "key": YOUTUBE_API_KEY
        },
        timeout=10
    ).json()

    try:
        return int(r["items"][0]["statistics"]["viewCount"])
    except:
        return None

# ---------------- OK ----------------
def ok_views(url):
    def parse(html):
        patterns = [
            r'"viewsCount"\s*:\s*(\d+)',
            r'"viewCount"\s*:\s*"([\d\s]+)"',
            r'"count"\s*:\s*(\d+)\s*,\s*"type"\s*:\s*"VIEW"',
            r'Просмотров[^0-9]*([\d\s]+)'
        ]
        for p in patterns:
            m = re.search(p, html)
            if m:
                return int(m.group(1).replace(" ", ""))
        return None

    # desktop
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        v = parse(r.text)
        if v is not None:
            return v
    except:
        pass

    # mobile
    if "ok.ru" in url and "m.ok.ru" not in url:
        try:
            murl = url.replace("ok.ru", "m.ok.ru")
            r = requests.get(murl, headers=HEADERS, timeout=15)
            v = parse(r.text)
            if v is not None:
                return v
        except:
            pass

    # embed
    vid = re.search(r'/video/(\d+)', url)
    if vid:
        try:
            eurl = f"https://ok.ru/videoembed/{vid.group(1)}"
            r = requests.get(eurl, headers=HEADERS, timeout=15)
            v = parse(r.text)
            if v is not None:
                return v
        except:
            pass

    return None

# ---------------- RuTube ----------------
def rutube_views(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    html = r.text
    m = re.search(r'"views"\s*:\s*(\d+)', html)
    return int(m.group(1)) if m else None

# ---------------- Telegram ----------------
def telegram_views(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    html = r.text
    m = re.search(r'class="tgme_widget_message_views">([\d\s]+)', html)
    return int(m.group(1).replace(" ", "")) if m else None

# ---------------- Dzen ----------------
def dzen_views(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    html = r.text
    m = re.search(r'Просмотров[^0-9]*([\d\s]+)', html)
    return int(m.group(1).replace(" ", "")) if m else None

# ---------------- ROUTE ----------------
@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    error = None

    if request.method == "POST":
        url = request.form["url"].strip()

        try:
            if "vk.com" in url:
                if "wall" in url:
                    m = re.search(r"wall(-?\d+)_(\d+)", url)
                    result = vk_post_views(m.group(1), m.group(2)) if m else None
                elif "video" in url:
                    m = re.search(r"video(-?\d+)_(\d+)", url)
                    result = vk_video_views(m.group(1), m.group(2)) if m else None

            elif "ok.ru" in url:
                result = ok_views(url)

            elif "youtube.com" in url or "youtu.be" in url:
                result = youtube_views(url)

            elif "rutube.ru" in url:
                result = rutube_views(url)

            elif "t.me" in url:
                result = telegram_views(url)

            elif "dzen.ru" in url:
                result = dzen_views(url)

            else:
                error = "Платформа не поддерживается"

            if result is None and not error:
                error = "Не удалось определить количество просмотров"
            else:
                result = f"Просмотры: {result}"

        except Exception as e:
            error = f"Ошибка: {e}"

    return render_template_string(HTML, result=result, error=error)

if __name__ == "__main__":
    app.run()
