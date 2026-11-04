"""Пакет здоровья 20.10, 22:17, и отзыв владельца:
№147 — «сам не проверяет свои обновления, и по просьбе не может»: инструмент app_update — «проверь обновления».
№153 — Windows: «Обновление 0.38.95 не скачалось: [WinError 32] файл занят другим процессом» — прежний пакет занят
       (антивирус, открытый установщик): кладём рядом под другим именем, старые — убираем, когда освободятся.
Владелец, телефон: «Звук на нуле — включить и прочитать» выскочило ложно сразу после записи голоса, со следующей
       записью исчезло: распознаватель телефона на время записи глушит звук и возвращает не сразу — ждём ~2 с."""
import os, subprocess, sys, tempfile, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import tools as T  # noqa: E402

ok("app_update" in T.TOOLS and T.TOOLS["app_update"][2] == "safe", "инструмент «проверь обновления» есть и не спрашивает разрешения")


class Up:
    def __init__(self, info=None, err=""):
        self.info, self.err, self.calls = info, err, 0

    def check(self, **kw):
        self.calls += 1
        return self.info

    def public(self):
        return {"current": "0.38.95", "error": self.err}


fn = T.TOOLS["app_update"][3]
u = Up({"version": "0.38.96"})
r = fn({}, {"engine": types.SimpleNamespace(updater=u)})
ok(u.calls == 1 and "0.38.96" in r and "нажмите, чтобы обновить" in r and "сама не ставь" in r, f"есть новая — проверила сейчас же и сказала, как поставить: {r[:90]}")
r = fn({}, {"engine": types.SimpleNamespace(updater=Up())})
ok("последняя версия Dewiar 0.38.95" in r, f"нового нет — так и говорит: {r}")
r = fn({}, {"engine": types.SimpleNamespace(updater=Up(err="dewiar.pro: timeout"))})
ok("не получилось" in r and "«Проверить обновления»" in r, f"сайт недоступен — честно и где проверить руками: {r[:80]}")
import engine_answer as EA  # noqa: E402
ok("app_update" in EA.INFO_TOOLS, "это «узнать»: после него — ответ словами, а не «Готово»")

# Windows: занятый файл не срывает обновление
import updater as UP  # noqa: E402
import hashlib  # noqa: E402
data = b"dewiar-update" * 1000
sha = hashlib.sha256(data).hexdigest()


class Resp:
    status_code, headers = 200, {}
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def raise_for_status(self): pass
    def iter_bytes(self, n): yield data


import httpx  # noqa: E402
httpx.stream = lambda *a, **k: Resp()
u = UP.Updater(types.SimpleNamespace(get=lambda *a, **k: None), "0.38.95", tmp / "st")
u.dir.mkdir(parents=True, exist_ok=True)
(u.dir / "dewiar.deb").write_bytes(b"old")
real = Path.replace
busy = {"n": 0}


def fake_replace(self, target):
    if Path(target).name == "dewiar.deb" and not busy["n"]:
        busy["n"] += 1
        raise PermissionError(32, "файл занят другим процессом")
    return real(self, target)


Path.replace = fake_replace
real_unlink = Path.unlink
Path.unlink = lambda self, missing_ok=False: (_ for _ in ()).throw(PermissionError(32, "занят")) if self.name == "dewiar.deb" else real_unlink(self, missing_ok=missing_ok)
try:
    p = u._download({"url": "https://example.test/dewiar.deb", "sha256": sha, "version": "0.38.96"})
    ok(p.exists() and p.read_bytes() == data and p.name != "dewiar.deb", f"прежний пакет занят — новый рядом, под другим именем: {p.name}")
except Exception as e:  # noqa: BLE001
    ok(False, f"занятый файл сорвал скачивание: {e}")
finally:
    Path.replace, Path.unlink = real, real_unlink

# телефон: звук «на нуле» сразу после записи — подождать
from playwright.sync_api import sync_playwright  # noqa: E402
www = Path(tempfile.mkdtemp()) / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
errs = []
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 820})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    R = pg.evaluate("""async () => { D.mock = false; let vol = 0; D.volume = () => vol; S.textMode = false; const n0 = sayN;
        sttT0 = Date.now() - 3000; say('Напомню сегодня в 21:15.');
        setTimeout(() => { vol = 40; }, 700);                  // распознаватель вернул звук через 0,7 с
        await new Promise(r => setTimeout(r, 1300));
        const a = [sayN - n0, !!document.getElementById('vol-up')];
        stopVoice && stopVoice(); vol = 0; const n1 = sayN; say('А теперь звук правда на нуле.');
        await new Promise(r => setTimeout(r, 2600));
        const c = [sayN - n1, ((document.getElementById('vol-up') || {}).textContent || ''), volMuted, document.getElementById('card').innerHTML.slice(0, 60)];
        D.mock = true; return [a, c]; }""")
    ok(R[0] == [1, False], f"сразу после записи звук вернулся — ответ голосом, без «Звук на нуле»: {R[0]}")
    ok(R[1][0] == 0 and "Звук на нуле" in R[1][1], f"звук правда на нуле — кнопка, как раньше (через ~2 с): {R[1]}")
    ok(not errs, f"без ошибок JavaScript: {errs[:2]}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
