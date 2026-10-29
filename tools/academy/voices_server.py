"""Голоса урока со своего сервера голосов Dewiar (server/voices — Qwen3-TTS на видеокарте): тот же голос, каким Лира
говорит в программе с «Голосом Dewiar». Запускать там, где сервер голосов доступен (на самом сервере — localhost:8000).
Только стандартная библиотека Python.

    python3 voices_server.py lesson.json                       # http://localhost:8000 → voices-<урок>.zip рядом
    python3 voices_server.py lesson.json http://сервер:8000    # другой адрес

Каждому персонажу — его голос по назначению на сервере (поле persona: «Голоса» в панели), иначе — встроенный диктор
(Лира — serena, Патрик — ryan, как в core/personas.py). Готовый архив — в сборку: build.py <урок> --voices voices-….zip
"""
import io
import json
import sys
import urllib.request
import wave
import zipfile
from pathlib import Path

FALLBACK = {"lira": "serena", "patrik": "ryan"}


def main():
    les_path = Path(sys.argv[1])
    url = (sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000").rstrip("/") + "/v1/audio/speech"
    les = json.loads(les_path.read_text(encoding="utf-8"))
    out = les_path.with_name(f"voices-{les_path.parent.name or 'lesson'}.zip")
    with zipfile.ZipFile(out, "w") as z:
        for l in les["lines"]:
            body = json.dumps({"input": l["tts"], "persona": l["who"], "voice": FALLBACK.get(l["who"], "serena"),
                               "response_format": "wav"}).encode()
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                wav = r.read()
            try:
                with wave.open(io.BytesIO(wav)) as w:
                    sec = w.getnframes() / w.getframerate()
            except (wave.Error, EOFError, ZeroDivisionError):
                sec = 0.0
            z.writestr(f"{l['id']}.wav", wav)
            z.writestr(f"{l['id']}.txt", l["tts"])
            print(f"{l['id']}  {sec:4.1f} с  {l['sub']}", flush=True)
    print("готово:", out)


if __name__ == "__main__":
    main()
