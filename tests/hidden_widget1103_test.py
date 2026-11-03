"""№512 (ПК 0.79, Windows 11, 03.11): «Dewiar не запускается (диагностика)». По журналу ядро и виджет работали: ui.pid
живой, в ui.log раз за разом «студия: открыть»; в 22:22 восстановлен слепок (с другого компьютера), ядро перезапустилось,
дальше раз в минуту «Telegram: этого бота уже слушает другая программа (или второй Dewiar)».
Что сделано:
(а) восстановление слепка с другого компьютера не переносит положение виджета (hud_x, hud_y) — остаётся этого компьютера;
(б) повторный запуск ярлыка на Windows не только будит интерфейс: виджет — на видимом месте рабочей области и поверх окон
    (bring_back; раньше на Windows он ничего не делал), и в ui.log видно «повторный запуск: показать виджет»;
(в) свой бот, который слушает и другой компьютер (409 дольше минуты), — один раз человеку «Этого бота слушает другой ваш
    компьютер — бот отвечает оттуда», дальше опрос раз в 10 минут, без записи в журнал каждую минуту."""
import json, logging, os, sys, tempfile, threading, time
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


# ---------- (а) слепок с другого компьютера: место виджета — своё ----------
import backup as B  # noqa: E402
cfg = tmp / "bcfg"; cfg.mkdir()
(cfg / "settings.json").write_text(json.dumps({"ui": {"hud_x": 3200, "hud_y": 1500, "zoom": 1.1}, "audio": {"input": "Чужой микрофон"}},
                                              ensure_ascii=False), encoding="utf-8")
bk = B.Backup.__new__(B.Backup)
bk.cfg = cfg
bk._fix_paths(other=True, here={"ui": {"hud_x": 900, "hud_y": 500}})
s = json.loads((cfg / "settings.json").read_text(encoding="utf-8"))
ok(s["ui"]["hud_x"] == 900 and s["ui"]["hud_y"] == 500 and s["ui"]["zoom"] == 1.1 and s["audio"]["input"] == "",
   f"слепок с другого компьютера: место виджета — этого компьютера, остальное из слепка: {s}")
(cfg / "settings.json").write_text(json.dumps({"ui": {"hud_x": 3200, "hud_y": 1500}}), encoding="utf-8")
bk._fix_paths(other=True, here={"ui": {}})
s = json.loads((cfg / "settings.json").read_text(encoding="utf-8"))
ok(s["ui"].get("hud_x") is None and s["ui"].get("hud_y") is None, "здесь места не было — встанет в угол по умолчанию, а не на чужой экран")
(cfg / "settings.json").write_text(json.dumps({"ui": {"hud_x": 3200, "hud_y": 1500}}), encoding="utf-8")
bk._fix_paths(other=False, here={"ui": {"hud_x": 1, "hud_y": 2}})
ok(json.loads((cfg / "settings.json").read_text(encoding="utf-8"))["ui"]["hud_x"] == 3200, "свой же слепок — место из слепка")

# ---------- (б) повторный запуск на Windows: виджет на видимое место ----------
src = (ROOT / "ui/app.py").read_text(encoding="utf-8")
i = src.index("    def bring_back(self):")
bb = src[i:i + 2400]
ok("if WIN:\n            h = self._hwnd(self.mode)" in bb and "winshell.clamp(h, x, y, w, hh)" in bb and "winshell.raise_top(h)" in bb
   and "winshell.move(h, nx, ny)" in bb, "Windows: bring_back ставит виджет в рабочую область ближайшего монитора и поверх окон")
w = src[src.index("def main_win"):]
w = w[w.index("def watch():"):w.index("def remember_fail")]
ok("api.from_tray()\n                    api.bring_back()" in w and "повторный запуск: показать виджет" in w,
   "сигнал «покажись» (повторный запуск ярлыка) — и виджет на видное место, и запись в ui.log")
