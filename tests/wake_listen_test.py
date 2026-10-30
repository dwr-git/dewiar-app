"""Слушание после имени. Ловит случаи из журнала разговора:
  «🎤 Имя «эва» услышано → 📝 Игрова. → Ложное срабатывание» (ассистент гаснет), «📝 Элла. → ❓ Элла.» (модель ищет «Элла»),
  «Фраза 22.4 с» под музыку (команда тонет), «Играй. → Играю.» (модель отвечает словами — тишина),
  радио на 5% после «тише» (кажется, что не играет).
Проверяем сами решения: короткая фраза с услышанным именем — это имя; фраза под музыкой начинается с имени;
радио молчит, пока слушаем; «играй» без плеера — последняя станция; тихое радио — так и говорим."""
import collections, os, queue, sys, threading, time
from pathlib import Path
from types import SimpleNamespace
import numpy as np
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
ok = lambda c, m: print(("✅ " if c else "❌ ") + m)
import engine as E  # noqa: E402
from radio import Radio  # noqa: E402

ALIASES = {"eva": ["эва"], "lira": ["лира"], "patrik": ["патрик"]}


def stub():
    e = E.Engine.__new__(E.Engine)
    e.calls = []
    e._said, e.state, e._spoke_until = collections.deque(maxlen=40), "listening", 0.0
    e.pending_confirm, e.task_answer_until = None, 0.0
    e.tasks = SimpleNamespace(waiting=lambda: None)
    e.aliases = ALIASES
    e.personas = SimpleNamespace(wake_map=lambda only=None, **k: {"эва": "eva", "лира": "lira", "патрик": "patrik"})
    e.s = SimpleNamespace(get=lambda *k, default=None: {"persona": "eva"}.get(k[0], default) if len(k) == 1 else default)
    e.follow_up_until = 0.0
    e._wake_phrase = ""
    e.switch_persona = lambda pid: e.calls.append(("persona", pid))
    e.listen_for_command = lambda seconds=8: e.calls.append(("listen",))
    e.ask = lambda t, **k: e.calls.append(("ask", t))
    e.go_sleep = lambda *a, **k: e.calls.append(("sleep",))
    e.set_state = lambda st: e.calls.append(("state", st))
    e.emit = lambda *a, **k: None
    e.tones = []
    e.play_tone = lambda k: e.tones.append(k)
    e._media_stop_word = lambda *a, **k: None
    e.note = lambda m: e.calls.append(("note",))
    return e


def run(text, by_wake, follow=False, dur=1.0, phrase="эва"):
    e = stub(); e._wake_phrase = phrase
    if follow:
        e.follow_up_until = time.monotonic() + 5
    E.Engine.handle_text(e, text, by_wake, follow, None, dur=dur)
    return e.calls


ok(run("Игрова.", True, dur=0.9) == [("listen",)], "«Эва» услышана, распознано «Игрова.» — слушаю вопрос, а не гасну")
ok(run("", True, dur=1.0) == [("listen",)], "распознавание вернуло пусто — тоже слушаю")
ok(run("Элла.", True, follow=True, dur=1.0) == [("listen",)], "«Элла.» во время ожидания — не вопрос модели, а имя")
ok(run("Ира.", True, dur=0.8, phrase="лира") == [("persona", "lira"), ("listen",)], "«Лира» → «Ира.»: переключаюсь на Лиру и слушаю")
r = run("Так что вот, в принципе, всё, что будем делать. Позвонили, всё, потом дальше", True, dur=9.2, phrase="агент")
ok(("listen",) not in r and ("state", "idle") in r, "длинный чужой разговор с «именем» — по-прежнему ложное срабатывание")
ok(run("Лира, включи радио", True, dur=1.8, phrase="лира") == [("persona", "lira"), ("ask", "включи радио")], "«Лира, включи радио» одной фразой — как раньше")
ok(run("Играй.", False, follow=True) == [("ask", "Играй.")], "после «слушаю» — «Играй.» идёт вопросом")
ok(run("Привет", False, follow=False) == [("state", "idle")], "без имени и не в ожидании — не отвечаем")
# люди рядом разговаривают (отчёт 11.10): длинная фраза без имени в «продолжении разговора» — не вопрос; «…Пауза.» — стоп
r = run("Я внутрь встроил ещё мессенджер безопасный, то есть, собственно, переписываться можно файлами, и звонить, и это всё "
        "работает через наш сервер, вот так", False, follow=True, dur=25.0)
