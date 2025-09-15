#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloud app: YouTube + OK.ru + RuTube + Dzen
- YouTube: через API (env YOUTUBE_API_KEY)
- OK/RuTube: парсинг HTML/JSON-LD
- Dzen: рендер через Playwright (Chromium), чтобы увидеть счётчик на видео
"""

import os, re, csv, io, json
from datetime import date
from urllib.parse import urlsplit, urlunsplit

from flask import Flask, render_template, request, send_file
import requests
from bs4 import BeautifulSoup

# --------- конфиг
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/videos"
UA = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0 Safari/537.36")
}

# --------- утилиты

YT_PATTERNS = [
    r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([A-Za-z0-9_\-]{6,})",
    r"(?:https?://)?(?:www\.)?youtu\.be/([A-Za-z0-9_\-]{6,})",
    r"(?:https?://)?(?:m\.)?youtube\.com/watch\?v=([A-Za-z0-9_\-]{6,})",
    r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([A-Za-z0-9_\-]{6,})",
]

def normalize_url(u: str) -> str:
    """Обрезаем query/fragment (?share_to=...) — мешают парсингу."""
    try:
        sp = urlsplit(u.strip())
        return urlunsplit((sp.scheme, sp.netloc, sp.path, "", ""))
    except Exception:
        return u.strip()

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
        s = s.replace("\u00A0"," ").replace(",", " ").strip()
        digits = re.sub(r"[^\d]", "", s)
        return int(digits) if digits.isdigit() else None
    return None

def extract_views_jsonld(html: str):
    """Пытаемся найти interactionStatistic→WatchAction→userInteractionCount."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for obj in items:
            stats = obj.get("interactionStatistic") or obj.get("interactionStatistics")
            if not stats:
                continue
            stats = stats if isinstance(stats, list) else [stats]
            for st in stats:
                it = st.get("interactionType")
                if isinstance(it, dict):
                    it = it.get("@type")
                if (isinstance(it, str) and "WatchAction" in it) or st.get("@type") == "InteractionCounter":
                    v = parse_int(st.get("userInteractionCount"))
                    if v is not None:
                        return v
    return None

def extract_views_generic(html: str):
    for pattern in [
        r'"viewCount"\s*:\s*"?([\d\s,\.]+)"?',
        r'"views"\s*:\s*"?([\d\s,\.]+)"?',
        r'(?:Просмотров|просмотров|ПРОСМОТРОВ)[^\d]{0,10}([\d\s\u00A0,\.]+)',
    ]:
        m = re.search(pattern, html)
        if m:
            return parse_int(m.group(1))
    return None

# --------- площадки

def fetch_views_ok(url: str):
    """OK.ru: обычная страница → мобильная m.ok.ru → доп. паттерны."""
    try:
        html = http_get(url)
        v = extract_views_jsonld(html) or extract_views_generic(html)
        if v is not None: return v
    except Exception:
        pass
    try:
        m_url = url if "://m.ok.ru/" in url else url.replace("://ok.ru/", "://m.ok.ru/")
        html = http_get(m_url)
        v = extract_views_jsonld(html)
        if v is not None: return v
        m = re.search(r'"viewsCount"\s*:\s*([0-9]{1,12})', html)
        if m: return int(m.group(1))
        m = re.search(r'"viewCount"\s*:\s*"([\d\s\u00A0,\.]+)"', html)
        if m: return parse_int(m.group(1))
        m = re.search(r'(?:Просмотров|просмотров)[^\d]{0,10}([\d\s\u00A0,\.]+)', html)
        if m: return parse_int(m.group(1))
    except Exception:
        pass
    return None

def fetch_views_rutube(url: str):
    try:
        html = http_get(url)
        return extract_views_jsonld(html) or extract_views_generic(html)
    except Exception:
        return None

def fetch_views_youtube(urls):
    ids, id_by_url = [], {}
    for u in urls:
        vid = yt_extract_id(u)
        if vid and vid not in id_by_url:
            id_by_url[u] = vid
            ids.append(vid)
    out = {u: None for u in urls}
    if not ids or not YOUTUBE_API_KEY:
        return out
    for i in range(0, len(ids), 50):
        batch = ids[i:i+50]
        r = requests.get(YOUTUBE_API_URL, params={
            "part": "statistics", "id": ",".join(batch), "key": YOUTUBE_API_KEY
        }, timeout=25)
        r.raise_for_status()
        data = r.json()
        stats = {it["id"]: it.get("statistics", {}).get("viewCount") for it in data.get("items", [])}
        for u, vid in id_by_url.items():
            if vid in batch:
                out[u] = stats.get(vid)
    return out

# --------- Dzen через Playwright (браузер)

