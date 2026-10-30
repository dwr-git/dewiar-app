"""Обложки и видео уроков дома (29.10, владелец: «обложки положил — не видно», в браузере 01-council.jpg открывается,
а ?p=/academy отдаёт ссылки). Дома запрос ядра уходит на сайт напрямую (net._LanFirst), и сайт собирает ссылки из
своего Host — http://192.168.…:9099/dwrapp/academy/…; окно студии грузит картинки и видео само, мимо ядра.
Проверка: academy_list в ядре отдаёт публичные ссылки (как в браузере), чужие поля и YouTube не трогает."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import cloud  # noqa: E402
from engine_commands import CommandsMixin  # noqa: E402

LAN = "http://192.168.1.46:9099/dwrapp/academy/"
seen = []


def fake_public(url, path, body=None, timeout=20):
    seen.append((url, path))
    return {"ok": True, "items": [
        {"id": "01-council", "n": 1, "video": LAN + "01-council.mp4", "poster": LAN + "01-council.jpg", "youtube": ""},
        {"id": "02-watch", "n": 2, "video": "https://dewiar.pro/dwrapp/academy/02-watch.mp4", "poster": "", "youtube": ""},
        {"id": "03-leads", "n": 3, "video": "", "poster": LAN + "03-leads.jpg", "youtube": "https://youtu.be/xyz"}]}


cloud.public = fake_public


class E(CommandsMixin):
    class cloud:
        url = "https://dewiar.pro/dwrapp/cloud.php?p="
    kids = None


d = E().command("academy_list", {})
it = {x["id"]: x for x in d["items"]}
PUB = "https://dewiar.pro/dwrapp/academy/"
ok(seen and seen[0][1] == "/academy", "ядро спрашивает сайт ?p=/academy")
ok(it["01-council"]["poster"] == PUB + "01-council.jpg" and it["01-council"]["video"] == PUB + "01-council.mp4",
   f"домашние ссылки → публичные: {it['01-council']}")
ok(it["02-watch"]["video"] == PUB + "02-watch.mp4" and it["02-watch"]["poster"] == "", "публичные и пустые — без изменений")
ok(it["03-leads"]["youtube"] == "https://youtu.be/xyz" and it["03-leads"]["video"] == "" and it["03-leads"]["poster"] == PUB + "03-leads.jpg",
   "YouTube и пустое видео не трогаем")

E.cloud.url = "https://my-site.example/dw/cloud.php"
d = E().command("academy_list", {})
ok(d["items"][0]["poster"] == "https://my-site.example/dw/academy/01-council.jpg", "своё облако — ссылки на его адрес")

print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
