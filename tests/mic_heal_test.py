"""Микрофон после OBS (отзыв 17.10: «OBS уже выключил, но она меня не слышит» и подсказка «Микрофон молчит — Микрофон
молчит — … в студии → «Слух»»). Поток микрофона остался открытым, но шли одни нули. Теперь: нули 5 с — ядро само
переоткрывает микрофон и эхоподавление (не чаще раза в 2 минуты); не помогло — через 15 с подсказка, и ведёт она туда,
где выбирают микрофон («Звук и поведение»), а заголовок уведомления не повторяется в тексте."""
import os, sys, threading, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine  # noqa: E402
import engine_audio  # noqa: E402
E = engine.Engine
told, pushed = [], []
stub = types.SimpleNamespace(state="idle", hold=None, restart_audio=threading.Event(), note=lambda t: told.append(t),
                             push=lambda title, text, **k: pushed.append((title, text)), report_problem=lambda *a: None,
                             s=types.SimpleNamespace(get=lambda *k: ""))
stub._mic_silent = lambda exact=True: E._mic_silent(stub, exact)
engine_audio.list_devices = lambda: [{"name": "real", "description": "Встроенный микрофон", "kind": "source"}]
zero, voice = b"\x00" * 1024, (b"\x10\x05" * 512)
st = {"since": None, "told": False, "all": True}
acts = [E._mic_zero_step(stub, st, zero, t / 10) for t in range(0, 70)]          # 7 с нулей
ok("heal" in acts and acts.index("heal") in range(50, 62) and stub.restart_audio.is_set() and not told,
   f"нули 5 с — сами переоткрываем микрофон, человеку пока ничего не говорим: шаг {acts.index('heal') if 'heal' in acts else None}")
stub.restart_audio.clear()
# не во время ответа, разговора или диктовки (вопрос 17.10: «не будет ли проблемой в тех же диктовках?»)
for state, hold in (("speaking", None), ("thinking", None), ("listening", None), ("idle", {"pcm": []})):
    s2 = types.SimpleNamespace(**vars(stub)); s2.state, s2.hold, s2._zero_heal_at = state, hold, -1e9
    s2._mic_silent = lambda exact=True: None
    st2 = {"since": None, "told": False, "all": True}
    a2 = [E._mic_zero_step(s2, st2, zero, t / 10) for t in range(0, 70)]
    ok("heal" not in a2 and not s2.restart_audio.is_set(), f"{state}{' + диктовка' if hold else ''} — микрофон не переоткрываем")
# в тихой комнате живой микрофон шумит (пик 4–40) — это не нули: не переоткрываем и не жалуемся
quiet = (b"\x06\x00\xfb\xff" * 256)
st3 = {"since": None, "told": False, "all": True}; s3 = types.SimpleNamespace(**vars(stub)); s3._zero_heal_at = -1e9
s3._mic_silent = lambda exact=True: told.append("SILENT")
n0 = len(told)
a3 = [E._mic_zero_step(s3, st3, quiet, t / 10) for t in range(0, 600)]               # минута тишины в комнате
ok("heal" not in a3 and len(told) == n0, "минута тишины в комнате (живой шум) — ничего не переоткрываем и не говорим")
st = {"since": None, "told": False, "all": True}                                   # новый поток — снова нули
acts = [E._mic_zero_step(stub, st, zero, 7 + t / 10) for t in range(0, 170)]
ok("heal" not in acts and told and pushed, "второй раз за 2 минуты не переоткрываем — через 15 с подсказка")
ok("«Звук и поведение» → «Микрофон»" in told[-1] and "«Слух»" not in told[-1], f"подсказка ведёт туда, где выбирают микрофон: {told[-1][:90]}")
ok(pushed[-1][0] == "Микрофон молчит" and not pushed[-1][1].startswith("Микрофон молчит"), f"в уведомлении заголовок не повторяется: {pushed[-1]}")
E._mic_zero_step(stub, st, voice, 30)
ok(told[-1] == "" and st["since"] is None, "голос появился — подсказка убрана")
# №370 (28.10, Linux Mint, веб-камера C920): эхоподавление отдаёт нули и после переоткрытия — второй раз слушаем
# микрофон напрямую, без эхоподавления (до перезапуска программы), и говорим об этом
s5 = types.SimpleNamespace(**vars(stub)); s5._zero_heal_at, s5._zero_heals = -1e9, 0; s5.status = {"aec": True, "headphones": False}
s5.restart_audio = threading.Event(); s5._mic_silent = lambda exact=True: None
n0 = len(told)
st5 = {"since": None, "told": False, "all": True}
a5 = [E._mic_zero_step(s5, st5, zero, t / 10) for t in range(0, 70)]
ok("heal" in a5 and not getattr(s5, "_aec_bypass", False) and len(told) == n0, "первые нули — просто переоткрываем, эхоподавление остаётся")
st5 = {"since": None, "told": False, "all": True}
a5 = [E._mic_zero_step(s5, st5, zero, 200 + t / 10) for t in range(0, 70)]
ok("heal" in a5 and getattr(s5, "_aec_bypass", False) and "напрямую" in told[-1], f"нули снова — микрофон напрямую, без эхоподавления: {told[-1][:70]}")
ok('not getattr(self, "_aec_bypass", False) and self.aec.setup' in (ROOT / "core/engine_audio.py").read_text(encoding="utf-8"),
   "при переоткрытии эхоподавление пропускается")
