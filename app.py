import os
import re
import requests
from flask import Flask, request, render_template_string
from bs4 import BeautifulSoup

app = Flask(__name__)

### ------------------ HTML UI ------------------------

HTML = """
<!doctype html>
<title>Social Views Checker</title>
<h2>Проверка просмотров</h2>
<form method="post">
  <input name="url" style="width:450px" placeholder="Вставьте ссылку VK / OK / YouTube" required>
  <button type="submit">Проверить</button>
</form>
{% if error %}
  <p style="color:red">{{ error }}</p>
{% endif %}
{% if views is not none %}
  <h3>Просмотры: {{ views }}</h3>
{% endif %}
"""

### ---------------- VK через API --------------------

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

### ---------------- OK.RU через HTML + mobile fallback ---------------

UA = {
    "User-Agent":
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
}

def parse_ok(html_text):
    # JSON поля
    m = re.search(r'"viewsCount"\s*:\s*([0-9]+)', html_text)
    if m: return int(m.group(1))

    m = re.search(r'"viewCount"\s*:\s*([0-9]+)', html_text)
    if m: return int(m.group(1))

    # html текст
    soup = BeautifulSoup(html_text, "lxml")
    tag = soup.find("span", class_="vp_cnt")
    if tag:
        digits = re.sub(r"\D+", "", tag.text)
        if digits: return int(digits)

    return None

def get_ok_views(url):
    try:
        # 1 попытка — обычная страница
        r = requests.get(url, headers=UA, timeout=10)
        v = parse_ok(r.text)
        if v: return v

        # 2 попытка — мобильная версия
        m_url = url.replace("://ok.ru", "://m.ok.ru")
        r = requests.get(m_url, headers=UA, timeout=10)
        v = parse_ok(r.text)
        if v: return v

        # 3 попытка — embed
        em_url = url.replace("ok.ru/video/", "ok.ru/videoembed/")
        r = requests.get(em_url, headers=UA, timeout=10)
        v = parse_ok(r.text)
        if v: return v

    except Exception as e:
        print("OK ERROR:", e)

    return None

### ---------------- Stub для YouTube (позже включим) ----------------

def get_youtube_views(url):
    return None

### ---------------- Controller ----------------------

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


# prod launch
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
