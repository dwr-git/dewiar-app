"""Образы Лиры (владелец 20.11: «Лира бывает разной»): живое лицо образа из картинки, где лицо совпадает с
data/avatars/lira.webp (нарисовано по исходнику; картинки — design/looks/lira-<образ>.jpg).

Каждый образ — свой набор слоёв, как у Патрика (tools/live_face.py): портрет 360×360 в кадре lira.webp (вырезка 26, 54,
458×458 из портрета 512), фон снят мягко (кайма волос — прозрачностью по яркости, без чёрного ореола), глаза — пустые
белком ЭТОГО образа, радужка — вырезанная с ЭТОГО образа (в покое лицо в точности как на фото), рот 0..3 и улыбка — из губ
ЭТОГО образа. В entities.js — LIVE_CONF["lira-<образ>"] (геометрия печатается в конце).
Запуск: python3 tools/live_looks.py [образ …]"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import live_face as LF  # noqa: E402

SRC = ROOT / "design/looks"
LIVE = ROOT / "ui/assets/live"
K = LF.K
# по персонажу: кадр живого портрета в портрете 512, где глаза (центры радужки), диаметр выреза радужки, губы
# (линия смыкания, середина, полуширина) и рамка слоя рта — всё в пикселях живого портрета 360
WHO = {
    "lira": {"crop": (26, 54, 484, 512), "eyes": [(147.5, 162.6), (212.6, 163.2)], "iris": 16.0,
             "lip": (227.0, 180.0, 23.5), "mouth": (147.0, 206.0, 66.0, 44.0), "smile": 2.2, "light_hair": True},
    "patrik": {"crop": (0, 0, 512, 512), "eyes": [(146.8, 148.9), (212.5, 149.3)], "iris": 15.0,
               "lip": (221.4, 180.0, 28.5), "mouth": (143.0, 201.0, 74.0, 44.0), "smile": 2.4, "light_hair": False},
}
CROP = WHO["lira"]["crop"]


NECK_GAP = {"lira-home"}                          # высокий ворот: тёмный фон по бокам шеи — насквозь


def matte(src, crop=None, light_hair=True, neck_gap=False):
    big = src.crop(crop or CROP).resize((360 * K, 360 * K), Image.LANCZOS)
    arr = np.asarray(big).astype(np.float32)
    lum = arr.max(2)
    m = Image.fromarray((lum < (30 if light_hair else 14)).astype(np.uint8) * 255, "L").copy()
    n = 360 * K - 1
    for xy in [(0, 0), (n, 0), (0, n), (n, n), (n // 2, 0), (0, n // 2), (n, n // 2)]:
        if m.getpixel(xy) == 255:
            ImageDraw.floodfill(m, xy, 128)
    bg = Image.fromarray(np.where(np.asarray(m) == 128, 255, 0).astype(np.uint8), "L")
    # волосы: тёмные просветы между прядями и тёмная кайма — насквозь (на чёрном фоне видимое = прозрачность × цвет),
    # даже не связанные с краем; светлые пряди — как есть; лицо, шея и одежда по центру не трогаем (мягкая граница)
    H = 360 * K
    yy, xx = np.mgrid[0:H, 0:H].astype(np.float32) / K
    face = ((xx - 180) / 62) ** 2 + ((yy - 182) / 86) ** 2 < 1
    body = ((np.abs(xx - 180) < 44) & (yy > 205)) | ((np.abs(xx - 180) < 108) & (yy > 264)) | (yy > 292)   # низ — одежда (он и так растворяется в окне)
    prot = Image.fromarray(((face | body) * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(6 * K))
    w = 1 - np.asarray(prot).astype(np.float32) / 255                # 1 — волосы и фон, 0 — лицо и одежда
    near = np.asarray(bg.filter(ImageFilter.MaxFilter(9))) > 0
    a_dark = np.clip((lum - 12) / 110, 0, 1)
    # тёмные волосы (Патрик): по яркости их не отличить от чёрного фона — только фон, связанный с краем, мягким краем 1 px
    alpha = np.where(near, a_dark, w * a_dark + (1 - w)) if light_hair else 1.0 - np.asarray(bg.filter(ImageFilter.GaussianBlur(1.2))).astype(np.float32) / 255
    # чёрные просветы у шеи (между волосами и воротом); neck_gap (21.11, «Дома» — тёмные клинья у высокого ворота) — и ниже,
    # по бокам шеи; только образам из NECK_GAP: у остальных там тёмная механика шеи и чёрная одежда — их не трогаем
    hole = (lum < 24) & ~face & ((yy < 262) | (np.abs(xx - 180) > 70) | (neck_gap & (yy < 286) & (np.abs(xx - 180) > 36)))
    if light_hair:
        alpha = np.where(hole, np.minimum(alpha, a_dark), alpha)
    alpha = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(0.6))).astype(np.float32) / 255
    col = np.where(alpha[..., None] > 0.03, arr / np.maximum(alpha[..., None], 0.12), arr) if light_hair else arr
    return Image.fromarray(np.dstack([col.clip(0, 255), alpha * 255]).astype(np.uint8), "RGBA")


def find_iris(big, cx, cy):
    """Центр радужки рядом с (cx, cy): самые тёмные точки в круге 9 px (кадр 360) — их середина."""
    a = np.asarray(big).astype(np.float32)[..., :3].mean(2)
    x0, y0, R = int((cx - 12) * K), int((cy - 9) * K), 9 * K
    win = a[y0:y0 + 18 * K, x0:x0 + 24 * K]
    thr = np.percentile(win, 12)
    ys, xs = np.nonzero(win <= thr)
    return (x0 + xs.mean()) / K, (y0 + ys.mean()) / K


def build(name, who="lira"):
    W = WHO[who]
    LF.LIP_Y, LF.MOUTH_CX, LF.MOUTH_HALF = W["lip"]
    LF.MOUTH = W["mouth"]
    src = Image.open(SRC / f"{who}-{name}.jpg").convert("RGB").resize((512, 512), Image.LANCZOS)
    src.save(ROOT / f"data/avatars/{who}-{name}.webp", quality=90, method=6)
    big = matte(src, W["crop"], W["light_hair"], f"{who}-{name}" in NECK_GAP)
    # глаза — как на фото, без закраски белком (у Лиры тёмные тени вокруг глаз — «белок» выходил серым пятном):
    # радужка-слой вырезана из того же места портрета — в покое лицо в точности как на фото, при взгляде сдвигается на 1 px
    D = W["iris"]
    LF.IRIS, LF.IRIS_D = W["eyes"], D
    pre = f"{who}-{name}"
    big.resize((360, 360), Image.LANCZOS).save(LIVE / f"{pre}.webp", quality=92, method=6)
    for side, im in zip("lr", LF.iris_crops(big)):
        im.save(LIVE / f"{pre}-iris-{side}.png", optimize=True)
    for i, op in enumerate((0.0, 2.0, 3.6, 5.2)):
        LF.mouth_layer(big, open_px=op).save(LIVE / f"{pre}-mouth-{i}.webp", quality=92, method=6)
    LF.mouth_layer(big, smile_px=W["smile"]).save(LIVE / f"{pre}-smile.webp", quality=92, method=6)
    geo = {"eyes": [[round(x - D / 2, 1), round(y - D / 2, 1)] for x, y in W["eyes"]], "iris": D,
           "mouth": list(W["mouth"]), "moveX": 1.0, "moveY": 0.35}
    return {"own": True, "iris": [f"{pre}-iris-l.png", f"{pre}-iris-r.png"], "geo": geo}


THUMB_BOX = (71, 40, 441, 410)                 # кружок выбора — одинаковый кадр у всех (голова и причёска) в портрете 512
THUMB = 112


def thumb(who, look=""):
    """Кружок для выбора образа — у всех образов и у обычного облика один кадр и один размер: ui/assets/live/thumbs/<имя>.webp."""
    name = f"{who}-{look}" if look else who
    src = Image.open(ROOT / f"data/avatars/{name}.webp").convert("RGB").resize((512, 512), Image.LANCZOS)
    W = WHO[who]
    big = matte(src, (0, 0, 512, 512), W["light_hair"] and bool(look)) if look else matte(src, (0, 0, 512, 512), False)
    k = big.size[0] / 512
    out = big.crop(tuple(int(v * k) for v in THUMB_BOX)).resize((THUMB, THUMB), Image.LANCZOS)
    (LIVE / "thumbs").mkdir(exist_ok=True)
    out.save(LIVE / "thumbs" / f"{name}.webp", quality=88, method=6)


LOOKS = {"lira": ["hair", "home", "spring", "silk", "curls", "buns", "winter", "street", "gamer", "tails", "loose", "braid"], "patrik": ["suit", "home", "silver"]}

if __name__ == "__main__":
    conf = {}
    for who, names in LOOKS.items():
        for n in names:
            if len(sys.argv) < 2 or f"{who}-{n}" in sys.argv[1:]:
                conf[f"{who}-{n}"] = build(n, who)
    for who, names in LOOKS.items():                # кружки — всем (и обычному облику), одинаково
        thumb(who)
        for n in names:
            thumb(who, n)
    print(json.dumps(conf, ensure_ascii=False))
