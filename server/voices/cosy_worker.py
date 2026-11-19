"""CosyVoice3 — проба (19.11, владелец: «можно попробовать… чтобы легко убрать; со временем придёт что-то лучше — не замусорить
систему»). Отдельный процесс в своём окружении (/opt/cosy, ставится в образ только если в панели выбран движок CosyVoice3):
зависимости CosyVoice не смешиваются со службой голосов. app.py запускает его сам, когда нужен, и говорит с ним по
localhost; сбой здесь — фраза уходит ESpeech.

  GET  /ready → {"ok": true, "sr": частота}
  POST /tts   JSON {text, ref (путь к образцу wav), ref_text, instruct?} → float32 моно, частота — в заголовке X-Rate

--fake — без модели (проверки): тон длиной по тексту."""
import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

P = argparse.ArgumentParser()
P.add_argument("--model", default="FunAudioLLM/Fun-CosyVoice3-0.5B-2512")
P.add_argument("--port", type=int, default=8011)
P.add_argument("--src", default="/opt/cosy/src")
P.add_argument("--fake", action="store_true")
A = P.parse_args()
PROMPT = "You are a helpful assistant."           # как в примерах CosyVoice3: подсказка<|endofprompt|>текст образца
M, SR = None, 24000


def load():
    global M, SR
    if A.fake:
        return
    sys.path[:0] = [A.src, A.src + "/third_party/Matcha-TTS"]
    from huggingface_hub import snapshot_download
    from cosyvoice.cli.cosyvoice import AutoModel
    M = AutoModel(model_dir=snapshot_download(A.model))      # веса — в общей папке моделей (HF_HUB_CACHE), как у остальных
    SR = int(M.sample_rate)


def synth(text, ref, ref_text, instruct):
    if A.fake:
        n = int(SR * min(10.0, 0.06 * max(1, len(text))))
        return (0.1 * np.sin(np.arange(n) * 2 * np.pi * 220 / SR)).astype(np.float32)
    if instruct:
        gen = M.inference_instruct2(text, f"{PROMPT} {instruct}<|endofprompt|>", ref, stream=False)
    else:
        gen = M.inference_zero_shot(text, f"{PROMPT}<|endofprompt|>{ref_text}", ref, stream=False)
    parts = [j["tts_speech"].squeeze().detach().cpu().numpy().astype(np.float32) for j in gen]
    return np.concatenate(parts) if parts else np.zeros(1, np.float32)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/ready":
            return self._send(200, json.dumps({"ok": True, "sr": SR}).encode())
        self._send(404, b"{}")

    def do_POST(self):
        if self.path != "/tts":
            return self._send(404, b"{}")
        try:
            b = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            w = synth(str(b.get("text") or ""), str(b.get("ref") or ""), str(b.get("ref_text") or ""), str(b.get("instruct") or ""))
            self._send(200, w.tobytes(), "application/octet-stream", {"X-Rate": str(SR)})
        except Exception as e:  # noqa: BLE001
            self._send(500, json.dumps({"error": str(e)[:300]}, ensure_ascii=False).encode())


if __name__ == "__main__":
    load()
    ThreadingHTTPServer(("127.0.0.1", A.port), H).serve_forever()