ok(("ask",) not in [c[:1] for c in r] and ("state", "idle") in r, f"продолжение разговора: 25 с чужой речи без имени — не вопрос: {r}")
ok(run("То есть можно ещё пригласить людей? Так, думает. Вроде я её не вызывал. Пауза.", False, follow=True, dur=6.0) == [("sleep",)],
   "«…Вроде я её не вызывал. Пауза.» — это «стоп», а не вопрос")
# «засыпает на половине фразы» (отчёт 18.10): длинный вопрос сразу после ответа — с просьбой ко мне или с именем внутри
r = run("Хорошо, давай расскажи мне, что можно создать сейчас из приложений для Android и Apple, которые, допустим, "
        "пригодились бы людям и которые сейчас в тренде", False, follow=True, dur=12.4)
ok(r and r[-1][0] == "ask", f"длинная просьба ко мне («…расскажи мне…») в продолжении — вопрос, а не «разговор рядом»: {r}")
r = run("Я так и начал. Лира, расскажи мне что-нибудь о новых трендах для создания приложений для Android и Apple. Что сейчас "
        "в тренде? Что нужно людям, какие боли у людей?", True, follow=True, dur=15.3, phrase="лира")
ok(r and r[-1][0] == "ask", f"имя во втором предложении длинной фразы — вопрос: {r}")
r = run("Я внутрь встроил ещё мессенджер безопасный, то есть, собственно, переписываться можно файлами, и звонить, и это всё "
        "работает через наш сервер, вот так", False, follow=True, dur=25.0)
ok(("note",) in r, "чужую длинную фразу пропустила — один раз подсказала, как обратиться (не «уснула» молча)")
ok(run("А какая завтра погода?", False, follow=True, dur=2.0) == [("ask", "А какая завтра погода?")], "короткое продолжение — как раньше, вопросом")
# пакет 22.10, №182/№183 «пропадает, не дослушав вопрос»: позвали по имени («Лира» → «Слушаю») и задали длинный вопрос
# без повелительного глагола — это вопрос, а не «разговор рядом»
e7 = stub(); e7._invited_until = time.monotonic() + 30; e7.follow_up_until = time.monotonic() + 5
q = ("Мне интересно, как лучше устроить рабочее место дома, чтобы спина не уставала, у меня стол у окна, "
     "стул обычный офисный, а работаю я часов по десять")
E.Engine.handle_text(e7, q, False, True, None, dur=15.5)
ok(e7.calls and e7.calls[-1] == ("ask", q) and e7._invited_until == 0.0, f"вопрос после имени — даже длинный — вопрос: {e7.calls[-1:]}")
e8 = stub(); e8.follow_up_until = time.monotonic() + 5
E.Engine.handle_text(e8, q, False, True, None, dur=15.5)
ok(("ask", q) not in e8.calls, "та же фраза в обычном продолжении разговора (без «Слушаю») — по-прежнему не вопрос")
# 28.10 (отзыв: «зову „Лира“, начинаю говорить — через пару секунд молча отключается, примерно в 30 % случаев»):
# быстрый слух слышал имя в начале фразы, а точная модель его ослышала («Мира») или потеряла — это обращение


def run_off(text, off, dur=2.5, noisy=False):
    e = stub(); e._wake_phrase = "лира"; e._wake_off = off; e._noisy = lambda: noisy
    E.Engine.handle_text(e, text, True, False, None, dur=dur)
    return e.calls


