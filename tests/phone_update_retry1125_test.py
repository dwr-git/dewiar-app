"""№1057 (25.11, телефон Huawei): «Не может установить обновление» — «Не скачалось: файл пришёл повреждённым» раз за
разом, хотя у 19 других телефонов та же версия встала. Файл портит дорога (оборванная связь без ошибки, кэш по пути).
Теперь: обрыв раньше заявленного размера — отдельной причиной; до трёх попыток, со второй — мимо кэшей; каждая попытка
и итог — в журнал (отчёт раньше не знал о сбое); после трёх — честная подсказка: VPN/прокси и страница сайта."""
import os, re, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


j = (ROOT / "android/src/pro/dewiar/app/Update.java").read_text(encoding="utf-8")
ok("for (int t = 1; t <= 3; t++)" in j, "до трёх попыток")
ok('"nc=" + System.currentTimeMillis()' in j and '"Cache-Control", "no-cache"' in j and "setUseCaches(false)" in j, "со второй — мимо кэшей")
ok("total > 0 && got < total" in j and "связь оборвалась" in j, "обрыв раньше размера — не «повреждён», а обрыв")
ok('a.event("upd_retry"' in j and j.index('a.event("upd_error"') > j.index("for (int t = 1"), "ошибка — только после всех попыток")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok('N.on("upd_retry"' in app and "обновление не скачалось" in app, "попытки и отказ — в журнал")
ok("VPN, прокси" in app and "dewiar.pro" in app.split('N.on("upd_error"')[1][:600], "после трёх — что сделать человеку")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
