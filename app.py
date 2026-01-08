from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

def get_ok_views(url):
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code != 200:
            return None

        # 1. Пытаемся вытащить JSON конфиг
        m = re.search(r"data-module=\"OKVideo\"[^>]+data-options=\"([^\"]+)\"", r.text)
        if m:
            import html
            config_str = html.unescape(m.group(1))
            config = dict(re.findall(r'(\w+)\s*:\s*([0-9]+)', config_str))
            if "count" in config:
                return int(config["count"])

        # 2. Пытаемся вытащить просмотры из HTML
        soup = BeautifulSoup(r.text, "lxml")
        span = soup.find("span", {"class": "vp_cnt"})
        if span:
            text = span.text.strip()
            digits = ''.join(re.findall(r'\d+', text))
            if digits:
                return int(digits)

        return None
    except:
        return None

def get_youtube_views(url):
    return None  # временно выключено, чтобы не мешать деплою

@app.route("/", methods=["GET", "POST"])
def index():
    views = None
    error = None
    if request.method == "POST":
        url = request.form.get("url", "").strip()

        if "ok.ru" in url:
            views = get_ok_views(url)
        elif "youtu" in url:
            views = get_youtube_views(url)
        else:
            error = "Сайт пока не поддерживается"

        if views is None:
            error = "Не удалось определить количество просмотров"

    return render_template("index.html", views=views, error=error)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
