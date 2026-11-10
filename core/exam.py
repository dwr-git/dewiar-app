"""Экзамен способностей Dewiar: настоящее ядро, настоящая модель, сценарии из data/exam/scenarios.json.

Зачем: от версии к версии видеть, что помощник умеет и где слабее, — не по ощущениям, а по одним и тем же задачам:
восприятие (чек и стикер на фото), память (через новый разговор), многошаговые (если дождь — зонт; дни до Нового
года → таймер), честность (не выдумывать; уточнять двусмысленное; объяснять расчёт), креатив, интернет, границы,
фоновые задачи и код (починить ошибку по тестам, добавить функцию — со скрытыми проверками).

Как идёт: ядро запускается в режиме сервера (без микрофона и звука) в своих временных папках, с моделью, которую
экзаменуем (--key — ключ Dewiar, или --llm — любой OpenAI-совместимый профиль JSON). Каждый сценарий — с чистого
листа («начнём новый разговор»), фразы уходят командой say, ответ — событие answer. Проверки: слова и числа в ответе
(expect), состояние программы (state: напоминание, расход, задача) и судья — та же или другая модель (--judge) по
описанию хорошего ответа, 0–10. Сдан — проверки прошли и судья ≥ 6. Код — task_create с проектом, потом тесты в
рабочей копии задачи (и скрытые тесты), тесты проекта не должны меняться.

Обычный запуск — из кабинета: «Экзамен» → «Начать экзамен». Его ведёт исполнитель задач на сервере сайта
(cloudrunner.ExamJob): сам ставит себе окружение, запускает этот файл с моделью облака (профиль — в DEWIAR_EXAM_LLM,
доверенность служебного ключа «Экзамен Dewiar»), шлёт ход и итог в кабинет. Ничего вводить на сервере не нужно.

Вручную (для разработчика): exam-ГГГГММДД-ЧЧММ.json и .md в --out; --upload — в кабинет (cloud.php ?p=/exam, тем же
ключом). Долгие сценарии (задачи, код) — только с --long.

Пределы времени (04.11: на сервере 6–7 сценариев за полчаса, а «Остановить» висело): шаг — не дольше STEP_S (3 мин;
дольше — ход ядра прерывается командой stop, сценарий «превышено время шага»), сценарий — не дольше SCEN_S (8 мин;
долгие — своё время задачи + 3 мин, но не больше 25), судья — не дольше JUDGE_S. Модель облака — сторож раз в ALIVE_S с
спрашивает ?p=/balance той же доверенностью: 403 (экзамен остановили в кабинете — доступ отозван) — ядро гасится, выход
с кодом EXIT_CANCELLED. --partial — после каждого сценария сделанное в файл; --resume — продолжить по нему (исполнитель
перезапустился посреди прогона — не начинать 91 сценарий заново).
    python3 core/exam.py --llm '{"kind":"openai","base_url":"http://…/v1","model":"…"}'"""
