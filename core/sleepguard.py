"""Не мешать компьютеру уснуть (идея №70, 29.10: «Windows 11 не уходит в сон — powercfg /requests показал: сон держит
аудиопоток микрофона, открытый pythonw.exe»). Открытый микрофон — это «аудиопоток в работе», и Windows не засыпает,
пока он открыт. Dewiar отпускает микрофон, когда компьютер и так вот-вот уснёт: человек не трогал мышь и клавиатуру
почти столько, сколько стоит «Сон» в параметрах питания, и голоса в микрофоне тоже не было. Тронули мышь — микрофон снова
открыт. «Сон: никогда» — ничего не меняется. Только Windows: в Linux открытый микрофон сну не мешает."""

import os
import re
import subprocess
import time

_cache = {"t": 0.0, "v": None}


def idle_seconds():
    """Сколько секунд не трогали мышь и клавиатуру (Windows), иначе None."""
    if os.name != "nt":
        return None
    try:
        import ctypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
        li = LASTINPUTINFO()
        li.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li)):
            return None
        return max(0.0, (ctypes.windll.kernel32.GetTickCount() - li.dwTime) / 1000.0)
    except Exception:  # noqa: BLE001
        return None


def _on_ac():
    try:
        import ctypes

        class SPS(ctypes.Structure):
            _fields_ = [("ACLineStatus", ctypes.c_byte), ("BatteryFlag", ctypes.c_byte), ("BatteryLifePercent", ctypes.c_byte),
                        ("SystemStatusFlag", ctypes.c_byte), ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]
        s = SPS()
        if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s)):
            return s.ACLineStatus != 0
    except Exception:  # noqa: BLE001
        pass
    return True


def parse_standby(text, on_ac=True):
    """Вывод «powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE» (любой язык) -> секунд до сна или 0 («никогда»).
    Индексов два: от сети, потом от батареи."""
    vals = [int(x, 16) for x in re.findall(r":\s*0x([0-9a-fA-F]{8})\s*$", text or "", re.M)]
    if len(vals) < 2:
        return 0
    return vals[-2] if on_ac else vals[-1]


def standby_seconds():
    """Через сколько секунд простоя Windows уснёт по своим настройкам (0 — никогда). Раз в 10 минут спрашиваем заново."""
    if os.name != "nt":
        return 0
    if _cache["v"] is not None and time.monotonic() - _cache["t"] < 600:
        return _cache["v"]
    v = 0
    try:
        r = subprocess.run(["powercfg", "/query", "SCHEME_CURRENT", "SUB_SLEEP", "STANDBYIDLE"], capture_output=True, text=True,
                           timeout=8, creationflags=0x08000000, encoding="utf-8", errors="replace")
        v = parse_standby(r.stdout, _on_ac())
    except Exception:  # noqa: BLE001
        v = 0
    _cache.update(t=time.monotonic(), v=v)
    return v


def release_due(idle_s, standby_s, voice_ago_s, busy):
    """Пора ли отпустить микрофон: сон настроен, до него меньше минуты (или уже пора), голоса не было столько же и ассистент
    не занят (разговор, будильник, радио, суфлёр)."""
    if not standby_s or idle_s is None or busy:
        return False
    edge = max(30.0, standby_s - 60.0)
    return idle_s >= edge and voice_ago_s >= edge
