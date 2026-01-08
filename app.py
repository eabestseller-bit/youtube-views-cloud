import os
import re
import requests
from flask import Flask, request, render_template_string
from bs4 import BeautifulSoup

app = Flask(__name__)

VK_TOKEN = os.environ.get("VK_TOKEN")
OK_COOKIE = os.environ.get("OK_COOKIE")
VK_API = "https://api.vk.com/method"
VK_VERSION = "5.199"

HTML = """
<!doctype html>
<title>Просмотры соцсетей</title>
<h2>Проверка просмотров</h2>
<form method="post">
  <input name="url" style="width:400px" placeholder="Введите ссылку" required>
  <button>Проверить</button>
</form>

{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
{% if views is not none %}<h3>Просмотры: {{ views }}</h3>{% endif %}
"""


# ========= VK =========
def get_vk_views(url):
    post = re.search(r"wall(-?\d+)_(\d+)", url)
    video = re.search(r"video(-?\d+)_(\d+)", url)
    vkvideo = re.search(r"vkvideo\.ru/video(-?\d+)_(\d+)", url)

    if vkvideo:
        owner, vid = vkvideo.group(1), vkvideo.group(2)
    elif post:
        owner, vid = post.group(1), post.group(2)
    elif video:
        owner, vid = video.group(1), video.group(2)
    else:
        return None

    r = requests.get(f"{VK_API}/wall.getById", params={
        "posts": f"{owner}_{vid}",
        "access_token": VK_TOKEN,
        "v": VK_VERSION
    }).json
