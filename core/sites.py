"""«Сайты» (03.11, владелец: «Лира должна научиться делать сайты… переделать сайт в любой момент — от структуры до дизайна —
одной командой; публикация на dewiar.pro — имя.dewiar.pro; аналитика и заявки — красиво; модерация — потом, в кабинете»).

Сайт — JSON (sites_kit — детали, sites_render — вёрстка):
  {id, name, tagline, template, theme: {palette, colors, fonts, radius, header, art}, logo: {text, mark, style, svg},
   menu: {style, cta}, contacts: {phone, email, address, hours, telegram, …}, seo: {description},
   pages: [{title, slug, description, blocks: [{uid, type, variant, tone, nav, id, …поля, items: […]}]}],
   assets: {"img/….webp": {w, h}}, published: {name, url, ts, status, reason}, created, updated}

Где лежит: STATE_DIR/sites/<id>/ — site.json, history/ (каждое изменение — версия, «верни как было» — откат), img/
(картинки, уже уменьшенные в webp), out/ (собранный сайт для просмотра в браузере).

Как меняется: apply(id, ops) — операции (палитра, шрифт, меню, добавить/убрать/переставить блок, поля блока, «другой
дизайн» — шаблон с сохранением текста…). say(id, фраза) — фраза человека: сначала простые правила (quick_ops: «тёмная
шапка», «строгий шрифт», «добавь цены», «меню бургером», «верни как было»), иначе — модель пишет операции (llm_ops).
create() — по описанию: шаблон по словам (sites_kit.pick_template), имя и контакты — из слов, тексты — модель
переписывает под дело человека (fill), без выдуманных отзывов, людей и цен.

Публикация — dewiar.pro (cloud.php → sites.php): /sites/check, /sites/publish (готовые файлы), /sites/stats (посещения
без cookie), /sites/leads (заявки с формы — раз в 2 минуты в «Клиенты», как «Чат для сайта»), /sites/remove, /sites/mine
(статус: заблокирован администратором и почему). Продвижение — audit(): заголовки, описания, h1/h2, alt, вес страниц,
контакты и форма, Open Graph, заглушки — понятными словами, у каждого пункта — фраза «исправь» для Лиры.
Части (чистое ядро, 1.0.18): sites_base — шаблоны, имена, быстрые операции, reach и fetch_image (подменять — там);
sites_make — создание; sites_edit — изменения и картинки; sites_out — вёрстка, публикация, заявки, «Статьи». Здесь —
хранение и история версий, для студии.
"""

import base64
import copy
import hashlib
import io
import json
import logging
import re
import secrets
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

import sites_kit as K
import sites_render as R  # noqa: F401 — как раньше: sites.R

from sites_base import (
    BLOCK_WORDS, chat_knowledge, clean_fields, clean_svg, _clip, code_to_video, COLOR_WORDS, _colors_in, EDIT_SYSTEM,
    EMBED_RX, fetch_image, FILL_SYSTEM, _find, FONT_WORDS, FONTS_DIR, HISTORY_MAX, _json_in, log, mix_hex,
    name_problem, NAME_RX, _now, OPS_HELP, ops_help, page_media, PALETTE_WORDS, quick_ops, reach, REACH_SAY,
    ref_outline, RESERVED, _simple, site_brief, SiteError, STYLE_WORDS, SVG_ATTRS, SVG_TAGS, TAKE_MEDIA_RX,
    TEMPLATE_WORDS, TEXT_MAX, translit, _uid, URL_RX, verify_code)  # noqa: F401 — прежние имена на месте
from sites_make import MakeMixin
from sites_edit import EditMixin
from sites_out import OutMixin


