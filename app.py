import os
import re
import requests
from flask import Flask, request, render_template_string

app = Flask(__name__)

VK_TOKEN = os.environ.get("VK_TOKEN")
VK_API = "https://api.vk.com/method"
VK_VERSION = "5.199"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

HTML = """
<!doctype html>
<title>Social Views Checker</title>
<h2>Проверка просмотров</h2>
<form method="post">
  <input name="url" style="width:500px" placeholder="Вставьте ссылку" required>
  <button>Проверить</button>
</form>
{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
{% if result %}<h3>{{ result }}</h3>{% endif %}
"""

# ---------- VK ----------
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

# ---------- OK ----------
def ok_views(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    html = r.text

    for pattern in [
        r'"viewsCount"\s*:\s*(\d+)',
        r'"viewCount"\s*:\s*"([\d\s]+)"',
        r'Просмотров[^0-9]*([\d\s]+)'
    ]:
        m = re.search(pattern, html)
        if m:
            return int(m.group(1).replace(" ", ""))
    return None

# ---------- YouTube ----------
def youtube_views(url):
    r = requests.get(
        "https://www.youtube.com/oembed",
        params={"url": url, "format": "json"},
        timeout=10
    )
    if r.status_code == 200:
        data = r.json()
        return data.get("view_count")
    return None

# ---------- RuTube ----------
def rutube_views(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    html = r.text
    m = re.search(r'"views"\s*:\s*(\d+)', html)
    return int(m.group(1)) if m else None

# ---------- Telegram ----------
def telegram_views(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    html = r.text
    m = re.search(r'class="tgme_widget_message_views">([\d\s]+)', html)
    return int(m.group(1).replace(" ", "")) if m else None

# ---------- Dzen ----------
def dzen_views(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    html = r.text
    m = re.search(r'Просмотров[^0-9]*([\d\s]+)', html)
    return int(m.group(1).replace(" ", "")) if m else None

# ---------- ROUTE ----------
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

            if result is not None:
                result = f"Просмотры: {result}"

        except Exception as e:
            error = f"Ошибка: {e}"

    return render_template_string(HTML, result=result, error=error)

if __name__ == "__main__":
    app.run()
