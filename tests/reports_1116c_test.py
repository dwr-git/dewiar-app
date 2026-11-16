"""Пачка 16.11, 13:05:
№778 (Mac): бот Dewiar «на старт не реагирует, и пропал раздел подключиться к своему боту» — пока ждём «Запустить», настройка
     была спрятана; теперь «Отменить — подключить иначе». «Telegram ответил 302» — понятным текстом.
№780: удалённый рабочий стол — «Удалённое аудио»: что включить в подключении, а не «поднимите громкость».
№776 (телефон): «напоминание в четверг 6:00 и 7:00» — модель поставила «завтра» и оба на 6:00. День недели — из слов
     человека; два времени в одной фразе — не сводим к первому.
№770: «убрал настройки внутреннего сервиса Dewiar — как вернуть?» — кнопка «Вернуть настройки Dewiar» в профиле моделей Dewiar."""
import json, os, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


st = (ROOT / "ui/settings.html").read_text(encoding="utf-8")
ln = (ROOT / "ui/studio/links.js").read_text(encoding="utf-8")
ok('id="tg-pair-cancel"' in st and '$("#tg-pair-cancel").onclick' in ln and 'core.call("tg_forget")' in ln and '$("#tg-own").open = true' in ln,
   "№778: ждём «Запустить» — можно отменить и подключить своего бота или прокси")
import telegram as TG  # noqa: E402
b = TG.Telegram.__new__(TG.Telegram)
b.data = {"mode": "dewiar"}
ok("перенаправляет" in b._bad_status(302) and "302" not in b._bad_status(302), f"№778: 302 общего бота — по-человечески: {b._bad_status(302)}")
b.data = {"mode": ""}
ok("прокси" in b._bad_status(302) and b._bad_status(500) == "Telegram ответил 500", "свой бот: перенаправление — про прокси; прочее — как было")
au = (ROOT / "core/engine_audio.py").read_text(encoding="utf-8")
ok("remote audio" in au and "Запись с этого компьютера" in au, "№780: удалённый рабочий стол — что включить в подключении")

# №776: телефон — ставим по словам человека
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
i = app.index("// №776 (16.11): «напоминание в четверг 6:00»"); j = app.index('if (!at || isNaN(at)) return "Ошибка: не понял время', i)
blk = app[i:j]
js = """
function fix(said, atIso) { let at = new Date(atIso); const a = {}; const turnAsk = said; %s return at; }
const base = new Date(2026, 10, 16, 9, 44);       // понедельник
const tom6 = new Date(2026, 10, 17, 6, 0).toISOString();
const r = [fix("Запиши напоминание четверг 6:00 утра и 7:00 утра мотошкола.", tom6), fix("Завтра же вторник.", tom6),
           fix("напомни в пятницу купить хлеб", tom6), fix("напомни в четверг и в пятницу", tom6)];
console.log(JSON.stringify(r.map(d => [d.getDay(), d.getDate(), d.getHours()])));
""" % blk
r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30)
res = json.loads(r.stdout or "[]") if r.returncode == 0 else []
ok(res and res[0] == [4, 19, 6], f"«четверг 6:00», а модель дала завтра — ставим на четверг 19-го в 6:00: {res[:1]} {r.stderr[:200]}")
ok(len(res) == 4 and res[1] == [2, 17, 6] and res[2][0] == 5 and res[3] == [2, 17, 6], f"«завтра» — как есть; пятница — пятница; два дня — не трогаем: {res[1:]}")
ok("|| []).length === 1 && !/кажд|по будн|по выходн/i.test(said)" in app, "два времени в одной фразе — второе не сводится к первому")

br = (ROOT / "ui/studio/brain.js").read_text(encoding="utf-8")
ok('data-a="cloud-reset"' in br and 'core.call("cloud_connect", { use: true })' in br, "№770: «Вернуть настройки Dewiar» — тем же ключом или входом")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
