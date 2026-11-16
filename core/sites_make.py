"""«Сайты» — создание (часть Sites, чистое ядро 1.0.18): из шаблона или по описанию, своё имя и контакты, фото и
видео со страницы человека, тексты под дело человека (fill)."""
import copy
import json
import re
import secrets

import sites_kit as K
from sites_base import (
    clean_fields, FILL_SYSTEM, _json_in, log, _now, ref_outline, site_brief, SiteError, TAKE_MEDIA_RX, _uid)


class MakeMixin:
    # ---------- создание ----------

    def from_template(self, tid, name="", tagline="", contacts=None):
        tid = tid if tid in K.TEMPLATES else "personal"
        t = K.TEMPLATES[tid]
        s = {"id": secrets.token_hex(5), "template": tid, "name": (name or t["name"]).strip()[:80], "tagline": (tagline or t["tagline"]).strip()[:160],
             "theme": {"palette": t["palette"], "fonts": t["fonts"], "radius": t["radius"], "header": t["header"], "art": t["art"], "colors": {},
                       "style": t.get("style") or "classic"},
             "logo": {"text": (name or t["name"]).strip()[:60], "mark": t["logo"]["mark"], "style": t["logo"]["style"]},
             "menu": {"style": t["menu"]}, "contacts": dict(contacts if contacts is not None else t["contacts"]), "seo": {"description": ""},
             "pages": copy.deepcopy(t["pages"]), "assets": {}, "published": None, "created": _now()}
        for pg in s["pages"]:
            for b in pg["blocks"]:
                b["uid"] = _uid()
        if name and tid:
            for b in s["pages"][0]["blocks"]:
                if b["type"] == "hero" and b.get("variant") in ("poster", "center") and b.get("title") == t["name"]:
                    b["title"] = s["name"]               # обложка-афиша с названием — сразу своё
        return s

    def create(self, template="", describe="", name="", tagline="", contacts=None, fill=True, ref=""):
        """Новый сайт: шаблон (или по описанию), своё имя и контакты; тексты — моделью под дело человека.
        ref — сайт-образец (№552): его разделы и тон — подсказкой для шаблона и текстов, тексты и бренды — не копируем."""
        outline, media = "", {}
        if str(ref or "").strip():
            try:
                outline = ref_outline(str(ref).strip(), media=media)
            except SiteError as e:
                log.info("🌐 Сайт-образец не прочитался: %s", e)
        tid = template if template in K.TEMPLATES else K.pick_template(f"{describe} {name} {outline[:600]}")
        ct = {k: str(v).strip()[:200] for k, v in (contacts or {}).items() if k in K.CONTACT_KEYS and str(v or "").strip()}
        s = self.from_template(tid, name, tagline, ct if ct else (None if not describe else {}))
        if describe and not ct:
            s["contacts"] = {}                          # контактов человек не назвал — заглушки шаблона не оставляем
        s["describe"] = str(describe or "")[:3000]
        if outline:
            s["ref"] = str(ref).strip()[:300]
        (self.root / s["id"]).mkdir(parents=True, exist_ok=True)
        note = ""
        if fill and (describe or outline):
            try:
                note = self.fill(s, describe or s.get("name") or "", outline)
            except Exception as e:  # noqa: BLE001
                log.info("🌐 Тексты под дело не написались (оставила заготовки шаблона): %s", e)
                note = "тексты пока из шаблона — модель не ответила"
        s["logo"]["text"] = s["name"]
        self._save(s, f"Создан из шаблона «{K.TEMPLATES[tid]['title']}»")
        if media and TAKE_MEDIA_RX.search(str(describe or "")):
            try:                                        # «…и добавь с сайта фото и видео» — сайт его, просьба прямая
                s = self.take_media(s["id"], media, video=bool(re.search(r"видео|ролик", describe, re.I)),
                                    photo=bool(re.search(r"фото|картин|изображ|снимк", describe, re.I)))
            except SiteError as e:
                log.info("🌐 Фото и видео с образца не взялись: %s", e)
        s["_note"] = note
        return s

    def take_media(self, sid, media, photo=True, video=True):
        """Фото и видео со страницы человека (page_media) — на его сайт: первое фото — на обложку, остальные — в «Галерею»
        (нет — добавится), ролики — в «Видео» (нет — добавится). Только по прямой просьбе человека (TAKE_MEDIA_RX)."""
        s = self.get(sid)
        blocks = s["pages"][0]["blocks"]
        ops = []
        imgs = list(media.get("images") or [])[:9] if photo else []
        if imgs:
            hero = next((b for b in blocks if b["type"] == "hero"), None)
            if hero is not None:
                ops.append({"op": "image", "url": imgs.pop(0), "block": hero["uid"]})
            if imgs:
                gal = next((b for b in blocks if b["type"] == "gallery"), None)
                if gal is None:
                    gal = dict(K.blank_block("gallery"), uid=_uid(), items=[])
                    at = next((i for i, b in enumerate(blocks) if b["type"] in ("lead", "contacts")), len(blocks))
                    blocks.insert(at, gal)
                else:
                    gal["items"] = [x for x in gal.get("items") or [] if x.get("image")]
                ops += [{"op": "image", "url": u, "block": gal["uid"]} for u in imgs]
        vids = list(media.get("videos") or [])[:4] if video else []
        if vids:
            vb = next((b for b in blocks if b["type"] == "video"), None)
            if vb is None:
                vb = dict(K.blank_block("video"), uid=_uid())
                at = next((i for i, b in enumerate(blocks) if b["type"] in ("lead", "contacts")), len(blocks))
                blocks.insert(at, vb)
            vb["items"] = [{"url": u, "caption": ""} for u in vids]
        if not ops and not vids:
            return s
        self._save(s, "Фото и видео с сайта-образца")
        if ops:
            s = self.apply(sid, ops, "Фото с сайта-образца")
        return s

    def fill(self, s, describe, ref=""):
        """Модель переписывает тексты шаблона под дело человека (только его факты). ref — схема сайта-образца (№552)."""
        user = (f"ЧТО РАССКАЗАЛ ЧЕЛОВЕК:\n{describe}\n\n"
                + (f"САЙТ-ОБРАЗЕЦ, который человек привёл в пример (возьми только идею: какие разделы и в каком порядке, тон и "
                   f"длину текстов; НЕ копируй его тексты, названия, бренды, имена, цены, телефоны и адреса — всё своё, по делу "
                   f"человека):\n{ref}\n\n" if ref else "")
                + f"ШАБЛОН (uid блока — в квадратных скобках):\n{site_brief(s)}\n\n"
                "Верни JSON, как сказано. Блоки, которые не нужно менять, не включай.")
        d = _json_in(self.llm(FILL_SYSTEM, user, 3500))
        if not isinstance(d, dict):
            raise SiteError("модель не вернула JSON")
        if str(d.get("name") or "").strip():
            s["name"] = str(d["name"]).strip()[:80]
        if str(d.get("tagline") or "").strip():
            s["tagline"] = str(d["tagline"]).strip()[:160]
        if str(d.get("description") or "").strip():
            s.setdefault("seo", {})["description"] = str(d["description"]).strip()[:300]
        for k, v in (d.get("contacts") or {}).items():
            if k in K.CONTACT_KEYS and str(v or "").strip():
                s["contacts"][k] = str(v).strip()[:200]
        by = {b["uid"]: b for pg in s["pages"] for b in pg["blocks"]}
        # 0.94: «Цифры», «Полосы», «Кейсы» шаблона — чужие числа («1 400+ выпускников»): если модель их не переписала
        # числами человека, на сайт они не выходят (блок скрыт — человек включит, когда впишет свои)
        nums = {uid: json.dumps(b.get("items") or [], ensure_ascii=False) for uid, b in by.items() if b["type"] in ("stats", "bars", "cases")}
        for uid, f in (d.get("blocks") or {}).items():
            b = by.get(uid)
            if b is None or not isinstance(f, dict):
                continue
            f = clean_fields(f)
            if b["type"] in ("reviews",):
                f.pop("items", None)                     # отзывы — только от человека
            if b["type"] == "team" and "items" in f:
                for x in f["items"]:
                    x.setdefault("todo", True)
            b.update({k: v for k, v in f.items() if k not in ("type", "variant", "tone")})
        for uid, before in nums.items():
            if json.dumps(by[uid].get("items") or [], ensure_ascii=False) == before:
                by[uid]["hidden"] = True
        for b in s["pages"][0]["blocks"]:
            if b["type"] == "hero" and b.get("variant") == "poster" and len(str(b.get("title") or "")) > 24:
                b["variant"] = "split"                   # длинный заголовок на афише не помещается — вёрстка «текст и картинка»
        return ""

    def llm(self, system, user, max_tokens=2500):
        if self._llm:
            return self._llm(system, user)
        from llm import stream_chat
        h = self.host
        prof = h.s.active_llm() if h is not None else None
        if not (prof or {}).get("base_url") and (prof or {}).get("kind") != "ollama":
            raise SiteError("нет модели — выберите её в «Мозге»")
        return "".join(stream_chat(dict(prof, max_tokens=max_tokens, temperature=0.4), system, [{"role": "user", "content": user}]))
