#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloud-ready app: YouTube + OK.ru + RuTube views
- YouTube via API (YOUTUBE_API_KEY)
- OK/RuTube via HTML/JSON-LD parsing (best-effort)
"""
import os, re, csv, io
from datetime import date
from flask import Flask, render_template, request, send_file
import requests
from bs4 import BeautifulSoup

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/videos"
UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

YT_PATTERNS = [
    r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([A-Za-z0-9_\-]{6,})",
    r"(?:https?://)?(?:www\.)?youtu\.be/([A-Za-z0-9_\-]{6,})",
    r"(?:https?://)?(?:m\.)?youtube\.com/watch\?v=([A-Za-z0-9_\-]{6,})",
    r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([A-Za-z0-9_\-]{6,})",
]

def detect_platform(url: str) -> str:
    u = url.lower()
    if "youtu" in u: return "youtube"
    if "ok.ru" in u or "odnoklassniki" in u: return "ok"
    if "rutube.ru" in u: return "rutube"
    if "dzen.ru" in u or "zen.yandex" in u: return "dzen"
    return "unknown"


def yt_extract_id(token: str):
    token = token.strip()
    if re.fullmatch(r"[A-Za-z0-9_\-]{6,}", token): return token
    for p in YT_PATTERNS:
        m = re.search(p, token)
        if m: return m.group(1)
    return None

def http_get(url: str) -> str:
    r = requests.get(url, headers=UA, timeout=25)
    r.raise_for_status()
    return r.text

def parse_int(s):
    if s is None: return None
    if isinstance(s, int): return s
    if isinstance(s, str):
        s = s.replace("\u00A0"," ").replace(","," ").strip()
        digits = re.sub(r"[^\d]", "", s)
        return int(digits) if digits.isdigit() else None
    return None

def extract_views_jsonld(html: str):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", {"type":"application/ld+json"}):
        try:
            import json
            data = json.loads(tag.string or "")
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for obj in items:
            stats = obj.get("interactionStatistic") or obj.get("interactionStatistics")
            if not stats: continue
            stats = stats if isinstance(stats, list) else [stats]
            for st in stats:
                it = st.get("interactionType")
                if isinstance(it, dict): it = it.get("@type")
                if (isinstance(it, str) and "WatchAction" in it) or st.get("@type")=="InteractionCounter":
                    v = parse_int(st.get("userInteractionCount"))
                    if v is not None: return v
    return None

def extract_views_generic(html: str):
    m = re.search(r'"viewCount"\s*:\s*"?([\d\s,\.]+)"?', html)
    if m: return parse_int(m.group(1))
    m = re.search(r'"views"\s*:\s*"?([\d\s,\.]+)"?', html)
    if m: return parse_int(m.group(1))
    m = re.search(r'(?:Просмотров|просмотров|ПРОСМОТРОВ)[^\d]{0,10}([\d\s\u00A0,\.]+)', html)
    if m: return parse_int(m.group(1))
    return None

def fetch_views_ok(url: str):
    """
    Пытаемся вытащить просмотры с OK.ru:
    1) пробуем оригинальную ссылку
    2) пробуем мобильную версию m.ok.ru (часто там данные отдаются сервером)
    3) несколько шаблонов (JSON-LD + популярные поля)
    """
    try:
        html = http_get(url)
        v = extract_views_jsonld(html) or extract_views_generic(html)
        if v is not None:
            return v
    except Exception:
        pass

    # Попробуем мобильную версию (сервер часто рендерит больше данных)
    try:
        # если ссылка уже мобильная — просто используем её
        m_url = url
        if "://ok.ru/" in url and "://m.ok.ru/" not in url:
            m_url = url.replace("://ok.ru/", "://m.ok.ru/")
        html = http_get(m_url)
        # Доп. паттерны для OK:
        #  - JSON-LD
        v = extract_views_jsonld(html)
        if v is not None:
            return v
        #  - data-* и inline JSON
        import re as _re
        # "viewsCount": 12345
        m = _re.search(r'"viewsCount"\s*:\s*([0-9]{1,12})', html)
        if m:
            return int(m.group(1))
        # "viewCount": "12 345"
        m = _re.search(r'"viewCount"\s*:\s*"([\d\s\u00A0,\.]+)"', html)
        if m:
            from html import unescape
            return parse_int(unescape(m.group(1)))
        # Текстовые варианты (Просмотров 12 345)
        m = _re.search(r'(?:Просмотров|просмотров)[^\d]{0,10}([\d\s\u00A0,\.]+)', html)
        if m:
            return parse_int(m.group(1))
    except Exception:
        pass

    return None


def fetch_views_rutube(url: str):
    try:
        html = http_get(url)
        return extract_views_jsonld(html) or extract_views_generic(html)
    except Exception:
        return None

def fetch_views_dzen(url: str):
    """
    Яндекс Дзен: пробуем вытащить число просмотров из HTML.
    1) JSON-LD (interactionStatistic/WatchAction)
    2) Популярные поля (views, viewCount, watchCount)
    3) Русский текст "Просмотров 12 345"
    """
    try:
        html = http_get(url)
        v = extract_views_jsonld(html)
        if v is not None:
            return v

        # Частые JSON-поля
        import re as _re
        for pattern in [
            r'"views"\s*:\s*"?([\d\s\u00A0,\.]+)"?',
            r'"viewCount"\s*:\s*"?([\d\s\u00A0,\.]+)"?',
            r'"watchCount"\s*:\s*"?([\d\s\u00A0,\.]+)"?',
        ]:
            m = _re.search(pattern, html)
            if m:
                return parse_int(m.group(1))

        # Текстовые варианты
        m = _re.search(r'(?:Просмотров|просмотров|ПРОСМОТРОВ)[^\d]{0,10}([\d\s\u00A0,\.]+)', html)
        if m:
            return parse_int(m.group(1))

    except Exception:
        pass
    return None


def fetch_views_youtube(urls: list[str]):
    # batch by ids
    ids, id_by_url = [], {}
    for u in urls:
        vid = yt_extract_id(u)
        if vid and vid not in id_by_url:
            id_by_url[u] = vid
            ids.append(vid)
    if not ids or not YOUTUBE_API_KEY:
        return {u: None for u in urls}
    out = {u: None for u in urls}
    for i in range(0, len(ids), 50):
        batch = ids[i:i+50]
        r = requests.get(YOUTUBE_API_URL, params={
            "part":"statistics","id":",".join(batch),"key":YOUTUBE_API_KEY
        }, timeout=25)
        r.raise_for_status()
        data = r.json()
        stats = {it["id"]: it.get("statistics",{}).get("viewCount") for it in data.get("items",[])}
        for u, vid in id_by_url.items():
            if vid in batch:
                out[u] = stats.get(vid)
    return out

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
            by_platform = {"youtube":[], "ok":[], "rutube":[], "unknown":[]}
            for u in urls:
                by_platform[detect_platform(u)].append(u)

            rows = []
            # YouTube
            if by_platform["youtube"]:
                yt_map = fetch_views_youtube(by_platform["youtube"])
                for u in by_platform["youtube"]:
                    rows.append((u, "YouTube", yt_map.get(u,"")))
            # OK
            for u in by_platform["ok"]:
                v = fetch_views_ok(u)
                rows.append((u, "OK.ru", v if v is not None else ""))
            # RuTube
            for u in by_platform["rutube"]:
                v = fetch_views_rutube(u)
                rows.append((u, "RuTube", v if v is not None else ""))
            # Dzen
            for u in by_platform["dzen"]:
                v = fetch_views_dzen(u)
                rows.append((u, "Dzen", v if v is not None else ""))
            # Unknown
            for u in by_platform["unknown"]:
                rows.append((u, "Unknown", ""))

        except Exception as e:
            error = str(e)

    return render_template("index.html", rows=rows, links=links, today=date.today(), error=error)

@app.route("/download", methods=["POST"])
def download():
    links = request.form.get("links","")
    urls = [u.strip() for u in links.splitlines() if u.strip()]
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["url","platform","views"])
    # reuse same logic for consistency
    by_platform = {"youtube":[], "ok":[], "rutube":[], "dzen":[], "unknown":[]}
    for u in urls:
        by_platform[detect_platform(u)].append(u)
    yt_map = fetch_views_youtube(by_platform["youtube"]) if by_platform["youtube"] else {}
    for u in urls:
        p = detect_platform(u)
        if p=="youtube":
            v = yt_map.get(u,"")
            w.writerow([u,"YouTube",v])
        elif p=="ok":
            w.writerow([u,"OK.ru", fetch_views_ok(u) or ""])
        elif p=="rutube":
            w.writerow([u,"RuTube", fetch_views_rutube(u) or ""])
        elif p=="dzen":
            w.writerow([u, "Dzen", fetch_views_dzen(u) or ""])
        else:
            w.writerow([u,"Unknown",""])
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"social_views_{date.today()}.csv"
    )

@app.route("/healthz")
def healthz():
    return "ok", 200