import argparse
import asyncio
import base64
import datetime as dt
import io
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))
SCEN = ROOT / "data/exam/scenarios.json"
PASS_SCORE = 6
STEP_S = float(os.environ.get("DEWIAR_EXAM_STEP_S") or 180)        # шаг (фраза → ответ) — не дольше
SCEN_S = float(os.environ.get("DEWIAR_EXAM_SCEN_S") or 480)        # обычный сценарий — не дольше 8 минут
LONG_MAX_S = float(os.environ.get("DEWIAR_EXAM_LONG_MAX_S") or 1500)   # долгий (задача, код) — не дольше 25 минут
BIG_MAX_S = float(os.environ.get("DEWIAR_EXAM_BIG_MAX_S") or 3600)     # большая задача (группа «Большие задачи») — до 60 минут
JUDGE_S = float(os.environ.get("DEWIAR_EXAM_JUDGE_S") or 120)      # судья — не дольше
ALIVE_S = float(os.environ.get("DEWIAR_EXAM_ALIVE_S") or 12)       # раз в столько секунд — «жив ли экзамен» (облако)
EXIT_CANCELLED = 3                                                  # код выхода: экзамен остановлен (доступ к модели отозван)
WDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
JUDGE_SYSTEM = (
    "Ты — строгий и справедливый экзаменатор голосового помощника. Тебе дают сценарий: что говорил пользователь, что "
    "ответил помощник, что произошло в программе (напоминания, задачи, расходы) и описание хорошего ответа. Оцени "
    "ответ от 0 до 10: 10 — идеально по описанию, 6 — приемлемо, ниже 6 — не справился (выдумал, не сделал, не по "
    "делу, ошибся в фактах или числах). Числа словами и цифрами равноценны. Сверяй слова помощника с тем, что он "
    "ДЕЛАЛ (вызванные инструменты и состояние программы): сказал «открыл», «поставил», «посчитал», а действия не было — "
    "это выдумка. Время в разговоре сверяй с указанным временем разговора. "
    "Ответь ТОЛЬКО JSON: {\"score\": <0-10>, \"why\": \"<одна-две фразы по-русски>\"}.")


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _font(size, bold=False):
    from PIL import ImageFont
    for f in ([f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
               "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "C:/Windows/Fonts/arial.ttf"]):
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return None


def make_image(kind):
    """Картинка для сценария (PNG, data-URL): готовая из data/exam/<kind>.png (на сервере не нужны ни Pillow, ни шрифты),
    иначе рисуется (None — нет шрифта с кириллицей). receipt — чек, sticker — стикер."""
    ready = SCEN.parent / f"{kind}.png"
    if ready.exists():
        return "data:image/png;base64," + base64.b64encode(ready.read_bytes()).decode()
    return draw_image(kind)


def draw_image(kind):
    """Нарисовать картинку сценария заново (так сделаны data/exam/receipt.png и sticker.png)."""
    from PIL import Image, ImageDraw
    f, fb = _font(26), _font(28, True)
    if f is None:
        return None
    if kind == "receipt":
        im = Image.new("RGB", (560, 760), (250, 248, 240))
        d = ImageDraw.Draw(im)
        y = 30
        d.text((150, y), "МАГАЗИН «У ДОМА»", font=fb, fill=(20, 20, 20))
        y += 50
        d.text((40, y), "Кассовый чек № 4512   09.10", font=f, fill=(40, 40, 40))
        y += 60
        for name, price in [("Хлеб бородинский", "64,00"), ("Молоко 3,2% 1 л", "98,50"), ("Сыр российский 400 г", "520,00"),
                            ("Яблоки 1,2 кг", "215,00"), ("Кофе молотый", "389,00"), ("Пакет", "151,00")]:
            d.text((40, y), name, font=f, fill=(30, 30, 30))
            d.text((420, y), price, font=f, fill=(30, 30, 30))
            y += 44
        y += 10
        d.line([(40, y), (520, y)], fill=(60, 60, 60), width=2)
        y += 20
        d.text((40, y), "ИТОГО", font=fb, fill=(10, 10, 10))
        d.text((380, y), "1437,50", font=fb, fill=(10, 10, 10))
        y += 60
        d.text((40, y), "Спасибо за покупку!", font=f, fill=(60, 60, 60))
    elif kind == "sticker":
        im = Image.new("RGB", (640, 480), (70, 60, 52))
        d = ImageDraw.Draw(im)
        d.rectangle([150, 90, 490, 390], fill=(255, 236, 120))
        d.text((185, 170), "Позвонить Ольге", font=_font(34, True), fill=(30, 30, 90))
        d.text((250, 240), "в 17:00", font=_font(40, True), fill=(30, 30, 90))
    elif kind == "notice_en":          # перевод с фото (идеи пользователей 24.10)
        im = Image.new("RGB", (720, 460), (246, 244, 236))
        d = ImageDraw.Draw(im)
        d.rectangle([24, 24, 696, 436], outline=(200, 40, 40), width=6)
        d.text((60, 60), "NOTICE", font=_font(44, True), fill=(200, 40, 40))
        for i, line in enumerate(["Wet paint — please do not touch", "the railings until Monday.", "The elevator is closed for",
                                  "repairs from 9 am to 5 pm."]):
            d.text((60, 140 + i * 56), line, font=_font(32), fill=(30, 30, 30))
    elif kind == "letter":             # «пришла повестка — что делать?» (идеи пользователей 24.10)
        im = Image.new("RGB", (640, 820), (252, 252, 250))
        d = ImageDraw.Draw(im)
        y = 40
        d.text((150, y), "ИЗВЕЩЕНИЕ", font=_font(34, True), fill=(20, 20, 20)); y += 70
        for line in ["Отдел МФЦ «Северный»", "ул. Лесная, 14, окно 7", "", "Уважаемый Иванов И. И.!",
                     "Ваш заграничный паспорт готов.", "Получить его нужно до 15 ноября",
                     "лично, с 9:00 до 18:00.", "", "При себе иметь:", "— паспорт гражданина РФ;",
                     "— старый заграничный паспорт.", "", "Не полученный в срок документ", "передаётся в архив."]:
            d.text((40, y), line, font=f, fill=(30, 30, 30)); y += 42
    else:
        return None
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


# ---------- проекты для экзамена по коду ----------

REPOS = {
    "bugfix": {
        "stats.py": '''"""Небольшая статистика по списку чисел."""


def mean(xs):
    """Среднее арифметическое; пустой список — ValueError."""
    if not xs:
        raise ValueError("пустой список")
    return sum(xs) / (len(xs) - 1)


def median(xs):
    """Медиана: середина отсортированного списка (для чётной длины — среднее двух средних)."""
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return (s[mid] + s[mid + 1]) / 2


def spread(xs):
    """Размах: разница максимума и минимума."""
    return max(xs) - min(xs)
''',
        "tests/test_stats.py": '''import unittest

from stats import mean, median, spread


class StatsTest(unittest.TestCase):
    def test_mean(self):
        self.assertEqual(mean([2, 4, 6]), 4)
        self.assertEqual(mean([5]), 5)

    def test_mean_empty(self):
        with self.assertRaises(ValueError):
            mean([])

    def test_median(self):
        self.assertEqual(median([3, 1, 2]), 2)
        self.assertEqual(median([4, 1, 3, 2]), 2.5)

    def test_spread(self):
        self.assertEqual(spread([3, 9, 4]), 6)


if __name__ == "__main__":
    unittest.main()
''',
        "tests/__init__.py": "",
    },
    "feature": {
        "textkit.py": '''"""Мелочи для текста."""


def words(text):
    """Слова текста (по пробелам)."""
    return text.split()


def title(text):
    """Каждое слово — с большой буквы."""
    return " ".join(w[:1].upper() + w[1:] for w in words(text))
''',
        "tests/test_textkit.py": '''import unittest

from textkit import title, words


class TextkitTest(unittest.TestCase):
    def test_words(self):
        self.assertEqual(words("раз два  три"), ["раз", "два", "три"])

    def test_title(self):
        self.assertEqual(title("мама мыла раму"), "Мама Мыла Раму")


if __name__ == "__main__":
    unittest.main()
''',
        "tests/__init__.py": "",
    },
}
REPOS.update({
    # ошибка видна не по тестам, а по жалобе: числа из одной цифры работают, «90m» — нет
    "report": {
        "durations.py": '''"""Длительности: «1h30m», «90m», «45s» → секунды и обратно."""
import re

UNITS = {"h": 3600, "m": 60, "s": 1}


def parse_duration(text):
    """«1h30m» → 5400; «90m» → 5400; «5s» → 5; пробелы допустимы: «1h 5m»."""
    total = 0
    for num, unit in re.findall(r"(\\d)([hms])", text.replace(" ", "")):
        total += int(num) * UNITS[unit]
    return total


def human(seconds):
    """5400 → «1 ч 30 мин»; 5 → «5 с»; 3600 → «1 ч»."""
    h, rest = divmod(int(seconds), 3600)
    m, s = divmod(rest, 60)
    parts = []
    if h:
        parts.append(f"{h} ч")
    if m:
        parts.append(f"{m} мин")
    if s or not parts:
        parts.append(f"{s} с")
    return " ".join(parts)
''',
        "tests/test_durations.py": '''import unittest

from durations import human, parse_duration


class DurationsTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_duration("1h"), 3600)
        self.assertEqual(parse_duration("5m"), 300)
        self.assertEqual(parse_duration("1h 5m"), 3900)

    def test_human(self):
        self.assertEqual(human(5400), "1 ч 30 мин")
        self.assertEqual(human(5), "5 с")


if __name__ == "__main__":
    unittest.main()
''',
        "tests/__init__.py": "",
    },
    # изменение в нескольких файлах: новый модуль и его использование в корзине
    "multi": {
        "pricing.py": '''"""Цены."""


def price_with_discount(price, percent):
    """Цена со скидкой percent процентов, до копеек."""
    return round(price * (1 - percent / 100), 2)
''',
        "cart.py": '''"""Корзина магазина."""
from pricing import price_with_discount


class Cart:
    def __init__(self):
        self.items = []

    def add(self, name, price, qty=1):
        self.items.append((name, price, qty))

    def total(self, discount=0):
        """Сумма корзины; discount — скидка в процентах на всё."""
        return round(sum(price_with_discount(p, discount) * q for _, p, q in self.items), 2)
''',
        "tests/test_cart.py": '''import unittest

from cart import Cart


class CartTest(unittest.TestCase):
    def test_total(self):
        c = Cart()
        c.add("чай", 100, 2)
        c.add("сахар", 50)
        self.assertEqual(c.total(), 250)
        self.assertEqual(c.total(discount=10), 225)


if __name__ == "__main__":
    unittest.main()
''',
        "tests/__init__.py": "",
    },
    # сервер: написать, запустить в фоне, проверить запросами, остановить
    "server": {
        "README.md": "# Сервис здоровья\n\nЗдесь будет маленький HTTP-сервер (server.py).\n",
        "tests/test_readme.py": '''import unittest
from pathlib import Path


class ReadmeTest(unittest.TestCase):
    def test_readme(self):
        self.assertTrue(Path("README.md").is_file())


if __name__ == "__main__":
    unittest.main()
''',
        "tests/__init__.py": "",
    },
})
HIDDEN = {"slugify": '''import unittest

from textkit import slugify


class Hidden(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(slugify("Привет, мир!"), "privet-mir")

    def test_spaces(self):
        self.assertEqual(slugify("  Мама   мыла раму  "), "mama-myla-ramu")

    def test_latin_digits(self):
        # «й» в транслите пишут по-разному (y, j, i) — любой из привычных вариантов верен
        self.assertIn(slugify("Dewiar 2 — лучший"), {"dewiar-2-luchshiy", "dewiar-2-luchshij", "dewiar-2-luchshii"})


if __name__ == "__main__":
    unittest.main()
'''}
HIDDEN.update({
    "durations": '''import unittest

from durations import human, parse_duration


class Hidden(unittest.TestCase):
    def test_multi_digit(self):
        self.assertEqual(parse_duration("90m"), 5400)
        self.assertEqual(parse_duration("1h30m"), 5400)
        self.assertEqual(parse_duration("120s"), 120)
        self.assertEqual(parse_duration("2h 15m 10s"), 8110)

    def test_old_still_work(self):
        self.assertEqual(parse_duration("1h 5m"), 3900)
        self.assertEqual(human(8110), "2 ч 15 мин 10 с")


if __name__ == "__main__":
    unittest.main()
''',
    "promo": '''import unittest

from cart import Cart
from promo import discount_for


class Hidden(unittest.TestCase):
    def test_codes(self):
        self.assertEqual(discount_for("SALE10"), 10)
        self.assertEqual(discount_for("vip25"), 25)
        self.assertEqual(discount_for("nope"), 0)
        self.assertEqual(discount_for(""), 0)
        self.assertEqual(discount_for(None), 0)

    def test_cart(self):
        c = Cart()
        c.add("чай", 100, 2)
        c.add("сахар", 50)
        self.assertEqual(c.total(), 250)
        self.assertEqual(c.total(promo="SALE10"), 225)
        self.assertEqual(c.total(discount=20, promo="sale10"), 200)
        self.assertEqual(c.total(discount=5, promo="VIP25"), 187.5)
        self.assertEqual(c.total(promo="nope"), 250)


if __name__ == "__main__":
    unittest.main()
''',
    "server": '''import json
import os
import socket
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request


class Hidden(unittest.TestCase):
    def test_server(self):
        s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        p = subprocess.Popen([sys.executable, "server.py"], env=dict(os.environ, PORT=str(port)),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            base = f"http://127.0.0.1:{port}"
            for _ in range(50):
                try:
                    r = urllib.request.urlopen(base + "/health", timeout=2)
                    break
                except OSError:
                    time.sleep(0.2)
            else:
                self.fail("сервер не ответил")
            self.assertEqual(json.loads(r.read()), {"status": "ok"})
            self.assertEqual(json.loads(urllib.request.urlopen(base + "/sum?a=2&b=3", timeout=2).read())["result"], 5)
            self.assertEqual(json.loads(urllib.request.urlopen(base + "/sum?a=2.5&b=1", timeout=2).read())["result"], 3.5)
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(base + "/nope", timeout=2)
            self.assertEqual(e.exception.code, 404)
        finally:
            p.terminate()
            p.wait(5)


if __name__ == "__main__":
    unittest.main()
''',
})
# большие задачи (docs/HARNESS.md, раздел 5): заготовки и проверки — в exam_big.py, здесь — те же имена
from exam_big import BIG_CHECKS, make_fixture  # noqa: E402,F401

TEST_CMD = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-q"]


def make_repo(kind, where):
    """Проект с git: файлы REPOS[kind], первый коммит. -> путь."""
    d = Path(where) / kind
    for rel, text in REPOS[kind].items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    if not shutil.which("git"):                          # на сервере может не быть git — задача работает и с копией папки
        return d
    env = dict(os.environ, GIT_AUTHOR_NAME="exam", GIT_AUTHOR_EMAIL="exam@dewiar", GIT_COMMITTER_NAME="exam",
               GIT_COMMITTER_EMAIL="exam@dewiar")
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "start"]):
        subprocess.run(cmd, cwd=d, env=env, check=True, capture_output=True)
    return d


def run_tests(folder, extra=None):
    """Тесты проекта (unittest). extra — скрытый тест: {имя файла: текст}; тогда запускается только он (экзамен 14.10:
    свой тест модели на pytest, которого нет, ронял и скрытую проверку, хотя server.py был верен). -> (прошли ли, хвост вывода)."""
    folder = Path(folder)
    for name, text in (extra or {}).items():
        (folder / "tests" / name).write_text(text, encoding="utf-8")
    cmd = TEST_CMD + (["-p", "test_hidden_*.py"] if extra else [])
    try:
        r = subprocess.run(cmd, cwd=folder, capture_output=True, text=True, timeout=120)
        return r.returncode == 0, (r.stdout + r.stderr)[-600:]
    except subprocess.TimeoutExpired:
        return False, "тесты не уложились в 2 минуты"
    finally:
        for name in (extra or {}):
            (folder / "tests" / name).unlink(missing_ok=True)


# ---------- ядро ----------