ok(run_off("Мира, включи музыку", 0.1) == [("persona", "lira"), ("ask", "включи музыку")], "«Лира» в начале, распознано «Мира, …» — вопрос, а не молчаливое «отключилась»")
ok(run_off("Ирма, какая завтра погода", 0.3) == [("persona", "lira"), ("ask", "какая завтра погода")], "«Ирма, какая погода» — тоже")
ok(run_off("включи музыку", 0.2) == [("persona", "lira"), ("ask", "включи музыку")], "имя срезано, а это просьба — вопрос")
ok(("ask",) not in [c[:1] for c in run_off("Мира, включи музыку", 0.1, noisy=True)], "вокруг разговор — не гадаем (там имя проверяет точная модель)")
ok(("ask",) not in [c[:1] for c in run_off("Платформа открылась для мира, и теперь каждый может попробовать", 1.5, dur=4.5)], "«…открылась для мира» — по-прежнему не обращение")
ok(("ask",) not in [c[:1] for c in run_off("ну вот мы и приехали домой наконец-то", 0.2)], "имени нет и это не просьба — не вопрос")
ok(("ask",) not in [c[:1] for c in run_off("Мира, включи музыку", 3.5, dur=5.0)], "имя прозвучало не в начале — не гадаем")
from engine_base import to_me as _tm  # noqa: E402
ok(all(_tm(t) for t in ("Добавь в заметки молоко", "сохрани это", "удали последнюю заметку", "запусти таймер")), "«добавь», «сохрани», «удали», «запусти» — просьбы ко мне")
# «…открылась для мира» из видео (отчёт 11.10): быстрый слух принял «мира» за «Лиру» — фраза не вопрос, «мира» не имя
r = run("Платформа открылась для мира, и теперь каждый может попробовать", True, dur=4.5, phrase="лира")
ok(("ask",) not in [c[:1] for c in r] and ("state", "idle") in r, f"«…открылась для мира» — не обращение к Лире: {r}")
ok(run("Для мира.", True, dur=0.9, phrase="лира")[-1:] != [("ask", "Для мира.")], "«Для мира.» — тоже не вопрос")
from engine_base import find_name as _fn  # noqa: E402
_A = {"lira": ["лира"], "patrik": ["патрик"]}
ok([_fn(t, _A)[0] for t in ("для мира", "Тира", "Лира, привет", "лиру позови", "Ира, погода", "Батрик, привет")] == [None, None, "lira", "lira", "lira", "patrik"],
   "короткое имя: «мира», «тира» — нет; «Лира», «лиру», «Ира» — да; длинное «Батрик» — по-прежнему «Патрик»")
# «стоп» ослышан (отзыв 11.10: «Вы: Ctop.» → «Хорошо, я слушаю.») — всё равно стоп
r = {t: run(t, False, follow=True, dur=0.8) for t in ("Ctop.", "Сстоп!", "Стоб.", "Паузу.", "Pauza", "Стопп")}
ok(all(v == [("sleep",)] for v in r.values()), f"ослышанное «стоп/пауза» в продолжении разговора — сон: {r}")
ok(run("Лира, Ctop.", True, dur=1.0, phrase="лира") == [("persona", "lira"), ("sleep",)], "«Лира, Ctop.» — стоп")
ok(run("Стол.", False, follow=True, dur=0.8) == [("ask", "Стол.")] and run("Стопа болит", False, follow=True)[0][0] == "ask",
   "похожие, но другие слова («стол», «стопа болит») — не стоп")
from engine_base import is_sleep_phrase as _isp  # noqa: E402
ok(all(_isp(t) for t in ("Ctop.", "Хорошо, Ctop", "Пayзa", "хватить")) and not any(_isp(t) for t in ("Стол", "сто", "Топ")),
   "is_sleep_phrase: латиница и ослышки — стоп, «стол», «сто», «топ» — нет")
