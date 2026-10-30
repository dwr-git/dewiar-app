"""Своя модель с маленьким окном контекста (29.10, пакет: «не влезло в окно модели» — 102 за неделю; отчёт №407 — 176
сбоев за сутки; Ollama с окном 4096 молча отрезает начало подсказки — характер и инструменты).
- окно узнаётся у LM Studio (/api/v0/models: loaded_context_length), Ollama (/api/ps: context_length), vLLM (/models:
  max_model_len); не узнать — None;
- всё влезает — без изменений; не влезает — по ступеням: без старой истории → без действий → самая короткая подсказка;
  заметка с советом — один раз;
- облако и Dewiar не трогаем (окно у них большое и не наше)."""
import json, os, sys, threading, types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


KIND = {"k": "lmstudio", "n": 4096}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _j(self, code, o):
        b = json.dumps(o).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        k, n = KIND["k"], KIND["n"]
        if self.path == "/api/v0/models" and k == "lmstudio":
            return self._j(200, {"data": [{"id": "other", "state": "not-loaded", "max_context_length": 131072},
                                          {"id": "qwen2.5-7b", "state": "loaded", "loaded_context_length": n, "max_context_length": 32768}]})
        if self.path == "/api/ps" and k == "ollama":
            return self._j(200, {"models": [{"name": "qwen2.5:7b", "model": "qwen2.5:7b", "context_length": n}]})
        if self.path == "/v1/models" and k == "vllm":
            return self._j(200, {"data": [{"id": "Qwen/Qwen3-8B", "max_model_len": n}]})
        if self.path == "/v1/models":
            return self._j(200, {"data": [{"id": "x"}]})
        self._j(404, {})


srv = ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{srv.server_address[1]}/v1"
import llm  # noqa: E402

ok(llm.context_window({"base_url": BASE, "model": "qwen2.5-7b"}) == 4096, "LM Studio: окно загруженной модели (loaded_context_length)")
llm._ctx_cache.clear(); KIND.update(k="ollama", n=2048)
ok(llm.context_window({"base_url": BASE, "model": "qwen2.5:7b"}) == 2048, "Ollama: окно запущенной модели (/api/ps)")
llm._ctx_cache.clear(); KIND.update(k="vllm", n=32768)
ok(llm.context_window({"base_url": BASE, "model": "Qwen/Qwen3-8B"}) == 32768, "vLLM: max_model_len")
llm._ctx_cache.clear(); KIND.update(k="none")
ok(llm.context_window({"base_url": BASE, "model": "x"}) is None, "сервер не говорит окно — None (ничего не меняем)")
ok(llm.context_window({"base_url": "http://127.0.0.1:9/v1"}) is None, "сервер недоступен — None, без ошибки")

import engine_answer as EA  # noqa: E402
notes = []
SYS_FULL = "Ты Лира. " + "Правила действий и навыки. " * 900          # ≈ 24 тыс. знаков ≈ 8 тыс. токенов
SYS_NO = "Ты Лира. Память о пользователе. " * 120                     # ≈ 4 тыс. знаков
SYS_LEAN = "Ты Лира. Короткие правила. " * 150                      # ≈ 3,5 тыс. знаков
e = types.SimpleNamespace(_system=lambda with_tools=False, lean=None: (SYS_LEAN if lean else SYS_FULL) if with_tools else SYS_NO,
                          _system_min=lambda: "Ты Лира.", note=notes.append)
CORE = ["weather", "set_reminder", "calc", "web_search"]
specs = [{"name": CORE[i] if i < len(CORE) else f"tool{i}", "description": "Делает что-то полезное " * 8,
          "parameters": {"type": "object", "properties": {}}} for i in range(60)]
hist = [{"role": "user", "content": "Расскажи длинную историю " * 60}, {"role": "assistant", "content": "Жила-была " * 300},
        {"role": "user", "content": "(Сообщение пользователя)\nКакая погода?"}]