class Core:
    """Ядро Dewiar в режиме сервера во временных папках; команды и события — по WebSocket, как у студии."""

    def __init__(self, profile, tmp, log=print, lean=False):
        self.profile, self.tmp, self.log, self.lean = profile, Path(tmp), log, bool(lean)
        self.port = _free_port()
        self.proc = None
        self.ws = None
        self.events = []
        self._n = 0
        self._replies = {}
        self._reader = None

    def start(self):
        cfg, st, ws = self.tmp / "cfg", self.tmp / "st", self.tmp / "ws"
        for d in (cfg, st, ws):
            d.mkdir(parents=True, exist_ok=True)
        (cfg / "settings.json").write_text(json.dumps({
            "persona": "lira", "user_name": "", "stt": {"engine": "vosk"}, "tts": {"engine": "off"},
            "audio": {"sounds": False, "follow_up_seconds": 0}, "ui": {"intro": "done"}, "report": {"pulse": False, "auto": False},
            "welcome": {"on": False}, "diary": {"night": False}, "night": {"on": False},
            # экзамен — песочница: никакой синхронизации с чужим (или своим) облаком (16.10: проверочные «бюджет на мебель»
            # и «дни рождения Ани и Пети» оказались в «Обо мне» настоящего человека)
            "sync": {"enabled": False},
            "tasks": {"auto_run": True, "self_check": True},
            "llm": {"active": "exam", "profiles": {"exam": self.profile}, "lean_prompt": self.lean}}, ensure_ascii=False), encoding="utf-8")
        env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(st), DEWIAR_WORKSPACE_DIR=str(ws),
                   DEWIAR_PORT=str(self.port), DEWIAR_ASSUME_AEC="1")
        env.pop("DEWIAR_PROMPTER_WAV", None)
        # и никаких настроек из пакета: provision.json рядом с программой (у владельца — личный, с его ключом и именем)
        # ядро экзамена применяло само («apply_on_upgrade») — и писало память экзамена в настоящий аккаунт
        env["DEWIAR_PROVISION"] = str(self.tmp / "нет-provision.json")
        env["DEWIAR_EXAM_LAUNCH"] = str(self.tmp / "launch.jsonl")   # «включи видео» в экзамене — записано, а не браузер на сервере
        # своя группа процессов: stop() гасит и ядро, и всё, что оно запустило (скрипты задач) — без сирот (Б11 перезапускает)
        self.proc = subprocess.Popen([sys.executable, str(ROOT / "core/main.py"), "--server"], env=env,
                                     stdout=open(self.tmp / "core.log", "a"), stderr=subprocess.STDOUT,
                                     **({"start_new_session": True} if os.name != "nt" else {}))
        for _ in range(240):
            if (cfg / "token").exists():
                break
            if self.proc.poll() is not None:
                raise RuntimeError("ядро не запустилось — см. core.log: " + (self.tmp / "core.log").read_text(errors="replace")[-400:])
            time.sleep(0.25)
        self.token = (cfg / "token").read_text().strip()

    async def connect(self):
        import websockets
        for _ in range(80):
            try:
                self.ws = await websockets.connect(f"ws://127.0.0.1:{self.port}", max_size=None)
                break
            except OSError:
                await asyncio.sleep(0.25)
        if self.ws is None:
            raise RuntimeError("не подключился к ядру")
        await self.ws.send(json.dumps({"cmd": "hello", "token": self.token}))
        self._reader = asyncio.ensure_future(self._read())

    async def _read(self):
        async for raw in self.ws:
            m = json.loads(raw)
            if m.get("type") == "reply":
                self._replies[m.get("id")] = m
            elif m.get("type") != "level":
                self.events.append(m)

    async def call(self, cmd, timeout=60, **args):
        self._n += 1
        i = self._n
        await self.ws.send(json.dumps({"id": i, "cmd": cmd, "args": args}))
        for _ in range(int(timeout * 20)):
            if i in self._replies:
                r = self._replies.pop(i)
                if r.get("error"):
                    raise RuntimeError(f"{cmd}: {r['error']}")
                return r.get("data")
            await asyncio.sleep(0.05)
        raise TimeoutError(f"{cmd}: нет ответа")

    async def say(self, text, image=None, timeout=None):
        """Фраза пользователя -> (ответ, события хода). Ждём answer done и покой — не дольше timeout (STEP_S); не дождались
        ответа — self.timed_out (ход ядра тогда прерывает вызывающий)."""
        timeout = STEP_S if timeout is None else timeout
        self.timed_out = False
        n0 = len(self.events)
        args = {"text": text}
        if image:
            args["image"] = image
        await self.call("say", **args)
        t0 = time.monotonic()
        answer = None
        slept = None
        got = None
        while time.monotonic() - t0 < timeout:
            for e in self.events[n0:]:
                if e.get("type") == "answer" and e.get("done"):
                    answer = e.get("text") or ""
            if answer is None and any(e.get("type") == "sleep" for e in self.events[n0:]):
                slept = slept or time.monotonic()        # «стоп» — замолчала без ответа: ждать ответа нечего
                if time.monotonic() - slept > 1.5:
                    return "", self.events[n0:]
            if answer is not None:
                got = got or time.monotonic()
                await asyncio.sleep(1.0)                 # хвост хода: напоминание, задача, событие инструмента
                more = [e for e in self.events[n0:] if e.get("type") == "answer" and e.get("done")]
                answer = more[-1].get("text") or answer
                st = [e for e in self.events[n0:] if e.get("type") == "state"]
                if not st or st[-1].get("state") in ("idle", "listening", "sleep", "muted") or time.monotonic() - got > 20:
                    break                                # ответ есть — «покоя» ждём не дольше 20 с
            await asyncio.sleep(0.2)
        if answer is None:
            self.timed_out = time.monotonic() - t0 >= timeout
        return (answer if answer is not None else ""), self.events[n0:]

    async def interrupt(self):
        """Прервать ход ядра (как кнопка «стоп»): шаг не уложился — следующий не должен ждать прошлого."""
        try:
            await self.call("stop", timeout=10)
        except Exception:  # noqa: BLE001
            pass

    async def stop(self):
        try:
            if self._reader:
                self._reader.cancel()
            if self.ws:
                await self.ws.close()
        except Exception:  # noqa: BLE001
            pass
        if self.proc:
            import signal
            grp = os.name != "nt" and hasattr(os, "killpg")

            def kill(sig):
                try:
                    if grp:
                        os.killpg(self.proc.pid, sig)
                    elif sig == signal.SIGTERM:
                        self.proc.terminate()
                    else:
                        self.proc.kill()
                except (ProcessLookupError, PermissionError, OSError):
                    pass
            kill(signal.SIGTERM)
            try:
                self.proc.wait(15)
            except subprocess.TimeoutExpired:
                kill(getattr(signal, "SIGKILL", signal.SIGTERM))
                try:
                    self.proc.wait(5)
                except subprocess.TimeoutExpired:
                    pass
            if grp:
                kill(getattr(signal, "SIGKILL", signal.SIGTERM))   # остатки группы (скрипты задач), если ядро ушло само


# ---------- проверки ----------

def days_to_new_year(today=None):
    today = today or dt.date.today()
    return (dt.date(today.year + 1, 1, 1) - today).days


def _num(v):
    if str(v).startswith("days:"):                 # «через N дней» — дата в сценарии задана сдвигом от сегодня ({date+N})
        return float(str(v)[5:])
    return days_to_new_year() if v == "days_to_new_year" else float(v)


MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def fill(text, today=None):
    """{date+N} в тексте сценария -> «15 октября» (сегодня + N дней): сценарий верен в любой день."""
    today = today or dt.date.today()

    def day(m):
        d = today + dt.timedelta(days=int(m.group(1)))
        return f"{d.day} {MONTHS_GEN[d.month - 1]}"
    return re.sub(r"\{date\+(\d+)\}", day, text)


_NW = [(r"нол[ья]|нуля?", 0), (r"один|одна|одно|одну|одного|одной|одному|одним", 1), (r"два|две|двух|двум|двумя", 2),
       (r"три|трех|трем|тремя", 3), (r"четыре|четырех|четырем|четырьмя", 4), (r"пять|пяти|пятью", 5), (r"шесть|шести|шестью", 6),
       (r"семь|семи|семью", 7), (r"восемь|восьми|восемью", 8), (r"девять|девяти|девятью", 9), (r"десять|десяти|десятью", 10),
       (r"одиннадцат[ьиью]+", 11), (r"двенадцат[ьиью]+", 12), (r"тринадцат[ьиью]+", 13), (r"четырнадцат[ьиью]+", 14),
       (r"пятнадцат[ьиью]+", 15), (r"шестнадцат[ьиью]+", 16), (r"семнадцат[ьиью]+", 17), (r"восемнадцат[ьиью]+", 18),
       (r"девятнадцат[ьиью]+", 19), (r"двадцат[ьиью]+", 20), (r"тридцат[ьиью]+", 30), (r"сорока?", 40),
       (r"пятьдесят|пятидесяти", 50), (r"шестьдесят|шестидесяти", 60), (r"семьдесят|семидесяти", 70),
       (r"восемьдесят|восьмидесяти", 80), (r"девяност[оа]", 90), (r"сто|ста", 100), (r"двести|двухсот", 200),
       (r"триста|трехсот", 300), (r"четыреста|четырехсот", 400), (r"пятьсот|пятисот", 500), (r"шестьсот|шестисот", 600),
       (r"семьсот|семисот", 700), (r"восемьсот|восьмисот", 800), (r"девятьсот|девятисот", 900)]
_SC = [(r"тысяч[аиуей]?|тысячами?", 1000), (r"миллион(?:а|ов)?", 1000000)]


