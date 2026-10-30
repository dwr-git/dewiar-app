"""Плагин «Рекрутер» (владелец 30.10 прислал свой AI Recruiter: разбор резюме, оценка, «битва» кандидатов, красные флаги).
Встроенный плагин со своим кодом (data/plugins/recruiter/server.py, MCP по stdio):
— резюме из папки: Word, RTF, текст (PDF — тем же knowledge.extract ядра); повтор не заводится;
— без модели: ФИО, телефон, почта, Telegram, город, возраст, стаж, должность, зарплата, языки (rabota.by / hh и свободные);
— сигналы «уточнить»: стаж больше возможного по возрасту, senior при малом стаже, нет контактов;
— вакансия и отбор по словам (технологии весят больше); оценка Лиры по пяти критериям — итог по весам 40/30/13/10/7;
— воронка этапов и заметки; плагин встроенный, дело по будням, MCP отвечает."""
import json, os, subprocess, sys, tempfile, zipfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
os.environ["DEWIAR_PLUGIN_DATA"] = str(tmp / "data")
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


CV = tmp / "Резюме"
CV.mkdir()
(CV / "ivanov.txt").write_text("""Иванов Пётр Сергеевич
Мужчина, 41 год, родился 3 марта 1985
+375 (29) 123-45-67
ivanov.p@example.com
Проживает: Минск
Желаемая должность и зарплата
Главный бухгалтер
3 500 BYN на руки
Опыт работы — 12 лет 4 месяца
ООО «Альфа» — главный бухгалтер. Ведение учёта в 1С:Бухгалтерия 8.3, налоговая отчётность, МСФО, закрытие месяца.
ОАО «Бета» — бухгалтер участка основных средств, 1С, расчёт заработной платы.
Образование: БГЭУ, бухгалтерский учёт и аудит, 2007
Английский — B1
""", encoding="utf-8")
doc = ("<w:document xmlns:w='x'><w:body>" + "".join(f"<w:p><w:r><w:t>{t}</w:t></w:r></w:p>" for t in [
    "Петрова Анна Викторовна", "Женщина, 23 года", "Telegram: @anna_petrova", "Город: Гродно", "Должность: Senior бухгалтер",
    "Опыт работы 2 года 6 месяцев", "Бухгалтер-кассир, первичная документация, Excel.", "Образование: колледж, не окончено"]) + "</w:body></w:document>")
with zipfile.ZipFile(CV / "petrova.docx", "w") as z:
    z.writestr("word/document.xml", doc)
(CV / "sidorov.rtf").write_bytes(r"{\rtf1\ansi Sidorov Ivan\par Python developer\par Work experience 3 years\par Python, Django, PostgreSQL, Docker\par sidorov@example.org\par}".encode("cp1251"))
(CV / "~$temp.docx").write_bytes(b"lock")
(CV / "scan.txt").write_text("скан", encoding="utf-8")

sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(ROOT / "data/plugins/recruiter"))
import server as R  # noqa: E402

os.environ["DEWIAR_PLUGIN_SETTINGS"] = json.dumps({"folder": str(CV)})
r = R.add("")
names = sorted(x["name"] for x in r["added"])
ok(names == ["Sidorov Ivan", "Иванов Пётр Сергеевич", "Петрова Анна Викторовна"], f"три резюме из папки настроек (Word, RTF, текст): {names}")
ok(any("scan.txt" in p and "нет текста" in p for p in r["problems"]) and not any("~$" in p for p in r["problems"]),
   f"пустой файл — понятная причина; временные файлы Word — пропущены: {r['problems']}")
d = R.load()["cands"]
iv = next(c for c in d.values() if c["file"] == "ivanov.txt")
ok(iv["name"] == "Иванов Пётр Сергеевич" and iv["phone"].startswith("+375") and iv["email"] == "ivanov.p@example.com" and iv["city"] == "Минск"
   and iv["age"] == 41 and iv["exp_months"] == 12 * 12 + 4 and iv["position"] == "Главный бухгалтер" and "3 500 BYN" in iv["salary"]
   and iv["languages"] == ["Английский — B1"], f"факты без модели (формат rabota.by): {R.get(iv['id'])}")
ok(iv["flags"] == [], f"у Иванова уточнять нечего: {iv['flags']}")
pe = next(c for c in d.values() if c["file"] == "petrova.docx")
ok(pe["name"] == "Петрова Анна Викторовна" and pe["telegram"] == "@anna_petrova" and pe["city"] == "Гродно" and pe["age"] == 23 and pe["exp_months"] == 30,
   f"Word: ФИО, Telegram, город, возраст, стаж: {[pe.get(k) for k in ('name', 'telegram', 'city', 'age', 'exp_months')]}")
ok(any("не сходится" in f for f in pe["flags"]) is False and any("senior" in f for f in pe["flags"]),
   f"Senior при стаже 2,5 года — сигнал «уточнить»: {pe['flags']}")
