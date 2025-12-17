from flask import Flask, request, jsonify, render_template_string
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
                  "Mobile/15E148 Safari/604.1"
}


def normalize_vk_url(url: str) -> str:
    if "vk.com" in url and "m.vk.com" not in url:
        return url.replace("vk.com", "m.vk.com")
    return url


def extract_views(html: str):
    soup = BeautifulSoup(html, "html.parser")

    # Ищем любые упоминания просмотров
    for tag in soup.find_all(["div", "span"]):
        text = tag.get_text(strip=True)
        if "просмотр" in text:
            return text

    return None


HTML_PAGE = """
<!doctype html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>VK Views</title>
    <style>
        body { font-family: Arial, sans-serif; background:#f4f4f4; }
        .box { max-width:500px; margin:60px auto; background:#fff;
               padding:20px; border-radius:8px; box-shadow:0 0 10px rgba(0,0,0,.1);}
        input, button { width:100%; padding:10px; margin-top:10px; }
        button { background:#4a76a8; color:white; border:none; cursor:pointer; }
        .result { margin-top:15px; font-size:18px; }
    </style>
</head>
<body>
<div class="box">
    <h2>VK — количество просмотров</h2>
    <form method="post">
        <input name="url" placeholder="Вставьте ссылку VK" required>
        <button type="submit">Проверить</button>
    </form>
    {% if result %}
        <div class="result">{{ result }}</div>
    {% endif %}
</div>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    result = None

    if request.method == "POST":
        url = request.form.get("url", "").strip()
        if url:
            url = normalize_vk_url(url)
            try:
                r = requests.get(url, headers=HEADERS, timeout=10)
                views = extract_views(r.text)
                if views:
                    result = f"Просмотры: {views}"
                else:
                    result = "❌ Не удалось определить количество просмотров"
            except Exception as e:
                result = f"Ошибка: {e}"

    return render_template_string(HTML_PAGE, result=result)


@app.route("/api")
def api():
    url = request.args.get("url", "").strip()
    if not url:
        return jsonify({"error": "URL не передан"}), 400

    url = normalize_vk_url(url)

    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        views = extract_views(r.text)
        if views:
            return jsonify({"views": views})
        else:
            return jsonify({"error": "Просмотры не найдены"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