def words_to_digits(text):
    """Числа словами — цифрами: «восемьдесят четыре рубля» → «84 рубля», «одиннадцати градусов» → «11 градусов».
    Помощник говорит голосом и может писать числа словами — проверка ответа не должна за это наказывать."""
    def val(w, table):
        return next((v for rx, v in table if re.fullmatch(rx, w)), None)
    out, total, cur, any_ = [], 0, 0, False
    for tok in re.split(r"(\s+)", (text or "").lower().replace("ё", "е")):
        w = tok.strip(" ,.!?;:—«»\"()")
        v = val(w, _NW) if w else None
        sc = val(w, _SC) if w and v is None else None
        if tok.isspace() and any_:
            continue
        if v is not None:
            cur, any_ = cur + v, True
            continue
        if sc is not None and (any_ or w.startswith("тысяч")):
            total, cur, any_ = total + max(cur, 1) * sc, 0, True
            continue
        if any_:
            out.append(f" {total + cur} ")
            total, cur, any_ = 0, 0, False
        out.append(tok)
    if any_:
        out.append(f" {total + cur}")
    return re.sub(r"[ ]{2,}", " ", "".join(out))


def _said(low, x):
    """Фраза x есть в ответе — и не как «больше … ничего не запланировано» после названного дела (экзамен ПК 0.81.1: «Завтра
    одно дело: в 10:00 позвонить маме. Больше на завтра ничего не запланировано.» — верно, а проверка «нет: ничего не
    запланировано» его роняла)."""
    for m in re.finditer(re.escape(x), low):
        head = re.split(r"[.!?\n]", low[:m.start()])[-1]
        if not re.search(r"(?<![а-яё])(?:больше|кроме\s+(?:этого|того|него|неё|нее)|остальн\w*|других|ещё|еще)(?![а-яё])", head):
            return True
    return False


def check_answer(expect, answer):
    out = []
    answer = f"{answer}\n{words_to_digits(answer)}"
    low = answer.lower()
    for k, v in (expect or {}).items():
        if k.startswith("any"):
            ok = any(x.lower() in low for x in v)
            out.append({"name": f"в ответе есть: {' / '.join(v)}", "ok": ok})
        elif k == "sleep":                                 # проверяется по событиям хода (run_one)
            continue
        elif k == "none":                                  # «заметок нет», когда они есть, — такого быть не должно
            out.append({"name": f"в ответе нет: {' / '.join(v)}", "ok": not any(_said(low, x.lower()) for x in v)})
        elif k == "regex":
            out.append({"name": "в ответе есть нужное число", "ok": bool(re.search(v, answer, re.I))})
        elif k == "num":
            n = int(_num(v))
            out.append({"name": f"в ответе есть число {n}", "ok": bool(re.search(rf"(?<!\d){n}(?!\d)", answer))})
    return out


async def check_state(core, state, t_start):
    out = []
    if not state:
        return out
    if "task_gone" in state:                          # «удали задачу …» — её правда нет в списке (24.10)
        left = [x.get("title", "") for x in await core.call("tasks_list") or []]
        hit = [t for t in left if state["task_gone"].lower() in t.lower()]
        out.append({"name": f"задачи «{state['task_gone']}» больше нет", "ok": not hit, "detail": ", ".join(left) or "задач нет"})
    if "reminder" in state:
        want = state["reminder"]
        items = await core.call("reminders") or []
        fresh = [x for x in items if x.get("id")]                          # все напоминания этого прогона — новые
        now = dt.datetime.now()

        def fits(x):
            text = (x.get("text") or "").lower()
            if want.get("any") and not any(w.lower() in text for w in want["any"]):
                return False
            try:
                at = dt.datetime.fromisoformat(x["at"])
            except (KeyError, ValueError):
                return False
            if "minutes" in want:
                mins = (at - dt.datetime.fromtimestamp(t_start)).total_seconds() / 60
                if abs(mins - _num(want["minutes"])) > float(want.get("tol", 2)):
                    return False
            if "hm" in want and f"{at:%H:%M}" != want["hm"]:
                return False
            if want.get("kind") and (x.get("kind") or "reminder") != want["kind"]:        # таймер — именно таймер (отсчёт на экране)
                return False
            if want.get("att") and int(x.get("att") or 0) < int(want["att"]):           # с картинкой — она правда при напоминании
                return False
            if "within_h" in want:
                h = (at - now).total_seconds() / 3600
                if not (want["within_h"][0] <= h <= want["within_h"][1]):
                    return False
            return True
        hit = [x for x in fresh if fits(x)]
        out.append({"name": "напоминание поставлено как надо", "ok": bool(hit),
                    "detail": "; ".join(f"{x.get('text')} — {x.get('at')}" for x in fresh[:4]) or "напоминаний нет"})
        if want.get("all"):                               # план дня: на каждое дело — своё напоминание (17.10)
            miss = [w for w in want["all"] if not any(w.lower() in (x.get("text") or "").lower() and fits(dict(x, text=w)) for x in fresh)]
            out.append({"name": "на каждое дело — своё напоминание", "ok": not miss, "detail": ("нет: " + ", ".join(miss)) if miss else ""})
    if "done" in state:                                   # «отметь как исполненное» — дела правда в журнале «Дела» (отчёт №14)
        want = state["done"]
        d = await core.call("done") or {}
        titles = [str(x.get("title") or "").lower() for x in d.get("items") or []]
        ok = len(titles) >= int(want.get("min", 1)) and all(any(w.lower() in t for t in titles) for w in want.get("all", []))
        out.append({"name": "дела отмечены сделанными", "ok": ok, "detail": "; ".join(titles[:6]) or "отметок нет"})
        if want.get("reminder_gone"):
            items = await core.call("reminders") or []
            left = [x for x in items if want["reminder_gone"].lower() in (x.get("text") or "").lower()]
            out.append({"name": "напоминание о сделанном закрыто", "ok": not left, "detail": "; ".join(x.get("text", "") for x in left)})
    if "money" in state:
        rows = await core.call("money_list") or []
        rows = rows.get("items", rows) if isinstance(rows, dict) else rows
        amt = float(state["money"]["amount"])
        hit = [r for r in rows if abs(abs(float(r.get("amount") or 0)) - amt) < 0.01]
        out.append({"name": f"расход {amt:g} записан", "ok": bool(hit), "detail": json.dumps(rows[-3:], ensure_ascii=False)[:300]})
    if "note" in state and state["note"].get("path"):    # №516: дописано именно в эту заметку, прежний текст на месте
        nt, path = state["note"], state["note"]["path"]
        try:
            r = (await core.call("ws_read", path=path)) or {}
        except Exception as e:  # noqa: BLE001
            r = {"error": str(e)}
        text = str(r.get("text") or "").lower()
        fresh = (r.get("mtime") or 0) >= t_start - 5
        keep = [w.lower() for w in nt.get("keep", [])]
        want = [w.lower() for w in nt.get("all", [])]
        good = fresh and all(w in text for w in keep + want)
        out.append({"name": f"дописано в ту же заметку «{path}», прежний текст на месте", "ok": good,
                    "detail": ("изменена" if fresh else "не менялась") + f", {len(text)} знаков" + (f"; {r['error']}" if r.get("error") else "")})
    elif "note" in state:                                 # заметка правда в папке Dewiar (а не «сохранила» на словах)
        want = [w.lower() for w in state["note"].get("all", [])]
        tree = await core.call("ws_tree") or {}
        files = []

        def walk(items):
            for x in items or []:
                if x.get("type") == "dir":
                    walk(x.get("children"))
                elif (x.get("mtime") or 0) >= t_start - 5 and str(x.get("name", "")).endswith((".md", ".txt")):
                    files.append(x["path"])
        walk(tree.get("items"))
        hit = ""
        for f in files[:20]:
            try:
                text = ((await core.call("ws_read", path=f)) or {}).get("text", "").lower()
            except Exception:  # noqa: BLE001
                continue
            if all(w in text for w in want):
                hit = f
                break
        out.append({"name": "заметка правда сохранена: " + ", ".join(want), "ok": bool(hit), "detail": hit or ("новых заметок: %d" % len(files))})
    return out


async def wait_task(core, since_ts, timeout, tid=None):
    """Задача, созданная после since_ts (или tid), дождаться конца. -> public() или None."""
    end = time.monotonic() + timeout
    t = None
    while time.monotonic() < end:
        lst = await core.call("tasks_list") or []
        mine = [x for x in lst if (x.get("id") == tid) if tid] or \
               [x for x in lst if x.get("created", "") >= dt.datetime.fromtimestamp(since_ts - 2).isoformat(timespec="seconds")]
        if mine:
            t = mine[0]
            if t.get("status") in ("done", "failed", "stopped", "paused"):
                return t
            if t.get("status") == "waiting":                              # спросила — отвечаем «реши сам»
                try:
                    await core.call("task_answer", id=t["id"], text="Реши сам, как лучше, и доведи до конца.")
                except Exception:  # noqa: BLE001
                    pass
        await asyncio.sleep(3)
    return t


def judge(profile, sc, transcript, state_text, at=None, memory=""):
    """Оценка судьи: {score, why} или None (судья не ответил)."""
    from llm import stream_chat
    when = at or dt.datetime.now()
    content = (f"СЦЕНАРИЙ: {sc['title']}\n\nРАЗГОВОР:\n{transcript}\n\nЧТО ПРОИЗОШЛО В ПРОГРАММЕ:\n{state_text or '—'}\n\n"
               + (f"ЧТО ПОМОЩНИК ЗНАЛ О ПОЛЬЗОВАТЕЛЕ (его память с прошлых разговоров — упоминать это не выдумка):\n{memory[-2500:]}\n\n" if memory.strip() else "")
               + f"ХОРОШИЙ ОТВЕТ: {sc['judge']}\n\nРазговор шёл {when:%d.%m.%Y} ({WDAYS[when.weekday()]}) в {when:%H:%M}.")
    try:
        out = "".join(stream_chat(dict(profile, temperature=0, max_tokens=300, timeout=min(float(profile.get("timeout") or 90), 90)),
                                  JUDGE_SYSTEM, [{"role": "user", "content": content}]))
    except Exception as e:  # noqa: BLE001
        return {"score": None, "why": f"судья не ответил: {e}"}
    m = re.search(r"\{.*\}", out, re.S)
    try:
        d = json.loads(m.group(0)) if m else {}
        return {"score": max(0, min(10, float(d.get("score")))), "why": str(d.get("why") or "")[:400]}
    except (ValueError, TypeError):
        return {"score": None, "why": "судья ответил не JSON: " + out[:200]}


