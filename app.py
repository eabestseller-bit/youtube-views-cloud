#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Social Views Checker
Поддержка: YouTube + OK.ru + RuTube + Dzen + VK (vk.com/vkvideo.ru) + Telegram

- YouTube: API (env YOUTUBE_API_KEY)
- OK/RuTube: HTML/JSON-LD
- Dzen: Playwright (Chromium)
- VK: HTML + мобильная m.vk.com, расширенные паттерны
- Telegram: HTML (виджет)

Флаги окружения:
- YOUTUBE_API_KEY=...  — ключ для YouTube Data API v3
- DISABLE_DZEN=1       — пропустить Dzen (ускоряет тест на слабых инстансах)
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
YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/videos"
DISABLE_DZEN = os.getenv("DISABLE_DZEN", "0") == "1"

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
    """Обрезаем query/fragment (?share_to=...) — мешают парсингу/кешам."""
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
    if "vk.com" in u or "vkvideo.ru" in u or "vkontakte" in u: return "vk"
    if "t.me" in u or "telegram.me" in u: return "telegram"
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
    log.info(f"[GET] {r.status_code} {url} (len={len(r.text) if r.text else 0})")
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
    """Ищем interactionStatistic→WatchAction→userInteractionCount в JSON-LD (если сайт отдал)."""
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
    """Общие эвристики по разметке."""
    for pattern in [
        r'"viewCount"\s*:\s*"?([\d\s,\.]+)"?',
        r'"views"\s*:\s*"?([\d\s,\.]+)"?',
        r'(?:Просмотров|просмотров|ПРОСМОТРОВ)[^\d]{0,10}([\d\s\u00A0,\.]+)',
    ]:
        m = re.search(pattern, html)
        if m:
            return parse_int(m.group(1))
    return None

# ---------- площадки ----------

def fetch_views_ok(url: str):
    log.info(f"[OK] start: {url}")
    try:
        html = http_get(url)
        v = extract_views_jsonld(html) or extract_views_generic(html)
        if v is not None:
            log.info(f"[OK] found: {v}")
            return v
    except Exception as e:
        log.info(f"[OK] error: {e}")
    try:
        m_url = url if "://m.ok.ru/" in url else url.replace("://ok.ru/", "://m.ok.ru/")
        html = http_get(m_url)
        v = extract_views_jsonld(html)
        if v is not None:
            log.info(f"[OK] found (m): {v}")
            return v
        m = re.search(r'"viewsCount"\s*:\s*([0-9]{1,12})', html)
        if m: return int(m.group(1))
        m = re.search(r'"viewCount"\s*:\s*"([\d\s\u00A0,\.]+)"', html)
        if m: return parse_int(m.group(1))
        m = re.search(r'(?:Просмотров|просмотров)[^\d]{0,10}([\d\s\u00A0,\.]+)', html)
        if m: return parse_int(m.group(1))
    except Exception as e:
        log.info(f"[OK] error (m): {e}")
    log.info("[OK] not found")
    return None

def fetch_views_rutube(url: str):
    log.info(f"[RT] start: {url}")
    try:
        html = http_get(url)
        v = extract_views_jsonld(html) or extract_views_generic(html)
        log.info(f"[RT] result: {v}")
        return v
    except Exception as e:
        log.info(f"[RT] error: {e}")
        return None

def fetch_views_youtube(urls):
    out = {u: None for u in urls}
    if not urls or not YOUTUBE_API_KEY:
        return out
    ids, id_by_url = [], {}
    for u in urls:
        vid = yt_extract_id(u)
        if vid and vid not in id_by_url:
            id_by_url[u] = vid
            ids.append(vid)
    for i in range(0, len(ids), 50):
        batch = ids[i:i+50]
        r = requests.get(YOUTUBE_API_URL, params={
            "part": "statistics", "id": ",".join(batch), "key": YOUTUBE_API_KEY
        }, timeout=25)
        log.info(f"[YT] API {r.status_code} ids={len(batch)}")
        r.raise_for_status()
        data = r.json()
        stats = {it["id"]: it.get("statistics", {}).get("viewCount") for it in data.get("items", [])}
        for u, vid in id_by_url.items():
            if vid in batch:
                out[u] = stats.get(vid)
    return out

