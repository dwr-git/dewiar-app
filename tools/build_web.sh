#!/bin/bash
# Веб-версия Dewiar (19.10: «у меня iPhone», «MacBook», «не хочу ставить программу») — тот же интерфейс телефона
# (android/assets/www + общие файлы, android/tools/www_assemble.sh), но вместо Bridge.java — android/web/webbridge.js
# (слух, голос, напоминания, радио средствами браузера). Ставится на сайт в dwrapp/web/ (tools/build_server_zip.sh
# кладёт её в архив сервера): вход, облако и голоса — тот же адрес, без CORS. Можно «На экран Домой» (manifest.json, sw.js).
#   bash tools/build_web.sh <папка>   → <папка>/web/
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$(mkdir -p "${1:?папка}" && cd "$1" && pwd)/web"
VER=$(sed -n 's/.*static final String VERSION = "\([0-9.]*\)".*/\1/p' "$ROOT/android/src/pro/dewiar/app/BuildInfo.java")
PC=$(sed -n 's/^VERSION = "\(.*\)"/\1/p' "$ROOT/core/version.py")
rm -rf "$OUT"; mkdir -p "$OUT"
bash "$ROOT/android/tools/www_assemble.sh" "$OUT"
cp "$ROOT/android/web/webbridge.js" "$OUT/"
python3 - "$OUT" "$ROOT" "$VER" "$PC" <<'PY'
import json, re, sys, hashlib
from pathlib import Path
from PIL import Image
out, root, ver, pc = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
web = f"{ver}-web"
(out / "webver.js").write_text(f'window.DEWIAR_WEB_VERSION = "{web}";\n', encoding="utf-8")
# значки: «На экран Домой» (iPhone — apple-touch-icon 180, Android и компьютер — 192 и 512)
src = Image.open(root / "android/web/icon.png").convert("RGBA")          # значок Dewiar — тот же, что на сайте
for n in (180, 192, 512):
    bg = Image.new("RGBA", (n, n), (10, 10, 15, 255))
    ic = src.resize((int(n * .84), int(n * .84)), Image.LANCZOS)
    bg.alpha_composite(ic, ((n - ic.width) // 2, (n - ic.height) // 2))
    bg.convert("RGB").save(out / f"icon-{n}.png", optimize=True)
(out / "manifest.json").write_text(json.dumps({
    "name": "Dewiar", "short_name": "Dewiar", "lang": "ru", "dir": "ltr",
    "description": "Голосовой ассистент с персонажами — в браузере, без установки",
    "start_url": "./index.html", "scope": "./", "display": "standalone", "orientation": "portrait",
    "background_color": "#0a0a0f", "theme_color": "#0a0a0f",
    "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
              {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}]}, ensure_ascii=False, indent=1), encoding="utf-8")
# Не запустилась или ошибка (жалоба 28.10: «веб-версия не работает совсем, не отвечает»): человеку — понятные слова,
# сайту — короткий отчёт (браузер и текст ошибки, без переписки) → кабинет → «Здоровье» → «Веб-версия». Только ES5:
# этот кусок должен работать и там, где сам app.js не разберётся.
BOOT = r"""<script>(function () {
  var sent = 0, ver = "{web}", errs = window.__dwrErrs = [];
  function send(kind, msg) {
    if (sent >= 3) return; sent++;
    try { var b = JSON.stringify({ kind: kind, msg: String(msg).slice(0, 500), ver: ver }), u = "../cloud.php?p=/webfail";
      if (navigator.sendBeacon) navigator.sendBeacon(u, new Blob([b], { type: "text/plain" })); else { var x = new XMLHttpRequest(); x.open("POST", u); x.send(b); } } catch (e) { }
  }
  window.addEventListener("error", function (e) {
    var m = String(e.message || "ошибка"); if (/^Script error|ResizeObserver/.test(m)) return;
    m += " @" + String(e.filename || "").split("/").pop().split("?")[0] + ":" + (e.lineno || 0);
    errs.push(m);
    if (!window.DEWIAR_STARTED && errs.length > 1) return;   // до запуска — только первая: остальные из-за неё («$ is not defined» в work.js)
    send(window.DEWIAR_STARTED ? "error" : "start", m);
  });
  window.addEventListener("load", function () { setTimeout(function () {
    if (window.DEWIAR_STARTED) return;
    if (!errs.length) send("start", "не запустилась, без ошибки");
    var d = document.createElement("div"); d.id = "dwr-boot";
    d.setAttribute("style", "position:fixed;left:16px;right:16px;bottom:24px;z-index:99;padding:16px 18px;border-radius:16px;background:#1d1b2e;color:#fff;font:15px/1.45 -apple-system,system-ui,sans-serif;box-shadow:0 12px 30px rgba(0,0,0,.4)");
    d.innerHTML = "<b>Dewiar не запустился в этом браузере.</b><br>Обновите iOS или Safari до свежей версии — или откройте страницу в Chrome. Отчёт об ошибке уже ушёл нам.";
    document.body.appendChild(d);
  }, 5000); });
})();</script>
"""
# страница: мост браузера — до app.js; версия у файлов — чтобы после обновления сайта браузер не взял старые из кэша
html = (out / "index.html").read_text(encoding="utf-8")
html = re.sub(r'(<(?:script src|link rel="stylesheet" href)=")([^"?]+\.(?:js|css))(")', lambda m: f'{m.group(1)}{m.group(2)}?v={web}{m.group(3)}', html)
html = html.replace(f'<script src="app.js?v={web}"></script>', f'<script src="webver.js?v={web}"></script>\n<script src="webbridge.js?v={web}"></script>\n<script src="app.js?v={web}"></script>')
assert "webbridge.js" in html, "не нашёл app.js в index.html"
head = ('<meta name="theme-color" content="#0a0a0f">\n<meta name="apple-mobile-web-app-capable" content="yes">\n'
        '<meta name="mobile-web-app-capable" content="yes">\n<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">\n'
        '<meta name="apple-mobile-web-app-title" content="Dewiar">\n<meta name="description" content="Dewiar — голосовой ассистент с персонажами, в браузере без установки">\n'
        '<link rel="manifest" href="manifest.json">\n<link rel="icon" href="icon-192.png">\n<link rel="apple-touch-icon" href="icon-180.png">\n'
        '<script>if ("serviceWorker" in navigator && location.protocol === "https:") addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));</script>\n' + BOOT.replace("{web}", web))
html = html.replace("</head>", head + "</head>", 1)
html = html.replace('<html lang="ru">', '<html lang="ru" class="web">', 1)
(out / "index.html").write_text(html, encoding="utf-8")
# сайт с PHP, где папка открывается через index.php, а не index.html, — тоже откроет страницу
(out / "index.php").write_text("<?php\n// Веб-версия Dewiar: та же страница, что index.html (на сайтах, где папку открывает index.php)\n"
                               "header('Content-Type: text/html; charset=utf-8');\nheader('Cache-Control: no-cache');\nreadfile(__DIR__ . '/index.html');\n", encoding="utf-8")
# офлайн-оболочка: страница и её файлы — в кэше (без mermaid и обликов — они догружаются по ходу)
files = sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file() and p.name not in ("sw.js", "index.php")
               and not str(p.relative_to(out)).startswith(("vendor/", "skins/", "live/")) and p.suffix in (".html", ".js", ".css", ".png", ".json", ".webp", ".svg"))