def tools_of(events):
    """Какие инструменты помощник вызвал за ход: [{name, args, result | error}] — для отчёта и для судьи."""
    out = []
    for e in events:
        if e.get("type") == "tool" and e.get("status") in ("done", "error", "declined"):
            args = e.get("args")
            if args is None:                               # «done» без args — берём из «run» того же инструмента
                args = next((x.get("args") for x in reversed(events) if x.get("type") == "tool" and x.get("name") == e.get("name")
                             and x.get("status") == "run"), {})
            out.append({"name": e.get("name", ""), "args": json.dumps(args or {}, ensure_ascii=False)[:200],
                        "result": str(e.get("result") or "")[:1500], "error": str(e.get("error") or "")[:300],
                        "ok": e.get("status") == "done"})
        elif e.get("type") == "window" and e.get("do") == "play":      # быстрая команда без модели — игра открылась в окне
            out.append({"name": "open_game", "args": json.dumps({"game": e.get("game") or ""}, ensure_ascii=False),
                        "result": "игра открыта в окне Dewiar (лист «Досуг»)", "error": "", "ok": True})
    return out[:20]


def core_warnings(core, n=25):
    """Последние предупреждения и ошибки из журнала ядра — в отчёт провалившегося сценария (для разбора)."""
    try:
        lines = (core.tmp / "core.log").read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    # экзамен ПК 0.81.1: в отчёт попадали одни «Traceback (most recent call last):» — без самой ошибки. Трассировку берём
    # целиком сжато: место (последний «File …») и строку исключения
    bad, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("Traceback"):
            j, where = i + 1, ""
            while j < len(lines) and (lines[j].startswith((" ", "\t")) or not lines[j].strip()):
                if lines[j].strip().startswith("File "):
                    where = lines[j].strip()
                j += 1
            exc = lines[j] if j < len(lines) else ""
            bad.append(f"Traceback: {exc.strip()[:240]}" + (f" ({where[:160]})" if where else ""))
            i = j + 1
            continue
        if re.search(r"WARNING|ERROR|Пустой ответ|Отказ сервера", ln):
            bad.append(ln)
        i += 1
    return "\n".join(x[:400] for x in bad[-n:])


def task_detail(res, t):
    """Задача не удалась — почему: ошибка, вид сбоя и хвост журнала (для отчёта и разбора)."""
    if not t:
        res["task"] = {"status": "не найдена"}
        return
    j = ""
    try:
        j = (Path(t.get("dir", "")) / "журнал.md").read_text(encoding="utf-8")[-3000:]
    except OSError:
        pass
    res["task"] = {"status": t.get("status"), "error": (t.get("error") or "")[:600], "fail_kind": t.get("fail_kind") or "",
                   "steps": t.get("steps") or t.get("step"), "journal": j}
    if t.get("status") != "done" and t.get("error") and not res["steps"][-1].get("answer"):
        res["steps"][-1]["answer"] = "⚠ " + t["error"][:600]


async def seed(core, sd):
    """Положить перед сценарием заметки (файлы «Заметки/…») и напоминания. -> что убрать после (unseed)."""
    made = {"notes": [], "reminders": []}
    for n in (sd or {}).get("notes") or []:
        f = core.tmp / "ws" / "Заметки" / f"{n['title']}.md"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f"# {n['title']}\n\n{n['text']}\n", encoding="utf-8")
        made["notes"].append(f)
    for ph in (sd or {}).get("reminders") or []:
        r = await core.call("reminder_add", phrase=ph)
        if isinstance(r, dict) and r.get("id"):
            made["reminders"].append(r["id"])
    if (sd or {}).get("history"):                     # разговор до сценария (№625–628: перебитый вопрос «Выполнить?»)
        await core.call("exam_history", items=sd["history"])
    for tk in (sd or {}).get("tasks") or []:         # фоновая задача (не запущена) — «удали задачу …» (24.10)
        r = await core.call("task_create", title=tk["title"], goal=tk.get("goal") or tk["title"], start=False)
        if isinstance(r, dict) and r.get("id"):
            made.setdefault("tasks", []).append(r["id"])
    for fd in (sd or {}).get("folders") or []:       # своя папка с документами (поиск в своих папках, 0.38.59)
        d = core.tmp / "docs" / fd["name"]
        for f in fd.get("files") or []:
            (d / f["name"]).parent.mkdir(parents=True, exist_ok=True)
            (d / f["name"]).write_text(f["text"], encoding="utf-8")
        await core.call("knowledge_folder_add", path=str(d))
        made.setdefault("folders", []).append(str(d))
        for _ in range(60):                            # читается в фоне — ждём, пока прочитается
            st = await core.call("knowledge_folders") or []
            if any(x.get("path") == str(d.resolve()) and x.get("chunks") and not x.get("busy") for x in st):
                break
            await asyncio.sleep(0.5)
    return made


async def unseed(core, made):
    for f in made.get("notes") or []:
        try:
            f.unlink()
        except OSError:
            pass
    for rid in made.get("reminders") or []:
        try:
            await core.call("reminder_cancel", id=rid)
        except Exception:  # noqa: BLE001
            pass
    for tid in made.get("tasks") or []:
        try:
            await core.call("task_delete", id=tid)
        except Exception:  # noqa: BLE001 — уже удалена (так и надо было)
            pass
    for d in made.get("folders") or []:
        try:
            await core.call("knowledge_folder_remove", path=d)
        except Exception:  # noqa: BLE001
            pass


async def program_state(core, sd):
    """Что на самом деле есть в программе — для судьи: все заметки и напоминания, а не только положенные сценарием
    (экзамен 11.10: заметки и напоминания, созданные прошлыми сценариями, судья считал выдуманными)."""
    out = []
    if sd.get("notes"):
        root = core.tmp / "ws" / "Заметки"
        ns = sorted(root.rglob("*.md"), key=lambda p: -p.stat().st_mtime) if root.is_dir() else []
        out.append(f"заметок {len(ns)}: " + "; ".join(p.stem for p in ns[:12]))
    if sd.get("reminders"):
        try:
            items = await core.call("reminders") or []
        except Exception:  # noqa: BLE001
            items = []
        out.append(f"напоминаний {len(items)}: " + "; ".join(f"{x.get('text')} — {x.get('at')}" for x in items[:12]))
    return "; ".join(out)


async def reset_state(core):
    """Каждое испытание — с чистого листа (экзамен 16.10: «отчёт по продажам» из одного испытания всплывал в плейлисте и
    советах про кино, заметка «Позвонить Ольге» — в «содержимом скриншота», а фоновая задача прошлого испытания докладывала
    «готова» вместо новой презентации). Память, заметки, напоминания, расходы и идущие задачи прошлых испытаний — убираем."""
    try:
        await core.call("memory_set", text="")
    except Exception:  # noqa: BLE001
        pass
    root = core.tmp / "ws" / "Заметки"
    if root.is_dir():
        shutil.rmtree(root, ignore_errors=True)
    # и журнал сработавших напоминаний: календарь и «что по плану?» показывают прозвеневшее — прошлое испытание подсовывало
    # своё («подготовить презентацию, сработало в 8:05» — судья счёл выдумкой, экзамен ПК 0.81.1)
    try:
        (core.tmp / "st" / "reminders-log.json").unlink()
    except OSError:
        pass
    try:                                           # «Собери совет» прошлого испытания не должен договаривать итог в этом
        await core.call("council_stop")
    except Exception:  # noqa: BLE001
        pass
    for cmd, lst, kill, key in (("reminders", None, "reminder_cancel", "id"), ("money_list", None, "money_delete", "id"),
                                ("tasks_list", None, "task_delete", "id")):
        try:
            items = await core.call(cmd) or []
        except Exception:  # noqa: BLE001
            continue
        for x in items if isinstance(items, list) else []:
            try:
                if cmd == "tasks_list" and x.get("status") not in ("done", "failed", "error", "stopped", "cancelled"):
                    await core.call("task_stop", id=x.get(key))
                await core.call(kill, id=x.get(key))
            except Exception:  # noqa: BLE001
                pass


def _thread(fn, *a, **kw):
    """Вызвать fn в отдельном потоке и ждать без блокировки (asyncio.to_thread — только с Python 3.9)."""
    import functools
    return asyncio.get_running_loop().run_in_executor(None, functools.partial(fn, *a, **kw))


def _dur(sec):
    """180 → «3 мин», 45 → «45 с»."""
    return f"{round(sec / 60)} мин" if sec >= 90 else f"{round(sec)} с"


class StepTimeout(Exception):
    """Шаг сценария не уложился в STEP_S."""


def scenario_limit(sc):
    """Сколько секунд сценарию можно идти: обычному — SCEN_S; долгому — время его задачи + 3 минуты, не больше LONG_MAX_S;
    большой задаче — так же, но до BIG_MAX_S (60 минут)."""
    if sc.get("big"):
        return min(BIG_MAX_S, float(sc["big"].get("timeout") or 2400) + 180)
    if sc.get("code") or (sc.get("state") or {}).get("task"):
        own = float((sc.get("code") or {}).get("timeout") or ((sc.get("state") or {}).get("task") or {}).get("timeout") or 1200)
        return min(LONG_MAX_S, own + 180)
    return SCEN_S


