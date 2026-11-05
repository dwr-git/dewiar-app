"""№542 (пакет 04.11, ПК 0.82.2): «на сколько хватает 1 талер?». Кабинет сайта знал «Хватит примерно на N ответов», а в
программе и на телефоне было видно только «на сколько хватит всего счёта» — и то, пока он не пуст; Лира отвечала наугад.
Теперь: сервер отдаёт per_taler (и до пополнения), «Мозг» → «ИИ-баланс» показывает «1 талер ≈ N ответов» (ПК и телефон),
в руководстве — раздел «Талер», а к вопросу о талерах Лира получает настоящие числа своего счёта."""
import json, os, re, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


php = (ROOT / "server" / "dwrapp" / "cloud.php").read_text(encoding="utf-8")
ok(php.count("'per_taler' =>") == 2, "сервер: per_taler — и у ключа, и у счёта сайта")
ok("'per_taler' => $avg > 0 ? (int)floor(1 / $avg) : 0" in php, "ключ: по средней цене ответа (до разговоров — по основной модели)")
pc = (ROOT / "ui" / "studio" / "dewiar.js").read_text(encoding="utf-8")
ok('id="cc-per"' in (ROOT / "ui" / "settings.html").read_text(encoding="utf-8") and "1 талер ≈ ${pt.toLocaleString" in pc, "ПК: «Мозг» → «ИИ-баланс» — строка «1 талер ≈ N ответов»")
ph = (ROOT / "android" / "assets" / "www" / "app.js").read_text(encoding="utf-8")
ok('id="cl-per"' in ph and "1 талер ≈ ${pt.toLocaleString" in ph, "телефон: «Мозг» → «Баланс» — та же строка")

# расчёт строки: с сервера, у старого сервера — по остатку
import subprocess  # noqa: E402
js = re.search(r"const perTaler = [^\n]+", pc).group(0)
r = subprocess.run(["node", "-e", js + "; console.log(JSON.stringify([perTaler({per_taler: 64}), perTaler({balance: 2.5, turns: 160}), perTaler({balance: 0, turns: 0}), perTaler(null)]))"],
                   capture_output=True, text=True)
ok(r.stdout.strip() == "[64,64,0,0]", f"1 талер: с сервера / по остатку / пусто — {r.stdout.strip() or r.stderr[:100]}")

# руководство: Лира находит ответ
import guide  # noqa: E402
g = json.loads((ROOT / "data" / "guide.json").read_text(encoding="utf-8"))
t = next((x for x in g if x["id"] == "taler"), None)
ok(t and "1 талер ≈" in " ".join(t["how"]) and "phone" in t["where"], "руководство: раздел «Талер» для ПК и телефона")
h = guide.hint("на сколько хватает 1 талер?") if hasattr(guide, "hint") else ""
ok("Талер" in str(h), f"вопрос из жалобы находит раздел: {str(h)[:80]}")

# живые числа к вопросу о талерах
import engine as E  # noqa: E402
e = E.Engine.__new__(E.Engine)
e.cloud = type("C", (), {"status": lambda self: {"connected": True, "per_taler": 64, "balance": 2.5, "balance_text": "", "turns": 160}})()
s = e._taler_now()
ok("1 талер ≈ 64 обычных ответов" in s and "примерно на 160 ответов" in s, f"Лире — настоящие числа: {s[:110]}")
e.cloud = type("C", (), {"status": lambda self: {"connected": False}})()
ok("не подключены" in e._taler_now(), "облако не подключено — так и скажет")
import engine_answer as EA  # noqa: E402
ok(EA.TALER_RX.search("на сколько хватает 1 талер?") and "_taler_now()" in (ROOT / "core" / "engine_answer.py").read_text(encoding="utf-8"),
   "вопрос о талерах — справка с числами к вопросу")
print("ALL OK" if not fails else f"FAILED: {len(fails)}")
sys.exit(1 if fails else 0)
