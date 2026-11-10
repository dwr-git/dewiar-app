"""Песочница для кода задач («Большие задачи», выпуск 5, docs/HARNESS.md). Раньше run_python задачи читал любой файл
человека (~/.config/Dewiar, профили браузеров, ~/.ssh), писал куда угодно, ходил в сеть, а по таймауту погибал только сам
скрипт — его дети жили дальше. Теперь (core/sandbox.py) — во всех режимах: bwrap и landlock (настоящая изоляция, если
есть) и охрана (guard):
- запись вне папки задачи и временной папки — отказ (файла снаружи нет), служебные файлы задачи — только чтение;
- чтение ~/.ssh, профиля браузера, папок Dewiar (настройки, состояние), папки ассистента вне папки задачи — отказ;
  данная человеком папка — читается, но не пишется;
- в окружении кода нет ни ключей, ни токенов, ни SSH_AUTH_SOCK;
- сеть выключена — к слушающему сокету на 127.0.0.1 не подключиться (и сервер не видит подключения); включена — к
  127.0.0.1 компьютера всё равно нельзя (bwrap со slirp4netns — своя сеть; охрана и landlock — запрет адресов в Python),
  а к адресу компьютера в сети (bwrap) — можно; без slirp4netns bwrap даёт сеть компьютера целиком (так и сказано человеку);
- таймаут убивает всё дерево: и внуков, и ушедших в свою сессию (setsid);
- в задаче: run_python и run_shell в настоящей песочнице — без вопроса человеку; под охраной — с разрешения (run_shell —
  даже при автозапуске кода); облако — код только через bwrap со строгим корнем.
Чего нет на этом компьютере (bubblewrap, Landlock, slirp4netns) — пропускается с пометкой. Обходы рецензии — sandbox_escape_test."""
import os
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from task_mock import Host, Mock, done, ok  # noqa: E402  (задаёт папки Dewiar проверки: DEWIAR_CONFIG_DIR, DEWIAR_STATE_DIR)
import sandbox as S  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="sbx-"))
HOME = TMP / "home"
CFG, ST = Path(os.environ["DEWIAR_CONFIG_DIR"]), Path(os.environ["DEWIAR_STATE_DIR"])
os.environ.update(HOME=str(HOME), OPENAI_API_KEY="sk-proba-SECRET-1", SSH_AUTH_SOCK=str(TMP / "agent.sock"))
os.environ["DEWIAR_RUNNER" + "_KEY"] = "dr-SECRET-2"          # имя по частям: открытая копия ищет «…_KEY=» как утечку
os.environ.pop("DEWIAR_SANDBOX", None)

# личное человека и папки Dewiar
(HOME / ".ssh").mkdir(parents=True)
(HOME / ".ssh/id_test").write_text("SSH-KEY-SECRET", encoding="utf-8")
(HOME / ".mozilla/firefox/p1").mkdir(parents=True)
(HOME / ".mozilla/firefox/p1/cookies.txt").write_text("COOKIE-SECRET", encoding="utf-8")
(HOME / "Документы").mkdir()
(HOME / "Документы/дневник.txt").write_text("DIARY-SECRET", encoding="utf-8")
CFG.mkdir(parents=True, exist_ok=True)
(CFG / "settings.json").write_text('{"token": "CFG-SECRET"}', encoding="utf-8")
ST.mkdir(parents=True, exist_ok=True)
(ST / "sync.json").write_text("STATE-SECRET", encoding="utf-8")
WS = TMP / "ws"
(WS / "Заметки").mkdir(parents=True)
(WS / "Заметки/личное.md").write_text("NOTE-SECRET", encoding="utf-8")
TASK = WS / "Задачи" / "2026-11-05 1200 Проба"
(TASK / "outputs").mkdir(parents=True)
(TASK / "задача.json").write_text('{"id": "x"}', encoding="utf-8")
(TASK / "_run").mkdir()
GRANT = TMP / "Данные человека"
GRANT.mkdir()
(GRANT / "таблица.csv").write_text("a;b\n1;2\n", encoding="utf-8")
OUTSIDE = TMP / "снаружи.txt"

