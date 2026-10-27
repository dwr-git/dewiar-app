"""Android (app.js): рассуждения модели и вызовы функций текстом — как на компьютере (свой Ollama с моделью,
которая пишет «Okay, the user wants…</think>» и <tool_call> в формате GLM).
Проверяем llmStream напрямую: поток Ollama режется на куски как попало; на экран и в озвучку не должно попасть
ни рассуждение, ни разметка вызова, а вызовы — распознаны."""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
ok = lambda c, m: print(("✅ " if c else "❌ ") + m)

www = Path(tempfile.mkdtemp()) / "www"
shutil.copytree(ROOT / "android/assets/www", www)
shutil.copy(ROOT / "ui/assets/entities.js", www / "entities.js")
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)   # живое лицо Эвы
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")


def nd(pieces):
    """Поток Ollama /api/chat: строки NDJSON, порезанные на куски по 7 символов (как приходит по сети)."""
    s = "".join(json.dumps({"message": {"role": "assistant", "content": p}, "done": False}, ensure_ascii=False) + "\n" for p in pieces)
    s += json.dumps({"message": {"role": "assistant", "content": ""}, "done": True}) + "\n"
    return [s[i:i + 7] for i in range(0, len(s), 7)]


def by_char(t):
    return list(t)


REASON = ("Okay, the user is asking about the USB hub and the monitors. I need to figure out what to check first. "
          "Let me think about which command would show the connected devices. Probably lsusb, and then dmesg. ") * 3
CASES = {
    "glm": nd(["Okay, the user wants Yandex Music. I should call yandex_music with the query.\n", "</think>", "<tool",
               "_call>yandex", "_music\n<arg_key>query</arg_key>\n", "<arg_value>Элла</arg_value>\n</tool_call>"]),
    "think": nd(by_char("<think>Пользователь здоровается.</think>Привет! Всё хорошо.")),
    "short": nd(["Привет! Всё хорошо."]),
    "only_reason": nd([REASON]),
    "gptoss": nd(["analysis", "The user greets. Answer briefly.", "assistant", "final", "Здравствуйте! Чем помочь?"]),
    "qwen_coder": nd(["Открываю.", "<tool_call>\n<function=open_app>\n<parameter=name>\nTelegram\n</parameter>\n</function>\n</tool_call>"]),
    "ru_ok": nd(["Хорошо, сейчас открою Telegram и проверю сообщения."]),
    "reason_then_ru": nd(by_char(REASON + "</think>\n\nПроверьте кабель хаба и выполните lsusb.")),
    "hermes": nd(['<tool_call>\n{"name": "get_time", "arguments": {}}\n</tool_call>']),
    "tail": nd(["Сравнение: пять меньше, чем шесть, то есть 5 <", "<", "<tool"]),
    "think_mid": nd(["<thi", "nk>", "Думаю, что сказать", "</th", "ink>", "Готово, ", "открыла."]),
    "multi": nd(["Сначала проверю.", "<tool_call>run_command\n<arg_key>command</arg_key>\n<arg_value>lsusb</arg_value>\n</tool_call>",
                 "<tool_call>battery_status\n</tool_call>"]),
    # Эва в 21:00: «{"name": "money_report", …}</tool_call>» без открывающего тега, потом сочинённый ответ
    "stray": nd(by_char('{"name": "x", "arguments": {"a": 1}}</tool_call>Сегодня потратили 500 рублей.')),
    "mid": nd(['Сейчас посмотрю. {"name": "x", "argu', 'ments": {}}</tool', '_call> Итог: ноль.']),
    "json_text": nd(by_char('Вот: {"name": "Иван", "age": 30} — пример.')),
    # №337 (пакет 27.10): иероглифы посреди русского ответа — прочь
    "cjk": nd(by_char("Сегодня тепло, 你好 около пятнадцати градусов.")),
    # №301 (пакет 27.10): DeepSeek пишет вызовы языком DSML — было видно в ответе, а погоду выдумывал
    "dsml": nd(by_char('Узнаю погоду.<｜DSML｜function_calls>\n<｜DSML｜invoke name="weather">\n<｜DSML｜parameter name="city" string="true">Москва'
                       '</｜DSML｜parameter>\n<｜DSML｜parameter name="days" string="false">1</｜DSML｜parameter>\n</｜DSML｜invoke>\n</｜DSML｜function_calls>'
                       ' Сейчас +13.')),
    # №348 (пакет 27.10, 11:31): DeepSeek v4.1 — «<DSML calls>» без «｜», все аргументы одним JSON; читалось вслух
    "dsml2": nd(by_char('Пишу.\n<DSML calls>\n<DSML invoke name="lab_write">\n<DSML parameter name="arguments" string="false">'
                        '{"name": "a.py", "content": "print(1)"}</DSML parameter>\n</DSML invoke>\n</DSML calls>\n')),
}

R = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto((www / "index.html").as_uri())
    pg.wait_for_timeout(800)
    for name, chunks in CASES.items():
        R[name] = pg.evaluate("""async (chunks) => {
            S.llm.kind = "ollama"; S.llm.base_url = "http://127.0.0.1:11434/v1"; S.llm.model = "chat";
            window.resolveModel = async () => "chat";
            window.http = async (m, u, o) => { for (const c of chunks) o.onChunk(c); return { status: 200, body: "" }; };
            const shown = [];
            const r = await llmStream([{ role: "user", content: "т" }], [{ name: "x", parameters: {} }], (t) => shown.push(t));
            return { text: r.text, shown: shown.join(""), calls: r.calls.map(c => [c.name, JSON.parse(c.args || "{}")]) };
        }""", chunks)
    b.close()

g = R["glm"]
ok(g["calls"] == [["yandex_music", {"query": "Элла"}]], f"GLM-вызов текстом распознан: {g['calls']}")
ok("Okay" not in g["shown"] and "tool" not in g["shown"] and "think" not in g["shown"], f"рассуждение и разметка не показаны: {g['shown']!r}")
ok(R["think"]["text"] == "Привет! Всё хорошо.", f"<think>…</think> по буквам вырезан: {R['think']['text']!r}")
ok(R["short"]["text"] == "Привет! Всё хорошо.", "короткий ответ — как есть")
ok(R["only_reason"]["text"] == "" and R["only_reason"]["shown"] == "", "одно рассуждение без ответа — не показывается и не озвучивается")
ok(R["gptoss"]["text"].strip() == "Здравствуйте! Чем помочь?", f"gpt-oss: только финальный ответ: {R['gptoss']['text']!r}")
q = R["qwen_coder"]
ok(q["calls"] == [["open_app", {"name": "Telegram"}]] and q["text"] == "Открываю.", f"Qwen3-Coder: {q['calls']} / {q['text']!r}")
ok(R["ru_ok"]["text"].startswith("Хорошо, сейчас открою"), "обычный ответ «Хорошо, …» не принят за рассуждение")
rr = R["reason_then_ru"]
ok(rr["text"].strip() == "Проверьте кабель хаба и выполните lsusb." and "Okay" not in rr["shown"], f"рассуждение без <think> по буквам → только ответ: {rr['text'].strip()!r}")
ok(R["hermes"]["calls"] == [["get_time", {}]] and not R["hermes"]["text"].strip(), f"JSON-вызов (Qwen/Hermes): {R['hermes']['calls']}")
m = R["multi"]
ok(m["calls"] == [["run_command", {"command": "lsusb"}], ["battery_status", {}]] and m["text"] == "Сначала проверю.", f"два вызова подряд: {m['calls']}")
ok(R["tail"]["text"] == "Сравнение: пять меньше, чем шесть, то есть 5 <<<tool" and R["tail"]["shown"] == R["tail"]["text"],
   f"конец ответа, похожий на начало тега, не теряется: {R['tail']['text']!r}")
ok(R["think_mid"]["text"] == "Готово, открыла.", f"теги <think> разрезаны на куски: {R['think_mid']['text']!r}")
st = R["stray"]
ok(st["calls"] == [["x", {"a": 1}]] and st["shown"] == "" and not st["text"].strip(), f"голый JSON + одинокий </tool_call> — вызов, ничего не звучит: {st}")
md = R["mid"]
ok(md["calls"] == [["x", {}]] and md["shown"].strip() == "Сейчас посмотрю." and "{" not in md["shown"], f"вызов голым JSON посреди текста вырезан: {md}")
ok(R["json_text"]["text"] == 'Вот: {"name": "Иван", "age": 30} — пример.' and not R["json_text"]["calls"], f"обычный JSON в ответе — текстом: {R['json_text']}")
ok(R["cjk"]["text"].replace("  ", " ") == "Сегодня тепло, около пятнадцати градусов.", f"иероглифы в русском ответе убраны: {R['cjk']['text']!r}")
ds = R["dsml"]
ok(ds["calls"] == [["weather", {"city": "Москва", "days": 1}]] and "DSML" not in ds["shown"] and "+13" not in ds["shown"],
   f"вызов DeepSeek (DSML) — выполняется, разметка и выдумка не видны: {ds}")
d2 = R["dsml2"]
ok(d2["calls"] == [["lab_write", {"name": "a.py", "content": "print(1)"}]] and "DSML" not in d2["shown"] and "print" not in d2["shown"],
   f"№348: «<DSML calls>» и аргументы одним JSON — вызов, вслух не читается: {d2}")
ok(not errors,"без ошибок JavaScript" + (f": {errors}" if errors else ""))
