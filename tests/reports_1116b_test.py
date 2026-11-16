"""Пачка 16.11, 00:40, №761–764 (Windows, снимки): ядро запускали вручную «python main.py --debug» системным Python 3.11
(C:\\Users\\…\\Python311), а не тем, что поставил установщик: «No module named 'vosk'», студия — «нет связи с ядром».
Ядро, запущенное чужим Python в установленной папке, перезапускается своим (<папка Dewiar>\\python\\python.exe) и говорит,
что обычно Dewiar запускают ярлыком."""
import importlib.util, os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


spec = importlib.util.spec_from_file_location("core_main", ROOT / "core/main.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
d = Path(tempfile.mkdtemp())
(d / "python").mkdir(); (d / "python" / "python.exe").write_text("")
(d / "app" / "core").mkdir(parents=True); (d / "app" / "core" / "main.py").write_text("")
main = d / "app" / "core" / "main.py"
ok(M.own_python("C:/Users/u/Python311/python.exe", main) == d / "python" / "python.exe", "чужой Python в установленной папке — свой python.exe")
ok(M.own_python(d / "python" / "python.exe", main) is None, "свой Python — как есть")
ok(M.own_python(sys.executable, ROOT / "core/main.py") is None, "из исходников (своей папки python нет) — как есть")
src = (ROOT / "core/main.py").read_text(encoding="utf-8")
ok('own = own_python() if os.name == "nt" else None' in src and "subprocess.call([str(own)" in src and "ярлыком" in src,
   "перезапуск своим Python с теми же ключами и подсказкой про ярлык — только на Windows")
# «Ещё раз» в «Чате»: шаг «Руководство» (раздел руководства к вопросу, 1.0.6) — не действие: не спрашивать «повторятся?»
import engine as EN  # noqa: E402
ok({"app_help", "web_search", "read_file"} <= EN.LOOK_ONLY and "set_reminder" not in EN.LOOK_ONLY, "только смотрящие шаги помечены")
cj = (ROOT / "ui/studio/chat.js").read_text(encoding="utf-8")
ok('&& !st.r).map(st => st.t)' in cj, "«Ещё раз» предупреждает только о настоящих действиях")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