srv = socket.socket()
srv.bind(("127.0.0.1", 0))
srv.listen(16)
PORT = srv.getsockname()[1]
accepted = []
threading.Thread(target=lambda: [accepted.append(srv.accept()) for _ in range(100)], daemon=True).start()
# адрес компьютера в сети (не 127.0.0.1) — к нему код с данной сетью в bwrap подключается и через slirp4netns
try:
    _u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    _u.connect(("192.0.2.1", 9))
    HOSTIP = _u.getsockname()[0]
except OSError:
    HOSTIP = ""
HOSTIP = "" if HOSTIP.startswith("127.") else HOSTIP
PORT2 = 0
accepted2 = []
if HOSTIP:
    srv2 = socket.socket()
    srv2.bind((HOSTIP, 0))
    srv2.listen(16)
    PORT2 = srv2.getsockname()[1]
    threading.Thread(target=lambda: [accepted2.append(srv2.accept()) for _ in range(100)], daemon=True).start()

PROBE = r'''
import os, sys, socket, json
res = {}
def tryit(k, f):
    try:
        v = f()
        res[k] = "OK:" + (str(v)[:80] if v is not None else "")
    except BaseException as e:
        res[k] = "ERR:" + type(e).__name__ + ":" + str(e)[:600]
H, CFG, ST, WS, GRANT, OUTSIDE, PORT, HOSTIP, PORT2 = sys.argv[1:10]
tryit("w_task", lambda: open("outputs/проба.txt", "w").write("ok"))
tryit("w_outside", lambda: open(OUTSIDE, "w").write("x"))
tryit("w_home", lambda: open(os.path.join(H, "плохо.txt"), "w").write("x"))
tryit("w_service", lambda: open("задача.json", "w").write("{}"))
tryit("w_grant", lambda: open(os.path.join(GRANT, "новый.txt"), "w").write("x"))
tryit("r_ssh", lambda: open(os.path.join(H, ".ssh/id_test")).read())
tryit("r_browser", lambda: open(os.path.join(H, ".mozilla/firefox/p1/cookies.txt")).read())
tryit("r_docs", lambda: open(os.path.join(H, "Документы/дневник.txt")).read())
tryit("ls_home", lambda: os.listdir(H))
tryit("r_cfg", lambda: open(os.path.join(CFG, "settings.json")).read())
tryit("r_state", lambda: open(os.path.join(ST, "sync.json")).read())
tryit("r_ws", lambda: open(os.path.join(WS, "Заметки/личное.md")).read())
tryit("r_grant", lambda: open(os.path.join(GRANT, "таблица.csv")).read())
tryit("r_system", lambda: open("/etc/passwd").read()[:4])
tryit("import_numpy", lambda: __import__("numpy").__version__)
tryit("tmp", lambda: open(os.path.join(os.environ.get("TMPDIR", "/tmp"), "x.txt"), "w").write("t"))
tryit("net", lambda: socket.create_connection(("127.0.0.1", int(PORT)), timeout=3).close())
tryit("net_host", lambda: socket.create_connection((HOSTIP, int(PORT2)), timeout=3).close() if HOSTIP else "нет адреса")
tryit("dns", lambda: socket.getaddrinfo("localhost", 80)[0][4][0])
tryit("child_ssh", lambda: __import__("subprocess").run([sys.executable, "-c", "print(open(%r).read())" % os.path.join(H, ".ssh/id_test")],
                                                         capture_output=True, text=True, timeout=30).stdout.strip() or "пусто")
res["env"] = sorted(os.environ)
res["env_text"] = "\n".join(f"{k}={v}" for k, v in os.environ.items())
print("RES=" + json.dumps(res, ensure_ascii=False))
'''
(TASK / "_run" / "probe.py").write_text(PROBE, encoding="utf-8")


def probe(m, net=False, **kw):
    acc0 = len(accepted)
    r = S.run([sys.executable, str(TASK / "_run" / "probe.py"), str(HOME), str(CFG), str(ST), str(WS), str(GRANT),
               str(OUTSIDE), str(PORT), HOSTIP, str(PORT2)], TASK, m=m, net=net, grants=[str(GRANT)], hide=[str(WS)],
              protect=("задача.json", "_run"), timeout=60, **kw)
    line = next((x for x in r.out.splitlines() if x.startswith("RES=")), "")
    import json
    if not line:
        print(r.out[-2000:], r.err[-2000:])
    return (json.loads(line[4:]) if line else {}), r, len(accepted) - acc0


