"""«Совет ИИ» видит документы (29.10, человек: «подключил папку с документами — Лира их видит и по ним рассуждает, а когда
собираю Совет ИИ, они эти документы не видят»). Совету — отрывки из «Документов» по вопросу (общие для всех, и ведущему
к итогу) и знания каждого персонажа (его базы и папки) — как в разговоре; в студии строкой — какие файлы смотрит совет;
в протоколе — «Документы: …». Документов нет — подсказка о них не добавляется."""
import sys, tempfile, threading, time, types
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))
import council as CM  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


CALLS = []


def fake_stream(prof, system, msgs, cancel):
    CALLS.append((system, msgs[0]["content"]))
    yield "Согласен, по договору срок — две недели."


CM.stream_chat = fake_stream
ws = Path(tempfile.mkdtemp())


class KB:
    def __init__(self, files): self.files = files
    def has_files(self): return bool(self.files)
    def search(self, q, limit=5, within=None):
        return [{"path": "Договор аренды.pdf", "text": "Арендатор предупреждает о выезде за 14 дней."}] if self.files else []


def host(files, kb_for=()):
    ev = []
    ps = [{"id": "lira", "name": "Лира", "character": "тёплая"}, {"id": "patrik", "name": "Патрик", "character": "строгий",
                                                                    "knowledge": [{"kind": "folder", "label": "Право"}] if "patrik" in kb_for else []}]
    h = types.SimpleNamespace(
        personas=types.SimpleNamespace(all=lambda: ps, get=lambda pid: next((p for p in ps if p["id"] == pid), None)),
        s=types.SimpleNamespace(get=lambda *a: {"persona": "lira"}.get(a[0]) if len(a) == 1 else (None if a[0] != "llm" else {})),
        emit=lambda kind, **k: ev.append(k), knowledge=KB(files),
        workspace=types.SimpleNamespace(ensure=lambda: ws),
        _persona_knowledge=lambda q, turn, p=None, quiet=False, hist=None: "\n\nИЗ БАЗЫ «Право»: Гражданский кодекс, ст. 610." if (p or {}).get("knowledge") else "")
    return h, ev


def run(files, kb_for=()):
    CALLS.clear()
    h, ev = host(files, kb_for)
    c = CM.Council(h)
    c.profile_for = lambda pid: ({"base_url": "http://x", "model": "m"}, "m")
    c.members = lambda: [{"id": "lira", "name": "Лира"}, {"id": "patrik", "name": "Патрик"}]
    c.start("За сколько дней предупредить хозяина о выезде?", ["lira", "patrik"])
    for _ in range(100):
        if c.cur and c.cur["done"]:
            break
        time.sleep(0.05)
    return c, ev


c, ev = run(True, kb_for=("patrik",))
r1 = [(s, u) for s, u in CALLS if "участник «Совета ИИ»" in s and "Ответь коллегам" not in s]
ok(len(r1) == 2 and all("Договор аренды.pdf" in u and "14 дней" in u for s, u in r1), "мнения — с отрывками из «Документов» человека")
ok(all("называй документ" in s for s, u in r1), "участникам сказано опираться на документы и называть их")
pat = next((s for s, u in r1 if "Ты — Патрик" in s), "")
lira = next((s for s, u in r1 if "Ты — Лира" in s), "")
ok("ст. 610" in pat and "ст. 610" not in lira, "свои знания персонажа — только у него (Патрик с базой «Право»)")
summ = next((u for s, u in CALLS if "ведущий" in s), "")
ok("Договор аренды.pdf" in summ, "ведущий подводит итог, видя документы")
d = next((e for e in ev if e.get("phase") == "docs"), None)
ok(d and d["files"] == ["Договор аренды.pdf"] and d["members"] == ["patrik"], f"в студию — какие файлы смотрит совет и у кого свои знания: {d}")
proto = (ws / c.cur["file"]).read_text(encoding="utf-8") if c.cur.get("file") else ""
ok("Документы: Договор аренды.pdf" in proto, "в протоколе — «Документы: …»")
ok(c.state()["docs"] == ["Договор аренды.pdf"], "и в состоянии совета (студия открылась позже)")

c, ev = run(False)
r1 = [(s, u) for s, u in CALLS if "участник «Совета ИИ»" in s and "Ответь коллегам" not in s]
ok(r1 and all("документ" not in s and "Из документов" not in u for s, u in r1) and not any(e.get("phase") == "docs" for e in ev),
   "документов нет — подсказки о них нет")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
