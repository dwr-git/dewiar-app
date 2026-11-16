"""«Подкасты» (0.87; владелец 11.11, ориентир — Audio Overview в Google NotebookLM). Человек даёт материал — файлы (PDF,
Word, текст, книга EPUB/FB2), ссылку на страницу или видео YouTube, или просто тему словами — и через несколько минут
получает выпуск: двое ведущих (по умолчанию Лира и Патрик, их голосами) живо обсуждают тему, плюс текст выпуска.

Путь выпуска (поток «podcast», один выпуск за раз; ход — событием «podcast» {id, stage, pct, note, status}):
  read    — материал → текст (knowledge.extract с его пределами, EPUB/FB2/RTF — здесь; ссылки — httpx с пределом размера,
            адреса домашней сети не читаем; видео — субтитры video.transcript);
  digest  — длинный материал (> DIGEST_AT) — выжимка по частям (как разведчик explore: каждая часть — с чистого листа),
            много выжимок — ещё раз сводятся, чтобы не потерять важное из конца книги;
  plan    — план выпуска одним JSON: название, «крючок», 3–8 смысловых блоков, что унести;
  script  — сценарий по ролям частями (длинный — 2–4 захода с концом предыдущего), разбор parse_script;
  check   — второй проход: нет ли выдумок сверх материала и ошибок в фактах (только если материал есть) — правки по номерам;
  voice   — каждая реплика своим голосом (голос персонажа: облако Dewiar, если подключено, иначе голос этого компьютера;
            свой сервер голоса или ElevenLabs — если человек выбрал их);
  mix     — паузы (короче на подхватах), ровная громкость ведущих, заставка по желанию, ffmpeg: громкость по EBU R128
            (loudnorm) и MP3 (нет lame — M4A, нет ffmpeg — WAV).
Выпуск — папка «Подкасты/‹дата› ‹название›/» в папке ассистента: звук, «Текст выпуска.md», podcast.json (реплики с
временем — студия подсвечивает текущую), «_материал.txt» (для «Продолжить», если программу закрыли посреди работы).

Материал человека — данные, не инструкции: он идёт в блоке МАТЕРИАЛ, модели сказано не выполнять просьб из него, а
инструментов у этих запросов нет вовсе. Пределы — на число и размер файлов, длину текста и ссылок.
Части (чистое ядро, 1.0.18): podcast_base — постоянные, тексты для модели, чтение ссылок (подменять _addrs, _bad_ip,
_private — там); podcast_make — источники и сценарий; podcast_voice — озвучка и сборка. Здесь — папки и
список, ведущие, модель и цена, запуск и ход.
"""

import base64
import json
import logging
import math
import os
import re
import subprocess
import threading
import time
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from podcast_base import (
    _addrs, AUDIO_EXT, audio_ok, _bad_ip, balance, BLOCKS, CHARS_PER_MIN, CHECK_SYS, _clean, clean_meta, _COLOR_RX,
    DATA_RULE, detect_lang, DIGEST_AT, DIGEST_SYS, DOC_EXT, encode, _epub_text, estimate_tokens, FACTS_MAT,
    FACTS_TOPIC, _fb2_text, file_text, fmt_dur, FOLDER, gap_after, _html_text, ID_RX, jingle, _json, LENGTHS,
    LINE_MAX, _LOCAL_NAMES, log, material_ok, MAX_BYTES, MAX_FILE, MAX_FILES, MAX_TEXT, MAX_URLS, _NAME_BAD,
    _no_surrogates, NOTES_MAX, _np, _num, OUT_RATE, parse_script, PART, _PCT, PLAN_SYS, PodcastError, _private,
    REDUCE_SYS, rms, _rtf_text, _rtf_u, safe_get, _safe_name, SCRIPT_SYS, SEGMENTS, sentences, _split_long,
    _STAGE_RX, _STAGE_WORDS, STAGES, STATUSES, Stopped, _str, _strip_stage, STYLE_NOTE, STYLES, _subs_text,
    _sys_proxy, TOPIC_MAX, trim, _ts, URL_MAX, url_text)  # noqa: F401 — прежние имена на месте
from podcast_make import MakeMixin
from podcast_voice import VoiceMixin


