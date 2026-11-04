"""Компьютер голосом без модели: «громче», «тише», «громкость 40», «выключи звук», «выключи компьютер»,
«перезагрузи», «спящий режим», «заблокируй экран», «отмени выключение».

parse(text) — разбор фразы (только короткие команды целиком, до 9 слов: «выключи компьютер» внутри длинной фразы —
не команда); Power — выполнение (выключение и перезагрузка — через минуту, отменить можно голосом). Громкость
выполняет вызывающий код. DEWIAR_DRY_TOOLS=<файл> — для проверок: команды питания не выполняются, а пишутся в файл."""

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading

log = logging.getLogger("dewiar.pc")
WIN = os.name == "nt"
MAC = sys.platform == "darwin"
DRY = os.environ.get("DEWIAR_DRY_TOOLS")

PC = r"(?:компьютер|комп|ноутбук|ноут|пк|систему)"
NUM = {"десять": 10, "двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50, "шестьдесят": 60, "семьдесят": 70,
       "восемьдесят": 80, "девяносто": 90, "сто": 100, "половину": 50, "половина": 50, "пять": 5, "пятнадцать": 15,
       "двадцать пять": 25, "тридцать пять": 35, "сорок пять": 45, "семьдесят пять": 75}
POWER_WORDS = {"shutdown": "выключу компьютер", "reboot": "перезагружу компьютер", "sleep": "переведу компьютер в сон",
               "lock": "заблокирую экран", "logout": "выйду из системы"}


def _num(s):
    """«40» или «сорок» -> 40; другое -> None. Словами — только круглые и ходовые значения из NUM."""
    s = s.strip()
    if s.isdigit():
        return int(s)
    return NUM.get(s)


def parse(text):
    """-> {"op": "volume", "change"|"percent"|"mute"} | {"op": "power", "action"} | {"op": "power_cancel"} | None."""
    t = re.sub(r"[^\w\s%-]", " ", (text or "").lower().replace("ё", "е"))
    t = " ".join(t.split())
    if not t or len(t.split()) > 9:
        return None
    # --- громкость ---
    if re.fullmatch(r"(?:сделай\s+|можно\s+|еще\s+|чуть\s+|чуть-чуть\s+|немного\s+|побольше\s+)*(?:по)?громче(?:\s+(?:пожалуйста|еще|звук))*", t) or \
            re.fullmatch(r"(?:прибавь|добавь|увеличь|подними|повысь)\s+(?:звук|громкость)(?:\s+пожалуйста)?", t):
        return {"op": "volume", "change": 10}
    if re.fullmatch(r"(?:сделай\s+|можно\s+|еще\s+|чуть\s+|чуть-чуть\s+|немного\s+)*(?:по)?тише(?:\s+(?:пожалуйста|еще|звук))*", t) or \
            re.fullmatch(r"(?:убавь|уменьши|понизь|приглуши|опусти)\s+(?:звук|громкость)(?:\s+пожалуйста)?", t):
        return {"op": "volume", "change": -10}
    m = re.fullmatch(r"(?:поставь\s+|сделай\s+|установи\s+)?(?:громкость|звук)\s+(?:на\s+)?([\w ]+?)(?:\s*%|\s+процент\w*)?", t)
    if m and _num(m.group(1)) is not None:
        return {"op": "volume", "percent": max(0, min(100, _num(m.group(1))))}
    if re.fullmatch(r"(?:громкость|звук)\s+(?:на\s+)?(?:максимум|полную|максимальн\w*)|(?:на\s+)?полную\s+громкость", t):
        return {"op": "volume", "percent": 100}
    if re.fullmatch(r"(?:выключи|отключи|убери)\s+звук(?:\s+(?:на\s+)?(?:компьютере|ноутбуке))?|без\s+звука|"
                    r"(?:сделай\s+)?беззвучн\w+(?:\s+режим)?", t):
        return {"op": "volume", "mute": True}
    if re.fullmatch(r"(?:включи|верни)\s+звук(?:\s+обратно)?", t):
        return {"op": "volume", "mute": False}
    # --- питание ---
    if re.fullmatch(rf"(?:отмени|отмена|останови)\s+(?:выключени\w+|перезагрузк\w+)|не\s+(?:выключай|перезагружай)(?:\s+{PC})?", t):
        return {"op": "power_cancel"}
    if re.fullmatch(rf"(?:выключи|выруби|отключи|заверши\s+работу)\s+{PC}|(?:выключение|завершение\s+работы)\s+{PC}\w*", t):
        return {"op": "power", "action": "shutdown"}
    if re.fullmatch(rf"(?:перезагрузи|перезапусти|ребутни)\s+{PC}|перезагрузка\s+{PC}\w*", t):
        return {"op": "power", "action": "reboot"}
    if re.fullmatch(rf"(?:переведи|отправь|поставь)\s+{PC}\s+в\s+(?:спящий\s+режим|сон)|(?:усыпи|усни)\s+{PC}|"
                    rf"{PC}\s+в\s+(?:спящий\s+режим|сон)|спящий\s+режим(?:\s+{PC}\w*)?", t):
        return {"op": "power", "action": "sleep"}
    if re.fullmatch(rf"(?:заблокируй|заблокировать|блокируй|запри)\s+(?:{PC}|экран)|блокировка\s+экрана", t):
        return {"op": "power", "action": "lock"}
    return None