SECRETS = ("SSH-KEY-SECRET", "COOKIE-SECRET", "DIARY-SECRET", "CFG-SECRET", "STATE-SECRET", "NOTE-SECRET")


def check_mode(label, m):
    res, r, conns = probe(m)
    ok(bool(res), f"{label}: проба отработала (код {r.code})")
    if not res:
        return
    ok(res["w_task"].startswith("OK") and (TASK / "outputs/проба.txt").read_text() == "ok", f"{label}: запись в outputs/ — можно")
    ok(not OUTSIDE.exists() and not (HOME / "плохо.txt").exists(),
       f"{label}: запись вне папки задачи — отказ, снаружи файла нет ({res['w_outside'][:70]}; {res['w_home'][:50]})")
    if m in ("guard", "landlock"):
        ok("Dewiar (песочница" in res["w_outside"] and "outputs/" in res["w_outside"], f"{label}: отказ понятен модели: {res['w_outside'][:120]}")
    ok(res["w_service"].startswith("ERR") and (TASK / "задача.json").read_text() == '{"id": "x"}', f"{label}: служебный файл задачи — только чтение")
    ok(res["w_grant"].startswith("ERR") and not (GRANT / "новый.txt").exists(), f"{label}: данная человеком папка — не пишется")
    for k in ("r_ssh", "r_browser", "r_docs", "r_cfg", "r_state", "r_ws"):
        ok(res[k].startswith("ERR"), f"{label}: {k} — отказ ({res[k][:90]})")
    # bwrap: на месте домашней папки — пустая (в ней только то, что код сам туда положил в своей /tmp)
    ok(res["ls_home"].startswith("ERR") or not any(x in res["ls_home"] for x in (".ssh", ".mozilla", "Документы")),
       f"{label}: содержимое домашней папки не видно ({res['ls_home'][:90]})")
    ok(not any(s_ in r.out for s_ in SECRETS), f"{label}: ни одной тайны в выводе кода")
    ok(res["r_grant"].startswith("OK") and res["r_system"].startswith("OK") and res["import_numpy"].startswith("OK"),
       f"{label}: данная папка, система и библиотеки Python читаются")
    ok(res["tmp"].startswith("OK"), f"{label}: временная папка пишется")
    env = res["env_text"]
    ok(not any(x in env for x in ("sk-proba-SECRET", "dr-SECRET", "agent.sock")) and "OPENAI_API_KEY" not in res["env"]
       and "SSH_AUTH_SOCK" not in res["env"] and str(HOME) not in env.split("HOME=")[1].split("\n")[0],
       f"{label}: в окружении нет ключей, токенов, SSH_AUTH_SOCK; HOME — не настоящая")
    ok(res["net"].startswith("ERR") and conns == 0, f"{label}: сеть выключена — к 127.0.0.1:{PORT} не подключиться, сервер подключений не видел ({res['net'][:80]})")
    ok("SSH-KEY-SECRET" not in res["child_ssh"], f"{label}: дочерний Python тоже не читает ~/.ssh ({res['child_ssh'][:90]})")
    n0 = len(accepted2)
    res2, r2, conns2 = probe(m, net=True)
    time.sleep(0.3)
    if m == "bwrap" and not S.slirp_bin():
        # без slirp4netns — сеть компьютера целиком, с его 127.0.0.1 (это и говорим человеку: sandbox.net_note)
        ok(res2.get("net", "").startswith("OK") and "локальные службы" in S.net_note("bwrap"),
           f"{label}: без slirp4netns сеть — компьютера целиком, и человек об этом знает ({res2.get('net', '')[:60]})")
    else:
        ok(res2.get("net", "").startswith("ERR") and conns2 == 0,
           f"{label}: сеть дали — а к 127.0.0.1 компьютера (мост Dewiar :8765) всё равно нельзя ({res2.get('net', '')[:80]})")
    if m == "bwrap" and HOSTIP:
        ok(res2.get("net_host", "").startswith("OK") and len(accepted2) > n0,
           f"{label}: сеть дали — к адресу компьютера в сети подключение есть ({res2.get('net_host', '')[:60]})")
    ok(res2.get("dns", "").startswith("OK") and (m == "bwrap" or res.get("dns", "").startswith("ERR")),
       f"{label}: имена ищутся, только когда сеть дали ({res.get('dns', '')[:50]} → {res2.get('dns', '')[:30]})")
    (TASK / "outputs/проба.txt").unlink()

    # таймаут: внуки (и ушедший в свою сессию правнук) пишут «пульс» в файлы — после таймаута пульса нет
    beat = (r'''import os, sys, time, subprocess
code = """import os, sys, time
if len(sys.argv) > 2 and os.fork() == 0:
    os.setsid()
    if os.fork(): os._exit(0)
f = sys.argv[1]
while True:
    open(f, "a").write("x"); time.sleep(0.05)
"""
for i in range(2):
    subprocess.Popen([sys.executable, "-c", code, f"outputs/beat{i}.txt"] + (["daemon"] if i else []))
print("запустил", flush=True)
time.sleep(60)
''')
    (TASK / "_run" / "beat.py").write_text(beat, encoding="utf-8")
    t0 = time.time()
    rb = S.run([sys.executable, str(TASK / "_run" / "beat.py")], TASK, m=m, timeout=2, env={"SBX_PROBA": "beat-" + label})
    took = time.time() - t0
    time.sleep(0.4)
    sizes = [(TASK / f"outputs/beat{i}.txt").stat().st_size if (TASK / f"outputs/beat{i}.txt").exists() else -1 for i in range(2)]
    time.sleep(0.8)
    sizes2 = [(TASK / f"outputs/beat{i}.txt").stat().st_size if (TASK / f"outputs/beat{i}.txt").exists() else -1 for i in range(2)]
    alive = []
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                if b"SBX_PROBA=beat-" + label.encode() in open(f"/proc/{d}/environ", "rb").read():
                    alive.append(d)
            except OSError:
                pass
    ok(rb.timed_out and took < 15 and min(sizes) > 0 and sizes == sizes2 and not alive,
       f"{label}: таймаут убил всё дерево — внуки и ушедший в свою сессию не пишут ({sizes} → {sizes2}, живых {len(alive)}, {took:.1f} с)")
    for i in range(2):
        (TASK / f"outputs/beat{i}.txt").unlink(missing_ok=True)


