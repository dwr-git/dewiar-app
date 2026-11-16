"""Действия модели: «Сайты» (сделать, переделать фразой, показать, опубликовать, статьи, оценка) и плагины
(включить, сделать, изменить)."""

import os
import time

from tools_base import log, ToolError
import tools_base as base          # launch — через основу: проверки подменяют их там


def _sites(ctx):
    s = ctx.get("sites")
    if s is None:
        raise ToolError("«Сайты» выключены — студия → «Возможности» → «Сайты»")
    return s


def _site_open(S, sid):
    """Собрать сайт в папку и открыть в браузере (с диска)."""
    f = S.export(sid)
    base.launch(["xdg-open", str(f)])
    return f


def _eyes(ctx, path, goal):
    """Посмотреть на результат глазами (engine.eyes_page) -> строка для модели («Посмотрела: …») или ""."""
    f = ctx.get("eyes")
    if not callable(f) or not path:
        return ""
    try:
        bad = f(str(path), goal)
    except Exception:  # noqa: BLE001
        return ""
    return (f" ПОСМОТРЕЛА НА РЕЗУЛЬТАТ (снимок экрана телефона): {bad}. Скажи об этом человеку и сразу поправь — "
            "это недоработка, а не вкус.") if bad else ""


def t_site_create(a, ctx):
    """«Сделай сайт для моей кофейни на Садовой, 5…» — шаблон по делу, тексты под человека, сразу открыть."""
    from sites import SiteError
    S = _sites(ctx)
    ct = {k: a[k] for k in ("phone", "email", "address", "hours", "telegram", "whatsapp", "vk") if str(a.get(k) or "").strip()}
    describe = str(a.get("describe") or "").strip()
    if not describe and not a.get("name") and not a.get("ref"):
        raise ToolError("Спроси одной фразой, для чего сайт: чем занимается человек и как называется дело.")
    try:
        s = S.create(a.get("kind") or "", describe, a.get("name") or "", a.get("tagline") or "", ct, ref=str(a.get("ref") or ""))
        page = _site_open(S, s["id"])
    except SiteError as e:
        raise ToolError(str(e)) from e
    import sites_kit as K
    blocks = [K.BLOCKS[b["type"]]["title"] for b in s["pages"][0]["blocks"]]
    miss = [w for k, w in (("phone", "телефон"), ("address", "адрес"), ("hours", "часы работы")) if not (s.get("contacts") or {}).get(k)]
    note = s.get("_note") or ""
    return (f"Сайт «{s['name']}» готов (дизайн «{K.TEMPLATES[s['template']]['title']}», разделы: {', '.join(blocks)}) и открыт в браузере; "
            f"редактор — студия → «Сайты». {('Заметка: ' + note + '. ') if note else ''}"
            "Скажи одной-двумя фразами, что получилось, и предложи: поменять что угодно одной фразой (цвета, шрифт, разделы, "
            "«другой дизайн»), прислать фото и цены" + (f", назвать {', '.join(miss)}" if miss else "") + ", а когда понравится — опубликовать на "
            "dewiar.pro под своим именем. Отзывы и людей не выдумывай." + _eyes(ctx, page, describe or s.get("name") or ""))


def t_site_edit(a, ctx):
    """Любая правка фразой: «сделай шапку тёмной», «добавь цены», «другой дизайн целиком», «верни как было»."""
    from sites import SiteError
    S = _sites(ctx)
    try:
        sid = S.find(a.get("site") or "")
        r = S.say(sid, str(a.get("request") or "").strip() or "верни как было")
        page = S.export(sid)
        if a.get("show"):
            _site_open(S, sid)
    except SiteError as e:
        raise ToolError(str(e)) from e
    pub = (r["site"].get("published") or {}).get("url")
    return (f"{r['said']} Сайт «{r['site']['name']}»: в студии → «Сайты» видно сразу" + (", в открытом браузере — обновите страницу" if not a.get("show") else ", открыла в браузере")
            + (f". На {pub} изменения появятся после «опубликуй ещё раз»" if pub else "") + ". Скажи это коротко; отменить — «верни как было»."
            + _eyes(ctx, page, str(a.get("request") or "")))


