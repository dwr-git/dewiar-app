"""№446 (ПК 0.76.0, 31.10): «Неимоверно долго отвечает, устал ждать, непонятно, что не так». Лира вернувшемуся человеку
готовила приветствие в одну фразу — и пять минут «думала»: служебное поручение длинное, и его считали «сложной
просьбой» (размышления включались сами), а виджет говорил только «Модель отвечает долго — 307 с». Проверяем:
— служебные поручения (приветствие, утренняя сводка) — без размышлений; дело по расписанию — по самому делу;
— пока модель молчит, движок знает, чего ждём (сервер не ответил / размышляет / пишет действие / слова пошли);
— через WAIT_NOTE_SEC в строке состояния — что происходит и что сделать; с первым словом строка убирается;
— приветствие, на которое модель не ответила за GREET_LATE_SEC, отменяется — без «Думаю…» на минуты."""
import json, os, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_WORKSPACE=str(tmp / "ws"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"))
sys.path.insert(0, str(ROOT / "core"))
import llm  # noqa: E402
import presence  # noqa: E402
import engine_answer as EA  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def wait_for(cond, sec=10):
    end = time.time() + sec
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


# ── 1. размышления: служебное — нет, дело по расписанию — по самому делу ──
greet = presence.prompt({"kind": "back", "facts": ["Скоро: в 14:00 — Разобраться с этим."], "gone": "1 ч 43 мин"})
ok(llm.wants_think(greet), "приветствие длинное — раньше оно считалось «сложной просьбой»")
ok(not llm.wants_think(EA.think_ask(greet, True)), "служебное приветствие — без размышлений")
job = ("[Дело по расписанию] Поручение пользователя: «Сравни цены на гречку в трёх магазинах». Выполни его сам прямо сейчас — "
       "используй инструменты (поиск в интернете, чтение страниц, почта, заметки)…" + " подробности" * 40)
ok(EA.think_ask(job, True) == "Сравни цены на гречку в трёх магазинах" and llm.wants_think(EA.think_ask(job, True)),
   "дело по расписанию — решаем по самому делу («сравни» — подумать)")
ok(not llm.wants_think(EA.think_ask(job.replace("Сравни цены на гречку в трёх магазинах", "Курс доллара"), True)),
   "простое дело по расписанию — без размышлений, хоть поручение и длинное")
ok(EA.think_ask("Напиши стих про осень", False) == "Напиши стих про осень", "вопрос человека — как раньше")
src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("wants_think(think_ask(text, getattr(turn, \"raw\", False)))" in src and "turn.raw = raw" in src, "ход знает, что он служебный")

# ── 2. чего ждём: мок сервера — молчит, потом размышляет, потом отвечает ──
gate = {"head": threading.Event(), "think": threading.Event(), "talk": threading.Event()}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        gate["head"].wait(10)
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        self.wfile.write(("data: " + json.dumps({"choices": [{"delta": {"reasoning_content": "Хм, нужно подумать…"}}]}) + "\n\n").encode())
        self.wfile.flush()
        gate["think"].wait(10)
        self.wfile.write(("data: " + json.dumps({"choices": [{"delta": {"content": "Привет! С возвращением."}}]}, ensure_ascii=False) + "\n\n").encode())
        self.wfile.flush()
        gate["talk"].wait(10)
        self.wfile.write(b"data: [DONE]\n\n")


srv = ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
prof = {"kind": "openai", "base_url": f"http://127.0.0.1:{srv.server_port}/v1", "model": "m", "think": "on"}
cancel = threading.Event()
got = []
th = threading.Thread(target=lambda: got.extend(llm.stream_events(prof, "sys", [{"role": "user", "content": "Привет"}], cancel=cancel)))
th.start()
ok(wait_for(lambda: (llm.wait_info(cancel) or {}).get("phase") == "connect"), "запрос ушёл, сервер молчит — phase connect")
ok("Сервер модели ещё не ответил" in llm.wait_hint(25, llm.wait_info(cancel)) and "прокси" in llm.wait_hint(25, llm.wait_info(cancel)),
   "строка: сервер не ответил — проверить интернет и прокси")
gate["head"].set()
ok(wait_for(lambda: (llm.wait_info(cancel) or {}).get("reasoning", 0) > 0), f"сервер ответил, модель размышляет: {llm.wait_info(cancel)}")
h = llm.wait_hint(30, llm.wait_info(cancel), think_auto=True)
ok("обдумывает" in h and "Думать над сложными просьбами" in h and "30 с" in h, f"строка: модель обдумывает, как ускорить — {h}")
ok("без размышлений" in llm.wait_hint(30, llm.wait_info(cancel), think_auto=False), "размышляет сама модель — совет выбрать другую")
gate["think"].set()
ok(wait_for(lambda: (llm.wait_info(cancel) or {}).get("text")), "пошли слова — text")
gate["talk"].set(); th.join(10)
ok(llm.wait_info(cancel) is None and "".join(v for k, v in got if k == "text") == "Привет! С возвращением.", "ответ кончился — запись ожидания убрана")
ok("готовит действие" in llm.wait_hint(25, {"phase": "stream", "calls": True}) and "Выполняю действие" in llm.wait_hint(25, None)
   and "на этом компьютере" in llm.wait_hint(25, {"phase": "stream", "local": True})
   and "сервер на связи" in llm.wait_hint(25, {"phase": "stream"}), "строки для действия, своей модели и медленного облака")


# ── 3. движок: строка ожидания и опоздавшее приветствие ──
class Turn:
    def __init__(self, greet=False):
        self.cancel, self.full, self.via, self.via_job, self.greet, self.spoken = threading.Event(), "", None, False, greet, []


import engine_remote as ER  # noqa: E402  — _cancel_locked (отмена хода)


class Eng(EA.AnswerMixin, ER.RemoteMixin):
    WAIT_NOTE_SEC, GREET_LATE_SEC = 1.0, 2.5

    def __init__(self):
        self.status, self.notes, self.states, self._turn_lock = {"note": ""}, [], [], threading.RLock()
        self.turn, self.player, self.history, self.pending_confirm = None, None, [], None
        self.s = type("S", (), {"get": lambda *a: None})()

    def note(self, text):
        self.status["note"] = text; self.notes.append(text)

    def set_state(self, st): self.states.append(st)


e = Eng(); t = Turn(); e.turn = t
st = llm._wait_track(t.cancel, "https://dewiar.pro/dwrapp/cloud.php?p=", {"model": "chat"}, True)
w = threading.Thread(target=e._wait_watch, args=(t,)); w.start()
ok(wait_for(lambda: e.status["note"].startswith("Сервер модели ещё не ответил"), 5), f"через WAIT_NOTE_SEC — строка, чего ждём: {e.status['note']!r}")
t.full = "Привет!"
ok(wait_for(lambda: e.status["note"] == "", 4) and not w.join(3) and not w.is_alive(), "первое слово — строка убрана, сторож закончил")
llm._wait_untrack(t.cancel, st)

e2 = Eng(); g = Turn(greet=True); e2.turn = g
w2 = threading.Thread(target=e2._wait_watch, args=(g,)); w2.start()
ok(wait_for(lambda: g.cancel.is_set(), 6) and e2.turn is None and e2.states[-1:] == ["idle"], "приветствие без ответа дольше GREET_LATE_SEC — отменено, виджет не «думает»")
w2.join(3)
ok(e2.status["note"] == "", "после отмены строка ожидания убрана")

e3 = Eng(); v = Turn(); v.via = {"done": print}; e3.turn = v
w3 = threading.Thread(target=e3._wait_watch, args=(v,)); w3.start()
time.sleep(2.2); v.cancel.set(); w3.join(3)
ok(not e3.notes, "вопрос из мессенджера — без строки в виджете")

print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
os._exit(1 if fails else 0)
