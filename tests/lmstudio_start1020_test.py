"""Отчёт №118 (19.10): «Не видит LM Studio. Хотя установлено. Обновил, перезагружал…» — у LM Studio сервер по умолчанию
выключен, «Найти Ollama или LM Studio» его не находил и говорил «не запущены». Теперь: LM Studio стоит (есть ~/.lmstudio и его
командная строка lms) — «Найти» сам включает сервер (`lms server start`), порт берёт из `lms server status` и добавляет
профиль; включить не вышло — понятная подсказка, где в LM Studio переключатель. Проверка — с поддельным lms в поддельном HOME."""
import json, os, socket, subprocess, sys, tempfile, textwrap
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


tmp = Path(tempfile.mkdtemp())
PORT = free()
home = tmp / "home"
(home / ".lmstudio/bin").mkdir(parents=True)
srv = tmp / "srv"; (srv / "v1").mkdir(parents=True)
(srv / "v1/models").write_text(json.dumps({"data": [{"id": "qwen3-4b"}]}))
lms = home / ".lmstudio/bin/lms"
lms.write_text(textwrap.dedent(f"""\
    #!/bin/sh
    echo "$@" >> "{tmp}/lms.log"
    if [ "$1 $2" = "server start" ]; then
      [ -f "{tmp}/broken" ] && {{ echo "Error: failed to start"; exit 1; }}
      cd "{srv}" && nohup {sys.executable} -m http.server {PORT} --bind 127.0.0.1 >/dev/null 2>&1 &
      echo "Starting server..."; sleep 1; echo "Success! Server is now running on port {PORT}"
    elif [ "$1 $2" = "server status" ]; then
      [ -f "{tmp}/weird" ] && {{ echo "Server: ON"; exit 0; }}
      [ -f "{tmp}/broken" ] && {{ echo "The server is not running."; exit 0; }}
      echo "The server is running on port {PORT}."
    fi
    """))
lms.chmod(0o755)
code = ("import sys, json; sys.path.insert(0, sys.argv[1]); import llm\n"
        "try:\n    print(json.dumps(llm.discover_local(start=True), ensure_ascii=False))\n"
        "except llm.LLMError as e:\n    print(json.dumps({'error': str(e)}, ensure_ascii=False))\n")


def discover():
    r = subprocess.run([sys.executable, "-c", code, str(ROOT / "core")], capture_output=True, text=True, timeout=120,
                       env=dict(os.environ, HOME=str(home), PATH="/usr/bin:/bin"))
    return json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {"error": r.stderr[-300:]}


try:
    # сервер выключен, включить не выходит — подсказка, где переключатель
    (tmp / "broken").write_text("1")
    d = discover()
    others = isinstance(d, list)                          # на этой машине уже есть другой сервер моделей — подсказки не будет
    ok(others or ("Developer" in d.get("error", "") and "Status: Running" in d["error"]), f"не включился — подсказка, где в LM Studio сервер: {d}")
    (tmp / "broken").unlink()
    d = discover()
    lm = [f for f in d if f.get("preset") == "lmstudio"] if isinstance(d, list) else []
    ok(lm and lm[0]["base_url"] == f"http://127.0.0.1:{PORT}/v1" and lm[0]["models"] == ["qwen3-4b"] and lm[0].get("started"),
       f"сервер включён сам (lms server start), порт — из lms server status, модель видна: {d}")
    log = (tmp / "lms.log").read_text()
    ok("server start" in log and "server status" in log, f"вызовы lms: {log.split(chr(10))}")
    d2 = discover()
    lm2 = [f for f in d2 if f.get("preset") == "lmstudio"] if isinstance(d2, list) else []
    ok(lm2 and not lm2[0].get("started") and (tmp / "lms.log").read_text().count("server start") == log.count("server start"),
       "сервер уже работает (на своём порту) — второй раз не включаем, находим по lms server status")
    # №496 (03.11): «Success! Server is now running on port 1234», а status ответил по-своему — порт из ответа start
    subprocess.run(["pkill", "-f", f"http.server {PORT}"], capture_output=True)
    import time; time.sleep(0.5)
    (tmp / "weird").write_text("1")
    d3 = discover()
    lm3 = [f for f in d3 if f.get("preset") == "lmstudio"] if isinstance(d3, list) else []
    ok(lm3 and lm3[0]["base_url"].endswith(f":{PORT}/v1") and lm3[0].get("started"), f"status не назвал порт — берём из ответа start: {d3}")
    (tmp / "weird").unlink()
    js = (ROOT / "ui/studio/brain.js").read_text(encoding="utf-8")
    ok("f.started" in js and "Сервер LM Studio был выключен — включила" in js, "студия говорит, что сервер LM Studio включён")
finally:
    subprocess.run(["pkill", "-f", f"http.server {PORT}"], capture_output=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
