"""Студия → «Бот в Telegram» → «Посты» и «Рубрики» (0.69): видны, только когда бот подключён; каналы и группы — плитками
(выбранные залиты), «Добавить» @канал; пост — текст или «Придумать» по теме, сейчас (с «Опубликовать сейчас?») или ко
времени («Запланировать»); ждущий одобрения — «Опубликовать»; рубрика — тема, дни, время, с одобрением; новички —
переключатель и текст приветствия."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


FAKE_CORE = """(() => {
  window.calls = [];
  const D = { posts: [
      { id: "w1", text: "Совет дня: улун заваривают при 85°.", poll: null, chats: ["-1001"], at: "", status: "wait", source: "rubric", topic: "совет дня", created: 2, sent: [], err: "" },
      { id: "s1", text: "Новый улун приехал!", poll: null, chats: ["-1001"], at: "", status: "sent", source: "studio", topic: "", created: 1, at_sent: 1761800000, sent: [{ chat: "-1001", link: "https://t.me/chainews/5" }], err: "" }],
    rubrics: [], chats: [{ id: "-1001", title: "Новости чая", type: "channel", username: "chainews", can: true }, { id: "-700", title: "Клуб любителей", type: "supergroup", username: "", can: true }],
    greet: { on: false, text: "" }, wait: 1 };
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "pbot_get") return { connected: true, on: true, running: true, bot: "chai_bot", persona: "lira", personas: [{ id: "lira", name: "Лира", color: "#9BD4FF", kb: 1 }], groups: true, per_user: 30, per_day: 300, brief: "", welcome: "", kb: [], model: "", log: [], chats: [], today: 0, total: 0 };
      if (c === "pbot_post_write") return { text: "Улун — чай между зелёным и чёрным. А вы какой любите?" };
      if (c === "pbot_rubric_set") { D.rubrics.push({ id: "r1", topic: a.topic, days: a.days, time: a.time, approve: a.approve, chats: a.chats }); return D; }
      if (c === "pbot_greet") { Object.assign(D.greet, a.on !== undefined ? { on: a.on } : {}, a.text !== undefined ? { text: a.text } : {}); return D; }
      if (c.startsWith("pbot_post") || c.startsWith("pbot_chat")) return D;
      return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();"""

with sync_playwright() as p:
    b = p.chromium.launch(); errors = []
    st = b.new_page(viewport={"width": 1400, "height": 1000}); st.on("pageerror", lambda e: errors.append(str(e)))
    st.route(re.compile(r"^https?://"), lambda r: r.abort())
    st.add_init_script(FAKE_CORE)
    st.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); st.wait_for_timeout(1500)
    st.evaluate("document.querySelector('nav button[data-p=\"pbot\"]').click()"); st.wait_for_timeout(800)
    ok(st.locator("#bp-posts").is_visible() and st.locator("#bp-rub").is_visible(), "бот подключён — «Посты» и «Рубрики» видны")
    tiles = st.locator("#pp-where .pp-chat")
    ok(tiles.count() == 2 and "канал · @chainews" in tiles.nth(0).inner_text() and "on" in tiles.nth(0).get_attribute("class"), "каналы и группы — плитками, первый выбран")
    ok("ждут одобрения: 1" in st.inner_text("#pp-stat") and "Ждут одобрения" in st.inner_text("#pp-list") and "рубрика «совет дня»" in st.inner_text("#pp-list"), "ждущий одобрения пост — первым, с рубрикой")
    ok(st.get_attribute("#pp-list .st-sent a", "href") == "https://t.me/chainews/5", "опубликованный — со ссылкой «Открыть»")
    st.click("#pp-list [data-ok='w1']"); st.wait_for_timeout(200)
    ok(["pbot_post_ok", {"id": "w1"}] in st.evaluate("calls"), "«Опубликовать» ждущий пост")
    st.fill("#pp-topic", "что такое улун"); st.click("#pp-write"); st.wait_for_timeout(300)
    ok(st.input_value("#pp-text").startswith("Улун — чай") and ["pbot_post_write", {"topic": "что такое улун", "chat_title": "Новости чая"}] in st.evaluate("calls"),
       "«Придумать» — пишет персонаж, текст можно поправить")
    tiles.nth(1).click(); st.wait_for_timeout(100)
    st.click("#pp-go"); st.wait_for_timeout(200)
    q = st.inner_text(".dwq") if st.locator(".dwq").count() else ""
    ok("Новости чая, Клуб любителей" in q, f"сейчас — сначала «Опубликовать сейчас в …?»: {q!r}")
    st.click(".dwq .yes"); st.wait_for_timeout(300)
    add = [a for c, a in st.evaluate("calls") if c == "pbot_post_add"]
    ok(add and add[0]["chats"] == ["-1001", "-700"] and add[0]["text"].startswith("Улун") and add[0]["at"] == "" and add[0]["poll"] is None, f"пост — в оба: {add[:1]}")
    st.fill("#pp-text", "Дегустация в субботу в 18:00"); st.fill("#pp-at", "2026-10-31T10:00"); st.wait_for_timeout(100)
    ok(st.inner_text("#pp-go") == "Запланировать", "указали время — «Запланировать»")
    st.click("#pp-go"); st.wait_for_timeout(300)
    add = [a for c, a in st.evaluate("calls") if c == "pbot_post_add"]
    ok(len(add) == 2 and add[1]["at"] == "2026-10-31T10:00", "запланировано без лишнего вопроса")
    st.fill("#pp-rt", "совет дня о чае"); st.click("#pp-rubf .pp-days button[data-d='4']"); st.fill("#pp-rtime", "11:00")
    st.click("#pp-rubf button[type=submit]"); st.wait_for_timeout(300)
    rs = [a for c, a in st.evaluate("calls") if c == "pbot_rubric_set"]
    ok(rs and rs[0]["days"] == [0, 1, 2, 3] and rs[0]["time"] == "11:00" and rs[0]["approve"] is True, f"рубрика: дни, время, с одобрением: {rs}")
    ok("совет дня о чае" in st.inner_text("#pp-rubs") and "Пн, Вт, Ср, Чт в 11:00" in st.inner_text("#pp-rubs"), "рубрика — в списке")
    st.click(".bp-row:has(#pp-greet)"); st.wait_for_timeout(300)
    ok(["pbot_greet", {"on": True}] in st.evaluate("calls") and st.locator("#pp-greet-t").is_visible(), "новички: включили — появился текст приветствия")
    st.locator("#bp-posts").screenshot(path="/tmp/claude-0/pbot_posts.png"); st.locator("#bp-rub").screenshot(path="/tmp/claude-0/pbot_rub.png")
    ok(not errors, f"без ошибок: {errors[:2]}")
    b.close()
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
