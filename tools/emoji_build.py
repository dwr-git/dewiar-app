"""Смайлы Dewiar (0.63; владелец 28.10: «смайлы в Близких и группах — ограниченное количество, не особо симпатичные»):
Fluent Emoji 3D (Microsoft, MIT — пакет @lobehub/fluent-emoji-3d) картинками 64 px и названия по-русски для поиска
(emojibase-data, MIT). Без оттенков кожи (их показываем основной картинкой) и без служебных «компонентов».

Запуск (пакеты — из npm, распакованные):
  python3 tools/emoji_build.py <fluent-emoji-3d/package> <emojibase-data/package>
Пишет ui/assets/emoji/img/<код>.webp, ui/assets/emoji/emoji-data.js (window.DEWIAR_EMOJI_DATA) и LICENSE.txt."""
import json, sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "ui/assets/emoji"
GROUPS = {0: "Смайлы", 1: "Люди", 3: "Природа", 4: "Еда", 5: "Места", 6: "Занятия", 7: "Предметы", 8: "Символы", 9: "Флаги"}


def main(fl, eb):
    fl, eb = Path(fl), Path(eb)
    have = {p.stem.replace("-fe0f", ""): p.stem for p in (fl / "assets").glob("*.webp")}   # без FE0F: «2764» и «2764-fe0f» — одно
    data = json.loads((eb / "ru/data.json").read_text(encoding="utf-8"))
    (OUT / "img").mkdir(parents=True, exist_ok=True)
    groups = {g: [] for g in GROUPS}
    n = 0
    for x in sorted(data, key=lambda x: x.get("order", 0)):
        g = x.get("group")
        if g not in GROUPS:
            continue
        hx = x["hexcode"].lower()
        key = hx.replace("-fe0f", "")
        src = have.get(key)
        if not src:
            continue
        dst = OUT / "img" / f"{key}.webp"
        if not dst.exists():
            Image.open(fl / "assets" / f"{src}.webp").convert("RGBA").resize((64, 64), Image.LANCZOS).save(dst, "WEBP", quality=80, method=6)
        groups[g].append([x["emoji"], key, x.get("label", ""), " ".join(x.get("tags") or [])])
        n += 1
    out = [[GROUPS[g], items] for g, items in groups.items() if items]
    (OUT / "emoji-data.js").write_text("/* Смайлы Fluent Emoji (Microsoft, MIT), названия — emojibase-data (MIT); собрано tools/emoji_build.py */\n"
                                       "window.DEWIAR_EMOJI_DATA = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    (OUT / "LICENSE.txt").write_text(
        "Картинки смайлов — Fluent Emoji, © Microsoft Corporation, лицензия MIT (https://github.com/microsoft/fluentui-emoji),\n"
        "пакет @lobehub/fluent-emoji-3d (MIT). Названия и группы — emojibase-data (MIT, https://emojibase.dev).\n", encoding="utf-8")
    print(f"смайлов: {n}, групп: {len(out)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
