"""«Статьи» сайтов (0.93; владелец 12.11: «как такие сайты будут продвигаться в поисковиках… Лира пишет статьи на нужные
пользователю темы согласно его плану и тематике сайта… брать из Радара… даже если Радар не настроен — со стороны настройки
публикации незаметно активировать… черновик — корректировать на телефоне»).

Почему не автопилот: поисковики наказывают поток ИИ-текстов без пользы (Google — scaled content abuse, Яндекс —
«малополезный контент»), а все сайты живут на поддоменах dewiar.pro — общая репутация; за выдуманную цену или совет
отвечает бизнес. Поэтому: по умолчанию черновик → «Да» владельца (студия или телефон), «сразу» — только после AUTO_AFTER
одобренных и не чаще расписания; факты о деле — только с сайта, новости и цифры — только из материалов Радара со ссылками.

Где что: настройки — site["blog"] (conf); статьи — на сервере (sites.php: /sites/articles, /sites/article/save|set),
страницы /blog/ собирает сервер по шаблону dw-blog.html из sites_render. Здесь — план тем (plan), черновик (write: тема →
материалы Радара → модель → сервер → весточка), расписание (due/next_slot, тикает в Sites._loop), Радар без настройки
(radar_boost: миссия по сайту, источники ниши — модель предлагает, обход проверяет, неживые убираются)."""

import json
import logging
import re
import threading
import time
from datetime import datetime, timedelta

log = logging.getLogger("dewiar")

FREQ = {"2w": "раз в две недели", "week": "раз в неделю", "2pw": "два раза в неделю"}
GAP = {"2w": 13 * 86400, "week": 6 * 86400, "2pw": 2 * 86400}
LEN = {"short": (450, 700), "mid": (800, 1200), "long": (1300, 1800)}
AUTO_AFTER = 3                   # «публиковать сразу» — после стольких одобренных черновиков
PLAN_N = 12
DEFAULT = {"on": False, "plan": [], "freq": "week", "day": 1, "hour": 10, "mode": "ask", "avoid": "", "len": "mid",
           "approved": 0, "live": 0, "drafts": 0, "next": 0, "last": 0, "radar": False, "err": ""}


class BlogError(Exception):
    pass


def conf(site):
    b = dict(DEFAULT)
    b.update({k: v for k, v in (site.get("blog") or {}).items() if k in DEFAULT})
    return b


def clean_patch(p):
    """Что можно поменять из студии и голосом."""
    out = {}
    if "on" in p:
        out["on"] = bool(p["on"])
    if p.get("freq") in FREQ:
        out["freq"] = p["freq"]
    if str(p.get("day", "")).lstrip("-").isdigit():
        out["day"] = max(0, min(6, int(p["day"])))
    if str(p.get("hour", "")).isdigit():
        out["hour"] = max(6, min(22, int(p["hour"])))
    if p.get("mode") in ("ask", "auto"):
        out["mode"] = p["mode"]
    if p.get("len") in LEN:
        out["len"] = p["len"]
    if "avoid" in p:
        out["avoid"] = re.sub(r"\s+", " ", str(p["avoid"] or "")).strip()[:400]
    if isinstance(p.get("plan"), list):
        out["plan"] = clean_plan(p["plan"])
    return out


def clean_plan(items):
    seen, out = set(), []
    for x in items:
        t = re.sub(r"\s+", " ", str(x.get("t") if isinstance(x, dict) else x or "")).strip(" .;-—")[:140]
        if len(t) < 6 or t.lower() in seen:
            continue
        seen.add(t.lower())
        out.append({"t": t, "done": int(x.get("done") or 0) if isinstance(x, dict) else 0})
    return out[:40]


def next_slot(b, now=None):
    """Когда писать следующий черновик: ближайший выбранный день недели и час, не раньше GAP после прошлого."""
    now = time.time() if now is None else now
    days = {int(b.get("day", 1))} if b.get("freq") != "2pw" else {int(b.get("day", 1)), (int(b.get("day", 1)) + 3) % 7}
    after = max(now, float(b.get("last") or 0) + GAP.get(b.get("freq"), GAP["week"]))
    d0 = datetime.fromtimestamp(now).replace(hour=int(b.get("hour", 10)), minute=0, second=0, microsecond=0)
    for k in range(0, 40):
        d = d0 + timedelta(days=k)
        if d.weekday() in days and d.timestamp() > after:
            return int(d.timestamp())
    return int(after)


