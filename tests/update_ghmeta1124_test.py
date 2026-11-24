"""№1005 (24.11, Linux Mint): «Версия не обновляется». dewiar.pro из сети человека не открывался (latest.json: timed out), и
программа даже не узнавала о новой версии — запасной путь GitHub работал, только когда сайт сам его назвал. Теперь: сайт не
ответил (нет связи, тайм-аут, 5xx) — сведения о выпуске берём с GitHub (Dewiar-latest.json выпуска открытой копии, его кладёт
release.yml), файл — оттуда же, sha256 сверяется как всегда. Сайт ответил «нет такого» (4xx), свой адрес обновлений
или выключено updates.mirror_github — GitHub не трогаем."""
import hashlib, json, os, subprocess, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"))
for k in [k for k in os.environ if "proxy" in k.lower()]:
    os.environ.pop(k)
sys.path.insert(0, str(ROOT / "core"))
import updater as UP  # noqa: E402
UP.UPDATE_EVERY = UP.UPDATE_JITTER = 0
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


DATA = os.urandom(200_000)
NAME = "dewiar-assistant_99.3.0_all.deb"
MODE = {"site": "down", "gh_sha": hashlib.sha256(DATA).hexdigest()}
HITS = []


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def do_GET(self):
        HITS.append(self.path)
        if self.path.startswith("/site/"):
            code = 404 if MODE["site"] == "404" else 502
            self.send_response(code); self.send_header("Content-Length", "0"); self.end_headers(); return
        if self.path.endswith("Dewiar-latest.json"):
            body = json.dumps({"name": "Dewiar", "version": "99.3.0", "source": "github", "deb": f"{BASE}/gh/{NAME}",
                               "sha256": MODE["gh_sha"], "size": len(DATA)}).encode()
        else:
            body = DATA
        self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{srv.server_port}"
UP.GH_JSON = f"{BASE}/gh/Dewiar-latest.json"
UP.MAC = False
UP.WIN = False


class S:
    def __init__(self, url="", mirror=True):
        self.url, self.mirror = url, mirror

    def get(self, *k):
        if k == ("updates", "url"):
            return self.url
        if k == ("updates", "mirror_github"):
            return self.mirror
        return None


def run(name, site, **kw):
    MODE["site"] = site
    HITS.clear()
    u = UP.Updater(S(**kw), "1.0.66", tmp / name)
    return u, u.check()


# сайт обновлений — на порту, где никто не слушает (как «timed out» у человека): нет связи
UP.DEFAULT_URL = "http://127.0.0.1:9/dwrapp/latest.json"
u, i = run("a", "down")
ok(i and i["version"] == "99.3.0" and Path(i["path"]).read_bytes() == DATA, f"сайт недоступен — версия и файл с GitHub: {i and i.get('version')}")
ok(any(h.endswith("Dewiar-latest.json") for h in HITS), "спросили Dewiar-latest.json выпуска открытой копии")
ok(u.last["error"] == "", f"ошибки в «Обновлениях» нет: {u.last['error']!r}")

# сайт отвечает 5xx — тоже GitHub
UP.DEFAULT_URL = f"{BASE}/site/latest.json"
u, i = run("b", "502")
ok(i and i["version"] == "99.3.0", "сайт отвечает 502 — сведения с GitHub")

# сайт ответил «нет такого» (404) — не подменяем, ждём сайт
u, i = run("c", "404")
ok(i is None and not any("Dewiar-latest" in h for h in HITS), "сайт ответил 404 — GitHub не трогаем")

# выключено updates.mirror_github — не трогаем
UP.DEFAULT_URL = "http://127.0.0.1:9/dwrapp/latest.json"
u, i = run("d", "down", mirror=False)
ok(i is None and not HITS, "updates.mirror_github выключено — GitHub не трогаем")

# свой адрес обновлений (своя сборка, компания) — GitHub не подставляем
u, i = run("e", "down", url="http://127.0.0.1:9/own/latest.json")
ok(i is None and not HITS, "свой адрес обновлений — GitHub не подставляем")

# подменённый файл (sha256 не тот) — не принят
MODE["gh_sha"] = "0" * 64
u, i = run("f", "down")
ok(i is None and not list((tmp / "f" / "updates").glob("*.deb")), f"sha256 не совпал — файл не принят: {u.last['error'][:80]}")

# release.yml кладёт Dewiar-latest.json: проверяем сам кусок на настоящих файлах
yml = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
seg = yml[yml.index("python3 - <<'PY'"):]
code = seg[seg.index("\n") + 1:seg.index("\n          PY")]
code = "\n".join(line[10:] if line.startswith(" " * 10) else line for line in code.splitlines())
d = tmp / "dist"; d.mkdir()
(d / "dewiar-assistant_1.0.67_all.deb").write_bytes(b"deb"); (d / "Dewiar-Setup-1.0.67-online.exe").write_bytes(b"exe")
(d / "Dewiar-Setup-1.0.67.exe").write_bytes(b"full")
r = subprocess.run([sys.executable, "-c", code], cwd=d, env=dict(os.environ, V="1.0.67", R="https://github.com/x/y/releases/download/v1.0.67"),
                   capture_output=True, text=True)
j = json.loads((d / "Dewiar-latest.json").read_text()) if (d / "Dewiar-latest.json").exists() else {}
ok(j.get("version") == "1.0.67" and j.get("deb", "").endswith("/dewiar-assistant_1.0.67_all.deb")
   and j.get("sha256") == hashlib.sha256(b"deb").hexdigest(), f"release.yml: Linux — полный адрес и sha256 ({r.stderr[-200:]})")
ok(j.get("windows", {}).get("exe", "").endswith("Dewiar-Setup-1.0.67-online.exe") and j["windows"]["sha256"] == hashlib.sha256(b"exe").hexdigest(),
   "release.yml: Windows — компактный установщик, sha256")
ok("dist/Dewiar-latest.json" in yml, "release.yml прикладывает Dewiar-latest.json к выпуску")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
