"""Дневник и душа: править и удалять (28.10, владелец: «Дневник и Душа — может сделать возможность править или удалять?»).
Настоящее ядро: запись дня и ночная запись в «Дневник/ГГГГ-ММ-ДД.md»; diary_entry_save правит текст (у ночной — и
название), diary_entry_delete удаляет одну запись (ночную — вместе с выводами «на завтра»), последняя — и файл дня;
soul_delete стирает душу. Студия: у записи кнопки «Поправить» и «Удалить», правка на месте."""
import asyncio, json, os, socket, subprocess, sys, tempfile, time
from datetime import date
from pathlib import Path
from playwright.sync_api import sync_playwright
import websockets
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = ROOT / "tests"
PY = os.environ.get("DEWIAR_PY") or sys.executable
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


tmp = Path(tempfile.mkdtemp()); PORT = free(); cfg = tmp / "cfg"; cfg.mkdir(); ws = tmp / "ws"
day = date.today().isoformat()
(ws / "Дневник").mkdir(parents=True)
(ws / "Дневник" / f"{day}.md").write_text(
    "# Дневник — сегодня\n\n### 14:20 · Лира\n\nМысль дня про чайник.\n\n"
    "## 🌙 Ночью — о прожитом дне · «Тень в логах» 🕯\n\nТекст ночи про логи.\n\n**На завтра:**\n- напомнить про IP\n", encoding="utf-8")
(cfg / "settings.json").write_text(json.dumps({"persona": "lira", "audio": {"sounds": False}, "ui": {"news_seen": "99.0.0", "welcome": "done"},
    "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "updates": {"auto_check": False}}))
st = tmp / "st"; st.mkdir()
(st / "diary.json").write_text(json.dumps({"insights": {"day": day, "title": "Тень в логах", "lines": ["напомнить про IP"]},
                                           "titles": {day: {"title": "Тень в логах", "mood": "🕯", "who": "Лира"}}}, ensure_ascii=False))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(st), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(ws), DEWIAR_DRY_TOOLS=str(tmp / "dry.jsonl"))
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
R = {}


async def run():
    ws_ = None
    for _ in range(300):
        await asyncio.sleep(0.2)
        if (cfg / "token").exists():
            try:
                ws_ = await websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None); break
            except OSError:
                continue
    await ws_.send(json.dumps({"cmd": "hello", "token": (cfg / "token").read_text().strip()}))
    n = [0]

    async def call(cmd, **args):
        n[0] += 1; i = n[0]; await ws_.send(json.dumps({"id": i, "cmd": cmd, "args": args}))
        while True:
            e = json.loads(await asyncio.wait_for(ws_.recv(), 20))
            if e.get("type") == "reply" and e.get("id") == i:
                return e
    R["save"] = await call("diary_entry_save", day=day, i=1, text="Новый текст ночи.\n\n**На завтра:**\n- позвонить маме", title="Светлый вечер")
    R["after_save"] = (ws / "Дневник" / f"{day}.md").read_text(encoding="utf-8")
    R["empty"] = await call("diary_entry_save", day=day, i=0, text="  ")
    R["del"] = await call("diary_entry_delete", day=day, i=1)
    R["after_del"] = (ws / "Дневник" / f"{day}.md").read_text(encoding="utf-8")
    R["diary_json"] = json.loads((st / "diary.json").read_text(encoding="utf-8"))
    R["del2"] = await call("diary_entry_delete", day=day, i=0)
    R["soul_save"] = await call("soul_save", persona="Лира", text="# Душа — Лира\n\n## Кто я\n\nТест.")
    R["soul_del"] = await call("soul_delete", persona="Лира")
    await ws_.close()


try:
    asyncio.run(run())
    a = R["after_save"]
    ok("«Светлый вечер»" in a and "Новый текст ночи." in a and "Текст ночи про логи" not in a and "Мысль дня про чайник" in a and "## 🌙" in a,
       "ночная запись поправлена: текст и название, дневная запись на месте")
    ok(not R["empty"].get("ok", True) or R["empty"].get("error"), "пустую запись сохранить нельзя — лучше удалить")
    b = R["after_del"]
    ok("🌙" not in b and "Мысль дня про чайник" in b, "удалена одна ночная запись, дневная осталась")
    dj = R["diary_json"]
    ok(not (dj.get("insights") or {}).get("lines") and day not in (dj.get("titles") or {}), "с ночной записью ушли и её выводы «на завтра»")
    ok(not (ws / "Дневник" / f"{day}.md").exists(), "удалили последнюю запись — нет и файла дня")
    ok(R["soul_del"].get("ok", True) and not (R["soul_del"].get("data") or {}).get("text") and not list((ws / "Душа").glob("*.md")) if (ws / "Душа").exists() else True,
       "«Стереть душу» — файла души нет")
finally:
    core.terminate()

# студия: кнопки у записей и правка на месте (отдельное ядро с новым файлом дня)
(ws / "Дневник" / f"{day}.md").write_text("# Дневник — сегодня\n\n### 14:20 · Лира\n\nМысль дня про чайник.\n", encoding="utf-8")
PORT2 = free(); env["DEWIAR_PORT"] = str(PORT2); (cfg / "token").unlink(missing_ok=True)
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core2.log", "w"), stderr=subprocess.STDOUT)
try:
    for _ in range(150):
        time.sleep(0.2)
        if (cfg / "token").exists():
            break
    time.sleep(2); tok = (cfg / "token").read_text().strip(); errs = []
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1400, "height": 1000})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT2}"); time.sleep(2.5)
        pg.click('nav button[data-p="diary"]'); time.sleep(1.2)
        ok(pg.locator("#d-page .dentry [data-ed]").count() == 1 and pg.locator("#d-page .dentry [data-del]").count() == 1, "у записи — «Поправить» и «Удалить»")
        pg.hover("#d-page .dentry"); pg.click("#d-page [data-ed]"); time.sleep(0.3)
        pg.fill("#dent-text", "Мысль дня про самовар."); pg.click("#dent-save"); time.sleep(1.2)
        ok("самовар" in pg.inner_text("#d-page") and "самовар" in (ws / "Дневник" / f"{day}.md").read_text(encoding="utf-8"), "правка на месте — сохранилась в файл")
        ok(not errs, f"без ошибок на странице: {errs[:2]}")
        b.close()
finally:
    core.terminate()
print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
