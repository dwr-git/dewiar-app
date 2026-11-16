"""Подкасты — озвучка и сборка (часть Podcasts, чистое ядро 1.0.18): голоса ведущих, цепочка движков, озвучка реплик,
сведение, текст выпуска, ход работы и итог."""
import re
import time
from datetime import datetime
from podcast_base import (
    balance, detect_lang, DIGEST_AT, encode, fmt_dur, gap_after, jingle, log, _np, OUT_RATE, PodcastError,
    _safe_name, sentences, Stopped, STYLES, trim)


class VoiceMixin:
    # ---------- озвучка ----------

    def _voices(self, m):
        out = {}
        for k in ("a", "b"):
            h = m["hosts"][k]
            if hasattr(self.host, "_voice_cfg"):
                v = self.host._voice_cfg(h["id"])
            else:
                p = self.host.personas.get(h["id"])
                v = dict(p.get("voice") or {}, _gender=p.get("gender"), _pid=p.get("id"), _slot=0)
            out[k] = v
        return out

    def _chain(self, voice):
        """Голоса по порядку попыток: облако Dewiar (если подключено и человек не выбрал свой сервер голоса или ElevenLabs),
        потом голоса, которыми говорит сама Лира (в том числе при «Текстовом режиме» — прежний), Piper, eSpeak."""
        out = []
        cl = self._voice_cloud()
        if cl is not None:
            out.append(cl)
        f = getattr(self.host, "_engines_for_speech", None)
        if callable(f):
            try:
                out += [e for e in f(voice, True) if not (cl is not None and getattr(e, "cfg", {}).get("cloud"))]
            except Exception as e:  # noqa: BLE001
                log.info("Подкаст: голоса Лиры: %s", e)
        piper = getattr(self.host, "piper", None)
        if piper is not None and not any(e is piper for e in out):
            vid = voice.get("piper") or ("ru_RU-denis-medium" if voice.get("_gender") == "male" else "ru_RU-irina-medium")
            try:
                if piper.has(vid):
                    out.append(piper)
            except Exception:  # noqa: BLE001
                pass
        return out

    def _say(self, eng, text, voice, speed):
        """Одна реплика одним голосом -> int16 numpy OUT_RATE (длинная — по предложениям)."""
        np = _np()
        from tts import resample
        bits = []
        for piece in sentences(text):
            f = getattr(self.host, "_synth_mixed", None)
            gen = f(eng, piece, voice, speed) if callable(f) else eng.synth(piece, voice, speed)
            buf, rate = bytearray(), None
            for r_, pcm in gen:
                rate = rate or r_
                buf += pcm
            if not buf:
                raise RuntimeError("голос вернул пустоту")
            a = np.frombuffer(resample(bytes(buf), rate, OUT_RATE), dtype=np.int16)
            bits.append(trim(a))
            bits.append(np.zeros(int(0.16 * OUT_RATE), dtype=np.int16))
        return np.concatenate(bits[:-1]) if bits else np.zeros(0, dtype=np.int16)

    def _voice_all(self, job, lines):
        """Все реплики -> [int16 numpy]. Голос выпуска закрепляется за первым сработавшим (весь выпуск — одними голосами);
        сбой реплики — три повтора с паузой (голоса сервера бывают заняты), потом проще текст, потом следующий голос."""
        np = _np()
        from tts import RemoteTTS
        m = job["meta"]
        voices = self._voices(m)
        speed = float((self.host.s.get("tts") or {}).get("speed") or 1.0)
        chains = {k: self._chain(v) for k, v in voices.items()}
        if not any(chains.values()):
            raise PodcastError("нет голоса, чтобы озвучить: подключите «Голос Dewiar» (студия → «Голос») или скачайте голос Piper")
        locked = {}
        res = [None] * len(lines)
        failed = []

        def one(i, final=True):
            x = lines[i]
            v, chain = voices[x["who"]], chains[x["who"]]
            order = ([locked[x["who"]]] if x["who"] in locked else []) + [e for e in chain if e is not locked.get(x["who"])]
            if not final and x["who"] in locked:
                # владелец 11.11: «часть ответов Патрика — голосом Патрика, часть — другим движком, картавым и быстрым»:
                # голос сервера был занят, и реплика сразу уходила к запасному голосу. Теперь в первом проходе — только
                # закреплённый голос; не вышло — реплика ждёт второго прохода (сервер к тому времени освобождается)
                order = order[:1]
            for eng in order:
                for attempt in range(3 if eng is locked.get(x["who"]) or isinstance(eng, RemoteTTS) else 1):
                    if job["cancel"].is_set():
                        return
                    try:
                        pcm = self._say(eng, x["text"], v, speed)
                        if len(pcm):
                            locked.setdefault(x["who"], eng)
                            if isinstance(eng, RemoteTTS) and eng.cfg.get("cloud"):
                                m["usage"]["tts"] += len(x["text"])
                            res[i] = pcm
                            return
                    except Exception as e:  # noqa: BLE001
                        log.info("Подкаст: реплика %d (%s), попытка %d: %s", i + 1, getattr(eng, "name", eng), attempt + 1, e)
                    if job["cancel"].wait(1.5 * (attempt + 1) if isinstance(eng, RemoteTTS) else 0.1):
                        return
                try:                                   # простые буквы — тем же голосом
                    simple = re.sub(r"[^\wЁё ,.!?-]+", " ", x["text"]).strip()
                    if simple and simple != x["text"]:
                        pcm = self._say(eng, simple, v, speed)
                        if len(pcm):
                            res[i] = pcm
                            return
                except Exception:  # noqa: BLE001
                    pass
            (failed if final else later).append(i)

        later = []
        # первая реплика каждого ведущего — по очереди (закрепить голос), остальное — три сразу, если голос в облаке
        firsts = []
        for k in ("a", "b"):
            j = next((i for i, x in enumerate(lines) if x["who"] == k), None)
            if j is not None:
                firsts.append(j)
        done = 0
        for j in firsts:
            one(j)
            done += 1
        rest = [i for i in range(len(lines)) if i not in firsts]
        par = 3 if all(isinstance(locked.get(k), RemoteTTS) for k in locked) and locked else 1
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(par) as ex:
            for _ in ex.map(lambda i: one(i, final=False), rest):
                done += 1
                self._stage(job, "voice", done / max(1, len(lines)), f"реплика {done} из {len(lines)}")
        if later and not job["cancel"].wait(5):          # второй проход — по одной, тем же голосом; потом уже запасной
            for i in sorted(later):
                one(i, final=True)
        if job["cancel"].is_set():
            raise Stopped()
        alt = [i for i in range(len(lines)) if res[i] is not None and i in later]
        if alt:
            log.info("Подкаст: реплик со второго прохода — %d", len(alt))
        if len(failed) > max(2, len(lines) // 5):
            raise PodcastError("голос не справился с репликами — проверьте «Голос» в студии и нажмите «Продолжить»")
        m["voice"] = {k: getattr(e, "name", type(e).__name__) for k, e in locked.items()}
        return [r if r is not None else np.zeros(0, dtype=np.int16) for r in res]

    def _mix(self, job, lines, pcms):
        np = _np()
        import random
        m = job["meta"]
        pcms = balance(pcms, [x["who"] for x in lines])
        rnd = random.Random(m["id"])
        out, t = [], 0.0
        if m.get("intro", True):
            j = jingle()
            out += [j, np.zeros(int(0.35 * OUT_RATE), dtype=np.int16)]
            t = (len(j) + int(0.35 * OUT_RATE)) / OUT_RATE
        prev = ""
        for k, (x, pcm) in enumerate(zip(lines, pcms)):
            if k:
                g = gap_after(prev, x["text"], rnd.uniform(-1, 1))
                out.append(np.zeros(int(g * OUT_RATE), dtype=np.int16))
                t += int(g * OUT_RATE) / OUT_RATE
            x["t0"] = round(t, 2)
            out.append(pcm)
            t += len(pcm) / OUT_RATE
            x["t1"] = round(t, 2)
            if len(pcm):
                prev = x["text"]
        if m.get("intro", True):
            out += [np.zeros(int(0.7 * OUT_RATE), dtype=np.int16), jingle(short=True)]
        else:
            out.append(np.zeros(int(0.5 * OUT_RATE), dtype=np.int16))
        full = np.concatenate(out)
        self._stage(job, "mix", 0.3, "громкость и MP3")
        stem = _safe_name(m.get("title") or "Подкаст", 60)
        f = encode(full, job["dir"], stem, m.get("title") or "")
        for old in job["dir"].glob("*"):                   # прежний звук (повтор после «Продолжить») — прочь
            if old.is_file() and old != f and old.suffix.lower() in (".mp3", ".m4a", ".wav") and not old.name.startswith("."):
                if old.parent == job["dir"]:
                    old.unlink(missing_ok=True)
        m["audio"] = f.name
        m["duration"] = round(len(full) / OUT_RATE, 1)
        return f

    def _text_md(self, job):
        m = job["meta"]
        a, b = m["hosts"]["a"]["name"], m["hosts"]["b"]["name"]
        src = ", ".join(s.get("title") or s.get("name") for s in m.get("sources") or [] if not s.get("skipped"))
        head = [f"# {m.get('title')}", "", f"Подкаст Dewiar · ведут {a} и {b} · {STYLES[m['style']].lower()} · "
                f"{fmt_dur(m.get('duration')) if m.get('duration') else str(m['minutes']) + ' мин'}"]
        if src:
            head += ["", f"Материал: {src}"]
        if m.get("topic"):
            head += ["", f"Тема: {m['topic']}"]
        body = []
        for x in m.get("lines") or []:
            tm = f"[{fmt_dur(x['t0'])}] " if "t0" in x else ""
            body.append(f"{tm}**{a if x['who'] == 'a' else b}:** {x['text']}")
        tail = []
        if (m.get("checked") or {}).get("missing"):
            tail = ["", "---", "", "Не вошло в выпуск (по сверке с материалом): " + "; ".join(m["checked"]["missing"])]
        (job["dir"] / "Текст выпуска.md").write_text("\n".join(head + [""] + body + tail) + "\n", encoding="utf-8")

    def _run(self, job):
        m = job["meta"]
        try:
            self._stage(job, "read", 0)
            text, sources = self._gather(job)
            m["sources"] = sources
            m["lang_used"] = m["lang"] if m.get("lang") in ("ru", "en") else detect_lang(text or m.get("topic") or "")
            self._save(job)
            notes = text
            if len(text) > DIGEST_AT:
                self._stage(job, "digest", 0, "")
                notes = self._digest(job, text)
            self._stage(job, "plan", 0)
            plan = self._plan(job, notes)
            if plan.get("title") and m.get("title") != plan["title"]:
                m["title"] = plan["title"]
                self._emit(job, title=plan["title"])
                nd = job["dir"].with_name(f"{datetime.fromtimestamp(m['created']).strftime('%Y-%m-%d %H-%M')} {_safe_name(plan['title'], 60)}")
                if nd != job["dir"] and not nd.exists():
                    try:
                        job["dir"].rename(nd)
                        job["dir"] = nd
                    except OSError as e:                  # Windows: папку держит проводник — останется прежнее имя
                        log.info("Подкаст: папку не переименовала: %s", e)
            self._save(job)
            self._stage(job, "script", 0)
            lines = self._script(job, notes if text else "", plan)
            self._save(job)
            if text:
                self._stage(job, "check", 0)
                lines = self._check(job, notes, lines)
                self._save(job)
            self._text_md(job)
            self._stage(job, "voice", 0, f"реплика 0 из {len(lines)}")
            pcms = self._voice_all(job, lines)
            self._stage(job, "mix", 0)
            self._mix(job, lines, pcms)
            m["status"] = "done"
            m["done_at"] = int(time.time())
            m["cost"] = self._cost(job)
            self._save(job)
            self._text_md(job)
            self._finish(job)
        except Stopped:
            m["status"] = "stopped"
            self._save_quiet(job)
            self._finish(job, stopped=True)
        except PodcastError as e:
            m["status"], m["error"] = "error", str(e)
            self._save_quiet(job)
            self._finish(job, error=str(e))
        except Exception as e:  # noqa: BLE001
            log.exception("подкаст")
            m["status"], m["error"] = "error", f"сбой: {str(e)[:200]}"
            self._save_quiet(job)
            self._finish(job, error=m["error"])

    def _cost(self, job):
        us = job["meta"]["usage"]
        pr = self._price(job["prof"])
        out = {"tin": us["tin"], "tout": us["tout"], "tts": us["tts"]}
        tal = 0.0
        if pr:
            tal += (us["tin"] * pr[0] + us["tout"] * pr[1]) / 1e6
        if us["tts"]:
            tal += us["tts"] / 1000 * (pr[2] if pr else 0.002)
        if pr or us["tts"]:
            out["talers"] = round(tal, 4)
        return out

    def _save_quiet(self, job):
        try:
            self._save(job)
        except OSError:
            pass

    def _finish(self, job, stopped=False, error=""):
        m = job["meta"]
        job["status"] = m["status"]                       # сначала итог, потом «готово»: state() не увидит done с прежним статусом
        job["done"] = True
        self._index()
        self._emit(job, stage="end", pct=100 if m["status"] == "done" else job.get("pct", 0), status=m["status"], error=error,
                   stopped=stopped, duration=m.get("duration", 0), title=m.get("title"))
        if m["status"] == "done":
            title = m.get("title") or "Подкаст"
            try:
                if hasattr(self.host, "push"):
                    self.host.push("Подкаст готов", f"«{title}» — {fmt_dur(m.get('duration'))}. Слушать — студия → «Подкасты».",
                                   telegram=False)
                if job.get("announce") and hasattr(self.host, "announce"):
                    self.host.announce(f"Подкаст «{title}» готов — он в студии, в разделе «Подкасты».")
            except Exception:  # noqa: BLE001
                log.info("подкаст: уведомление", exc_info=True)
        elif error and job.get("announce") and hasattr(self.host, "announce"):
            try:
                self.host.announce(f"Подкаст не получился: {error}")
            except Exception:  # noqa: BLE001
                pass
