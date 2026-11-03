"""Студия → «Сейф паролей» → «Один сейф на всех моих устройствах» (группа Telegram 03.11: «смешно читать подсказку, что
можно выгрузить его в файл и перенести самому — раз есть синхронизация, а сейф шифруется»).
- подсказки «сейф никуда не синхронизируется» больше нет; закрытая копия — скромной строкой, кнопки на месте;
- выключено: переключатель → форма «Придумайте мастер-пароль» дважды: короткий и несовпавший — отказ здесь же, без ядра;
  верный — vault_sync on, «включено», «Сменить мастер-пароль»; мастер-пароль на экране не остаётся;
- на другом устройстве сейф уже общий — сразу форма «Мастер-пароль сейфа», неверный — ответ ядра словами;
- выключить — только через вопрос; vault_changed (пришло с другого устройства) — список обновляется.
SAFE_SHOTS=<папка> — снимок vault-studio.png."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


html = (ROOT / "ui/settings.html").read_text(encoding="utf-8")
ok("никуда не синхронизируется" not in html and "не синхронизируются" not in (ROOT / "ui/assets/privacy.js").read_text(encoding="utf-8"),
   "подсказки «сейф никуда не синхронизируется» нет ни в студии, ни в «Ваших данных»")

FAKE = "window.pywebview = { api: new Proxy({}, { get: (_, k) => (...a) => Promise.resolve(true) }) };"
CORE = r"""
(() => { window.calls = []; window.ST = { on: false, stale: false, remote: false, server: true, linked: true, sync_on: true, count: 2, min: 8 };
  window.V = [{ id: "a1", name: "Почта", login: "m@example.org", url: "", note: "", value: "Секрет-123" }];
  const pub = () => V.map(x => { const o = Object.assign({}, x, { length: x.value.length }); delete o.value; return o; });
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "vault_list") return { items: pub() };
      if (c === "backup_info") return { items: [] };
      if (c === "vault_sync") {
        if (a.op === "on") { if (ST.remote && a.password !== "верный-мастер") throw new Error("мастер-пароль не подошёл — это пароль, который вы придумали, когда включали сейф на другом устройстве");
          Object.assign(ST, { on: true, remote: false, stale: false }); }
        if (a.op === "off") ST.on = false;
        return Object.assign({}, ST); }
      return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();
"""
SHOT = os.environ.get("SAFE_SHOTS")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 950}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script(FAKE); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1500)
    pg.evaluate("document.querySelector('nav button[data-p=\"vault\"]').click()"); pg.wait_for_timeout(500)
    ok(pg.is_visible("#vl-sync") and "Один сейф на всех моих устройствах" in pg.inner_text("#vl-sync"), "в сейфе — карточка «Один сейф на всех моих устройствах»")
    ok(pg.is_visible("#vl-keep-go") and pg.is_visible("#vl-keep-back"), "закрытая копия — кнопки на месте, скромной строкой")
    ok(not pg.is_checked("#vs-on") and not pg.query_selector("#vs-form"), "выключено: переключатель снят, формы нет")
    pg.click("#vl-sync label.tg"); pg.wait_for_timeout(100)
    ok(pg.is_visible("#vs-pw") and pg.is_visible("#vs-pw2"), "включить — форма «Придумайте мастер-пароль» дважды")
    n = len(pg.evaluate("calls"))
    pg.fill("#vs-pw", "кор"); pg.fill("#vs-pw2", "кор"); pg.click("#vs-go"); pg.wait_for_timeout(100)
    ok("Не короче" in pg.inner_text("#vs-res") and len(pg.evaluate("calls")) == n, "короткий — отказ здесь же, ядро не спрашиваем")
    pg.fill("#vs-pw", "тихий-сад-2026"); pg.fill("#vs-pw2", "тихий-сад-2027"); pg.click("#vs-go"); pg.wait_for_timeout(100)
    ok("не совпадают" in pg.inner_text("#vs-res"), "несовпавшие — отказ")
    pg.fill("#vs-pw2", "тихий-сад-2026"); pg.click("#vs-go"); pg.wait_for_timeout(300)
    last = pg.evaluate("calls.filter(c => c[0] === 'vault_sync').pop()")
    ok(last[1] == {"op": "on", "password": "тихий-сад-2026"}, f"верный — vault_sync on: {last}")
    ok(pg.is_checked("#vs-on") and "включено" in pg.inner_text("#vl-sync") and pg.is_visible("#vs-change"), "включено: метка, «Сменить мастер-пароль»")
    ok(not pg.query_selector("#vs-pw") and "тихий-сад" not in pg.content(), "мастер-пароль на странице не остаётся")
    ok("«Всё» → «Сейф»" in pg.inner_text("#vl-sync"), "подсказка, где сейф на телефоне")
    if SHOT:
        Path(SHOT).mkdir(parents=True, exist_ok=True)
        pg.locator("#p-vault").screenshot(path=str(Path(SHOT) / "vault-studio.png"))
    # выключить — через вопрос
    pg.click("#vl-sync label.tg"); pg.wait_for_timeout(200)
    ok(pg.is_visible(".dwq"), "выключить — только через вопрос")
    pg.click(".dwq button.yes"); pg.wait_for_timeout(300)
    ok(not pg.is_checked("#vs-on") and pg.evaluate("calls.filter(c => c[0] === 'vault_sync').pop()")[1]["op"] == "off", "выключено на этом компьютере")
    # на другом устройстве уже общий
    pg.evaluate("ST.remote = true; vlSync()"); pg.wait_for_timeout(200)
    ok(pg.is_visible("#vs-pw") and not pg.query_selector("#vs-pw2") and "уже общий" in pg.inner_text("#vl-sync"), "на другом устройстве сейф общий — сразу «Мастер-пароль сейфа»")
    pg.fill("#vs-pw", "не-тот"); pg.click("#vs-go"); pg.wait_for_timeout(200)
    ok("не подошёл" in pg.inner_text("#vs-res"), "неверный — ответ ядра словами")
    pg.fill("#vs-pw", "верный-мастер"); pg.click("#vs-go"); pg.wait_for_timeout(300)
    ok(pg.is_checked("#vs-on"), "верный — сейф подключён")
    # пришло с другого устройства — список обновился
    pg.evaluate("V.push({ id: 'b2', name: 'Банк', value: 'x-1' }); core.emit('vault_changed', {})"); pg.wait_for_timeout(800)
    ok("Банк" in pg.inner_text("#vl-list"), "запись с другого устройства — в списке сразу")
    ok(not errs, f"без ошибок: {errs[:2]}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