# ---- VK (vk.com / vkvideo.ru)
def fetch_views_vk(url: str):
    """
    VK / VK Video:
    - Пытаемся по самому URL
    - Если это vkvideo.ru, строим эквиваленты на vk.com и m.vk.com
    - Куча шаблонов: JSON, data-атрибуты, aria-label, текст, K/M
    """
    log.info(f"[VK] start: {url}")

    def parse_km(num_str: str):
        m = re.search(r'^\s*([\d\s\u00A0,\.]+)\s*([KkMm])\s*$', num_str)
        if m:
            base = parse_int(m.group(1))
            if base is None: return None
            mult = 1_000 if m.group(2).lower() == 'k' else 1_000_000
            return base * mult
        return parse_int(num_str)

    def try_parse(html: str):
        # JSON-LD
        v = extract_views_jsonld(html)
        if v is not None:
            return v
        # JSON-поля
        m = re.search(r'"views"\s*:\s*\{\s*"count"\s*:\s*([0-9]{1,12})\s*\}', html)
        if m: return int(m.group(1))
        m = re.search(r'"views_count"\s*:\s*([0-9]{1,12})', html)
        if m: return int(m.group(1))
        m = re.search(r'"count_views"\s*:\s*([0-9]{1,12})', html)
        if m: return int(m.group(1))
        m = re.search(r'"viewCount"\s*:\s*"([^"]+)"', html)
        if m:
            v = parse_km(m.group(1))
            if v is not None: return v
        m = re.search(r'"views"\s*:\s*"([^"]+)"', html)
        if m:
            v = parse_km(m.group(1))
            if v is not None: return v
        # mvData / mv_data
        m = re.search(r'"mvData"\s*:\s*\{[^}]*?"views"\s*:\s*([0-9]{1,12})', html, re.DOTALL)
        if m: return int(m.group(1))
        m = re.search(r'"mv_data"\s*:\s*\{[^}]*?"views"\s*:\s*([0-9]{1,12})', html, re.DOTALL)
        if m: return int(m.group(1))
        # Атрибуты/верстка
        m = re.search(r'aria-label="([^"]+?)"', html, re.IGNORECASE)
        if m and ("просмотр" in m.group(1).lower() or "views" in m.group(1).lower()):
            v = parse_km(m.group(1))
            if v is None:
                m2 = re.search(r'([\d\s\u00A0,\.]+[KkMm]?)', m.group(1))
                if m2:
                    v = parse_km(m2.group(1))
            if v is not None:
                return v
        m = re.search(r'data-views\s*=\s*"([0-9]{1,12})"', html)
        if m: return int(m.group(1))
        m = re.search(r'class="[^"]*mv[_-]?views[^"]*"\s*[^>]*>\s*([\d\s\u00A0,\.KkMm]+)\s*<', html)
        if m:
            v = parse_km(m.group(1))
            if v is not None: return v
        # Текстовые варианты
        m = re.search(r'(?:Просмотров|просмотров|Views|views)[^\dKkMm]{0,12}([\d\s\u00A0,\.KkMm]+)', html)
        if m:
            v = parse_km(m.group(1))
            if v is not None: return v
        return None

    # 1) сам URL
    try:
        html = http_get(url)
        v = try_parse(html)
        if v is not None:
            log.info(f"[VK] found: {v}")
            return v
    except Exception as e:
        log.info(f"[VK] error: {e}")

    # 2) альтернативы
    alt_urls = []
    try:
        low = url.lower()
        if "vkvideo.ru" in low:
            m = re.search(r'/video([-\d_]+)', url)
            if m:
                tail = m.group(1)  # -48064554_456242034
                alt_urls.append(f"https://vk.com/video{tail}")
                alt_urls.append(f"https://m.vk.com/video{tail}")
    except Exception:
        pass
    if "vk.com" in url and "m.vk.com" not in url:
        alt_urls.append(url.replace("://vk.com/", "://m.vk.com/"))

    for u2 in alt_urls:
        log.info(f"[VK] alt: {u2}")
        try:
            html = http_get(u2)
            v = try_parse(html)
            if v is not None:
                log.info(f"[VK] found alt: {v}")
                return v
        except Exception as e:
            log.info(f"[VK] alt error: {e}")

    log.info("[VK] not found")
    return None

# ---- Telegram (t.me)
def fetch_views_telegram(url: str):
    """
    Telegram: .tgme_widget_message_views / _meta / _info; поддержка K/M; пробуем зеркало /s/.
    """
    log.info(f"[TG] start: {url}")

    def parse_page(html: str):
        soup = BeautifulSoup(html, "html.parser")
        el = soup.select_one(".tgme_widget_message_views")
        if el:
            v = parse_int(el.get_text(strip=True))
            if v is not None: return v
        meta = soup.select_one(".tgme_widget_message_meta") or soup.select_one(".tgme_widget_message_info")
        if meta:
            txt = meta.get_text(" ", strip=True)
            m = re.search(r'([\d\s\u00A0,\.]+[KkMm]?)', txt)
            if m:
                num = m.group(1)
                if re.search(r'[Kk]$', num):
                    base = parse_int(num[:-1]);  return base * 1_000 if base is not None else None
                if re.search(r'[Mm]$', num):
                    base = parse_int(num[:-1]);  return base * 1_000_000 if base is not None else None
                v = parse_int(num)
                if v is not None: return v
        v = extract_views_generic(html)
        if v is not None: return v
        return None

    # оригинал
    try:
        html = http_get(url)
        v = parse_page(html)
        if v is not None:
            log.info(f"[TG] found: {v}")
            return v
    except Exception as e:
        log.info(f"[TG] error: {e}")

    # зеркало /s/
    try:
        sp = urlsplit(url)
        parts = sp.path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] != "s":
            mirror = urlunsplit((sp.scheme or "https", sp.netloc, "/s/" + "/".join(parts), "", ""))
            log.info(f"[TG] mirror: {mirror}")
            html = http_get(mirror)
            v = parse_page(html)
            if v is not None:
                log.info(f"[TG] found mirror: {v}")
                return v
    except Exception as e:
        log.info(f"[TG] mirror error: {e}")

    log.info("[TG] not found")
    return None

