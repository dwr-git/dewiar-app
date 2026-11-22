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
             "lip": (227.0, 180.0, 23.5), "mouth": (147.0, 206.0, 66.0, 44.0), "smile_box": (116.0, 188.0, 128.0, 82.0), "smile": 5.5, "open": (0.0, 3.2, 5.6, 8.0), "light_hair": True},   # улыбка 5,5 (владелец 21.11: «у образов почти не видна»)
    "patrik": {"crop": (0, 0, 512, 512), "eyes": [(146.8, 148.9), (212.5, 149.3)], "iris": 15.0,
               "lip": (221.4, 180.0, 28.5), "mouth": (143.0, 201.0, 74.0, 44.0), "smile_box": (110.0, 182.0, 140.0, 82.0), "smile": 4.8, "open": (0.0, 2.8, 4.8, 7.0), "light_hair": False},
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


def source(who, name):
    """Исходник образа: design/looks/<who>-<name>.png с прозрачным фоном (владелец 21.11 снял фон сам, «качественно») —
    или прежний .jpg на чёрном. -> (RGB на чёрном 1024, RGBA 1024 или None)."""
    png = SRC / f"{who}-{name}.png"
    if png.exists():
        rgba = Image.open(png).convert("RGBA")
        if rgba.size != (1024, 1024):
            rgba = rgba.resize((1024, 1024), Image.LANCZOS)
        black = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
        black.alpha_composite(rgba)
        return black.convert("RGB"), rgba
    return Image.open(SRC / f"{who}-{name}.jpg").convert("RGB"), None


def matte_alpha(rgba, crop):
    """Готовый прозрачный фон: та же вырезка и размер, что у matte, прозрачность — как в исходнике (край чуть мягче)."""
    big = rgba.crop(crop).resize((360 * K, 360 * K), Image.LANCZOS)
    arr = np.asarray(big).astype(np.float32)
    a = np.asarray(Image.fromarray(arr[..., 3].astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(0.5))).astype(np.float32)
    return Image.fromarray(np.dstack([arr[..., :3], a]).clip(0, 255).astype(np.uint8), "RGBA")


