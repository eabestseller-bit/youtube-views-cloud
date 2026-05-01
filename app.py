import os
import re
import csv
import io
import requests
from datetime import date
from flask import Flask, request, render_template_string, Response

app = Flask(__name__)

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/videos"

HTML = """
<h1>Проверка просмотров YouTube</h1>

<form method="post">
  <p>Вставьте ссылки — по одной в строке:</p>
  <textarea name="links" rows="12" cols="90">{{ links or "" }}</textarea><br><br>
  <button type="submit">Показать просмотры</button>
</form>

{% if rows %}
<h2>Результат на {{ today }}</h2>

<table border="1" cellpadding="8">
  <tr>
    <th>URL</th>
    <th>Video ID</th>
    <th>Просмотры</th>
    <th>Статус</th>
  </tr>
  {% for row in rows %}
  <tr>
    <td>{{ row.url }}</td>
    <td>{{ row.video_id }}</td>
    <td>{{ row.views }}</td>
    <td>{{ row.status }}</td>
  </tr>
  {% endfor %}
</table>

<br>
<form method="post" action="/download_csv">
  <textarea name="links" style="display:none;">{{ links }}</textarea>
  <button type="submit">Скачать CSV</button>
</form>
{% endif %}
"""

def get_youtube_id(url):
    patterns = [
        r"v=([^&]+)",
        r"youtu\.be/([^?&/]+)",
        r"shorts/([^?&/]+)",
        r"embed/([^?&/]+)"
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None

def get_youtube_views(video_id):
    if not YOUTUBE_API_KEY:
        return None

    params = {
        "part": "statistics",
        "id": video_id,
        "key": YOUTUBE_API_KEY
    }

    try:
        response = requests.get(YOUTUBE_API_URL, params=params, timeout=10)
        data = response.json()
        return int(data["items"][0]["statistics"]["viewCount"])
    except Exception:
        return None

def process_links(links_text):
    links = [line.strip() for line in links_text.splitlines() if line.strip()]
    rows = []

    for url in links:
        video_id = get_youtube_id(url)

        if not video_id:
            rows.append({
                "url": url,
                "video_id": "",
                "views": "",
                "status": "Ссылка не распознана"
            })
            continue

        views = get_youtube_views(video_id)

        rows.append({
            "url": url,
            "video_id": video_id,
            "views": views if views is not None else "",
            "status": "OK" if views is not None else "Не удалось получить просмотры"
        })

    return rows

@app.route("/", methods=["GET", "POST"])
def index():
    rows = []
    links = ""

    if request.method == "POST":
        links = request.form.get("links", "")
        rows = process_links(links)

    return render_template_string(
        HTML,
        rows=rows,
        links=links,
        today=date.today().strftime("%d.%m.%Y")
    )

@app.route("/download_csv", methods=["POST"])
def download_csv():
    links = request.form.get("links", "")
    rows = process_links(links)

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["URL", "Video ID", "Просмотры", "Статус"])

    for row in rows:
        writer.writerow([row["url"], row["video_id"], row["views"], row["status"]])

    csv_data = output.getvalue().encode("utf-8-sig")

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=youtube_views.csv"
        }
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0")
