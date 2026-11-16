"""Экзамен «как в жизни» (18.10: «самые успешные экзамены взял для видео, и почти ни одно реально не сработало —
эмуляция в экзаменах отличается от реальной практики»). Отличия были такие: каждое испытание с чистого листа и одна
просьба (а на съёмке просили снова — и модель копировала свой прошлый ответ: «Я Лира.», «Звоню» без звонка), фразы с
запятыми и двоеточиями (распознавание речи их не ставит), план дня в экзамене шёл мимо быстрого пути телефона.
Теперь: группа «Как в жизни» на компьютере и телефоне — просьбы повторяются, фразы как из распознавания; проверки
tool_count (действие на каждую просьбу) и distinct (ответы не копия). «Граница на грубость» из экзамена убрана —
её ведёт код (boundaries.py, телефон — своей фразой), экзамену там проверять нечего (поведение — в boundaries_test).
Быстрые пути понимают речь без знаков: «отправь сообщение андрею привет как дела», «а теперь лёхе напиши…»,
«позвони ей ещё раз» (тому же близкому через Dewiar), «набери людмилу снова»."""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import srctext  # noqa: E402 — текст исходника вместе с частями (tests/srctext.py)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


pc = {x["id"]: x for x in json.loads((ROOT / "data/exam/scenarios.json").read_text(encoding="utf-8"))["scenarios"]}
ex = (ROOT / "android/assets/www/exam.js").read_text(encoding="utf-8")
ok("rude" not in pc and 'id: "rude"' not in ex, "«граница на грубость» — не в экзамене (её ведёт код)")
ok(all(i in pc for i in ("life_about_twice", "life_youtube", "life_plan_done")) and pc["life_youtube"]["tool_count"] == {"play_youtube": 3}
   and pc["life_about_twice"]["distinct"] is True and all(not any(c in s["say"] for c in ",:") for s in pc["life_plan_done"]["steps"]),
   "компьютер: «как в жизни» — повтор просьб, действие на каждую, фразы без знаков")
ok(all(f'id: "{i}"' in ex for i in ("life_about_twice", "life_call_again", "life_send_two", "life_plan_done"))
   and "tool_count: { close_call: 3 }" in ex and "tool_count: { close_send: 2 }" in ex, "телефон: «как в жизни» — звонок снова, два сообщения, план и отметки")
src = srctext.text(ROOT, "core/exam.py")
ok('sc.get("tool_count")' in src and 'sc.get("distinct")' in src and 'env["DEWIAR_EXAM_LAUNCH"]' in src,
   "компьютер: проверки «на каждую просьбу» и «не копия»; браузер и программы в экзамене — записываются, а не запускаются")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("function planQuick(text) {                          // и в экзамене" in app and "if (examOn()) return null;" not in app.split("function doneQuick", 1)[1][:200],
   "телефон: план и отметки в экзамене — тем же быстрым путём, что у человека")

from playwright.sync_api import sync_playwright  # noqa: E402
tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for x in ("entities.js", "speechnorm.js", "skins.css", "skins.js"):
    shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1200)
    r = pg.evaluate("""async () => {
      window.DewiarCall = {}; const calls = [], sends = [];
      clCall = async (pid, video) => { calls.push([pid, !!video]); };                                   // eslint-disable-line
      clSend = async (pid, text) => { sends.push([pid, text]); return { to: pid }; };                 // eslint-disable-line
      const st = clLoad(); st.people = [{ pid: "p1", name: "Людмила Исаева", devs: [{ dev: "d" }] }, { pid: "p2", name: "Андрей", devs: [{ dev: "d" }] },
        { pid: "p3", name: "Лёха", devs: [{ dev: "d" }] }];
      const out = {};
      for (const q of ["позвони людмиле исаевой по видеосвязи", "позвони ей ещё раз", "набери людмилу снова"]) out[q] = ((await quick(q)) || {}).say || null;
      out.calls = calls.slice();
      for (const q of ["отправь сообщение андрею привет как дела", "а теперь лёхе напиши во сколько встречаемся завтра", "андрей напиши стих"]) out[q] = ((await quick(q)) || {}).say || null;
      out.sends = sends.slice();
      out.life = examLifeChecks({ tool_count: { close_call: 3 }, distinct: true }, [
        { say: "a", answer: "Звоню через Dewiar: Людмила.", tools: [{ name: "close_call", result: "ok" }] },
        { say: "b", answer: "Звоню через Dewiar: Людмила.", tools: [] }, { say: "c", answer: "Ок", tools: [{ name: "close_call" }] }]);
      return out; }""")
    ok(r["calls"] == [["p1", True], ["p1", True], ["p1", False]] and all(r[q] for q in ("позвони людмиле исаевой по видеосвязи", "позвони ей ещё раз", "набери людмилу снова")),
       f"телефон: звонок близкой — и «позвони ей ещё раз», и «набери людмилу снова» — снова ей, через Dewiar: {r['calls']}")
    ok(r["sends"] == [["p2", "Привет как дела"], ["p3", "Во сколько встречаемся завтра"]] and r["андрей напиши стих"] is None,
       f"телефон: сообщения без двоеточий и с именем впереди — отправлены; «Андрей, напиши стих» — не сообщение: {r['sends']}")
    ok([c["ok"] for c in r["life"]] == [False, False] and "2 из 3" in r["life"][0]["detail"],
       f"экзамен телефона: звонок лишь в двух шагах из трёх и повтор слово в слово — не сдано: {r['life']}")
    ok(not errs, f"без ошибок на странице: {errs[:2]}")
    b.close()
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