def fetch_views_dzen(url: str):
    """
    Открываем страницу в Chromium (headless), ждём рендера,
    кликаем по видео при необходимости, ищем число в текстах и глобальном стейте.
    """
    from playwright.sync_api import sync_playwright

    def pick_number(texts):
        import re as _re
        for t in texts or []:
            m = _re.search(r'([\d\s\u00A0.,]+)', t)
            if m:
                v = parse_int(m.group(1))
                if v is not None:
                    return v
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            context = browser.new_context(
                user_agent=UA["User-Agent"],
                locale="ru-RU",
                viewport={"width": 1366, "height": 768},
            )
            page = context.new_page()
            page.set_default_timeout(20000)

            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(1200)

            # 1) сначала попробуем JSON-LD из уже отрисованного HTML
            html = page.content()
            v = extract_views_jsonld(html)
            if v is not None:
                browser.close()
                return v

            # 2) «пнуть» плеер — иногда после клика появляется оверлей со счетчиком
            try:
                page.click("video", timeout=2000)
                page.wait_for_timeout(800)
            except Exception:
                pass

            # 2a) собрать текстовые узлы, содержащие «просмотр»
            texts = page.evaluate("""
                () => {
                  const out = [];
                  const walker = document.createTreeWalker(
                    document.body, NodeFilter.SHOW_TEXT
                  );
                  let n;
                  while ((n = walker.nextNode())) {
                    const t = (n.textContent || "").trim();
                    if (!t) continue;
                    if (/[Пп]росмотр/.test(t) && /\\d/.test(t)) out.push(t);
                  }
                  return out.slice(0, 80);
                }
            """)
            v = pick_number(texts)
            if v is not None:
                browser.close()
                return v

            # 3) посмотреть глобальные объекты состояния (если есть)
            try:
                data_candidates = page.evaluate("""
                  () => {
                    const out = [];
                    try { if (window.__INITIAL_STATE__) out.push(window.__INITIAL_STATE__); } catch(e){}
                    try { if (window.__DATA__) out.push(window.__DATA__); } catch(e){}
                    try { if (window.__ZEN__) out.push(window.__ZEN__); } catch(e){}
                    return out;
                  }
                """)
                from collections import deque
                def from_obj(obj):
                    for k in ("views", "viewCount", "viewsCount", "watchCount"):
                        try:
                            pv = parse_int(obj.get(k))
                            if pv is not None: return pv
                        except Exception:
                            pass
                    for k1 in ("stats", "statistics", "meta", "counters", "analytics"):
                        try:
                            inner = obj.get(k1)
                            if isinstance(inner, dict):
                                for k2 in ("views", "viewCount", "viewsCount", "watchCount"):
                                    pv = parse_int(inner.get(k2))
                                    if pv is not None: return pv
                        except Exception:
                            pass
                    try:
                        vc = obj.get("viewCounter")
                        if isinstance(vc, dict):
                            pv = parse_int(vc.get("count"))
                            if pv is not None: return pv
                    except Exception:
                        pass
                    return None

                for root in data_candidates or []:
                    dq, seen = deque([root]), set()
                    while dq:
                        cur = dq.popleft()
                        if id(cur) in seen: 
                            continue
                        seen.add(id(cur))
                        if isinstance(cur, dict):
                            pv = from_obj(cur)
                            if pv is not None:
                                browser.close()
                                return pv
                            for v2 in cur.values():
                                if isinstance(v2, (dict, list)):
                                    dq.append(v2)
                        elif isinstance(cur, list):
                            for v2 in cur:
                                if isinstance(v2, (dict, list)):
                                    dq.append(v2)
            except Exception:
                pass

            # 4) резерв — общий поиск по HTML
            html = page.content()
            v = extract_views_generic(html)
            browser.close()
            return v
    except Exception:
        return None

# --------- Flask

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    error = None
    links = ""
    rows = None
    if request.method == "POST":
        try:
            links = request.form.get("links", "")
            urls = [normalize_url(u) for u in links.splitlines() if u.strip()]
            by_platform = {"youtube": [], "ok": [], "rutube": [], "dzen": [], "unknown": []}
            for u in urls:
                by_platform[detect_platform(u)].append(u)

            rows = []
            if by_platform["youtube"]:
                yt_map = fetch_views_youtube(by_platform["youtube"])
                for u in by_platform["youtube"]:
                    rows.append((u, "YouTube", yt_map.get(u, "") or ""))
            for u in by_platform["ok"]:
                rows.append((u, "OK.ru", fetch_views_ok(u) or ""))
            for u in by_platform["rutube"]:
                rows.append((u, "RuTube", fetch_views_rutube(u) or ""))
            for u in by_platform["dzen"]:
                rows.append((u, "Dzen", fetch_views_dzen(u) or ""))
            for u in by_platform["unknown"]:
                rows.append((u, "Unknown", ""))

        except Exception as e:
            error = str(e)

    return render_template("index.html", rows=rows, links=links, today=date.today(), error=error)

@app.route("/download", methods=["POST"])
def download():
    links = request.form.get("links", "")
    urls = [normalize_url(u) for u in links.splitlines() if u.strip()]
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["url", "platform", "views"])

    by_platform = {"youtube": [], "ok": [], "rutube": [], "dzen": [], "unknown": []}
    for u in urls:
        by_platform[detect_platform(u)].append(u)
    yt_map = fetch_views_youtube(by_platform["youtube"]) if by_platform["youtube"] else {}

    for u in urls:
        p = detect_platform(u)
        if p == "youtube":
            w.writerow([u, "YouTube", yt_map.get(u, "") or ""])
        elif p == "ok":
            w.writerow([u, "OK.ru", fetch_views_ok(u) or ""])
        elif p == "rutube":
            w.writerow([u, "RuTube", fetch_views_rutube(u) or ""])
        elif p == "dzen":
            w.writerow([u, "Dzen", fetch_views_dzen(u) or ""])
        else:
            w.writerow([u, "Unknown", ""])

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
