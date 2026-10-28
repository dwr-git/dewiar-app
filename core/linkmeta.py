"""Ссылка в заметке — карточкой (0.58, «Заметки как Keep»): название, картинка и сайт. YouTube — через oEmbed (название,
обложка, канал), остальное — первые 400 КБ страницы: og:title / og:image / og:description или <title>. Кэш —
STATE_DIR/links.json (500 последних, неудача — на сутки). Стоп-кран «Ничего не уходит в интернет» — только адрес."""

import html
import json
import logging
import re
import threading
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

log = logging.getLogger("dewiar.links")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Accept-Language": "ru,en;q=0.8"}
YT_RX = re.compile(r"(?:youtube\.com/(?:watch\?v=|shorts/|live/|embed/)|youtu\.be/)([\w-]{6,})")


def _meta(page, prop):
    for rx in (rf'<meta[^>]+(?:property|name)=["\']{prop}["\'][^>]+content=["\']([^"\']+)', rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{prop}["\']'):
        m = re.search(rx, page, re.I)
        if m:
            return html.unescape(m.group(1)).strip()
    return ""


class LinkMeta:
    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()
        try:
            self.cache = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.cache = {}

    def _save(self):
        try:
            with self._lock:
                items = sorted(self.cache.items(), key=lambda kv: kv[1].get("at", 0))[-500:]
                self.cache = dict(items)
                self.path.write_text(json.dumps(self.cache, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def get(self, url):
        """-> {url, site, title, image, desc, video}; без сети или страница не ответила — только site."""
        url = str(url or "").strip()
        u = urlparse(url)
        if u.scheme not in ("http", "https") or not u.netloc:
            raise ValueError("это не ссылка")
        site = u.netloc.lower().removeprefix("www.").removeprefix("m.")
        c = self.cache.get(url)
        if c and (c.get("title") or time.time() - c.get("at", 0) < 86400):
            return c
        out = {"url": url, "site": site, "title": "", "image": "", "desc": "", "video": False, "at": int(time.time())}
        try:
            import egress
            if egress.local_only():
                return out
        except Exception:  # noqa: BLE001
            pass
        import httpx
        try:
            yt = YT_RX.search(url)
            if yt:
                r = httpx.get("https://www.youtube.com/oembed", params={"url": url, "format": "json"}, headers=UA, timeout=8)
                if r.status_code == 200:
                    j = r.json()
                    out.update(title=j.get("title", ""), image=f"https://i.ytimg.com/vi/{yt.group(1)}/hqdefault.jpg",
                               desc=j.get("author_name", ""), video=True, site="YouTube")
            if not out["title"]:
                with httpx.stream("GET", url, headers=UA, timeout=8, follow_redirects=True) as r:
                    if "html" in r.headers.get("content-type", ""):
                        buf = b""
                        for chunk in r.iter_bytes():
                            buf += chunk
                            if len(buf) > 400_000:
                                break
                        page = buf.decode(r.encoding or "utf-8", errors="replace")
                        t = _meta(page, "og:title") or _meta(page, "twitter:title")
                        if not t:
                            m = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
                            t = html.unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else ""
                        img = _meta(page, "og:image") or _meta(page, "twitter:image")
                        out.update(title=t[:200], image=urljoin(str(r.url), img) if img else "",
                                   desc=(_meta(page, "og:description") or _meta(page, "description"))[:300],
                                   video=_meta(page, "og:type").startswith("video"))
        except Exception as e:  # noqa: BLE001
            log.debug("ссылка %s: %s", site, e)
        with self._lock:
            self.cache[url] = out
        self._save()
        return out