def _json(text):
    t = re.sub(r"(?is)<think>.*?</think>", "", str(text or "")).strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```\s*$", "", t)
    a, b = t.find("{"), t.rfind("}")
    a2, b2 = t.find("["), t.rfind("]")
    for x, y in ((a, b), (a2, b2)):
        if x >= 0 and y > x:
            try:
                return json.loads(t[x:y + 1])
            except ValueError:
                continue
    return None


# ------------------------------------------------------------ Радар ------------------------------------------------------------
def radar_of(W):
    try:
        import engine_insight as EI
        return EI.radar(W.host) if W.host is not None else None
    except Exception:  # noqa: BLE001
        return None


def materials(W, topic, limit=8):
    """Материалы Радара к теме (по словам темы; нет — самое сильное за две недели). -> [{n, title, url, source, summary}]."""
    r = radar_of(W)
    if r is None:
        return []
    import insight as I
    items = [x for x in r.st.items() if x.get("a") and (x.get("ts") or x.get("seen") or 0) >= time.time() - 21 * 86400]
    ctx = I.ask_context(items, [], None, None, topic, limit)
    rows = ctx["items"] or (I.ask_context(items, [], None, None, "", 4)["items"] if items else [])
    return [{"n": i + 1, "title": x["title"], "url": x.get("url") or "", "source": x.get("source") or "", "summary": x.get("summary") or ""}
            for i, x in enumerate(rows)]


def radar_boost(W, s, wait=False):
    """Радар без настройки: включен ли, есть ли миссия и источники. Нет миссии — по сайту; нет источников — модель
    предлагает открытые источники ниши, обход их проверяет, неживые (ошибка или пусто) убираются. -> что сделали."""
    r = radar_of(W)
    if r is None:
        return {}
    done = {}
    c = r.conf()
    if not c.get("on", True):
        r.set_conf({"on": True})
        done["on"] = True
    if not str(c.get("mission") or "").strip():
        r.set_conf({"mission": f"Ниша сайта «{s.get('name')}»: {s.get('tagline') or ''}. Новости, идеи и вопросы клиентов — для статей блога сайта."[:600]})
        done["mission"] = True
    if [x for x in r.st.sources() if x.get("on", True)]:
        return done
    try:
        raw = W.llm(*suggest_prompt(s), max_tokens=900)
    except Exception as e:  # noqa: BLE001
        log.info("Статьи: источники для Радара — модель не ответила: %s", e)
        return done
    links = [str(x.get("url") if isinstance(x, dict) else x).strip() for x in (_json(raw) or []) if x][:10]
    added, _bad, _why = r.st.add_sources("\n".join(links))
    for a in added:
        r.st.update_source(a["id"], auto="blog")
    done["sources"] = len(added)

    def check():
        for a in added:
            src = next((x for x in r.st.sources() if x["id"] == a["id"]), None)
            if not src:
                continue
            try:
                n = r.crawl_source(src)
                fresh = next((x for x in r.st.sources() if x["id"] == a["id"]), {})
                if not fresh.get("found"):
                    raise ValueError("пусто")
                r.st.update_source(a["id"], last=int(time.time()), err="", last_new=n)
            except Exception as e:  # noqa: BLE001
                log.info("Статьи: источник %s не живой (%s) — убран", src.get("url"), e)
                r.st.remove_source(a["id"])
        try:
            r.tick(True)
        except Exception:  # noqa: BLE001
            pass
    if wait:
        check()
    else:
        threading.Thread(target=check, name="blog-radar", daemon=True).start()
    return done


def suggest_prompt(s):
    ct = s.get("contacts") or {}
    system = ("Ты подбираешь источники для Радара — Лира будет читать их и брать оттуда новости и идеи для статей блога сайта. "
              "Предложи 6–10 ОТКРЫТЫХ источников по нише: RSS-ленты и разделы известных сайтов со статьями, открытые Telegram-каналы "
              "(@имя), YouTube-каналы, тематические разделы Хабра или vc.ru, если подходят. Только реально существующие и известные "
              "тебе, на языке аудитории сайта; лучше меньше, но живые. Без соцсетей с входом, без закрытых каналов. "
              "Ответ — только JSON-массив: [{\"url\": \"…\", \"why\": \"…\"}].")
    user = f"Сайт: «{s.get('name')}» — {s.get('tagline') or ''}. Город/адрес: {ct.get('address') or '—'}."
    return system, user


# ------------------------------------------------------------ план ------------------------------------------------------------
def plan_prompt(s, b, mats, have):
    import sites as S
    kb = S.chat_knowledge(s)
    system = ("Ты — редактор блога малого бизнеса. Составь план статей для сайта: темы, которые реально ищут клиенты этого дела в "
              "поиске, — «как выбрать…», «сколько стоит и от чего зависит…», «что делать, если…», «чем отличается…», сезонные и местные "
              "вопросы, разборы новостей ниши. Каждая тема — готовый заголовок до 90 знаков, понятный человеку, без кликбейта и без "
              "перечня ключевых слов. Не обещай цен, скидок и гарантий. Темы разные, не повторяй уже написанные. "
              f"Ответ — только JSON-массив из {PLAN_N} строк.")
    user = (f"Сегодня {datetime.now():%Y-%m-%d} — темы о настоящем и будущем, без устаревших годов.\nСайт: {kb['brief']}\n\nЧто есть на сайте:\n{kb['kb'][:3500]}\n\n"
            + (f"Свежие материалы ниши (из Радара):\n" + "\n".join(f"- {m['title']}: {m['summary'][:160]}" for m in mats[:8]) + "\n\n" if mats else "")
            + (f"Уже написаны или в плане: {'; '.join(have[:30])}\n" if have else "")
            + (f"Не писать о: {b['avoid']}\n" if b.get("avoid") else ""))
    return system, user


def make_plan(W, sid, more=False):
    s = W.get(sid)
    b = conf(s)
    have = [x["t"] for x in b["plan"]]
    mats = materials(W, s.get("tagline") or s.get("name") or "")
    topics = _json(W.llm(*plan_prompt(s, b, mats, have), max_tokens=1200))
    if not isinstance(topics, list):
        raise BlogError("модель не составила план — попробуйте ещё раз")
    fresh = clean_plan([{"t": t} for t in topics if isinstance(t, str)])
    plan = clean_plan(b["plan"] + fresh) if more else clean_plan([x for x in b["plan"] if x.get("done")] + fresh)
    W.blog_save_conf(sid, {"plan": plan})
    return plan


# ------------------------------------------------------------ черновик ------------------------------------------------------------
def write_prompt(s, b, topic, mats):
    import sites as S
    kb = S.chat_knowledge(s)
    lo, hi = LEN.get(b.get("len"), LEN["mid"])
    system = (f"Ты пишешь статью для блога сайта «{s.get('name')}». Пиши по-русски, живо и по делу, как опытный человек из этой "
              "сферы говорит с клиентом. Правила:\n"
              "- Польза: ответь на вопрос из темы конкретно — шаги, примеры, на что смотреть, частые ошибки. Без воды и общих фраз "
              "(«в современном мире», «не секрет, что»).\n"
              "- Факты о самом деле (услуги, цены, адрес, часы) — ТОЛЬКО из «Данных сайта». Ничего не придумывай: ни цен, ни скидок, ни "
              "отзывов, ни людей, ни наград, ни гарантий, ни сроков.\n"
              "- Новости, цифры и даты из мира — только из «Материалов», с пометкой [n]. Материалов нет — без конкретных цифр и дат.\n"
              "- Здоровье, право, деньги — осторожно: общее знание и совет обратиться к специалисту, без диагнозов и обещаний.\n"
              "- Без кликбейта, без перечня ключевых слов, без «Заключение» в конце.\n"
              "- В конце — короткий абзац, чем может помочь это дело, и спокойное приглашение связаться.\n"
              f"- Объём {lo}–{hi} слов. Разметка: «## » подзаголовки (3–6), списки «- », **жирный** — редко. Без заголовка статьи в тексте.\n"
              "Ответ — только JSON: {\"title\": \"заголовок до 90 знаков\", \"descr\": \"описание для поиска, 120–160 знаков\", "
              "\"body\": \"текст с разметкой\", \"refs\": [номера использованных материалов], "
              "\"ask\": \"1–2 коротких вопроса владельцу: что добавить из его опыта, чтобы статья стала живой\"}")
    user = (f"Сегодня {datetime.now():%Y-%m-%d}: «в этом году» — это {datetime.now():%Y}; свои знания о мире могут быть устаревшими — "
            f"новое бери из материалов.\nТема: {topic}\n\nДанные сайта: {kb['brief']}\n{kb['kb'][:5000]}\n\n"
            + ("Материалы:\n" + "\n".join(f"[{m['n']}] {m['source']} — {m['title']}: {m['summary']}" for m in mats) + "\n\n" if mats else "Материалов нет.\n\n")
            + (f"Не писать о: {b['avoid']}\n" if b.get("avoid") else ""))
    return system, user


def parse_article(raw, mats):
    d = _json(raw)
    if not isinstance(d, dict):
        raise BlogError("модель не написала статью — попробуйте ещё раз")
    title = re.sub(r"\s+", " ", str(d.get("title") or "")).strip(" «»\"")[:200]
    body = str(d.get("body") or "").replace("\r", "").strip()
    body = re.sub(r"^#\s+.+\n+", "", body)                       # заголовок статьи — отдельно
    if len(title) < 3 or len(body) < 300:
        raise BlogError("статья вышла пустой — попробуйте ещё раз")
    used = {int(n) for n in (d.get("refs") or []) if str(n).isdigit()} | {int(n) for n in re.findall(r"\[(\d{1,2})\]", body)}
    refs = [{"title": m["title"], "url": m["url"]} for m in mats if m["n"] in used and m.get("url")]
    body = re.sub(r"\s?\[(\d{1,2})\]", "", body)                  # [n] — в «Источники» внизу, в тексте — без скобок
    descr = re.sub(r"\s+", " ", str(d.get("descr") or "")).strip()[:300]
    return {"title": title, "descr": descr, "body": body, "refs": refs, "ask": str(d.get("ask") or "").strip()[:600]}


def write(W, sid, topic=""):
    """Черновик статьи: тема (своя или следующая из плана), материалы Радара, модель → на сервер черновиком (или сразу,
    если «публиковать сразу» уже открыто), весточка владельцу. -> статья с сервера."""
    s = W.get(sid)
    name = (s.get("published") or {}).get("name")
    if not name:
        raise BlogError("сначала опубликуйте сайт — статьи живут на нём")
    b = conf(s)
    pi = None
    if not topic:
        pi = next((i for i, x in enumerate(b["plan"]) if not x.get("done")), None)
        if pi is None:
            b["plan"] = make_plan(W, sid, more=True)
            pi = next((i for i, x in enumerate(b["plan"]) if not x.get("done")), None)
        if pi is None:
            raise BlogError("в плане нет новых тем — добавьте свою")
        topic = b["plan"][pi]["t"]
    mats = materials(W, topic)
    art = parse_article(W.llm(*write_prompt(s, b, topic, mats), max_tokens=4200), mats)
    auto = b["mode"] == "auto" and b["approved"] >= AUTO_AFTER
    d = W._fetch("/sites/article/save", dict(art, name=name, topic=topic, src="lira", status="live" if auto else "draft"), timeout=40)
    a = d.get("article") or {}
    s = W.get(sid)
    b = conf(s)
    if pi is not None and pi < len(b["plan"]) and b["plan"][pi]["t"] == topic:
        b["plan"][pi]["done"] = int(a.get("id") or 1)
    now = int(time.time())                               # написали (по расписанию или «сейчас») — следующий от этого
    W.blog_save_conf(sid, {"plan": b["plan"], "last": now, "err": "", "next": next_slot(dict(b, last=now), now) if b["on"] else 0})
    if W.host is not None:
        try:
            if auto:
                W.host.push("📝 Статья на сайте", f"«{a.get('title')}» — {a.get('url')}", quiet=True)
            else:
                W.host.push("📝 Черновик статьи", f"«{a.get('title')}» — посмотрите и опубликуйте: в студии («Сайты» → «Статьи») "
                            "или в приложении на телефоне", quiet=False, open="sites-blog:" + sid, head=a.get("title"),
                            body="Черновик для " + str(name) + ".dewiar.pro — прочитайте, поправьте и нажмите «Опубликовать». Удобно и с телефона.")
        except Exception:  # noqa: BLE001
            pass
    sync(W, sid)
    return a


def sync(W, sid):
    """Счётчики со статей на сервере: опубликовано, черновиков, одобрено. Первая опубликованная — пересобрать сайт (пункт
    меню «Статьи»). -> список статей."""
    s = W.get(sid)
    name = (s.get("published") or {}).get("name")
    if not name:
        return []
    arts = W._fetch("/sites/articles", {"name": name}, timeout=20).get("articles") or []
    live = sum(1 for a in arts if a["status"] == "live")
    drafts = sum(1 for a in arts if a["status"] == "draft")
    b = conf(s)
    patch = {"live": live, "drafts": drafts}
    W.blog_save_conf(sid, patch)
    if (b["live"] == 0) != (live == 0):                              # меню «Статьи» появилось или ушло — обновить сайт
        try:
            W.publish(sid)
        except Exception as e:  # noqa: BLE001
            log.info("Статьи: пункт меню — сайт не обновился: %s", e)
    return arts


def set_status(W, sid, aid, status):
    s = W.get(sid)
    d = W._fetch("/sites/article/set", {"id": int(aid), "status": status}, timeout=30)
    if status == "live":
        W.blog_save_conf(sid, {"approved": conf(W.get(sid))["approved"] + 1})
    sync(W, sid)
    return d.get("article")


def due(W):
    """Из фонового цикла «Сайтов»: пора — пишем черновик (по одному сайту за раз)."""
    now = time.time()
    for sid in W.ids():
        try:
            s = W.get(sid)
        except Exception:  # noqa: BLE001
            continue
        b = conf(s)
        if not b["on"] or not (s.get("published") or {}).get("name"):
            continue
        if now - float((s.get("blog") or {}).get("synced") or 0) > 1800:   # раз в полчаса — что опубликовали с телефона
            try:
                sync(W, sid)
            except Exception:  # noqa: BLE001
                pass
            W.blog_save_conf(sid, {"synced": int(now)})
            b = conf(W.get(sid))
        if not b["next"]:
            W.blog_save_conf(sid, {"next": next_slot(b, now)})
            continue
        if now < b["next"]:
            continue
        if b["drafts"] >= 3 and b["mode"] == "ask":                   # три черновика ждут «Да» — не копим, ждём
            W.blog_save_conf(sid, {"next": next_slot(dict(b, last=now), now)})
            continue
        try:
            write(W, sid)
        except Exception as e:  # noqa: BLE001
            log.info("Статьи: черновик не написан: %s", e)
            W.blog_save_conf(sid, {"err": str(e)[:200]})
        W.blog_save_conf(sid, {"next": next_slot(dict(conf(W.get(sid)), last=time.time()), time.time())})
        return


def fix(W, aid, text):
    """«Попросить Лиру поправить» (студия; на телефоне — так же своей моделью): просьба владельца своими словами — модель
    переписывает, факты и разметку сохраняет. -> статья с сервера (черновик или опубликованная — как была)."""
    if not text:
        raise BlogError("напишите, что поправить")
    a = W._fetch("/sites/article", {"id": int(aid)}).get("article") or {}
    system = ("Ты правишь статью для блога сайта по просьбе владельца. Сделай ровно то, о чём просят; остальное оставь как есть. "
              "Факты о деле не придумывай; разметку сохрани (## подзаголовки, «- » списки). Если владелец пишет о своём опыте — "
              "вплети это в текст его словами. Ответ — только JSON: {\"title\": \"…\", \"descr\": \"…\", \"body\": \"…\"}")
    user = f"Просьба владельца: {text}\n\nЗаголовок: {a.get('title')}\nОписание: {a.get('descr')}\n\nТекст:\n{a.get('body')}"
    d = _json(W.llm(system, user, max_tokens=4200))
    if not isinstance(d, dict) or len(str(d.get("body") or "")) < 200:
        raise BlogError("модель не справилась — попробуйте сказать иначе")
    out = W._fetch("/sites/article/save", {"id": int(aid), "title": str(d.get("title") or a.get("title"))[:200],
                                           "descr": str(d.get("descr") or a.get("descr") or "")[:300], "body": str(d["body"])})
    return out.get("article")
