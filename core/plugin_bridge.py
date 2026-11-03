"""Мост своей страницы плагина — расширение (Creator, 03.11: «чтобы мы были не хуже DeepSeek Creator Mode»).

Страница плагина (ui.html) живёт во фрейме-песочнице студии без сети и без доступа к студии (ui/studio/plugpage.js);
всё, что ей можно, идёт через window.dewiar → студия → команды ядра. Здесь — то, что добавлено к run/settings/open/ask:

  store       — своё хранилище страницы: JSON в папке данных плагина (plugins.data_dir — переживает переустановку и
                правки словами), не больше STORE_MAX байт; ключ — до 80 знаков, значение null — удалить ключ;
  data(scope) — данные Лиры, только объявленные в plugin.json ("data": [...]) и только с разрешения человека: студия
                спрашивает при первом обращении, выбор хранится в settings.plugins.grants[id][scope] (True / False) и
                отзывается на странице плагина («Доступ»). Ядро проверяет разрешение ещё раз — студия не может обойти.
                Области: notes, reminders, money, chat_stats (сколько сообщений по дням и часам, с кем, частые слова —
                без текста), chat (текст переписки — отдельным разрешением);
  theme(vars) — плагин с "theme": true перекрашивает студию: только переменные из THEME_VARS и только цвета/градиенты
                (без url(), без выражений); хранится в settings.ui.plugin_theme, сбросить — «Оформление» → «Сбросить тему»;
  read_url    — текст статьи по адресу (читалка): только http(s), не при стоп-кране «Ничего не уходит в интернет»."""

import json
import re
import time
from collections import Counter
from datetime import datetime, timedelta

from plugins import DATA_SCOPES, data_dir

STORE_MAX = 512 * 1024
STORE_FILE = ".page-store.json"
THEME_VARS = ("--accent", "--brand", "--scene", "--ink", "--muted", "--dim", "--line", "--field", "--panel", "--panel2",
              "--good", "--bad", "--glass2", "--soft", "--soft2")
_THEME_OK = re.compile(r"^[#\w\s.,%()+\-/]{1,700}$")
_THEME_BAD = re.compile(r"url|image|element|expression|attr|import|javascript", re.I)


class BridgeError(Exception):
    pass


# ---------- хранилище страницы ----------
def _store_path(pid):
    return data_dir(pid) / STORE_FILE


