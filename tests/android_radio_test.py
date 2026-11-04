"""Радио на телефоне: просьба поставить радио не открывает сайты или Яндекс Музыку.
Радио играет внутри приложения: быстрые команды без модели («включи радио», «поставь джаз», «Маяк», «дальше»,
«пауза», «продолжи», «выключи радио»); модель получает инструмент play_radio и включает станцию сама, а не сайт;
станция не отвечает — следующая; нет в своём списке — каталог radio-browser; пока ассистент слушает и говорит —
радио тише; плашка сверху с паузой и «выключить». Заглушка телефона вместо Java (MediaPlayer)."""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
ok_all = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    ok_all.append(bool(c))


def free():
    import socket
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


LLM = free()
www = Path(tempfile.mkdtemp()) / "www"
shutil.copytree(ROOT / "android/assets/www", www)
shutil.copy(ROOT / "ui/assets/entities.js", www / "entities.js")
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)   # живое лицо Эвы
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
# как в сборке (android/tools/build_apk.sh): свой список станций — тот же, что у компьютера
radio = json.loads((ROOT / "data/radio.json").read_text(encoding="utf-8"))
radio["stations"].insert(0, {"name": "Мёртвая волна", "url": "https://dead.example/stream", "tags": "проверка", "aliases": ["мертвая волна"]})
radio["stations"].insert(1, {"name": "Живая волна", "url": "https://live.example/stream", "tags": "проверка", "aliases": ["живая волна"]})
radio["stations"].insert(2, {"name": "Тихая волна", "url": "https://silent.example/stream", "tags": "тишина", "aliases": ["тихая волна"]})
radio["stations"].insert(3, {"name": "Запасная тишины", "url": "https://spare.example/stream", "tags": "тишина", "aliases": []})
radio["stations"].insert(4, {"name": "Вязкий эфир", "url": "https://slow.example/stream", "tags": "вязкая", "aliases": ["вязкий эфир"]})
radio["stations"].insert(5, {"name": "Вязкий второй", "url": "https://slow2.example/stream", "tags": "вязкая", "aliases": []})
(www / "radio.js").write_text("window.RADIO_LIST = " + json.dumps(radio, ensure_ascii=False) + ";", encoding="utf-8")
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM)])
time.sleep(1)
CATALOG = []


def proxy(route):
    req = route.request
    if req.method == "OPTIONS":
        return route.fulfill(status=204, headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "*"})
    try:
        r = urllib.request.urlopen(urllib.request.Request(req.url, data=req.post_data_buffer, method=req.method,
                                                          headers={"Content-Type": "application/json"}), timeout=20)
        body, status, ctype = r.read(), r.status, r.headers.get("Content-Type", "application/json")
    except urllib.error.HTTPError as e:
        body, status, ctype = e.read(), e.code, "application/json"
    route.fulfill(status=status, body=body, headers={"Access-Control-Allow-Origin": "*", "Content-Type": ctype})


def catalog(route):
    CATALOG.append(route.request.url)
    route.fulfill(status=200, headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"},
                  body=json.dumps([{"name": "Радио Шансон Москва", "url_resolved": "https://chanson.example/live", "tags": "chanson", "countrycode": "RU"},
                                   {"name": "Шансон Плюс", "url": "https://chanson2.example/live", "tags": "chanson"}], ensure_ascii=False))