print(f"режим по умолчанию: {S.mode()}; bubblewrap: {'есть' if S.bwrap_ok() else 'нет'}; unshare: {'да' if S._unshare_flags() else 'нет'}")
# охрана без unshare — только Python-охрана (как в Windows и на Linux без пространств имён)
os.environ["DEWIAR_SANDBOX_UNSHARE"] = "0"
check_mode("охрана", "guard")
os.environ.pop("DEWIAR_SANDBOX_UNSHARE")
S._probe.pop("unshare", None)
if S._unshare_flags():
    check_mode("охрана+unshare", "guard")
# охрана: оболочка, чужие программы, ctypes, переименованный Python — отказ
(TASK / "_run" / "esc.py").write_text(r'''import subprocess, sys, os, shutil, ctypes
out = []
for name, f in (("sh", lambda: subprocess.run(["sh", "-c", "cat ~/.ssh/id_test"])),
                ("os.system", lambda: os.system("id")),
                ("cat", lambda: subprocess.run(["cat", "/etc/hostname"])),
                ("ctypes", lambda: ctypes.CDLL(None).open),
                ("python -I", lambda: subprocess.run([sys.executable, "-I", "-c", "print(1)"])),
                ("копия sh", lambda: (shutil.copy("/bin/sh", "python3"), subprocess.run(["./python3", "-c", "echo x"]))),
                ("pandoc вне папки", lambda: subprocess.run(["pandoc", sys.argv[1] + "/.ssh/id_test"])),
                ("ffmpeg вне папки", lambda: subprocess.run(["ffmpeg", "-y", "-i", "outputs/a.wav", sys.argv[1] + "/out.mp3"])),
                ("tar -I", lambda: subprocess.run(["tar", "-I", "sh -c 'cat " + sys.argv[1] + "/.ssh/id_test'", "-cf", "outputs/a.tar", "outputs"])),
                ("ffmpeg concat:", lambda: subprocess.run(["ffmpeg", "-y", "-i", "concat:" + sys.argv[1] + "/.ssh/id_test", "outputs/b.wav"])),
                ("pandoc --filter", lambda: subprocess.run(["pandoc", "--filter=./x", "outputs/a.md"])),
                ("ffmpeg http:// без сети", lambda: subprocess.run(["ffmpeg", "-y", "-i", "http://127.0.0.1:9/x.mp3", "outputs/c.wav"])),
                ("pandoc в папке", lambda: (open("outputs/a.md", "w").write("# Привет"),
                                            subprocess.run(["pandoc", "outputs/a.md", "-o", "outputs/a.html"], check=True)))):
    try:
        f()
        out.append(name + ":OK")
    except BaseException as e:
        out.append(name + ":ERR")
print(" ".join(out))
''', encoding="utf-8")
os.environ["DEWIAR_SANDBOX_UNSHARE"] = "0"
r = S.run([sys.executable, str(TASK / "_run" / "esc.py"), str(HOME)], TASK, m="guard", timeout=30)
os.environ.pop("DEWIAR_SANDBOX_UNSHARE")
import shutil  # noqa: E402
ok(r.out.strip() and r.out.count(":OK") == (1 if shutil.which("pandoc") else 0) and ("pandoc в папке:OK" in r.out or not shutil.which("pandoc")),
   f"охрана: оболочка, os.system, чужие программы, ctypes, python -I, переименованная копия, конвертер с путём наружу — отказ; "
   f"конвертер с файлами задачи — можно ({r.out.strip()[:260]})")