def t_site_show(a, ctx):
    from sites import SiteError
    S = _sites(ctx)
    items = S.list()
    if not items:
        return "Сайтов пока нет. Предложи сделать: спроси, чем человек занимается."
    try:
        sid = S.find(a.get("site") or "")
        if not a.get("zip"):
            _site_open(S, sid)
    except SiteError as e:
        raise ToolError(str(e)) from e
    s = S.get(sid)
    if a.get("zip"):                                  # 15.11: сайт на свой хостинг и домен — тот же архив, что в студии
        out = S.export_zip(sid)
        if not os.environ.get("DEWIAR_DRY_TOOLS"):
            import export as X
            X.reveal(out)
        return (f"Архив сайта «{s['name']}» — {out.name} в «Загрузках» (открыла папку). Скажи коротко: файлы архива положить в корень "
                "сайта на хостинге (public_html), домен направить на хостинг у регистратора; внутри — «КАК-ПОСТАВИТЬ.txt». "
                + ("Заявки с формы придут в «Клиенты», пока сайт опубликован в Dewiar." if (s.get("published") or {}).get("url")
                   else "Форма заявки заработает, если сайт опубликовать в Dewiar и скачать архив снова."))
    others = [x["name"] for x in items if x["id"] != sid]
    pub = (s.get("published") or {})
    return (f"Открыла сайт «{s['name']}» в браузере" + (f" (в интернете: {pub.get('url')}" + (", ЗАБЛОКИРОВАН администратором: " + pub.get("reason", "") if pub.get("status") == "blocked" else "") + ")" if pub.get("url") else ", он ещё не опубликован")
            + (f". Другие сайты: {', '.join(others)}" if others else "") + ". Скажи это одной фразой.")


def t_site_publish(a, ctx):
    from sites import SiteError, name_problem
    S = _sites(ctx)
    try:
        sid = S.find(a.get("site") or "")
        n = str(a.get("name") or "").strip().lower() or S.suggest_name(sid)
        p = name_problem(n)
        if p:
            raise ToolError(f"Имя «{n}» не подходит: {p}. Предложи человеку 2–3 имени латиницей и спроси, какое взять.")
        chk = S.check_name(n, sid)
        if not chk.get("free"):
            raise ToolError(f"Адрес {n}.dewiar.pro уже занят. Предложи другие имена латиницей (с городом, с дефисом) и спроси.")
        s = S.publish(sid, n)
    except SiteError as e:
        raise ToolError(str(e)) from e
    if not ((s["published"] or {}).get("reach") or {"ok": True}).get("ok"):
        from sites import REACH_SAY
        return (REACH_SAY.format(url=s["published"]["url"]) + " Скажи человеку именно это — не говори, что сайт уже открывается; "
                "ссылку пока не предлагай отправлять клиентам.")
    return (f"Сайт «{s['name']}» опубликован: {s['published']['url']} — открывается у всех, с телефона тоже. Заявки с формы придут в «Клиенты», "
            "посещения — студия → «Сайты» → «Аналитика». Скажи адрес и что после правок нужно сказать «опубликуй ещё раз».")


def t_site_article(a, ctx):
    """«Статьи» сайта (0.93) голосом: «напиши статью для сайта про…», «что с моими статьями», «опубликуй статью», «включи статьи»."""
    from sites import SiteError
    import sites_blog as B
    S = _sites(ctx)
    act = str(a.get("action") or "list").lower()
    try:
        sid = S.find(a.get("site") or "")
        s = S.get(sid)
        if not (s.get("published") or {}).get("name"):
            raise ToolError("Сайт ещё не опубликован — статьи живут на опубликованном. Предложи сначала опубликовать (site_publish).")
        if act == "on":
            S.blog_set(sid, {"on": True})
            b = B.conf(S.get(sid))
            return (f"Статьи включены для «{s['name']}»: план из {len(b['plan'])} тем, черновик — {B.FREQ[b['freq']]}, первый — по расписанию; "
                    "Радар сам собирает новости ниши. Черновики приходят на «Да» — в студию («Сайты» → «Статьи») и на телефон. Скажи коротко.")
        if act == "off":
            S.blog_set(sid, {"on": False})
            return "Статьи выключены — опубликованные остаются на сайте. Скажи коротко."
        if act == "write":
            art = B.write(S, sid, str(a.get("topic") or "").strip()[:200])
            st = "опубликована" if art.get("status") == "live" else "черновик ждёт «Да»"
            return (f"Статья «{art.get('title')}» — {st}. Прочитать и поправить — студия → «Сайты» → «Статьи» или приложение на телефоне "
                    "(«Всё» → «Статьи сайта»). Скажи коротко, не пересказывай статью.")
        arts = S.blog_get(sid)["articles"]
        if act == "publish":
            q = str(a.get("title") or "").lower()
            drafts = [x for x in arts if x["status"] == "draft" and (not q or q in x["title"].lower())]
            if not drafts:
                raise ToolError("Черновиков для публикации нет." if not q else f"Черновика «{a.get('title')}» нет.")
            x = drafts[0]
            B.set_status(S, sid, x["id"], "live")
            return f"Опубликовано: «{x['title']}» — {x['url']}. Скажи коротко."
        b = B.conf(S.get(sid))
        dr = [x["title"] for x in arts if x["status"] == "draft"]
        lv = [x for x in arts if x["status"] == "live"]
        return (f"Статьи «{s['name']}»: {'включены' if b['on'] else 'выключены'}; на сайте {len(lv)}"
                + (f" (просмотров всего {sum(x['views'] for x in lv)})" if lv else "")
                + (f"; ждут «Да»: {'; '.join(dr[:5])}" if dr else "; черновиков нет")
                + (f"; следующий черновик — {time.strftime('%d.%m %H:%M', time.localtime(b['next']))}" if b["on"] and b["next"] else "")
                + ". Скажи главное коротко.")
    except (SiteError, B.BlogError) as e:
        raise ToolError(str(e)) from e


