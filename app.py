import os
import re
import requests
from flask import Flask, request, render_template_string
from bs4 import BeautifulSoup

app = Flask(__name__)

HTML = """
<!doctype html>
<title>Social Views Checker</title>
<h2>Проверка просмотров</h2>
<form method="post">
  <input name="url" style="width:450px" placeholder="VK / OK / YouTube" required>
  <button type="submit">Проверить</button>
</form>
{% if error %}
  <p style="color:red">{{ error }}</p>
{% endif %}
{% if views is not none %}
  <h3>Просмотры: {{ views }}</h3>
{% endif %}
"""

### ---------- VK (через API) ----------
VK_TOKEN = os.environ.get("VK_TOKEN")
VK_API = "https://api.vk.com/method"
VK_VERSION = "5.199"

def get_vk_views(url):
    post = re.search(r"wall(-?\d+)_(\d+)", url)
    video = re.search(r"video(-?\d+)_(\d+)", url)

    if post:
        owner, post_id = post.group(1), post.group(2)
        r = requests.get(f"{VK_API}/wall.getById", params={
            "posts": f"{owner}_{post_id}",
            "access_token": VK_TOKEN,
            "v": VK_VERSION
        }).json()
        try:
            return r["response"][0]["views"]["count"]
        except:
            return None

    if video:
        owner, vid = video.group(1), video.group(2)
        r = requests.get(f"{VK_API}/video.get", params={
            "videos": f"{owner}_{vid}",
            "access_token": VK_TOKEN,
            "v": VK_VERSION
        }).json()
        try:
            return r["response"]["items"][0]["views"]
        except:
            return None
    return None


### ---------- OK.RU (Усиленный парсер) ----------

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15",
    "Accept-Language": "ru-RU,ru",
    "Referer": "https://m.ok.ru",
    "Cookie": "stid=A=B"
}

def extract_ok(html_text):
    # JSON варианты
    for pat in [
        r'"viewCount"\s*:\s*([0-9]+)',
        r'"viewsCount"\s*:\s*([0-9]+)',
        r'"count"\s*:\s*([0-9]+)'
    ]:
        m = re.search(pat, html_text)
        if m:
            return int(m.group(1))

    # HTML текст
    soup = BeautifulSoup(html_text, "lxml")
    # vp_cnt — старый вариант
    tag = soup.find("span", class_="vp_cnt")
    if tag:
        digits = re.sub(r"\D+", "", tag.get_text(strip=True))
        if digits:
            return int(digits)

    # словесный
    m = re.search(r"Просмотров[^0-9]*([0-9\s]+)", html_text)
    if m:
        return int(m.group(1).replace(" ", ""))

    return None

def get_ok_views(url):
    candidates = [
        url,
        url.replace("://ok.ru", "://m.ok.ru"),
        url.replace("ok.ru/video/", "ok.ru/videoembed/"),
        url.replace("ok.ru/video/", "m.ok.ru/video/"),
    ]

    for u in candidates:
        try:
            r = requests.get(u, headers=HEADERS, timeout=10)
            v = extract_ok(r.text)
            if v:
                return v
        except Exception as e:
            print("OK ERROR:", e)

    return None


### ---------- YouTube (пока выключено) ----------

def get_youtube_views(url):
    return None


### ---------- Контроллер ----------
@app.route("/", methods=["GET", "POST"])
def index():
    views = None
    error = None

    if request.method == "POST":
        url = request.form.get("url", "").strip()

        if "vk.com" in url or "vkvideo.ru" in url:
            views = get_vk_views(url)

        elif "ok.ru" in url:
            views = get_ok_views(url)

        elif "youtu" in url:
            views = get_youtube_views(url)

        else:
            error = "Сайт пока не поддерживается"

        if views is None and not error:
            error = "Не удалось определить количество просмотров"

    return render_template_string(HTML, views=views, error=error)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