def smile_real(who, name, big):
    """Настоящая улыбка образа (владелец 21.11: сдвиг губ выходил гримасой — «если не так симпатично, как у оригинальной Лиры,
    лучше без улыбки»; владелец прислал тот же кадр с лёгкой улыбкой: design/looks/<who>-<name>-smile.png). Слой — низ лица
    (губы, щёки, складки) из кадра с улыбкой в рамке smile_box с мягким овальным краем; общий тон кадра с улыбкой подгоняется
    под основной (генератор чуть менял цвет кожи) — по коже вокруг рта, без самого рта. -> (RGBA слоя в 3×, рамка) или (None, None)."""
    f = SRC / f"{who}-{name}-smile.png"
    if not f.exists():
        return None, None
    from scipy.ndimage import gaussian_filter
    W = WHO[who]
    sm = Image.open(f).convert("RGB")
    if sm.size != (1024, 1024):
        sm = sm.resize((1024, 1024), Image.LANCZOS)
    crop = tuple(round(v * 2) for v in W["crop"])
    sb = np.asarray(sm.crop(crop).resize((360 * K, 360 * K), Image.LANCZOS)).astype(np.float32)
    bb = np.asarray(big.convert("RGB")).astype(np.float32)
    x, y, w, h = W["smile_box"]
    X0, Y0, X1, Y1 = int(x * K), int(y * K), int((x + w) * K), int((y + h) * K)
    yy, xx = np.mgrid[0:360 * K, 0:360 * K].astype(np.float32)
    cx, cy, rx, ry = (X0 + X1) / 2, (Y0 + Y1) / 2, (X1 - X0) / 2, (Y1 - Y0) / 2
    r = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    mx, my, mw, mh = W["mouth"]
    rc = np.sqrt(((xx - (mx + mw / 2) * K) / (mw * K * 0.62)) ** 2 + ((yy - (my + mh / 2) * K) / (mh * K * 0.62)) ** 2)
    ring = ((r < 1.35) & (rc > 1.0)).astype(np.float32)          # кожа вокруг рта — по ней подгоняем тон
    s_ = 9.0 * K
    corr = np.dstack([gaussian_filter((bb[..., c] - sb[..., c]) * ring, s_) for c in range(3)]) / (gaussian_filter(ring, s_)[..., None] + 1e-3)
    out = np.clip(sb + corr, 0, 255)
    # цвет губ — как в основном кадре (владелец 21.11: «губы были бледными, стали розовыми»): средний оттенок области рта
    # кадра с улыбкой сдвигаем к оттенку основного, яркость и форма улыбки остаются
    rl = np.sqrt(((xx - (mx + mw / 2) * K) / (mw * K * 0.58)) ** 2 + ((yy - (my + mh / 2) * K) / (mh * K * 0.5)) ** 2)
    mk = np.clip((1.0 - rl) / 0.45, 0, 1)
    chroma = lambda im: im - im.mean(2, keepdims=True)   # noqa: E731
    cs = (chroma(out) * mk[..., None]).sum((0, 1)) / (mk.sum() + 1e-3)
    cb = (chroma(bb) * mk[..., None]).sum((0, 1)) / (mk.sum() + 1e-3)
    out = np.clip(out - mk[..., None] * (cs - cb), 0, 255)
    a = np.clip((1.0 - r) / 0.42, 0, 1) ** 1.6                    # мягкий овал: к краю рамки — основной кадр
    a = a * (np.asarray(big.getchannel("A")).astype(np.float32) / 255.0 if big.mode == "RGBA" else 1.0) ** 2
    # ↑ только по самому портрету: за контуром лица (фон окна виден насквозь) кадр с улыбкой не рисуем — у скул на светлом
    # фоне выходило тёмное пятно (фон кадра с улыбкой — чёрный)
    lay = np.dstack([out, a * 255])[Y0:Y1, X0:X1]
    return Image.fromarray(lay.astype(np.uint8), "RGBA"), [x, y, w, h]


def find_iris(big, cx, cy):
    """Центр радужки рядом с (cx, cy): самые тёмные точки в круге 9 px (кадр 360) — их середина."""
    a = np.asarray(big).astype(np.float32)[..., :3].mean(2)
    x0, y0, R = int((cx - 12) * K), int((cy - 9) * K), 9 * K
    win = a[y0:y0 + 18 * K, x0:x0 + 24 * K]
    thr = np.percentile(win, 12)
    ys, xs = np.nonzero(win <= thr)
    return (x0 + xs.mean()) / K, (y0 + ys.mean()) / K


def blank_eyes(big, eyes, D, rr=1.04):
    """Глаз без радужки: каждую строку её круга заполняем переходом между цветами по краям слева и справа — веко, белок
    и тени макияжа остаются как в этой строке (сплошной «белок» на тёмных тенях Лиры выходил серым пятном)."""
    arr = np.asarray(big).astype(np.float32).copy()
    for cx, cy in eyes:
        X, Y, r = cx * K, cy * K, D / 2 * K * rr
        for y in range(int(Y - r) - 1, int(Y + r) + 2):
            dy = y + 0.5 - Y
            if abs(dy) >= r:
                continue
            w = (r * r - dy * dy) ** 0.5
            xl, xr = int(np.floor(X - w)) - 1, int(np.ceil(X + w)) + 1
            cl, cr = arr[y, xl - 2:xl + 1, :3].mean(0), arr[y, xr:xr + 3, :3].mean(0)
            t = (np.arange(xr - xl + 1, dtype=np.float32) / (xr - xl))[:, None]
            arr[y, xl:xr + 1, :3] = cl * (1 - t) + cr * t
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGBA")


