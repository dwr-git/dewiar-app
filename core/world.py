"""«Интересное в мире» (владелец 14.11: «что действительно интересное и необычное в мире происходит, от Лиры кратко
услышать с возможностью перейти для полного прочтения… у всех разные вкусы — это бы придумать как решить»).

Сервер собирает ОДИН общий выпуск на всех (исполнитель облака, core/cloudrunner.WorldJob, раз в ~12 часов): читает
подборку лент (науки, космоса, технологий, природы, культуры…), модель выбирает до 14 по-настоящему любопытных материалов
и раскладывает их по темам с оценкой «насколько интересно широкому кругу». Без политики, войн, преступлений, катастроф,
смертей, рекламы и сплетен. Выпуск лежит на сайте (?p=/world) — без входа и без данных человека.

Вкус — на самом телефоне (android/assets/www/app.js, world*): выбранные темы, «👍 Интересно» / «👎 Не моё» под карточкой
и намёки из памяти («люблю космос») двигают веса тем; из выпуска выбирается одна лучшая для этого человека новость,
которую он ещё не видел. Сервер про вкусы не знает ничего.

Здесь — чистая логика без сети: collect (ленты -> кандидаты), pick_prompt / parse_pick (модель -> материалы), digest."""
import hashlib
import json
import re
import time

import insight as I

TOPICS = [("science", "Наука", "Science"), ("space", "Космос", "Space"), ("tech", "Технологии", "Tech"), ("ai", "ИИ", "AI"),
          ("health", "Здоровье", "Health"), ("nature", "Природа и животные", "Nature & animals"),
          ("culture", "Кино, книги, музыка", "Movies, books, music"), ("money", "Деньги", "Money"), ("travel", "Путешествия", "Travel"),
          ("food", "Еда", "Food"), ("sport", "Спорт", "Sport"), ("curious", "Необычное", "Curious")]
TOPIC_IDS = [t[0] for t in TOPICS]
SOURCES = {
    "ru": ["https://nplus1.ru/rss", "https://naked-science.ru/feed", "https://elementy.ru/rss/news", "https://habr.com/ru/rss/news/?fl=ru",
           "https://3dnews.ru/news/rss/", "https://www.ixbt.com/export/news.rss", "https://lifehacker.ru/feed/",
           "https://www.techinsider.ru/rss/", "https://www.championat.com/rss/news/"],
    "en": ["https://www.sciencedaily.com/rss/top.xml", "https://www.nasa.gov/feed/", "https://www.theverge.com/rss/index.xml",
           "https://feeds.arstechnica.com/arstechnica/index", "https://www.smithsonianmag.com/rss/latest_articles/",
           "https://www.newscientist.com/feed/home/", "https://www.atlasobscura.com/feeds/latest", "https://lifehacker.com/feed/rss"],
}
# политику, войны, преступления и беды отсекаем ещё до модели (модель тоже просят — это страховка)
STOP = re.compile(r"выбор|депутат|парламент|президент|санкци|войн|военн|ракет|обстрел|удар[аы]? по|теракт|убий|погиб|жертв|катастроф|"
                  r"авари|пожар|землетряс|арест|суд\b|приговор|election|parliament|president|sanction|\bwar\b|military|missile|"
                  r"attack|killed|dead\b|death|crash|shooting|arrest|court", re.I)
MAX_ITEMS = 14
HOURS = 36


def item_id(url, title=""):
    return hashlib.sha1((I.norm_link(url) or title).encode("utf-8", "replace")).hexdigest()[:12]


def collect(fetch, sources, now=None, hours=HOURS, per_source=25, limit=140):
    """Ленты -> кандидаты [{n, title, url, source, text}] за последние hours часов; источник не открылся — пропускаем.
    -> (кандидаты, ошибки по источникам)."""
    now = now or time.time()
    seen, out, errs = set(), [], {}
    for src in sources:
        try:
            page = fetch(src)
            items = I.parse_feed(page, src)
        except Exception as e:  # noqa: BLE001 — один сломанный источник не мешает остальным
            errs[src] = str(e)[:160]
            continue
        host = re.sub(r"^www\.", "", re.sub(r"^https?://([^/]+).*$", r"\1", src))
        for x in items[:per_source]:
            url, title = str(x.get("url") or ""), re.sub(r"\s+", " ", str(x.get("title") or "")).strip()
            ts = int(x.get("ts") or 0)
            if not url or not title or (ts and ts < now - hours * 3600) or STOP.search(title):
                continue
            k = I.norm_link(url) or title.lower()
            if k in seen:
                continue
            seen.add(k)
            out.append({"title": title[:200], "url": url, "source": host, "ts": ts,
                        "text": re.sub(r"\s+", " ", I._strip_tags(str(x.get("text") or "")))[:280]})
    out.sort(key=lambda x: -(x["ts"] or 0))
    out = out[:limit]
    for i, x in enumerate(out):
        x["n"] = i + 1
    return out, errs


