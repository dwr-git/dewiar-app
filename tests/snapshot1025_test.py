"""«Слепок знаний» (0.45.2, владелец: «одним нажатием выгрузить всё одним файлом… зашифрован… с другой стороны Markdown,
который будет работать, даже когда программа устареет… восстановить без перетирания данных»). Ядро (core/backup.py):
- открытый .zip — обычный архив: README, manifest, заметки .md, данные JSON; без ключей, паролей и сейфа;
- закрытый .dwr — под паролем, со всем (и сейф); без пароля не открыть; старые .dwbak читаются;
- «Добавить недостающее» (merge): удалённое вернулось, своё изменённое осталось, а вариант из слепка — рядом копией;
  в JSON (платежи, напоминания) дополнены записи с новыми id, свои не тронуты; настройки — свои; сейф — одноимённые свои;
- «Вернуть как было» (replace) — как раньше; перед любым восстановлением — слепок «до восстановления»;
- пароль слепка запоминается на этом компьютере и в слепок не попадает; автокопия с ним — закрытая."""
import io, json, os, shutil, sys, tempfile, zipfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg"); os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st")
import backup as B  # noqa: E402
from vault import Vault  # noqa: E402
cfg, st, ws, out = tmp / "cfg", tmp / "st", tmp / "ws", tmp / "out"
for d in (cfg / "personas", st, ws / "Заметки", out):
    d.mkdir(parents=True, exist_ok=True)
(cfg / "settings.json").write_text(json.dumps({"user_name": "Миша", "llm": {"profiles": {"x": {"api_key": "sk-SECRET"}}}}), encoding="utf-8")
(cfg / "payments.json").write_text(json.dumps({"bills": [{"id": "b1", "name": "Газ"}, {"id": "b2", "name": "Свет"}], "pays": [{"id": "p1", "bill": "b1", "amount": 10}]}), encoding="utf-8")
(cfg / "personas" / "lira.json").write_text("{}", encoding="utf-8")
(st / "reminders.json").write_text(json.dumps([{"id": "r1", "text": "позвонить"}]), encoding="utf-8")
(ws / "Заметки" / "Дача.md").write_text("# Дача\nкупить семена", encoding="utf-8")
(ws / "Заметки" / "Ремонт.md").write_text("# Ремонт\nобои", encoding="utf-8")
v = Vault(cfg / "vault.bin", cfg / "vault.key"); v.put("Вайфай", "кот123"); v.put("Почта", "pass-1")
bk = B.Backup(cfg, st, ws, v, "0.45.2")
# открытый
z = bk.make(out, fmt="zip")
ok(z["name"].endswith("(открытый).zip") and z["format"] == "zip", f"открытый слепок — .zip: {z['name']}")
with zipfile.ZipFile(z["path"]) as zz:
    names = zz.namelist(); man = json.loads(zz.read("manifest.json"))
    ok("README.txt" in names and "workspace/Заметки/Дача.md" in names and "config/payments.json" in names, "внутри — README, заметки .md, платежи JSON")
    ok("sk-SECRET" not in zz.read("config/settings.json").decode() and "vault.json" not in names, "без ключей и без сейфа")
ok(man["stats"].get("notes") == 2 and man["stats"].get("bills") == 2 and man["stats"].get("reminders") == 1 and man["stats"].get("personas") == 1,
   f"в описании — сколько заметок, счетов, дел, персонажей: {man['stats']}")
# закрытый
bk.pw_set("слепок-пароль")
ok(bk.pw_get() == "слепок-пароль", "пароль слепка запомнен на этом компьютере")
d = bk.make(out, password=bk.pw_get())
ok(d["name"].endswith(".dwr") and d["encrypted"] and d["vault"] == 2, f"закрытый .dwr — с паролем и сейфом: {d['name']}")
raw = Path(d["path"]).read_bytes()
ok(b"sk-SECRET" not in raw and "кот123".encode() not in raw, "внутри всё зашифровано")
try:
    bk.open(d["path"], "не тот"); ok(False, "чужой пароль не подходит")
except B.BackupError as e:
    ok("пароль" in str(e), "чужой пароль — «пароль не подходит»")
with zipfile.ZipFile(io.BytesIO(B.unseal_pw(raw[raw.index(b"\n", len(B.HEAD)) + 1:], "слепок-пароль"))) as zz:
    ok("config/snapshot.pw" not in zz.namelist() and "vault.json" in zz.namelist(), "запомненный пароль в слепок не попадает, сейф — да")
