"""«Сайты» — изменения (часть Sites, чистое ядро 1.0.18): операции к сайту (apply_ops), картинки по ссылке и из чата,
подвал и документы, черновик политики, другой дизайн, фраза человека -> изменение, картинки сайта."""
import base64
import hashlib
import io
import json
import re
from pathlib import Path

import sites_kit as K
from sites_base import (
    clean_fields, clean_svg, _clip, EDIT_SYSTEM, _json_in, _now, ops_help, quick_ops, ref_outline, site_brief,
    SiteError, translit, _uid, verify_code)
import sites_base as SIB  # подменяемые в проверках имена — через основу


class EditMixin:
    # ---------- изменения ----------

    def _block(self, s, ref):
        """Блок по uid, якорю или типу (первый такого типа). -> (страница, индекс, блок)."""
        ref = str(ref or "").strip()
        for pi, pg in enumerate(s["pages"]):
            for j, b in enumerate(pg["blocks"]):
                if b.get("uid") == ref or (ref and b.get("id") == ref):
                    return pi, j, b
        for pi, pg in enumerate(s["pages"]):
            for j, b in enumerate(pg["blocks"]):
                if b.get("type") == ref:
                    return pi, j, b
        raise SiteError(f"нет такого раздела: {ref}")

    def apply(self, sid, ops, label="", merge=False):
        s = self.get(sid)
        if any(o.get("op") == "undo" for o in ops or [] if isinstance(o, dict)):
            return self.undo(sid)
        mf = [o for o in ops or [] if isinstance(o, dict) and o.get("op") == "media_from" and o.get("url")]
        if mf:                                         # «возьми фото и видео с моего сайта …» — со страницы человека
            media = {}
            ref_outline(str(mf[0]["url"]), media=media)
            s = self.take_media(sid, media, photo=mf[0].get("photo", True) is not False, video=mf[0].get("video", True) is not False)
            ops = [o for o in ops if o not in mf]
            if not ops:
                return s
        ops, got = self._images_by_url(sid, s, ops)
        done = self.apply_ops(s, ops) + got
        if done and all(x.startswith("картинка не взялась") for x in done):
            raise SiteError("; ".join(done))           # одни неудачи — версию не пишем, модель скажет честно
        if not done:
            raise SiteError("ничего не поменялось")
        return self._save(s, label or "; ".join(done)[:120], merge=merge)

    def _images_by_url(self, sid, s, ops):
        """{"op":"image","url":…,"block":uid[,"index":n]} — картинка по ссылке (15.11, люди: «хочу свои картинки — дать их Лире,
        а она разместит»; «возьми фото с моего сайта»): скачать, уменьшить в webp сайта и поставить в раздел или карточку;
        index нет у галереи — новой карточкой. Не скачалась — честно в списке сделанного. -> (прочие операции, сделанное)."""
        rest, done = [], []
        for o in ops or []:
            if not (isinstance(o, dict) and o.get("op") == "image" and (o.get("url") or o.get("file"))):
                rest.append(o)
                continue
            try:
                data = self._own_image(o["file"]) if o.get("file") else SIB.fetch_image(str(o["url"]))
                name = self.image_add(sid, data, o.get("alt") or "")
                s.setdefault("assets", {}).update(self.get(sid).get("assets") or {})
                pi, j, b = self._block(s, o.get("block"))
            except SiteError as e:
                done.append(f"картинка не взялась ({e})")
                continue
            i = o.get("index")
            if isinstance(i, int) and 0 <= i < len(b.get("items") or []):
                b["items"][i]["image"] = name
            elif b["type"] == "gallery" or (K.BLOCKS.get(b["type"], {}).get("items") and not any(f[0] == "image" for f in K.BLOCKS[b["type"]]["fields"])):
                its = [x for x in b.setdefault("items", []) if x.get("image") or str(x.get("caption") or x.get("title") or "").strip()]
                b["items"] = its + [{"image": name, "caption": str(o.get("caption") or "")[:200]}]
            else:
                b["image"] = name
            done.append(f"картинка в разделе {K.BLOCKS.get(b['type'], {}).get('title', b['type'])}")
        return rest, done

    def _own_image(self, rel):
        """Картинка, которую человек приложил в чат (сохранена во «Входящие» его папки): только картинки и только внутри
        папки ассистента — модель не может взять на сайт файл откуда угодно (15.11)."""
        ws = getattr(self.host, "workspace", None)
        root = Path(getattr(ws, "root", "") or "") if ws is not None else None
        if not root or not str(root) or str(root) == ".":
            raise SiteError("свои картинки — приложите их в чат")
        f = (root / str(rel).strip().lstrip("/\\")).resolve()
        if root.resolve() not in f.parents or f.suffix.lower() not in self.IMG_EXT or not f.is_file():
            raise SiteError(f"нет такой картинки: {rel}")
        if f.stat().st_size > 25 * 1024 * 1024:
            raise SiteError("картинка больше 25 МБ")
        return f.read_bytes()

    def apply_ops(self, s, ops):
        """Операции к сайту (на месте). -> список того, что сделано (для истории)."""
        done = []
        th = s.setdefault("theme", {})
        for o in ops or []:
            if not isinstance(o, dict):
                continue
            op = o.get("op")
            if op == "palette" and o.get("name") in K.PALETTES:
                th["palette"], th["colors"] = o["name"], {}
                th.pop("bg", None)                     # новая палитра — со своим фоном
                done.append(f"палитра {K.PALETTES[o['name']]['title']}")
            elif op == "background":
                cs = [c for c in (o.get("colors") if isinstance(o.get("colors"), list) else [o.get("colors")] if o.get("colors") else [])
                      if re.fullmatch(r"#[0-9a-fA-F]{6}", str(c or ""))][:2]
                if cs:
                    th["bg"] = cs
                    done.append("фон " + ("градиентом" if len(cs) > 1 and cs[0] != cs[1] else "одним цветом"))
                elif "colors" in o and th.get("bg"):
                    th.pop("bg", None)
                    done.append("фон — как в палитре")
            elif op == "colors":
                cs = {k: v for k, v in o.items() if k in K.COLOR_KEYS and re.fullmatch(r"#[0-9a-fA-F]{6}", str(v or ""))}
                if cs:
                    th.setdefault("colors", {}).update(cs)
                    done.append("цвета")
                if o.get("header") in K.HEADERS:
                    th["header"] = o["header"]
                    done.append("шапка")
            elif op == "style" and o.get("value") in K.STYLES:
                # стиль (0.94): «Авангард» приносит свои палитру, шрифт и углы — их потом можно поменять отдельно
                st = K.STYLES[o["value"]]
                th["style"] = o["value"]
                for k in ("palette", "fonts", "radius", "header"):
                    if st.get(k) and not o.get("keep"):
                        th[k] = st[k]
                if st.get("palette") and not o.get("keep"):
                    th["colors"] = {}
                done.append(f"стиль «{st['title']}»")
            elif op == "header" and o.get("value") in K.HEADERS:
                th["header"] = o["value"]
                done.append(K.HEADERS[o["value"]].lower())
            elif op == "fonts" and o.get("name") in K.FONTS:
                th["fonts"] = o["name"]
                done.append(f"шрифт {K.FONTS[o['name']]['title']}")
            elif op == "radius" and o.get("name") in K.RADII:
                th["radius"] = o["name"]
                done.append(K.RADII[o["name"]]["title"].lower())
            elif op == "space" and o.get("name") in K.SPACES:
                th["space"] = o["name"]
                done.append(f"отступы {K.SPACES[o['name']]['title'].lower()}")
            elif op == "art" and o.get("name") in K.ARTS:
                th["art"] = o["name"]
                done.append("узор")
            elif op == "menu":
                m = s.setdefault("menu", {})
                if o.get("style") in K.MENUS:
                    m["style"] = o["style"]
                    done.append("меню " + K.MENUS[o["style"]].lower())
                if "cta" in o:
                    m["cta"] = _clip("button", o.get("cta") or "")
                    done.append("кнопка в шапке")
            elif op == "logo":
                lg = s.setdefault("logo", {})
                if o.get("text"):
                    lg["text"] = _clip("title", o["text"])[:60]
                if o.get("mark") in K.MARKS:
                    lg["mark"], lg["svg"] = o["mark"], ""
                if o.get("style") in K.LOGO_STYLES:
                    lg["style"] = o["style"]
                if o.get("svg"):
                    lg["svg"] = clean_svg(o["svg"])
                done.append("логотип")
            elif op == "site":
                for k in ("name", "tagline"):
                    if str(o.get(k) or "").strip():
                        s[k] = _clip("title", o[k]).strip()[:160 if k == "tagline" else 80]
                        if k == "name" and not (s.get("logo") or {}).get("svg"):
                            s.setdefault("logo", {})["text"] = s["name"]
                if "description" in o:
                    s.setdefault("seo", {})["description"] = _clip("text", o.get("description") or "")[:300]
                for k in ("verify_yandex", "verify_google"):          # 0.93: подтверждение в Вебмастере и Search Console
                    if k in o:
                        s.setdefault("seo", {})[k] = verify_code(o.get(k))
                done.append("название и описание")
            elif op == "contacts":
                ct = s.setdefault("contacts", {})
                for k, v in o.items():
                    if k in K.CONTACT_KEYS:
                        v = str(v or "").strip()[:200]
                        if v:
                            ct[k] = v
                        else:
                            ct.pop(k, None)
                done.append("контакты")
            elif op == "legal":
                if self._legal(s, o):
                    done.append("подвал и документы")
            elif op == "template" and o.get("id") in K.TEMPLATES:
                self._restyle(s, o["id"])
                done.append(f"дизайн «{K.TEMPLATES[o['id']]['title']}»")
            elif op == "add_block" and o.get("type") in K.BLOCKS:
                pi = int(o.get("page") or 0) if str(o.get("page") or "0").isdigit() else 0
                pi = max(0, min(pi, len(s["pages"]) - 1))
                bl = s["pages"][pi]["blocks"]
                b = K.blank_block(o["type"])
                b.update(clean_fields(o.get("data") or {}))
                if o["type"] == "reviews":
                    b["items"] = [x for x in b.get("items") or [] if str(x.get("text") or "").strip()]
                if o["type"] == "team":
                    for x in b.get("items") or []:
                        if not x.get("image") and not str(x.get("text") or "").strip() and x.get("name") in ("Имя", ""):
                            x["todo"] = True
                b["uid"] = _uid()
                b["nav"] = b.get("nav") or K.BLOCKS[o["type"]]["title"]
                at = None
                if o.get("after"):
                    try:
                        p2, j, _ = self._block(s, o["after"])
                        if p2 == pi:
                            at = j + 1
                    except SiteError:
                        pass
                if at is None:                           # по умолчанию — перед заявкой и контактами в конце страницы
                    at = len(bl)
                    while at > 0 and bl[at - 1]["type"] in ("lead", "contacts", "links") and o["type"] not in ("lead", "contacts"):
                        at -= 1
                prev = bl[at - 1]["tone"] if at > 0 else "alt"
                b["tone"] = b.get("tone") if o.get("data", {}).get("tone") in K.TONES else ("alt" if prev == "base" else "base")
                bl.insert(at, b)
                done.append(f"добавлен раздел {K.BLOCKS[o['type']]['title']}")
            elif op == "remove_block":
                pi, j, b = self._block(s, o.get("block"))
                s["pages"][pi]["blocks"].pop(j)
                done.append(f"убран раздел {K.BLOCKS.get(b['type'], {}).get('title', b['type'])}")
            elif op == "move_block":
                pi, j, b = self._block(s, o.get("block"))
                bl = s["pages"][pi]["blocks"]
                to = o.get("to")
                if to == "up":
                    to = j - 1
                elif to == "down":
                    to = j + 1
                try:
                    to = max(0, min(int(to), len(bl) - 1))
                except (TypeError, ValueError):
                    continue
                bl.insert(to, bl.pop(j))
                done.append("порядок разделов")
            elif op == "block":
                pi, j, b = self._block(s, o.get("block"))
                f = clean_fields({k: v for k, v in o.items() if k not in ("op", "block")})
                if f.get("variant") is not None and f["variant"] not in K.BLOCKS[b["type"]]["variants"]:
                    f.pop("variant")
                if f.get("tone") is not None and f["tone"] not in K.TONES:
                    f.pop("tone")
                if "id" in f:
                    f["id"] = re.sub(r"[^a-z0-9_-]", "", str(f["id"]).lower())[:30]
                if b["type"] == "reviews" and "items" in f:
                    f["items"] = [x for x in f["items"] if str(x.get("text") or "").strip()]
                if "items" in f:
                    for x in f["items"]:
                        if b["type"] == "team" and not x.get("todo") and x.get("name") in ("Имя врача", "Имя"):
                            x["todo"] = True
                b.update(f)
                done.append(f"раздел {K.BLOCKS.get(b['type'], {}).get('title', b['type'])}")
            elif op == "item":
                pi, j, b = self._block(s, o.get("block"))
                its = b.setdefault("items", [])
                i = o.get("index")
                if o.get("remove") and isinstance(i, int) and 0 <= i < len(its):
                    its.pop(i)
                elif isinstance(i, int) and 0 <= i < len(its):
                    its[i].update(clean_fields(o.get("data") or {}, "item"))
                    if its[i].get("todo") and o.get("data"):
                        its[i].pop("todo", None)          # человек заполнил заглушку — она его
                else:
                    its.append(clean_fields(o.get("data") or {}, "item"))
                done.append("карточки")
            elif op == "add_page":
                title = _clip("nav", o.get("title") or "Страница")
                slug = translit(title) or f"page{len(s['pages'])}"
                if slug == "index" or any(p.get("slug") == slug for p in s["pages"]):
                    slug += f"-{len(s['pages'])}"
                blocks = []
                for t in o.get("blocks") or ["text"]:
                    if t in K.BLOCKS:
                        b = K.blank_block(t)
                        b["uid"] = _uid()
                        blocks.append(b)
                s["pages"].append({"title": title, "slug": slug, "blocks": blocks})
                done.append(f"страница «{title}»")
            elif op == "remove_page":
                i = int(o.get("page") or 0)
                if 0 < i < len(s["pages"]):
                    s["pages"].pop(i)
                    done.append("страница убрана")
            elif op == "page":
                i = int(o.get("page") or 0)
                if 0 <= i < len(s["pages"]):
                    pg = s["pages"][i]
                    if o.get("title"):
                        pg["title"] = _clip("nav", o["title"])
                    if "description" in o:
                        pg["description"] = _clip("text", o.get("description") or "")[:300]
                    if "seo_title" in o:
                        pg["seo_title"] = _clip("title", o.get("seo_title") or "")[:90]
                    done.append("страница")
        return done

    @staticmethod
    def _legal(s, o):
        """«Подвал и документы» (0.87): реквизиты, документы (ссылка или свой текст — своя страница сайта), доп. ссылки.
        -> поменялось ли что-то."""
        lg = s.get("legal") if isinstance(s.get("legal"), dict) else {}
        before = json.dumps(lg, ensure_ascii=False, sort_keys=True)
        for k in K.LEGAL_FIELDS:
            if k not in o:
                continue
            v = re.sub(r"[\x00-\x1f]", " ", str(o.get(k) or "")).strip()
            if k in ("inn", "ogrn"):
                v = re.sub(r"\D", "", v)[:12 if k == "inn" else 15]
            v = v[:300 if k == "address" else 200]
            if v:
                lg[k] = v
            else:
                lg.pop(k, None)
        if isinstance(o.get("docs"), dict):
            docs = lg.setdefault("docs", {})
            for k, d in o["docs"].items():
                if k not in K.LEGAL_DOCS or not isinstance(d, dict):
                    continue
                cur = dict(docs.get(k) or {})
                if "mode" in d:
                    cur["mode"] = d["mode"] if d["mode"] in ("link", "text") else ""
                if "url" in d:
                    cur["url"] = str(d.get("url") or "").strip()[:500]
                if "text" in d:
                    t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(d.get("text") or "")).replace("\r\n", "\n")[:K.LEGAL_TEXT_MAX]
                    if t != cur.get("text"):
                        cur["text"], cur["ts"] = t, _now()
                        if not d.get("draft"):
                            cur.pop("draft", None)          # человек поправил черновик Лиры — он его
                if d.get("draft"):
                    cur["draft"] = True
                if not cur.get("mode") and not cur.get("text") and not cur.get("url"):
                    docs.pop(k, None)
                else:
                    docs[k] = cur
            if not docs:
                lg.pop("docs", None)
        if isinstance(o.get("links"), list):
            links = []
            for x in o["links"][:K.LEGAL_LINKS_MAX]:
                if isinstance(x, dict):
                    t, u = str(x.get("title") or "").strip()[:80], str(x.get("url") or "").strip()[:500]
                    if t or u:
                        links.append({"title": t, "url": u})
            if links:
                lg["links"] = links
            else:
                lg.pop("links", None)
        if lg:
            s["legal"] = lg
        else:
            s.pop("legal", None)
        return json.dumps(lg, ensure_ascii=False, sort_keys=True) != before

    def legal_draft(self, sid, key="privacy"):
        """«Составить черновик политики ПД по моим данным» (0.87): Лира пишет политику (или согласие) по реквизитам и
        устройству сайта; кладём «своим текстом» с пометкой draft — в студии: «черновик — проверьте с юристом»."""
        if key not in ("privacy", "consent"):
            raise SiteError("черновик Лира пишет для политики обработки данных и согласия")
        s = self.get(sid)
        lg = s.get("legal") or {}
        ct = s.get("contacts") or {}
        org = str(lg.get("org") or "").strip()
        if not org:
            raise SiteError("сначала впишите название организации или ИП — в политике оно обязательно")
        mail, phone = str(lg.get("email") or ct.get("email") or "").strip(), str(lg.get("phone") or ct.get("phone") or "").strip()
        if not mail and not phone:
            raise SiteError("впишите почту или телефон — куда людям писать о своих данных")
        pub = (s.get("published") or {}).get("url") or ""
        blocks = [b for pg in s.get("pages") or [] for b in pg.get("blocks") or [] if not b.get("hidden")]
        lead = next((b for b in blocks if b.get("type") == "lead"), None)
        fields = ["имя", "телефон, почта или ник в Telegram"] + (["комментарий"] if lead and lead.get("ask_message") else [])
        facts = "\n".join(x for x in (
            f"Оператор: {org}", f"ИНН: {lg['inn']}" if lg.get("inn") else "", f"ОГРН/ОГРНИП: {lg['ogrn']}" if lg.get("ogrn") else "",
            f"Адрес: {lg.get('address') or ct.get('address') or ''}" if (lg.get("address") or ct.get("address")) else "",
            f"Почта для обращений: {mail}" if mail else "", f"Телефон: {phone}" if phone else "",
            f"Сайт: «{s.get('name') or ''}» {pub}".strip(), f"Чем занимается: {s.get('tagline') or ''}",
            ("Форма заявки на сайте собирает: " + ", ".join(fields) + ". Цель — связаться с человеком по его заявке.") if lead
            else "Формы заявки на сайте нет; данные приходят, только если человек сам напишет или позвонит.",
            "Сайт работает на сервисе Dewiar (dewiar.pro): заявки хранятся там и передаются владельцу сайта; посещения считаются без cookie и без сторонних счётчиков; cookie сайт не ставит.",
        ) if x)
        what = "политику в отношении обработки персональных данных (152-ФЗ, ст. 18.1)" if key == "privacy" else \
            "согласие посетителя на обработку персональных данных (152-ФЗ, ст. 9), которое он даёт галочкой в форме заявки"
        system = ("Ты — помощник по документам сайта в программе Dewiar. Напиши " + what + " для небольшого сайта по-русски, "
                  "простым ясным языком, без воды. Используй ТОЛЬКО факты ниже; чего нет — не выдумывай (не пиши о cookie, "
                  "рассылках, оплате, передаче за границу, если этого нет в фактах). Разделы — строкой «## Название» (общие "
                  "положения, кто оператор, какие данные, цели, правовые основания, сроки хранения, кому передаём, права "
                  "человека и как отозвать согласие, защита данных, изменения документа). Списки — строками «- …». Верни "
                  "только текст документа, без пояснений до и после.")
        text = self.llm(system, "ФАКТЫ:\n" + facts, 3500)
        text = re.sub(r"^```\w*\s*|\s*```\s*$", "", str(text or "").strip()).strip()
        if len(text) < 400:
            raise SiteError("модель вернула слишком короткий текст — попробуйте ещё раз")
        self.apply(sid, [{"op": "legal", "docs": {key: {"mode": "text", "text": text, "draft": True}}}],
                   f"Черновик: {K.LEGAL_DOCS[key]['title'].lower()}")
        return {"text": text}

    def _restyle(self, s, tid):
        """«Другой дизайн целиком»: тема, меню, вид логотипа и вёрстка блоков — из шаблона tid; тексты и порядок — свои."""
        t = K.TEMPLATES[tid]
        s["template"] = tid
        s["theme"] = {"palette": t["palette"], "fonts": t["fonts"], "radius": t["radius"], "header": t["header"], "art": t["art"], "colors": {},
                      "style": t.get("style") or "classic"}
        s.setdefault("menu", {})["style"] = t["menu"]
        lg = s.setdefault("logo", {})
        lg["style"] = t["logo"]["style"]
        tb = {}
        for b in t["pages"][0]["blocks"]:
            tb.setdefault(b["type"], b)
        for pg in s["pages"]:
            for j, b in enumerate(pg["blocks"]):
                src = tb.get(b["type"])
                if src:
                    b["variant"], b["tone"] = src["variant"], src["tone"]
                    if b["type"] == "hero" and src["variant"] == "poster" and len(str(b.get("title") or "")) > 24:
                        b["variant"] = "split"
                else:
                    b["tone"] = "alt" if j % 2 else "base"

    def say(self, sid, text):
        """Фраза человека -> изменение. -> {site, said}."""
        s = self.get(sid)
        ops, said = quick_ops(text, s)
        if ops:
            if ops[0].get("op") == "undo":
                return {"site": self.undo(sid), "said": said}
            try:
                return {"site": self.apply(sid, ops, f"«{str(text)[:80]}»"), "said": said}
            except SiteError:
                pass
        d = _json_in(self.llm(EDIT_SYSTEM + ops_help(), f"{site_brief(s)}\n\nПРОСЬБА ЧЕЛОВЕКА: {text}", 3500))
        if isinstance(d, list):
            d = {"ops": d}
        if not isinstance(d, dict) or not d.get("ops"):
            raise SiteError("не поняла, что поменять, — скажите иначе: «добавь раздел с ценами», «сделай шапку тёмной»")
        s2 = self.apply(sid, d["ops"], f"«{str(text)[:80]}»")
        return {"site": s2, "said": str(d.get("say") or "Готово.")[:300]}

    # ---------- картинки ----------

    def image_add(self, sid, data, alt=""):
        """Картинка (data:… или байты) -> уменьшенная webp в img/ сайта. -> путь (img/….webp) для поля image."""
        from PIL import Image, ImageOps
        if isinstance(data, str):
            m = re.match(r"data:image/[a-z+.-]+;base64,(.+)$", data, re.S)
            if not m:
                raise SiteError("нужна картинка (jpg, png, webp)")
            raw = base64.b64decode(m.group(1))
        else:
            raw = bytes(data)
        if len(raw) > 25 * 1024 * 1024:
            raise SiteError("картинка больше 25 МБ")
        try:
            im = Image.open(io.BytesIO(raw))
            im = ImageOps.exif_transpose(im).convert("RGB")
        except Exception as e:  # noqa: BLE001
            raise SiteError("это не картинка или она повреждена") from e
        im.thumbnail((1920, 1920))
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=80, method=5)
        b = buf.getvalue()
        name = f"img/{hashlib.sha1(b).hexdigest()[:16]}.webp"
        d = self._dir(sid)
        (d / "img").mkdir(parents=True, exist_ok=True)
        (d / name).write_bytes(b)
        s = self.get(sid)
        s.setdefault("assets", {})[name] = {"w": im.width, "h": im.height, "alt": str(alt or "")[:200], "size": len(b)}
        with self._lock:
            (d / "site.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
        return name

    def _images(self, sid, s, mode):
        out = {}
        for name in (s.get("assets") or {}):
            f = self._dir(sid) / name
            if not f.exists():
                continue
            if mode == "preview":
                key = (str(f), f.stat().st_mtime)
                if key not in self._img_cache:
                    self._img_cache[key] = "data:image/webp;base64," + base64.b64encode(f.read_bytes()).decode()
                out[name] = self._img_cache[key]
            else:
                out[name] = name
        return out
