"""«Что нового» после обновления (отзыв 13.10: «что было в обновлении — непонятно, пришлось догадываться»).
Текст — data/whatsnew.json, общий с телефоном (android/tools/build_apk.sh кладёт его в whatsnew.js): выпуски с версиями
компьютера (pc) и телефона (phone), у пункта — значок, заголовок, что это, как попробовать и где (where: pc, phone).
Студия показывает новое один раз (settings ui.news_seen), помощница при встрече говорит о нём одной фразой (ui.news_said)."""
import json

from settings import DATA_DIR

ANN_EVERY = 30 * 60                   # объявления для всех — раз в полчаса


def announcements(url, timeout=10):
    """Объявления для всех (cloud.php ?p=/news, без ключа; кабинет → «Новости», 24.10) -> [{id, title, text, level, link,
    link_label, img (полный адрес или ""), ts}], новые первыми. Нет связи — исключение (вызывающий молчит)."""
    import httpx
    from cloud import DEFAULT_URL, base_of
    base = base_of(url or DEFAULT_URL)
    r = httpx.get(base + "?p=/news", timeout=timeout)
    r.raise_for_status()
    out = []
    for i in r.json().get("items") or []:
        if isinstance(i, dict) and int(i.get("id") or 0) > 0:
            img = str(i.get("img") or "")
            out.append(dict(i, id=int(i["id"]), img=(base + "?p=" + img) if img.startswith("/news/img") else ""))
    return sorted(out, key=lambda x: -x["id"])


def ver_key(v):
    out = []
    for x in str(v or "").split(".")[:3]:
        try:
            out.append(int(x))
        except ValueError:
            out.append(0)
    return tuple(out + [0] * (3 - len(out)))


def load():
    try:
        d = json.loads((DATA_DIR / "whatsnew.json").read_text(encoding="utf-8"))
        return d if isinstance(d, list) else []
    except (OSError, ValueError):
        return []


def releases(frm, to, where="pc", limit=3):
    """Выпуски новее frm (пусто — любые) и не новее to — с пунктами для этой платформы, новые первыми, не больше limit."""
    out = []
    for r in load():
        v = r.get(where) or ""
        if not v or (frm and ver_key(v) <= ver_key(frm)) or ver_key(v) > ver_key(to):
            continue
        items = [i for i in r.get("items") or [] if where in (i.get("where") or ["pc", "phone"])]
        if items:
            out.append(dict(r, version=v, items=items))
    out.sort(key=lambda r: ver_key(r["version"]), reverse=True)
    return out[:limit]


def say_fact(rels):
    """Одной строкой для приветствия: «Dewiar обновился до 0.38.23. Новое: …»."""
    if not rels:
        return ""
    titles = [i["title"] for r in rels for i in r["items"] if "Что нового" not in i["title"]][:4]   # о самом окне — не вслух
    if not titles:
        return ""
    return (f"Dewiar обновился до {rels[0]['version']}. Новое: " + "; ".join(titles)
            + ". Скажи об этом одной-двумя фразами, своими словами; подробнее — в студии («Что нового»).")