try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 393, "height": 852}, device_scale_factor=2)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route(f"http://127.0.0.1:{LLM}/**", proxy)
        pg.route("**/json/stations/search**", catalog)
        pg.route("https://dewiar.pro/**", lambda r: r.abort())
        pg.goto((www / "index.html").as_uri())
        pg.wait_for_timeout(800)
        pg.evaluate(f"""() => {{ Object.assign(S.llm, {{ kind: "openai", base_url: "http://127.0.0.1:{LLM}/v1", model: "chat", name: "тест" }}); saveS(); }}""")

        def say(t, wait=900):
            pg.evaluate("t => ask(t)", t)
            pg.wait_for_timeout(wait)
            return pg.evaluate("""() => ({ bot: document.querySelector('#bot').textContent, st: radio.state(), log: Dewiar._radio.log.slice(),
                chip: !document.querySelector('#radiobox').hidden, chipName: document.querySelector('#rchip b').textContent,
                paused: document.querySelector('#rchip').classList.contains('paused') })""")

        r = say("Включи радио")
        ok(r["st"]["state"] == "playing" and r["chip"] and r["chipName"] == r["st"]["name"] and r["log"][-1].startswith("play"),
           f"«Включи радио» — играет здесь же, без модели: {r['st']['name']} ({r['bot']})")
        ok(r["chip"], "плашка: название станции, пауза, выключить")
        geo = pg.evaluate("""() => { const c = document.querySelector('#rchip').getBoundingClientRect(), t = document.querySelector('#top').getBoundingClientRect(),
            h = document.querySelector('#rhint'); return { top: c.top, head: t.bottom, hint: h.textContent, shown: getComputedStyle(h).opacity === '1' && h.offsetHeight > 0,
            state: getComputedStyle(document.querySelector('#state')).display }; }""")
        ok(geo["top"] >= geo["head"], f"плашка под пластинкой, на кнопки сверху не наезжает: {geo['top']:.0f} ≥ {geo['head']:.0f}")
        ok(geo["shown"] and "микрофон" in geo["hint"] and "дальше" in geo["hint"] and geo["state"] == "none",
           f"подсказка: голосом — после нажатия на микрофон ({geo['hint']})")
        pg.wait_for_timeout(600)
        ok(pg.evaluate("orb && orb.vinyl") == r["st"]["name"], f"как на компьютере: вместо облика крутится пластинка с названием станции ({pg.evaluate('orb && orb.vinyl')})")
        pg.screenshot(path=str(www.parent / "radio-vinyl.png"))
        r = say("поставь джаз")
        ok(r["st"]["state"] == "playing" and r["st"]["name"] in ("Jazz", "Radio Swiss Jazz", "Secret Agent"), f"«поставь джаз» — джазовая станция: {r['st']['name']}")
        first = r["st"]["name"]
        r = say("дальше")
        ok(r["st"]["state"] == "playing" and r["st"]["name"] != first, f"«дальше» — другая станция: {first} → {r['st']['name']}")
        r = say("пауза")
        ok(r["st"]["state"] == "paused" and r["paused"] and r["chip"], "«пауза» — на паузе, плашка остаётся")
        ok(pg.evaluate("orb && orb.vinyl") is None, "на паузе пластинка не крутится — снова облик персонажа")
        r = say("продолжи")
        ok(r["st"]["state"] == "playing" and not r["paused"], "«продолжи» — снова играет")
        r = say("Маяк")
        ok(r["st"]["name"] != "Маяк", "одно слово «Маяк» без глагола — не перехватываем (может быть вопрос)")
        r = say("включи маяк")
        ok(r["st"]["state"] == "playing" and r["st"]["name"] == "Маяк", f"«включи маяк» — по названию: {r['st']['name']}")
        r = say("включи мертвую волну", 1500)
        ok(r["st"]["state"] == "playing" and r["st"]["name"] == "Живая волна" and "play Мёртвая волна" in r["log"],
           f"станция не отвечает — следующая похожая: {r['log'][-3:]}")
        n0 = len(r["log"])
        r = say("включи фонарик")
        ok(len(r["log"]) == n0 and "Фонарик" in r["bot"], "«включи фонарик» — фонарик, радио не трогаем")
        pg.evaluate("setState('listening')")
        duck_on = pg.evaluate("Dewiar._radio.duck")
        pg.evaluate("setState('idle')")
        ok(duck_on is True and pg.evaluate("Dewiar._radio.duck") is False, "пока слушаю и отвечаю — радио тише, потом громкость возвращается")
        # «включи лёгкую музыку» — спокойная станция без модели; «следующая станция» — каждый раз новая, не по кругу
        r = say("включи легкую музыку")
        ok(r["st"]["state"] == "playing" and any(t in next(x["tags"] for x in radio["stations"] if x["name"] == r["st"]["name"]) for t in ("релакс", "спокойно", "поп")),
           f"«включи лёгкую музыку» — спокойная станция сразу, без модели: {r['st']['name']}")
        names = [r["st"]["name"]]
        for _ in range(5):
            r = say("включи следующую станцию", 700)
            names.append(r["st"]["name"])
        ok(len(set(names)) == 6 and r["st"]["state"] == "playing", f"«следующая станция» 5 раз — каждый раз новая, без круга: {names}")
        r = say("включи станцию тихая волна", 1800)
        ok(r["st"]["state"] == "playing" and r["st"]["name"] != "Тихая волна" and "play Тихая волна" in r["log"],
           f"станция «заиграла», но молчит — сама включается другая: {r['st']} {r['log'][-6:]}")
        pg.evaluate("Dewiar._focusLoss()"); pg.wait_for_timeout(150)
        paused_focus = pg.evaluate("radio.state().state")
        pg.evaluate("setState('listening')"); pg.evaluate("setState('idle')"); pg.wait_for_timeout(150)
        ok(paused_focus == "paused" and pg.evaluate("radio.state().state") == "playing",
           "распознавание речи забрало динамик — после разговора радио продолжает само")
        say("пауза"); pg.evaluate("setState('idle')"); pg.wait_for_timeout(150)
        ok(pg.evaluate("radio.state().state") == "paused", "а пауза по просьбе — остаётся паузой")
        say("продолжи")
        r = say("выключи радио")
        ok(r["st"]["state"] == "stopped" and not r["chip"], f"«выключи радио» — выключено, плашки нет ({r['bot']})")

        # через модель: просьба, которую быстрые команды не разбирают
        specs = pg.evaluate("toolSpecs().map(t => t.name + ': ' + t.description)")
        pr = next((s for s in specs if s.startswith("play_radio")), "")
        ok(pr and "не открывай сайты" in pr, "у модели есть инструмент play_radio: «не открывай сайты и Яндекс Музыку»")
        ok("play_radio" in pg.evaluate("systemPrompt()"), "и в описании возможностей сказано, что радио играет здесь")
        r = say("А можно что-то по радио про джаз", 2500)
        ok(r["st"]["state"] == "playing" and "джаз" in (r["st"]["name"] + json.dumps(radio, ensure_ascii=False)).lower()
           and r["st"]["name"] in ("Jazz", "Radio Swiss Jazz", "Secret Agent"), f"модель сама включила джаз через play_radio: {r['st']['name']} — {r['bot'][:80]}")
        res = pg.evaluate("runTool('play_radio', { query: 'шансон' })")
        st = pg.evaluate("radio.state()")
        ok("Играет радио «Радио Шансон Москва»" in res and CATALOG and "tag=chanson" in CATALOG[-1],
           f"нет в своём списке — каталог radio-browser по жанру: {res[:70]} / {CATALOG[-1] if CATALOG else '—'}")
        res2 = pg.evaluate("runTool('radio_control', { action: 'pause' })")
        ok(res2 == "На паузе." and pg.evaluate("radio.state().state") == "paused", "radio_control pause — для модели")
        pg.click("#r-pp"); pg.wait_for_timeout(200)
        ok(pg.evaluate("radio.state().state") == "playing", "кнопка на плашке — продолжить")
        pg.screenshot(path=str(www.parent / "radio-chip.png"))
        pg.click("#r-x"); pg.wait_for_timeout(200)
        ok(pg.evaluate("radio.state().state") == "stopped" and pg.evaluate("document.querySelector('#radiobox').hidden"), "кнопка ✕ — выключить")
        qs = pg.evaluate("""async () => { const out = {}; for (const t of ["поставь таймер на 2 минуты", "таймер на 3 секунды", "громкость 40 процентов"])
            { const r = await quick(t); out[t] = r && r.say; } return out; }""")
        ok(all(qs.values()) and "2 минуты" in qs["поставь таймер на 2 минуты"],
           f"русские окончания в быстрых командах («минуты», «секунды», «процентов») — раньше \\w в JS не видел кириллицу: {qs}")
        # Гонка команд: прежняя команда, ещё перебирающая станции, не должна перебить новую (называется новая станция,
        # а играет прежняя) и в конце выключить радио — новая команда отменяет прежнюю целиком.
        pg.evaluate("() => { window._race = null; radio.play('вязкий эфир').then(r => { window._race = r; }); }")      # станция не отвечает — ждёт 15 с, потом следующая
        pg.wait_for_timeout(500)
        r2 = pg.evaluate("radio.play('живая волна')")
        pg.wait_for_timeout(16500)                                       # прежняя дождалась своего таймаута
        first = pg.evaluate("window._race")
        log = pg.evaluate("Dewiar._radio.log.slice(-6)")
        ok(r2.get("ok") and first.get("superseded") and pg.evaluate("radio.state()")["name"] == "Живая волна" and pg.evaluate("radio.state().state") == "playing"
           and log[-1] == "play Живая волна", f"новая команда отменяет прежнюю: играет «Живая волна», прежний перебор не перебил её и не выключил ({log})")
        say("выключи радио"); pg.wait_for_timeout(300)
        r = say("другое радио поставь", 1500)
        ok(r["st"]["state"] == "playing" and r["st"]["name"] != "Живая волна" and "Играет" in r["bot"],
           f"«другое радио поставь» сразу после выключения — другая станция, а не «не понял» ({r['st']['name']}, {r['bot']})")
        vols = pg.evaluate("""async () => { window._vol = []; for (const t of ["тише", "сделай радио потише", "чуть тише", "намного тише", "громче"]) await quick(t); return window._vol; }""")
        ok(vols == [["down", 20], ["down", 20], ["down", 10], ["down", 35], ["up", 20]], f"«тише» — заметно (−20%), «чуть тише» −10%, «намного тише» −35%: {vols}")
        ok(errs == [], f"без ошибок на странице {errs}")
        b.close()
finally:
    mock.terminate()
print(f"   (снимок плашки: {www.parent}/radio-chip.png)")
print("ИТОГ:", "всё прошло" if all(ok_all) else f"провалов {ok_all.count(False)}")
sys.exit(0 if all(ok_all) else 1)