async def run_scenario(core, sc, judge_prof, work, log):
    t0 = time.time()
    res = {"id": sc["id"], "group": sc["group"], "title": sc["title"], "video": bool(sc.get("video")), "steps": [], "checks": []}
    limit = scenario_limit(sc)
    made = {}

    async def body():
        nonlocal made
        await reset_state(core)
        made = await seed(core, sc.get("seed")) if sc.get("seed") else {}
        return await _run_scenario(core, sc, judge_prof, work, log, t0, res)
    try:
        return await asyncio.wait_for(body(), limit)
    except asyncio.TimeoutError:
        # сценарий не уложился (модель или шлюз отвечают очень долго): ход ядра прерываем, в отчёте — «превышено время»
        await core.interrupt()
        res["timeout"] = f"превышено время сценария ({_dur(limit)})"
        res["error"] = "⏱ " + res["timeout"]
        res["time_s"] = round(time.time() - t0, 1)
        log(f"   ⏱ {res['timeout']}")
        return finish_result(core, res)
    finally:
        if made:
            try:
                await asyncio.wait_for(unseed(core, made), 60)
            except Exception:  # noqa: BLE001
                pass


async def _run_scenario(core, sc, judge_prof, work, log, t0, res):
    try:
        await core.say("Начнём новый разговор", timeout=30)
        if sc.get("big"):
            state_text = await run_big(core, sc, res, t0, work, log)
        elif sc.get("code"):
            c = sc["code"]
            repo = make_repo(c["repo"], work)
            t = await core.call("task_create", title=sc["title"], goal=c["goal"], project=str(repo))
            res["steps"].append({"say": f"[задача по коду] {c['goal']}", "answer": ""})
            t = await wait_task(core, t0, float(c.get("timeout", 1200)), tid=t.get("id"))
            st = (t or {}).get("status")
            res["checks"].append({"name": "задача по коду завершена", "ok": st == "done", "detail": f"статус: {st}"})
            wt = Path((t or {}).get("dir", "")) / "рабочая копия"
            folder = wt if wt.is_dir() else repo
            ok, tail = await _thread(run_tests, folder)
            res["checks"].append({"name": "тесты проекта проходят", "ok": ok, "detail": tail[-300:]})
            if c.get("hidden_test"):
                ok2, tail2 = await _thread(run_tests, folder, {f"test_hidden_{c['hidden_test']}.py": HIDDEN[c["hidden_test"]]})
                res["checks"].append({"name": "скрытые проверки проходят", "ok": ok2, "detail": tail2[-300:]})
            orig = {n: src for n, src in REPOS[c["repo"]].items() if n.startswith("tests/")}  # сверка с исходным текстом:
            weakened = []                                                                     # дописывать тесты можно,
            for n, src in orig.items():                                                       # убирать и менять — нет
                have = (folder / n).read_text(encoding="utf-8").splitlines() if (folder / n).exists() else None
                if have is None or any(ln.strip() and ln not in have for ln in src.splitlines()):
                    weakened.append(n)
            res["checks"].append({"name": "тесты проекта не ослаблены", "ok": not weakened, "detail": ", ".join(weakened)})
            res["steps"][-1]["answer"] = ((t or {}).get("result") or "")[:1500]
            task_detail(res, t)
            state_text = f"задача: {st}; " + "; ".join(f"{x['name']}: {'да' if x['ok'] else 'нет'}" for x in res["checks"])
            if any(x["name"] == "скрытые проверки проходят" for x in res["checks"]):
                state_text += (" (скрытые проверки — тесты экзамена, помощник их не видел; его «все тесты проходят» — о тестах "
                               "проекта, и это правда, если «тесты проекта проходят: да». Не проходят скрытые — функция работает "
                               "не во всех случаях: снижай оценку за качество, но не называй это выдумкой)")
        else:
            for stp in sc["steps"]:
                if stp.get("new"):
                    await core.say("Начнём новый разговор", timeout=30)
                    res["steps"].append({"say": "[новый разговор]", "answer": ""})
                    continue
                img = make_image(stp["image"]) if stp.get("image") else None
                if stp.get("image") and img is None:
                    res["skipped"] = "нет шрифта с кириллицей для картинки"
                    return res
                if stp.get("template"):                 # готовый персонаж из галереи (Джарвис, Эва…) — добавить перед шагом
                    await core.call("gallery_add", id=stp["template"])
                if stp.get("persona"):                  # кто отвечает на этот шаг (команда: Лира, Патрик)
                    await core.call("persona_set", id=stp["persona"])
                said = fill(stp["say"])
                ans, ev = await core.say(said, img)
                src = [x.get("label") or x.get("name") for e in ev if e.get("type") == "answer" and e.get("done") for x in e.get("sources") or []]
                res["steps"].append({"say": said, "image": stp.get("image"), "answer": ans[:2000], "tools": tools_of(ev), "sources": src})
                if core.timed_out:                      # шаг не уложился в STEP_S — прерываем ход, дальше не идём
                    await core.interrupt()
                    res["steps"][-1]["timeout"] = True
                    res["timeout"] = f"превышено время шага ({_dur(STEP_S)}): модель так и не ответила"
                    res["error"] = "⏱ " + res["timeout"]
                    raise StepTimeout(res["timeout"])
            last = res["steps"][-1]["answer"]
            res["checks"] += check_answer(sc.get("expect"), last)
            if sc.get("source"):                          # ответ по документам — под ним нужный файл (кнопка «открыть»)
                got = [x for s_ in res["steps"] for x in s_.get("sources") or []]
                res["checks"].append({"name": "под ответом — файл-источник", "ok": any(w.lower() in str(g).lower() for g in got for w in sc["source"]),
                                      "detail": ", ".join(got) or "источников нет"})
            for name in sc.get("tool") or {}:              # действие правда выполнено (как на телефоне): show_images, mark_done…
                used = [x["name"] for s in res["steps"] for x in s.get("tools") or []]
                res["checks"].append({"name": f"действие {name} выполнено", "ok": any(x["name"] == name and x["ok"] for s in res["steps"]
                                                                                   for x in s.get("tools") or []), "detail": ", ".join(used)})
            # «как в жизни» (18.10: на съёмке «позвони», «включи видео» срабатывали раз, а потом — одни слова; «Я Лира.»
            # повторялось слово в слово): действие — на каждую просьбу, а не только на первую; ответы — не копия прошлых
            real = [s_ for s_ in res["steps"] if s_["say"] != "[новый разговор]"]
            for name, n in (sc.get("tool_count") or {}).items():
                k = sum(1 for s_ in real if any(x["name"] == name and x["ok"] for x in s_.get("tools") or []))
                res["checks"].append({"name": f"действие {name} — на каждую просьбу ({n})", "ok": k >= int(n),
                                      "detail": f"шагов с действием: {k} из {len(real)}"})
            if sc.get("distinct"):
                norm = [re.sub(r"[^a-zа-яё0-9]+", " ", s_["answer"].lower().replace("ё", "е")).strip() for s_ in real]
                res["checks"].append({"name": "ответы не повторяются слово в слово", "ok": len(set(norm)) == len(norm) and all(norm),
                                      "detail": " | ".join(x[:60] for x in norm)})
            if (sc.get("expect") or {}).get("sleep"):       # «стоп» (и ослышанное «Ctop.») — замолчать, а не «Хорошо, я слушаю»
                res["checks"].append({"name": "замолчала до имени, без ответа", "ok": any(e.get("type") == "sleep" for e in ev) and not last.strip(),
                                      "detail": last[:120]})
            res["checks"] += await check_state(core, sc.get("state"), t0)
            if sc.get("seed"):                          # судье — что было в программе (иначе «выдумал заметки», которые правда есть)
                res["checks"].append({"name": "в программе было", "ok": True, "detail": await program_state(core, sc["seed"])})
            if (sc.get("state") or {}).get("task"):
                want = sc["state"]["task"]
                t = await wait_task(core, t0, float(want.get("timeout", 1200)))
                outs = [o.get("path", "") for o in (t or {}).get("outputs") or []]
                res["checks"].append({"name": "задача завершена", "ok": (t or {}).get("status") == "done", "detail": f"статус: {(t or {}).get('status')}"})
                task_detail(res, t)
                res["checks"].append({"name": "есть файл результата", "ok": any(o.lower().endswith(tuple(want["outputs"])) for o in outs),
                                      "detail": ", ".join(outs)[:200]})
            state_text = "; ".join(f"{x['name']}: {'да' if x['ok'] else 'нет'}" + (f" ({x['detail']})" if x.get("detail") else "")
                                   for x in res["checks"] if "ответе" not in x["name"])
        transcript = "\n".join((f"Пользователь: {s['say']}" + (" [приложена картинка]" if s.get("image") else "")
                                + "".join(f"\n  [помощник вызвал {x['name']}({x['args']}) → {x['result'] or x['error']}]" for x in s.get("tools") or [])
                                + f"\nПомощник: {s['answer']}") for s in res["steps"])
        try:
            mem = (core.tmp / "ws" / "Память" / "Обо мне.md").read_text(encoding="utf-8")
        except OSError:
            mem = ""
        res["judge"] = None
        if sc.get("judge"):                             # в потоке: сценарий можно прервать по пределу и во время судьи
            try:
                res["judge"] = await asyncio.wait_for(_thread(judge, judge_prof, sc, transcript, state_text,
                                                                        at=dt.datetime.fromtimestamp(t0), memory=mem), JUDGE_S)
            except asyncio.TimeoutError:
                res["judge"] = {"score": None, "why": f"судья не ответил за {round(JUDGE_S)} с"}
    except StepTimeout as e:
        log(f"   ⏱ {e}")
    except Exception as e:  # noqa: BLE001
        res["error"] = f"{e.__class__.__name__}: {e}"
        log(f"   ⚠ {res['error']}")
    finally:
        res["time_s"] = round(time.time() - t0, 1)
    return finish_result(core, res)


