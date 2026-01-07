import os
import re
import requests
from flask import Flask, request, render_template_string
from playwright.sync_api import sync_playwright

app = Flask(__name__)

VK_TOKEN = os.environ.get("VK_TOKEN")
VK_API = "https://api.vk.com/method"
VK_VERSION = "5.199"

HTML = """
<!doctype html>
<title>Просмотры</title>
<h2>Просмотры по ссылке</h2>
<form method="post">
  <input name="url" style="width:500px" placeholder="Вставь ссылку VK / OK / YouTube" required>
  <button>Проверить</button>
</form>
{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
{% if views is not none %}<h3>Просмотры: {{ views }}</h3>{% endif %}
"""

# ---------- VK ----------
def vk_post_views(owner_id, post_id):
    r = requests.get(f"{VK_API}/wall.getById", params={
        "posts": f"{owner_id}_{post_id}",
        "access_token": VK_TOKEN,
        "v": VK_VERSION
    }).json()
    return r.get("response", [{}])[0].get("views", {}).get("count")

def vk_video_views(owner_id, video_id):
    r = requests.get(f"{VK_API}/video.get", params={
        "videos": f"{owner_id}_{video_id}",
        "access_token": VK_TOKEN,
        "v": VK_VERSION
    }).json()
    items = r.get("response", {}).get("items", [])
    return items[0].get("views") if items else None

# ---------- YouTube ----------
def youtube_views(url):
    html = requests.get(url).text
    m = re.search(r'"viewCount":"(\d+)"', html)
    return int(m.group(1)) if m else None

# ---------- OK (Playwright) ----------
def ok_video_views(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)

        page.wait_for_timeout(5000)

        content = page.content()
        browser.close()

        m = re.search(r'"viewCount":(\d+)', content)
        if m:
            return int(m.group(1))

        m = re.search(r'Просмотров[:\s]+([\d\s]+)', content)
        if m:
            return int(m.group(1).replace(" ", ""))

        return None

# ---------- ROUTE ----------
@app.route("/", methods=["GET", "POST"])
def index():
    views = None
    error = None

    if request.method == "POST":
        url = request.form["url"].strip()

        try:
            if "vk.com" in url:
                post = re.search(r"wall(-?\d+)_(\d+)", url)
                video = re.search(r"video(-?\d+)_(\d+)", url)

                if post:
                    views = vk_post_views(post.group(1), post.group(2))
                elif video:
                    views = vk_video_views(video.group(1), video.group(2))
                else:
                    error = "Ссылка VK не распознана"

            elif "ok.ru" in url:
                views = ok_video_views(url)

            elif "youtube.com" in url or "youtu.be" in url:
                views = youtube_views(url)

            else:
                error = "Платформа не поддерживается"

            if views is None and not error:
                error = "Не удалось определить количество просмотров"

        except Exception as e:
            error = f"Ошибка: {str(e)}"

    return render_template_string(HTML, views=views, error=error)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
