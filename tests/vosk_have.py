"""Модель имён Vosk (vosk-model-small-ru-0.22, 45 МБ) для проверок, где ядро слушает речь из WAV: «хватит» поверх
рассказа, «пауза» и «громче» без имени, отпечаток имени, голосовое в Telegram. В пакете её нет — ядро берёт zip из data/
или скачивает с alphacephei.com (или DEWIAR_VOSK_URL). Где ни того, ни другого (среда без доступа к сайту, 04.11) —
такие проверки не «красные», а пропущены с причиной: «⏭ ПРОПУСК: …» (run_all.sh показывает их отдельно).

    from vosk_have import vosk_missing, skip_without_vosk
    skip_without_vosk(ROOT)            # нет модели — строка «⏭ ПРОПУСК: …» и выход с кодом 0
"""
import os, sys
from pathlib import Path

NAME = "vosk-model-small-ru-0.22"
URL = "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip"
_cache = {}


def vosk_missing(root) -> str:
    """'' — модель ядру достанется (zip в data/ или адрес отвечает); иначе — почему нет (для строки пропуска)."""
    root = Path(root)
    if (root / "data" / f"{NAME}.zip").exists():
        return ""
    urls = [u for u in (os.environ.get("DEWIAR_VOSK_URL"), URL) if u]
    key = tuple(urls)
    if key in _cache:
        return _cache[key]
    why = []
    for u in urls:
        try:
            import httpx
            r = httpx.get(u, headers={"Range": "bytes=0-0"}, timeout=10, follow_redirects=True)
            if r.status_code in (200, 206):
                _cache[key] = ""
                return ""
            why.append(f"{u.split('/')[2]} ответил {r.status_code}")
        except Exception as e:  # noqa: BLE001 — нет сети, прокси не пускает
            why.append(f"{u.split('/')[2]} недоступен ({type(e).__name__})")
    _cache[key] = (f"нет модели Vosk {NAME}: в data/ её zip нет, скачать нельзя — " + "; ".join(why)
                   + f". Положите {NAME}.zip в data/ или задайте DEWIAR_VOSK_URL")
    return _cache[key]


def skip_without_vosk(root):
    why = vosk_missing(root)
    if why:
        print("⏭ ПРОПУСК: " + why)
        sys.exit(0)
