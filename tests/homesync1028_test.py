"""«Дома по Wi-Fi» (0.59; владелец 28.10: синхронизация без dewiar.pro — напрямую по домашнему Wi-Fi «подойдёт»):
компьютер — узел (core/homehub.py) с тем же обменом, что ?p=/sync, его Sync — HomeSync по 127.0.0.1; телефон (app.js в
Chromium) подключается кодом dewiar://home с экрана компьютера и меняется с ним зашифрованными запросами.
Проверяем: чужой ключ, повтор, старое время, отключённый телефон — отказ; без ключа данных не отдать; заметка, напоминание,
расход и память — с компьютера на телефон и обратно, без эха; компьютер вне сети — понятная причина, правки ждут."""
import datetime as dt
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"))
os.environ.pop("DEWIAR_WORKSPACE", None)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


import closecrypto as CC  # noqa: E402
import homehub  # noqa: E402
from money import Money  # noqa: E402
from sync import HomeSync, Sync  # noqa: E402
from tools import Reminders  # noqa: E402
from workspace import Workspace  # noqa: E402

homehub.lan_addresses = lambda: ["127.0.0.1"]           # в проверке «домашняя сеть» — этот же компьютер


class FakeS:
    def get(self, *k, default=None): return str(tmp / "ws") if k == ("workspace", "path") else default


class PC:
    def __init__(self, hub):
        self.hub = hub
        self.workspace = Workspace(FakeS())
        self.reminders = Reminders(lambda it: None)
        self.reminders.path = tmp / "reminders.json"; self.reminders.items = []
        self.money = Money(tmp / "money.json", self.workspace, lambda: "BYN")
        self.sync = Sync(self)
        self.home = HomeSync(self, self.sync)
    def credentials(self): return "", "", ""                       # облака нет совсем
    def home_credentials(self): return self.hub.own_token(), "", f"http://127.0.0.1:{self.hub.port}/"
    def device_name(self): return "Домашний"
    def note(self, n): return self.workspace.ensure() / "Заметки" / n


