"""Пакет 17.11 (владелец): «в редакторе переношу каждую строку на новую, нажимаю замочек — проходит время, и оно опять
слипается в единую кашу». Блок был таблицей из одной ячейки: при сохранении переводы строк в ячейке становились
пробелами (Markdown-таблица — одна строка на ряд), и при следующем открытии вкладки строки склеивались. Теперь перевод
в ячейке хранится как «<br>» (как в GitHub и Obsidian) и читается обратно — в блокноте, в студии и на телефоне."""
import os, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


MD = "| План: 1.0.15 — llm.py 1.0.16 — sync.py 1.0.17 — cloud.php |\n| --- |\n| итог |\n"
CARET = """() => { const th = document.querySelector('th'), t = th.lastChild, i = t.nodeValue.indexOf(arguments[0]);
  const r = document.createRange(); r.setStart(t, i); r.collapse(true); const s = getSelection(); s.removeAllRanges(); s.addRange(r); }"""
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.set_content(f'<div id="ed" contenteditable="true"></div><script>{(ROOT / "ui/assets/padmd.js").read_text(encoding="utf-8")}</script>')
    pg.evaluate("md => { document.getElementById('ed').innerHTML = PadMD.md2html(md); }", MD)
    pg.click("th")
    for key, at in (("Enter", "1.0.16"), ("Shift+Enter", "1.0.17")):
        pg.evaluate("""at => { const th = document.querySelector('th'), t = th.lastChild, i = t.nodeValue.indexOf(at);
          const r = document.createRange(); r.setStart(t, i); r.collapse(true); const s = getSelection(); s.removeAllRanges(); s.addRange(r); }""", at)
        pg.keyboard.press(key)
    md = pg.evaluate("PadMD.html2md(document.getElementById('ed'))")
    ok(md.splitlines()[0] == "| План: 1.0.15 — llm.py <br>1.0.16 — sync.py <br>1.0.17 — cloud.php |", f"сохранение: переводы в ячейке — <br>: {md.splitlines()[0]!r}")
    back = pg.evaluate("md => { const d = document.createElement('div'); d.innerHTML = PadMD.md2html(md); return [d.querySelector('th').innerHTML, PadMD.html2md(d)]; }", md)
    ok(back[0].count("<br>") == 2 and "&lt;br" not in back[0], f"открытие: в ячейке снова три строки: {back[0]!r}")
    ok(back[1] == md, "туда-обратно без изменений (замок, синхронизация и новое открытие ничего не склеят)")
    pasted = pg.evaluate("""() => PadMD.html2md('<table><tr><td><p>первая</p><p>вторая</p></td><td>x</td></tr><tr><td>a</td><td>b</td></tr></table>')""")
    ok(pasted.startswith("| первая<br>вторая | x |"), f"вставка с сайта: абзацы в ячейке — строками, не слитно: {pasted.splitlines()[0]!r}")
    ok(pg.evaluate("PadMD.md2html('| <b>x</b><br><img src=x onerror=alert(1)> |\\n| --- |\\n')").count("<img") == 0,
       "в ячейке понимается только <br>, прочая разметка — текстом")
    b.close()
for rel, mark in (("ui/studio/folder.js", "c.split(/<br\\s*\\/?>/i).map(mdInline)"), ("android/www-src/app/11-notes.js", ".split(/<br\\s*\\/?>/i).map(inl)"),
                  ("android/assets/www/app.js", ".split(/<br\\s*\\/?>/i).map(inl)")):
    ok(mark in (ROOT / rel).read_text(encoding="utf-8"), f"{rel}: перевод строки в ячейке показывается так же")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
