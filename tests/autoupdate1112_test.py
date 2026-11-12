"""Пакет 11.11: 262 компьютера из 541 — на 0.84.2. Причина: вопрос «Обновить сейчас?» виджет задаёт только развёрнутым
(с автозапуском он в трее) и раз в 20 часов на минуту — его не видят. Теперь на Windows скачанное обновление ставится
само, когда человека 10 минут нет за компьютером (updater.auto_due → событие update_auto → виджет ставит), выключается
в студии («Ставить обновления самой»); Linux (пароль pkexec) — только по нажатию."""
import os, sys, tempfile, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import settings as SET  # noqa: E402
import updater as U  # noqa: E402

ok(SET.DEFAULTS["updates"].get("auto_install") is True, "по умолчанию — ставить самой")


class S:
    def __init__(self, v=None):
        self.v = v

    def get(self, sec, key):
        return self.v if (sec, key) == ("updates", "auto_install") else None


a = {"version": "0.90.0", "path": "/x/Dewiar-Setup-0.90.0.exe"}
I = U.AUTO_IDLE
ok(U.auto_due(S(), a, I + 1, win=True), "Windows, скачано, вас нет 10 минут, разговора нет — ставим")
ok(not U.auto_due(S(), a, I + 1, win=False), "Linux — нет (система спросит пароль)")
ok(not U.auto_due(S(False), a, I + 1, win=True), "выключено в студии — нет")
ok(not U.auto_due(S(), a, I - 5, win=True) and not U.auto_due(S(), a, None, win=True), "вы за компьютером (или не знаем) — нет")
ok(not U.auto_due(S(), {"version": "0.90.0"}, I + 1, win=True) and not U.auto_due(S(), None, I + 1, win=True), "ещё не скачано — нет")
ok(not U.auto_due(S(), a, I + 1, "speaking", win=True) and not U.auto_due(S(), a, I + 1, busy=True, win=True),
   "Лира говорит, идёт разговор, звенит будильник или созвон — нет")
ok(not U.auto_due(S(), a, I + 1, tasks_running=True, win=True) and U.auto_due(S(), a, 3 * I, tasks_running=True, win=True),
   "идёт фоновая задача — ждём втрое дольше")

# ядро: раз в минуту, одна версия — одно событие
import engine_music as EM  # noqa: E402
ev = []
U_WIN = U.WIN
U.WIN = True
eng = types.SimpleNamespace(updater=types.SimpleNamespace(available=dict(a)), s=S(), turn=None, alarm=None, meeting=False,
                            state="idle", tasks=types.SimpleNamespace(list=lambda: []),
                            emit=lambda t, **kw: ev.append((t, kw)))
tick = EM.MusicMixin._auto_update_tick if hasattr(EM, "MusicMixin") else next(
    getattr(c, "_auto_update_tick") for c in vars(EM).values() if isinstance(c, type) and hasattr(c, "_auto_update_tick"))
ok(tick(eng, I + 5) and ev == [("update_auto", {"version": "0.90.0", "path": a["path"]})], f"ядро шлёт update_auto: {ev}")
eng._auto_upd_t = 0
ok(not tick(eng, I + 5) and len(ev) == 1, "та же версия — второй раз не шлём")
eng._auto_upd_t, eng._auto_upd_ver = 0, ""
eng.state = "thinking"
ok(not tick(eng, I + 5), "Лира думает — не шлём")
U.WIN = U_WIN

hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
ok('core.on("update_auto"' in hud and 'window.t("hud.upd.auto"' in hud and '$("upd").onclick()' in hud.split('core.on("update_auto"')[1][:600],
   "виджет: на update_auto — говорит, что ставит, и ставит (как по нажатию)")
em = (ROOT / "core/engine_music.py").read_text(encoding="utf-8")
ok("self._auto_update_tick(idle)" in em, "проверка — в фоновом потоке присутствия (раз в 5 с, событие — не чаще раза в минуту)")
st = (ROOT / "ui/settings.html").read_text(encoding="utf-8")
ok('data-k="updates.auto_install"' in st and 'data-i18n="st.upd.auto"' in st, "в студии — переключатель «Ставить обновления самой»")
import json  # noqa: E402
for lang in ("ru", "en"):
    d = json.loads((ROOT / f"data/i18n/{lang}.json").read_text(encoding="utf-8"))
    ok(all(d.get(k) for k in ("hud.upd.auto", "st.upd.auto", "st.upd.auto.tip")) and "{v}" in d["hud.upd.auto"], f"строки — в словаре {lang}")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
