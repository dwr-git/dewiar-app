"""№538 (04.11, ПК 0.82.0): «Хорошо бы ассистент ставился туда, куда ставишь, без C:\\Документы: поставил на диск F — и вся
база туда же… и чтобы обновление не влияло на память». Обновление память и так не трогает (она — не в папке программы).
А папку ассистента («Документы\\Dewiar»: заметки, память, дневник, знания) раньше можно было только «переключить» на другую —
пустую, без переноса. Теперь студия → «Папка» → «Перенести…»: выбрать папку — ядро всё копирует, сверяет число файлов и размер,
и только тогда переключается; старая остаётся на месте. Выбрали корень диска — внутри него «Dewiar»; там уже папка Dewiar —
просто переключиться; мало места, папка внутри старой, чужое непустое — понятный отказ, ничего не меняется."""
import json, os, re, shutil, sys, tempfile, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.pop("DEWIAR_WORKSPACE", None)
os.environ.update(DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"))
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import workspace as W  # noqa: E402

conf = {"workspace": {"path": str(tmp / "Документы" / "Dewiar")}}
st = types.SimpleNamespace(get=lambda a, b=None: conf.get(a, {}).get(b) if b else conf.get(a))
ws = W.Workspace(st)
src = ws.ensure()
(src / "Заметки" / "Покупки.md").write_text("- хлеб\n- молоко\n", encoding="utf-8")
(src / "Знания").mkdir(exist_ok=True); (src / "Знания" / "договор.pdf").write_bytes(b"%PDF" + b"x" * 5000)
(src / "Память" / "Обо мне.md").write_text("# Обо мне\n- любит чай\n", encoding="utf-8")
n_src = sum(1 for f in src.rglob("*") if f.is_file())

drive = tmp / "F"; drive.mkdir(); (drive / "Игры").mkdir(); (drive / "фото.jpg").write_bytes(b"jpg")
r = ws.move_to(str(drive))
ok(r["path"] == str((drive / "Dewiar").resolve()) and not r["switched"], f"выбрали корень диска с файлами — внутри него «Dewiar»: {r['path']}")
new = Path(r["path"])
ok(r["files"] == n_src and (new / "Заметки" / "Покупки.md").read_text(encoding="utf-8").startswith("- хлеб")
   and (new / "Знания" / "договор.pdf").stat().st_size == 5004, f"всё скопировано: файлов {r['files']} из {n_src}")
ok((src / "Память" / "Обо мне.md").exists(), "старая папка осталась на месте (удалить — решает человек)")
ok(not list(drive.glob("*.перенос")), "временной папки не осталось")
ok((drive / "фото.jpg").exists() and (drive / "Игры").is_dir(), "чужие файлы на диске не тронуты")

conf["workspace"]["path"] = str(new)
r2 = W.Workspace(st).move_to(str(src))
ok(r2["switched"] and r2["files"] == 0 and r2["path"] == str(src.resolve()), "там уже папка Dewiar — просто переключиться, ничего не копируя")

conf["workspace"]["path"] = str(src)
for bad, why in [(str(src / "Заметки" / "тут"), "внутри"), ("", "укажите"), ("relative/path", "полный путь"), (str(src), "уже здесь")]:
    try:
        W.Workspace(st).move_to(bad); got = "перенеслось"
    except W.WorkspaceError as e:
        got = str(e)
    ok(why in got, f"«{bad or 'пусто'}» — отказ: {got}")
busy = tmp / "Чужое"; busy.mkdir(); (busy / "Dewiar").mkdir(); (busy / "Dewiar" / "чужой.txt").write_text("x")
(busy / "x.txt").write_text("x")
try:
    W.Workspace(st).move_to(str(busy)); got = "перенеслось"
except W.WorkspaceError as e:
    got = str(e)
ok("уже что-то есть" in got, f"непустая чужая папка (и «Dewiar» в ней чужая) — отказ: {got}")
real = shutil.disk_usage
W.shutil.disk_usage = lambda p: types.SimpleNamespace(free=10, total=10, used=0)
try:
    W.Workspace(st).move_to(str(tmp / "Мало")); got = "перенеслось"
except W.WorkspaceError as e:
    got = str(e)
finally:
    W.shutil.disk_usage = real
ok("мало места" in got and not (tmp / "Мало" ).exists() or not any((tmp / "Мало").iterdir()), f"мало места — отказ до копирования: {got}")

# ядро: ws_move — перенос и переключение тем же путём, что ws_set_path; детям — нельзя
cm = (ROOT / "core/engine_commands.py").read_text(encoding="utf-8")
h = cm[cm.index('if cmd == "ws_move":'):][:900]
ok("self.workspace.move_to(" in h and 'cmd = "ws_set_path"' in h and '"ws_move"' in cm[:2000], "ядро: ws_move → копия → ws_set_path; в детском режиме закрыто")

# студия: «Перенести…» — выбор папки, вопрос, ws_move, итог
from playwright.sync_api import sync_playwright  # noqa: E402
CORE = r"""(() => { window.calls = []; const ready = () => { if (!window.core) return setTimeout(ready, 5);
  core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; try { core.ws.close(); } catch (e) {} }
  core.call = async (c, a) => { calls.push([c, a]); if (c === "ws_move") return { path: "F:\\Dewiar", old: "C:\\Users\\u\\Documents\\Dewiar", files: 42, bytes: 1, switched: false };
    if (c === "ws_tree") return { root: "F:\\Dewiar", items: [] }; return {}; }; }; ready(); })();"""
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script("window.pywebview = { api: { pick_folder: () => Promise.resolve('F:\\\\') } };"); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(900)
    pg.evaluate("() => { S = Object.assign({}, S || {}, { ui: {}, llm: { profiles: {} }, features: {} }); window.ask = (t) => { window.asked = t; return Promise.resolve(true); }; }")
    pg.evaluate("() => $('nav button[data-p=\"folder\"]').click()"); pg.wait_for_timeout(300)
    ok(pg.inner_text("#f-move").strip() == "Перенести…", "кнопка — «Перенести…»")
    pg.click("#f-move"); pg.wait_for_timeout(500)
    ok("Старая папка останется" in (pg.evaluate("window.asked") or ""), "перед переносом — честный вопрос: что будет со старой папкой")
    ok(["ws_move", {"path": "F:\\"}] in pg.evaluate("calls"), "выбрана папка — ws_move")
    ok("Перенесено: файлов 42" in pg.inner_text("#toast") and "Старая папка осталась" in pg.inner_text("#toast"), f"итог: {pg.inner_text('#toast')!r}")
    b.close()
ok(not errs, f"без ошибок страницы: {errs[:2]}")
print("ALL OK" if not fails else f"FAILS: {len(fails)}")
sys.exit(1 if fails else 0)