async def run_big(core, sc, res, t0, work, log):
    """Большая задача (группа «Большие задачи», docs/HARNESS.md раздел 5): задача создаётся без запуска, в её папку кладётся
    заготовка (make_fixture — ответы остаются у экзамена), задача запускается; restart_after — после стольких шагов ядро
    останавливается и запускается снова (Б11). Проверки — BIG_CHECKS, метрики — шаги, токены, доля кэша, время. -> текст для судьи."""
    b = sc["big"]
    goal = fill(b["goal"])
    web = None
    if b["fixture"] == "research":                     # Б1: локальный «интернет» — страницы и поиск заготовки (WebFixture)
        from exam_big import WebFixture
        web = WebFixture(Path(work) / "big" / f"site-{sc['id']}")
    try:
        return await _run_big(core, sc, res, t0, work, log, b, goal, web)
    finally:
        if web is not None:
            web.close()


async def _run_big(core, sc, res, t0, work, log, b, goal, web):
    t = await core.call("task_create", title=sc["title"], goal=goal, start=False, **({"search_url": web.url} if web else {}))
    tdir = Path(t["dir"])
    kw = {"site": str(web.root), "base": web.url} if web else {}
    info = await _thread(make_fixture, b["fixture"], tdir, int(b.get("seed") or 1), **kw)
    (Path(work) / "big").mkdir(parents=True, exist_ok=True)
    (Path(work) / "big" / f"{sc['id']}.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")   # ответы — не в папке задачи
    res["steps"].append({"say": f"[большая задача] {goal}", "answer": ""})
    await core.call("task_resume", id=t["id"])
    limit = float(b.get("timeout") or 2400)
    if b.get("restart_after"):
        end = time.monotonic() + limit
        while time.monotonic() < end:
            lst = await core.call("tasks_list") or []
            x = next((y for y in lst if y.get("id") == t["id"]), {})
            if int(x.get("steps") or 0) >= int(b["restart_after"]) or x.get("status") in ("done", "failed", "stopped"):
                break
            await asyncio.sleep(1)
        if x.get("status") not in ("done", "failed", "stopped"):
            log(f"   ↻ перезапуск ядра после шага {x.get('steps')}")
            await core.stop()
            core.start()
            await core.connect()
            info["restarted"] = True
            for _ in range(120):                           # продолжит сама через ~20 с (auto_resume) — ждём, пока проснётся
                lst = await core.call("tasks_list") or []
                x = next((y for y in lst if y.get("id") == t["id"]), {})
                if x.get("status") != "paused" or not x.get("auto_resume"):
                    break
                await asyncio.sleep(1)
    t = await wait_task(core, t0, limit, tid=t["id"])
    task_detail(res, t)
    res["steps"][-1]["answer"] = ((t or {}).get("result") or "")[:1500]
    st = (t or {}).get("status")
    if b["fixture"] != "anki":
        res["checks"].append({"name": "задача завершена", "ok": st == "done", "detail": f"статус: {st}"})
    try:
        res["checks"] += await _thread(BIG_CHECKS[b["fixture"]], tdir, info, t)
    except Exception as e:  # noqa: BLE001 — сломалась проверка (кривой файл результата) — это провал сценария, не экзамена
        res["checks"].append({"name": "проверка итога", "ok": False, "detail": f"{e.__class__.__name__}: {e}"})
    res["metrics"] = big_metrics(t, time.time() - t0)
    files = []
    for p in sorted((tdir / "outputs").rglob("*")) if (tdir / "outputs").is_dir() else []:
        if p.is_file():
            files.append(f"{p.relative_to(tdir).as_posix()} ({p.stat().st_size} байт)")
    return (f"задача: {st}; файлы: {', '.join(files[:20]) or 'нет'}; "
            + "; ".join(f"{x['name']}: {'да' if x['ok'] else 'нет'}" + (f" ({x['detail']})" if x.get("detail") and not x["ok"] else "")
                        for x in res["checks"]))


def big_metrics(t, sec):
    """Метрики большой задачи: шаги, токены на вход и выход, доля кэша, время (с)."""
    u = ((t or {}).get("quality") or {}).get("usage") or {}
    m = {"steps": int((t or {}).get("steps") or 0), "tok_in": int(u.get("in") or 0), "tok_out": int(u.get("out") or 0),
         "cache": round(u["cached"] / u["in"], 3) if u.get("ck") and u.get("in") else None, "time_s": round(sec), "req": int(u.get("req") or 0)}
    subs = ((t or {}).get("quality") or {}).get("subs") or {}
    if subs:                                           # выпуск 6: помощники (разведчик, проверяющий — в tok_*; части — отдельно)
        m["tok_sub"] = sum(int(x.get("in") or 0) + int(x.get("out") or 0) for x in subs.values() if isinstance(x, dict))
        m["parts"] = int((subs.get("part") or {}).get("n") or 0)
    return m


def finish_result(core, res):
    j = (res.get("judge") or {}).get("score")
    res["passed"] = (not res.get("error") and not res.get("skipped") and all(c["ok"] for c in res["checks"])
                     and (j is None or j >= PASS_SCORE))
    # «не проверено» (нет браузера для Б5): не «сдано» и не «провал» — отдельный статус: всё, что проверено, прошло
    unch = [c["name"] for c in res["checks"] if c.get("unchecked")]
    res["partial"] = bool(unch and not res["passed"] and not res.get("error") and not res.get("skipped")
                          and all(c["ok"] or c.get("unchecked") for c in res["checks"]) and (j is None or j >= PASS_SCORE))
    if unch:
        res["unchecked"] = unch
    if not res["passed"] and not res.get("skipped"):
        w = core_warnings(core)
        if w:
            res["core_log"] = w
    res["score"] = j
    return res


def summary(results):
    by = {}
    for r in results:
        if r.get("skipped"):
            continue
        g = by.setdefault(r["group"], {"passed": 0, "total": 0})
        g["total"] += 1
        g["passed"] += 1 if r["passed"] else 0
        if r.get("partial"):
            g["partial"] = g.get("partial", 0) + 1
    done = [r for r in results if not r.get("skipped")]
    scores = [r["score"] for r in done if r.get("score") is not None]
    out = {"passed": sum(1 for r in done if r["passed"]), "total": len(done), "by_group": by,
           "partial": sum(1 for r in done if r.get("partial")),        # сдано не полностью: часть не проверить (нет браузера)
           "avg_score": round(sum(scores) / len(scores), 1) if scores else None}
    big = [r["metrics"] for r in done if r.get("metrics")]

    def mean(xs):
        return sum(xs) / len(xs) if xs else 0
    if big:                                          # большие задачи: средние шаги, токены, доля кэша, время
        cache = [m["cache"] for m in big if m.get("cache") is not None]
        out["big"] = {"n": len(big), "steps": round(mean([m["steps"] for m in big]), 1), "tok_in": round(mean([m["tok_in"] for m in big])),
                      "tok_out": round(mean([m["tok_out"] for m in big])), "cache": round(mean(cache), 3) if cache else None,
                      "time_s": round(mean([m["time_s"] for m in big]))}
    return out


def markdown(rep):
    s = rep["summary"]
    lines = [f"# Экзамен Dewiar {rep['version']} — {rep['started'][:16].replace('T', ' ')}", "",
             f"Модель: **{rep['model']}**. Сдано **{s['passed']} из {s['total']}**"
             + (f" (и ещё {s['partial']} — не проверено до конца: нет браузера)" if s.get("partial") else "")
             + (f", средняя оценка судьи {s['avg_score']}" if s.get("avg_score") is not None else "") + f", {round(rep['duration_s'] / 60)} мин.", ""]
    for g, v in s["by_group"].items():
        lines.append(f"- {g}: {v['passed']} из {v['total']}" + (f", не проверено до конца — {v['partial']}" if v.get("partial") else ""))
    if s.get("big"):
        b = s["big"]
        lines.append(f"- большие задачи в среднем: шагов {b['steps']}, токенов {b['tok_in']} на вход и {b['tok_out']} на выход"
                     + (f", из кэша {round(100 * b['cache'])}%" if b.get("cache") is not None else "") + f", {_dur(b['time_s'])}")
    for r in rep["scenarios"]:
        mark = "⏭" if r.get("skipped") else ("✅" if r["passed"] else ("◐" if r.get("partial") else "❌"))
        lines += ["", f"## {mark} {r['group']} — {r['title']}" + (" 🎬" if r.get("video") else ""),
                  f"_{r['time_s']} с" + (f", судья: {r['score']:g}/10 — {r['judge']['why']}" if r.get("score") is not None else "") + "_"]
        if r.get("metrics"):
            m = r["metrics"]
            lines.append(f"_Шагов {m['steps']}, токенов {m['tok_in']} → {m['tok_out']}" + (f", из кэша {round(100 * m['cache'])}%" if m.get("cache") is not None else "") + "_")
        for st in r["steps"]:
            lines += ["", f"> **Вы:** {st['say']}"]
            for x in st.get("tools") or []:
                lines.append(f">  🔧 `{x['name']}` {x['args'][:120]} → {(x['result'] or ('⚠ ' + x['error']))[:160]}".replace("\n", " "))
            lines += ["", f"**Помощник:** {st['answer'] or '—'}"]
        if r.get("task") and r["task"].get("status") != "done":
            tk = r["task"]
            lines += ["", f"_Задача: {tk.get('status')}" + (f" ({tk['fail_kind']})" if tk.get("fail_kind") else "")
                      + (f" — {tk['error']}" if tk.get("error") else "") + "_"]
            if tk.get("journal"):
                lines += ["", "<details><summary>Журнал задачи (конец)</summary>", "", "```", tk["journal"][-2000:], "```", "", "</details>"]
        for c in r["checks"]:
            lines.append(f"- {'✓' if c['ok'] else ('◐' if c.get('unchecked') else '✗')} {c['name']}" + (f" — `{c['detail'][:160]}`" if c.get("detail") and not c["ok"] else ""))
        if r.get("error"):
            lines.append(f"- ⚠ {r['error']}")
        if r.get("skipped"):
            lines.append(f"- пропущен: {r['skipped']}")
    return "\n".join(lines) + "\n"