def pick_prompt(cands, lang="ru"):
    en = (lang or "ru").startswith("en")
    topics = ", ".join(t[0] for t in TOPICS)
    rows = "\n".join(f"[{x['n']}] {x['source']} — {x['title']}" + (f": {x['text'][:200]}" if x.get("text") else "") for x in cands)
    if en:
        system = ("You pick the day's most interesting news for a wide audience — the kind a friend would tell over coffee: "
                  "surprising discoveries, space, clever tech, nature, useful findings, curious facts. "
                  "NEVER pick: politics, elections, wars, military, crime, disasters, deaths, accidents, ads, sales, celebrity gossip, "
                  "stock tips. Pick up to 14, spread across topics. Answer ONLY a JSON array, each element: "
                  '{"n": source number, "topic": one of [' + topics + '], "title": a short catchy title in English (up to 80 chars, '
                  'no clickbait), "text": 1–2 sentences — what happened and why it is interesting, "score": 1–10 how interesting '
                  "for most people (10 — everyone will talk about it)}.")
    else:
        system = ("Ты выбираешь самые интересные новости дня для широкого круга — то, что друг расскажет за чашкой чая: "
                  "удивительные открытия, космос, умная техника, природа, полезные находки, любопытные факты. "
                  "НИКОГДА не бери: политику, выборы, войны, военное, преступления, катастрофы, смерти, аварии, рекламу, скидки, "
                  "сплетни о знаменитостях, советы по акциям. Выбери до 14, разных тем. Ответ — ТОЛЬКО массив JSON, элемент: "
                  '{"n": номер источника, "topic": одна из [' + topics + '], "title": короткий живой заголовок по-русски (до 80 '
                  'знаков, без кликбейта), "text": 1–2 предложения — что случилось и чем интересно, "score": 1–10 насколько интересно '
                  "большинству (10 — об этом будут говорить все)}.")
    return system, (I.today_line(lang) + "\n\n" + (rows or "—"))


def parse_pick(raw, cands):
    """Ответ модели -> материалы выпуска: только существующие номера, темы из списка, без повторов; сильнее — первыми."""
    text = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.S)
    m = re.search(r"\[.*\]", text, flags=re.S)
    try:
        arr = json.loads(m.group(0)) if m else []
    except (ValueError, TypeError):
        arr = []
    by = {x["n"]: x for x in cands}
    out, used = [], set()
    for a in arr if isinstance(arr, list) else []:
        if not isinstance(a, dict):
            continue
        try:
            n = int(a.get("n"))
            score = max(1.0, min(10.0, float(a.get("score") or 0)))
        except (TypeError, ValueError):
            continue
        c = by.get(n)
        topic = str(a.get("topic") or "").strip().lower()
        title = re.sub(r"\s+", " ", str(a.get("title") or "")).strip()[:100] or (c or {}).get("title", "")[:100]
        txt = re.sub(r"\s+", " ", str(a.get("text") or "")).strip()[:320]
        if not c or n in used or topic not in TOPIC_IDS or not title:
            continue
        used.add(n)
        out.append({"id": item_id(c["url"], c["title"]), "topic": topic, "title": title, "text": txt, "url": c["url"],
                    "source": c["source"], "score": round(score, 1)})
    out.sort(key=lambda x: -x["score"])
    return out[:MAX_ITEMS]


def digest(fetch, ask, lang="ru", sources=None, now=None):
    """Весь выпуск: ленты -> кандидаты -> модель -> {lang, at, items, errs}. ask(system, user) -> текст ответа модели."""
    cands, errs = collect(fetch, sources or SOURCES.get(lang) or SOURCES["ru"], now)
    if len(cands) < 5:
        return {"lang": lang, "at": int(now or time.time()), "items": [], "errs": errs, "note": "мало материалов"}
    items = parse_pick(ask(*pick_prompt(cands, lang)), cands)
    return {"lang": lang, "at": int(now or time.time()), "items": items, "errs": errs}
