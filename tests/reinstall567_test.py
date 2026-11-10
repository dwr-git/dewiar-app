"""№567, №569, №571 (VitalForce, ПК 0.83–0.84.2, 05.11): «после переустановки слетел ИИ-баланс» → «очередная переустановка,
удаление ключа, регистрация — и всё равно 0, а было больше 90 %» → «баланс вернулся, 100 %, не понимаю, что я сделал».
По журналам: при удалении отвечали «удалить настройки» — вместе с ними пропадал номер установки (cloud.dev), сайт узнавал
компьютер только по номеру машины и, как задумано, выдавал НОВЫЙ ключ без подарка (заряд 0 %, «Подарок на этом компьютере уже
был»), а заряд оставался на прежнем ключе. Теперь: номер установки хранится ещё и в реестре пользователя (удаление его не
стирает) — сайт возвращает прежний ключ; ключ с зарядом возвращается и позже gift_days; если вернуть нельзя — честно «заряд не
пропал, он на ключе DW-N» и кнопка «Перенести прежний заряд» в «Мозге». Серверная часть — в pay_flow1104."""
import os, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


keep = Path(tempfile.mkdtemp()) / "dev"
os.environ["DEWIAR_DEV_KEEP"] = str(keep)
import cloud  # noqa: E402


class S:
    def __init__(self):
        self.d = {}

    def get(self, *k):
        v = self.d
        for x in k:
            v = (v or {}).get(x) if isinstance(v, dict) else None
        return v

    def update(self, patch):
        for a, b in patch.items():
            self.d.setdefault(a, {}).update(b)


s1 = S()
ids1 = cloud.device_ids(s1)
ok(ids1[0].startswith("pc-") and keep.read_text() == ids1[0], f"номер установки — и вне папки настроек: {keep.read_text()[:6]}…")
s2 = S()                                       # переустановка с «удалить настройки»: настроек нет
ids2 = cloud.device_ids(s2)
ok(ids2[0] == ids1[0] and s2.get("cloud", "dev") == ids1[0], "после переустановки — тот же номер установки: сайт вернёт прежний ключ с зарядом")
src = (ROOT / "core/cloud.py").read_text(encoding="utf-8")
ok('HKEY_CURRENT_USER, DEV_REG' in src and r'DEV_REG = r"Software\Dewiar"' in src, "Windows: HKCU\\Software\\Dewiar (удаление программы этот раздел не трогает)")
nsi = (ROOT / "packaging/windows/dewiar.nsi").read_text(encoding="utf-8")
ok('DeleteRegKey HKCU "Software\\Dewiar"' not in nsi, "удаление программы не стирает номер установки в реестре")
t = cloud.gift_text({"gift": "none", "prev": "DW-1700"})
ok("не пропал" in t and "DW-1700" in t and "Перенести прежний заряд" in t, f"уведомление — не «подарок уже был», а «заряд не пропал»: {t}")
ok("уже был" in cloud.gift_text({"gift": "none"}), "без прежнего заряда — как раньше")
t2 = cloud.gift_text({"gift": "none", "prev": "?"})
ok("не пропал" in t2 and "DW-" not in t2, f"рецензия 0.86: совпала только машина — без номера ключа: {t2}")
eb = (ROOT / "core/engine_brain.py").read_text(encoding="utf-8")
ok('"prev": str(d.get("prev") or "")' in eb and '"prev": str(self.s.get("cloud", "prev")' in src, "номер прежнего ключа — в настройках и в cloud_status для «Мозга»")

errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for theme in ("neusky", "neudusk"):
        pg = b.new_page(viewport={"width": 1300, "height": 900}); pg.on("pageerror", lambda x: errs.append(str(x)))
        pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
        pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1&skin=" + theme); pg.wait_for_timeout(1000)
        pg.evaluate("""(th) => { window._sent = []; S = { llm: { profiles: {}, active: '' }, stt: { engine: 'vosk' }, tts: {}, cloud: {} };
          core.call = (c, a) => { if (c === 'cloud_topup_send') { _sent.push(a); return Promise.resolve({ ok: true, requests: [] }); }
            if (c === 'cloud_status') return Promise.resolve({ connected: true, tail: 'qzrw', percent: 0, empty: true, balance: 0, turns: 0, prev: 'DW-1700', pending: _sent.length > 0 });
            return Promise.resolve({}); };
          document.querySelectorAll('section.cur').forEach(x => x.classList.remove('cur')); $('#p-brain').classList.add('cur');
          cloudFill({ connected: true, tail: 'qzrw', percent: 0, empty: true, balance: 0, turns: 0, prev: 'DW-1700' }); }""", theme)
        pg.wait_for_timeout(400)
        r = pg.evaluate("() => [!$('#cc-prev').hidden, $('#cc-prev-t').textContent, !$('#cc-prev-go').hidden]")
        ok(r[0] and "не пропал" in r[1] and "DW-1700" in r[1] and r[2], f"[{theme}] «Мозг»: новый ключ с нулём — «прежний заряд не пропал» и кнопка: {r[1][:80]}")
        if os.environ.get("DEWIAR_SHOTS"):
            pg.locator("#cloud-card").screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / f"reinstall567-{theme}.png"))
        pg.click("#cc-prev-go"); pg.wait_for_timeout(600)
        sent = pg.evaluate("_sent")
        ok(sent and "Перенести прежний заряд" in sent[0]["note"] and "DW-" not in sent[0]["note"] and not sent[0]["amount"] and not sent[0]["image"],
           f"[{theme}] кнопка — заявка администратору без суммы и снимка; прежний ключ сервер берёт из своей записи, не из заметки: {sent}")
        pg.evaluate("() => { _sent = []; cloudFill({ connected: true, tail: 'qzrw', percent: 0, empty: true, balance: 0, turns: 0, prev: '?' }); }")
        r = pg.evaluate("() => [!$('#cc-prev').hidden, $('#cc-prev-t').textContent]")
        ok(r[0] and "DW-" not in r[1] and "не пропал" in r[1], f"[{theme}] совпала только машина — карточка без номера ключа: {r[1][:70]}")
        pg.evaluate("() => cloudFill({ connected: true, tail: 'qzrw', percent: 0, empty: true, balance: 0, turns: 0, prev: 'DW-1700' })")
        pg.click("#cc-prev-go"); pg.wait_for_timeout(600)
        r = pg.evaluate("() => [$('#cc-prev-t').textContent, $('#cc-prev-go').hidden]")
        ok("отправлена" in r[0] and r[1], f"[{theme}] после заявки — «отправлена», кнопки нет: {r[0][:60]}")
        pg.evaluate("() => cloudFill({ connected: true, tail: 'qzrw', percent: 96, empty: false, balance: 1.2, turns: 300, prev: 'DW-1700' })")
        ok(pg.evaluate("$('#cc-prev').hidden"), f"[{theme}] заряд перенесли — подсказка уходит")
        pg.close()
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
