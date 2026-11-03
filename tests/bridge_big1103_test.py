"""№473/№474 (01.11, ПК 0.76.0): «Ошибка в виджете: нет связи с ядром — вопрос вернул в поле, отправьте ещё раз».
Ядро не падало и не перезапускалось — человек приложил к вопросу выгрузку переписки (несколько файлов), сообщение вышло
больше прежнего предела связи 16 МБ, и websockets молча рвал связь (1009): окно видело «нет связи», у ядра — ни строчки.
Теперь предел больше, а всё сверх MSG_MAX получает отказ словами, связь остаётся и следующий вопрос уходит."""
import json, os, socket, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import bridge  # noqa: E402
from websockets.sync.client import connect  # noqa: E402

s = socket.socket(); s.bind(("127.0.0.1", 0)); PORT = s.getsockname()[1]; s.close()
bridge.MSG_MAX = 30 * 1024 * 1024                    # в проверке — поменьше, чтобы не гонять сотни мегабайт
got = []


def handler(cmd, args):
    got.append((cmd, len(json.dumps(args))))
    return {"hello": True} if cmd == "hello" else {"ok": True}


B = bridge.Bridge("tok", port=PORT)
B.handler = handler
B.start()
ok(B.ready.is_set(), "связь поднялась")
with connect(f"ws://127.0.0.1:{PORT}", max_size=None) as ws:
    ws.send(json.dumps({"cmd": "hello", "token": "tok"}))
    ok(json.loads(ws.recv(timeout=5))["type"] == "hello", "окно подключилось")
    # 20 МБ — два-три файла выгрузки переписки: раньше (предел 16 МБ) связь рвалась
    ws.send(json.dumps({"id": 1, "cmd": "say", "args": {"text": "оцени переписку", "files": [{"name": "messages.html", "b64": "A" * (20 * 1024 * 1024)}]}}))
    r = json.loads(ws.recv(timeout=20))
    ok(r.get("id") == 1 and r.get("ok") is True and got[-1][0] == "say", f"20 МБ вложений — дошли до ядра, ответ пришёл: {str(r)[:120]}")
    # больше предела — отказ словами, связь не рвётся
    ws.send(json.dumps({"id": 2, "cmd": "say", "args": {"text": "ещё", "files": [{"name": "big.zip", "b64": "B" * (34 * 1024 * 1024)}]}}))
    r = json.loads(ws.recv(timeout=20))
    ok(r.get("id") == 2 and r.get("ok") is False and "слишком большие" in r.get("error", "") and "папку ассистента" in r.get("error", ""),
       f"сверх предела — отказ с причиной, тому же вызову: {r}")
    ok(got[-1][0] == "say" and len(got) == 2, "огромное сообщение в ядро не попало")
    ws.send(json.dumps({"id": 3, "cmd": "ping2", "args": {}}))
    r = json.loads(ws.recv(timeout=5))
    ok(r.get("id") == 3 and r.get("ok") is True, "связь осталась — следующий вопрос уходит")
ok(bridge.MSG_HARD >= 4 * 16 * 1024 * 1024, "жёсткий предел связи — с запасом (десять файлов по 11 МБ)")
ok(bridge.too_big(b'{"id":7,"cmd":"say"' + b"x" * (bridge.MSG_MAX + 1))["id"] == 7, "id вызова находится и в байтах")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