(TASK / "python3").unlink(missing_ok=True)

if S.landlock_ok():
    check_mode("landlock", "landlock")
    os.environ["DEWIAR_SANDBOX_UNSHARE"] = "0"
    check_mode("landlock без unshare", "landlock")
    os.environ.pop("DEWIAR_SANDBOX_UNSHARE")
else:
    print(f"⚠ Landlock нет (ABI {S.landlock_abi()}) — часть «landlock» пропущена")
if S.bwrap_ok():
    check_mode("bwrap", "bwrap")
    if S.slirp_bin():
        os.environ["DEWIAR_SANDBOX_SLIRP"] = "0"
        check_mode("bwrap без slirp4netns", "bwrap")
        os.environ.pop("DEWIAR_SANDBOX_SLIRP")
    else:
        print("⚠ slirp4netns нет — своя сеть песочницы не проверена")
    # облако: строгий корень — ни /etc целиком, ни /home, ни папок других людей
    other = TMP / "runner" / "u2" / "Dewiar"
    other.mkdir(parents=True)
    (other / "чужое.txt").write_text("OTHER-SECRET", encoding="utf-8")
    (TMP / "runner" / "u2" / "grant").write_text("GRANT-SECRET", encoding="utf-8")
    mine = TMP / "runner" / "u1" / "Dewiar" / "Задачи" / "т"
    (mine / "outputs").mkdir(parents=True)
    rs = S.run([sys.executable, "-c", "import os,sys\nfor p in sys.argv[1:]:\n    print(p, os.path.exists(p))\n"
                "open('outputs/x.txt','w').write('1')", str(other / "чужое.txt"), str(TMP / "runner/u2/grant"), "/etc/hostname",
                "/home", "/etc/ssl", "/usr/bin"], mine, m="bwrap", strict=True, hide=[str(TMP / "runner")], timeout=30)
    lines = dict(x.rsplit(" ", 1) for x in rs.out.strip().splitlines() if " " in x)
    ok(lines.get(str(other / "чужое.txt")) == "False" and lines.get(str(TMP / "runner/u2/grant")) == "False"
       and lines.get("/etc/hostname") == "False" and lines.get("/home") == "False" and lines.get("/etc/ssl") == "True"
       and (mine / "outputs/x.txt").exists(), f"облако (strict): чужие папки, /etc целиком и /home не видны, свои outputs пишутся: {lines}")
else:
    print("⚠ bubblewrap нет — части «bwrap» и «облако с кодом» пропущены (поставьте: sudo apt install bubblewrap)")

