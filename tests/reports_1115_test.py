"""Отчёты людей 15.11 (после видео), что исправлено по нашей вине:
№725 «Плагины: как менять время уведомлений? не могу найти» — у дела плагина только переключатель; время меняется в
     «Календаре» (одно место для всех дел) — теперь это написано у дел плагина и есть ссылка «Открыть календарь».
№734 «на телефоне не работает подписка OpenCode Go» — 400 «missing x-opencode-session»: компьютер шлёт заголовок сессии
     с 04.11 (№524), телефон — нет. Теперь и телефон: постоянный id установки.
(№724 PDF на Windows — pdf_win1113_test; №728 виджет без WebView2 — winstart1103_test; №732 язык телефона — phone_lang_tz1115_test.)"""
import json, os, re, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


pj = (ROOT / "ui/studio/plugins.js").read_text(encoding="utf-8")
pp = (ROOT / "ui/studio/plugpage.js").read_text(encoding="utf-8")
ok("Время и дни включённого дела меняются в «Календаре»" in pj and 'nav button[data-p="calendar"]' in pj, "№725: у дел плагина — где менять время, ссылка в «Календарь» (карточка)")
ok("Время и дни включённого дела меняются в «Календаре»" in pp and 'nav button[data-p="calendar"]' in pp, "№725: то же на странице плагина")

www = Path(tempfile.mkdtemp()) / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(); pg.add_init_script("window.DW_SYS_LANG = 'ru';"); pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1500)
    h = pg.evaluate("(() => { S.llm.base_url = 'https://opencode.ai/zen/go/v1'; S.llm.cloud = false; S.llm.api_key = 'sk-x'; return [llmHeaders(), llmHeaders()]; })()")
    sid = h[0].get("x-opencode-session", "")
    ok(re.fullmatch(r"[0-9a-f-]{16,64}", sid or "") is not None and h[1].get("x-opencode-session") == sid, f"№734: телефон шлёт OpenCode постоянный x-opencode-session: {sid!r}")
    h2 = pg.evaluate("(() => { S.llm.base_url = 'https://openrouter.ai/api/v1'; return llmHeaders(); })()")
    ok("x-opencode-session" not in h2, "другим серверам моделей — без этого заголовка")
    b.close()
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
