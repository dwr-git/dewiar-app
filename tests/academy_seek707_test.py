"""№707 (пакет 14.11, компьютер 0.96.0): «Нельзя перематывать видео». Видеоурок студия берёт из кэша ядра через сервер
окон (/academy-cache/…, №575 — Windows), а тот отдавал файл без Range — ползунок не перематывал. Теперь видео уроков —
как звук подкастов: 206 и Content-Range."""
import os, sys, tempfile, urllib.request
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TMP = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(TMP / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(TMP / "cfg")
for k in [k for k in os.environ if "proxy" in k.lower()]:
    os.environ.pop(k)
sys.path.insert(0, str(ROOT / "core")); sys.path.insert(0, str(ROOT / "ui"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from settings import STATE_DIR  # noqa: E402
(Path(STATE_DIR) / "academy").mkdir(parents=True, exist_ok=True)
whole = bytes(range(256)) * 4000
(Path(STATE_DIR) / "academy" / "dewiar.pro_09-docs.mp4").write_bytes(whole)
import app as UI  # noqa: E402
base = UI.ui_http_base()
got = urllib.request.urlopen(base + "academy-cache/dewiar.pro_09-docs.mp4", timeout=5)
ok(got.status == 200 and got.headers.get("Accept-Ranges") == "bytes" and got.headers.get("Content-Type") == "video/mp4" and got.read() == whole,
   "видео урока целиком — с Accept-Ranges")
rq = urllib.request.Request(base + "academy-cache/dewiar.pro_09-docs.mp4", headers={"Range": "bytes=500000-500099"})
got = urllib.request.urlopen(rq, timeout=5)
ok(got.status == 206 and got.read() == whole[500000:500100] and got.headers.get("Content-Range") == f"bytes 500000-500099/{len(whole)}",
   "перемотка: кусок с середины (206)")
try:
    urllib.request.urlopen(base + "academy-cache/..%2Fsettings.json", timeout=5); bad = True
except urllib.error.HTTPError:
    bad = False
ok(not bad, "чужие файлы не отдаём")
# 14.11 (владелец: «в справке старый ролик… видео обновил по FTP»): копия в кэше — по имени с версией сайта (?v=время файла)
import academy_cache as AC  # noqa: E402
cu = "https://dewiar.pro/dwrapp/cloud.php"
n0 = AC.local_name("https://dewiar.pro/dwrapp/academy/09-docs.mp4", cu)
n1 = AC.local_name("https://dewiar.pro/dwrapp/academy/09-docs.mp4?v=1794650000", cu)
n2 = AC.local_name("https://dewiar.pro/dwrapp/academy/09-docs.mp4?v=1794659999", cu)
ok(n0 == "09-docs.mp4" and n1 == "09-docs.v1794650000.mp4" and n1 != n2, f"заменили видео на сайте — новая копия, не старая: {n0} {n1} {n2}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
