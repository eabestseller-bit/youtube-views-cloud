from flask import Flask, request, jsonify, render_template_string
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}

HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>VK Views Checker</title>
</head>
<body style="font-family: Arial; padding: 40px;">
    <h2>VK просмотры</h2>
    <form method="post">
        <input name="url" style="width:400px;" placeholder="https://vk.com/..." required>
        <button type="submit">Проверить</button>
    </form>
    {% if result %}
        <h3>Результат:</h3>
        <pre>{{ result }}</pre>
    {% endif %}
</body>
</html>
"""

def extract_views(html):
    soup = BeautifulSoup(html, "html.parser")

    # Видео / клипы
    match = re.search(r'"views":(\d+)', html)
    if match:
        return match.group(1)

    # Посты
    span = soup.find("span", class_="like_views")
    if span:
        return span.text.strip()

    return "Не удалось определить"

@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    if request.method == "POST":
        url = request.form.get("url")
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            result = extract_views(r.text)
        except Exception as e:
            result = f"Ошибка: {e}"
    return render_template_string(HTML, result=result)

@app.route("/api", methods=["GET"])
def api():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "url is required"}), 400

    r = requests.get(url, headers=HEADERS, timeout=10)
    views = extract_views(r.text)
    return jsonify({"views": views})

if __name__ == "__main__":
    app.run()
