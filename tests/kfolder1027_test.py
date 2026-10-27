"""YouTube 27.10: «При создании персонажа нет возможности добавить знания из локальной папки, только с сервера. Но если
я работаю локально, то желательно включить такую возможность». Студия → персонаж → «Знания» → «Папка на компьютере…»:
папка читается в фоне (knowledge.py, отдельно от общих своих папок), перед ответом персонаж ищет в ней — без интернета и
входа, — и модель получает отрывки с именами файлов. В общий поиск по документам папки персонажей не попадают."""
import json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path
from types import SimpleNamespace
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_CONFIG_DIR=str(tmp / "ucfg"), DEWIAR_STATE_DIR=str(tmp / "ust"))
sys.path.insert(0, str(ROOT / "core"))
docs = tmp / "Рецепты бабушки"; docs.mkdir()
(docs / "Борщ.md").write_text("# Борщ\n\nСвёклу тушить отдельно с ложкой уксуса, чтобы борщ остался красным. Чеснок — в самом конце.\n", encoding="utf-8")
(docs / "Блины.txt").write_text("Блины на кефире: два яйца, литр кефира, соль, сахар, сода на кончике ножа.\n", encoding="utf-8")
other = tmp / "Работа"; other.mkdir()
(other / "Отчёт.md").write_text("Свёкла в отчёте о закупках: 40 кг.\n", encoding="utf-8")

from knowledge import Knowledge  # noqa: E402
ws = SimpleNamespace(root=tmp / "ws")
kn = Knowledge(ws, tmp / "kn.json", folders=lambda: [str(other)], extra=lambda: [str(docs)])
kn.refresh_folders()
r = kn.search("как сделать чтобы борщ был красным", within=[str(docs)])
ok(r and r[0]["path"].endswith("Борщ.md") and "уксуса" in r[0]["text"], f"поиск в папке персонажа: {[x['path'] for x in r]}")
ok(all("Работа" not in x["path"] for x in kn.search("свёкла", within=[str(docs)])), "только в его папке — чужая не попадает")
g = kn.search("свёкла")
ok(g and all("Рецепты" not in x["path"] for x in g), f"общий поиск по документам — без папок персонажей: {[x['path'] for x in g]}")

from personas import Personas  # noqa: E402
P = Personas()
pid = P.save({"name": "Бабушка", "gender": "female", "character": "Ты — бабушка.", "knowledge": [
    {"kind": "folder", "path": str(docs), "label": "Рецепты бабушки"}, {"kind": "folder", "label": "без пути"}, {"kind": "lib", "id": "7", "label": "Библия"}]})
kb = P.get(pid)["knowledge"]
ok([b.get("kind") for b in kb] == ["folder", "lib"] and kb[0]["path"] == str(docs), f"папка сохраняется у персонажа: {kb}")

from engine_brain import BrainMixin  # noqa: E402
ev = []
fake = SimpleNamespace(knowledge=kn, emit=lambda *a, **k: ev.append(k))
out = BrainMixin._persona_local_knowledge(fake, "борщ красный", [{"kind": "folder", "path": str(docs), "label": "Рецепты бабушки"}])
ok("ТВОЯ БАЗА ЗНАНИЙ (папки на компьютере" in out and "«Борщ.md»" in out and "уксуса" in out, "модель получает отрывок с именем файла")
out2 = BrainMixin._persona_local_knowledge(fake, "квантовая хромодинамика", [{"kind": "folder", "path": str(docs), "label": "Рецепты бабушки"}])
ok("ничего не нашлось" in out2 and "«Рецепты бабушки»" in out2, "не нашлось — так и сказать")

# студия: кнопка «Папка на компьютере…»
LLM, PORT = free(), free()
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM)], env=dict(os.environ, MOCK_LOG=str(tmp / "a.log")))
cfg = tmp / "cfg"; cfg.mkdir()
(cfg / "settings.json").write_text(json.dumps({"persona": "lira", "audio": {"sounds": False}, "ui": {"news_seen": "99.0.0", "welcome": "done"},
                                               "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "updates": {"auto_check": False},
                                               "llm": {"active": "m", "profiles": {"m": {"name": "Мок", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM}/v1", "model": "mock"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws2"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8")
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
for _ in range(150):
    time.sleep(0.2)
    if (cfg / "token").exists():
        break
time.sleep(2)
tok = (cfg / "token").read_text().strip()
errs = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1400, "height": 1000})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.add_init_script("window.pywebview = { api: { pick_folder: () => Promise.resolve(%s) } };" % json.dumps(str(docs)))
        pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}"); time.sleep(3)
        pg.click('nav button[data-p="personas"]'); time.sleep(0.8)
        pg.locator("#pgrid .card", has_text="Лира").first.locator(".edit").click(); time.sleep(0.6)
        pg.click("#kb-folder"); time.sleep(0.4)
        ok("📁 Рецепты бабушки" in pg.inner_text("#e-kb"), f"в «Знаниях» — папка: {pg.inner_text('#e-kb')[:80]!r}")
        pg.click("#e-save"); time.sleep(1.0)
        pj = json.loads((cfg / "personas" / "lira.json").read_text(encoding="utf-8"))
        ok(pj.get("knowledge") == [{"kind": "folder", "path": str(docs), "label": "Рецепты бабушки"}], f"сохранено у Лиры: {pj.get('knowledge')}")
        ok(not errs, f"без ошибок на странице: {errs[:2]}")
        b.close()
finally:
    core.terminate(); mock.terminate()

print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