src = (ROOT / "core/engine_audio.py").read_text(encoding="utf-8")
ok('bool(lf.get("follow"))' in src and '"follow": follow}' in src, "склейка частей фразы не превращает фразу без имени в вопрос")

# --- цикл слушания: 20 с «музыки», которую детектор принимает за речь, и имя в конце ---
FR = E.FRAME
e = stub()
e.s = SimpleNamespace(get=lambda *k, default=None: {("audio", "end_silence_ms"): 650, ("audio", "barge_in"): "smart"}.get(k, default))
e.stopping, e.restart_audio, e.muted, e.state = threading.Event(), threading.Event(), False, "idle"
e.status, e.meeting, e.alarm, e.utt_id, e.wake_time = {"aec": True}, [], None, 0, 0.0
e._listen_peak = e._listen_vad = 0.0
e._pending_media_stop, e.check_q, e.stt_q = 0.0, queue.Queue(), queue.Queue()
e.radio = SimpleNamespace(playing=True)
e._meeting_ignores = lambda p: False
e._noisy = lambda: False
e.wake_checker = lambda: None
e._level = lambda *a: None
e.interrupt = lambda *a, **k: None
got = []
e._on_utterance = lambda pcm, t0, now: got.append(len(pcm) / 2 / 16000)
frames = int(20 / E.FRAME_S)
name_at = frames - int(0.4 / E.FRAME_S)                  # быстрый слух отозвался почти в конце 20 с
after = int(2.0 / E.FRAME_S)                             # потом радио замолчало: тишина
total = frames + after
state = {"i": 0}


def read():
    i = state["i"]; state["i"] += 1
    if i >= total:
        e.stopping.set()
        return b"\0" * (FR * 2)
    return (np.random.default_rng(i).normal(0, 2000, FR)).astype(np.int16).tobytes() if i < frames else b"\0" * (FR * 2)


e.capture = SimpleNamespace(read=read)
e.vad = SimpleNamespace(prob=lambda f: 0.9 if state["i"] <= frames else 0.05, reset=lambda: None)
e.spotter = SimpleNamespace(feed=lambda f: [("wake", "лира")] if state["i"] == name_at else [], rec=SimpleNamespace(Reset=lambda: None),
                            last_final=None)
e.set_state = lambda st: setattr(e, "state", st)
e.wav_input = None                 # не запись из файла — обычный микрофон
e._mic_ring = collections.deque(maxlen=40)
e._quiet_until = 0.0
e.hold = None
E.Engine._listen(e)
ok(len(got) == 1 and got[0] < 3.0, f"имя под музыку: фраза начинается с имени, а не тянется 20 с ({got[0] if got else '—':.1f} с)")
ok(e._wake_phrase == "лира" and e.state == "listening", "имя запомнено, ассистент слушает")
ok(e.tones == ["wake"], f"звук «слушаю» — сразу на имя, а не после распознавания фразы: {e.tones}")

# --- «стоп» поверх ответа: одно слово — замолчать и уснуть со звуком (а не 3 с «продолжения» для разговора рядом) ---
e4 = stub(); e4.stop_utt, e4._stop_sleep = True, True
E.Engine._on_utterance(e4, b"\0\0" * int(16000 * 0.8), 0.0, 1.0)
ok(e4.calls == [("sleep",)], f"короткое «стоп» поверх ответа — сон до имени: {e4.calls}")
e5 = stub(); e5.stop_utt, e5._stop_sleep = True, True
e5.prompter, e5.calib, e5.vosk_wake_check, e5.barge_sent, e5.barge_hit, e5.barge_speech, e5.utt_id = None, None, -1, -1, -1, -1, 1
e5.wake_time, e5.last_speak_end, e5.meeting, e5.status = 0.0, 0.0, [], {"aec": True}
try:
    E.Engine._on_utterance(e5, b"\0\0" * int(16000 * 2.5), 0.0, 1.0)