def build(name, who="lira"):
    W = WHO[who]
    LF.LIP_Y, LF.MOUTH_CX, LF.MOUTH_HALF = W["lip"]
    LF.MOUTH = W["mouth"]
    full, rgba = source(who, name)
    src = full.resize((512, 512), Image.LANCZOS)
    src.save(ROOT / f"data/avatars/{who}-{name}.webp", quality=90, method=6)
    # 21.11 (владелец: «качество ниже… грубоватые пиксели»): портрет режем из исходника 1024, а не из уменьшенного 512 —
    # меньше растягивания, чётче лицо и волосы
    k = full.width / 512
    crop = tuple(round(v * k) for v in W["crop"])
    big = matte_alpha(rgba, crop) if rgba is not None else matte(full, crop, W["light_hair"], f"{who}-{name}" in NECK_GAP)
    D = W["iris"]
    LF.IRIS, LF.IRIS_D = W["eyes"], D
    pre = f"{who}-{name}"
    # радужка-слой — с того же места портрета (в покое лицо в точности как на фото); под ней — «пустой» глаз (21.11, владелец:
    # «оригинальная Лира смотрит в разные стороны, моргает… на новых образах — статичность»): строки круга радужки — переходом
    # между цветами по краям (веко, белок, тень), так взгляд ходит по-настоящему, а моргание — веко на миг закрывает глаз
    for side, im in zip("lr", LF.iris_crops(big)):
        im.save(LIVE / f"{pre}-iris-{side}.png", optimize=True)
    blank_eyes(big, W["eyes"], D).resize((360, 360), Image.LANCZOS).save(LIVE / f"{pre}.webp", quality=94, method=6)
    # раскрытие рта — по WHO["open"] (владелец 21.11: «рот открывается плохо, хуже, чем у оригинальной Лиры»: лицо в образе
    # мельче, и 5,2 пикселя на портрете — едва щель)
    for i, op in enumerate(W["open"]):
        LF.mouth_layer(big, open_px=op).save(LIVE / f"{pre}-mouth-{i}.webp", quality=92, method=6)
    geo = {"eyes": [[round(x - D / 2, 1), round(y - D / 2, 1)] for x, y in W["eyes"]], "iris": D,
           "mouth": list(W["mouth"]), "moveX": 2.2, "moveY": 0.9}
    lay, box = smile_real(who, name, big)
    if lay is not None:                          # настоящая улыбка из кадра с улыбкой — своя рамка (низ лица)
        lay.save(LIVE / f"{pre}-smile.webp", quality=92, method=6)
        geo["smile"] = box
    else:                                        # кадра с улыбкой нет — образ без улыбки (слой — закрытый рот)
        LF.mouth_layer(big, smile_px=0.0).save(LIVE / f"{pre}-smile.webp", quality=92, method=6)
    return {"own": True, "soft": True, "iris": [f"{pre}-iris-l.png", f"{pre}-iris-r.png"], "geo": geo}


THUMB_BOX = (71, 40, 441, 410)                 # кружок выбора — одинаковый кадр у всех (голова и причёска) в портрете 512
THUMB = 112


def thumb(who, look=""):
    """Кружок для выбора образа — у всех образов и у обычного облика один кадр и один размер: ui/assets/live/thumbs/<имя>.webp."""
    name = f"{who}-{look}" if look else who
    W = WHO[who]
    rgba = source(who, look)[1] if look and (SRC / f"{who}-{look}.png").exists() else None
    if rgba is not None:
        big = matte_alpha(rgba, (0, 0, 1024, 1024))
    else:
        src = Image.open(ROOT / f"data/avatars/{name}.webp").convert("RGB").resize((512, 512), Image.LANCZOS)
        big = matte(src, (0, 0, 512, 512), W["light_hair"] and bool(look)) if look else matte(src, (0, 0, 512, 512), False)
    k = big.size[0] / 512
    out = big.crop(tuple(int(v * k) for v in THUMB_BOX)).resize((THUMB, THUMB), Image.LANCZOS)
    (LIVE / "thumbs").mkdir(exist_ok=True)
    out.save(LIVE / "thumbs" / f"{name}.webp", quality=88, method=6)


LOOKS = {"lira": ["home", "hair", "silk", "curls", "buns", "street", "tails", "ties", "cyber", "braid", "kolos", "bob", "bangs"], "patrik": ["suit", "home", "silver", "coat", "beard", "shirt"]}

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