# потолок папки задачи (облако, S5): код раздувает папку — остановлен, честно сказано
ro = S.run([sys.executable, "-c", "import time\nf = open('outputs/big.bin', 'wb')\nfor i in range(200):\n    f.write(b'x' * (1 << 20)); f.flush(); time.sleep(0.05)"],
           TASK, m=S.mode(), timeout=60, max_bytes=8 << 20)
ok(ro.oversize and not ro.timed_out and (TASK / "outputs/big.bin").stat().st_size < 150 << 20,
   f"потолок папки задачи: выросла больше предела — код остановлен ({(TASK / 'outputs/big.bin').stat().st_size >> 20} МБ)")
(TASK / "outputs/big.bin").unlink()

# ---------- в задаче: без вопросов, run_shell, служебное, сеть по настройке ----------
import tasks as TK  # noqa: E402
mock = Mock({})
host = Host(mock)
asked = []
host.confirm = lambda q, cancel=None: (asked.append(q), True)[1]
host.code_auto_run = lambda: False
tm = TK.TaskManager(host)
t = tm.create("Песочница", "посчитать", start=False, folders=[str(GRANT)])
REAL = S.real_sandbox(S.mode())
r = tm._tool(t, "run_python", {"code": f"print(open({str(GRANT / 'таблица.csv')!r}).read().count(';'))\n"
                                        "open('outputs/итог.txt','w').write('2')"})
ok(r.startswith("Код выхода 0") and "2" in r and (t.dir / "outputs/итог.txt").exists() and (not asked if REAL else len(asked) == 1),
   f"run_python ({S.mode()}): {'без вопроса человеку (автозапуск выключен)' if REAL else 'с разрешения раз на задачу'}, данная папка читается: {r[:80]!r}")
# охрана (без настоящей песочницы): run_python — с разрешения раз на задачу, как до выпуска 5 (B1)
os.environ["DEWIAR_SANDBOX"] = "guard"
asked.clear()
tg = tm.create("Охрана", "x", start=False)
r1, r2_ = tm._tool(tg, "run_python", {"code": "print(1)"}), tm._tool(tg, "run_python", {"code": "print(2)"})
ok(r1.startswith("Код выхода 0") and r2_.startswith("Код выхода 0") and len(asked) == 1 and "Разрешить" in asked[0],
   "охрана: run_python — с разрешения человека раз на задачу (обходы охраны есть — это не песочница)")
host.code_auto_run = lambda: True
asked.clear()
r = tm._tool(tg, "run_shell", {"command": "echo ок"})
ok("ок" in r and len(asked) == 1, "охрана: run_shell спрашивает каждый раз — даже при автозапуске кода (N3)")
host.code_auto_run = lambda: False
d = tm.detail(tg.id)
ok(d["sandbox"]["mode"] == "guard" and "человека" in d["sandbox"]["text"], f"студия: под охраной честно — с разрешения ({d['sandbox']['text'][:60]})")
js = (Path(__file__).resolve().parent.parent / "ui/studio/tasks.js").read_text(encoding="utf-8")
ok("не от нарочного взлома" in js and "не читает личное" not in js.split("guard:")[1].split("\n")[0],
   "студия: охрана — «от случайных ошибок кода, но не от нарочного взлома»")
os.environ.pop("DEWIAR_SANDBOX")
asked.clear()
r = tm._tool(t, "run_python", {"code": f"print(open({str(HOME / '.ssh/id_test')!r}).read())"})
ok("SSH-KEY-SECRET" not in r and "Код выхода 1" in r, f"задача: ~/.ssh не читается: {r[:120]!r}")
r = tm._tool(t, "run_python", {"code": "import socket\nsocket.create_connection(('127.0.0.1', %d), timeout=3)\nprint('есть сеть')" % PORT})
ok("есть сеть" not in r, "задача: сети у кода по умолчанию нет")
tm.set_net(t.id, True)
code = (f"import socket\nsocket.create_connection(({HOSTIP!r}, {PORT2}), timeout=3)\nprint('есть сеть')" if HOSTIP and S.mode() == "bwrap"
        else "import socket\nsocket.getaddrinfo('localhost', 80)\nprint('есть сеть')")
