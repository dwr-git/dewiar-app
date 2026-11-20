"""Ответ ядра окну («hello») — лёгкий (владелец 20.11: «Тяжёлый ответ при открытии виджета и студии — да!»). У людей он
доходил до ~5 МБ: своё фото персонажа (до 6 МБ) уходило целиком в каждое «hello» и в каждую рассылку персонажей
(на Mac — №908, предел websockets 1 МБ). Теперь крупное фото — уменьшенной копией; маленькое и анимация — как были."""
import base64, io, os, random, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_CONFIG_DIR"], os.environ["DEWIAR_STATE_DIR"] = str(tmp / "cfg"), str(tmp / "st")
sys.path.insert(0, str(ROOT / "core"))
from PIL import Image  # noqa: E402
import personas as P  # noqa: E402

bad = 0
def ok(c, m):
    global bad
    bad += 0 if c else 1
    print(("✅ " if c else "❌ ") + m)


def data_url(img, fmt):
    b = io.BytesIO(); img.save(b, fmt)
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(b.getvalue()).decode(), len(b.getvalue())


random.seed(1)
big = Image.frombytes("RGB", (1100, 1100), bytes(random.getrandbits(8) for _ in range(1100 * 1100 * 3)))   # фото с телефона: шум не жмётся
url, n = data_url(big, "PNG")
ps = P.Personas()
pid = ps.save({"name": "Тестовая", "gender": "female", "avatar_data": url})
pub = {p["id"]: p for p in ps.public()}
au = pub[pid]["avatar_url"]
ok(n > 3 * 1024 * 1024 and len(au) < 400 * 1024, f"фото {n // 1024} КБ — окну {len(au) // 1024} КБ")
im = Image.open(io.BytesIO(base64.b64decode(au.split(",", 1)[1])))
ok(max(im.size) == P.AVATAR_SIDE, f"уменьшенная копия {im.size}, картинка читается")
ok((P.PERSONAS_DIR / f"{pid}.avatar.png").stat().st_size == n, "сам файл персонажа не тронут (оригинал на месте)")
au2 = {p["id"]: p for p in ps.public()}[pid]["avatar_url"]
ok(au2 == au, "второй раз — то же самое (из памяти, без пересчёта)")

small, ns = data_url(Image.new("RGBA", (120, 120), (200, 100, 50, 128)), "PNG")
pid2 = ps.save({"name": "Маленькая", "gender": "female", "avatar_data": small})
ok({p["id"]: p for p in ps.public()}[pid2]["avatar_url"] == small, "маленькое фото — как было, байт в байт")

big_alpha = Image.frombytes("RGBA", (800, 800), bytes(random.getrandbits(8) for _ in range(800 * 800 * 4)))
u4, n4 = data_url(big_alpha, "PNG")
pid4 = ps.save({"name": "Прозрачная", "gender": "female", "avatar_data": u4})
a4 = {p["id"]: p for p in ps.public()}[pid4]["avatar_url"]
im4 = Image.open(io.BytesIO(base64.b64decode(a4.split(",", 1)[1])))
ok(len(a4) < n4 and im4.mode in ("RGBA", "LA", "P"), f"прозрачный фон сохраняется ({im4.format}, {im4.mode})")

ok(all(len(p.get("avatar_url") or "") < 120 * 1024 for p in ps.public() if p["id"] not in (pid, pid2, pid4)), "встроенные портреты — лёгкие")
print("ALL OK" if not bad else f"FAILED {bad}")
sys.exit(1 if bad else 0)