fit = lambda prof, s, sp, ms: EA.AnswerMixin._fit_window(e, prof, s, sp, ms)  # noqa: E731

llm._ctx_cache.clear(); KIND.update(k="lmstudio", n=131072)
P = {"base_url": BASE, "model": "qwen2.5-7b", "max_tokens": 1024}
s1, sp1, m1 = fit(P, SYS_FULL, specs, hist)
ok(s1 == SYS_FULL and sp1 == specs and m1 == hist and not notes, "окно большое — ничего не меняем")

llm._ctx_cache.clear(); KIND.update(n=15000)
s2, sp2, m2 = fit(P, SYS_FULL, specs, hist)
ok(sp2 == specs and len(m2) == 1 and s2 == SYS_FULL, "чуть не влезает — только без старой истории, действия остаются")

llm._ctx_cache.clear(); KIND.update(n=6144)
s3, sp3, m3 = fit(P, SYS_FULL, specs, hist)
ok([x["name"] for x in sp3] == CORE and s3 == SYS_LEAN and len(m3) == 1, "меньше — главные действия на каждый день, короткая инструкция")
ok(len(notes) == 1 and "6144" in notes[0] and "главными действиями" in notes[0] and "32768" in notes[0] and "OLLAMA_CONTEXT_LENGTH" in notes[0],
   f"заметка с советом: {notes}")

llm._ctx_cache.clear(); KIND.update(n=2500)
s3, sp3, m3 = fit(P, SYS_FULL, specs, hist)
ok(sp3 == [] and s3.startswith(SYS_NO) and "маленькое окно" in s3 and len(m3) == 1, "совсем мало — без действий, с честной фразой")

llm._ctx_cache.clear(); KIND.update(n=900)
s4, sp4, m4 = fit(P, SYS_FULL, specs, hist)
ok(s4 == "Ты Лира." and sp4 == [] and len(notes) == 1, "совсем крошечное — самая короткая подсказка; заметка второй раз не повторяется")

for prof, why in (({"base_url": "https://dewiar.pro/dwrapp/cloud.php?p=", "cloud": True}, "облако Dewiar"),
                  ({"base_url": "https://api.openai.com/v1", "model": "gpt-4.1"}, "чужой облачный сервис")):
    s5, sp5, m5 = fit(prof, SYS_FULL, specs, hist)
    ok(s5 == SYS_FULL and sp5 == specs and m5 == hist, f"{why} — не трогаем")

# «Проверить» в «Мозге»: окно и совет — сразу, а не после первых сбоев
import httpx  # noqa: E402
llm._ctx_cache.clear(); KIND.update(k="lmstudio", n=4096)
orig = llm.stream_chat, llm.probe_tools
llm.stream_chat = lambda p, s, m, **k: iter(["готово"]); llm.probe_tools = lambda p: "native"
r = llm.test_profile({"base_url": BASE, "model": "qwen2.5-7b"})
ok(r["ok"] and r["ctx"] == 4096 and "4096" in r["ctx_note"] and "без действий" in r["ctx_note"] and "32768" in r["ctx_note"],
   f"«Проверить»: окно 4096 — совет сразу: {r.get('ctx_note')!r}")
llm._ctx_cache.clear(); KIND.update(n=65536)
r = llm.test_profile({"base_url": BASE, "model": "qwen2.5-7b"})
ok(r["ok"] and r["ctx"] == 65536 and r["ctx_note"] == "", "окно 65536 — без замечаний")
llm.stream_chat, llm.probe_tools = orig
br = (ROOT / "ui/studio/brain.js").read_text(encoding="utf-8")
ok("r.ctx_note" in br, "студия «Мозг» показывает совет про окно")
src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("system, specs, msgs = self._fit_window(prof, system, specs, msgs)" in src and "self._system_min(), msgs[-1:]" in src,
   "в ходе разговора: подгонка до запроса; и без действий не влезло — самая короткая подсказка")
srv.shutdown()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