def access_revoked(profile, timeout=10):
    """Модель облака Dewiar: доступ ещё есть? -> текст причины, если отозван (403: экзамен остановили в кабинете, ключ
    приостановлен), иначе "" (и когда облако просто не ответило — это не повод останавливаться)."""
    import httpx
    base = str(profile.get("base_url") or "")
    if not (profile.get("cloud") or "cloud.php?p=" in base) or not profile.get("api_key"):
        return ""
    try:
        r = httpx.get(base + "/balance", headers={"Authorization": "Bearer " + str(profile["api_key"])}, timeout=timeout)
    except Exception:  # noqa: BLE001
        return ""
    if r.status_code != 403:
        return ""
    try:
        e = (r.json().get("error") or {})
    except ValueError:
        e = {}
    return str(e.get("message") or "доступ к модели отозван")


async def watch_access(profile, core, tmp, keep, log):
    """Сторож: раз в ALIVE_S с — жив ли экзамен (доступ к модели). Отозван — гасим ядро и выходим сразу, не дожидаясь
    ответа модели или судьи (они могут ждать минутами)."""
    while True:
        await asyncio.sleep(ALIVE_S)
        why = await _thread(access_revoked, profile)
        if why:
            log(f"Экзамен остановлен: {why}")
            try:
                if core.proc and core.proc.poll() is None:
                    core.proc.kill()
            except Exception:  # noqa: BLE001
                pass
            if not keep:
                shutil.rmtree(tmp, ignore_errors=True)
            sys.stdout.flush()
            os._exit(EXIT_CANCELLED)


def load_partial(path):
    """Сделанное в прошлый раз (--resume): {started, results} или None."""
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return d if isinstance(d.get("results"), list) else None
    except (OSError, ValueError, AttributeError):
        return None


async def run_exam(profile, judge_prof=None, only=None, long=False, log=print, keep=None, lean=False, partial=None, resume=False, big=False):
    from version import VERSION
    data = json.loads(SCEN.read_text(encoding="utf-8"))
    scs = [s for s in data["scenarios"] if (not only or s["id"] in only) and (long or not s.get("long") or (only and s["id"] in only))
           and (big or not s.get("big") or (only and s["id"] in only))]   # большие задачи — только с --big (галочка)
    tmp = Path(keep) if keep else Path(tempfile.mkdtemp(prefix="dewiar-exam-"))
    core = Core(profile, tmp / "core", log, lean=lean)
    started = dt.datetime.now()
    results = []
    prev = load_partial(partial) if (partial and resume) else None
    if prev:                                        # исполнитель перезапустился посреди прогона — продолжаем, а не заново
        ids = {s["id"] for s in scs}
        results = [r for r in prev["results"] if r.get("id") in ids]
        try:
            started = dt.datetime.fromisoformat(prev.get("started") or "")
        except ValueError:
            pass
    done = {r["id"] for r in results}
    log(f"Экзамен Dewiar {VERSION}: {len(scs)} сценариев, модель {profile.get('title') or profile.get('model')}"
        + (f" — продолжаю: {len(done)} уже пройдены" if done else ""))

    def save_partial():
        if partial:
            try:
                Path(partial).write_text(json.dumps({"started": started.isoformat(timespec="seconds"), "results": results},
                                                    ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass
    core.start()
    watch = asyncio.ensure_future(watch_access(profile, core, tmp, keep, log))
    try:
        await core.connect()
        for i, sc in enumerate(scs, 1):
            if sc["id"] in done:
                continue
            log(f"[{i}/{len(scs)}] {sc['group']} — {sc['title']}")
            r = await run_scenario(core, sc, judge_prof or profile, tmp / "repos", log)
            log(f"   {'⏭ пропущен' if r.get('skipped') else ('✅ сдан' if r['passed'] else '✗ не сдан')}"
                + (f", судья {r['score']:g}" if r.get("score") is not None else "") + f", {r['time_s']} с")
            results.append(r)
            save_partial()
    finally:
        watch.cancel()
        await core.stop()
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)
    order = {s["id"]: k for k, s in enumerate(scs)}
    results.sort(key=lambda r: order.get(r.get("id"), 0))
    rep = {"version": VERSION, "started": started.isoformat(timespec="seconds"), "duration_s": round((dt.datetime.now() - started).total_seconds()),
           # проба короткой инструкции — в подписи модели: в кабинете и отчёте сразу видно, какой прогон с чем сравнивать
           "model": (profile.get("title") or profile.get("model") or "?") + (" · короткая инструкция" if lean else ""), "lean": bool(lean),
           "host": platform.node()[:40],
           "os": f"{platform.system()} {platform.release()}"[:60], "long": bool(long), "big": bool(big), "scenarios": results}
    rep["summary"] = summary(results)
    return rep


def upload(rep, url, key):
    import httpx
    from cloud import base_of, norm_key
    body = json.loads(json.dumps(rep))
    for r in body["scenarios"]:
        for s in r["steps"]:
            s["answer"] = (s.get("answer") or "")[:1500]
    body["md"] = markdown(rep)                                   # кабинет отдаёт его как «Отчёт .md» без пересборки
    r = httpx.post(base_of(url) + "?p=/exam", json=body, headers={"Authorization": f"Bearer {norm_key(key)}"}, timeout=60)
    d = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code >= 400 or not d.get("ok"):
        raise RuntimeError(f"кабинет не принял: {r.status_code} {str(d)[:200]}")
    return d.get("id")


def main():
    ap = argparse.ArgumentParser(description="Экзамен способностей Dewiar (см. начало файла)")
    ap.add_argument("--key", help="ключ Dewiar (dw-…): экзаменуем модель облака Dewiar")
    ap.add_argument("--url", default="", help="адрес облака (по умолчанию dewiar.pro)")
    ap.add_argument("--model", default="", help="модель облака (по умолчанию первая доступная ключу)")
    ap.add_argument("--llm", help="профиль модели JSON: {kind, base_url, model, api_key}")
    ap.add_argument("--judge", help="профиль судьи JSON (по умолчанию — та же модель)")
    ap.add_argument("--only", help="только эти сценарии: id через запятую")
    ap.add_argument("--long", action="store_true", help="и долгие: фоновые задачи и код")
    ap.add_argument("--big", action="store_true", help="и большие задачи (Б1, Б3–Б7, Б11: до часа каждая, docs/HARNESS.md)")
    ap.add_argument("--out", default=".", help="куда положить отчёт")
    ap.add_argument("--upload", action="store_true", help="отправить отчёт в кабинет (тем же ключом)")
    ap.add_argument("--keep", help="папка для временных файлов ядра (не удалять — для разбора)")
    ap.add_argument("--lean", action="store_true", help="короткая инструкция модели (llm.lean_prompt) — проба")
    ap.add_argument("--json-out", help="записать отчёт JSON (с md) ещё и в этот файл — так его забирает исполнитель")
    ap.add_argument("--partial", help="после каждого сценария — сделанное в этот файл (для --resume)")
    ap.add_argument("--resume", action="store_true", help="продолжить по файлу --partial: пройденные сценарии не повторять")
    a = ap.parse_args()
    env_llm = os.environ.get("DEWIAR_EXAM_LLM")           # исполнитель на сервере: профиль с доверенностью — не в командной строке
    if env_llm:
        prof = json.loads(env_llm)
    elif a.llm:
        prof = json.loads(a.llm)
    elif a.key:
        from cloud import api_base, fetch, norm_key
        key = norm_key(a.key)
        models = (fetch(a.url, key, "/models").get("data") or [])
        m = next((x for x in models if x["id"] == a.model), models[0] if models else {"id": a.model or "chat"})
        prof = {"name": "Dewiar Облако", "kind": "openai", "base_url": api_base(a.url), "api_key": key, "model": m["id"],
                "cloud": True, "title": m.get("title") or m["id"]}
    else:
        ap.error("нужен --key или --llm")
    jp = json.loads(a.judge) if a.judge else None
    rep = asyncio.run(run_exam(prof, jp, set(a.only.split(",")) if a.only else None, a.long, keep=a.keep, lean=a.lean,
                               log=lambda t: print(t, flush=True), partial=a.partial, resume=a.resume, big=a.big))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"exam-{rep['started'][:16].replace('-', '').replace(':', '').replace('T', '-')}"
    (out / f"{stem}.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / f"{stem}.md").write_text(markdown(rep), encoding="utf-8")
    if a.json_out:
        Path(a.json_out).write_text(json.dumps(dict(rep, md=markdown(rep)), ensure_ascii=False), encoding="utf-8")
    s = rep["summary"]
    print(f"\nСдано {s['passed']} из {s['total']}. Отчёт: {out / stem}.md", flush=True)
    if a.upload:
        if not a.key:
            print("Отправка в кабинет — только с --key")
        else:
            print(f"В кабинете: экзамен №{upload(rep, a.url, a.key)}")


if __name__ == "__main__":
    main()