def t_site_review(a, ctx):
    """«Оцени мой сайт», «как его продвигать» — проверка продвижения + посещения и источники."""
    from sites import SiteError
    S = _sites(ctx)
    try:
        sid = S.find(a.get("site") or "")
        au = S.audit(sid)
        st = {}
        if (S.get(sid).get("published") or {}).get("name"):
            try:
                st = S.stats(sid, 30)
            except SiteError as e:
                st = {"error": str(e)}
    except SiteError as e:
        raise ToolError(str(e)) from e
    s = S.get(sid)
    bad = [x for x in au["items"] if not x["ok"]]
    good = [x for x in au["items"] if x["ok"]]
    out = [f"Сайт «{s['name']}»: проверка продвижения — {au['score']} из 100."]
    if bad:
        out.append("Что улучшить: " + "; ".join(f"{x['title']} — {x['detail']} ({x['level']})" for x in bad[:8]) + ".")
    out.append("Уже хорошо: " + "; ".join(x["title"] for x in good[:8]) + ".")
    if st.get("days") is not None:
        views = sum(d.get("views", 0) for d in st.get("days") or [])
        vis = sum(d.get("visitors", 0) for d in st.get("days") or [])
        refs = ", ".join(f"{r['ref']} — {r['views']}" for r in (st.get("refs") or [])[:5]) or "нет данных"
        dev = st.get("devices") or {}
        out.append(f"За 30 дней: просмотров {views}, посетителей примерно {vis}, заявок с формы {st.get('leads', 0)}. Откуда пришли: {refs}. "
                   f"С телефона {dev.get('phone', 0)}, с компьютера {dev.get('desktop', 0)}.")
    elif st.get("error"):
        out.append(f"Посещения не узнала: {st['error']}.")
    else:
        out.append("Сайт ещё не опубликован — посещений нет.")
    out.append("Дай человеку 3–5 советов по продвижению простыми словами, по ЭТИМ данным (что исправить на сайте — предложи сделать "
               "одной фразой, я исправлю через site_edit; где рассказать о сайте — Яндекс Бизнес/Карты, 2ГИС, соцсети и мессенджеры, "
               "визитки и QR на месте, подпись в письмах). Не выдумывай цифры, которых здесь нет.")
    return "\n".join(out)


def t_plugin_enable(a, ctx):
    """«Нарисуй открытку», а «Художник» выключен (04.11: «я не умею рисовать») — включить готовый плагин из каталога после
    «Выполнить?». Только готовые плагины Dewiar (не свои и не пришедшие с других компьютеров) и только выключенные."""
    eng = (ctx or {}).get("engine")
    P = getattr(eng, "plugins", None)
    if P is None:
        raise ToolError("Плагины здесь недоступны")
    pid = str(a.get("id") or "").strip().lower()
    p = P.items.get(pid) or next((x for x in P.items.values() if x["name"].lower() == pid), None)
    if not p or not p.get("builtin"):
        raise ToolError(f"Готового плагина «{a.get('id')}» нет. Готовые: " + ", ".join(f"{x['name']} ({x['id']})" for x in P.items.values() if x.get("builtin")))
    if p["id"] in {x["id"] for x in P.installed()}:
        return f"Плагин «{p['name']}» уже включён — выполни просьбу им сразу (use_skill и его действия)."
    need = [x["label"] for x in p.get("settings") or [] if x.get("required")]
    if need:
        return (f"Плагину «{p['name']}» сначала нужны настройки ({', '.join(need)}). Скажи человеку: студия → «Все плагины» → "
                f"«{p['name']}» — заполнить их и нажать «Включить».")
    try:
        if hasattr(eng, "command"):
            eng.command("plugin_install", {"id": p["id"]})       # как кнопкой в студии: навыки и действия плагина подхватятся
        else:
            P.install(p["id"])
    except Exception as e:  # noqa: BLE001
        raise ToolError(f"Плагин не включился: {e}") from e
    return (f"Плагин «{p['name']}» включён. Его действия подключаются несколько секунд — скажи человеку одной фразой, что "
            "плагин включён, и попроси повторить просьбу (или нажать «Повторить»).")


