#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloud-ready Flask app for YouTube views lookup.
- Uses env var YOUTUBE_API_KEY
- Production entry point: gunicorn 'app:app'
"""
import os, re, csv, io
from flask import Flask, render_template, request, send_file, abort
import requests
from datetime import date

API_KEY = os.getenv("YOUTUBE_API_KEY")  # <-- set in cloud provider dashboard
if not API_KEY:
    # Render/Railway/Heroku will show this in logs until you set the env var
    print("WARNING: YOUTUBE_API_KEY is not set. The app will not work without it.")

API_URL = "https://www.googleapis.com/youtube/v3/videos"
PATTERNS = [
    r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([A-Za-z0-9_\-]{6,})",
    r"(?:https?://)?(?:www\.)?youtu\.be/([A-Za-z0-9_\-]{6,})",
    r"(?:https?://)?(?:m\.)?youtube\.com/watch\?v=([A-Za-z0-9_\-]{6,})",
    r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([A-Za-z0-9_\-]{6,})",
]

def extract_id(url: str):
    url = url.strip()
    if re.fullmatch(r"[A-Za-z0-9_\-]{6,}", url):
        return url
    for p in PATTERNS:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None

def fetch_views(video_ids):
    if not API_KEY:
        return {}
    if not video_ids:
        return {}
    r = requests.get(API_URL, params={
        "part": "statistics",
        "id": ",".join(video_ids),
        "key": API_KEY
    }, timeout=20)
    if r.status_code != 200:
        # Bubble error to UI
        raise RuntimeError(f"API error {r.status_code}: {r.text}")
    data = r.json()
    results = {}
    for item in data.get("items", []):
        vid = item.get("id")
        views = item.get("statistics", {}).get("viewCount")
        results[vid] = views
    return results

app = Flask(__name__)

@app.route("/", methods=["GET","POST"])
def index():
    error = None
    links = ""
    rows = None
    if request.method == "POST":
        try:
            links = request.form.get("links","")
            urls = [u.strip() for u in links.splitlines() if u.strip()]
            ids = [extract_id(u) for u in urls if extract_id(u)]
            views = fetch_views(ids) if ids else {}
            rows = [(u, views.get(extract_id(u), "")) for u in urls]
        except Exception as e:
            error = str(e)
    return render_template("index.html", rows=rows, links=links, today=date.today(), error=error)

@app.route("/download", methods=["POST"])
def download():
    links = request.form.get("links","")
    urls = [u.strip() for u in links.splitlines() if u.strip()]
    ids = [extract_id(u) for u in urls if extract_id(u)]
    views = fetch_views(ids) if ids else {}
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["url","views"])
    for u in urls:
        w.writerow([u, views.get(extract_id(u), "")])
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"youtube_views_{date.today()}.csv"
    )

# Health check
@app.route("/healthz")
def healthz():
    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT","5000")), debug=False)
