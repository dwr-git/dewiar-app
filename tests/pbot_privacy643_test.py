"""№643, №644 (10.11, «Бот в Telegram»): «в группе бот не отвечает ни на имя, ни на вопросы», «сделал админом, а у бота
надпись „не имеет доступа к сообщениям“». Это режим приватности Telegram: бот видит в группе только @упоминания и ответы
ему. Теперь ядро само спрашивает getMe (can_read_all_group_messages) и студия по шагам говорит, что сделать в @BotFather;
идея №147 — в группе бот отзывается и на имя без @ («Лира, подскажи…»), когда Telegram присылает ему такие сообщения.
Ядро — на подставном Telegram, студия — Playwright с подставным ядром."""
import os, sys, tempfile, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from pbot import PersonaBot  # noqa: E402


class Host:
    s = {"persona": "lira"}
    events = []

    class personas:
        @staticmethod
        def get(pid):
            return {"id": "lira", "name": "Лира"}

    def emit(self, kind, **kw):
        self.events.append((kind, kw))


host = Host()
b = PersonaBot(host, path=Path(tempfile.mkdtemp()) / "pbot.json")
ME = {"id": 42, "is_bot": True, "username": "school_bot", "first_name": "Ассистент Школы", "can_read_all_group_messages": False}
CALLS, ANSWERS, SENT = [], [], []


def fake_call(method, timeout=20, files=None, **params):
    CALLS.append(method)
    if method == "getMe":
        return dict(ME)
    if method == "sendMessage":
        SENT.append(params)
        return {"message_id": 1}
    return True


b._call = fake_call
b.start = lambda: None                                   # без опроса Telegram
b.connect("123456789:AAH" + "x" * 32)
ok(b.public()["read_all"] is False, "подключили — режим приватности известен сразу (getMe: can_read_all_group_messages)")
ok(b.public()["names"] == ["Лира", "Ассистент Школы"], f"имена бота — персонаж и имя из @BotFather: {b.public()['names']}")

# имя
for t, want in (("Лира, подскажи, есть ли рассрочка?", True), ("эй, Лира", True), ("а ты как думаешь, Лира?", True),
                ("Привет Лира! кто ведёт курс", True), ("Ассистент Школы, сколько стоит?", True),
                ("я вчера говорил Лире про курс", False), ("мне кажется Лира права", False), ("Лиру потом спрошу", False),
                ("лирика тут ни при чём", False)):
    ok(b.called(t) is want, f"«{t}» — {'зовут' if want else 'не зовут'} по имени")

# группа: сообщения
b._answer = lambda chat, reply_to, who, text, group, voice=None: ANSWERS.append(text)
b.pool.submit = lambda fn, *a, **k: fn(*a, **k)
G = {"id": -100500, "type": "supergroup", "title": "Курс ТРТ"}
n = [0]


def msg(text, **kw):
    n[0] += 1
    b._handle({"update_id": n[0], "message": dict({"message_id": n[0], "chat": G, "from": {"id": 7 + n[0], "first_name": "Аня"}, "text": text}, **kw)})
    b.last_chat.clear()                                  # не «чаще раза в 4 с»


msg("Лира, есть ли рассрочка?")
ok(ANSWERS[-1:] == ["Лира, есть ли рассрочка?"], f"«Лира, есть ли рассрочка?» — ответила по имени: {ANSWERS}")
ok((b.data.get("chats") or {}).get("-100500", {}).get("hears") is True, "сообщение не боту пришло — группа помечена «слышит всё»")
k = len(ANSWERS); msg("ребята, кто сегодня на занятии?")
ok(len(ANSWERS) == k, "обычный разговор участников — бот молчит")
msg("@school_bot сколько стоит курс?")
ok(len(ANSWERS) == k + 1 and "сколько стоит курс" in ANSWERS[-1], "@упоминание — как раньше")
b.set({"by_name": False}); k = len(ANSWERS); msg("Лира, есть ли рассрочка?")
ok(len(ANSWERS) == k and b.public()["by_name"] is False, "«Отзываться на имя» выключено — на имя молчит")
b.set({"by_name": True})