def post(url, data=b"", headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def sealed(k, body, ts=None, n=None):
    env = {"ts": int((ts or time.time()) * 1000), "n": n or CC.b64e(os.urandom(9)), "body": body}
    return CC.b64e(CC.seal(k, json.dumps(env).encode()))


hub = homehub.HomeHub(tmp / "st" / "homehub.sqlite", name=lambda: "Домашний")
port = hub.start(port=free())
U = f"http://127.0.0.1:{port}/"
www = tmp / "www"
try:
    # ---- узел: кто может, кто нет ----
    st, b = post(U + "sync", b"{}", {"Content-Type": "application/json"})
    ok(st == 401 and "код" in b, f"без ключа — отказ: {st} {b[:80]}")
    st, b = post(U + "sync", b"{}", {"Authorization": "Bearer hm-chuzhoj"})
    ok(st == 401, "чужой «свой» ключ — отказ")
    p = hub.pair_new(); link = hub.pair_link(p); K = CC.b64d(p["k"])
    ok(link.startswith("dewiar://home?u=http%3A%2F%2F127.0.0.1%3A") and f"t={p['tid']}" in link and "n=%D0%94%D0%BE%D0%BC" in link, f"ссылка для кода: {link[:90]}…")
    st, b = post(U + "sync", sealed(os.urandom(32), {}).encode(), {"X-Home": p["tid"]})
    ok(st == 401 and "не расшифровался" in b, "запрос, зашифрованный другим ключом, — отказ")
    nn = "одинаковый"
    st1, b1 = post(U + "sync", sealed(K, {"since": 0, "device": "phone-t1", "name": "Проба", "kinds": []}, n=nn).encode(), {"X-Home": p["tid"]})
    st2, b2 = post(U + "sync", sealed(K, {"since": 0, "device": "phone-t1", "kinds": []}, n=nn).encode(), {"X-Home": p["tid"]})
    rep = json.loads(CC.unseal(K, CC.b64d(b1)).decode()) if st1 == 200 else {}
    ok(st1 == 200 and rep.get("rev") == 0 and rep.get("space") == "home", f"верный ключ — ответ, зашифрованный тем же ключом: {st1} {list(rep)[:6]}")
    ok("rev" not in b1 and "items" not in b1, "в ответе по сети — только шифр")
    ok(st2 == 400 and "повтор" in b2, f"перехваченный запрос повторить нельзя: {st2}")
    st, b = post(U + "sync", sealed(K, {}, ts=time.time() - 3600).encode(), {"X-Home": p["tid"]})
    ok(st == 400 and "часы" in b, "запрос часовой давности — отказ")
    ok([x["name"] for x in hub.phones()] == ["Проба"], f"телефон в списке компьютера: {hub.phones()}")
    hub.forget(p["tid"])
    st, b = post(U + "sync", sealed(K, {"since": 0}).encode(), {"X-Home": p["tid"]})
    ok(st == 401 and not hub.phones(), "отключённый телефон — отказ")
    p2 = hub.pair_new(); hub.now = lambda: time.time() + 700
    st, b = post(U + "sync", sealed(K, {}).encode(), {"X-Home": p2["tid"]})
    ok(st == 401, "код не использовали 10 минут — устарел")
    hub.now = time.time

    # ---- компьютер ↔ телефон ----
    A = PC(hub)
    soon = dt.datetime.now().replace(second=0, microsecond=0) + dt.timedelta(hours=2)
    r1 = A.reminders.add(soon, "Позвонить маме")
    A.workspace.save_note("Идея", "Помощник для бабушки")
    A.money.add("expense", 12, note="такси")
    A.workspace.remember("Любит зелёный чай")
    A.home.run_once()
    ok(A.home.status.get("ok") and A.home.status["counts"]["sent"] >= 4, f"компьютер отдал своё узлу: {A.home.status.get('counts')} {A.home.status.get('error')}")
    ok(A.home.state["device"] == A.sync.state["device"], "у домашней синхронизации — тот же номер компьютера")

    shutil.copytree(ROOT / "android/assets/www", www)
    shutil.copy(ROOT / "ui/assets/entities.js", www / "entities.js")
    shutil.copy(ROOT / "ui/assets/closecrypto.js", www / "closecrypto.js")
    shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
    (www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                    capture_output=True, text=True, check=True).stdout, encoding="utf-8")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(); pg = b.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(800)
        if not pg.evaluate("!!window.DewiarCrypto"):
            pg.add_script_tag(path=str(www / "closecrypto.js"))
        p3 = hub.pair_new(); link3 = hub.pair_link(p3)
        R1 = pg.evaluate("""async (link) => {
            S.sync = { on: true }; saveS();
            let err = ""; try { await homeClaim(link); } catch (e) { err = e.message; }
            return { err, st: syncStatus, cred: syncChan(), cloud: syncCred(), alarms: JSON.parse(D.alarms()), notes: notes(), money: money(), memory: S.memory };
        }""", link3)
        ok(not R1["err"] and R1["st"]["ok"] and R1["cred"]["home"], f"телефон подключился кодом: {R1['err']} {R1['st'].get('error')} {R1['cred'].get('via')}")
        ok("напрямую по Wi-Fi с «Домашний»" in (R1["cred"].get("via") or ""), f"как синхронизируется — понятно: {R1['cred'].get('via')}")
        ok(R1["cloud"] is None, "облачные дела («Близкие», почта своих устройств) по-прежнему знают: входа в dewiar.pro нет — к компьютеру с ними не ходят")
        ok(any(a["id"] == r1["id"] and a["title"] == "Позвонить маме" for a in R1["alarms"]), "напоминание компьютера — на телефоне")
        ok(any(n["title"] == "Идея" and "бабушки" in n["text"] for n in R1["notes"]), "заметка компьютера — на телефоне")
        ok([m["amount"] for m in R1["money"]] == [12], "расход — на телефоне")
        ok("Любит зелёный чай" in R1["memory"], "память — на телефоне")
        ok(any(x["name"] == "Домашний" or x.get("app") == "pc" for x in R1["st"].get("all") or []), f"компьютер в списке устройств телефона: {R1['st'].get('all')}")

        R2 = pg.evaluate("""async () => {
            await runTool("save_note", { title: "С телефона", text: "купить батарейки" });
            await runTool("money_add", { kind: "expense", amount: 4.2, note: "кофе" });
            await runTool("remember", { fact: "Ездит на велосипеде" });
            await syncRun(true); const first = syncStatus.counts;
            await syncRun(true);
            return { first, second: syncStatus.counts };
        }""")
        ok(R2["first"]["sent"] == 3 and R2["second"] == {"sent": 0, "got": 0}, f"телефон отправил 3, повторно — пусто: {R2}")
        A.home.run_once()
        ok(A.note("С телефона.md").exists(), "заметка с телефона — на компьютере")
        ok(sorted(m["amount"] for m in A.money.items) == [4.2, 12.0], "расход с телефона — на компьютере")
        ok("Ездит на велосипеде" in (A.workspace.ensure() / "Память/Обо мне.md").read_text(encoding="utf-8"), "факт с телефона — в памяти компьютера")
        A.home.run_once()
        ok(A.home.status["counts"] == {"sent": 0, "got": 0}, f"эха нет: {A.home.status['counts']}")
        A.reminders.remove(r1["id"]); A.home.run_once()
        R3 = pg.evaluate("""async (rid) => { await syncRun(true); return JSON.parse(D.alarms()).some(x => x.id === rid); }""", r1["id"])
        ok(not R3, "отменённое на компьютере — отменено на телефоне")

        # «Устройства» на телефоне
        pg.evaluate("""async () => { try { D.web = false; } catch (e) { }       // как в приложении (браузерная версия по http к компьютеру не ходит)
            openSettings("devices"); await new Promise(r => setTimeout(r, 900)); }""")
        txt = pg.evaluate("document.querySelector('#sh-set') ? document.querySelector('#sh-set').innerText : ''")
        ok("компьютер дома" in txt.lower() and "Домашний" in txt and "Отключить" in txt and "ввести код" not in txt.lower(), "«Устройства»: компьютер дома и «Отключить»; облачного «Ввести код» нет")
        pg.screenshot(path=str(Path(os.environ.get("DEWIAR_SHOTS") or tmp) / "home-phone.png"))

        # компьютер не в сети — понятная причина, правка ждёт и уходит потом
        hub.stop()
        R4 = pg.evaluate("""async () => { await runTool("save_note", { title: "Без сети", text: "потом" });
            while (syncBusy) await new Promise(r => setTimeout(r, 100));        // обмен по таймеру (после правки) — дождаться
            await syncRun(true); return syncStatus; }""")
        ok(R4["ok"] is False and "не в этой сети" in R4["error"], f"компьютер выключен — понятно почему: {R4}")
        hub.start(port=port)
        R5 = pg.evaluate("""async () => { while (syncBusy) await new Promise(r => setTimeout(r, 100)); await syncRun(true); return syncStatus; }""")
        A.home.run_once()
        ok(R5["ok"] and A.note("Без сети.md").exists(), "сеть вернулась — правка дошла")

        # роутер дал компьютеру другой адрес (0.65): прежний молчит — телефон находит узел в своей сети Wi-Fi по /hello
        dead = free()
        R6 = pg.evaluate("""async ([U, dead]) => {
            const real = http; window._seen = [];
            http = (m, url, o) => { _seen.push(url); return real(m, url.replace("http://127.0.0.42:8766/", U), o); };
            D.lanIps = () => JSON.stringify([{ ip: "127.0.0.9", wifi: true }, { ip: "10.20.30.40", wifi: false }]);
            S.sync.home.u = ["http://127.0.0.1:" + dead + "/"]; saveS(); homeSeekAt = 0;
            await runTool("save_note", { title: "Новый адрес", text: "нашёлся" });
            while (syncBusy) await new Promise(r => setTimeout(r, 100));
            await syncRun(true);
            const st = JSON.parse(JSON.stringify(syncStatus)), u = S.sync.home.u.slice(), hello = _seen.filter(x => /hello$/.test(x));
            S.sync.home.u = ["http://127.0.0.1:" + dead + "/"]; saveS(); _seen = [];
            await syncRun(true);
            const st2 = JSON.parse(JSON.stringify(syncStatus)), again = _seen.filter(x => /hello$/.test(x)).length;
            http = real;
            return { st, u, n: hello.length, other: hello.filter(x => !/^http:\/\/127\.0\.0\./.test(x)).length, st2, again };
        }""", [U, dead])
        A.home.run_once()
        ok(R6["st"]["ok"] and R6["u"][0] == "http://127.0.0.42:8766/" and A.note("Новый адрес.md").exists(),
           f"компьютер сменил адрес — телефон нашёл его сам, правка дошла: {R6['st'].get('error')} {R6['u'][:2]}")
        ok(R6["n"] > 0 and R6["other"] == 0, f"ищем только в своей сети Wi-Fi (мобильную не трогаем): {R6['n']} запросов, чужих {R6['other']}")
        ok(R6["st2"]["ok"] is False and R6["again"] == 0, "не нашёлся — не ищем снова каждую минуту (раз в 10 минут)")
        pg.evaluate("() => { S.sync.home.u = [arguments[0]]; saveS(); }".replace("arguments[0]", json.dumps(U)))
        ok(errs == [], f"без ошибок на странице: {errs[:3]}")
        b.close()
    # ---- ядро: команды студии (engine_home.py) ----
    import threading as _th
    from engine_home import HomeMixin

    class SS:
        def __init__(self): self.d = {"sync": {"home": {"on": False}}}
        def get(self, *k, default=None):
            v = self.d
            for x in k:
                v = v.get(x) if isinstance(v, dict) else None
            return default if v is None else v
        def update(self, patch):
            def merge(a, b_):
                for k_, v_ in b_.items():
                    if isinstance(v_, dict) and isinstance(a.get(k_), dict):
                        merge(a[k_], v_)
                    else:
                        a[k_] = v_
            merge(self.d, patch)

    class E(HomeMixin, PC):
        def __init__(self):
            PC.__init__(self, None)
            self.s, self.wav_input, self.stopping = SS(), None, _th.Event()
        def credentials(self): return "", "", ""
    import engine_home
    engine_home.STATE_DIR = tmp / "st2"
    e = E()
    h0 = e.home_cmd("home_get", {})
    ok(h0["on"] is False and not h0["running"], "по умолчанию узел выключен — компьютер сеть не слушает")
    h1 = e.home_cmd("home_pair", {})
    ok(h1["on"] and h1["running"] and h1["pair"]["link"].startswith("dewiar://home?") and e.s.get("sync", "home", "on") is True,
       f"«Показать код» — узел включается сам, ссылка для QR: {h1['pair']['link'][:40]}")
    h2 = e.home_cmd("home_set", {"on": False})
    ok(not h2["on"] and not h2["running"], "выключили — сеть больше не слушает")
    e.stopping.set()

    # ---- студия: «Устройства» → «Дома по Wi-Fi» ----
    import re as _re
    with sync_playwright() as pw:
        b = pw.chromium.launch(); errs = []
        pg = b.new_page(viewport={"width": 1300, "height": 1500}); pg.on("pageerror", lambda x: errs.append(str(x)))
        pg.route(_re.compile(r"^https?://"), lambda r: r.abort())
        pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
        pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(900)
        pg.evaluate("""(link) => {
          const now = Date.now() / 1000;
          window._home = { on: false, running: false, port: 8766, ips: ['192.168.1.5'], phones: [], ok: null, at: 0, error: '', counts: {} };
          core.call = (c, a) => {
            if (c === 'devices_get') return Promise.resolve({ me: { name: 'Домашний', id: 'pc-1' }, devices: [{ id: 'pc-1', name: 'Домашний', app: 'pc', me: true, seen: now }].concat(_home.phones.length ? [{ id: 'phone-x', name: 'Pixel Миши', app: 'phone', seen: now - 20, home: true }] : []),
              sync: { available: false, on: true }, home: _home, can_pair: false });
            if (c === 'home_pair') { Object.assign(_home, { on: true, running: true }); return Promise.resolve(Object.assign({}, _home, { pair: { link, until: now + 600, tid: 'ab12' } })); }
            if (c === 'home_get') { _home.phones = [{ tid: 'ab12', name: 'Pixel Миши', seen: Date.now() / 1000, created: now }]; _home.ok = true; _home.at = now; return Promise.resolve(_home); }
            if (c === 'home_set') { _home.on = a.on; _home.running = a.on; return Promise.resolve(_home); }
            return Promise.resolve({}); };
          document.querySelector('nav button[data-p=devices]').click(); }""", link3)
        pg.wait_for_timeout(700)
        ok(pg.is_visible("#dv-home") and pg.get_attribute("#dv-ways [data-way=home]", "aria-selected") == "true",
           "входа в Dewiar нет — в «Как связать устройства» сразу открыт способ «Дома по Wi-Fi»")
        ok("без интернета и dewiar.pro" in pg.inner_text("#dv-ways") and "везде, где есть интернет" in pg.inner_text("#dv-ways"),
           "два способа рядом — и чем отличаются")
        pg.locator("#dv-ways").screenshot(path=str(Path(os.environ.get("DEWIAR_SHOTS") or tmp) / "home-studio-ways.png"))
        pg.click("#dv-ways [data-way=cloud]")
        ok(pg.is_visible("#dv-give") and pg.is_hidden("#dv-home"), "«Через dewiar.pro» — код из 6 цифр и «Ввести код»")
        pg.click("#dv-ways [data-way=home]")
        pg.click("#dv-home-go"); pg.wait_for_timeout(500)
        ok(pg.is_visible("#dv-home-qr svg") and "Код действует ещё" in pg.inner_text("#dv-home-left"), "«Показать код» — QR и сколько он действует")
        shots = Path(os.environ.get("DEWIAR_SHOTS") or tmp)
        pg.locator("#dv-home").screenshot(path=str(shots / "home-studio-code.png"))
        pg.wait_for_timeout(3500)
        ok(pg.is_hidden("#dv-home-code") and "Pixel Миши" in pg.inner_text("#dv-home-list"), "телефон подключился — код спрятан, телефон в списке с «Отключить»")
        pg.locator("#dv-home").screenshot(path=str(shots / "home-studio.png"))
        ok(not errs, f"студия без ошибок: {errs[:3]}")
        b.close()
finally:
    hub.stop()
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