class Sites(MakeMixin, EditMixin, OutMixin):
    def __init__(self, root, host=None, llm=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.host = host
        self._llm = llm                         # тесты: llm(system, user) -> текст
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None
        self.recent = []                        # заявки с сайтов за сеанс (студия)
        self.error = ""
        self._img_cache = {}

    # ---------- хранение ----------

    def _dir(self, sid):
        if not re.fullmatch(r"[a-z0-9]{6,16}", str(sid or "")):
            raise SiteError("нет такого сайта")
        return self.root / sid

    def ids(self):
        return [d.name for d in sorted(self.root.iterdir()) if d.is_dir() and (d / "site.json").exists()] if self.root.exists() else []

    def get(self, sid):
        try:
            return json.loads((self._dir(sid) / "site.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise SiteError("нет такого сайта") from e

    def list(self):
        out = []
        for sid in self.ids():
            try:
                s = self.get(sid)
            except SiteError:
                continue
            out.append({"id": sid, "name": s.get("name"), "tagline": s.get("tagline"), "template": s.get("template"),
                        "updated": s.get("updated"), "created": s.get("created"), "published": s.get("published") or None,
                        "palette": (s.get("theme") or {}).get("palette"), "pages": len(s.get("pages") or []),
                        "blocks": sum(len(p.get("blocks") or []) for p in s.get("pages") or []),
                        "blog": {k: (s.get("blog") or {}).get(k) or 0 for k in ("on", "drafts", "live")}})
        return sorted(out, key=lambda x: -(x.get("updated") or 0))

    def find(self, who=""):
        """Сайт по имени или поддомену (пусто — последний изменённый). -> id."""
        items = self.list()
        if not items:
            raise SiteError("сайтов пока нет — скажите, какой сайт сделать")
        w = str(who or "").strip().lower()
        if not w:
            return items[0]["id"]
        for x in items:
            if w in (x["id"], ((x.get("published") or {}).get("name") or "")) or w in str(x.get("name") or "").lower():
                return x["id"]
        for x in items:
            if any(p for p in re.findall(r"\w{4,}", w) if p[:5] in str(x.get("name") or "").lower()):
                return x["id"]
        return items[0]["id"]

    def _save(self, s, label, to=None, merge=False):
        """Записать и положить версию в историю. merge — правка текста в студии: та же подпись в пределах 90 с не плодит
        версии, а обновляет последнюю (печатают по буквам)."""
        code_to_video(s)                               # код встраивания — не текстом, а разделом «Видео» (15.11)
        with self._lock:
            d = self._dir(s["id"])
            (d / "history").mkdir(parents=True, exist_ok=True)
            s["updated"] = _now()
            txt = json.dumps(s, ensure_ascii=False, indent=1)
            tmp = d / "site.json.tmp"
            tmp.write_text(txt, encoding="utf-8")
            tmp.replace(d / "site.json")
            idx = self._history(s["id"])
            if merge and idx and idx[-1]["label"] == str(label)[:120] and s["updated"] - idx[-1]["ts"] < 90 and len(idx) > 1:
                (d / "history" / f"{idx[-1]['v']:05d}.json").write_text(txt, encoding="utf-8")
                idx[-1]["ts"] = s["updated"]
                (d / "history" / "index.json").write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
                self._emit(s["id"])
                return s
            v = (idx[-1]["v"] + 1) if idx else 1
            (d / "history" / f"{v:05d}.json").write_text(txt, encoding="utf-8")
            idx.append({"v": v, "ts": s["updated"], "label": str(label or "Изменение")[:120], **({"to": to} if to else {})})
            for old in idx[:-HISTORY_MAX]:
                try:
                    (d / "history" / f"{old['v']:05d}.json").unlink()
                except OSError:
                    pass
            idx = idx[-HISTORY_MAX:]
            (d / "history" / "index.json").write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
        self._emit(s["id"])
        return s

    def _history(self, sid):
        try:
            return json.loads((self._dir(sid) / "history" / "index.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def history(self, sid):
        return self._history(sid)[::-1]

    def restore(self, sid, v):
        idx = self._history(sid)
        it = next((x for x in idx if x["v"] == int(v)), None)
        if not it:
            raise SiteError("такой версии нет")
        s = json.loads((self._dir(sid) / "history" / f"{it['v']:05d}.json").read_text(encoding="utf-8"))
        cur = self.get(sid)
        s["published"] = cur.get("published")                   # публикация — состояние, а не версия
        return self._save(s, f"Возврат к версии от {datetime.fromtimestamp(it['ts']).strftime('%d.%m %H:%M')}: {it['label']}", to=it["v"])

    def undo(self, sid):
        """«Верни как было»: на шаг назад от того, что сейчас. Откат — запись с to (к какой версии вернулись): её
        состояние — та версия, поэтому «ещё раз» идёт от неё дальше назад, а не к отменённой правке."""
        idx = self._history(sid)
        byv = {x["v"]: x for x in idx}
        cur = idx[-1] if idx else None
        while cur and cur.get("to") in byv:
            cur = byv[cur["to"]]
        pos = idx.index(cur) if cur in idx else 0
        if pos < 1:
            raise SiteError("раньше этого ничего не было — откатывать некуда")
        return self.restore(sid, idx[pos - 1]["v"])

    def delete(self, sid):
        s = self.get(sid)
        if (s.get("published") or {}).get("name"):
            try:
                self.unpublish(sid)
            except SiteError as e:
                log.info("🌐 Сайт удалён, но с dewiar.pro не снялся: %s", e)
        shutil.rmtree(self._dir(sid), ignore_errors=True)
        self._emit("")
        return {"ok": True}

    def _emit(self, sid):
        try:
            if self.host is not None:
                self.host.emit("sites", id=sid)
        except Exception:  # noqa: BLE001
            pass


    IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")

    # ---------- для студии ----------

    def meta(self):
        return {"templates": [{"id": k, "title": K.TEMPLATES[k]["title"], "sub": K.TEMPLATES[k]["sub"], "palette": K.TEMPLATES[k]["palette"],
                               "fonts": K.TEMPLATES[k]["fonts"], "name": K.TEMPLATES[k]["name"],
                               "style": K.TEMPLATES[k].get("style") or "classic"} for k in K.TEMPLATE_ORDER],
                "palettes": {k: {c: v[c] for c in ("title",) + K.COLOR_KEYS} for k, v in K.PALETTES.items()},
                "fonts": {k: {"title": v["title"], "sub": v["sub"], "head": v["head"], "body": v["body"], "hw": v["hw"], "italic": bool(v.get("italic"))}
                          for k, v in K.FONTS.items()},
                "styles": {k: {"title": v["title"], "sub": v["sub"]} for k, v in K.STYLES.items()},
                "radii": {k: v["title"] for k, v in K.RADII.items()}, "spaces": {k: v["title"] for k, v in K.SPACES.items()}, "menus": K.MENUS, "headers": K.HEADERS, "tones": K.TONES,
                "marks": {k: {"title": v[0], "svg": K.mark_svg(k)} for k, v in K.MARKS.items()}, "logo_styles": K.LOGO_STYLES,
                "contacts": K.CONTACT_KEYS,
                "legal": {"fields": K.LEGAL_FIELDS, "docs": {k: dict(v) for k, v in K.LEGAL_DOCS.items()}, "links_max": K.LEGAL_LINKS_MAX,
                          "text_max": K.LEGAL_TEXT_MAX},
                "blocks": {k: {"title": v["title"], "sub": v["sub"], "variants": v["variants"], "fields": v["fields"],
                               "items": v.get("items")} for k, v in K.BLOCKS.items()}}

    def template_preview(self, tid):
        s = self.from_template(tid)
        return R.page_html(s, 0, "preview")

    def artist_logos(self):
        """SVG из «Художника» (папка «Рисунки») — кандидаты в логотип."""
        try:
            ws = self.host.workspace.root() if self.host is not None else None
        except Exception:  # noqa: BLE001
            ws = None
        d = Path(ws) / "Рисунки" if ws else None
        if not d or not d.exists():
            return []
        out = []
        for f in sorted(d.glob("*.svg"), key=lambda p: -p.stat().st_mtime)[:24]:
            try:
                out.append({"name": f.stem, "svg": clean_svg(f.read_text(encoding="utf-8"), 64)})
            except (OSError, SiteError):
                continue
        return out

    def public(self, sid):
        s = self.get(sid)
        return {"site": s, "history": self.history(sid)[:40], "meta_v": 1}