lst = [x["format"] for x in bk.list(out)]
ok(sorted(lst) == ["dwr", "zip"], f"в списке — оба слепка: {lst}")
# старая копия .dwbak
old = out / "Dewiar — копия 2026-10-01 10-00.dwbak"; shutil.copy(d["path"], old)
ok(any(x["name"] == old.name for x in bk.list(out)) and bk.open(old, "слепок-пароль")[0]["encrypted"], "старые копии .dwbak видны и открываются")
# чужой zip
fz = out / "чужой.zip"
with zipfile.ZipFile(fz, "w") as zz:
    zz.writestr("a.txt", "x")
try:
    bk.describe(fz); ok(False, "чужой zip")
except B.BackupError as e:
    ok("не слепок" in str(e), f"чужой zip — «это не слепок Dewiar»: {e}")
# изменения после слепка
(ws / "Заметки" / "Дача.md").unlink()
(ws / "Заметки" / "Ремонт.md").write_text("# Ремонт\nобои и плитка — новое", encoding="utf-8")
(ws / "Заметки" / "Новая.md").write_text("свежая", encoding="utf-8")
pj = json.loads((cfg / "payments.json").read_text()); pj["bills"] = [{"id": "b2", "name": "Свет (мой)"}, {"id": "b3", "name": "Вода"}]
(cfg / "payments.json").write_text(json.dumps(pj), encoding="utf-8")
(cfg / "settings.json").write_text(json.dumps({"user_name": "Михаил", "llm": {"profiles": {"x": {"api_key": "sk-NEW"}}}}), encoding="utf-8")
(st / "reminders.json").write_text(json.dumps([{"id": "r2", "text": "новое дело"}]), encoding="utf-8")
v.put("Почта", "pass-2"); v._items = None
r = bk.restore(d["path"], bk.pw_get(), mode="merge")
ok(r["mode"] == "merge" and r["before"] and Path(r["before"]).exists(), "перед восстановлением — слепок «до восстановления»")
ok((ws / "Заметки" / "Дача.md").read_text() == "# Дача\nкупить семена", "удалённая заметка вернулась")
ok("плитка — новое" in (ws / "Заметки" / "Ремонт.md").read_text(), "изменённая заметка — ваша, не перетёрта")
side = [p.name for p in (ws / "Заметки").glob("Ремонт (из слепка *).md")]
ok(len(side) == 1 and (ws / "Заметки" / side[0]).read_text() == "# Ремонт\nобои", f"вариант из слепка — рядом копией: {side}")
ok((ws / "Заметки" / "Новая.md").exists(), "новая заметка (после слепка) — на месте")
pj = json.loads((cfg / "payments.json").read_text())
ok([b["id"] for b in pj["bills"]] == ["b2", "b3", "b1"] and pj["bills"][0]["name"] == "Свет (мой)", f"платежи: свои как есть, недостающий счёт добавлен: {pj['bills']}")
ok([x["id"] for x in json.loads((st / "reminders.json").read_text())] == ["r2", "r1"], "дела: своё новое на месте, из слепка добавлено")
ok(json.loads((cfg / "settings.json").read_text())["user_name"] == "Михаил", "настройки — свои, не из слепка")
v2 = Vault(cfg / "vault.bin", cfg / "vault.key")
ok(v2.get(v2.find("Почта")["id"])["value"] == "pass-2" and v2.find("Вайфай") is not None, "сейф: своя «Почта» не перетёрта, «Вайфай» на месте")
ok(r["files"] >= 1 and r["merged"] >= 2 and r["beside"] == 1, f"итог для человека: {r}")
# replace — как раньше
r2 = bk.restore(z["path"], "", mode="replace")
ok((ws / "Заметки" / "Ремонт.md").read_text() == "# Ремонт\nобои" and r2["files"] > 0, "«Вернуть как было» — как в слепке")
ok(json.loads((cfg / "settings.json").read_text())["llm"]["profiles"]["x"]["api_key"] == "sk-NEW", "…а ключи этого компьютера остались (в открытом слепке их нет)")
# забыть пароль
bk.pw_set(""); ok(bk.pw_get() == "" and not (cfg / "snapshot.pw").exists(), "пароль можно забыть")
# merge_json по-простому
ok(B.merge_json({"a": [1, 2], "b": {"x": 1}}, {"a": [2, 3], "b": {"x": 9, "y": 2}, "c": 5}) == {"a": [1, 2, 3], "b": {"x": 1, "y": 2}, "c": 5}, "слияние JSON: недостающее добавлено, своё не заменено")
src = (ROOT / "core/engine_audio.py").read_text(encoding="utf-8")
ok("self.backup.make(folder, password=self.backup.pw_get(), auto=True)" in src, "автокопия — с запомненным паролем (закрытая, с сейфом)")
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
