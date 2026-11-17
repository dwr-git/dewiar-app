"""Б10 «Длинный документ» (docs/HARNESS.md, 17.11, харнесс «до идеала»): задача читает PDF и Word сама — file_read и
file_grep, без кода на Python (он просит разрешения). PDF — постранично, перед страницей «=== стр. N ===», чтобы модель
называла номер страницы. Заготовка экзамена — годовой отчёт на 120 страниц (≈250 тыс. знаков), 10 ключевых цифр 2025
года на известных страницах и те же показатели 2024 года на других (ловушка); проверка — ≥8 из 10 цифр с верной
страницей, выжимка на страницу."""
import json, re, zipfile
from task_mock import TMP, Host, Mock, ok  # noqa: E402
import exam_big as EB  # noqa: E402
import tasks as TK  # noqa: E402

tm = TK.TaskManager(Host(Mock({})))
t = tm.create("Отчёт", "Выжимка годового отчёта", start=False)
info = EB.make_fixture("longdoc", t.dir, 1)
ok((t.dir / "годовой_отчёт_2025.pdf").stat().st_size > 200_000 and info["pages"] == 120, "заготовка: PDF на 120 страниц")


def run(name, **a):
    return tm._tool(t, name, a)


r = run("file_read", path="годовой_отчёт_2025.pdf", start=1, end=4)
ok(r.startswith("1: === стр. 1 ===") and "Годовой отчёт за 2025 год" in r, f"file_read PDF — текст со страницами: {r[:90]!r}")
rev = info["facts"]["revenue"]
g = run("file_grep", pattern=r"выручка компании за 2025")
m = re.search(r"годовой_отчёт_2025\.pdf:(\d+):", g)
ok(m and "Выручка компании за 2025 год" in g, f"file_grep ищет внутри PDF: {g[:120]!r}")
around = run("file_read", path="годовой_отчёт_2025.pdf", start=max(1, int(m.group(1)) - 40) if m else 1, end=int(m.group(1)) if m else 2)
pages = re.findall(r"=== стр\. (\d+) ===", around)
ok(pages and int(pages[-1]) == rev["page"], f"по строке находки видно номер страницы: {pages[-1:] } = {rev['page']}")
# Word
doc = t.dir / "договор.docx"
with zipfile.ZipFile(doc, "w") as z:
    z.writestr("[Content_Types].xml", "<Types/>")
    z.writestr("word/document.xml", '<w:document xmlns:w="w"><w:body><w:p><w:r><w:t>Пункт 4.2. Оплата до 10-го числа.</w:t></w:r></w:p>'
               '<w:p><w:r><w:t>Пункт 5. Штраф 0,1 % в день.</w:t></w:r></w:p></w:body></w:document>')
r = run("file_read", path="договор.docx")
ok(r.startswith("1: Пункт 4.2") and "2: Пункт 5" in r, f"file_read Word — абзацы строками: {r[:80]!r}")
ok("договор.docx:" in run("file_grep", pattern="штраф"), "file_grep ищет внутри Word")
(t.dir / "скан.pdf").write_bytes(EB._pdf_pages([[""]]))
ok("Как исправить" in run("file_read", path="скан.pdf"), "PDF без текста — «что случилось — как исправить»")
specs = {x["name"]: x for x in tm._specs(t)}
ok("PDF" in specs["file_read"]["description"] and "стр. N" in specs["file_read"]["description"], "описание file_read говорит про PDF и страницы")

# ---------- проверка экзамена ----------
F = info["facts"]


def answer(values, prose_len=2600):
    rows = "\n".join(f"| {f['name']} | {EB._num_ru(values(f), f['kind'])} | {f['page']} |" for f in F.values())
    prose = ("Компания завершила год с ростом выручки и прибыли; ключевые направления — производство, экспорт и сервис. " * 40)[:prose_len]
    return f"# Выжимка\n\n{prose}\n\n| Показатель | Значение | Стр. |\n|---|---|---|\n{rows}\n"


def check(text):
    (t.dir / "outputs").mkdir(exist_ok=True)
    (t.dir / "outputs" / "выжимка.md").write_text(text, encoding="utf-8")
    return {c["name"]: c for c in EB.check_longdoc(t.dir, json.loads(json.dumps(info)))}


c = check(answer(lambda f: f["value"]))
ok(all(x["ok"] for x in c.values()), f"верная выжимка — сдано: {[x['detail'] for x in c.values()]}")
c = check(answer(lambda f: f["prev"]))
bad = [x for x in c.values() if not x["ok"]]
ok(bad and "2024" in bad[0]["detail"], f"цифры 2024 года вместо 2025 — не сдано, с пометкой: {bad[0]['detail'][:120] if bad else ''}")
c = check(answer(lambda f: f["value"], prose_len=400))
ok(any(not x["ok"] and "знаков" in x["detail"] for x in c.values()), "выжимка в два абзаца — не «на страницу»")
c = check(answer(lambda f: f["value"]).replace(f"| {rev['page']} |", f"| {rev['page'] + 1} |"))
ok(all(x["ok"] for x in c.values()), "одна страница указана неверно — всё ещё 9 из 10, сдано")
sc = next(s for s in json.loads((EB.Path(__file__).resolve().parent.parent / "data/exam/scenarios.json").read_text(encoding="utf-8"))["scenarios"]
          if s["id"] == "big_b10_longdoc")
ok(sc["big"]["fixture"] == "longdoc" and "2025" in sc["big"]["goal"] and "выжимка.md" in sc["big"]["goal"], "сценарий экзамена Б10 — в scenarios.json")
from task_mock import done  # noqa: E402
done()