pe2 = R.facts("Ким Олег\nМужчина, 25 лет\nОпыт работы 15 лет\n")
ok(any("не сходится" in f for f in R.flags(pe2, "")), "стаж 15 лет в 25 — «не сходится»")
si = next(c for c in d.values() if c["file"] == "sidorov.rtf")
ok("Python, Django" in si["text"] and si["exp_months"] == 36 and si["email"] == "sidorov@example.org", f"RTF читается: {si['text'][:80]!r}")
ok(R.add(str(CV))["already_known"] == 3 and len(R.load()["cands"]) == 3, "второй раз — не заводятся повторно")
one = R.add(str(CV / "ivanov.txt"))
ok(one["already_known"] == 1, "и один файл — тоже")

v = R.vacancy("Главный бухгалтер", "Опыт от 5 лет, 1С:Бухгалтерия 8.3, налоговая отчётность, МСФО, английский желательно. Минск, офис.")
ok(v["id"].startswith("v") and "МСФО" in v["key_terms"] and "1С" in " ".join(v["key_terms"]), f"вакансия и её ключевые слова: {v['key_terms']}")
m = R.shortlist("бухгалтер")
ok([x["name"] for x in m["items"]][0] == "Иванов Пётр Сергеевич" and m["items"][0]["words_match"] > m["items"][-1]["words_match"]
   and "МСФО" in m["items"][0]["has"] and "МСФО" in m["items"][1]["missing"], f"отбор по словам: Иванов первый: {[(x['name'], x['words_match']) for x in m['items']]}")
s1 = R.score(iv["id"], v["id"], {"hard_skills": 92, "experience": 95, "format_match": 80, "education": 85, "languages": 60},
             ["1С 8.3", "МСФО"], ["английский B1"], "Сильный главбух.")
ok(s1["total"] == round(92 * .4 + 95 * .3 + 80 * .13 + 85 * .1 + 60 * .07) and s1["place"] == 1 and s1["by"]["навыки"] == 92,
   f"итог — по весам, не «на глаз»: {s1}")
s2 = R.score(pe["id"], "бухгалтер", {"hard_skills": 40, "experience": 35})
ok(s2["total"] == round((40 * .4 + 35 * .3) / .7) and s2["place"] == 2 and s2["of"] == 2, f"часть критериев — итог по тем, что есть: {s2}")
ok("error" in R.score(pe["id"], v["id"], {"x": 1}), "без критериев — отказ, а не ноль")
L = R.lst(vacancy=v["id"])
ok([x["best_score"] for x in L["items"]] == [s1["total"], s2["total"]], "кандидаты под вакансию — по итогу")
R.update(pe["id"], "собеседование", "позвонить в пятницу")
c = R.get(pe["id"])
ok(c["stage"] == "собеседование" and c["notes"][-1]["text"] == "позвонить в пятницу" and R.lst(stage="собеседование")["total"] == 1,
   "воронка: этап и заметка")
ok("error" in R.update(pe["id"], "уволен"), "только свои этапы")
ok(R.lst(q="python")["total"] == 1, "поиск по словам в резюме")
R.update(si["id"], remove=True)
ok(len(R.load()["cands"]) == 2, "кандидата можно удалить")

env = dict(os.environ, DEWIAR_PLUGIN_DATA=str(tmp / "d2"), PYTHONPATH=str(ROOT / "core"))
msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "recruit_add", "arguments": {}}}]
p = subprocess.run([sys.executable, str(ROOT / "data/plugins/recruiter/server.py")], input="\n".join(json.dumps(x) for x in msgs) + "\n",
                   capture_output=True, text=True, env=env, timeout=60)
out = [json.loads(x) for x in p.stdout.splitlines() if x.strip()]
tl = out[1]["result"]["tools"] if len(out) > 1 else []
ok(len(tl) == 7 and all(t["annotations"]["readOnlyHint"] for t in tl) and sum(len(t["description"]) for t in tl) < 1400,
   f"семь действий, короткие описания (подсказка модели не раздувается): {sum(len(t['description']) for t in tl)}")
res = json.loads(out[2]["result"]["content"][0]["text"]) if len(out) > 2 else {}
ok(len(res.get("added", [])) == 3, f"через MCP — из папки настроек: {p.stderr[-200:]}")

import settings as ST  # noqa: E402
import plugins as PL  # noqa: E402
import tools as T  # noqa: E402
P = PL.Plugins(ST.Settings(tmp / "s.json"))
pp = P.items.get("recruiter")
ok(pp and pp["builtin"] and pp["icon"] == "🧑‍💼" and pp["jobs"] and set(pp["uses"]) <= set(T.TOOLS) and pp["mcp"]["main"]["command"] == "{python}",
   "встроенный плагин: значок целиком, дело по будням, только настоящие инструменты")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
