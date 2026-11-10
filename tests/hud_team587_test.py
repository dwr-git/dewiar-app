"""№587 (ПК 0.84.2, Windows 10, 06.11): «нажимаю раскрывающийся элемент (⌄ у панели виджета) — появляется непонятная область».
Снимок: у «⌄» нет значка персонажа, над панелью — пустая тёмная полоса. Так бывает, когда виджет остался без списка команды
(шаг приветствия ядра споткнулся раньше, чем список персонажей записан). Теперь персонажи — первыми, остальные шаги — каждый
сам по себе; пустое меню не открывается (виджет спрашивает ядро заново, не вышло — понятный текст), значок у «⌄» есть всегда.
№576 (Linux Omarchy, Hyprland): виджет растянут плиточным менеджером окон — окна-карточки просим держать плавающими."""
import os, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "ui"))
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


P = [{"id": "lira", "name": "Лира", "gender": "female", "role": "Главная помощница", "style": "face"},
     {"id": "patrik", "name": "Патрик", "gender": "male", "role": "Наставник"}]
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for skin in ("neon", "neusky"):
        pg = b.new_page(viewport={"width": 631, "height": 590}); pg.on("pageerror", lambda x: errs.append(str(x)))
        pg.goto((ROOT / "ui/hud.html").as_uri() + "?port=1&mode=card"); pg.wait_for_timeout(700)
        ok(pg.evaluate("!!document.querySelector('#team-dot svg')"), f"[{skin}] у «⌄» — значок персонажа ещё до связи с ядром")
        pg.evaluate("() => { window._asked = 0; core.call = (c) => { if (c === 'hello') _asked++; return Promise.reject(new Error('нет связи с ядром')); }; }")
        pg.click("#b-team"); pg.wait_for_timeout(300)
        r = pg.evaluate("() => { const t = document.getElementById('team'); return [t.getBoundingClientRect().height, _asked]; }")
        ok(r[0] == 0 and r[1] == 1, f"[{skin}] списка нет — пустая полоса не открывается, виджет спрашивает ядро заново: {r}")
        # приветствие ядра, где один шаг спотыкается (битые напоминания) — команда всё равно на месте
        pg.evaluate("""([P, skin]) => (core.handlers.hello || []).forEach(f => f({ reminders: 'битые', settings: { ui: { skin }, features: {}, privacy: {}, tts: {}, llm: { active: 'x' } },
            personas: P, muted: false, persona: 'lira', radio: null, state: 'idle', status: '' }))""", [P, skin])
        pg.wait_for_timeout(400)
        r = pg.evaluate("() => [personas.length, current && current.name]")
        ok(r == [2, "Лира"], f"[{skin}] шаг приветствия споткнулся — персонажи всё равно загружены: {r}")
        pg.click("#b-team"); pg.wait_for_timeout(300)
        r = pg.evaluate("() => [...document.querySelectorAll('#team button b')].map(x => x.textContent)")
        ok(r == ["Лира", "Патрик"], f"[{skin}] меню «Кто отвечает» — со списком: {r}")
        if os.environ.get("DEWIAR_SHOTS"):
            pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / f"hud-team587-{skin}.png"))
        pg.close()
    b.close()
ok(not [e for e in errs if "битые" not in e and "forEach" not in e], f"без ошибок на странице: {errs[:3]}")

# №576: Hyprland — правила для окон-карточек
import app as UI  # noqa: E402
seen = []
os.environ["HYPRLAND_INSTANCE_SIGNATURE"] = "test"
r = UI.hypr_rules(run=lambda a: (seen.append(a), "invalid field\n\n" if "windowrulev2" in a[1] else "ok\n\nok\n\nok\n\nok")[1])
ok(r == "windowrule" and "float, class:^(Dewiar)$" in seen[-1][1] and "Dewiar — студия" not in seen[-1][1],
   f"Hyprland: карточки плавающие (старый синтаксис не принят — новый), студию не трогаем: {r}")
os.environ.pop("HYPRLAND_INSTANCE_SIGNATURE")
ok(UI.hypr_rules(run=lambda a: "ok") == "", "не Hyprland — ничего не делаем")
ws = (ROOT / "ui/winshell.py").read_text(encoding="utf-8")
ok("u.DestroyMenu.argtypes = [wintypes.HMENU]" in ws and "u.SetForegroundWindow.argtypes = [wintypes.HWND]" in ws,
   "трей Windows: дескрипторы меню и окна — 64-битные (в журнале №587 «Трей: OverflowError», пункт меню не срабатывал)")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
