"""Телефон: руки в других приложениях (служба спец. возможностей Hands.java). Подменяем мост: «Telegram» с экраном
чатов и полем сообщения; модель по шагам: open_app → phone_tap «Мама» → phone_type → phone_tap «Отправить» → итог.
Проверяем: инструменты есть у модели, после действия к ответу приложен свежий экран, кругов больше шести, служба
выключена — честный ответ, как включить (и в подсказке модели), карточка «Управлять приложениями» в настройках."""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


www = Path(tempfile.mkdtemp()) / "www"
shutil.copytree(ROOT / "android/assets/www", www)
shutil.copy(ROOT / "ui/assets/entities.js", www / "entities.js")
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)   # живое лицо Эвы
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
JS = """async (handsOn) => {
  Object.assign(S.llm, { kind: "openai", base_url: "https://dewiar.pro/dwrapp/cloud.php?p=", api_key: "dw-x", model: "chat", cloud: true });
  S.onboarded = true; window.resolveModel = async () => "chat"; window.sleep = (ms) => new Promise(r => setTimeout(r, 5));
  const acts = [];
  let scr = "home";
  const SCREENS = {
    home: "Приложение: Рабочий стол (launcher)\\n[1] текст «Telegram»\\n",
    chats: "Приложение: Telegram (org.telegram.messenger)\\n[1] кнопка «Поиск»\\n[2] текст «Мама» — нажимается\\n[3] текст «Работа» — нажимается\\n",
    chat: "Приложение: Telegram (org.telegram.messenger)\\n[1] текст «Мама»\\n[2] поле ввода (подсказка: «Сообщение»)\\n[3] кнопка «Отправить»\\n",
    sent: "Приложение: Telegram (org.telegram.messenger)\\n[1] текст «Мама»\\n[2] текст «Задержусь на полчаса»\\n[3] поле ввода (подсказка: «Сообщение»)\\n",
  };
  Object.assign(D, {
    handsState: () => handsOn ? "on" : "",
    handsScreen: () => handsOn ? SCREENS[scr] : "OFF",
    handsTapText: (t) => { acts.push("tapText:" + t); if (!handsOn) return "OFF"; if (t === "Мама") scr = "chat"; return "Нажато: «" + t + "»."; },
    handsTap: (id, l) => { acts.push("tap:" + id); if (!handsOn) return "OFF"; if (scr === "chat" && id === 3) scr = "sent"; return "Нажато."; },
    handsType: (id, t, sub) => { acts.push("type:" + id + ":" + t); return handsOn ? "Введено." : "OFF"; },
    handsScroll: () => "Пролистано.", handsNav: (w) => { acts.push("nav:" + w); return "Готово."; }, toFront: () => acts.push("front"),
    openApp: (n) => { acts.push("open:" + n); if (/telegram|телеграм/i.test(n)) { scr = "chats"; return "Telegram"; } return ""; },
  });
  const NL = String.fromCharCode(10, 10), seen = [];
  const sse = (o) => "data: " + JSON.stringify(o) + NL;
  const call = (name, args) => sse({ choices: [{ delta: { tool_calls: [{ index: 0, id: "c" + seen.length, function: { name, arguments: JSON.stringify(args) } }] } }] });
  // восемь кругов с инструментами: раньше ход обрывался на шестом
  const plan = [["phone_screen", {}], ["open_app", { name: "Телеграм" }], ["phone_screen", {}], ["phone_tap", { text: "Мама" }], ["phone_screen", {}],
                ["phone_type", { id: 2, text: "Задержусь на полчаса" }], ["phone_screen", {}], ["phone_tap", { id: 3 }]];
  window.http = async (m, u, o) => {
    if (!o.onChunk) return { status: 200, body: "{}" };
    const body = typeof o.body === "string" ? JSON.parse(o.body) : o.body; seen.push(body);
    const step = body.messages.filter(x => x.role === "tool").length;
    const out = !handsOn ? (step ? sse({ choices: [{ delta: { content: "Включите «Управлять приложениями» в настройках." } }] }) : call("phone_screen", {}))
      : step < plan.length ? call(...plan[step]) : sse({ choices: [{ delta: { content: "Написала маме: «Задержусь на полчаса»." } }] });
    o.onChunk(out + "data: [DONE]" + NL); return { status: 200, body: "" };
  };
  await ask("напиши маме в телеграм что задержусь на полчаса");
  for (let i = 0; i < 300 && busy; i++) await new Promise(r => setTimeout(r, 30));
  const tools = seen[0].tools.map(t => t.function.name);
  const toolMsgs = seen[seen.length - 1].messages.filter(x => x.role === "tool").map(x => x.content);
  return { acts, tools, toolMsgs, rounds: seen.length, sys: seen[0].messages[0].content, bot: document.querySelector("#bot").textContent };
}"""
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 393, "height": 852}); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(800)
    R = pg.evaluate(JS, True)
    ok(all(t in R["tools"] for t in ("phone_screen", "phone_tap", "phone_type", "phone_scroll", "phone_nav")), "у модели есть инструменты рук")
    ok("open:Телеграм" in R["acts"] or any(a.startswith("open:") for a in R["acts"]), f"открыла Telegram: {R['acts']}")
    ok("tapText:Мама" in R["acts"] and "type:2:Задержусь на полчаса" in R["acts"] and "tap:3" in R["acts"], f"нажала, ввела, отправила: {R['acts']}")
    ok(R["rounds"] == 9, f"девять кругов модели (больше прежних шести): {R['rounds']}")
    ok(any("Открыто: Telegram" in m and "«Мама»" in m for m in R["toolMsgs"]), "open_app сразу показывает экран приложения")
    ok(any(m.startswith("Нажато") and "Теперь на экране" in m and "поле ввода" in m for m in R["toolMsgs"]), "после нажатия — свежий экран в ответе")
    ok("Написала маме" in R["bot"], f"итог сказан: {R['bot'][:80]}")
    ok("phone_screen" in R["sys"] and "подтверждение" in R["sys"], "подсказка модели: как работать в приложениях и спрашивать перед отправкой")
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(800)
    R = pg.evaluate(JS, False)
    ok(any("Управление другими приложениями выключено" in m and "Управлять приложениями" in m for m in R["toolMsgs"]), "служба выключена — модель узнаёт, как включить")
    ok(not any(a.startswith("type:") or a.startswith("tap") for a in R["acts"]), "выключено — ничего не нажато")
    ok("сможешь, если пользователь включит" in R["sys"], "подсказка модели при выключенной службе")
    pg.evaluate("() => { openSettings('hands'); }")
    pg.wait_for_timeout(300)
    card = pg.evaluate("() => { const c = document.querySelector('#hands-card'); return c ? c.innerText : ''; }")
    if not card:
        tabs = pg.evaluate("() => [...document.querySelectorAll('[data-st]')].map(b => b.dataset.st)")
        for t in tabs:
            pg.evaluate(f"() => {{ setTab = '{t}'; renderSettings(); }}")
            card = pg.evaluate("() => { const c = document.querySelector('#hands-card'); return c ? c.innerText : ''; }")
            if card:
                break
    ok("Включить" in card and "Специальные возможности" in card, f"карточка «Управлять приложениями» в настройках: {card[:90]}")
    opened = pg.evaluate("() => { let w = ''; D.openSettings = (x) => { w = x; return true; }; document.querySelector('#hands-go').click(); return w; }")
    ok(opened == "accessibility", "кнопка открывает «Специальные возможности»")
    # основная сборка без «рук» (Dewiar.apk ставится без предупреждений Android) — карточка ведёт к версии с руками
    url = pg.evaluate("""() => { D.handsState = () => "none"; let u = ""; D.openUrl = (x) => { u = x; return true; };
        renderSettings(); const b = document.querySelector('#hands-dl'); if (b) b.click(); return u; }""")
    card2 = pg.evaluate("() => { const c = document.querySelector('#hands-card'); return c ? c.innerText : ''; }")
    ok(url.endswith("/Dewiar-hands.apk") and "расширенная версия" in card2, f"в основной сборке — «Скачать версию с «руками»»: {url}")
    ok(not errors, f"без ошибок страницы {errors[:2]}")
    b.close()
print("ALL OK" if not fails else f"ошибок: {len(fails)}")
sys.exit(1 if fails else 0)
