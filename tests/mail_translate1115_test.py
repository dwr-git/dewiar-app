"""Перевод письма на «Главной» (владелец 15.11: «когда открываю письмо на главной, иногда хочется перевести на русский»).
Письмо не на языке программы — в полосе над ним «Перевести на русский» (в английской программе — «Translate to
English» для писем не на английском); перевод — Лирой тем же мозгом (pad_ai, act translate), по мере перевода;
«Показать оригинал» — обратно; другое письмо — перевод прежнего не тянется. Письмо на языке программы — кнопки нет."""
import json, os, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


EN = {"uid": "1", "from": "vidIQ <hello@send.vidiq.com>", "subject": "You're on a roll", "date": "Sun, 15 Nov 2026 04:14:00 +0300",
      "text": "Keep the momentum going with 6,000 AI credits a month and 40% off your first month of MAX. "
              "Your latest request in your AI chat left you with only 2 free AI credits.", "plain": True, "html": "", "files": []}
RU = {"uid": "2", "from": "Сергей <s@example.ru>", "subject": "Встреча", "date": "Sun, 15 Nov 2026 10:00:00 +0300",
      "text": "Здравствуйте! Подтверждаю встречу в четверг в 15:00, адрес тот же. Возьмите, пожалуйста, договор.", "plain": True,
      "html": "<p>Здравствуйте!</p>", "files": []}
MAIL = [{k: x[k] for k in ("uid", "from", "subject", "date")} | {"snippet": x["text"][:40], "unread": False, "files": []} for x in (EN, RU)]
CORE = r"""(() => { window.calls = []; const MAIL = __MAIL__, READ = __READ__;
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "mail_inbox") return { on: true, items: MAIL };
      if (c === "mail_read") return READ[a.uid];
      if (c === "pad_ai") return { id: "ai" + calls.length };
      return null; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();""".replace("__MAIL__", json.dumps(MAIL, ensure_ascii=False)).replace("__READ__", json.dumps({"1": EN, "2": RU}, ensure_ascii=False))
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1300, "height": 900})
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1&skin=neusky")
    pg.wait_for_timeout(1500)
    pg.evaluate("() => { const w = document.querySelector('#wlc'); if (w) w.remove(); loadHome(); }")
    pg.wait_for_timeout(600)
    pg.click("#hm-mail .hmm-row >> nth=0")
    pg.wait_for_timeout(500)
    ok(pg.is_visible("#hmm-tr") and "Перевести на русский" in pg.inner_text("#hmm-tr") and pg.is_hidden("#hmm-bar .hmm-seg"),
       "письмо по-английски (только текст) — «Перевести на русский», переключателя вида нет")
    pg.click("#hmm-tr")
    pg.wait_for_timeout(200)
    c = [x for x in pg.evaluate("calls") if x[0] == "pad_ai"]
    ok(c and c[0][1]["act"] == "translate" and c[0][1]["lang"] == "ru" and "6,000 AI credits" in c[0][1]["text"], f"перевод — Лирой (pad_ai translate → ru): {c[:1]}")
    rid = pg.evaluate("HMM.tr.id")
    pg.evaluate("(id) => core.emit('pad_ai', { id, text: 'Не сбавляйте темп', done: false })", rid)
    pg.wait_for_timeout(150)
    ok("Лира переводит" in pg.inner_text("#hmm-body") and "Не сбавляйте темп" in pg.inner_text("#hmm-body"), "перевод появляется по мере перевода")
    pg.evaluate("(id) => core.emit('pad_ai', { id: 'другой', text: 'ЧУЖОЕ', done: true })", rid)
    pg.evaluate("(id) => core.emit('pad_ai', { id, text: 'Не сбавляйте темп: 6000 ИИ-кредитов в месяц.', done: true })", rid)
    pg.wait_for_timeout(150)
    body = pg.inner_text("#hmm-body")
    ok("Перевод Лиры" in body and "6000 ИИ-кредитов" in body and "ЧУЖОЕ" not in body and "Показать оригинал" in pg.inner_text("#hmm-tr"),
       "готово — «Перевод Лиры», чужие ответы блокнота не путаются")
    pg.click("#hmm-tr")
    pg.wait_for_timeout(150)
    ok("6,000 AI credits" in pg.inner_text("#hmm-body") and "Перевести на русский" in pg.inner_text("#hmm-tr"), "«Показать оригинал» — снова письмо")
    pg.click("#hmm-tr")
    pg.wait_for_timeout(150)
    ok(len([x for x in pg.evaluate("calls") if x[0] == "pad_ai"]) == 1 and "6000 ИИ-кредитов" in pg.inner_text("#hmm-body"),
       "второй раз — готовый перевод, без нового запроса")
    pg.click("#hmm-x")
    pg.click("#hm-mail .hmm-row >> nth=1")
    pg.wait_for_timeout(500)
    ok(pg.is_hidden("#hmm-tr") and "Подтверждаю встречу" in pg.inner_text("#hmm-body") and pg.evaluate("HMM.tr") is None,
       "письмо по-русски — кнопки нет; перевод прежнего письма не тянется")
    pg.click("#hmm-x")
    pg.evaluate("() => { document.documentElement.lang = 'en'; }")
    pg.click("#hm-mail .hmm-row >> nth=1")
    pg.wait_for_timeout(500)
    ok(pg.is_visible("#hmm-tr") and "Translate to English" in pg.inner_text("#hmm-tr"), "английская программа: письмо по-русски — «Translate to English»")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:2]}")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