shell = ["./"] + [f + (f"?v={web}" if f.endswith((".js", ".css")) and "/" not in f else "") for f in files]
key = hashlib.sha1(("\n".join(shell) + web).encode()).hexdigest()[:10]
(out / "sw.js").write_text(f"""/* Dewiar в браузере: оболочка работает и без связи (страница, стили, код); разговор и облако — только по сети.
   Перехватываем только свои файлы (папка web/) — cloud.php, вход и голоса идут мимо кэша. Новый выпуск — новый кэш. */
const CACHE = "dewiar-web-{key}", SHELL = {json.dumps(shell, ensure_ascii=False)};
self.addEventListener("install", e => {{ e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); }});
self.addEventListener("activate", e => {{ e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith("dewiar-web-") && k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); }});
self.addEventListener("fetch", e => {{
  const r = e.request, u = new URL(r.url);
  if (r.method !== "GET" || u.origin !== location.origin || !u.pathname.startsWith(new URL("./", self.registration.scope).pathname)
      || u.searchParams.has("fresh")) return;   // проверка свежей версии (webbridge.js) — всегда с сайта
  if (r.mode === "navigate") {{   // страница — сначала свежая с сайта, без связи — из кэша
    e.respondWith(fetch(r).then(x => {{ const c = x.clone(); caches.open(CACHE).then(k => k.put("./", c)); return x; }}).catch(() => caches.match("./")));
    return;
  }}
  e.respondWith(caches.match(r).then(hit => hit || fetch(r).then(x => {{ if (x.ok && x.type === "basic") {{ const c = x.clone(); caches.open(CACHE).then(k => k.put(r, c)); }} return x; }})));
}});
""", encoding="utf-8")
print(f"веб-версия {web}: {len(files)} файлов в оболочке")
PY
echo "$OUT"