# режим приватности выключили в @BotFather — getMe говорит об этом, студия получает событие
ME["can_read_all_group_messages"] = True
b._priv_at = 0
host.events.clear()
ok(b.privacy() is True and b.public()["read_all"] is True, "getMe: режим приватности выключен — read_all")
ok(("pbot", {"read_all": True}) in host.events, f"событие «pbot» студии: {host.events}")
c0 = CALLS.count("getMe"); b.privacy(); b.privacy()
ok(CALLS.count("getMe") == c0, "getMe не чаще раза в 5 минут")
b.privacy(fresh=True)
ok(CALLS.count("getMe") == c0 + 1, "«Проверить снова» — спрашивает сейчас")
ok("назовут по имени" in b._hello(group=True), f"приветствие в группе говорит про имя: {b._hello(group=True)}")

# ---------- студия ----------
from playwright.sync_api import sync_playwright  # noqa: E402
import re  # noqa: E402
FAKE = """(() => { window.calls = []; window.RA = false;
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    const base = () => ({ connected: true, on: true, running: true, bot: "school_bot", persona: "lira", personas: [{ id: "lira", name: "Лира", color: "#9BD4FF", kb: 0 }],
      groups: true, by_name: true, read_all: window.RA, names: ["Лира"], per_user: 30, per_day: 300, brief: "", welcome: "", kb: [], model: "", log: [],
      chats: [{ title: "Курс ТРТ", type: "supergroup", can: true }], today: 0, total: 0 });
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "pbot_get" || c === "pbot_check") return base();
      if (c === "pbot_set") return Object.assign(base(), a.patch);
      if (c === "pbot_posts") return { posts: [], rubrics: [], chats: [], greet: { on: false, text: "" }, wait: 0 };
      return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();"""
SHOT = os.environ.get("DEWIAR_SHOTS", "")
with sync_playwright() as p:
    br = p.chromium.launch(); errors = []
    for skin in ("neusky", "neudusk"):
        st = br.new_page(viewport={"width": 1400, "height": 1000}); st.on("pageerror", lambda e: errors.append(str(e)))
        st.route(re.compile(r"^https?://"), lambda r: r.abort())
        st.add_init_script(FAKE)
        st.goto((ROOT / "ui/settings.html").as_uri() + "?port=1&skin=" + skin); st.wait_for_timeout(1500)
        st.evaluate("document.querySelector('nav button[data-p=\"pbot\"]').click()"); st.wait_for_timeout(800)
        txt = st.inner_text("#bp-priv") if st.locator("#bp-priv").is_visible() else ""
        ok("только @упоминания" in txt and "/setprivacy" in txt and "Disable" in txt and "добавьте снова" in txt,
           f"{skin}: режим приватности включён — что сделать в @BotFather, по шагам")
        ok(st.locator("#bp-byname-row").is_visible() and "Лира, подскажи" in st.inner_text("#bp-byname-row"), f"{skin}: «Отзываться на имя» — с именем персонажа")
        if SHOT:
            st.locator("#bp-priv").screenshot(path=f"{SHOT}/pbot_priv_{skin}.png")
        st.evaluate("window.RA = true"); st.click("#bp-priv-go"); st.wait_for_timeout(400)
        txt = st.inner_text("#bp-priv")
        ok("Видит сообщения в группах" in txt and "Лира, …" in txt and "«Курс ТРТ»" in txt and "ok" in st.get_attribute("#bp-priv", "class"),
           f"{skin}: «Проверить снова» — выключен: видит группы, отвечает на имя; группа без вестей — «уберите и добавьте снова»")
        ok(["pbot_check", {}] in st.evaluate("calls") or any(c[0] == "pbot_check" for c in st.evaluate("calls")), f"{skin}: «Проверить снова» спрашивает ядро")
        st.click("#bp-byname-row"); st.wait_for_timeout(300)
        ok(["pbot_set", {"patch": {"by_name": False}}] in st.evaluate("calls"), f"{skin}: переключатель «Отзываться на имя» сохраняется")
        st.close()
    ok(not errors, f"без ошибок на странице: {errors[:2]}")
    br.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
