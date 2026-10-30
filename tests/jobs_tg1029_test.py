"""Дела по расписанию в Telegram (29.10, пользователи через владельца, снимок): «чтобы само условие не прописывалось в
сообщении агента — только ответ; и пусть вставляет в тему смайлики». В мессенджер — только ответ, без «🗓 <поручение>»;
поручение для мессенджера просит строки со смайликами; в уведомлении — короткое имя дела (готовое — его название)."""
import sys, types
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))
import engine_music as EM  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


M = EM.MusicMixin
long = "Курс доллара, биткоина и TRAIX на сегодня (официальный, по нацбанку моей страны) и изменение со вчера. Курс TRAIX бери с https://www.traiex.com/ru/trading/TRAIX-USDT"
ok(M.job_name({"text": long, "preset": "fx"}) == "Курс валют", "готовое дело (поправили текст) — имя «Курс валют»")
t = M.job_name({"text": long})
ok(t.startswith("Курс доллара") and len(t) <= 41 and "http" not in t and "(" not in t, f"своё дело — начало поручения, коротко, без ссылок: {t}")
ok(M.job_name({"brief": True, "text": "x"}) == "Утренняя сводка", "утренняя сводка")
me = types.SimpleNamespace(_brief_context=lambda: "", _routine_note=lambda silent=True: "")
p_tg = M._job_prompt(me, {"text": long, "deliver": "telegram"})
p_v = M._job_prompt(me, {"text": long, "deliver": "voice"})
ok("смайлик" in p_tg and "без повтора поручения" in p_tg and "смайлик" not in p_v, "в мессенджер — строки со смайликами; голосом — без них")
src = (ROOT / "core/engine_music.py").read_text(encoding="utf-8")
ok("bot.send(text)" in src and 'bot.send(f"🗓 {title}' not in src, "в Telegram и MAX уходит только ответ, поручение не повторяется")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
