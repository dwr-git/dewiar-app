"""Телефон: исправления по первым отзывам.
1. «Готово!» на всё: модель сделала калькулятор (make_app) и ничего не сказала — раньше в историю шёл пустой ответ, следующий
   вопрос склеивался с «сделай калькулятор», и модель снова отвечала «Готово». Теперь — что сделано и где найти, в историю тоже.
2. «Что мы делали на этой неделе»: журнал дней (days.json) — коротко в подсказке, подробно — recall; open_made открывает сделанное.
3. Фото: на экране с кнопкой «Сохранить», show_photo показывает снова; модель знает, что снимок уже на экране.
4. Связь: «не в домашней сети» — только для домашнего адреса; сбой связи — одна повторная попытка и запись для отчёта.
5. «Позвони» без имени — «Кому позвонить?», а не звонок наугад."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


www = Path(tempfile.mkdtemp()) / "www"
shutil.copytree(ROOT / "android/assets/www", www)
shutil.copy(ROOT / "ui/assets/entities.js", www / "entities.js")
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 393, "height": 852}); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(800)
    R = pg.evaluate("""async () => {
      const R = {}, seen = [];
      Object.assign(S.llm, { kind: "openai", base_url: "http://127.0.0.1:9/v1", model: "m", api_key: "" });
      window.ensureBrain = async () => {};
      window.say = () => {};
      const HTML = "<html><body><button>1</button></body></html>";
      let mode = "app";
      window.llmStream = async (msgs, tools, onText) => {
        seen.push(JSON.parse(JSON.stringify(msgs)));
        if (mode === "app") {                       // модель вызывает make_app и молчит — и после результата тоже
          if (!msgs.some(m => m.role === "tool")) return { text: "", calls: [{ id: "c1", name: "make_app", args: JSON.stringify({ title: "Калькулятор", html: HTML }) }], finish: "tool_calls" };
          return { text: "", calls: [], finish: "stop" };
        }
        if (mode === "net1") { mode = "ok"; throw Object.assign(new Error("связь с сервером оборвалась"), { net: true, raw: "failed to connect to dewiar.pro after 15000ms", url: "https://dewiar.pro/dwrapp/cloud.php" }); }
        onText("Солнечно, плюс двенадцать."); return { text: "Солнечно, плюс двенадцать.", calls: [], finish: "stop" };
      };
      await ask("Кодер, сделай калькулятор на html");
      await new Promise(r => setTimeout(r, 300));
      R.bot1 = document.querySelector("#bot").textContent;
      R.hist1 = history.slice(-1)[0];
      mode = "ok";
      await ask("Какая погода сегодня?");
      const last = seen[seen.length - 1];
      R.lastUser = last.filter(m => m.role === "user").slice(-1)[0].content;
      R.sys = last[0].content;
      R.bot2 = document.querySelector("#bot").textContent;
      R.recall = recall(7, "калькулятор");
      R.openMade = await runTool("open_made", { title: "кальк" });
      await new Promise(r => setTimeout(r, 200));
      R.viewOpen = !!document.querySelector("#appview.on");
      R.toolNames = toolSpecs().map(t => t.name);
      // фото
      D.saveFile("last_photo.txt", "data:image/jpeg;base64,QUJD");
      R.photoTool = await runTool("show_photo", {});
      await new Promise(r => setTimeout(r, 120));
      R.photoCard = document.querySelector("#card").innerHTML;
      let saved = null; D.saveDownloadB64 = (n, m, b) => { saved = [n, m, b]; return "Загрузки/" + n; };
      savePhoto(); R.saved = saved;
      // связь
      R.errCity = netErr("failed to connect to dewiar.pro/1.2.3.4 (port 443) after 15000ms", "https://dewiar.pro/dwrapp/cloud.php");
      R.errHome = netErr("failed to connect to /192.168.1.46 (port 9099)", "http://192.168.1.46:9099/dwrapp/cloud.php");
      R.errRefused = netErr("ECONNREFUSED", "https://dewiar.pro/x");
      D.setPref("net_inc", "[]");
      mode = "net1";
      const n0 = seen.length;
      await ask("Погода на завтра?");
      for (let i = 0; i < 40 && seen.length < n0 + 2; i++) await new Promise(r => setTimeout(r, 100));
      await new Promise(r => setTimeout(r, 400));
      R.retried = seen.length - n0; R.bot3 = document.querySelector("#bot").textContent;
      R.inc = JSON.parse(prefGet("net_inc") || "[]");
      // файлы задач: текст и картинки открываются в приложении
      R.viewPy = fileViewHtml("main.py", btoa("print(1) <b>"));
      R.viewPng = fileViewHtml("chart.png", "iVBORw0KGgo=");
      R.viewable = ["a.md", "b.csv", "c.png", "d.html"].every(n => VIEWABLE.test(n)) && !VIEWABLE.test("e.pptx");
      // звонок без имени
      await ask("Позвони");
      R.call = document.querySelector("#bot").textContent;
      return R;
    }""")
    b.close()

ok("Калькулятор" in R["bot1"] and "Сделанное" in R["bot1"] and "Готово." != R["bot1"].strip(), f"сделала и промолчала — говорит, что сделано и где найти: {R['bot1']}")
ok(R["hist1"]["role"] == "assistant" and "Калькулятор" in R["hist1"]["content"], "в историю — не пустой ответ")
ok(R["lastUser"].split("(Сообщение пользователя)\n")[-1].strip() == "Какая погода сегодня?", f"следующий вопрос не склеивается с прошлой просьбой: {R['lastUser'][:120]}")
ok(R["bot2"].startswith("Солнечно"), "на новый вопрос — новый ответ, а не «Готово»")
ctx_ = R["sys"] + R["lastUser"]   # с 0.5x справка к ходу — в реплике человека (putContext), не в системной подсказке
ok("ЧТО БЫЛО НЕДАВНО" in ctx_ and "«Калькулятор»" in ctx_ and "сделай калькулятор" in ctx_.lower(), "в подсказке — что было за неделю и что сделано")
ok("калькулятор" in R["recall"].lower() and "Вы:" in R["recall"], f"recall вспоминает разговор: {R['recall'][:160]}")
ok("на экране" in R["openMade"] and R["viewOpen"], "open_made открывает сделанное на экране")
ok({"recall", "open_made", "show_photo"} <= set(R["toolNames"]), "новые инструменты у модели")
ok("снова на экране" in R["photoTool"] and "Сохранить" in R["photoCard"] and "<img" in R["photoCard"], "show_photo — снимок снова на экране с кнопкой «Сохранить»")
ok(R["saved"] and R["saved"][1] == "image/jpeg" and R["saved"][2] == "QUJD" and R["saved"][0].endswith(".jpg"), "снимок сохраняется в «Загрузки»")
ok("домашней" not in R["errCity"] and "дома" not in R["errCity"] and "связь" in R["errCity"], f"в городе — про связь, не про домашнюю сеть: {R['errCity']}")
ok("дома" in R["errHome"], f"домашний сервер — «вы не дома»: {R['errHome']}")
ok("домашней" not in R["errRefused"], "отказ облака — не «домашняя сеть»")
ok(R["retried"] >= 2 and R["bot3"].startswith("Солнечно"), f"сбой связи — повторная попытка, ответ пришёл ({R['retried']}): {R['bot3']}")
# пакеты 22.10 №189 и 23.10 №208: повтор помог — сбой «прошёл сам», в отчёт разработчику не идёт (журнал очищен)
ok(all(x.get("ok") for x in R["inc"]), f"повтор помог — сбой не считается для отчёта: {R['inc']}")
ok("<pre" in R["viewPy"] and "&lt;b&gt;" in R["viewPy"] and "data:image/png;base64,iVBOR" in R["viewPng"] and R["viewable"], "файлы задач: код и текст — текстом, картинки — картинкой, pptx — в «Загрузки»")
ok(R["call"].strip() == "Кому позвонить?", f"«Позвони» без имени — переспрашивает: {R['call']}")
ok(not errors, f"без ошибок JavaScript: {errors}")
print("\nИТОГ:", "всё хорошо" if not fails else f"ошибок {len(fails)}")
sys.exit(1 if fails else 0)
