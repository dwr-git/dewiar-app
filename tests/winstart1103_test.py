"""«Dewiar не запускается» (диагностика с ПК 0.76.0: №456, №469, №471, №472, №476, №489), 03.11.
№469 (Windows 10): WebView2 записан в реестре, но файлов среды нет — pywebview только пишет «WebView2 initialization
failed… Couldn't find a compatible Webview2 Runtime installation» в журнал, окна оставались пустыми и закрыть их было
нечем. Теперь эту запись ловим (WV2_FAIL), окна убираем, прямо говорим, что сломано и как починить (страница Microsoft),
студия — в браузере. Диагностика видит, что файлов среды нет (doctor.wv2_files_ok).
№471, №472: журналов нет вовсе — интерфейс (pythonw, без консоли) упал раньше своего журнала, человек не видел ничего.
Теперь — окно Windows с подсказкой и %TEMP%\\dewiar-ui-crash.txt, его кладёт в отчёт диагностика.
№457 (журнал): «WinError 1005» во временной папке (RAM-диск) убивал сторожа сигнала «покажись» — повторный запуск больше
не показывал виджет. Теперь сторож ошибку переживает."""
import logging, os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "ui")); sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import app  # noqa: E402

# №469: запись pywebview о сбое WebView2 -> событие; страничный сторож по нему убирает окна
app.wv2_fail_watch(); app.wv2_fail_watch()
lg = logging.getLogger("pywebview")
ok(sum(1 for h in lg.handlers if getattr(h, "_dewiar", False)) == 1, "слушатель журнала pywebview — один, сколько ни зови")
ok(not app.WV2_FAIL.is_set(), "пока сбоя нет — события нет")
lg.error("WebView2 initialization failed with exception:\n Couldn't find a compatible Webview2 Runtime installation")
ok(app.WV2_FAIL.is_set(), "№469: «WebView2 initialization failed» в журнале pywebview — замечено")
src = (ROOT / "ui/app.py").read_text(encoding="utf-8")
mw = src[src.index("def main_win(args, extra):"):src.index("def wv2_registry_fix")]
ok("if WV2_FAIL.wait(pause):" in mw and "return wv2_broken()" in mw, "сторож загрузки виджета ждёт и это событие")
wb = mw[mw.index("def wv2_broken():"):mw.index("print(f\"Виджет: {api._url")]
ok("w.hide()" in wb and "winshell.ask_yes_no(WV2_BROKEN_TEXT" in wb and "os.startfile(WV2_URL)" in wb and "studio_in_browser()" in wb,
   "окна убираем, предлагаем переустановить WebView2, студия — в браузере")
ok(mw.index("wv2_fail_watch()") < mw.index("webview.start("), "журнал слушаем до запуска окон")
ok("повреждён или удалён" in app.WV2_BROKEN_TEXT and "Ассистент работает" in app.WV2_BROKEN_TEXT and app.WV2_URL.startswith("https://go.microsoft.com/"),
   "понятный текст и страница загрузки у Microsoft")

import doctor  # noqa: E402
tmp = Path(tempfile.mkdtemp())
(tmp / "Microsoft/EdgeWebView/Application").mkdir(parents=True)
ok(not doctor.wv2_files_ok("150.0.4078.105", "", env={"ProgramFiles(x86)": str(tmp)}), "№469: папка есть, а msedgewebview2.exe нет — «повреждён»")
(tmp / "Microsoft/EdgeWebView/Application/151.0.1").mkdir()
(tmp / "Microsoft/EdgeWebView/Application/151.0.1/msedgewebview2.exe").write_text("")
ok(doctor.wv2_files_ok("150.0.4078.105", "", env={"ProgramFiles(x86)": str(tmp)}), "версия в реестре отстала от папки — не тревожим")
ok(doctor.wv2_files_ok("151.0.1", str(tmp / "Microsoft/EdgeWebView/Application"), env={}), "папка из реестра (location) с этой версией — в порядке")
ok(doctor.wv2_files_ok("150.0.1", "", env={}), "негде искать — не тревожим")
dsrc = (ROOT / "ui/doctor.py").read_text(encoding="utf-8")
ok("ФАЙЛОВ СРЕДЫ НЕТ" in dsrc and "wv2_files_ok(v, loc)" in dsrc, "диагностика пишет, что WebView2 повреждён")

# №471/472: интерфейс упал до журнала — окно с подсказкой и файл во временной папке
ok("fatal_box(_e, \"загрузка\")" in src and "fatal_box(e)" in src, "сбой при загрузке и в main() — окно Windows с подсказкой")
try:
    raise RuntimeError("проверка")
except RuntimeError as e:
    txt = app.fatal_box(e, "проверка")
ok("RuntimeError: проверка" in txt, "текст сбоя с трассировкой")
fb = src[src.index("def fatal_box"):src.index("try:\n    from settings import")]
ok("CRASH_NAME" in fb and "MessageBoxW" in fb and "Диагностика" in fb, "Windows: файл сбоя и окно с тем, что делать")
ok('"dewiar-ui-crash.txt"' in dsrc and app.CRASH_NAME == "dewiar-ui-crash.txt", "диагностика кладёт файл сбоя в отчёт")
ok("dewiar-ui.log" in src and "dewiar-ui.log" in dsrc, "нет папки журнала — журнал во временной папке, и он тоже в отчёте")

# №457 (журнал): сторож сигнала «покажись» переживает ошибку временной папки
w = mw[mw.index("def watch():"):mw.index("threading.Thread(target=watch")]
ok("except OSError" in w and "sig.exists()" in w.split("except OSError")[0] and "continue" in w, "WinError во временной папке не убивает сторожа")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
