"""«Каркас хода» (план «Качество», шаг 3; отзыв Alex 21.11: «самое неприятное — сказала, что сделала, а на самом деле нет»):
ответ сверяется с журналом хода (что программа сделала на самом деле — из рентгена); утверждает сделанное без основания —
правдой из журнала. Решает модель коротким вопросом с журналом, а не словарь фраз; слова — только грубый отбор, стоит ли
спрашивать (иначе ни вопроса, ни задержки). За переключателем llm.ledger — замер на стенде."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import ledger as L  # noqa: E402
import settings as SET  # noqa: E402

asked = []


def model(answer_json):
    def call(sys_, user_):
        asked.append(user_)
        return answer_json
    return call


ok(L.check("как дела?", "Всё хорошо, спасибо! А у вас?", [], model('{"unbacked": ["x"]}')) == [] and not asked,
   "болтовня без «сделала» — модель не спрашиваем (нет задержки)")
r = L.check("напиши в Избранное «тест»", "Написала, готово.", [], model('{"unbacked": ["сообщение в Избранное"]}'))
ok(r == ["сообщение в Избранное"] and "ничего не выполняла" in asked[-1], f"«Написала, готово» при пустом журнале — без основания: {r}")
acts = [{"name": "type_text", "title": "Ввод текста", "ok": False, "result": "поле не найдено"}]
r = L.check("напиши в Избранное", "Написала, готово.", acts, model('{"unbacked": ["сообщение в Избранное"]}'))
ok(r and "Ввод текста: НЕ вышло (поле не найдено)" in asked[-1], "в вопросе модели — журнал: что не вышло и почему")
fix = L.honest(r, acts)
ok(fix.startswith("Поправлюсь: на самом деле это не сделано — сообщение в Избранное.") and "Ввод текста — поле не найдено" in fix,
   f"правда из журнала: {fix}")
ok(L.check("включи радио", "Включила радио.", [{"name": "play_radio", "title": "Радио", "ok": True}], model('{"unbacked": []}')) == [],
   "сделано на самом деле — ворота молчат")
ok(L.check("x", "Готово.", [], model("не понимаю")) == [] and L.check("x", "Готово.", [], lambda a, b: 1 / 0) == [],
   "модель ответила не JSON или упала — ответ не трогаем")
ok(L.need_check("I've sent the email to Anna.") and L.need_check("Done!"), "по-английски — тоже отбирается (принцип, не язык)")
ok(SET.DEFAULTS["llm"]["ledger"] is False, "за переключателем llm.ledger — пока проба (стенд: --set llm.ledger=true)")
src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok('if self.s.get("llm", "ledger")' in src and "ledger.check(text, turn.full, acts_, _ask_)" in src and "✋ Ответ утверждает сделанное" in src,
   "ход: ворота в конце, поправка — проверкой «✋» (видна в рентгене и в замере по мозгам)")
# телефон, «Руки» (группа 21.11: «находит контакт, но не пишет текст в поле», а Лира — «Написала, готово»): ввод сверяется с экраном
import re as _re, shutil as _sh, subprocess as _sp, json as _js  # noqa: E402
js = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
grab = lambda name: _re.search(r"async function " + name + r"\(.*?\n}\n", js, _re.S).group(0)   # noqa: E731
if _sh.which("node"):
    prog = grab("handsAfter") + grab("handsTool") + r"""
const sleep = () => Promise.resolve(); const S = {}; const saveS = () => {}; const handsOff = () => "OFF";
let screen = "";
const D = { handsType: () => "Ввела текст.", handsScreen: () => screen };
(async () => {
  screen = "[3] поле: Привет, это тест\n[4] кнопка: Отправить"; const a = await handsTool("phone_type", { id: 3, text: "Привет, это тест" });
  screen = "[3] поле: Сообщение\n[4] кнопка: Отправить"; const b = await handsTool("phone_type", { id: 3, text: "Привет, это тест" });
  const c = await handsTool("phone_type", { id: 3, text: "Привет", submit: true });
  console.log(JSON.stringify([a, b, c]));
})();"""
    out = _sp.run(["node", "-e", prog], capture_output=True, text=True, timeout=30)
    r = _js.loads(out.stdout or "[]") if out.stdout.strip().startswith("[") else []
    ok(len(r) == 3 and not r[0].startswith("Ошибка") and r[1].startswith("Ошибка: текст в поле не появился") and not r[2].startswith("Ошибка"),
       f"телефон: текст в поле есть — сделано; нет — «Ошибка: текст в поле не появился» (модель не скажет «написала»); с отправкой — не проверяем {out.stderr[-200:]}")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