class Podcasts(MakeMixin, VoiceMixin):
    """host: s (настройки), emit, workspace, personas; по возможности — llm_profile, _voice_cfg, _engines_for_speech,
    _synth_mixed, cloud, chat (Telegram/MAX), push, announce, health_use. Одновременно — один выпуск."""

    def __init__(self, host):
        self.host = host
        self.cur = None
        self._lock = threading.Lock()
        self._prices = (0.0, None)

    # ---------- папки и список ----------

    def root(self):
        r = Path(self.host.workspace.ensure()) / FOLDER
        r.mkdir(parents=True, exist_ok=True)
        return r

    def _dirs(self):
        try:
            return [d for d in self.root().iterdir() if d.is_dir() and (d / "podcast.json").is_file()]
        except OSError:
            return []

    def _find(self, pid):
        pid = str(pid or "")
        if not ID_RX.fullmatch(pid):
            raise PodcastError("нет такого выпуска")
        if self.cur and self.cur["id"] == pid:
            return self.cur["dir"]
        for d in self._dirs():
            try:
                if self._meta(d).get("id") == pid:
                    return d
            except (OSError, ValueError):
                continue
        raise PodcastError("выпуск не найден — может быть, его папку удалили")

    def _meta(self, d):
        """podcast.json -> проверенные поля (рецензия 0.87: файл лежит в папке человека, его могут подменить — в студию,
        к «На телефон» и к «Продолжить» идёт только то, что прошло проверку). Нет верного id — ValueError."""
        return clean_meta(json.loads((Path(d) / "podcast.json").read_text(encoding="utf-8")), Path(d))

    def _save(self, job):
        d = job["dir"]
        m = job["meta"]
        tmp = d / ".podcast.json.tmp"
        tmp.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(d / "podcast.json")

    def _rel(self, d):
        """Путь от папки ассистента («Подкасты/…») — для ws_open, ws_export, удаления."""
        root = Path(self.host.workspace.ensure())
        try:
            return Path(d).resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            return Path(d).relative_to(root).as_posix()

    def list(self):
        """Выпуски — новые сверху: [{id, title, status, created, minutes, style, duration, audio, folder, sources}]."""
        out = []
        live = self.cur["id"] if self.cur and not self.cur.get("done") else ""
        for d in self._dirs():
            try:
                m = self._meta(d)
            except (OSError, ValueError):
                continue
            st = m.get("status") or "working"
            if st == "working" and m.get("id") != live:
                st = "stopped"                            # программу закрыли посреди работы — можно продолжить
            out.append({"id": m.get("id"), "title": m.get("title") or d.name, "status": st, "created": m.get("created", 0),
                        "minutes": m.get("minutes"), "style": m.get("style"), "duration": m.get("duration", 0),
                        "audio": bool(m.get("audio")), "folder": self._rel(d), "sources": m.get("sources") or [],
                        "error": m.get("error", ""), "hosts": m.get("hosts") or {}})
        out.sort(key=lambda x: x["created"] or 0, reverse=True)
        self._index(out)
        return out

    def get(self, pid):
        d = self._find(pid)
        m = self._meta(d)
        m["folder"] = self._rel(d)
        if m.get("audio") and (d / m["audio"]).is_file():
            f = d / m["audio"]
            m["uri"] = f.as_uri()
            m["size"] = f.stat().st_size
            m["path"] = self._rel(f)
        return m

    def _index(self, items=None):
        """STATE_DIR/podcasts.json: id -> файл звука. По нему сервер окон отдаёт звук студии (/podcast-audio/<id>,
        ui/app.py): страница с http://127.0.0.1 не открывает file://."""
        try:
            from settings import STATE_DIR
            idx = {}
            for d in self._dirs():
                try:
                    m = self._meta(d)
                except (OSError, ValueError):
                    continue
                if m.get("audio") and (d / m["audio"]).is_file():
                    idx[m["id"]] = str((d / m["audio"]).resolve())
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            tmp = STATE_DIR / ".podcasts.json.tmp"
            tmp.write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
            tmp.replace(STATE_DIR / "podcasts.json")
        except OSError as e:
            log.info("Подкасты: список для окна не записался: %s", e)

    def delete(self, pid):
        if self.cur and self.cur["id"] == pid and not self.cur.get("done"):
            raise PodcastError("этот выпуск ещё готовится — сначала остановите")
        d = self._find(pid)
        self.host.workspace.remove_dir(self._rel(d))
        self._index()
        return True

    def send(self, pid):
        """«Отправить на телефон» — файлом в Telegram или MAX (куда владелец писал последним)."""
        m = self.get(pid)
        if not m.get("audio"):
            raise PodcastError("у выпуска ещё нет звука")
        chat = getattr(self.host, "chat", None)
        if chat is None or not chat.paired():
            raise PodcastError("чтобы выпуск пришёл на телефон, подключите Telegram или MAX: студия → «Подключение»")
        f = self._find(pid) / m["audio"]
        if f.stat().st_size > 49 * 1024 * 1024:
            raise PodcastError("файл больше 50 МБ — мессенджер его не примет; скачайте его и перенесите сами")
        chat.send_file(str(f), f"🎧 {m.get('title') or 'Подкаст'} · {fmt_dur(m.get('duration'))}")
        return {"to": getattr(chat, "title", "Telegram")}

    # ---------- кто ведёт ----------

    def hosts(self, pick=None):
        """-> [{id, name, gender, color}, …] ×2: выбранные, иначе Лира и Патрик; нет их — первая героиня и первый герой."""
        ps = [p for p in self.host.personas.all() if not p.get("kids")]
        by = {p["id"]: p for p in ps}
        want = [x for x in (pick or []) if x in by][:2]
        for d in ("lira", "patrik"):
            if len(want) < 2 and d in by and d not in want:
                want.append(d)
        for g in ("female", "male"):
            if len(want) < 2:
                x = next((p["id"] for p in ps if p.get("gender") == g and p["id"] not in want), None)
                if x:
                    want.append(x)
        for p in ps:
            if len(want) < 2 and p["id"] not in want:
                want.append(p["id"])
        if len(want) < 2:
            raise PodcastError("для подкаста нужны двое ведущих — добавьте персонажа в студии → «Персонажи»")
        return [{"id": i, "name": by[i].get("name") or i, "gender": by[i].get("gender") or "female",
                 "color": by[i].get("color") or "#8B7CFF"} for i in want]

    # ---------- модель и цена ----------

    def _profile(self):
        h = self.host
        prof = h.llm_profile() if hasattr(h, "llm_profile") else h.s.active_llm()
        if not prof or not prof.get("base_url") or prof.get("trial"):
            raise PodcastError("для подкаста нужен мозг — подключите облако Dewiar или свою модель: студия → «Мозг»")
        return dict(prof)

    def _cloud(self):
        return getattr(self.host, "cloud", None)

    def _price(self, prof):
        """(цена входа, выхода за 1 млн токенов, цена голоса за 1000 знаков) в талерах облака или None — своя модель."""
        from cloud import is_cloud
        if not is_cloud(prof):
            return None
        at, got = self._prices
        if got is None or time.monotonic() - at > 1800:
            got = {}
            try:
                d = self._cloud().models() if self._cloud() is not None else {}
                got = {"models": {m["id"]: (float(m.get("price_in") or 0), float(m.get("price_out") or 0)) for m in d.get("data") or []},
                       "tts": float(d.get("tts_price") or 0.002)}
            except Exception as e:  # noqa: BLE001 — нет связи: оценим без цены
                log.info("Подкаст: цены облака не узнала: %s", e)
            self._prices = (time.monotonic(), got)
        ms = got.get("models") or {}
        pin, pout = ms.get(prof.get("model")) or (next(iter(ms.values())) if ms else (0.0, 0.0))
        return pin, pout, got.get("tts", 0.002)

    def _voice_cloud(self):
        """Голос облака Dewiar для выпуска -> RemoteTTS или None (облако не подключено, стоп-кран, голос выбран свой)."""
        tt = self.host.s.get("tts") or {}
        if (self.host.s.get("privacy") or {}).get("local_only"):
            return None
        if tt.get("engine") in ("remote", "elevenlabs") and not (tt.get("remote") or {}).get("cloud"):
            return None                                   # свой сервер голоса или ElevenLabs — выбор человека
        c = self._cloud()
        key = getattr(c, "key", "") if c is not None else ""
        if not key:
            return None
        from cloud import api_base
        from tts import RemoteTTS
        return RemoteTTS({"base_url": api_base(c.url), "api_key": key, "model": "tts-1", "sample_rate": 24000, "voice_f": "", "voice_m": "",
                          "extra": {"response_format": "wav", "stream": False}, "cloud": True, "from_account": True})

    def estimate(self, minutes=10, text_chars=0, files=(), urls=0, topic=""):
        """Цена и время до старта. files — [{name, size}] (текст ещё не извлечён — оцениваем по размеру)."""
        minutes = int(minutes) if int(minutes or 0) in LENGTHS else 10
        chars = int(text_chars or 0)
        for f in files or ():
            ext = Path(str(f.get("name") or "")).suffix.lower()
            sz = int(f.get("size") or 0)
            chars += sz // 2 if ext in (".txt", ".md", ".srt", ".vtt", ".fb2", ".html", ".htm", ".rtf") else sz // 8 if ext == ".pdf" else sz // 3
        chars += int(urls or 0) * 15000
        has = bool(files) or bool(urls) or chars > 600
        chars = min(chars, MAX_TEXT)
        e = estimate_tokens(minutes, chars, has)
        out = {"minutes": minutes, "chars": chars, "tin": e["tin"], "tout": e["tout"], "tts": e["tts"], "cloud": False,
               "voice": "", "talers": None, "rub": None, "answers": None, "long": minutes >= 20 or chars > 150_000}
        try:
            prof = self._profile()
        except PodcastError as ex:
            out["error"] = str(ex)
            return out
        pr = self._price(prof)
        cloud_voice = self._voice_cloud() is not None
        eng = (self.host.s.get("tts") or {}).get("engine")
        out["voice"] = "голоса Dewiar" if cloud_voice else "голоса ElevenLabs" if eng == "elevenlabs" else \
            "голоса вашего сервера голоса" if eng == "remote" else "голоса этого компьютера"
        tal = 0.0
        if pr:
            out["cloud"] = True
            tal += (e["tin"] * pr[0] + e["tout"] * pr[1]) / 1e6
        if cloud_voice:
            tal += e["tts"] / 1000 * ((pr or (0, 0, 0.002))[2])
        if pr or cloud_voice:
            info = getattr(self._cloud(), "info", None) or {}
            out["talers"] = round(tal, 4)
            if info.get("rub"):
                out["rub"] = round(tal * float(info["rub"]), 1)
            if info.get("per_taler"):
                out["answers"] = max(1, int(round(tal * float(info["per_taler"]))))
            if info.get("balance") is not None and tal > float(info.get("balance") or 0):
                out["short"] = True                       # на балансе меньше, чем нужно
        # время: модель ~35 токенов/с на выходе + звук (облако — три реплики сразу, свой голос — по одной)
        speed = 120 if cloud_voice else 60
        out["wait"] = max(1, int(round((e["tout"] / 35 + e["calls"] * 4 + e["tts"] / speed) / 60)))
        return out

    # ---------- ход ----------

    def state(self):
        c = self.cur
        if not c:
            return None
        return {k: c.get(k) for k in ("id", "stage", "pct", "note", "done", "status", "title", "error")}

    def stop(self):
        c = self.cur
        if c and not c.get("done"):
            c["cancel"].set()
            return True
        return False

    def _emit(self, job, **kw):
        job.update({k: v for k, v in kw.items() if k in ("stage", "pct", "note", "status", "title", "error")})
        try:
            self.host.emit("podcast", id=job["id"], **{k: job.get(k) for k in ("stage", "pct", "note", "status", "title")}, **{
                k: v for k, v in kw.items() if k not in ("stage", "pct", "note", "status", "title")})
        except Exception:  # noqa: BLE001
            log.debug("подкаст: событие", exc_info=True)

    def _stage(self, job, stage, frac=0.0, note=""):
        if job["cancel"].is_set():
            raise Stopped()
        a, b = _PCT[stage]
        pct = int(a + (b - a) * max(0.0, min(1.0, frac)))
        if stage != job.get("stage") or pct != job.get("pct") or note != job.get("note"):
            job["meta"]["stage"] = stage
            self._emit(job, stage=stage, pct=pct, note=note)

    def start(self, src=None, opts=None, announce=False, resume=""):
        """src: {topic, urls: [...], files: [{name, b64}], paths: [...]}; opts: {minutes, style, hosts, lang, intro}.
        resume — id прерванного выпуска: продолжить с того, что уже готово. -> {id, title, estimate}."""
        src, opts = dict(src or {}), dict(opts or {})
        with self._lock:
            if self.cur and not self.cur.get("done"):
                raise PodcastError("уже готовлю выпуск — дождитесь или остановите его")
            prof = self._profile()
            info = getattr(self._cloud(), "info", None) or {}
            from cloud import is_cloud
            if is_cloud(prof) and info.get("empty"):
                raise PodcastError("на ИИ-балансе пусто — пополните его (студия → «Dewiar.pro»), и подкаст получится")
            if resume:
                d = self._find(resume)
                meta = self._meta(d)
                if meta.get("status") == "done" and meta.get("audio"):
                    raise PodcastError("этот выпуск уже готов")
                meta["status"] = "working"
                meta.pop("error", None)
            else:
                topic = re.sub(r"[ \t]+", " ", str(src.get("topic") or "")).strip()
                if len(topic) > TOPIC_MAX:
                    raise PodcastError(f"тема и пожелания — до {TOPIC_MAX} знаков; длинный текст положите файлом")
                urls = [u.strip() for u in (src.get("urls") or []) if str(u or "").strip()]
                # ссылки, вставленные прямо в тему, — тоже материал
                for u in re.findall(r"https?://\S+", topic):
                    if u.rstrip(".,;)»") not in urls:
                        urls.append(u.rstrip(".,;)»"))
                topic = re.sub(r"https?://\S+", " ", topic).strip()
                files = list(src.get("files") or [])
                paths = [str(p) for p in (src.get("paths") or []) if str(p or "").strip()]
                if len(urls) > MAX_URLS:
                    raise PodcastError(f"ссылок — не больше {MAX_URLS}")
                if len(files) + len(paths) > MAX_FILES:
                    raise PodcastError(f"файлов — не больше {MAX_FILES} за раз")
                if not topic and not urls and not files and not paths:
                    raise PodcastError("дайте материал: файл, ссылку или тему словами")
                if len(topic) < 3 and not urls and not files and not paths:
                    raise PodcastError("тема слишком короткая — скажите, о чём выпуск")
                minutes = int(opts.get("minutes") or 10)
                minutes = minutes if minutes in LENGTHS else 10
                style = opts.get("style") if opts.get("style") in STYLES else "simple"
                hs = self.hosts(opts.get("hosts"))
                pid = uuid.uuid4().hex[:10]
                draft = topic or (Path(str((files[0] if files else {}).get("name") or (paths[0] if paths else ""))).stem) or \
                    re.sub(r"^https?://(www\.)?", "", urls[0] if urls else "")[:40]
                d = self.root() / f"{datetime.now().strftime('%Y-%m-%d %H-%M')} {_safe_name(draft, 40)}"
                n = 2
                while d.exists():
                    d = d.with_name(f"{d.name} ({n})")
                    n += 1
                found = [self._resolve_path(x) for x in paths]      # не нашлось — сразу понятный ответ, до папки выпуска
                d.mkdir(parents=True)
                meta = {"id": pid, "title": _safe_name(draft, 60), "status": "working", "created": int(time.time()), "minutes": minutes,
                        "style": style, "lang": opts.get("lang") if opts.get("lang") in ("ru", "en") else "auto",
                        "intro": opts.get("intro", True) is not False, "topic": topic, "urls": urls,
                        "hosts": {"a": hs[0], "b": hs[1]}, "sources": [], "usage": {"tin": 0, "tout": 0, "tts": 0}}
                try:
                    meta["files"] = self._save_files(d, files) + self._copy_files(d, found)
                except Exception:
                    import shutil
                    shutil.rmtree(d, ignore_errors=True)
                    raise
            job = {"id": meta["id"], "dir": d, "meta": meta, "cancel": threading.Event(), "done": False, "prof": prof,
                   "announce": bool(announce), "stage": "", "pct": 0, "note": "", "status": "working", "title": meta["title"]}
            self.cur = job
            self._save(job)
        threading.Thread(target=self._run, args=(job,), name="podcast", daemon=True).start()
        use = getattr(self.host, "health_use", None)
        if callable(use):
            try:
                use("podcast_voice" if announce else "podcast")
            except Exception:  # noqa: BLE001
                pass
        self._emit(job, stage="read", pct=0, status="working", started=True)
        return {"id": job["id"], "title": meta["title"], "minutes": meta["minutes"], "hosts": meta["hosts"]}
