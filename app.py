import os
import re
import requests
from flask import Flask, request, render_template_string
from bs4 import BeautifulSoup

app = Flask(__name__)

### VK ###
VK_TOKEN = os.environ.get("VK_TOKEN")
VK_API = "https://api.vk.com/method"
VK_VERSION = "5.199"

### ОДНОКЛАССНИКИ COOKIE ###
OK_COOKIE = os.environ.get("OK_COOKIE")  # вставь свои куки в Render как OK_COOKIE

HTML = """
<!doctype html>
<title>Views Checker</title>
<h2>Проверка просмотров</h2>

<form method="post">
  <input name="url" style="width:450px" placeholder="Ссылка на ОК / YouTube / VK / RuTube / Дзен / Telegram" required>
  <button>Проверить</button>
</form>

{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
{% if views is not none %}<h3>Просмотры: {{ views }}</h3>{% endif %}
"""

################ VK ################

def get_vk_post(owner_id, post_id):
    r = requests.get(f"{VK_API}/wall.getById", params={
        "posts": f"{owner_id}_{post_id}",
        "access_token": VK_TOKEN,
        "v": VK_VERSION
    }).json()
    try:
        return r["response"][0]["views"]["count"]
    except:
        return None

def get_vk_video(owner_id, video_id):
    r = requests.get(f"{VK_API}/video.get", params={
        "videos": f"{owner_id}_{video_id}",
        "access_token": VK_TOKEN,
        "v": VK_VERSION
    }).json()
    try:
        return r["response"]["items"][0]["views"]
    except:
        return None

################ YouTube ################

def get_youtube(url):
    yt_id = None
    if "shorts" in url:
        m = re.search(r"shorts/([A-Za-z0-9_-]{5,})", url)
        if m: yt_id = m.group(1)
    else:
        m = re.search(r"v=([A-Za-z0-9_-]{5,})", url)
        if m: yt_id = m.group(1)

    if not yt_id:
        return None

    api = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={yt_id}&format=json"
    r = requests.get(api)
    if r.status_code != 200:
        return None

    # к сожалению эта точка не даёт просмотры — только проверку id
    # вернем None чтобы функция ниже не сломалась
    return None

################ Одноклассники (через HTML + cookie) ################

def get_ok(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17 Safari/605.1.15",
            "Referer": "https://ok.ru/",
            "Accept-Language": "ru-RU,ru;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

        cookies = {}
        if OK_COOKIE:
            for part in OK_COOKIE.split(";"):
                if "=" in part:
                    k,v = part.strip().split("=",1)
                    cookies[k] = v

        r = requests.get(url, headers=headers, cookies=cookies, timeout=10)
        if r.status_code != 200:
            return None

        soup = BeautifulSoup(r.text, "lxml")

        # ищем просмотры в <span class="video-view-count">1234</span>
        el = soup.find("span", {"class": "video-view-count"})
        if el:
            digits = re.sub(r"\D", "", el.text)
            return int(digits)

        return None
    except:
        return None

################ RuTube (через HEAD) ################

def get_rutube(url):
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return None
        m = re.search(r'"viewCount":(\d+)', r.text)
        if m:
            return int(m.group(1))
    except:
        return None

################ Дзен ################

def get_dzen(url):
    try:
        r = requests.get(url, timeout=10)
        m = re.search(r'"viewCount":(\d+)', r.text)
        if m:
            return int(m.group(1))
    except:
        return None

################ Telegram ################

def get_telegram(url):
    try:
        r = requests.get(url, timeout=10)
        m = re.search(r'"views":(\d+)', r.text)
        if m:
            return int(m.group(1))
    except:
        return None

################ Flask ################

@app.route("/", methods=["GET", "POST"])
def index():
    views = None
    error = None

    if request.method == "POST":
        url = request.form["url"].strip()

        if "vk.com" in url:
            post = re.search(r"wall(-?\d+)_(\d+)", url)
            video = re.search(r"video(-?\d+)_(\d+)", url)
            if post:
                views = get_vk_post(post.group(1), post.group(2))
            elif video:
                views = get_vk_video(video.group(1), video.group(2))
        elif "ok.ru" in url:
            views = get_ok(url)
        elif "youtube.com" in url or "youtu.be" in url:
            views = get_youtube(url)
        elif "rutube" in url:
            views = get_rutube(url)
        elif "dzen.ru" in url:
            views = get_dzen(url)
        elif "t.me" in url:
            views = get_telegram(url)
        else:
            error = "Ссылка не распознана"

        if views is None and not error:
            error = "Не удалось определить количество просмотров"

    return render_template_string(HTML, views=views, error=error)

if __name__ == "__main__":
    app.run()