def _maker(ctx):
    M = (ctx or {}).get("maker")
    if M is None:
        raise ToolError("Создание плагинов здесь недоступно")
    return M


def _maker_by(M, a):
    """«Пусть Патрик сделает» — by: имя персонажа -> его id (модель персонажа); пусто — тот, кто отвечает."""
    name = str((a or {}).get("by") or "").strip()
    if not name:
        return None
    h = M.host
    pid = h.find_persona(name) if h is not None and hasattr(h, "find_persona") else None
    if not pid:
        raise ToolError(f"Персонажа «{name}» нет — назови одного из своих персонажей или оставь пустым.")
    return pid


def _plugin_done(ctx, r, open_=True):
    """Плагин сделан или изменён: ядро — навыки, серверы, событие plugin_made (студия открывает его страницу, в «Чате» под
    ответом — кнопка «Открыть»)."""
    eng = (ctx or {}).get("engine")
    if eng is not None:
        try:
            eng.plugins_changed(r["id"], code=bool(r.get("code")), open_=open_)
            eng._turn_plugin = (time.monotonic(), {"id": r["id"], "name": r.get("name") or "", "icon": r.get("icon") or "🧩"})
        except Exception as e:  # noqa: BLE001
            log.info("плагин: студия не узнала: %s", e)


def t_plugin_create(a, ctx):
    """«Сделай плагин, который показывает статистику наших разговоров» — Лира пишет страницу и встраивает её в студию."""
    from plugin_maker import MakerError
    M = _maker(ctx)
    describe = " ".join(str(a.get("describe") or "").split())
    if len(describe) < 6:
        raise ToolError("Спроси одной фразой, что должен делать плагин: что на странице и зачем.")
    try:
        with M.using(_maker_by(M, a)):
            r = M.create(describe, code=bool(a.get("code")), name=str(a.get("name") or ""))
            r["by"] = M.who()
    except MakerError as e:
        raise ToolError(str(e)) from e
    _plugin_done(ctx, r)
    import plugins as _pl
    need = ", ".join(_pl.DATA_SCOPES[x].split(" — ")[0] for x in r.get("data") or [])
    return (f"Плагин «{r['name']}» {r['icon']} готов и открыт в студии (меню слева → «Плагины» → «{r['name']}»; в чате под ответом "
            "— кнопка «Открыть»)." + (f" При первом открытии он спросит разрешение: {need} — это нормально, человек решает сам." if need else "")
            + (" В нём своя программа — человек это разрешил." if r.get("code") else "")
            + " Скажи одной-двумя фразами, что получилось, и что менять можно словами («сделай крупнее», «добавь график»), а "
            "«верни как было» — откат. Не пиши код и HTML в ответе.")


def t_plugin_change(a, ctx):
    """«Сделай крупнее», «добавь график», «верни как было» — новая версия плагина, сделанного Лирой."""
    from plugin_maker import MakerError
    M = _maker(ctx)
    req = " ".join(str(a.get("request") or "").split())
    try:
        pid = M.find(a.get("plugin") or "")
        with M.using(_maker_by(M, a)):
            r = M.undo(pid) if a.get("undo") or not req else M.change(pid, req, code=bool(a.get("code")))
            r["by"] = M.who()
    except MakerError as e:
        raise ToolError(str(e)) from e
    _plugin_done(ctx, r)
    return (f"{r.get('said') or 'Готово'}. Плагин «{r['name']}» — версия {r.get('version')}, страница в студии обновлена. "
            "Скажи это коротко; вернуть прежнее — «верни как было» (хранятся 10 последних версий).")
