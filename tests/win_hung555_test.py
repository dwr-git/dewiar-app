"""№555 (05.11, «Dewiar не запускается», Windows 11, 0.76): мьютекс «один экземпляр» держал осиротевший pythonw прошлого
запуска (жил с 04.11), а номера из ui.pid уже не было в живых. Каждый новый запуск писал сигнал «покажись» и молча выходил —
сигнал никто не брал. Теперь: сигнал не взят за 8 с и номера из ui.pid нет в живых — процессы Python из папки программы
завершаются, и запуск идёт заново; номер жив (тот ещё запускается) — ничего не трогаем."""
import ast, os, sys, tempfile, threading, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def grab(path, *names):
    src = (ROOT / path).read_text(encoding="utf-8")
    tree = ast.parse(src)
    ns = {"time": time, "Path": Path, "os": os}
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name in names:
            exec(compile(ast.Module([n], []), path, "exec"), ns)
    return ns, src


W, wsrc = grab("ui/winshell.py", "pythons_in")
lst = "\n".join(["101|D:\\Programs\\Dewiar\\python\\pythonw.exe", "102|d:\\programs\\dewiar\\python\\python.exe",
                 "103|C:\\Users\\A\\AppData\\Roaming\\uv\\python\\python.exe", "104|D:\\Programs\\DewiarX\\python\\python.exe",
                 "105|D:\\Programs\\Dewiar\\python\\pythonw.exe", "garbage"])
got = W["pythons_in"](lst, "D:\\Programs\\Dewiar", skip=(105,))
ok(got == [101, 102], f"только python из папки программы (без чужих uv/hermes, без похожей папки и без себя): {got}")

A, asrc = grab("ui/app.py", "hung_instance")
hung = A["hung_instance"]
tmp = Path(tempfile.mkdtemp())
sig = tmp / "sig"


def run(pid, alive, take_after=None, wait=1.0):
    sig.write_text("hud")
    (tmp / "ui.pid").unlink(missing_ok=True)
    if pid:
        (tmp / "ui.pid").write_text(pid)
    if take_after is not None:
        threading.Timer(take_after, lambda: sig.unlink(missing_ok=True)).start()
    return hung(sig, tmp, wait=wait, alive=lambda p: alive)


ok(run("3460", False, take_after=0.3) is False, "прежний взял сигнал — он жив, выходим как раньше")
ok(run("3460", True) is False, "сигнал не взят, но номер жив (ещё запускается) — ничего не трогаем")
ok(run("3460", False) is True, "сигнал не взят и номера нет в живых — прежний завис (№555)")
ok(run("", False) is True, "ui.pid нет вовсе, сигнал не взят — завис")
ok("hung_instance(sig, STATE_DIR)" in asrc and "winshell.our_pythons(Path(sys.executable).parent.parent)" in asrc,
   "main_win: при зависшем прежнем — завершает процессы своей папки и запускается")
ok("def pid_alive" in wsrc and "def our_pythons" in wsrc, "winshell: our_pythons и pid_alive")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