def _cmd(action):
    """Команда системы для действия. Отсрочку делает Power, поэтому здесь — «немедленно»."""
    if WIN:
        # SetSuspendState: если в Windows включена гибернация, компьютер уйдёт в гибернацию, а не в сон
        return {"shutdown": ["shutdown", "/s", "/t", "0"], "reboot": ["shutdown", "/r", "/t", "0"],
                "sleep": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                "lock": ["rundll32.exe", "user32.dll,LockWorkStation"], "logout": ["shutdown", "/l"]}[action]
    if MAC:                                      # Mac: питание — pmset и «События системы» (macOS спросит разрешение один раз)
        se = 'tell application "System Events" to '
        return {"shutdown": ["osascript", "-e", se + "shut down"], "reboot": ["osascript", "-e", se + "restart"],
                "sleep": ["pmset", "sleepnow"], "lock": ["pmset", "displaysleepnow"],
                "logout": ["osascript", "-e", se + "log out"]}[action]
    if action == "lock":                         # первая найденная из программ блокировки разных рабочих столов
        for c in (["loginctl", "lock-session"], ["xdg-screensaver", "lock"], ["gnome-screensaver-command", "-l"]):
            if shutil.which(c[0]):
                return c
        return ["loginctl", "lock-session"]
    if action == "logout":
        return ["gnome-session-quit", "--logout", "--no-prompt"] if shutil.which("gnome-session-quit") else \
            ["loginctl", "terminate-user", os.environ.get("USER", "")]
    return ["systemctl", {"shutdown": "poweroff", "reboot": "reboot", "sleep": "suspend"}[action]]


class Power:
    """Выключение, перезагрузка и выход — с отсрочкой (по умолчанию 60 с), чтобы успеть сказать «отмени»; сон
    и блокировка — через 3 с, чтобы успеть договорить ответ. Ждёт одно действие: новое отменяет прежнее.
    env() — окружение сеанса пользователя (для loginctl и программ блокировки)."""

    def __init__(self, env=None):
        self.env = env or (lambda: dict(os.environ))
        self.timer = None
        self.pending = None
        self._lock = threading.Lock()

    def run_now(self, action):
        """Выполнить сразу; OSError — команда не сработала (текст ошибки системы)."""
        cmd = _cmd(action)
        log.info("⏻ %s: %s", action, " ".join(cmd))
        if DRY:
            with open(DRY, "a", encoding="utf-8") as f:
                f.write(json.dumps(["power", action], ensure_ascii=False) + "\n")
            return
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20, env=self.env(),
                           creationflags=0x08000000 if WIN else 0)
        if r.returncode != 0:
            raise OSError((r.stderr or r.stdout or f"код {r.returncode}").strip()[-200:])

    def schedule(self, action, delay=None, on_error=None):
        """Запланировать действие -> текст подтверждения для ответа. delay — секунды (выключение, перезагрузка
        и выход — 60 по умолчанию, остальное — 3). on_error(текст) зовётся из потока таймера, если команда не сработала."""
        if action not in POWER_WORDS:
            raise ValueError("неизвестное действие")
        if delay is None:
            delay = 60 if action in ("shutdown", "reboot", "logout") else 3
        self.cancel()

        def go():
            with self._lock:
                # Сверяем сам таймер, а не действие: прежний таймер того же действия мог сработать в момент
                # перепланирования — иначе он выполнил бы команду сразу, не дожидаясь новой отсрочки
                if self.timer is not tm:
                    return
                self.pending, self.timer = None, None
            try:
                self.run_now(action)
            except Exception as e:  # noqa: BLE001
                log.warning("⏻ не получилось: %s", e)
                if on_error:
                    on_error(f"Не получилось: {e}")
        tm = threading.Timer(max(0, delay), go)
        tm.daemon = True
        with self._lock:
            self.pending, self.timer = action, tm
            tm.start()
        if delay >= 30:
            return f"Хорошо, {POWER_WORDS[action]} через минуту. Передумаете — скажите «отмени выключение»."
        return f"Хорошо, {POWER_WORDS[action]}."

    def cancel(self):
        """Отменить ожидающее действие -> какое было (или None)."""
        with self._lock:
            t, a = self.timer, self.pending
            self.timer = self.pending = None
        if t:
            t.cancel()
        return a