def store_all(pid):
    try:
        d = json.loads(_store_path(pid).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def store_get(pid, key=None):
    d = store_all(pid)
    if key in (None, ""):
        return d
    return d.get(str(key)[:80])


def store_set(pid, key, value):
    """-> {ok, size}; больше STORE_MAX — BridgeError словами."""
    k = str(key or "").strip()[:80]
    if not k:
        raise BridgeError("у записи нет имени (ключа)")
    d = store_all(pid)
    if value is None:
        d.pop(k, None)
    else:
        d[k] = value
    raw = json.dumps(d, ensure_ascii=False)
    if len(raw.encode("utf-8")) > STORE_MAX:
        raise BridgeError(f"хранилище плагина переполнено (больше {STORE_MAX // 1024} КБ) — удалите старое")
    p = _store_path(pid)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(raw, encoding="utf-8")
    tmp.replace(p)
    return {"ok": True, "size": len(raw.encode("utf-8"))}


# ---------- разрешения ----------
def grants(s, pid):
    g = ((s.get("plugins", "grants") or {}).get(pid)) or {}
    return {k: bool(v) for k, v in g.items() if k in DATA_SCOPES}


def grant(s, P, pid, scope, on):
    p = P.items.get(pid)
    if not p:
        raise BridgeError("нет такого плагина")
    if scope not in p.get("data", []):
        raise BridgeError(f"плагин не просит доступ к «{scope}» (нет в plugin.json → data)")
    allg = dict(s.get("plugins", "grants") or {})
    g = dict(allg.get(pid) or {})
    if on is None:
        g.pop(scope, None)                       # «спросить снова»
    else:
        g[scope] = bool(on)
    allg[pid] = g
    s.update({"plugins": {"grants": None}})
    s.update({"plugins": {"grants": allg}})
    return grants(s, pid)


def forget(s, pid):
    allg = dict(s.get("plugins", "grants") or {})
    if allg.pop(pid, None) is not None:
        s.update({"plugins": {"grants": None}})
        s.update({"plugins": {"grants": allg}})


# ---------- данные Лиры ----------
_STOP = set("""это как что так вот где когда или если чтобы потом тоже очень можно нужно надо есть был была было были будет
этот эта эти того тебя меня мне тебе себя свой своя свои наши ваши который которая которые просто сейчас сегодня завтра
вчера давай сделай скажи покажи пожалуйста спасибо привет хорошо ладно лира лиру лире лирой dewiar почему зачем какой какая
расскажи расскажите подскажи подскажите напомни найди открой включи выключи поставь запиши посмотри можешь сможешь хочу
какие сколько много мало ещё еще уже только даже потому через после перед около между""".split())


def _words(text):
    return [w for w in re.findall(r"[а-яёa-z]{5,}", str(text or "").lower().replace("ё", "е")) if w not in _STOP]


def chat_stats(items, personas=None, days=60):
    """Статистика разговоров без текста: по дням (вы / ответы), по часам и дням недели, по персонажам, частые слова."""
    now = datetime.now()
    start = (now - timedelta(days=days - 1)).date()
    per_day = {(start + timedelta(days=i)).isoformat(): {"you": 0, "lira": 0} for i in range(days)}
    hours, week, who, words = [0] * 24, [0] * 7, Counter(), Counter()
    total = {"you": 0, "lira": 0, "voice": 0, "messenger": 0}
    first = None
    for x in items:
        try:
            dt = datetime.fromtimestamp(float(x.get("ts") or 0))
        except (TypeError, ValueError, OSError):
            continue
        first = dt if first is None or dt < first else first
        mine = x.get("role") == "user"
        total["you" if mine else "lira"] += 1
        if mine and x.get("via") == "message":
            total["messenger"] += 1
        key = dt.date().isoformat()
        if key in per_day:
            per_day[key]["you" if mine else "lira"] += 1
        if mine:
            hours[dt.hour] += 1
            week[dt.weekday()] += 1
            words.update(set(_words(x.get("text"))))
        else:
            who[x.get("who") or ""] += 1
    names = {}
    for pid in who:
        try:
            names[pid] = ((personas.get(pid) if personas is not None and pid else None) or {}).get("name") or pid or "Ассистент"
        except Exception:  # noqa: BLE001
            names[pid] = pid or "Ассистент"
    # серия дней подряд (до сегодня или вчера)
    active = {k for k, v in per_day.items() if v["you"] or v["lira"]}
    streak, d = 0, now.date()
    if d.isoformat() not in active:
        d -= timedelta(days=1)
    while d.isoformat() in active:
        streak += 1
        d -= timedelta(days=1)
    return {"days": [{"date": k, **v} for k, v in per_day.items()], "hours": hours,
            "weekdays": week, "personas": [{"id": k, "name": names[k], "count": n} for k, n in who.most_common(8)],
            "topics": [{"word": w, "count": n} for w, n in words.most_common(24) if n >= 2][:16],
            "total": total, "active_days": len(active), "streak": streak,
            "since": first.date().isoformat() if first else None}


def collect(h, scope):
    """Данные области scope из ядра h (Engine или подобное: chatlog, personas, reminders, money, workspace)."""
    if scope == "chat_stats":
        items = list(getattr(getattr(h, "chatlog", None), "items", []) or [])
        return chat_stats(items, getattr(h, "personas", None))
    if scope == "chat":
        items = list(getattr(getattr(h, "chatlog", None), "items", []) or [])[-400:]
        return {"items": [{"at": int(x.get("ts") or 0), "role": "you" if x.get("role") == "user" else "lira",
                           "who": x.get("who") or "", "text": str(x.get("text") or "")[:4000]} for x in items]}
    if scope == "reminders":
        R = getattr(h, "reminders", None)
        out = []
        for x in list(getattr(R, "items", []) or []):
            if x.get("kind") == "job" and not x.get("text"):
                continue
            out.append({"id": x.get("id"), "at": x.get("at"), "text": x.get("text"), "repeat": x.get("repeat"),
                        "kind": x.get("kind") or "reminder"})
        return {"items": out[:500]}
    if scope == "money":
        M = getattr(h, "money", None)
        rows = M.list() if M is not None else []
        keep = ("date", "amount", "currency", "category", "note", "kind")
        return {"items": [{k: x.get(k) for k in keep} for x in rows[:2000]]}
    if scope == "notes":
        W = getattr(h, "workspace", None)
        out = []
        try:
            for n in (W.notes(limit=200) if W is not None else [])[:200]:
                try:
                    from pathlib import Path
                    text = Path(n["path"]).read_text(encoding="utf-8", errors="replace")[:6000]
                except (OSError, KeyError):
                    text = n.get("snippet") or ""
                out.append({"title": n.get("title"), "folder": n.get("folder"), "at": int(n.get("mtime") or 0), "text": text})
        except Exception:  # noqa: BLE001
            pass
        return {"items": out}
    raise BridgeError("нет таких данных")


def data(s, P, h, pid, scope):
    p = P.items.get(pid)
    if not p:
        raise BridgeError("нет такого плагина")
    if scope not in DATA_SCOPES:
        raise BridgeError(f"нет таких данных: «{scope}»")
    if scope not in p.get("data", []):
        raise BridgeError(f"плагин не просит доступ к «{scope}» — добавьте его в plugin.json → data")
    if grants(s, pid).get(scope) is not True:
        raise BridgeError(f"человек не разрешил плагину доступ: {DATA_SCOPES[scope]}")
    return collect(h, scope)


# ---------- тема студии ----------
def clean_theme(vars_):
    """{--переменная: значение} -> только разрешённые переменные с безопасными значениями; mode — dark | light."""
    if not isinstance(vars_, dict):
        raise BridgeError("тема — это набор цветов {\"--accent\": \"#…\"}")
    out = {}
    for k, v in vars_.items():
        k = str(k).strip()
        if k == "mode":
            if v in ("dark", "light"):
                out["mode"] = v
            continue
        if k not in THEME_VARS:
            continue
        v = " ".join(str(v or "").split())
        if not v or not _THEME_OK.match(v) or _THEME_BAD.search(v):
            continue
        out[k] = v
    if not [k for k in out if k != "mode"]:
        raise BridgeError("в теме нет ни одного подходящего цвета (--accent, --brand, --scene, --ink, --panel…)")
    return out


def set_theme(s, P, pid, vars_):
    p = P.items.get(pid)
    if not p:
        raise BridgeError("нет такого плагина")
    if vars_ is None:
        s.update({"ui": {"plugin_theme": None}})
        return None
    if not p.get("theme"):
        raise BridgeError("этот плагин не может менять оформление (нет \"theme\": true в plugin.json)")
    t = {"id": pid, "name": p["name"], "vars": clean_theme(vars_), "at": int(time.time())}
    s.update({"ui": {"plugin_theme": None}})
    s.update({"ui": {"plugin_theme": t}})
    return t


# ---------- текст статьи по ссылке ----------
def read_url(s, url, get=None):
    """-> {url, title, text}. get(url) -> (html, content_type, final_url) — для проверок без сети."""
    url = str(url or "").strip()
    if not re.match(r"^https?://[^\s\"'<>]{3,2000}$", url):
        raise BridgeError("это не адрес страницы")
    if (s.get("privacy") or {}).get("local_only"):
        raise BridgeError("включён стоп-кран «Ничего не уходит в интернет» (студия → «Безопасность»)")
    from tools import html_to_text
    if get is None:
        import httpx
        from tools import UA
        try:
            r = httpx.get(url, headers=UA, timeout=15, follow_redirects=True)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise BridgeError(f"страница не открылась: {e}") from e
        page, ctype, final = r.text, r.headers.get("content-type", "html"), str(r.url)
    else:
        page, ctype, final = get(url)
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", page or "")
    import html as _h
    title = " ".join(_h.unescape(m.group(1)).split())[:200] if m else ""
    body = page
    art = re.search(r"(?is)<article\b.*?</article>", page or "")
    if art and len(art.group(0)) > 1500:
        body = art.group(0)                      # статья — без меню, подвала и рекламы вокруг
    text = html_to_text(body) if "html" in (ctype or "html") else str(page or "")
    return {"url": final, "title": title, "text": text[:200_000]}
