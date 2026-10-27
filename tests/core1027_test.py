"""Мелкие исправления ядра по пакету 27.10:
— №267/№302: на Windows долгая команда run_command — понятный ответ, а не исключение и автоотчёт;
— №266: модель добавляет платёж, который уже есть, — «уже есть, обновлено», а не трассировка;
— №269: антивирус держит settings.json — настройки сохраняются со второй-третьей попытки;
— №324: «no credits remaining» (OpenAI/OpenRouter) — «закончились деньги», а не «модель не отвечает»;
— «Server disconnected without sending a response» и шаблон jinja в LM Studio (№281) — по-русски, с советом;
— №332: macOS — «macOS», а не «Linux»;  №311: в отчёте max_tokens не прячется звёздочками;
— №309: папка ассистента — один и тот же (раскрытый) путь, relative_to не падает."""
import os, subprocess, sys, tempfile, types
from pathlib import Path
from unittest import mock
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_WORKSPACE=str(tmp / "ws"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import tools  # noqa: E402
fake = types.SimpleNamespace(shell=lambda *a, **k: (_ for _ in ()).throw(subprocess.TimeoutExpired("powershell", 30)))
with mock.patch.object(tools, "WIN", True), mock.patch.object(tools, "winsys", fake, create=True), \
        mock.patch.dict(os.environ, {"DEWIAR_DRY_TOOLS": ""}):
    try:
        r = tools.t_run_command({"command": "Get-ChildItem Z:\\ -Recurse"}, {})
    except subprocess.TimeoutExpired:
        r = "ИСКЛЮЧЕНИЕ"
ok("не закончилась за 30 с" in str(r), f"Windows: долгая команда — понятный ответ: {str(r)[:70]!r}")

import payments, engine_pay  # noqa: E402,E401
pm = payments.Payments(tmp / "st" / "payments.json") if "Payments" in dir(payments) else None
if pm is not None:
    eng = types.SimpleNamespace(payments=pm, emit=lambda *a, **k: None, pay=pm)
    first = engine_pay.t_payments({"action": "add_bill", "name": "Ипотека", "day": 5}, {"engine": eng}) if hasattr(engine_pay, "t_payments") else None
    try:
        second = engine_pay.t_payments({"action": "add_bill", "name": "ипотека", "amount": 450}, {"engine": eng})
    except Exception as e:  # noqa: BLE001
        second = "ИСКЛЮЧЕНИЕ " + str(e)
    ok("уже есть" in str(second) and sum(1 for b in pm.bills if b["name"] == "Ипотека") == 1, f"повторный платёж — «уже есть», один: {second!r}")
    ok(next(b for b in pm.bills if b["name"] == "Ипотека").get("amount") == 450, "названная сумма — обновлена")
else:
    ok(False, "нет класса Payments")

import settings  # noqa: E402
st = settings.Settings(tmp / "cfg" / "settings.json")
real = Path.replace
n = {"k": 0}
def flaky(self, target):
    if self.name == "settings.json.tmp" and n["k"] < 2:
        n["k"] += 1; raise PermissionError(5, "Отказано в доступе")
    return real(self, target)
with mock.patch.object(Path, "replace", flaky):
    st.update({"ui": {"zoom": 1.1}})
ok(n["k"] == 2 and settings.Settings(tmp / "cfg" / "settings.json").get("ui", "zoom") == 1.1, "файл занят антивирусом — сохранилось с третьей попытки")
with mock.patch.object(settings.sys if hasattr(settings, "sys") else sys, "platform", "darwin"), mock.patch.object(settings, "WIN", False):
    ok(settings._os_name().startswith("macOS"), f"Mac — «macOS»: {settings._os_name()!r}")

import llm, httpx  # noqa: E402,E401
ok(llm.NO_MONEY_RX.search("You have no credits remaining. Add credits") is not None, "«no credits remaining» — нет денег")
t = llm._humanize(httpx.RemoteProtocolError("Server disconnected without sending a response."), "https://dewiar.pro/x")
ok("оборвал связь" in t and "Server" not in t, f"разрыв — по-русски: {t!r}")
class R:  # ответ 400 с ошибкой шаблона LM Studio
    status_code = 400; text = '{"error":"Error rendering prompt with jinja template: No user query found in messages."}'
    def json(self): return {"error": "Error rendering prompt with jinja template: No user query found in messages."}
e = httpx.HTTPStatusError("400", request=httpx.Request("POST", "http://127.0.0.1:1234/v1/chat/completions"), response=httpx.Response(400, text=R.text))
t = llm._humanize(e, "http://127.0.0.1:1234/v1", "m")
ok("шаблон" in t and "lmstudio-community" in t, f"jinja — подсказка про шаблон: {t[:80]!r}")

src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
import re  # noqa: E402
rx = re.search(r'secret = re.compile\(r"([^"]+)", re.I\)', src).group(1)
sec = re.compile(rx, re.I)
ok(not sec.search("max_tokens") and sec.search("api_key") and sec.search("token") and sec.search("tg_token"), "отчёт: max_tokens виден, ключи — нет")

import workspace  # noqa: E402
ws = workspace.Workspace(None)
p = ws.safe("Заметки/x.md")
ok(p.relative_to(ws.root).as_posix() == "Заметки/x.md", "путь в папке ассистента — относительно того же корня")
# №301: DeepSeek пишет вызовы языком DSML — разбираем, как <tool_call>, даже если тег разрезан между кусками
t = llm.ToolTagStripper(); t.known = {"weather"}
txt = ('Сейчас узнаю.<｜DSML｜function_calls>\n<｜DSML｜invoke name="weather">\n<｜DSML｜parameter name="city" string="true">Москва'
       '</｜DSML｜parameter>\n<｜DSML｜parameter name="days" string="false">1</｜DSML｜parameter>\n</｜DSML｜invoke>\n</｜DSML｜function_calls> Сейчас +13')
out = "".join(t.feed(txt[i:i + 5]) for i in range(0, len(txt), 5)) + t.tail()
ok(out == "Сейчас узнаю." and t.calls() == [{"name": "weather", "args": {"city": "Москва", "days": 1}}], f"DSML на компьютере: {out!r} {t.calls()}")
t = llm.ToolTagStripper()
ok(t.feed("Вот знак <｜ и текст.") + t.tail() == "Вот знак <｜ и текст.", "похожий на DSML текст — не теряется")
# №301/№304: open-meteo не открылся — погода через сервер Dewiar, а не «прогноз не получить»
import json as _j  # noqa: E402
def via(kind, url):
    if "geocoding" in url:
        return _j.dumps({"results": [{"name": "Москва", "latitude": 55.7, "longitude": 37.6}]})
    return _j.dumps({"current": {"temperature_2m": 7.2, "apparent_temperature": 4, "weather_code": 3, "wind_speed_10m": 11},
                     "daily": {"time": [], "weather_code": [], "temperature_2m_max": [], "temperature_2m_min": [], "precipitation_probability_max": []}})
with mock.patch.object(tools.httpx, "get", side_effect=httpx.ConnectError("timeout")):
    try:
        w = tools.t_weather({"city": "Москва", "days": 1}, {"dewiar_web": via})
    except Exception as e:  # noqa: BLE001
        w = "ИСКЛЮЧЕНИЕ " + str(e)
ok(str(w).startswith("Москва: сейчас 7°"), f"погода через сервер Dewiar: {str(w)[:60]!r}")
# №323: голос Windows (SAPI) — в отдельном процессе, сбой COM не роняет ядро
import tts, base64 as _b  # noqa: E402,E401
compile(tts.SAPI_PY, "sapi", "exec")
syn = tts.SapiTTS.synth.__code__.co_names + tts.SapiTTS.available.__code__.co_names
ok("comtypes" not in syn and "_sapi_run" in syn, "SAPI в ядре не трогается — только через отдельный процесс")
seen = {}
def fake_run(args, timeout):
    seen.update(args)
    return subprocess.CompletedProcess([], 0, stdout=_b.b64encode(b"\x01\x02" * 10).decode(), stderr="")
with mock.patch.object(tts, "_sapi_run", fake_run):
    got = list(tts.SapiTTS().synth("Привет, 5 минут", {"_gender": "female"}, 1.2))
ok(got and got[0][0] == 22050 and len(got[0][1]) == 20 and seen.get("gender") == "female" and seen.get("rate") == 2, f"синтез из процесса: {seen}")
def bad_run(args, timeout):
    return subprocess.CompletedProcess([], -1073741819, stdout="", stderr="Windows fatal exception: access violation")
with mock.patch.object(tts, "_sapi_run", bad_run):
    try:
        list(tts.SapiTTS().synth("Привет", {}, 1.0)); r = "без ошибки"
    except RuntimeError as e:
        r = str(e)
ok("голос Windows не сработал" in r, f"процесс упал — понятная ошибка, ядро живо: {r[:60]!r}")
# №331: сами отдали речь серверу, а он медленный — три медленные фразы, и снова Vosk
import engine_brain  # noqa: E402
cls = next(v for v in vars(engine_brain).values() if isinstance(v, type) and hasattr(v, "_stt_timing"))
st2 = settings.Settings(tmp / "cfg" / "s2.json"); st2.update({"device": {"light": True, "stt_auto": True}, "stt": {"engine": "remote"}})
e = types.SimpleNamespace(s=st2, cloud=types.SimpleNamespace(set_stt=lambda on: None), apply_engines=lambda: None, emit=lambda *a, **k: None,
                          push=lambda *a, **k: None, account=None)
e._apply_light_stt = lambda how: cls._apply_light_stt(e, how)
for ms in (21000, 23000):
    cls._stt_timing(e, None, ms)
ok(st2.get("stt", "engine") == "remote", "две медленные фразы — пока ждём")
cls._stt_timing(e, None, 25000)
ok(st2.get("stt", "engine") == "vosk" and not st2.get("device", "stt_auto") and st2.get("device", "stt_slow_at"), "третья — снова свой Vosk, сутки не переключаем")
print("ИТОГ:", "OK" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