except Exception:  # noqa: BLE001 — дальше фраза идёт в распознавание; заглушке его не хватает — нам важно, что не уснули
    pass
ok(("sleep",) not in e5.calls and e5._stop_sleep is False, "«стоп, лучше расскажи…» (длинная фраза) — не сон, а вопрос")

# --- имя прозвучало, вопроса нет — звук «не слушаю» ---
e6 = stub(); e6._wake_tone_at = time.monotonic()
E.Engine.handle_text(e6, "Так что вот, в принципе, всё, что будем делать дальше, позвонили", True, False, None, dur=6.0)
ok(e6.tones == ["sleep"], f"звучало «слушаю», а вопроса не было — звук «не слушаю»: {e6.tones}")

# --- радио: молчит, пока слушаем и думаем; тихо под голосом; тише 10% не бывает ---
r = Radio(lambda: None, lambda: None)
seen = {}
e2 = stub(); e2.muted, e2.state, e2.radio = False, "idle", r
e2.emit = lambda *a, **k: None
for st in ("listening", "thinking", "speaking", "idle"):
    E.Engine.set_state(e2, st); seen[st] = r._duck
ok(seen == {"listening": 0.0, "thinking": 0.0, "speaking": 0.25, "idle": 1.0}, f"радио: слушаем/думаем — тишина, говорим — 25%, потом как было: {seen}")
r.set_volume(0.05)
ok(r.volume == 0.1, "громкость радио не опускается до неслышных 5%")

# --- «играй» ---
import tools as _tools  # noqa: E402
_tools.media_players = lambda: 0
e3 = stub()
e3.radio = SimpleNamespace(playing=False, paused=None, last={"name": "Радио Джаз", "url": "u1", "tags": "jazz"}, volume=0.8, station=None, sounding=True, last_at=0.0)
e3.music = SimpleNamespace(stations=lambda: [{"name": "Джаз 2", "url": "u2", "tags": "jazz"}, {"name": "Рок", "url": "u3", "tags": "rock"}],
                           genres=lambda: ["джаз", "рок"])
e3._music_service = lambda: "radio"
played = []
e3._play_station = lambda c, said, ph: played.append([x["name"] for x in c])
e3._say_quick = lambda m, s, via=None: played.append(m)
e3._music_asked = 0.0
ok(E.Engine._music_cmd(e3, "Играй") is True and played and played[0][0] == "Радио Джаз" and played[0][1] == "Джаз 2",
   f"«Играй» без плеера — снова последняя станция (запасные — того же жанра): {played[:1]}")
played.clear(); e3.radio.last = None
ok(E.Engine._music_cmd(e3, "Играй") is True and "Что включить" in played[0], "ничего ещё не играло — спрашиваю, что включить")
played.clear(); e3.radio = SimpleNamespace(playing=True, paused=None, last=None, volume=0.1, station={"name": "Медляк FM"}, sounding=True, last_at=0.0)
ok(E.Engine._music_cmd(e3, "Играй") is True and "тихо" in played[0] and "10%" in played[0], f"радио играет на 10% — так и говорю: {played[0]}")
# жалоба №404 (29.10: «засыпает, прерывая разговор»): посреди длинной фразы быстрый слух принял «схватит» за «хватит» —
# слово-стоп посреди речи не усыпляет (решает точное распознавание в конце фразы); «схватит» и родня — в «приманках»
import engine_audio as EA  # noqa: E402
ok(EA.stop_mid_phrase(True, 4.0) and not EA.stop_mid_phrase(True, 0.8) and not EA.stop_mid_phrase(False, 6.0),
   "№404: «хватит» посреди длинной фразы — не сон; одно короткое «хватит» — сон")
_dec = set((ROOT / "data/decoys.txt").read_text(encoding="utf-8").split())
ok({"схватит", "захватит", "подхватит", "хватает"} <= _dec and "хватит" not in _dec, "№404: «схватит», «захватит», «хватает» — приманки быстрого слуха, «хватит» — нет")