src = (ROOT / "core/engine_audio.py").read_text(encoding="utf-8")
ok('self._mic_zero_step(zst, frame, now) == "heal"' in src, "главный цикл слуха проверяет каждый кадр этим шагом")
# «почти тишина» (пик ≤ 3, не нули) — массив микрофонов AMD с шумоподавлением в тихой комнате (№136, 20.10): тревога
# и автоотчёт после каждого перезапуска, а микрофон работал. Теперь: подсказка только через минуту; микрофон в этом запуске
# уже слышал — без уведомления и отчёта; не чаще раза в полчаса и после перезапуска (время в настройках)
cfg = {}
reported = []
s4 = types.SimpleNamespace(**vars(stub)); s4._zero_heal_at = -1e9
s4.report_problem = lambda *a: reported.append(a)
s4.s = types.SimpleNamespace(get=lambda *k: cfg.get(k[-1], ""), update=lambda p: cfg.update(p.get("audio", {})))
s4._mic_silent = lambda exact=True: E._mic_silent(s4, exact)
tiny = (b"\x02\x00\xfe\xff" * 256)
st4 = {"since": None, "told": False, "all": True}
n0, p0 = len(told), len(pushed)
[E._mic_zero_step(s4, st4, voice, t / 10) for t in range(0, 5)]                       # сначала слышал голос
[E._mic_zero_step(s4, st4, tiny, 1 + t / 10) for t in range(0, 300)]                  # 30 с «почти тишины»
ok(len(told) == n0, "почти тишина 30 с — ещё ничего не говорим (раньше — через 15 с)")
[E._mic_zero_step(s4, st4, tiny, 31 + t / 10) for t in range(0, 400)]                 # больше минуты
ok(len(told) == n0 + 1 and len(pushed) == p0 and not reported and cfg.get("mic_hint_at"),
   f"минута почти тишины, а микрофон уже слышал — только подсказка, без уведомления и отчёта: {len(told) - n0}, {len(pushed) - p0}, {reported}")
s5 = types.SimpleNamespace(**vars(s4)); s5._mic_alive = False
E._mic_silent(s5, False)
ok(len(told) == n0 + 1, "после перезапуска в те же полчаса — тишина (время подсказки — в настройках)")
cfg["mic_hint_at"] = 0
E._mic_silent(s5, False)
ok(len(pushed) == p0 + 1 and reported, "микрофон ни разу не слышал с запуска — подсказка, уведомление и отчёт, как раньше")
print("\nИТОГ:", "всё прошло" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
