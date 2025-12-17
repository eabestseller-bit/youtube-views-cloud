#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Social Views Checker
Поддержка: YouTube + OK.ru + RuTube + Dzen + VK Video + Telegram

VK: ТОЛЬКО просмотры через VK API (video.get)
"""

import os, re, csv, io, json, sys, logging
from datetime import date
from urllib.parse import urlsplit, urlunsplit

from flask import Flask, render_template, request, send_file
import requests
from bs4 import BeautifulSoup

# ---------- логирование ----------
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger("views")

# ---------- конфиг ----------
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
VK_TOKEN = os.getenv("VK_TOKEN")
DISABLE_DZEN = os.getenv("DISABLE_DZEN", "0") == "1"

YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/videos"
VK_API_URL = "https://api.vk.com/method/video.get"
VK_API_VERSION = "5.131"

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# ---------- утилиты ----------

YT_PATTERNS = [
    r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([A-Za-z0-9_\-]{6,})",
    r"(?:https?://)?(?:www\.)?youtu\.be/([A-Za-z0-9_\-]{6,})",
    r"(?:https?://)?(?:m\.)?youtube\.com/watch\?v=([A-Za-z0-9_\-]{6,})",
    r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([A-Za-z0-9_\-]{6,})",
]

def normalize_url(u: str) -> str:
    try:
        sp = urlsplit(u.strip())
        return urlunsplit((sp.scheme, sp.netloc, sp.path, "", ""))
    except Exception:
        return u.strip()

def detect_platform(url: str) -> str:
    u = url.lower()
    if "youtu" in u: return "youtube"
    if "ok.ru" in u: return "ok"
    if "rutube.ru" in u: return "rutube"
    if "dzen.ru" in u or "zen.yandex" in u: return "dzen"
    if "vk.com" in u or "vkvideo.ru" in u: return "vk"
    if "t.me" in u or "telegram.me" in u: return "telegram"
    return "unknown"

def yt_extract_id(token: str):
    token = token.strip()
    if re.fullmatch(r"[A-Za-z0-9_\-]{6,}", token):
        return token
    for p in YT_PATTERNS:
        m = re.search(p, token)
        if m:
            return m.group(1)
    return None

def http_get(url: str) -> str:
    r = requests.get(url, headers=UA, timeout=25)
    r.raise_for_status()
    return r.text

def parse_int(s):
    if s is None: return None
    if isinstance(s, int): return s
    s = re.sub(r"[^\d]", "", str(s))
    return int(s) if s.isdigit() else None

# ---------- YouTube ----------

def fetch_views_youtube(urls):
    out = {u: None for u in urls}
    if not urls or not YOUTUBE_API_KEY:
        return out

    ids, mapu = [], {}
    for u in urls:
        vid = yt_extract_id(u)
        if vid:
            ids.append(vid)
            mapu[u] = vid

    for i in range(0, len(ids), 50):
        batch = ids[i:i+50]
        r = requests.get(YOUTUBE_API_URL, params={
            "part": "statistics",
            "id": ",".join(batch),
            "key": YOUTUBE_API_KEY
        }, timeout=25)
        r.raise_for_status()
        data = r.json()

        stats = {
            it["id"]: it["statistics"].get("viewCount")
            for it in data.get("items", [])
        }

        for u, vid in mapu.items():
            if vid in stats:
                out[u] = stats[vid]

    return out

# ---------- VK Video (API ONLY) ----------

def extract_vk_video_id(url: str):
    """
    Извлекает ID формата -123_456
    """
    m = re.search(r'video(-?\d+_\d+)', url)
    if m:
        return m.group(1)
    return None

def fetch_views_vk(url: str):
    """
    VK Video → ТОЛЬКО просмотры через VK API
    """
    if not VK_TOKEN:
        log.info("[VK] VK_TOKEN not set")
        return None

    video_id = extract_vk_video_id(url)
    if not video_id:
        log.info("[VK] cannot extract video id")
        return None

    params = {
        "videos": video_id,
        "access_token": VK_TOKEN,
        "v": VK_API_VERSION
    }

    r = requests.get(VK_API_URL, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()

    if "response" in data and data["response"]["items"]:
        return data["response"]["items"][0].get("views")

    return None

# ---------- Telegram ----------

def fetch_views_telegram(url: str):
    try:
        html = http_get(url)
        soup = BeautifulSoup(html, "html.parser")
        el = soup.select_one(".tgme_widget_message_views")
        if el:
            return parse_int(el.text)
    except Exception:
        pass
    return None

# ---------- Flask ----------

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    error = None
    rows = None
    links = ""

    if request.method == "POST":
        try:
            links = request.form.get("links", "")
            urls = [normalize_url(u) for u in links.splitlines() if u.strip()]

            by = {
                "youtube": [], "ok": [], "rutube": [],
                "dzen": [], "vk": [], "telegram": [], "unknown": []
            }

            for u in urls:
                by[detect_platform(u)].append(u)

            rows = []

            yt_map = fetch_views_youtube(by["youtube"])
            for u in by["youtube"]:
                rows.append((u, "YouTube", yt_map.get(u, "") or ""))

            for u in by["vk"]:
                rows.append((u, "VK", fetch_views_vk(u) or ""))

            for u in by["telegram"]:
                rows.append((u, "Telegram", fetch_views_telegram(u) or ""))

            for u in by["unknown"]:
                rows.append((u, "Unknown", ""))

        except Exception as e:
            error = str(e)

    return render_template(
        "index.html",
        rows=rows,
        links=links,
        today=date.today(),
        error=error
    )

@app.route("/healthz")
def healthz():
    return "ok", 200
