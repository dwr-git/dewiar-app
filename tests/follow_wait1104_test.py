"""№514 (пакет 04.11, компьютер 0.80.0): «быстрая потеря связи — не успеваешь сказать больше 3 предложений, или говоришь,
а она отключается… можно 30 с пауза и тишина — тогда выкл, или 15». Журнал: «Продолжение разговора: длинная фраза без
имени (11.9 с, 34 слов) — похоже, говорят не со мной» на «Смотри, я делал систему лично под себя…» и то же на 9.8 с
«Смотри, смотри, я говорю тебе…»; окно «говорить без имени» — 8 с.
Теперь: «Сколько ждать, пока я молчу» (8/15/30 с) в «Слухе», по умолчанию 15 (и после имени тоже); обращение ко мне
(«смотри», «слушай», «тебе») — моё при любой длине, порог «разговора рядом» — 12 с / 32 слова; в долгой речи пауза конца
фразы длиннее, а склейка после долгой фразы ждёт продолжения до 1,5 с."""
import collections, json, os, sys, tempfile, time
from pathlib import Path
from types import SimpleNamespace
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_WORKSPACE=str(tmp / "ws"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import settings  # noqa: E402
import engine as E  # noqa: E402
from engine_base import addressed, to_me, FOLLOW_MAX_S, FOLLOW_MAX_WORDS, FRAME_S, LONG_SPEECH  # noqa: E402

# 1) сколько ждать: по умолчанию 15, прежние 8 по умолчанию — переводим один раз, выбор человека не трогаем
ok(settings.DEFAULTS["audio"]["follow_up_seconds"] == 15, "по умолчанию ждём 15 с, а не 8")
cases = [({"follow_up_seconds": 8}, 15, "прежние 8 с по умолчанию → 15"),
         ({"follow_up_seconds": 8, "follow_v2": True}, 8, "8 с, выбранные после перевода, — не трогаем"),
         ({"follow_up_seconds": 30}, 30, "30 с — выбор человека, не трогаем"),
         ({}, 15, "ничего не было — 15")]
for i, (au, want, msg) in enumerate(cases):
    p = tmp / "cfg" / f"m{i}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"audio": au}), encoding="utf-8")
    s = settings.Settings(p)
    ok(s.get("audio", "follow_up_seconds") == want and s.get("audio", "follow_v2") is True, f"{msg}: {s.get('audio', 'follow_up_seconds')}")

# 2) обращение ко мне — фразы из журнала №514
for t in ("Смотри, я делал систему лично под себя, то бишь раг плюс этот самый, как он там, ChromaDB. Я делал её чисто для того, "
          "чтоб работать на компе с сознанием того, что я уже забыл.",
          "Смотри, смотри, я говорю тебе, я не могу не успеть сказать тебе два предложения, три предложения, а ты чик-чик и отключилась.",
          "Слушай, а можно я расскажу подробнее, как всё было, с самого начала и по порядку",
          "Представь, что у тебя есть сад и в нём растут яблони и груши, а рядом течёт река"):
    ok(addressed(t), f"обращение ко мне: «{t[:40]}…»")
# рецензия 0.82 (жалоба 11.10 «вклинивается в беседу»): «знаешь», «понимаешь», «тебе», «подожди» — люди так говорят и друг другу
for t in ("Ты знаешь, вчера мы с Машей ходили в парк, и там было столько людей, я тебе говорю, яблоку негде упасть",
          "Понимаешь, он опять опоздал, и мы ждали его минут сорок у входа в кинотеатр",
          "Подожди, я тебе сейчас всё объясню, только дай договорить про нашу поездку",
          "Ну а он мне потом говорит: слушай, давай уйдём отсюда пораньше"):
    ok(not addressed(t), f"разговор людей, не мне: «{t[:40]}…»")
ok(addressed("Я даю тебе все карт-бланши. То бишь ты можешь заходить куда хочешь, на диске F, как хочешь, без всяких вопросов")
   and addressed("Разрешаю тебе заходить в папку проектов без вопросов, и в почту тоже, когда нужно"),
   "сам журнал №514: «Я даю тебе все карт-бланши…» — разрешение мне в начале фразы — моё")
ok(not addressed("Ну мы вчера с ним ходили туда и там было очень много людей а потом") and
   not addressed("Мне интересно, как лучше устроить рабочее место дома, чтобы спина не уставала"), "разговор рядом без обращения — не мне")
ok(addressed("Хорошо, давай расскажи мне, что можно создать") and to_me("Хорошо, давай расскажи мне, что можно создать"),
   "просьба (to_me) — по-прежнему обращение")
ok(FOLLOW_MAX_S >= 12 and FOLLOW_MAX_WORDS >= 32, f"порог «разговора рядом» — {FOLLOW_MAX_S} с / {FOLLOW_MAX_WORDS} слов")


def stub(follow_s=15):
    e = E.Engine.__new__(E.Engine)
    e.calls = []
    e._said, e.state, e._spoke_until = collections.deque(maxlen=40), "listening", 0.0
    e.pending_confirm, e.task_answer_until = None, 0.0
    e.tasks = SimpleNamespace(waiting=lambda: None)
    e.aliases = {"lira": ["лира"]}
    e.personas = SimpleNamespace(wake_map=lambda only=None, **k: {"лира": "lira"})
    conf = {"persona": "lira", ("audio", "follow_up_seconds"): follow_s}
    e.s = SimpleNamespace(get=lambda *k, default=None: conf.get(k[0] if len(k) == 1 else k, default))
    e.follow_up_until = time.monotonic() + 5
    e._wake_phrase = ""
    e.switch_persona = lambda pid: e.calls.append(("persona", pid))
    e.ask = lambda t, **k: e.calls.append(("ask", t))
    e.go_sleep = lambda *a, **k: e.calls.append(("sleep",))
    e.set_state = lambda st: e.calls.append(("state", st))
    e.emit = lambda *a, **k: None
    e.play_tone = lambda k: None
    e._media_stop_word = lambda *a, **k: None
    e.note = lambda m: e.calls.append(("note",))
    return e


# 3) продолжение разговора: фразы из журнала — вопрос, а не «говорят не со мной»
for text, dur in (("Смотри, я делал систему лично под себя, то бишь раг плюс этот самый, как он там, ChromaDB. Я делал её чисто для того, "
                   "чтоб работать на компе с сознанием того, что я уже забыл.", 11.9),
                  ("Смотри, смотри, я говорю тебе, я не могу не успеть сказать тебе два предложения, три предложения, а ты чик-чик и отключилась.", 9.8),
                  ("Потом я много дам тебе данных о себе, о своих проектах, и тогда мы начнём настоящую работу над памятью", 10.5)):
    e = stub()
    E.Engine.handle_text(e, text, False, True, None, dur=dur)
    ok(e.calls and e.calls[-1] == ("ask", text), f"{dur} с в продолжении разговора — вопрос: {e.calls[-1:]}")
q = ("Я внутрь встроил ещё мессенджер безопасный, то есть, собственно, переписываться можно файлами, и звонить, и это всё "
     "работает через наш сервер, вот так")
e = stub()
E.Engine.handle_text(e, q, False, True, None, dur=25.0)
ok(("state", "idle") in e.calls and not any(c[0] == "ask" for c in e.calls), "25 с чужого рассказа без обращения — по-прежнему не вопрос (отчёт 11.10)")

# 4) после имени ждём столько же, сколько выбрано («Сколько ждать, пока я молчу»), но не меньше 8 с
for want, conf in ((30, 30), (15, 15), (8, 0)):
    e = stub(conf)
    e._listen_peak = e._listen_vad = 0.0
    e._wake_tone_at = time.monotonic()
    E.Engine.listen_for_command(e)
    left = e.follow_up_until - time.monotonic()
    ok(want - 1 < left <= want, f"после имени — ждём {want} с (выбрано {conf}): {left:.1f}")
cmd = (ROOT / "core/engine_commands.py").read_text(encoding="utf-8")
ok("self.listen_for_command(8)" not in cmd, "кнопка микрофона тоже ждёт, сколько выбрано")

# 5) долгая речь: пауза конца фразы длиннее; склейка после долгой фразы — до 1,5 с
e = stub()
e._end_frames = 20
ok(E.Engine._end_need(e, 1.5) == 20, "короткая команда — пауза как раньше (быстрый ответ)")
ok(E.Engine._end_need(e, 5.0) == 20 + int(LONG_SPEECH[1][1] / FRAME_S), "говорят 5 с — ждём дольше")
ok(E.Engine._end_need(e, 12.0) == 20 + int(LONG_SPEECH[0][1] / FRAME_S), "говорят 12 с — ещё дольше")
ea = (ROOT / "core/engine_audio.py").read_text(encoding="utf-8")
ok("silence >= self._end_need(len(utt) * FRAME_S)" in ea, "конец фразы считается с учётом того, сколько уже говорят")
learned = []
e = stub()
e.state, e.utt_id = "thinking", 7
e.s = SimpleNamespace(get=lambda *k, default=None: {("audio", "end_silence_auto"): False}.get(k, default), update=lambda p: learned.append(p))
now = time.monotonic()
e._last_final = {"t": now, "pcm": b"\0" * (2 * 16000 * 9)}
E.Engine._pause_check(e, now + 1.2)
ok(e._last_final.get("cut") == 7, "после 9 с речи продолжили через 1,2 с — склеиваю, а не отвечаю на половину")
e._last_final = {"t": now, "pcm": b"\0" * (2 * 16000 * 2)}
E.Engine._pause_check(e, now + 1.2)
ok(not e._last_final.get("cut"), "после короткой команды 1,2 с — уже новая фраза (как раньше)")

# 6) студия: «Сколько ждать, пока я молчу» в «Слухе»
html = (ROOT / "ui/settings.html").read_text(encoding="utf-8")
ears = html[html.index('id="p-ears"'):html.index('id="sttstat"')]
ok("Сколько ждать, пока я молчу" in ears and all(f'<option value="{v}">' in ears for v in (8, 15, 30)), "в «Слухе» — выбор 8 / 15 / 30 с")
js = (ROOT / "ui/studio/brain.js").read_text(encoding="utf-8")
ok('save({ audio: { follow_up_seconds: +$("#follow-sel").value } })' in js, "выбор сохраняется числом")
print("ИТОГ:", "OK" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
