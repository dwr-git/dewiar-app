"""№669 (12.11): «студия на рабочем ПК, а Ollama и мои серверы — на другом железе; нода не видит, где прописать сервер с
мозгами». Нода брала только модель на этом компьютере (127.0.0.1). Теперь и свой сервер в домашней сети — из профилей
«Мозга», только частный IPv4 цифрами, без имени и пароля; адрес модели сайт по-прежнему не задаёт. Для такой модели
проверка видеокарты — «у сервера в сети», и пауза не ждёт свою видеокарту и процессор."""
import os, sys, tempfile, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import liranode as N  # noqa: E402
import llm  # noqa: E402

LAN = ["http://192.168.2.44:11434/v1", "http://10.0.0.5:8000/v1", "http://172.20.1.2:1234/v1"]
NOT = ["http://8.8.8.8:11434/v1", "http://192.168.2.44@evil.example/v1", "http://user:pw@192.168.2.44:11434/v1", "http://server.local:11434/v1",
       "http://169.254.1.1:11434/v1", "http://127.0.0.1:11434/v1", "file:///etc/passwd", "http://192.168.2.44.evil.example/v1"]
ok(all(N.is_lan(u) for u in LAN), "свой сервер в домашней сети — частный IPv4 цифрами")
ok(not any(N.is_lan(u) for u in NOT), f"не в счёт: внешние, с паролем, с именем, link-local, сам компьютер: {[u for u in NOT if N.is_lan(u)]}")
ok(N.is_own("http://127.0.0.1:11434/v1") and N.is_own(LAN[0]) and not N.is_own(NOT[0]), "своя модель = этот компьютер или свой сервер в сети")

# «Подходит ли мой компьютер»: профиль «Мозга» на сервере в сети — находится
llm.discover_local = lambda start=False: []
llm._models_at = lambda b, t=1.5: ["gemma4:26b", "qwen3.8:27b"] if "192.168.2.44" in b else None
eng = types.SimpleNamespace(s=types.SimpleNamespace(get=lambda a, b=None: {
    "p1": {"name": "Сервер 192.168.2.44 — gemma4:26b", "kind": "openai", "base_url": "http://192.168.2.44:11434/v1"},
    "p2": {"name": "Облако", "kind": "openai", "base_url": "https://api.example.com/v1"}} if (a, b) == ("llm", "profiles") else None))
found = N.models_here(eng)
ok(len(found) == 1 and found[0]["base_url"] == "http://192.168.2.44:11434/v1" and found[0].get("lan") and "gemma4:26b" in found[0]["models"],
   f"профиль «Мозга» на сервере в сети — найден, чужой облачный — нет: {found}")

# пауза: модель на сервере в сети — своя видеокарта и процессор ни при чём
N.SYS.on_battery = lambda: False
N.SYS.fullscreen = lambda: False
N.SYS.gpu = lambda fresh=False: {"temp": 90, "util": 99, "name": "RTX 4090", "mem_gb": 24}
N.SYS.cpu = lambda: 99
ok(N.blocked({"when": "always", "base": "http://127.0.0.1:11434/v1"}) != "", "своя модель на этом компьютере — горячая видеокарта: пауза")
ok(N.blocked({"when": "always", "base": LAN[0]}) == "", "модель на сервере в сети — своя занятая видеокарта не мешает")
code, why = N.ask_model("http://8.8.8.8:11434/v1", "m", {"messages": [{"role": "user", "content": "x"}]}, 5)
ok(code == 0 and "домашней сети" in why, f"внешний адрес — нода не отдаёт: {why}")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
