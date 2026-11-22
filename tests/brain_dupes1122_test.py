"""Владелец 22.11 (снимок «Мозг» персонажа): «в выборе мозга три Гугла и мозг Dewiar — непонятно, что выбирать». Каждое
«Подключить» по ключу добавляло новый профиль с тем же сервисом и моделью. Теперь: студия переподключает в тот же профиль
(тот же адрес и модель), а уже набравшиеся одинаковые при запуске сливаются в один — ссылки персонажей переходят к нему."""
import json, os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


import settings as SM  # noqa: E402
g = {"kind": "openai", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-flash-latest", "api_key": "k1"}
f = tmp / "settings.json"
f.write_text(json.dumps({"llm": {"active": "g2", "profiles": {
    "dw": {"name": "Dewiar Облако", "cloud": True, "base_url": "https://dewiar.pro/dwrapp/cloud.php?p=", "kind": "openai", "model": "chat"},
    "g1": dict(g, name="Google Gemini — gemini-flash-latest"), "g2": dict(g, name="Google Gemini — gemini-flash-latest"),
    "g3": dict(g, base_url=g["base_url"] + "/", name="Google Gemini — gemini-flash-latest"),
    "g4": dict(g, model="gemini-pro-latest", name="Google Gemini — gemini-pro-latest")},
    "persona": {"lira": "g1", "patrick": "g4"}}}), encoding="utf-8")
s = SM.Settings(f)
s.load()
pr = s.get("llm", "profiles")
ok(sorted(pr) == ["dw", "g2", "g4"], f"три одинаковых Гугла — один (остался выбранный), другая модель и облако — на месте: {sorted(pr)}")
ok(s.get("llm", "persona") == {"lira": "g2", "patrick": "g4"} and s.get("llm", "active") == "g2", "Лира думала лишним — теперь тем же, оставшимся")
cj = (ROOT / "ui/studio/connect.js").read_text(encoding="utf-8")
ok(cj.count("ckSame(") >= 3 and "ckId = ckSame(prof) || uid()" in cj, "студия: «Подключить» тот же сервис и модель — в тот же профиль")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
