"""Съёмка 17.10: на «Расскажи о себе, что ты умеешь» Лира раз за разом отвечала «Я Лира.» — модель (Qwen 27B) копировала
свой прошлый ответ из разговора. Теперь ответ слово в слово как недавний (короткий, без действий) — ядро просит модель
ответить по существу, и человек получает нормальный ответ. Первый раз «Я Лира.» не трогаем — повтора ещё нет.
Ядро — настоящее, модель — tests/mock_llm.py (на этот вопрос отвечает «Я Лира.», на просьбу не повторяться — по существу)."""
import srctext  # noqa: E402 — текст исходника вместе с частями (tests/srctext.py)
import asyncio, json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path
import websockets
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
PY = os.environ.get("DEWIAR_PY") or sys.executable
TESTS = Path(__file__).resolve().parent
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


tmp = Path(tempfile.mkdtemp()); (tmp / "cfg").mkdir()
PORT, LLM = free(), free()
(tmp / "cfg/settings.json").write_text(json.dumps({
    "persona": "lira", "llm": {"active": "t", "profiles": {"t": {"name": "Mock", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM}/v1", "disable_thinking": True}}},
    "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "audio": {"sounds": False, "follow_up_seconds": 0}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT),
           DEWIAR_ASSUME_AEC="1", DEWIAR_WORKSPACE_DIR=str(tmp / "ws"))
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
events = []


async def run():
    ws = None
    for _ in range(200):
        await asyncio.sleep(0.2)
        if (tmp / "cfg/token").exists():
            try:
                ws = await websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None); break
            except OSError:
                continue
    await ws.send(json.dumps({"cmd": "hello", "token": (tmp / "cfg/token").read_text().strip()}))

    async def reader():
        async for raw in ws:
            events.append(json.loads(raw))
    rd = asyncio.ensure_future(reader())
    await asyncio.sleep(3)
    for i in (1, 2):
        n0 = len([e for e in events if e.get("type") == "answer" and e.get("done")])
        await ws.send(json.dumps({"id": i, "cmd": "say", "args": {"text": "Расскажи о себе, что ты умеешь."}}))
        for _ in range(150):
            await asyncio.sleep(0.2)
            if len([e for e in events if e.get("type") == "answer" and e.get("done")]) > n0:
                break
        await asyncio.sleep(1)
    rd.cancel()

try:
    asyncio.run(run())
finally:
    core.terminate()
    try:
        core.wait(10)
    except subprocess.TimeoutExpired:
        core.kill()
    mock.terminate()
ans = [e.get("text", "") for e in events if e.get("type") == "answer" and e.get("done")]
log = (tmp / "core.log").read_text(encoding="utf-8", errors="replace")
ok(len(ans) >= 2 and ans[0].strip() == "Я Лира.", f"первый раз короткий ответ не трогаем: {ans[:1]}")
ok(len(ans) >= 2 and "напоминания" in ans[1] and "прошу ответить по существу" in log,
   f"второй раз то же самое — модель просят ответить по существу, человек получает нормальный ответ: {ans[1:2]}")
# «Звоню Людмиле.» без звонка (съёмка 17.10: раз сработало, потом только слова) — просим сделать
sys.path.insert(0, str(ROOT / "core"))
import quality as Q  # noqa: E402
c = {a: bool(Q.action_claim("Позвони Людмиле по видео", a)) for a in
     ("Звоню Людмиле.", "Звоню Людмиле по видео.", "Набираю маму.", "Отправила сообщение.", "Не звоню.", "Звонить ли Людмиле?", "Я Лира.")}
ok(c == {"Звоню Людмиле.": True, "Звоню Людмиле по видео.": True, "Набираю маму.": True, "Отправила сообщение.": True,
         "Не звоню.": False, "Звонить ли Людмиле?": False, "Я Лира.": False} and not Q.action_claim("x", "Звоню Людмиле.", {"close_call"}),
   f"«звоню / набираю / отправила» без вызова — просим сделать; с вызовом, отрицание или вопрос — нет: {c}")
# «Позвони Людмиле по видео» — человеку из «Близких» звоним сразу, без модели
import types  # noqa: E402
import engine_tools as ET  # noqa: E402
from close import CloseError, match_name  # noqa: E402
PEOPLE = [{"pid": "p1", "name": "Людмила Исаева", "devs": [{"dev": "d"}]}, {"pid": "p2", "name": "Мама", "devs": [{"dev": "d"}]}]


class FakeClose:
    def __init__(self): self.calls = []
    def person(self, who):
        p = match_name(who, PEOPLE)
        if not p:
            raise CloseError("нет")
        return p
    def call(self, who, video=False): self.calls.append((who, video)); return {"name": "Людмила Исаева"}


said = []
e = types.SimpleNamespace(emit=lambda *a, **k: None, close=FakeClose(), _say_quick=lambda msg, text, via=None, **k: said.append(msg))
r = [ET.ToolsMixin._call_cmd(e, q) for q in ("Позвони Людмиле Исаевой по видеосвязи.", "Лира, позвони Людмиле.", "Набери маме",
                                                "Позвони в такси", "Позвони Людмиле и скажи, что я задержусь на час, пожалуйста")]
ok(r == [True, True, True, False, False] and e.close.calls == [("p1", True), ("p1", False), ("p2", False)]
   and said[:2] == ["Звоню Людмиле Исаевой по видео.", "Звоню Людмиле."],
   f"«позвони Людмиле по видео» — звонок сразу, без модели; не из «Близких» или длинная просьба — модели: {r}, {e.close.calls}, {said}")
# «Отправь Людмиле сообщение: «…»» — сразу, без модели (съёмка 17.10: «говорит, что отправила, — и ничего»)
sent, said2 = [], []
PEOPLE += [{"pid": "p3", "name": "Андрей", "devs": [{"dev": "d"}]}, {"pid": "p4", "name": "Лёха", "devs": [{"dev": "d"}]}]
FakeClose.send = lambda self, pid, msg: sent.append((pid, msg))
e2 = types.SimpleNamespace(emit=lambda *a, **k: None, close=FakeClose(), _say_quick=lambda msg, text, via=None, **k: said2.append(msg), _SEND_RX=ET.ToolsMixin._SEND_RX)
e2._send_loose = lambda t: ET.ToolsMixin._send_loose(e2, t)
qs = ["Отправь Людмиле сообщение: «Привет, как твои дела?»", "Напиши Андрею: «Привет. Как твои дела?»",
      "Отправь сообщение Лёхе. Лёха, привет! Как твои дела?", "Лира, напиши маме, что я задержусь",
      "Напиши письмо Андрею о встрече", "Напиши Андрею в телеграм: привет", "Напиши стих про осень"]
r = [ET.ToolsMixin._send_cmd(e2, q) for q in qs]
ok(r == [True, True, True, True, False, False, False]
   and sent == [("p1", "Привет, как твои дела?"), ("p3", "Привет. Как твои дела?"), ("p4", "Лёха, привет! Как твои дела?"), ("p2", "Я задержусь")]
   and said2[0] == "Отправил Людмиле.",                         # в роде персонажа — engine._g («Отправила» у Лиры)
   f"сообщение близкому — сразу, без модели; письмо, Telegram, стих — модели: {r}, {sent}")
# как пишет распознавание речи (экзамен «как в жизни», 18.10): без двоеточия, имя впереди
sent.clear()
r = [ET.ToolsMixin._send_cmd(e2, q) for q in ("отправь сообщение андрею привет как дела", "а теперь лёхе напиши во сколько встречаемся завтра",
                                               "напиши андрею письмо", "андрей напиши стих")]
ok(r == [True, True, False, False] and sent == [("p3", "Привет как дела"), ("p4", "Во сколько встречаемся завтра")],
   f"без запятых и двоеточий — тоже отправка близкому: {r}, {sent}")
ok("self._send_cmd(text, via)" in srctext.text(ROOT, "core/engine_answer.py"), "быстрая отправка стоит перед моделью")
# «Включи смешное видео на YouTube» — сразу play_youtube, без модели (съёмка 17.10: «говорит, что включает, — и ничего»)
import tools_base as TT  # noqa: E402 — запуск и браузер — в основе действий (1.0.8)
opened = []
TT.launch = lambda cmd, **k: opened.append(cmd[-1])
said3 = []
e3 = types.SimpleNamespace(emit=lambda *a, **k: None, _say_quick=lambda msg, text, via=None, **k: said3.append((msg, k.get("acts"))))
r = [ET.ToolsMixin._youtube_cmd(e3, q) for q in ("Включи смешное видео на YouTube.", "найди мне на YouTube какое-нибудь смешное видео.",
                                                  "Лира, включи на ютубе лекцию про космос", "Включи музыку", "Открой YouTube")]
ok(r == [True, True, True, False, False] and len(opened) == 3 and all("youtube.com" in u for u in opened)
   and all(a == ["play_youtube"] for _, a in said3),
   f"«включи смешное видео на YouTube» — ролик открывается сразу, без модели; в истории помечено действие: {r}, {said3[:1]}")
# ссылка — в новом окне браузера (видео открывалось вкладкой в свёрнутом окне на другом мониторе)
import tempfile as _tf  # noqa: E402
home = Path(_tf.mkdtemp()); (home / ".local/share/applications").mkdir(parents=True)
(home / ".local/share/applications/google-chrome.desktop").write_text("[Desktop Entry]\nExec=/usr/bin/google-chrome-stable %U\n"
                                                                      "[Desktop Action new-window]\nExec=/usr/bin/google-chrome-stable --new-window\n")
real_run, real_dry, real_home = TT.subprocess.run, TT.DRY, os.environ.get("HOME")
TT.subprocess.run = lambda *a, **k: types.SimpleNamespace(stdout="google-chrome.desktop\n")
TT.DRY, os.environ["HOME"] = None, str(home)
try:
    bc = TT.browser_cmd("https://www.youtube.com/watch?v=x")
    TT.subprocess.run = lambda *a, **k: types.SimpleNamespace(stdout="org.gnome.Epiphany.desktop\n")
    bc2 = TT.browser_cmd("https://x.ru")
finally:
    TT.subprocess.run, TT.DRY = real_run, real_dry
    if real_home:
        os.environ["HOME"] = real_home
ok(bc == ["/usr/bin/google-chrome-stable", "--new-window", "https://www.youtube.com/watch?v=x"] and bc2 == ["xdg-open", "https://x.ru"],
   f"ролик и сайты — в новом окне браузера (Chrome/Firefox), прочие — как раньше: {bc}, {bc2}")
# в истории за словами видно действие — модель не копирует «Включаю.» без вызова
import engine_answer as EA  # noqa: E402
w = EA.team_window([{"role": "user", "content": "включи видео"}, {"role": "assistant", "content": "Включаю.", "who": "lira", "acts": ["play_youtube"]}],
                   "lira", lambda x: x)
ok("выполнено инструментами: play_youtube" in w[-1]["content"] and "СЛОВА НЕ ДЕЙСТВУЮТ" in srctext.text(ROOT, "core/engine_answer.py"),
   "в истории для модели ответ помечен выполненным действием; в подсказке — «слова не действуют, вызывай снова»")
from llm import CodeFilter  # noqa: E402
cf = CodeFilter()
spoken = cf.feed("Включаю.\n[в этом ответе выполнено инструментами: play_youtube]\nГотово.") + cf.flush()
ok(spoken == "Включаю.\nГотово." and EA.ACTS_RX.sub("", "Включаю. [в этом ответе выполнено инструментами: x]") == "Включаю.",
   f"пометку модель могла повторить — вслух и на экране её нет: {spoken!r}")
ok("self._call_cmd(text, via)" in srctext.text(ROOT, "core/engine_answer.py"), "быстрый звонок стоит перед моделью")
ok("or action_claim(text, step_text, called)" in srctext.text(ROOT, "core/engine_answer.py"), "проверка стоит в ходе разговора")
if fails:
    print("\n".join(l for l in log.splitlines() if "dewiar" in l)[-3000:])
print("\nИТОГ:", "всё прошло" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
