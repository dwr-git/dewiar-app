"""«Сайты» — наружу (часть Sites, чистое ядро 1.0.18): вёрстка и сборка, архив для своего хостинга, проверка
продвижения, публикация на dewiar.pro и проверка адреса, заявки с формы, «Статьи», фоновый цикл."""
import base64
import json
import re
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

import sites_kit as K
import sites_render as R
from sites_base import FONTS_DIR, log, name_problem, _now, SiteError, translit
import sites_base as SIB  # подменяемые в проверках имена — через основу


class OutMixin:
    # ---------- вёрстка ----------

    def render(self, sid, page=0, site=None):
        """Предпросмотр: page — номер страницы или «doc:privacy» (страница документа из «Подвала и документов»)."""
        s = site or self.get(sid)
        pg = str(page or 0)
        if pg.startswith("doc:"):
            return R.page_html(s, 0, "preview", self._images(sid, s, "preview"), doc=pg[4:])
        return R.page_html(s, int(pg) if pg.lstrip("-").isdigit() else 0, "preview", self._images(sid, s, "preview"))

    def build(self, sid, mode="publish", base_url=""):
        """Собрать сайт целиком: {путь: bytes}."""
        s = self.get(sid)
        imgs = self._images(sid, s, mode)
        files, fonts = R.site_files(s, imgs, base_url, mode)
        out = {k: v.encode("utf-8") for k, v in files.items()}
        for name, src in fonts:
            f = FONTS_DIR / src
            if f.exists():
                out["fonts/" + name] = f.read_bytes()
        used = "".join(files.values())
        for name in imgs:
            if name in used:
                out[name] = (self._dir(sid) / name).read_bytes()
        return out

    def export(self, sid):
        """Сайт в папку out/ — открыть в браузере с диска. -> путь к index.html."""
        d = self._dir(sid) / "out"
        shutil.rmtree(d, ignore_errors=True)
        for k, v in self.build(sid, "export").items():
            f = d / k
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(v)
        return d / "index.html"

    def export_zip(self, sid, folder=None):
        """Сайт архивом для своего сервера и домена (15.11, люди: «можно ли сайты из Лиры ставить на свой сервер под свой
        домен?»): те же файлы, что «Открыть с диска» (ссылки на .html — работает на любом хостинге без настроек), zip в
        «Загрузки». Заявки с формы идут в Dewiar, пока сайт опубликован и здесь. -> путь к .zip."""
        import zipfile
        import export as X
        s = self.get(sid)
        files = self.build(sid, "export")
        base = translit(s.get("name") or "")[:40].strip("-") or "site"
        d = Path(folder) if folder else X.downloads_dir()
        d.mkdir(parents=True, exist_ok=True)
        out, n = d / f"{base}.zip", 2
        while out.exists():
            out, n = d / f"{base}-{n}.zip", n + 1
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for k, v in sorted(files.items()):
                z.writestr(k, v)
            z.writestr("КАК-ПОСТАВИТЬ.txt", ("Сайт «" + str(s.get("name") or "") + "» из Dewiar.\n\nПоложите все файлы архива в корень сайта на своём "
                       "хостинге (папка public_html, www или htdocs) — так, чтобы index.html лежал сверху. Свой домен направьте на этот "
                       "хостинг у регистратора. Больше ничего настраивать не нужно.\n\n"
                       + ("Кнопка заявки ведёт к форме сайта на dewiar.pro — заявки приходят в Dewiar («Клиенты»), пока сайт там опубликован.\n"
                          if (s.get("published") or {}).get("url") else
                          "Форма заявки работает только у сайта, опубликованного в Dewiar: опубликуйте его и скачайте архив снова — "
                          "кнопка заявки поведёт к форме, а заявки придут в «Клиенты».\n")
                       + "\nИзменили сайт в Dewiar — скачайте архив снова и замените файлы.\n").encode("utf-8"))
        return out

    # ---------- продвижение ----------

    def audit(self, sid):
        """Проверка продвижения без внешних служб: заголовки и описания страниц, h1/h2, alt, вес, контакты и форма,
        Open Graph, заглушки. -> {score, items: [{ok, level, title, detail, fix}]} — fix: фраза для Лиры."""
        s = self.get(sid)
        files = self.build(sid, "publish", (s.get("published") or {}).get("url") or "")
        pages = [(i, pg, files.get(R.slug_of(pg, i) + ".html", b"").decode("utf-8", "replace")) for i, pg in enumerate(s.get("pages") or [])]
        items = []

        def add(ok, level, title, detail, fix=""):
            items.append({"ok": bool(ok), "level": level, "title": title, "detail": detail, "fix": "" if ok else fix})
        for i, pg, h in pages:
            pname = "главной" if i == 0 else f"страницы «{pg.get('title')}»"
            t = re.search(r"<title>(.*?)</title>", h, re.S)
            tl = len(R.html.unescape(t.group(1))) if t else 0
            add(15 <= tl <= 70, "важно", f"Заголовок {pname} для поисковиков",
                f"{tl} знаков — хорошо (нужно 15–70)" if 15 <= tl <= 70 else f"{tl} знаков, а лучше 15–70: в поиске заголовок {'обрежется' if tl > 70 else 'слишком короткий'}",
                f"Сделай заголовок {pname} для поисковиков длиной 40–65 знаков: название и чем занимаемся")
            dm = re.search(r'<meta name="description" content="([^"]*)"', h)
            dl = len(R.html.unescape(dm.group(1))) if dm else 0
            add(70 <= dl <= 170, "важно", f"Описание {pname}",
                f"{dl} знаков — хорошо" if 70 <= dl <= 170 else ("описания нет — поисковик возьмёт случайный кусок текста" if not dl else
                                                                 f"{dl} знаков, а лучше 120–160"),
                f"Напиши описание {pname} для поисковиков на 120–160 знаков: что предлагаем, где и почему к нам")
            h1 = len(re.findall(r"<h1[\s>]", h))
            add(h1 == 1, "важно", f"Главный заголовок (h1) {pname}", "один — как нужно" if h1 == 1 else f"их {h1}, а нужен ровно один",
                f"Добавь на {pname} обложку с главным заголовком")
            h2 = len(re.findall(r"<h2[\s>]", h))
            add(h2 >= 2 or len(pg.get("blocks") or []) < 3, "полезно", f"Подзаголовки разделов {pname}", f"{h2} — поисковику понятна структура" if h2 >= 2 else "мало подзаголовков",
                f"Дай каждому разделу {pname} понятный заголовок")
            imgs = re.findall(r"<img\b[^>]*>", h)
            noalt = [x for x in imgs if re.search(r'alt=""', x) or "alt=" not in x]
            add(not noalt, "полезно", f"Подписи к картинкам {pname}", "у всех картинок есть подписи" if imgs and not noalt else
                ("картинок нет" if not imgs else f"без подписи: {len(noalt)} из {len(imgs)}"),
                f"Подпиши фото на {pname}: коротко, что на них")
        size = sum(len(v) for k, v in files.items() if not k.startswith("fonts/"))
        fonts = sum(len(v) for k, v in files.items() if k.startswith("fonts/"))
        add(size < 1_500_000, "важно", "Вес сайта", f"{size // 1024} КБ страниц и картинок + {fonts // 1024} КБ шрифтов — открывается быстро даже с телефона"
            if size < 1_500_000 else f"{size // 1024} КБ — тяжело для мобильного интернета", "Уменьши фото на сайте или убери лишние")
        ct = s.get("contacts") or {}
        add(any(ct.get(k) for k in ("phone", "email", "telegram", "whatsapp", "max")), "важно", "Как связаться",
            "контакты есть" if any(ct.get(k) for k in ("phone", "email", "telegram", "whatsapp", "max")) else "ни телефона, ни почты, ни мессенджера",
            "Добавь на сайт телефон или Telegram — я продиктую")
        types = {b["type"] for pg in s.get("pages") or [] for b in pg.get("blocks") or []}
        add("lead" in types, "важно", "Форма заявки", "есть — заявки придут в «Клиенты»" if "lead" in types else "нет формы — посетителю сложнее оставить заявку",
            "Добавь форму заявки перед контактами")
        pol = R.legal_href(s, "privacy")
        draft = " (черновик Лиры — проверьте с юристом)" if pol.endswith(".html") and (((s.get("legal") or {}).get("docs") or {}).get("privacy") or {}).get("draft") else ""
        if pol:
            pdet = ("есть, в форме заявки — галочка согласия" if "lead" in types else "есть") + draft
        else:
            pdet = ("на сайте есть форма заявки, а политики обработки персональных данных нет — по закону (152-ФЗ) она нужна"
                    if "lead" in types else "формы заявки нет — политика пока не обязательна")
        add(bool(pol) or "lead" not in types, "важно" if "lead" in types else "полезно", "Политика обработки данных", pdet, "Подвал и документы")
        org = str((s.get("legal") or {}).get("org") or "").strip()
        add(bool(org), "полезно", "Реквизиты в подвале", f"есть: {org}" if org else "нет названия организации или ИП и ИНН — людям спокойнее, когда видно, кто за сайтом",
            "Подвал и документы")
        add(bool(ct.get("address")) or "contacts" in types, "полезно", "Адрес и карта", "есть" if ct.get("address") else "адреса нет — если вы принимаете у себя, его ищут первым",
            "Добавь адрес в контакты")
        add(True, "полезно", "Карточка для соцсетей (Open Graph)", "есть: название, описание и картинка в превью ссылки")
        if not any(b.get("image") for pg in s.get("pages") or [] for b in pg.get("blocks") or []):
            items[-1]["detail"] = "есть название и описание; добавьте фото на обложку — ссылка в мессенджерах будет с картинкой"
        todo = [b for pg in s.get("pages") or [] for b in pg.get("blocks") or [] if any(x.get("todo") for x in b.get("items") or [])]
        empty_prices = [b for pg in s.get("pages") or [] for b in pg.get("blocks") or [] if b["type"] in ("prices", "services", "products")
                        and any(not str(x.get("price") or "").strip() for x in b.get("items") or [])]
        add(not todo, "важно", "Заглушки", "все заглушки заменены" if not todo else
            f"в разделе «{K.BLOCKS[todo[0]['type']]['title']}» остались заглушки — их не видно на сайте, пока не замените",
            "Расскажу о сотрудниках — замени заглушки в команде")
        add(not empty_prices, "полезно", "Цены", "у всех позиций есть цены" if not empty_prices else "у части позиций нет цены — люди чаще пишут, когда видят цену",
            "Помоги заполнить цены — спроси меня о них")
        gal = [b for pg in s.get("pages") or [] for b in pg.get("blocks") or [] if b["type"] == "gallery"]
        if gal:
            have = sum(1 for b in gal for x in b.get("items") or [] if x.get("image"))
            add(have > 0, "полезно", "Фото в галерее", f"фото: {have}" if have else "фото не добавлены — галерея на сайте не покажется",
                "Как добавить фото в галерею?")
        pub = (s.get("published") or {}).get("url")
        seo = s.get("seo") or {}
        if pub:                                       # 0.93: технический SEO — сам; подтвердить сайт в поисковиках — одно поле
            add(True, "полезно", "Карта сайта и robots.txt", f"есть сами: {pub}/sitemap.xml — новые страницы и статьи попадают в неё автоматически, "
                "а Яндекс и Bing узнают о них сразу (IndexNow)")
            add(bool(seo.get("verify_yandex")), "полезно", "Яндекс Вебмастер", "сайт подтверждён — смотрите в Вебмастере, как Яндекс его видит"
                if seo.get("verify_yandex") else "не подтверждён — подтвердите: увидите поисковые запросы и ускорите появление в поиске", "@verify")
            add(bool(seo.get("verify_google")), "полезно", "Google Search Console", "сайт подтверждён" if seo.get("verify_google")
                else "не подтверждён — подтвердите, чтобы видеть, по каким запросам вас находят в Google", "@verify")
            bl = s.get("blog") or {}
            add(bool(bl.get("on")), "полезно", "Статьи", f"Лира ведёт статьи: на сайте {bl.get('live') or 0}" if bl.get("on")
                else "статей нет — статьи по вопросам клиентов приводят людей из поиска", "@blog")
        add(bool(pub), "важно", "Сайт в интернете", f"опубликован: {pub}" if pub else "ещё не опубликован — поисковики его не видят",
            "Опубликуй сайт")
        w = {"важно": 3, "полезно": 1}
        tot = sum(w[x["level"]] for x in items)
        score = round(100 * sum(w[x["level"]] for x in items if x["ok"]) / tot) if tot else 0
        return {"score": score, "items": sorted(items, key=lambda x: (x["ok"], x["level"] != "важно")), "size": size, "fonts": fonts}

    # ---------- dewiar.pro ----------

    def _key(self):
        return (getattr(getattr(self.host, "cloud", None), "key", "") or "").strip()

    def _fetch(self, path, body=None, timeout=40):
        from cloud import CloudError, fetch
        if not self._key():
            raise SiteError("нужен вход аккаунтом dewiar.pro или ключ Dewiar — студия → «Мозг»")
        try:
            return fetch(self.host.cloud.url, self._key(), path, timeout=timeout, body=body)
        except CloudError as e:
            raise SiteError(str(e)) from e

    def check_name(self, name, sid=""):
        n = str(name or "").strip().lower()
        p = name_problem(n)
        if p:
            return {"ok": False, "free": False, "reason": p}
        s = self.get(sid) if sid else {}
        if (s.get("published") or {}).get("name") == n:
            return {"ok": True, "free": True, "mine": True}
        d = self._fetch("/sites/check", {"name": n})
        return {"ok": True, "free": bool(d.get("free")), "mine": bool(d.get("mine")), "reason": d.get("reason") or ""}

    def suggest_name(self, sid):
        s = self.get(sid)
        return (s.get("published") or {}).get("name") or translit(s.get("name") or "")[:30].strip("-") or "moy-sait"

    def publish(self, sid, name=""):
        s = self.get(sid)
        n = str(name or (s.get("published") or {}).get("name") or self.suggest_name(sid)).strip().lower()
        p = name_problem(n)
        if p:
            raise SiteError(p)
        files = self.build(sid, "publish", f"https://{n}.dewiar.pro")
        total = sum(len(v) for v in files.values())
        if total > 8 * 1024 * 1024:
            raise SiteError(f"сайт весит {total // 1024 // 1024} МБ, а можно до 8 — уменьшите или уберите часть фото")
        was = (s.get("published") or {}).get("name") or ""
        body = {"name": n, "title": R.seo_title(s, 0)[:160], "description": R.seo_desc(s, 0)[:300], "site": sid, "from": was,
                "files": {k: ({"t": v.decode("utf-8")} if k.endswith((".html", ".css")) else {"b": base64.b64encode(v).decode()}) for k, v in files.items()}}
        d = self._fetch("/sites/publish", body, timeout=90)
        s["published"] = {"name": d.get("name") or n, "url": d.get("url") or f"https://{n}.dewiar.pro", "ts": _now(), "status": "live", "reason": ""}
        old = (self.get(sid).get("published") or {}).get("name")
        if old and old != n:
            try:
                self._fetch("/sites/remove", {"name": old})
            except SiteError:
                pass
        s["published"]["reach"] = self._reach(s["published"])
        self._save(s, f"Опубликован: {s['published']['url']}")
        if not s["published"]["reach"]["ok"]:
            # новый адрес часто открывается через несколько секунд (DNS, сертификат) — проверить ещё раз скоро, а не через полчаса
            # (владелец 14.11: «домен сразу стал открываться в браузере, а в Лире — „ждёт адреса“»)
            threading.Thread(target=self._reach_soon, args=(sid,), name="site-reach", daemon=True).start()
        log.info("🌐 Сайт опубликован: %s%s", s["published"]["url"],
                 "" if s["published"]["reach"]["ok"] else f" — по адресу пока не открывается ({s['published']['reach']['why']})")
        self.start()
        return s

    def _reach(self, pub):
        """Открывается ли сайт: сначала отсюда; не открылся — спросить сервер (владелец 15.11: «оранжевым горит „проверяю
        адрес“, хотя сайт открывается — я в подсети сайта»): отсюда мешают своя сеть, роутер без «петли», прокси, VPN.
        Сервер видит адрес как все в интернете; его «открывается» — правда. Сервер без этой проверки (старый) — как было."""
        r = SIB.reach(pub["url"])
        if r["ok"] or not pub.get("name"):
            return r
        try:
            d = self._fetch("/sites/reach", {"name": pub["name"]}, timeout=20)
        except SiteError:
            return r
        if d.get("reach") is True:
            return {"ok": True, "why": "", "at": r["at"], "via": "server", "here": r["why"]}
        return dict(r, why=d.get("why") or r["why"]) if d.get("reach") is False else r

    def _reach_soon(self, sid, waits=(10, 30, 90, 240)):
        for w in waits:
            time.sleep(w)
            try:
                st = self.recheck(sid)
            except Exception:  # noqa: BLE001
                return
            self._emit(sid)
            if ((st.get("published") or {}).get("reach") or {}).get("ok"):
                return

    def recheck(self, sid):
        """Открывается ли опубликованный сайт по своему адресу — снова (кнопка «Проверить адрес», фон раз в полчаса)."""
        s = self.get(sid)
        pub = s.get("published") or {}
        if not pub.get("url"):
            return s
        was = (pub.get("reach") or {}).get("ok")
        pub["reach"] = self._reach(pub)
        s["published"] = pub
        with self._lock:
            (self._dir(sid) / "site.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
        if pub["reach"]["ok"] and was is False and self.host is not None:
            try:
                self.host.push("Сайт открывается", f"{pub['url']} — адрес заработал, можно отправлять ссылку")
            except Exception:  # noqa: BLE001
                pass
        return s

    def unpublish(self, sid):
        s = self.get(sid)
        n = (s.get("published") or {}).get("name")
        if n:
            self._fetch("/sites/remove", {"name": n})
        s["published"] = None
        return self._save(s, "Снят с публикации")

    def stats(self, sid, days=30, prev=False):
        s = self.get(sid)
        n = (s.get("published") or {}).get("name")
        if not n:
            return {"none": True}
        d = self._fetch("/sites/stats", {"name": n, "days": int(days), "prev": bool(prev)})
        st = s.get("published") or {}
        if bool(d.get("blocked")) != (st.get("status") == "blocked") or (d.get("reason") or "") != (st.get("reason") or ""):
            st.update({"status": "blocked" if d.get("blocked") else "live", "reason": d.get("reason") or ""})
            s["published"] = st
            with self._lock:
                (self._dir(sid) / "site.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
        d["leads_local"] = [x for x in self.recent if x.get("site") == n][-20:][::-1]
        return d

    def sync_status(self):
        """Состояние своих сайтов на dewiar.pro (блокировка администратором и причина) -> обновить у себя."""
        if not any((self.get(i).get("published") or {}).get("name") for i in self.ids()):
            return 0
        d = self._fetch("/sites/mine", {})
        by = {x.get("name"): x for x in d.get("sites") or []}
        n = 0
        for sid in self.ids():
            s = self.get(sid)
            pub = s.get("published") or {}
            r = by.get(pub.get("name"))
            if not r:
                continue
            st = "blocked" if r.get("blocked") else "live"
            if st != pub.get("status") or (r.get("reason") or "") != (pub.get("reason") or ""):
                pub.update({"status": st, "reason": r.get("reason") or ""})
                s["published"] = pub
                with self._lock:
                    (self._dir(sid) / "site.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
                n += 1
                if st == "blocked":
                    try:
                        self.host.push("Сайт заблокирован", f"{pub.get('url')}: {r.get('reason') or 'причина в студии → «Сайты»'}")
                    except Exception:  # noqa: BLE001
                        pass
        if n:
            self._emit("")
        return n

    # ---------- заявки ----------

    def take(self, lead):
        """Заявка с формы сайта -> клиент (новый или знакомый) в «Клиентах». -> id клиента."""
        from sitechat import EMAIL_RX, PHONE_RX
        h = self.host
        C = getattr(h, "clients", None)
        if C is None:
            return ""
        contact = str(lead.get("contact") or "").strip()
        m1, m2 = EMAIL_RX.search(contact), PHONE_RX.search(contact)
        when = datetime.fromtimestamp(lead.get("ts") or time.time()).strftime("%d.%m %H:%M")
        text = (f"Заявка с сайта {lead.get('site')}.dewiar.pro ({when}): {contact}" + (f" — {lead['note']}" if lead.get("note") else "")
                + (f" (страница {lead['page']})" if lead.get("page") and lead.get("page") != "index" else ""))
        cid = h.sitechat._find_client(contact) if getattr(h, "sitechat", None) else None
        if cid:
            C.note(cid, text)
        else:
            cid = C.add((lead.get("name") or "").strip() or contact, phone=m2.group(0) if m2 and not m1 else "", email=m1.group(0) if m1 else "")["id"]
            C.note(cid, text)
        crm = getattr(h, "crm", None)
        if crm is not None and crm.connected() and crm.st.get("auto"):
            threading.Thread(target=lambda: crm.send(cid), name="crm-site", daemon=True).start()
        return cid

    def poll(self):
        if not self._key() or not any((self.get(i).get("published") or {}).get("name") for i in self.ids()):
            return 0
        try:
            d = self._fetch("/sites/leads", {})
        except SiteError as e:
            self.error = str(e)
            return 0
        self.error = ""
        done = []
        for lead in d.get("leads") or []:
            try:
                cid = self.take(lead)
            except Exception as e:  # noqa: BLE001
                log.warning("🌐 Заявка с сайта не завелась: %s", e)
                continue
            done.append(lead["id"])
            self._lead_log(lead, cid)
            self.recent.append({"ts": lead.get("ts"), "site": lead.get("site"), "name": lead.get("name") or "", "contact": lead.get("contact") or "",
                                "note": lead.get("note") or "", "page": lead.get("page") or "", "cid": cid})
            self.recent = self.recent[-100:]
            try:
                self.host.push("Заявка с сайта", f"{lead.get('name') or 'Посетитель'}, {lead.get('contact')} — в «Клиентах»")
            except Exception:  # noqa: BLE001
                pass
        if done:
            try:
                self._fetch("/sites/leads", {"ack": done})
            except SiteError as e:
                log.info("🌐 Заявки заведены, но сервер не узнал: %s", e)
            if self.host is not None:
                try:
                    (self.host.s.get("features") or {}).get("clients") or self.host.s.update({"features": {"clients": True}})
                except Exception:  # noqa: BLE001
                    pass
            self._emit("")
        return len(done)

    def _lead_log(self, lead, cid):
        """Заявка — и в журнал своего сайта (leads.json): вкладка «Заявки» показывает их и после перезапуска."""
        for sid in self.ids():
            if (self.get(sid).get("published") or {}).get("name") == lead.get("site"):
                f = self._dir(sid) / "leads.json"
                try:
                    items = json.loads(f.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    items = []
                items.append({"ts": lead.get("ts") or _now(), "name": lead.get("name") or "", "contact": lead.get("contact") or "",
                              "note": lead.get("note") or "", "page": lead.get("page") or "", "cid": cid})
                f.write_text(json.dumps(items[-500:], ensure_ascii=False), encoding="utf-8")
                return

    def leads(self, sid):
        """Заявки этого сайта (журнал leads.json; клиенты — в «Клиентах»), свежие сверху."""
        try:
            return json.loads((self._dir(sid) / "leads.json").read_text(encoding="utf-8"))[::-1]
        except (OSError, ValueError):
            return []

    # ---------- «Статьи» (0.93, sites_blog) ----------

    def blog_save_conf(self, sid, patch):
        """Настройки статей сайта — без версии в истории (это не правка сайта)."""
        with self._lock:
            s = self.get(sid)
            b = dict(s.get("blog") or {})
            b.update(patch)
            s["blog"] = b
            (self._dir(sid) / "site.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
        return b

    def blog_get(self, sid, fresh=True):
        import sites_blog as B
        s = self.get(sid)
        arts, err = [], ""
        if fresh and (s.get("published") or {}).get("name") and self._key():
            try:
                arts = B.sync(self, sid)
            except SiteError as e:
                err = str(e)
        b = B.conf(self.get(sid))
        r = B.radar_of(self)
        rad = {"sources": len([x for x in r.st.sources() if x.get("on", True)]), "items": len(r.st.items())} if r is not None else None
        return {"blog": b, "articles": arts, "error": err, "published": bool((s.get("published") or {}).get("name")),
                "url": (s.get("published") or {}).get("url") or "", "auto_after": B.AUTO_AFTER, "freqs": B.FREQ, "radar": rad}

    def blog_set(self, sid, patch):
        import sites_blog as B
        p = B.clean_patch(patch or {})
        if p.get("mode") == "auto" and B.conf(self.get(sid))["approved"] < B.AUTO_AFTER:
            raise SiteError(f"«Публиковать сразу» откроется после {B.AUTO_AFTER} одобренных черновиков — сначала посмотрите, как пишет Лира")
        was = B.conf(self.get(sid))
        b = self.blog_save_conf(sid, p)
        if p.get("on") and not was["on"]:                 # включили: Радар — сам, план — сразу, первый черновик — по расписанию
            boost = B.radar_boost(self, self.get(sid), wait=getattr(self, "blog_wait", False))   # проверки ждут обход
            self.blog_save_conf(sid, {"radar": bool(boost.get("sources")) or was.get("radar", False)})
            if not B.conf(self.get(sid))["plan"]:
                try:
                    B.make_plan(self, sid)
                except Exception as e:  # noqa: BLE001
                    self.blog_save_conf(sid, {"err": str(e)[:200]})
        if any(k in p for k in ("on", "freq", "day", "hour")):
            b = self.blog_save_conf(sid, {"next": B.next_slot(B.conf(self.get(sid))) if B.conf(self.get(sid))["on"] else 0})
        return self.blog_get(sid, fresh=False)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="sites", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        tick = 0
        while not self._stop.wait(120):
            try:
                import sites_blog
                sites_blog.due(self)                    # 0.93: пора — черновик статьи (по расписанию сайта)
            except Exception:  # noqa: BLE001
                log.exception("Сайты: статьи")
            try:
                self.poll()
                tick += 1
                if tick % 15 == 1:                      # раз в полчаса — не заблокирован ли сайт
                    self.sync_status()
                    for sid in self.ids():               # №549: адрес ещё не открывался — проверить снова, заработал — сказать
                        if ((self.get(sid).get("published") or {}).get("reach") or {}).get("ok") is False:
                            self.recheck(sid)
            except Exception:  # noqa: BLE001
                log.exception("Сайты: заявки")