sys.path.insert(0, str(ROOT / "ui"))
os.environ.setdefault("DEWIAR_NO_GTK", "1")
try:
    import app as UI  # noqa: E402
    ok(UI.fit_visible(3200, 1500, 360, 220, lambda: (1540, 820)) == (1540, 820), "за краем экрана — на место, которое дал монитор")
    ok(UI.fit_visible(-32000, -32000, 360, 220, lambda: 1 / 0) == (0, 0), "сбой определения монитора — хотя бы в левый верхний угол")
except Exception as e:  # noqa: BLE001 — без GTK интерфейс на этой машине не импортируется: проверяем исходник
    ok("def fit_visible(x, y, w, h, clamp):" in src, f"fit_visible есть (импорт интерфейса: {e})")

# ---------- (в) 409 дольше минуты: сказать один раз и опрашивать редко ----------
import telegram as T  # noqa: E402
got, recs = [], []


class Cap(logging.Handler):
    def emit(self, r):
        recs.append(r.getMessage())


logging.getLogger("dewiar.telegram").addHandler(Cap())
logging.getLogger("dewiar.telegram").setLevel(logging.INFO)
t = T.Telegram(on_message=lambda k, d: got.append((k, d)), path=tmp / "tg.json")
t.data = {"token": "123456789:" + "A" * 35, "owner": {"id": 1, "chat": 1}}


class R:
    status_code = 409

    def json(self):
        return {"ok": False, "error_code": 409, "description": "Conflict: terminated by other getUpdates request"}


t._http = lambda *a, **k: R()
try:
    t._get_updates()
    ok(False, "409 — ошибка")
except T.TelegramConflict as e:
    ok("другая программа" in str(e), "409 своего бота — TelegramConflict")
ok(t._conflict_hit(now=1000.0) is False and t._conflict_hit(now=1030.0) is False and got == [], "первую минуту — как раньше, без сообщения")
ok(t._conflict_hit(now=1061.0) is True and got == [("conflict", {"text": T.CONFLICT_SAY})], "дольше минуты — один раз «слушает другой компьютер»")
ok(t._conflict_hit(now=1700.0) is True and len(got) == 1, "дальше — молча")
ok(t._conflict_gone(now=1800.0) is False, "409 был недавно — по-прежнему редко")
ok(t._conflict_gone(now=1700.0 + 2 * t.CONFLICT_RARE + 1) is True and not t._c_said, "давно без 409 — снова отвечаем отсюда")
# настоящий поток приёма: 409 всё время — сообщение одно, запросов мало, в журнале не каждую попытку
t2 = T.Telegram(on_message=lambda k, d: got.append(("t2", k)), path=tmp / "tg2.json")
t2.data = dict(t.data)
calls = []


def http(*a, **k):
    calls.append(time.monotonic())
    return R()


t2._http = http
t2.CONFLICT_AFTER, t2.CONFLICT_RARE = 0.5, 1.5
recs.clear()
t2.start()
time.sleep(4.2)
t2.stop()
said = [x for x in got if x[0] == "t2"]
gaps = [b - a for a, b in zip(calls, calls[1:])]
ok(said == [("t2", "conflict")], f"поток приёма: сказано один раз ({said})")
ok(t2.problem == T.CONFLICT_SAY, f"в студии — понятная причина: {t2.problem}")
ok(gaps and max(gaps) >= 1.4 and len(calls) <= 6, f"после минуты конфликта — редкие запросы: {len(calls)} за 4 с, паузы {[round(g, 1) for g in gaps]}")
ok(sum(1 for m in recs if "другой ваш компьютер" in m) == 1, f"в журнале — одна запись о втором компьютере: {recs}")
eng = (ROOT / "core/engine_remote.py").read_text(encoding="utf-8")
ok('if kind == "conflict":' in eng and "self.push(tg.TITLE" in eng, "ядро показывает это человеку уведомлением")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
