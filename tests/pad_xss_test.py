"""Блокнот и заметки: Markdown не даёт выполнить код (третья рецензия выпуска 5, 05.11). В padmd.js голые ссылки
превращались в <a> регуляркой уже внутри собранной разметки: «![a https://x/…onerror=…](картинка)» выводил ссылку из
alt="…", и onerror исполнялся в окне блокнота (в адресе — ключ ядра: core.call без ограничений). Теперь готовые куски
уходят в заглушки, атрибуты — только из экранированного текста; заметки студии (ntRender) ищут голые ссылки по дереву,
а не по разметке. Проверяем в Chromium: строка рецензента и её варианты не дают ни одного on*-атрибута и ни одного
вызова; обычный Markdown по-прежнему даёт ссылки, картинки, код."""
import json
import shutil
import subprocess
import os
import re
import sys
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


EVIL = [
    "Заметка\n\n![a https://x/src='nope.png'onerror=location='javascript:core.call\\x28\\x22settings_save\\x22\\x29'//](https://invalid.invalid/i.png)",
    "![a https://x/onerror=window.PWN=1;throw'x'//](https://invalid.invalid/i.png)",
    "![x\" onerror=\"window.PWN=2](https://invalid.invalid/i.png)",
    "[a https://evil/\" onmouseover=\"window.PWN=3](https://x)",
    "[x](javascript:window.PWN=4)",
    "[x](https://a/(https://evil\"onfocus=window.PWN=5 autofocus x=\")",
    "- [ ] ![t https://e/ onerror=window.PWN=6//](https://invalid.invalid/i.png)",
    "| a | b |\n|---|---|\n| ![c https://e/ onerror=window.PWN=7//](https://invalid.invalid/i.png) | d |",
    "**https://x/\" onerror=\"window.PWN=8** `https://y/\"` ~~https://z/~~",
    "\u0001" + "0\u0001 ![a](https://x/i.png) \u00000\u0000",
    # четвёртая рецензия: заглушка в адресе ссылки и вложенность (картинка в ссылке, ссылка в картинке, код в ссылке)
    "[молоко](![ style=animation-name:aiSpin;animation-duration:1s onanimationstart=window.PWN=13 x](b))",
    "[x](![ autofocus tabindex=1 onfocus=window.PWN=14 x](b))",
    "![a](![ onerror=window.PWN=15 src=x ](b))",
    "[x](`\" onmouseover=window.PWN=16 x`)",
    "![a [b](![ onerror=window.PWN=17 ](c))](d)",
    "[[x](![ onfocus=window.PWN=18 autofocus ](e))](f)",
    "[a](https:\u00000\u0000)`\"onx=window.PWN=19`",
]
GOOD = "Привет [сайт](https://a.b/c?d=1&e=2) и https://x.y/z. Код `a<b>` и **жирный** ![кот](https://i.example/cat.png)"

