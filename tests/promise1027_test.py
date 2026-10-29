"""YouTube 27.10: «Попросил открыть сайт, но он этого не сделал. Агент ответил, что сейчас открою, но ничего не произошло»
(своя модель на компьютере). Проверка «сказал, а не сделал» ловила только настоящее время («открываю сайт»); теперь и
будущее («сейчас открою», «запущу», «позвоню») и прошедшее («открыла»), если просили именно это и за ход ничего не вызвано.
Предложение («если хотите — открою», «могу открыть») — не обещание. Телефон — то же (CLAIMS в app.js). Экзамен: open_site."""
import json, os, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from quality import action_claim  # noqa: E402
for ask, ans, want in (("открой сайт ютуб", "Сейчас открою.", True), ("открой, пожалуйста, википедию", "Хорошо, сейчас открою Википедию.", True),
                       ("запусти блокнот", "Запущу через секунду.", True), ("открой сайт", "Открыла YouTube.", True),
                       ("расскажи про погоду", "Если хотите, открою прогноз.", False), ("открой сайт", "Могу открыть, скажите адрес.", False),
                       ("что такое лира", "Лира — созвездие. Открою секрет: оно маленькое.", False), ("открой сайт", "Какой сайт открыть?", False)):
    ok(bool(action_claim(ask, ans)) == want, f"«{ask}» → «{ans}»: {'обещание' if want else 'не обещание'}")
ok(not action_claim("открой сайт ютуб", "Сейчас открою.", called={"open_url"}), "открыл по-настоящему — не придираемся")

JS = r"""
const src = require('fs').readFileSync(process.argv[1], 'utf8');
globalThis.CAM_ASK_RX = /камер/; globalThis.PHOTO_ASK_RX = /фот/; globalThis.HANDS_SET = new Set();
const m = src.indexOf('const MAKE_ASK_RX'); eval(src.slice(m, src.indexOf('\n', m) + 1).replace('const MAKE_ASK_RX', 'globalThis.MAKE_ASK_RX'));
const i = src.indexOf('const CLAIMS = ['), j = src.indexOf('\n];', i);
eval(src.slice(i, j + 3).replace('const CLAIMS', 'globalThis.CLAIMS'));
const k = src.indexOf('function claimedAction'), f = src.slice(k, src.indexOf('\n}\n', k) + 2);
eval(f.replace('function claimedAction', 'globalThis.claimedAction = function'));
const cases = JSON.parse(process.argv[2]);
console.log(JSON.stringify(cases.map(([ask, ans, called]) => !!claimedAction(ans, called ? new Set(called) : null, ask))));
"""
cases = [["открой сайт ютуб", "Сейчас открою.", None], ["открой ютуб", "Если хотите, открою.", None], ["открой ютуб", "Открываю YouTube.", ["open_url"]],
         ["открой телеграм", "Открыла.", ["open_app"]], ["расскажи", "Сейчас открою секрет.", None]]
r = subprocess.run(["node", "-e", JS, str(ROOT / "android/assets/www/app.js"), json.dumps(cases, ensure_ascii=False)], capture_output=True, text=True)
got = json.loads(r.stdout.strip() or "[]") if r.returncode == 0 else []
ok(got == [True, False, False, False, False], f"телефон: «сейчас открою» без open_url — проверка; предложение и настоящее открытие — нет: {got} {r.stderr[-200:]}")
sc = json.loads((ROOT / "data/exam/scenarios.json").read_text(encoding="utf-8"))["scenarios"]
ok(any(s["id"] == "open_site" and s.get("tool", {}).get("open_url") for s in sc), "экзамен: «открой сайт» — open_url")
# идея №42 (29.10): «сделай программу: 3D-модель…» — «Собираю», «Готово», «Теперь дерево», а make_app не вызван
P = "Сделай программу: 3D-модель атома и дерево размышлений"
long = "Делаю так: " + "сначала объясню, как устроен атом, " * 12
cases = [[P, "Собираю!", None], [P, "Готово.", None], [P, "Хорошо, теперь делаю дерево размышлений.", None], [P, "Готово, она на экране.", ["make_app"]],
         ["как у тебя дела?", "Готово.", None], [P, long, None], ["Сделай 3D-модель солнечной системы", "Сейчас, строю планеты.", None]]
r = subprocess.run(["node", "-e", JS, str(ROOT / "android/assets/www/app.js"), json.dumps(cases, ensure_ascii=False)], capture_output=True, text=True)
got = json.loads(r.stdout.strip() or "[]") if r.returncode == 0 else []
ok(got == [True, True, True, False, False, False, True], f"телефон: «собираю / готово» на просьбу сделать программу без make_app — проверка: {got} {r.stderr[-200:]}")
src = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("Но программа так и не собралась" in src, "и после просьбы снова без make_app — честно говорит, что не собралась")
print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
