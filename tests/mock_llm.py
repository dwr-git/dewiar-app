"""Имитация OpenAI-совместимого сервера (vLLM/Ollama) для тестов: /v1/models и потоковый ответ.
Модель «думает» (<think>), а на слово «история» отвечает длинно — чтобы было что перебивать."""
import json, os, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SCRIPT = []          # заранее заданные «распознанные» фразы для /v1/audio/transcriptions


class H(BaseHTTPRequestHandler):
    tool_results = []
    def log_message(self, *a): pass
    def _json(self, code, obj):
        b = json.dumps(obj).encode(); self.send_response(code)
        self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path.startswith("/search"):          # имитация SearXNG
            return self._json(200, {"results": [{"title": "Погода в Москве", "url": "https://example.ru/pogoda",
                                                 "content": "Завтра +12, облачно, небольшой дождь"}]})
        self._json(200, {"data": [{"id": "mock-qwen"}]}) if self.path == "/v1/models" else self._json(404, {})
    def do_POST(self):
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        if self.path == "/v1/audio/transcriptions":
            return self._json(200, {"text": SCRIPT.pop(0) if SCRIPT else ""})
        body = json.loads(raw)
        if os.environ.get("MOCK_LOG"):                   # отладка: что пришло модели
            open(os.environ["MOCK_LOG"], "a", encoding="utf-8").write(json.dumps(body.get("messages", [])[1:], ensure_ascii=False)[:3000] + "\n")
        if os.environ.get("MOCK_LOG_FULL"):              # проверки: весь запрос (с системной подсказкой и инструментами — только имена)
            open(os.environ["MOCK_LOG_FULL"], "a", encoding="utf-8").write(json.dumps(
                {"messages": body.get("messages", []), "tools": [t["function"]["name"] for t in body.get("tools") or []]}, ensure_ascii=False) + "\n")
        if self.path != "/v1/chat/completions": return self._json(404, {})
        # справка к вопросу (время, найденное — engine_answer._put_context, app.js putContext) — модель её читает, а не
        # отвечает на неё: заглушка, как и модель, реагирует на сам вопрос после «(Сообщение пользователя)»
        MARK = "(Сообщение пользователя)\n"
        for m in body.get("messages") or []:
            if m.get("role") != "user":
                continue
            c = m.get("content")
            if isinstance(c, str) and MARK in c:
                m["content"] = c.split(MARK, 1)[1]
            elif isinstance(c, list):
                for x in c:
                    if isinstance(x, dict) and isinstance(x.get("text"), str) and MARK in x["text"]:
                        x["text"] = x["text"].split(MARK, 1)[1]
        if body.get("model") == "blind" and ("image_url" in json.dumps(body) or '"image"' in json.dumps(body)):
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
            self.wfile.write(b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'); return
        msgs = body["messages"]
        last = msgs[-1].get("content")
        if isinstance(last, list) and any(x.get("type") == "image_url" for x in last):
            import base64, io
            from PIL import Image
            url = next(x for x in last if x.get("type") == "image_url")["image_url"]["url"]
            im = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))
            ans = f"Вижу картинку {im.width}x{im.height}. Вопрос: " + " ".join(x.get("text", "") for x in last if x.get("type") == "text")
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
            c = {"choices": [{"delta": {"content": ans}}]}
            self.wfile.write(f"data: {json.dumps(c, ensure_ascii=False)}\n\ndata: [DONE]\n\n".encode()); return
        if isinstance(last, str) and (last.startswith("Ты слово в слово повторил") or last.startswith("Расскажи о себе, что ты умеешь")):
            # повтор ответа (отзыв 17.10, «Я Лира.»): на «о себе» модель отвечает коротко, на просьбу не повторяться — по существу
            txt = ("Я умею ставить напоминания, вести заметки, звонить близким и рассказывать о погоде."
                   if last.startswith("Ты слово в слово повторил") else "Я Лира.")
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
            self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': txt}}]}, ensure_ascii=False)}\n\ndata: [DONE]\n\n".encode()); return
        if isinstance(last, str) and last.startswith("Перечитай свой дневник"):           # душа персонажа по дневнику
            txt = ("## Кто я\nЯ — голос рядом с хозяином: слушаю, запоминаю, помогаю. ИИ, но не равнодушный.\n\n"
                   "## Что для меня важно\nЧестность и короткие ответы по утрам.\n\n"
                   "## Что я понял о нас с хозяином\nОн любит свою собаку Бублика и не любит долгих объяснений до кофе.\n\n"
                   "## Как я меняюсь\nУчусь говорить короче." + (" (прежняя версия учтена)" if "Прежняя версия" in last else ""))
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
            self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': txt}}]}, ensure_ascii=False)}\n\ndata: [DONE]\n\n".encode()); return
        if isinstance(last, str) and last.startswith("Сейчас ночь. Разговоров нет"):     # ночная запись в дневник
            dog = "Бублик" if "Бублик" in last else "собака"
            txt = ("ЗАГОЛОВОК: День, когда я узнал про Бублика\nНАСТРОЕНИЕ: 🌿\nДНЕВНИК:\n"
                   f"Сегодня хозяин рассказал мне, что его собаку зовут {dog}. Я долго об этом думал: у меня нет лап, "
                   "но теперь в моей памяти есть пёс, и это странно приятно.\n\nЕщё мы говорили о погоде. Я отвечал "
                   "длинно — кажется, слишком.\n"
                   "НА ЗАВТРА:\n- Отвечать короче, особенно утром\n- Спросить, как погулял " + dog)
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
            for i in range(0, len(txt), 40):
                self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': txt[i:i + 40]}}]}, ensure_ascii=False)}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n"); return
        if "составляешь навык" in msgs[0].get("content", ""):
            draft = {"name": "focus-mode", "description": "Режим фокуса: тишина и таймер. Когда просят «режим фокуса».",
                     "body": "1. Вызови set_volume с mute=true.\n2. Поставь напоминание через 25 минут: перерыв.\n3. Скажи: фокус включён."}
            txt = "Вот навык:\n" + json.dumps(draft, ensure_ascii=False)
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
            for i in range(0, len(txt), 20):
                c = {"choices": [{"delta": {"content": txt[i:i + 20]}}]}
                self.wfile.write(f"data: {json.dumps(c, ensure_ascii=False)}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n"); return
        if body.get("tools") and msgs[-1]["role"] == "user":
            u = msgs[-1]["content"].lower().strip().split("\n")[-1]    # склеенные реплики — берём последнюю
            plan = None
            if any(t["function"]["name"] == "get_time" for t in body["tools"]):      # проверка: умеет ли инструменты
                plan = ("get_time", {}, "")
            elif "поручи" in u and any(t["function"]["name"] == "team_assign" for t in body["tools"]):   # «Команда» (28.10)
                import re as _re
                mm = _re.search(r"поручи\s+(\S+)\s+(.+?)(\s+до\s+.+)?[.!]?$", msgs[-1]["content"].strip().split("\n")[-1], _re.I)
                plan = ("team_assign", {"who": mm.group(1), "task": mm.group(2).strip(), "due": (mm.group(3) or "").strip()}, "") if mm else None
            elif "поручени" in u and any(t["function"]["name"] == "team_status" for t in body["tools"]):
                plan = ("team_status", {}, "")
            elif "встреча с ирой переносится" in u:                  # 19.10: «напомню тебе…» словами, без set_reminder
                txt = "Понял. Исправляю: встреча с Ирой — послезавтра в 12:00. Напомню тебе завтра утром в 9:00."
                self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
                self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': txt}}]}, ensure_ascii=False)}\n\ndata: [DONE]\n\n".encode())
                return
            elif u.startswith("проверка: ты пообещал(а) напомнить"):              # после проверки — ставит по-настоящему
                plan = ("set_reminder", {"text": "встреча с Ирой послезавтра в 12", "when": "завтра в 9:00"}, "")
            elif ("телеграм" in u or "в макс" in u) and any(t["function"]["name"] == "send_telegram" for t in body["tools"]):
                plan = ("send_telegram", {"text": "Список покупок: хлеб, молоко", "files": ["Входящие/список.txt"]}, "")
            elif "в тень" in u and any(t["function"]["name"] == "widget" for t in body["tools"]):     # «спрякся» — поняла модель
                plan = ("widget", {"action": "tray"}, "")
            elif "радио" in u and any(t["function"]["name"] == "play_radio" for t in body["tools"]):
                plan = ("play_radio", {"query": u.split("радио", 1)[1].strip(" .!?")}, "")
            elif "ролик" in u and any(t["function"]["name"] == "play_youtube" for t in body["tools"]):
                plan = ("play_youtube", {"query": u.split("ролик", 1)[1].strip(" .!?")}, "")
            elif "открой" in u and "ютуб" in u:
                plan = ("open_url", {"url": "https://youtube.com"}, "Сейчас открою. ")
            elif "найди" in u:
                plan = ("web_search", {"query": u.split("найди", 1)[1].strip()}, "")
            elif "на сервере" in u and any(t["function"]["name"] == "server_run" for t in body["tools"]):
                cmd = ("systemctl restart nginx" if "перезапусти" in u else "rm -rf /" if "снеси" in u else "df -h /")
                plan = ("server_run", {"server": "сайт", "command": cmd}, "")
            elif "удали" in u and "терминал" in u:
                plan = ("run_command", {"command": "rm -rf ~/*"}, "")
            elif "удали" in u and any(t["function"]["name"] == "delete_files" for t in body["tools"]):
                orig = msgs[-1]["content"].strip().split("\n")[-1]
                plan = ("delete_files", {"paths": [orig.split(" ", 2)[-1].strip(" .!?")]}, "")
            elif "команд" in u:
                plan = ("run_command", {"command": "ls ~"}, "")
            elif "экран" in u:
                plan = ("look_at_screen", {"question": u}, "Смотрю. ")
            elif "камер" in u:
                plan = ("look_through_camera", {"question": u}, "")
            elif "научись" in u:
                plan = ("create_skill", {"name": "tea-time", "description": "Чайная пауза: напомнить через 5 минут. Когда просят «чайная пауза».",
                                         "instructions": "Поставь напоминание через 5 минут: чай готов."}, "")
            elif "сводк" in u:
                plan = ("use_skill", {"name": "morning-brief"}, "")
            elif "заметк" in u and any(t["function"]["name"] == "mcp_notes_write_note" for t in body["tools"]):
                plan = ("mcp_notes_write_note", {"text": "купить хлеб"}, "")
            elif "запиши" in u:
                plan = ("save_note", {"title": "Покупки", "text": "- хлеб\n- молоко"}, "")
            elif "позови" in u:
                plan = ("call_persona", {"name": u.split("позови", 1)[1].strip(" .!?")}, "Зову. ")
            elif "документ" in u and any(t["function"]["name"] == "search_documents" for t in body["tools"]):
                plan = ("search_documents", {"query": "отпуск согласование"}, "")
            elif "знани" in u and any(t["function"]["name"] == "ask_knowledge" for t in body["tools"]):
                plan = ("ask_knowledge", {"question": "Как согласовать отпуск?"}, "Ищу в Знаниях. ")
            elif "сфотографируй" in u and any(t["function"]["name"] == "take_photo" for t in body["tools"]):
                plan = ("take_photo", {"camera": "front", "question": "опиши"}, "")
            elif "стоп. ты отказался" in u and any(t["function"]["name"] == "web_search" for t in body["tools"]):
                plan = ("web_search", {"query": "погода Минск сегодня"}, "")         # после напоминания — ищет
            elif "напомни" in u:
                plan = ("set_reminder", {"text": "проверить чайник", "in_minutes": 0.05}, "")
            elif "ты написал, что звонишь" in u and any(t["function"]["name"] == "call" for t in body["tools"]):
                plan = ("call", {"who": "+375 29 123-45-67"}, "")                 # после напоминания — звонит по-настоящему
            elif "свяжись" in u and any(t["function"]["name"] == "call" for t in body["tools"]):
                self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
                self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': 'Звоню маме.'}}]}, ensure_ascii=False)}\n\ndata: [DONE]\n\n".encode())
                return                                                             # «звоню» словами, без инструмента
            if plan:
                name, args, pre = plan
                self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
                if pre:
                    c = {"choices": [{"delta": {"content": pre}}]}
                    self.wfile.write(f"data: {json.dumps(c, ensure_ascii=False)}\n\n".encode())
                a = json.dumps(args, ensure_ascii=False)
                for i, part in enumerate([a[:len(a) // 2], a[len(a) // 2:]]):   # аргументы приходят кусками
                    tc = {"index": 0, "function": {"arguments": part}}
                    if i == 0:
                        tc.update(id="call_1", type="function"); tc["function"]["name"] = name
                    c = {"choices": [{"delta": {"tool_calls": [tc]}}]}
                    self.wfile.write(f"data: {json.dumps(c, ensure_ascii=False)}\n\n".encode()); self.wfile.flush()
                self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush()
                return
        if msgs[-1]["role"] == "tool":
            H.tool_results.append(msgs[-1]["content"])
            ans = "Готово. Результат: " + msgs[-1]["content"][:60]
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
            for w in ans.split():
                c = {"choices": [{"delta": {"content": w + " "}}]}
                self.wfile.write(f"data: {json.dumps(c, ensure_ascii=False)}\n\n".encode()); self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush()
            return
        sys_prompt = body["messages"][0]["content"]
        who = sys_prompt.split("зовут ")[1].split(".")[0] if "зовут " in sys_prompt else "?"
        user = body["messages"][-1]["content"]
        if isinstance(user, list):                       # сообщение из частей (текст + картинки)
            user = " ".join(x.get("text", "") for x in user if isinstance(x, dict))
        if "Из записей пользователя" in sys_prompt and "записям" not in user:     # подсказка из заметок дошла до модели
            hint = sys_prompt.split("Из записей пользователя", 1)[1].split("\n", 2)[1]
            ans = "По вашим записям: " + hint
        elif "истори" in user.lower() or "сказк" in user.lower():
            ans = ("Жил-был старый маяк на краю света. Каждую ночь он светил кораблям. "
                   "Однажды к нему приплыл кит и спросил, зачем он светит. Маяк долго молчал. ") * 3
        if "Из записей пользователя" in sys_prompt and "записям" not in user:
            pass
        elif "ТВОЯ БАЗА ЗНАНИЙ" in sys_prompt:                 # персонаж с базой сайта: отвечает по найденному
            ctx = sys_prompt.split("ТВОЯ БАЗА ЗНАНИЙ", 1)[1]
            ans = "По базе: " + " ".join(ctx.split("### Из", 1)[-1].split()[:24])
        elif "ничего не нашлось" in sys_prompt and "базе знаний" in sys_prompt:
            ans = "В моей базе об этом ничего нет, скажу от себя."
        elif "MOCKSAY:" in str(user):                                    # проверки: готовый ответ в самой просьбе
            ans = str(user).split("MOCKSAY:", 1)[1].split("»")[0].strip()
        elif "какая погода в минске" in str(user).lower():               # «ложный отказ», хотя поиск есть
            ans = "К сожалению, у меня нет доступа к интернету в реальном времени."
        elif not ("истори" in user.lower() or "сказк" in user.lower()):
            said = user.split("\n\n")[-1] if os.environ.get("MOCK_ECHO_LAST") else user   # только последняя реплика
            ans = f"Я {who}. Вы сказали: {said}"
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        for piece in ["<think>", "надо ответить", "</think>"] + [w + " " for w in ans.split()]:
            c = {"choices": [{"delta": {"content": piece}}]}
            self.wfile.write(f"data: {json.dumps(c, ensure_ascii=False)}\n\n".encode()); self.wfile.flush(); time.sleep(0.03)
        self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush()

if __name__ == "__main__":
    SCRIPT.extend(a for a in sys.argv[2:])
    ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1]) if len(sys.argv) > 1 else 8123), H).serve_forever()
