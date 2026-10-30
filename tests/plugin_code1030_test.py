"""Плагин со своим кодом (владелец 30.10: «у меня готовые модули — тендеры, резюме и кадры; если бы их можно было включать
как плагины — Лира стала бы масштабируемой»). Код лежит в папке плагина и запускается его MCP-сервером: в command/args
{python} — Python программы, {plugin_dir} — папка плагина; lib/ плагина — в пути модулей. Плагин из zip — ставится,
его функции видны помощнице и вызываются; удалили — сервер уходит."""
import io, json, os, shutil, sys, tempfile, zipfile
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


import settings as ST  # noqa: E402
import plugins as PL  # noqa: E402
import mcp as M  # noqa: E402

srv = (ROOT / "tests/mcp_test_server.py").read_text().replace('"text": "эхо: " + a["text"]', '"text": "эхо: " + a["text"] + " · " + __import__("helper").MARK')
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:
    z.writestr("orders/plugin.json", json.dumps({"id": "orders", "name": "Заказы", "icon": "📑", "tagline": "Подходящие тендеры — сами",
                                                  "description": "Смотрит площадки и говорит, когда есть подходящее.", "phrases": ["Есть новые тендеры?"],
                                                  "mcp": {"main": {"type": "stdio", "command": "{python}", "args": ["{plugin_dir}/server.py"]}}}, ensure_ascii=False))
    z.writestr("orders/server.py", srv)
    z.writestr("orders/lib/helper.py", "MARK = 'из lib плагина'\n")
    z.writestr("orders/README.md", "# Тендеры\n")
s = ST.Settings(tmp / "s.json")
P = PL.Plugins(s)
pid = P.install_zip(buf.getvalue())
P.install(pid)
cfg = (s.get("mcp", "servers") or {}).get("orders-main") or {}
ok(cfg.get("plugin") == "orders" and cfg.get("command") == "{python}", f"сервер плагина записан как есть, папка — при запуске: {cfg}")
x = M.plugin_expand(cfg)
ok(x["command"] == sys.executable and x["args"][0].endswith("orders/server.py") and Path(x["args"][0]).is_file()
   and x["env"]["PYTHONPATH"].split(os.pathsep)[0].endswith("orders/lib")
   and Path(x["env"]["DEWIAR_PLUGIN_DATA"]).is_dir() and json.loads(x["env"]["DEWIAR_PLUGIN_SETTINGS"]) == {}, f"{{python}}, {{plugin_dir}} и lib/ подставлены: {x['command']} {x['args']}")
mgr = M.MCPManager(s)
mgr.reconcile()
import time  # noqa: E402
for _ in range(100):
    if (mgr.status().get("orders-main") or {}).get("status") in ("ok", "error"):
        break
    time.sleep(0.1)
ok((mgr.status().get("orders-main") or {}).get("status") == "ok", f"сервер плагина запустился: {mgr.status()}")
names = [t["name"] for t in mgr.specs()] if hasattr(mgr, "specs") else []
echo = next((n for n in names if n.endswith("echo")), "")
ok(echo, f"функции плагина видны помощнице: {names}")
r = mgr.call(echo, {"text": "тендер"}) if echo else ""
ok("эхо: тендер · из lib плагина" in str(r), f"код плагина работает, его библиотеки из lib/: {r}")
mgr.close()
ok(M.plugin_expand({"command": "npx", "args": ["-y", "x"]})["command"] == "npx", "обычные MCP-серверы — как были")
try:
    M.plugin_expand({"plugin": "../evil", "command": "{python}", "args": []})
    ok(False, "чужой путь — отказ")
except M.MCPError:
    ok(True, "id плагина с путём — отказ")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