from playwright.sync_api import sync_playwright  # noqa: E402
pad_js = (ROOT / "ui/assets/padmd.js").read_text(encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.set_content("<html><head><style>@keyframes aiSpin{from{opacity:1}to{opacity:.9}}</style></head><body><div id=ED contenteditable></div></body></html>")
    pg.add_script_tag(content=pad_js)
    res = pg.evaluate("""(cases) => cases.map(s => { const d = document.getElementById('ED'); d.innerHTML = PadMD.md2html(s);
        const bad = [...d.querySelectorAll('*')].flatMap(e => [...e.attributes].filter(a => /^on/i.test(a.name) || /^\\s*javascript:/i.test(a.value)).map(a => e.tagName + ' ' + a.name));
        return bad; })""", EVIL)
    pg.wait_for_timeout(800)
    ok(all(not r for r in res), f"блокнот: ни одного on*-атрибута и javascript: из Markdown ({[r for r in res if r][:3]})")
    ok(pg.evaluate("window.PWN") is None, "блокнот: ни один вариант не выполнил код")
    good = pg.evaluate("(s) => PadMD.md2html(s)", GOOD)
    ok('<a href="https://a.b/c?d=1&amp;e=2">сайт</a>' in good and '<a href="https://x.y/z">https://x.y/z</a>.' in good
       and "<code>a&lt;b&gt;</code>" in good and "<strong>жирный</strong>" in good
       and '<img alt="кот" data-src="https://i.example/cat.png">' in good, f"блокнот: обычный Markdown — как раньше: {good}")
    nest = pg.evaluate("""() => [PadMD.md2html('[![кот](https://i/c.png)](https://x)'), PadMD.md2html('[`код` и **ж**](https://y)')]""")
    ok(nest[0] == '<p><a href="https://x"><img alt="кот" data-src="https://i/c.png"></a></p>'
       and nest[1] == '<p><a href="https://y"><code>код</code> и <strong>ж</strong></a></p>', f"блокнот: картинка и код внутри ссылки — как раньше: {nest}")
    back = pg.evaluate("(s) => PadMD.html2md(PadMD.md2html(s))", GOOD)
    ok(back.strip() == GOOD.replace(" Код ", " Код ").strip(), f"блокнот: туда-обратно без потерь: {back.strip()}")
    b.close()

# заметки студии (ntRender): то же — голые ссылки по дереву
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"
                       "window.addEventListener('DOMContentLoaded', () => { if (window.core) { core.connect = () => {}; core.retry = () => {}; } });")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?token=t&port=1")
    pg.wait_for_timeout(1200)
    res = pg.evaluate("""(cases) => cases.map(s => { const d = document.createElement('div'); d.innerHTML = ntRender(s); document.body.appendChild(d);
        return [...d.querySelectorAll('*')].flatMap(e => [...e.attributes].filter(a => /^on/i.test(a.name) || /^\\s*javascript:/i.test(a.value)).map(a => e.tagName + ' ' + a.name)); })""", EVIL)
    pg.wait_for_timeout(800)
    ok(all(not r for r in res) and pg.evaluate("window.PWN") is None, f"заметки студии: ни on*-атрибутов, ни выполненного кода ({[r for r in res if r][:3]})")
    md_ = pg.evaluate("""() => [md('[a](https://x/`\\"onx=1`)'), md('[x **y](https://a**b)'), md('[[a\\" b|c]]')]""")
    ok(all('<code' not in m.split('href="')[1].split('"')[0] if 'href="' in m else True for m in md_) and "</b>" not in md_[1].split(">")[0]
       and 'href="wiki:a%22%20b"' in md_[2], f"«Папка»/заметки (md): в адресах ссылок — ни разметки, ни кавычек: {md_}")
    html = pg.evaluate("(s) => ntRender(s)", "Сайт https://a.b/c, и [ссылка](https://x.y/) и `https://code/`")
    ok('<a href="#" data-ext="https://a.b/c">https://a.b/c</a>,' in html and '<a href="#" data-ext="https://x.y/">ссылка</a>' in html
       and "<code>https://code/</code>" in html, f"заметки: голые и обычные ссылки — во внешний браузер, код — как есть: {html}")
    b.close()

# остальные отрисовщики Markdown: регулярки не собирают атрибутов из текста
src = {f: (ROOT / f).read_text(encoding="utf-8") for f in ("ui/prompter.html", "ui/hud.html", "ui/studio/folder.js", "ui/studio/notes.js")}
ok("NT_URL" in src["ui/studio/notes.js"] and ".replace(/(^|[\\s>(«])(https?" not in src["ui/studio/notes.js"],
   "заметки: голые ссылки — не регуляркой по готовой разметке")
# рецензия 5e: строка «```js {1,3}» (и «> ```[») — блок кода не открывает, абзац её не брал: цикл без конца, память до отказа
if shutil.which("node"):
    hang = subprocess.run(["node", "--max-old-space-size=200", "-e", "global.window = {}; require(%s); "
                           "for (const s of ['Заметка\\n\\n```js {1,3}\\nconst a = 1;\\n```\\n', '> ```[ x', '```[']) window.PadMD.md2html(s); "
                           "console.log('ok')" % json.dumps(str(ROOT / "ui/assets/padmd.js"))], capture_output=True, text=True, timeout=30)
    ok(hang.stdout.strip() == "ok", f"блокнот: «```js {{1,3}}» не вешает отрисовку ({hang.stderr.strip()[-120:]})")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