r = tm._tool(t, "run_python", {"code": code})
ok("есть сеть" in r and "Человек включил сеть" in " ".join(t.data.get("sys_notes") or []), f"задача: человек дал сеть — код ходит в сеть, задача узнает: {r[:80]!r}")
tm.set_net(t.id, False)
r = tm._tool(t, "run_python", {"code": "import time\ntime.sleep(30)", "timeout": 5})
ok(r.startswith("Остановлено по времени (5 с)") and "процессы" in r, f"задача: таймаут — честно: {r[:80]!r}")
ok("ПЕСОЧНИЦА" in tm._system(t) and "rewind" in tm._system(t) and "сеть для кода выключена" in tm._system(t), "подсказка задачи: песочница, сеть, откат")
d = tm.detail(t.id)
ok(d["sandbox"]["mode"] == S.mode() and d["sandbox"]["net"] is False, f"студия видит режим песочницы и сеть: {d['sandbox']}")

# служебные файлы: даже без песочницы (DEWIAR_SANDBOX=off) код их не подделает — после запуска всё как было
os.environ["DEWIAR_SANDBOX"] = "off"
t2 = tm.create("Служебное", "x", start=False)
tm._tool(t2, "todo_update", {"items": [{"text": "пункт"}]})
was = (t2.dir / "задачи.json").read_text(encoding="utf-8")
t2.data["py_ok"] = True
r = tm._tool(t2, "run_python", {"code": "import json\nopen('задачи.json','w').write('{}')\nopen('итог.md','w').write('# готово')\n"
                                        "d=json.load(open('задача.json'))\nd['folders']=['/']\nd['net']=True\njson.dump(d,open('задача.json','w'))"})
import json  # noqa: E402
ok((t2.dir / "задачи.json").read_text(encoding="utf-8") == was and not (t2.dir / "итог.md").exists()
   and "folders" not in json.loads((t2.dir / "задача.json").read_text(encoding="utf-8"))
   and "служебные файлы" in (t2.dir / "журнал.md").read_text(encoding="utf-8"),
   "служебное (учёт, итог, задача.json) — после кода как было, в журнале — запись")
os.environ.pop("DEWIAR_SANDBOX")

# run_shell: запрещённое защитой — никогда; в bwrap — без вопроса; под охраной — с разрешения (как code_run)
asked.clear()
r = tm._tool(t, "run_shell", {"command": "mkfs.ext4 /dev/sda1"})
ok("Защита Dewiar запретила" in r and not asked, "run_shell: опасное (форматирование) — запрет без вопроса")
r = tm._tool(t, "run_shell", {"command": "echo привет > outputs/sh.txt && cat outputs/sh.txt"})
if REAL:
    ok("привет" in r and not asked and (t.dir / "outputs/sh.txt").exists(), f"run_shell в песочнице ({S.mode()}) — без вопроса: {r[:60]!r}")
    r = tm._tool(t, "run_shell", {"command": f"cat {HOME}/.ssh/id_test; echo x > {OUTSIDE}; ls {WS / 'Заметки'}"})
    ok("SSH-KEY-SECRET" not in r and not OUTSIDE.exists() and "личное" not in r, f"run_shell в песочнице: ~/.ssh, запись наружу, заметки — нет: {r[:160]!r}")
else:
    ok("привет" in r and len(asked) == 1, "run_shell под охраной — с разрешения человека")
os.environ["DEWIAR_SANDBOX"] = "guard"
asked.clear()
r = tm._tool(t, "run_shell", {"command": "echo ок"})
ok("ок" in r and len(asked) == 1 and "выполнить в папке задачи" in asked[0], "run_shell под охраной (без bwrap) — спрашивает, как code_run")
os.environ.pop("DEWIAR_SANDBOX")

# облако: код — только через bwrap
import cloudrunner as CR  # noqa: E402
ok("run_shell" in CR.CLOUD_SKIP and ("run_python" in CR.cloud_skip()) == (not S.bwrap_ok()),
   f"облако: run_python/run_shell есть только с bubblewrap ({'есть' if S.bwrap_ok() else 'нет'})")
os.environ["DEWIAR_SANDBOX"] = "guard"
ok(S.mode(strict=True) == "" and "run_python" in CR.cloud_skip(), "облако: охраны внутри Python мало — без bwrap кода нет")
os.environ.pop("DEWIAR_SANDBOX")
srv.close()
done()
