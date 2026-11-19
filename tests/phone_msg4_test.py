"""Идея №4 (план улучшений 19.11, п. 5: «Лира пишет в Telegram и MAX от вашего имени — с подтверждением каждого
сообщения»). Раньше «напиши Ане в телеграм: …» открывало Telegram с текстом, а получателя человек искал сам. Теперь —
чат именно с этим человеком (номер из контактов: tg://resolve?phone=…&text=…, WhatsApp — wa.me), текст уже в поле;
«Отправить» нажимает человек. Несколько похожих в контактах — спросить; MAX, Viber, VK и веб-версия — как раньше."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 820})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    pg.evaluate("""() => { window.__urls = []; window.__shared = [];
      const book = { 'Ане': { name: 'Аня Петрова', number: '8 (916) 123-45-67', alts: [] }, 'Саше': { name: 'Саша Иванов', number: '+7 916 000-11-22', alts: [{ name: 'Саша Работа', number: '+79160003344' }] },
                     'Олегу': { name: 'Олег', number: '+44 7700 900123', alts: [] }, 'мама': { name: 'Мама', number: '9161112233', alts: [] } };
      D.contact = (w) => JSON.stringify(book[w] || {}); D.openUrl = (u) => { __urls.push(u); return true; };
      D.shareTo = (pkg, t) => { __shared.push([pkg, t]); return true }; }""")

    def q(t):
        return pg.evaluate("async (t) => { __urls.length = 0; __shared.length = 0; const r = await quick(t); return [r && r.say, [...__urls], [...__shared]]; }", t)
    say, urls, sh = q("Напиши Ане в телеграм: опоздаю на 10 минут")
    ok(urls == ["tg://resolve?phone=79161234567&text=" + "%D0%BE%D0%BF%D0%BE%D0%B7%D0%B4%D0%B0%D1%8E%20%D0%BD%D0%B0%2010%20%D0%BC%D0%B8%D0%BD%D1%83%D1%82"]
       and "Аня Петрова" in say and "Отправить" in say and not sh, f"Telegram: чат с Аней (8 916… → 7916…), текст в поле: {say} {urls}")
    say, urls, sh = q("напиши Олегу в ватсап: привет")
    ok(urls == ["https://wa.me/447700900123?text=%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82"], f"WhatsApp: wa.me с международным номером: {urls}")
    say, urls, sh = q("напиши Саше в телеграм: созвонимся?")
    ok(not urls and not sh and "несколько похожих" in say and "Саша Работа" in say, f"двое похожих — спросить, не писать не тому: {say}")
    say, urls, sh = q("напиши Ане в макс: привет")
    ok(not urls and sh and sh[0][1] == "привет" and "выберите, кому" in say, f"MAX — ссылки на чат нет: как раньше, получателя выбирает человек: {say}")
    say, urls, sh = q("напиши в телеграм: всем привет")
    ok(not urls and sh and sh[0][1] == "всем привет", "без получателя — как раньше")
    say, urls, sh = q("напиши Ане в телеграм что буду в семь")
    ok(urls and urls[0].endswith("text=" + "%D0%B1%D1%83%D0%B4%D1%83%20%D0%B2%20%D1%81%D0%B5%D0%BC%D1%8C"), f"«…что буду в семь» — в сообщении «буду в семь»: {urls}")
    pg.evaluate("() => { D.handsState = () => 'on'; }")
    say, urls, sh = q("напиши Ане в телеграм что буду в семь")
    ok(say is None and not urls, "версия с «руками» — быстрый путь уступает модели (она откроет чат и напишет сама)")
    pg.evaluate("() => { D.handsState = () => 'none'; }")
    say, urls, sh = q("напиши Незнакомцу в телеграм: привет")
    ok(not urls and sh, "нет в контактах — как раньше, текст в Telegram")
    # инструмент модели: to
    r = pg.evaluate("""async () => { __urls.length = 0; turnAsk = 'напиши маме в телеграм, что я дома';
      const t = await runTool('send_message', { app: 'telegram', text: 'Я дома', to: 'маме' }); return [t, [...__urls]]; }""")
    ok(r[1] and r[1][0].startswith("tg://resolve?phone=79161112233&text=") and "Отправить" in r[0], f"модель: to «маме» — как у звонка (родные): {r}")
    spec = pg.evaluate("() => JSON.stringify(toolSpecs().find(t => (t.function || t).name === 'send_message'))")
    ok('"to"' in spec and "Отправляет всегда сам пользователь" in spec, "описание инструмента: to и «отправляет человек»")
    ok(pg.evaluate("[intlPhone('8 916 123-45-67'), intlPhone('+7 (916) 123-45-67'), intlPhone('123-45'), intlPhone('9161234567')]")
       == ["79161234567", "79161234567", "", "79161234567"], "номер — в международный вид; короткий — не годится")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
