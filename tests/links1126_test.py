"""Ссылки в ответах (26.11, владелец): «Ссылка не нажимается в ответе Лиры в беседе и в виджете на компьютере. В виджете ещё
и она обрезается… на просьбу открыть в браузере — открыла, но не в браузере, а в программе z-code».
- студия: голая https-ссылка в ответе — ссылка (длинная — короче, целиком в подсказке), не разъезжается;
- виджет: то же в карточке ответа и в «целиком»; длинная строка переносится, а не обрезается;
- «Открой в браузере» сразу после ответа с одной ссылкой — открываем её (open_url), без модели: модель звала show_page,
  делала страницу-файл, а .html в Windows открылся редактором кода;
- свои страницы (show_page) — именно браузером по умолчанию (Windows: тот, кто открывает https)."""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


LONG = "https://console.example.com/billing/0123-ABCD-4567/payment?organizationId=0&walkthrough_id=billing_tour"

# ---------- студия ----------
js = r"""
const fs = require("fs"); const src = fs.readFileSync(process.argv[1], "utf8");
global.escH = s => String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
eval(src.split("/* Блоки:")[0]);
console.log(JSON.stringify([mdInline("Прямая ссылка: " + process.argv[2]), mdInline("см. https://ya.ru, и [тут](https://x.ru/a)"),
  mdInline("адрес https://a.ru/x_y_z и `https://b.ru` в коде")]));
"""
out = json.loads(subprocess.run(["node", "-e", js, str(ROOT / "ui/studio/folder.js"), LONG], capture_output=True, text=True, check=True).stdout)
a = re.search(r'<a href="([^"]+)" target="_blank" title="[^"]+">([^<]+)</a>', out[0])
ok(a and a.group(1).replace("&amp;", "&") == LONG, f"студия: голая ссылка — ссылка на полный адрес: {out[0][:160]}")
ok(a and a.group(2) == "console.example.com/billing/…/payment?…", f"длинная — короче: {a and a.group(2)}")
ok('<a href="https://ya.ru" target="_blank">https://ya.ru</a>,' in out[1] and '<a href="https://x.ru/a" target="_blank">тут</a>' in out[1],
   "запятая после ссылки — не часть адреса; [подпись](ссылка) — как было")
ok('href="https://a.ru/x_y_z"' in out[2] and "<em>" not in out[2] and out[2].count("<a ") == 1, "подчёркивания в адресе — не курсив; ссылка в `коде` — не ссылка")
css = (ROOT / "ui/studio/studio.css").read_text(encoding="utf-8")
ok(re.search(r"\.md a \{[^}]*overflow-wrap: anywhere", css), "длинная ссылка переносится")

# ---------- виджет ----------
hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
fn = lambda name: hud[hud.index(name):hud.index("\n}\n", hud.index(name)) + 3]
code = ("const $ = id => document.getElementById(id);\n" + hud[hud.index("const URL_RX"):hud.index("\n", hud.index("const URL_RX"))] + "\n"
        + fn("function shortUrl(u)") + fn("function linkify(el, text)") + fn("function capParas(t)") + fn("function capSet(text)")
        + hud[hud.index("const escR"):hud.index("\n", hud.index("const escR"))] + "\n" + fn("function mdLite(t)"))
from playwright.sync_api import sync_playwright  # noqa: E402
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 320, "height": 300})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.set_content('<style>#bot{width:260px;white-space:pre-wrap;overflow-x:hidden;overflow-wrap:anywhere;font:14px sans-serif}</style><div id="bot"></div>'
                   + f"<script>{code}</script>")
    pg.evaluate("t => capSet(t)", f"Нашла. А вот прямая ссылка на оплату: {LONG}\nХочешь, открою её в браузере?")
    links = pg.evaluate("[...document.querySelectorAll('#bot a')].map(a => [a.href, a.textContent, a.target])")
    ok(len(links) == 1 and links[0][0] == LONG and links[0][2] == "_blank", f"виджет: ссылка нажимается и ведёт на полный адрес: {links}")
    ok(links and len(links[0][1]) <= 56 and links[0][1].startswith("console.example.com/"), f"короткая подпись: {links and links[0][1]}")
    ok(pg.evaluate("document.querySelector('#bot').scrollWidth <= document.querySelector('#bot').clientWidth + 1"), "ничего не обрезается по ширине")
    ok("Хочешь, открою" in pg.inner_text("#bot"), "текст вокруг ссылки на месте")
    md = pg.evaluate("t => mdLite(t)", f"См. [страницу](https://x.ru/p) и {LONG}.")
    ok('<a href="https://x.ru/p" target="_blank" rel="noopener" title="https://x.ru/p">страницу</a>' in md and md.count("<a ") == 2,
       f"«целиком»: и [подпись](ссылка), и голая ссылка — ссылки: {md[:200]}")
    ok(re.search(r"#cap \.bot \{[^}]*overflow-wrap: anywhere", hud), "длинный текст в карточке переносится, а не режется")
    ok(not errs, f"без ошибок: {errs[:2]}")
    b.close()

# ---------- «Открой в браузере» — та самая ссылка, без модели ----------
sys.path.insert(0, str(ROOT / "core"))
dry = Path(tempfile.mkdtemp()) / "launch.jsonl"
os.environ["DEWIAR_DRY_TOOLS"] = str(dry)
import acts_quick  # noqa: E402


class E(acts_quick.QuickMixin):
    def __init__(self, last):
        self.history = [{"role": "user", "content": "найди ссылку на оплату"}, {"role": "assistant", "content": last}]
        self.said, self.ev = [], []

    def emit(self, *a, **k):
        self.ev.append((a, k))

    def _say_quick(self, msg, said, via=None, **k):
        self.said.append(msg)


e = E(f"Нашла в заметке. Прямая ссылка: {LONG}\nХочешь, открою её в браузере?")
ok(e._open_link_cmd("Открой в браузере") and e.said and "console.example.com" in e.said[0] and e.said[0].startswith("Открываю"), f"«Открой в браузере» — сразу, без модели: {e.said}")
cmds = [json.loads(x) for x in dry.read_text(encoding="utf-8").splitlines()]
ok(cmds and cmds[-1][-1] == LONG, f"открыт тот самый адрес: {cmds[-1:]}")
for phrase in ("да, открой", "открой её", "Открой ссылку, пожалуйста", "давай открывай"):
    ok(E(f"Вот: {LONG}")._open_link_cmd(phrase), f"«{phrase}» — тоже")
ok(not E("Ссылок нет, только текст.")._open_link_cmd("Открой в браузере"), "ссылок в ответе нет — к модели")
ok(not E("Две: https://a.ru и https://b.ru")._open_link_cmd("Открой в браузере"), "ссылок две — к модели (какую — решит она или спросит)")
ok(not E(f"Вот: {LONG}")._open_link_cmd("открой калькулятор"), "«открой калькулятор» — не про ссылку")
eng = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("self._open_link_cmd(text, via)" in eng, "команда стоит в цепочке быстрых ответов")

# ---------- свои страницы — браузером ----------
tn = (ROOT / "core/tools_notes.py").read_text(encoding="utf-8")
ok("base.launch_browser(f)" in tn, "show_page открывает страницу браузером, а не программой для .html")
ws = (ROOT / "core/winsys.py").read_text(encoding="utf-8")
ok("UrlAssociations\\https\\UserChoice" in ws and "def open_in_browser" in ws, "Windows: браузер по умолчанию — тот, кто открывает https")

print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