# --------- Dzen (Playwright), можно отключить флагом DISABLE_DZEN=1 ----------
def fetch_views_dzen(url: str):
    if DISABLE_DZEN:
        log.info("[DZEN] disabled by env")
        return None

    log.info(f"[DZEN] start: {url}")
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    def pick_number_from_texts(texts):
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
            page.set_default_timeout(25000)

            for _ in range(3):
                page.goto(url, wait_until="domcontentloaded")
                try:
                    page.wait_for_load_state("networkidle", timeout=7000)
                except PWTimeout:
                    pass

                html = page.content()
                v = extract_views_jsonld(html)
                if v is not None:
                    browser.close()
                    log.info(f"[DZEN] found: {v}")
                    return v

                texts = page.evaluate("""
                    () => {
                      const out = [];
                      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                      let n;
                      while ((n = walker.nextNode())) {
                        const t = (n.textContent || "").trim();
                        if (!t) continue;
                        if (/[Пп]росмотр/.test(t) && /\\d/.test(t)) out.push(t);
                      }
                      return out.slice(0, 120);
                    }
                """)
                v = pick_number_from_texts(texts)
                if v is not None:
                    browser.close()
                    log.info(f"[DZEN] found text: {v}")
                    return v

                # резерв — общий HTML
                v = extract_views_generic(html)
                if v is not None:
                    browser.close()
                    log.info(f"[DZEN] found generic: {v}")
                    return v

                try:
                    page.click("video", timeout=1500)
                except Exception:
                    pass
                page.wait_for_timeout(800)

            browser.close()
            log.info("[DZEN] not found")
            return None
    except Exception as e:
        log.info(f"[DZEN] error: {e}")
        return None

# ---------- Flask ----------

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    error = None
    links = ""
    rows = None
    if request.method == "POST":
        log.info("[POST] / – получен запрос на проверку ссылок")
        try:
            links = request.form.get("links", "")
            urls = [normalize_url(u) for u in links.splitlines() if u.strip()]
            by_platform = {
                "youtube": [], "ok": [], "rutube": [],
                "dzen": [], "vk": [], "telegram": [], "unknown": []
            }
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
                val = "" if DISABLE_DZEN else (fetch_views_dzen(u) or "")
                rows.append((u, "Dzen", val))
            for u in by_platform["vk"]:
                rows.append((u, "VK", fetch_views_vk(u) or ""))
            for u in by_platform["telegram"]:
                rows.append((u, "Telegram", fetch_views_telegram(u) or ""))
            for u in by_platform["unknown"]:
                rows.append((u, "Unknown", ""))

        except Exception as e:
            error = str(e)
            log.info(f"[POST] error: {e}")

    return render_template("index.html", rows=rows, links=links, today=date.today(), error=error, dzen_disabled=DISABLE_DZEN)

@app.route("/download", methods=["POST"])
def download():
    links = request.form.get("links", "")
    urls = [normalize_url(u) for u in links.splitlines() if u.strip()]
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["url", "platform", "views"])

    by_platform = {
        "youtube": [], "ok": [], "rutube": [],
        "dzen": [], "vk": [], "telegram": [], "unknown": []
    }
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
            val = "" if DISABLE_DZEN else (fetch_views_dzen(u) or "")
            w.writerow([u, "Dzen", val])
        elif p == "vk":
            w.writerow([u, "VK", fetch_views_vk(u) or ""])
        elif p == "telegram":
            w.writerow([u, "Telegram", fetch_views_telegram(u) or ""])
        else:
            w.writerow([u, "Unknown", ""])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"social_views_{date.today()}.csv"
    )

# Отдельный debug-эндпоинт для быстрой проверки VK
@app.route("/debug/vk")
def debug_vk():
    u = request.args.get("u", "")
    if not u:
        return "pass ?u=<vk-url>", 400
    log.info(f"[DEBUG] /debug/vk u={u}")
    val = fetch_views_vk(u)
    return {"url": u, "views": val}, 200

@app.route("/healthz")
def healthz():
    return "ok", 200
