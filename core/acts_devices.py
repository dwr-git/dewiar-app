"""Свои устройства (часть Engine, чистое ядро 1.0.16): вход в облако, общее для своих устройств, «Взять мозги»,
поручения с телефона руководителя, своя память персонажа, мои компьютеры и задача на названный, «Устройства»."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка


class DevicesMixin:
    def credentials(self):
        """Чем входить в облако. -> (токен, ключ_для_связки, базовый адрес cloud.php).
        Токен — вход в аккаунт dewiar.pro, иначе ключ Dewiar. Если есть и то и другое, ключ отдаётся вторым, чтобы
        сервер связал его с аккаунтом. Адрес — из настроек, иначе из данных аккаунта (services.cloud)."""
        from cloud import base_of
        acc = self.account.token() if self.account.logged_in() else ""
        key = self.s.get("cloud", "key") or ""
        url = self.s.get("cloud", "url") or ""
        if not url and acc:
            svc = (self.account.data.get("services") or {}).get("cloud") or "/dwrapp/cloud.php"
            url = svc if svc.startswith("http") else (self.account.data.get("server") or "https://dewiar.pro").rstrip("/") + "/" + svc.lstrip("/")
        token = acc or key
        return token, (key if acc else ""), base_of(url)

    def _dewiar_web(self, kind, value):
        """Поиск (kind="search"), картинки (kind="images") или текст страницы (kind="fetch") через cloud.php — когда провайдер режет поисковик или сайт.
        Нужен вход в аккаунт dewiar.pro или ключ Dewiar, иначе RuntimeError. -> список результатов / текст."""
        import httpx
        if self.s.get("net", "web_via") is False:      # человек выключил запасной путь (письмо 19.10: рабочие данные — только напрямую)
            raise RuntimeError("запасной путь через сервер Dewiar выключен в настройках")
        token, _, url = self.credentials()
        if not token:
            raise RuntimeError("нет входа в аккаунт dewiar.pro и ключа Dewiar")
        p = {"p": "/" + kind, "q": value} if kind in ("search", "images") else {"p": "/fetch", "url": value}
        r = httpx.get(url, params=p, headers={"Authorization": "Bearer " + token}, timeout=40)
        try:
            d = r.json()
        except ValueError:
            d = {}
        if r.status_code != 200:
            raise RuntimeError((d.get("error") or {}).get("message") or f"сервер ответил {r.status_code}")
        return (d.get("results") or []) if kind in ("search", "images") else str(d.get("text") or "")

    # ---------- общее для своих устройств (close.own_send, сквозное шифрование): ключ умного дома ----------

    def own_snapshot(self):
        out = {}
        h = self.home.share()
        if h:
            out["home"] = h
        ha = self.ha.share() if getattr(self, "ha", None) else None
        if ha:
            out["ha"] = ha                         # Home Assistant: адрес и токен — тоже только конвертом своим устройствам
        k = self.sync_key.share() if getattr(self, "sync_key", None) else None
        if k:
            out["sync_key"] = k                    # ключ шифрования синхронизации — только своим устройствам, конвертом
        ml = self.mail.share() if getattr(self, "mail", None) else None
        if ml:
            out["mail"] = ml                       # почта с паролями приложений — только своим устройствам, конвертом (30.10)
        return out or None

    # ---------- «Взять мозги с другого устройства» (0.56; письмо 28.10: «на компе настроил — другие компы надо легко

    def brains_share(self):
        """Свои модели — своему устройству. Модель на этом же компьютере (127.0.0.1 — Ollama, LM Studio) другой не
        достанет (№871, 18.11: «не удаётся взять мозги с другого устройства», Ollama на 127.0.0.1): отдаём её по адресу
        этого компьютера в домашней сети (lan — тот проверит, отвечает ли), а нет такого адреса — только имя (local),
        чтобы там сказали, почему не пришло."""
        out, local = [], []
        lan = ""
        for pid, pr in (self.s.get("llm", "profiles") or {}).items():
            base = str(pr.get("base_url") or "")
            if not base or pr.get("cloud"):
                continue
            item = {k: pr.get(k) for k in ("name", "kind", "base_url", "api_key", "model", "economy", "title") if pr.get(k) not in (None, "")}
            if re.search(r"//(?:localhost|127\.|0\.0\.0\.0|\[::1\])", base):
                if lan == "":
                    try:
                        from homehub import lan_addresses
                        lan = (lan_addresses() or [None])[0] or None
                    except Exception:  # noqa: BLE001
                        lan = None
                if not lan:
                    local.append({"name": item.get("name") or item.get("model") or "модель", "base_url": base})
                    continue
                item["base_url"] = re.sub(r"//(?:localhost|127\.[\d.]+|0\.0\.0\.0|\[::1\])", "//" + lan, base, count=1)
                item["lan"] = True
            out.append(item)
        if not out and not local:
            return None
        return {"from": self.device_name(), "at": int(time.time() * 1000), "profiles": out[:12], **({"local": local[:6]} if local else {})}

    @staticmethod
    def brains_hint(base):
        """Что сделать на том компьютере, чтобы его модель была видна в домашней сети."""
        b = str(base or "")
        if ":11434" in b or "ollama" in b.lower():
            return "в Ollama на нём: Settings → «Expose Ollama to the network»"
        if ":1234" in b:
            return "в LM Studio на нём: Developer → Settings → «Serve on Local Network»"
        return "в программе модели на нём разрешите подключения из сети (не только с 127.0.0.1)"

    def brains_pull(self):
        """Попросить свои устройства прислать мозги; ответ примется 10 минут (own_apply). -> {sent}"""
        self._brains_until, self._brains_got, self._brains_miss = time.time() + 600, [], []
        try:
            sent = self.close.own_send({"want": ["brains"], "from": self.device_name()})
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"не отправилось: {e}") from e
        return {"sent": bool(sent), "until": int(self._brains_until)}

    def brains_status(self):
        return {"waiting": time.time() < getattr(self, "_brains_until", 0), "got": list(getattr(self, "_brains_got", [])),
                "miss": list(getattr(self, "_brains_miss", []))}

    def _brains_take(self, b):
        """Пришли мозги со своего устройства: добавить в профили те, которых нет (тот же адрес и модель — уже есть).
        Работающую модель не меняем; мозга не было — главной становится первая пришедшая. Модель того компьютера по
        домашней сети (lan) — только если отвечает отсюда; нет — в miss с подсказкой (№871)."""
        import hashlib
        profiles = dict(self.s.get("llm", "profiles") or {})
        have = {(str(x.get("base_url") or "").rstrip("/"), str(x.get("model") or "")) for x in profiles.values()}
        added, miss = [], []
        frm = str(b.get("from") or "другого устройства")[:40]
        for pr in (b.get("profiles") or [])[:12]:
            if not isinstance(pr, dict) or not str(pr.get("base_url") or "").startswith(("http://", "https://")):
                continue
            key = (str(pr["base_url"]).rstrip("/"), str(pr.get("model") or ""))
            if key in have:
                continue
            nm = str(pr.get("name") or "") or key[1] or "Модель"
            if pr.get("lan") and not self._brains_reach(key[0], str(pr.get("api_key") or "")):
                miss.append(f"«{nm}» на «{frm}» не отвечает по домашней сети — {self.brains_hint(key[0])}, и оба устройства — в одной сети")
                continue
            pid = "dev-" + hashlib.sha1("|".join(key).encode()).hexdigest()[:8]
            profiles[pid] = {k: str(pr.get(k) or "") for k in ("name", "kind", "base_url", "api_key", "model", "economy", "title")}
            profiles[pid]["name"] = nm
            have.add(key); added.append(nm)
        for lo in (b.get("local") or [])[:6]:
            if isinstance(lo, dict):
                miss.append(f"«{lo.get('name') or 'модель'}» работает только на самом «{frm}» (адрес 127.0.0.1) — {self.brains_hint(lo.get('base_url'))}")
        if miss:
            self._brains_miss = list(getattr(self, "_brains_miss", [])) + miss
            log.info("🧠 Мозги с «%s» не взялись: %s", frm, "; ".join(miss))
        if not added:
            if miss:
                self.emit("brains", data=self.brains_status())
            return []
        patch = {"profiles": profiles}
        if not self._has_own_brain() and not (self.s.get("llm", "active") or ""):
            patch["active"] = next(pid for pid in profiles if profiles[pid]["name"] == added[0])
        self.s.update({"llm": patch})
        self.emit("settings", settings=self.s.snapshot())
        log.info("🧠 Мозги со своего устройства «%s»: %s", b.get("from") or "?", ", ".join(added))
        try:
            self.push("Мозги с другого устройства", f"С «{b.get('from') or 'другого устройства'}» добавлено: {', '.join(added)}. Выбрать — «Мозг».", telegram=False)
        except Exception:  # noqa: BLE001
            pass
        return added

    @staticmethod
    def _brains_reach(base, key=""):
        """Отвечает ли модель по этому адресу (список моделей, 3 с)."""
        import httpx
        try:
            r = httpx.get(base.rstrip("/") + "/models", headers={"Authorization": f"Bearer {key}"} if key else {}, timeout=3.0)
            return r.status_code < 500
        except Exception:  # noqa: BLE001
            return False

    def _team_on(self):
        T = getattr(self, "team", None)
        return bool(T and (self.s.get("features") or {}).get("team") and T.connected() and getattr(self, "close", None))

    def team_changed(self):
        if not self._team_on() or getattr(self, "_team_pub_wait", False):
            return
        import threading
        self._team_pub_wait, t0 = True, time.time()

        def later():
            time.sleep(4)
            self._team_pub_wait = False
            if getattr(self, "_team_pub_at", 0) < t0:      # после изменения уже ушла доска с ответом на команду — хватит
                self._team_publish()
        threading.Thread(target=later, daemon=True).start()

    def _team_publish(self, res=None):
        if not self._team_on():
            return
        self._team_pub_at = time.time()
        body = {"team": dict(self.team.boss_snap(), dev=self.device_name())}
        if res:
            body["team_res"] = res
        self.close._own_quiet(body)

    def team_phone_cmd(self, c):
        """Команда с телефона руководителя -> выполнить здесь и ответить доской. Одна и та же (id) — один раз."""
        from team import TeamError
        cid, cmd, a = str(c.get("id") or "")[:40], str(c.get("cmd") or ""), c.get("a") if isinstance(c.get("a"), dict) else {}
        done = self.__dict__.setdefault("_team_cmds", [])
        if not cid or cid in done:
            return
        done.append(cid)
        del done[:-200]
        res = {"id": cid, "cmd": cmd, "ok": True}
        try:
            if cmd not in self.TEAM_CMDS:
                raise TeamError("этого с телефона не сделать")
            if time.time() * 1000 - float(c.get("ts") or 0) > 3 * 86400 * 1000:
                raise TeamError("команда пролежала больше трёх дней — повторите, если ещё нужно")
            T = self.team
            if cmd == "assign":
                r = T.assign(a.get("who") or "", a.get("title") or "", a.get("due") or "", a.get("note") or "", via="phone")
                res["name"] = r.get("name", "")
                res["sent"] = bool(r.get("sent") or r.get("repeat"))
            elif cmd == "back":
                T.back(a.get("id") or "", a.get("remark") or "")
            elif cmd == "message":
                T.message(a.get("who") or "", a.get("text") or "")
            else:
                getattr(T, cmd)(a.get("id") or "")
        except TeamError as e:
            res.update(ok=False, err=str(e))
        except Exception as e:  # noqa: BLE001
            log.warning("Поручения с телефона: %s", e, exc_info=True)
            res.update(ok=False, err="не получилось на компьютере")
        log.info("💼 Поручения с телефона: %s — %s", cmd, "готово" if res["ok"] else res.get("err"))
        self._team_publish(res)

    def own_apply(self, body):
        wm = (body or {}).get("watch_more")                  # «Дозор»: с телефона «Не то — ждать дальше»
        if isinstance(wm, dict) and hasattr(self, "watch_more"):
            try:
                self.watch_more(wm.get("id"), wm.get("why") or "")
            except Exception as e:  # noqa: BLE001
                log.info("👁 Дозор: «ждать дальше» не применилось: %s", e)
        if "watch" in ((body or {}).get("want") or ()) and hasattr(self, "_watch_publish"):   # №468: телефон спрашивает про «Дозор»
            self._watch_publish(True)
        if "team" in ((body or {}).get("want") or ()) and self._team_on():   # телефон руководителя открыл «Поручения»
            import threading
            threading.Thread(target=self._team_publish, daemon=True).start()
        tc = (body or {}).get("team_cmd")
        if isinstance(tc, dict) and self._team_on():
            import threading
            threading.Thread(target=self.team_phone_cmd, args=(dict(tc, ts=tc.get("ts") or (body or {}).get("ts") or 0),), daemon=True).start()
        if "brains" in ((body or {}).get("want") or ()):     # своё устройство просит мозги — отдаём, что есть
            share = self.brains_share()
            if share and getattr(self, "close", None):
                import threading
                threading.Thread(target=self.close._own_quiet, args=({"brains": share},), daemon=True).start()
        b = (body or {}).get("brains")
        if isinstance(b, dict) and time.time() < getattr(self, "_brains_until", 0):
            got = self._brains_take(b)
            if got:
                self._brains_got = list(getattr(self, "_brains_got", [])) + [{"from": b.get("from") or "", "names": got}]
                self.emit("brains", data=self.brains_status())
        h = (body or {}).get("home")
        if isinstance(h, dict) and self.home.adopt(h.get("token"), h.get("at")):
            self.emit("tools", tools=self.toolbox.catalog())
        ha = (body or {}).get("ha")
        if isinstance(ha, dict) and getattr(self, "ha", None) and self.ha.adopt(ha.get("url"), ha.get("token"), ha.get("at")):
            self.emit("tools", tools=self.toolbox.catalog())
            self.emit("ha", data=self.ha.public())
        ml = (body or {}).get("mail")
        if isinstance(ml, dict) and getattr(self, "mail", None) and self.mail.adopt(ml.get("boxes"), ml.get("at")):
            self.emit("tools", tools=self.toolbox.catalog())
            self.emit("mail", data=self.mail.public())
        k = (body or {}).get("sync_key")
        if isinstance(k, dict) and getattr(self, "sync_key", None) and self.sync_key.adopt(k.get("k"), k.get("at")):
            log.info("🔐 Ключ шифрования синхронизации получен со своего устройства")
            self.sync.key_arrived()

    def sync_key_wanted(self):
        """В облаке зашифрованное, а ключа здесь нет — попросить у своих устройств (не чаще раза в 10 минут)."""
        import time as _t
        if _t.time() - getattr(self, "_key_asked", 0) < 600 or not getattr(self, "close", None):
            return
        self._key_asked = _t.time()
        import threading
        threading.Thread(target=self.close._own_quiet, args=({"want": ["sync_key"]},), daemon=True).start()

    def note_rel_of(self, nid):
        """Заметка, пришедшая синхронизацией с id другого устройства, -> её путь в папке ассистента («Заметки/…») или None."""
        from sync import NOTES
        rel = (self.sync.state.get("map") or {}).get(str(nid))
        if rel and (self.workspace.ensure() / NOTES / rel).is_file():
            return f"{NOTES}/{rel}"
        return None

    def own_ask(self, what):
        """Попросить у своих устройств общее (почту, умный дом): ответят own_snapshot, когда будут на связи."""
        try:
            if getattr(self, "close", None) and self.credentials()[0]:
                self.close._own_quiet({"want": [what]})
        except Exception:  # noqa: BLE001
            log.debug("свои устройства: просьба не ушла", exc_info=True)

    def own_share(self):
        """Умный дом (Яндекс или Home Assistant) поменяли здесь — отправить своим устройствам (в фоне; нет связи — дойдёт со следующим изменением)."""
        snap = self.own_snapshot()
        if snap and self.credentials()[0]:
            import threading
            threading.Thread(target=self.close._own_quiet, args=(snap,), daemon=True).start()

    def device_name(self):
        """Имя этого компьютера в «Устройствах»: своё («Рабочий», «Домашний») или имя компьютера в системе."""
        from sync import default_device_name
        return (self.s.get("sync", "name") or "").strip()[:40] or default_device_name()

    # ---------- своя память у персонажа (0.56; письмо 28.10: «разные персонажи со своей памятью… пока это разные морды

    def own_memory(self):
        return [str(x) for x in (self.s.get("persona_memory", "own") or []) if x]

    def mem_owner(self):
        """Чья память сейчас: имя отвечающего персонажа, если у него своя, иначе "" (общая «Обо мне»)."""
        try:
            name = self.personas.get(self.s.get("persona"))["name"]
        except Exception:  # noqa: BLE001
            return ""
        return name if name in self.own_memory() else ""

    def persona_memory_set(self, name, own):
        name = (name or "").strip()[:40]
        if not name:
            raise ValueError("какой персонаж?")
        cur = [x for x in self.own_memory() if x != name] + ([name] if own else [])
        self.s.update({"persona_memory": {"own": cur, "at": int(time.time() * 1000)}})
        self.sync.soon.set()
        self.emit("settings", settings=self.s.snapshot())
        return {"own": cur}

    def computers(self):
        """Мои компьютеры из последней синхронизации (без облака): [{id, name, me, on, seen}] — для «сделай на рабочем…»."""
        out = []
        for d in self.sync.status.get("all") or []:
            if d.get("app") != "pc":
                continue
            me = bool(d.get("me"))
            out.append({"id": d.get("id", ""), "name": self.device_name() if me else (d.get("name") or "Компьютер"), "me": me,
                        "on": me or time.time() - float(d.get("seen") or 0) < 180, "seen": int(d.get("seen") or 0)})
        return out

    def find_computer(self, name):
        """«рабочий», «на рабочем компе», «Ноутбук» -> компьютер или None. Сначала точное имя, потом по началу слов."""
        q = [w[:5] for w in re.findall(r"[а-яёa-z0-9]+", (name or "").lower().replace("ё", "е"))
             if w not in ("на", "в", "мой", "моем", "моём", "моем", "компьютер", "компьютере", "комп", "компе", "пк", "ноуте")]
        comps = self.computers()
        for c in comps:
            if (c["name"] or "").lower().strip() == (name or "").lower().strip():
                return c
        best, score = None, 0
        for c in comps:
            ws = [w[:5] for w in re.findall(r"[а-яёa-z0-9]+", (c["name"] or "").lower().replace("ё", "е"))]
            sc = sum(1 for w in q if any(x.startswith(w[:4]) or w.startswith(x[:4]) for x in ws))
            if sc > score:
                best, score = c, sc
        return best

    def eyes_page(self, path, goal=""):
        """«Посмотреть глазами» (владелец 12.11: «посмотреть глазами важно — и в разделе, где она рисует и делает сайты»):
        страница результата (сайт, рисунок «Художника») — снимок экрана телефона модели со зрением: видно ли пустоту,
        наложения, обрезанное, нечитаемое, заглушки. -> что видно не так (коротко) или "" (всё видно как надо, браузера нет,
        модель без зрения — молча: не мешаем). Один и тот же файл с тем же содержимым дважды не смотрим."""
        import quality as Q
        from llm import LLMError, stream_chat, user_message
        p = Path(path)
        if not p.is_file():
            return ""
        prof = self.llm_profile() if hasattr(self, "llm_profile") else None
        if not prof:
            return ""
        key = f"{prof.get('base_url')}|{prof.get('model')}"
        if key in self._blind:
            return ""
        sig = (str(p), int(p.stat().st_mtime), p.stat().st_size)
        seen = getattr(self, "_eyes_seen", None)
        if seen is None:
            seen = self._eyes_seen = {}
        if sig in seen:
            return seen[sig]
        hc = Q.html_check([p], roots=[p.parent, p.parent.parent])
        v = (hc or {}).get(str(p)) or {}
        if not v.get("shot"):
            return ""
        try:
            raw = "".join(stream_chat(dict(prof, max_tokens=400, temperature=0, think="off"), Q.LOOK,
                                      [user_message(prof, f"Цель: {str(goal)[:400]}\nФайл: {p.name}", [v["shot"]])]))
        except LLMError as e:
            if re.search(r"image|vision|multimodal|картин|изображ", str(e), re.I):
                self._blind.add(key)
            return ""
        except Exception as e:  # noqa: BLE001
            log.info("Посмотреть глазами не вышло: %s", e)
            return ""
        r = Q.look_verdict(raw)
        out = r[1] if r and r[0] == "revise" else ""
        seen[sig] = out
        log.info("👀 Посмотрела на %s: %s", p.name, out or "видно как надо")
        return out

    def _talers_for_tokens(self, tokens):
        """Примерная цена задачи в талерах облака Dewiar (HARNESS 7: «план, срок, цена — начинаю?»): токены задачи — в
        основном вход (большая часть — из кэша), цены — те же, что у «Подкастов». Своя модель или цен нет — 0."""
        pc = getattr(self, "podcasts", None)
        if pc is None:
            return 0.0
        try:
            pr = pc._price(pc._profile())
        except Exception:  # noqa: BLE001
            return 0.0
        if not pr:
            return 0.0
        pin, pout = pr[0], pr[1]
        return round(float(tokens) / 1e6 * (0.85 * pin + 0.15 * pout), 2)

    def remote_task(self, on, title, goal, if_off=""):
        """Задача на названный компьютер. -> None (это он и есть — делать здесь) или текст для модели."""
        from sync import SyncError
        c = self.find_computer(on)
        names = ", ".join(f"«{x['name']}»" + (" (этот)" if x["me"] else " (на связи)" if x["on"] else " (не на связи)") for x in self.computers())
        if not c:
            raise ValueError(f"не нашла компьютер «{on}» среди ваших: {names or 'других компьютеров пока нет — подключите их в «Устройствах»'}")
        if c["me"]:
            return None
        if not c["on"] and if_off not in ("wait", "cloud"):
            ago = int((time.time() - c["seen"]) // 3600) if c["seen"] else 0
            return (f"Компьютер «{c['name']}» сейчас не на связи" + (f" (был {ago} ч назад)" if ago else "") + ". Спроси коротко: сделать, когда он "
                    "включится, или сейчас в облаке Dewiar? Ответ — снова start_task с тем же on и if_off: wait (когда включится) или cloud.")
        data = {"title": (title or goal[:50])[:80], "goal": goal[:4000]}
        if if_off == "cloud" and not c["on"]:
            data["cloud"] = True
        else:
            data["to"] = c["id"]
        try:
            self.sync.send_taskreq(data)
        except SyncError as e:
            raise ValueError(str(e)) from e
        if data.get("cloud"):
            return f"Задача «{data['title']}» ушла в облако Dewiar — «{c['name']}» не на связи. Результат появится в «Задачах». Скажи коротко, что взялась."
        return (f"Задача «{data['title']}» передана компьютеру «{c['name']}»" + (" — он возьмётся, как только включится." if not c["on"] else " — он уже берётся.")
                + " Ход и результат — на нём, в «Задачах». Результата ЕЩЁ НЕТ — скажи одной фразой, что передала.")

    def devices_public(self, fresh=True):
        """«Устройства» (0.56): это устройство, все мои устройства (с сайта, иначе — из последней синхронизации), синхронизация,
        как вошли (аккаунт или ключ) и можно ли выдать код. -> dict"""
        import httpx
        st = self.sync_public()
        tok, link, url = self.credentials()
        me = {"id": self.sync.state.get("device", ""), "name": self.device_name(), "app": "pc", "custom": bool(self.s.get("sync", "name"))}
        devs, err = list(st.get("all") or []), ""
        if tok and fresh:
            try:
                h = {"Authorization": "Bearer " + tok}
                if link and link != tok:
                    h["X-Sync-Link"] = link
                r = httpx.get(url, params={"p": "/sync/devices", "device": me["id"]}, headers=h, timeout=10)   # params заменяют ?p= в адресе — всё в params
                if r.status_code == 200:
                    devs = r.json().get("devices") or devs
            except Exception as e:  # noqa: BLE001
                err = str(e)
        if not any(d.get("me") for d in devs):
            devs.insert(0, {"id": me["id"], "name": me["name"], "app": "pc", "seen": st.get("at") or 0, "me": True})
        # одно устройство — одна строка (04.11: облачная запись телефона со старым временем перебивала свежую с узла
        # «Дома по Wi-Fi» — «второй компьютер видит смарт неактивным»): склеиваем по id, время — самое свежее
        merged = {}
        for d in devs:
            if not isinstance(d, dict):
                continue
            cur = merged.get(d.get("id"))
            if cur is None:
                merged[d.get("id")] = dict(d)
            elif int(d.get("seen") or 0) > int(cur.get("seen") or 0):
                cur.update(d, me=bool(cur.get("me") or d.get("me")))
        devs = list(merged.values())
        hs = getattr(self, "home_sync", None)              # телефоны по Wi-Fi (0.59) — в том же списке, с пометкой
        if hs is not None:
            for d in hs.status.get("all") or []:
                if d.get("me") or d.get("cloud") or not d.get("id"):    # cloud — узел знает о нём из облака, а не сам
                    continue
                cur = merged.get(d["id"])
                if cur is None:
                    cur = merged[d["id"]] = dict(d, home=True)
                    devs.append(cur)
                cur["home"] = True
                cur.pop("via", None)                       # «через этот же компьютер» здесь — просто «по Wi-Fi»
                if int(d.get("seen") or 0) > int(cur.get("seen") or 0):
                    cur["seen"] = int(d["seen"])
        for d in devs:
            if d.get("me"):
                d["name"] = me["name"]
        return {"me": me, "devices": devs, "sync": st, "home": self.home_public() if hasattr(self, "home_public") else None, "mode": "account" if self.account.logged_in() else ("key" if tok else ""),
                "login": (self.account.data.get("login") or "") if self.account.logged_in() else "", "can_pair": bool(tok), "error": err}

    # ---------- «Рядом — ещё одна Лира» (1.0.36; near.php) ----------

    def _near_post(self, path, body):
        import httpx
        tok, link, url = self.credentials()
        if not tok:
            raise ValueError("здесь нет входа в Dewiar")
        h = {"Authorization": "Bearer " + tok}
        if link and link != tok:
            h["X-Sync-Link"] = link
        try:
            r = httpx.post(url, params={"p": path}, json=dict(body, device=self.sync.state.get("device", "")), headers=h, timeout=20)
        except httpx.HTTPError as e:
            raise ValueError("сайт Dewiar не ответил — попробуйте через минуту") from e
        try:
            d = r.json()
        except ValueError:
            d = {}
        if r.status_code != 200:
            raise ValueError((d.get("error") or {}).get("message") or f"сайт ответил {r.status_code}")
        return d

    def near_ask(self, to):
        """Предложить устройству из той же сети стать одной Лирой: на нём появится вопрос, ответят там."""
        self._near_post("/sync/near/ask", {"to": to})
        n = next((x for x in self.sync.status.get("near") or [] if x.get("id") == to), {})
        for x in self.sync.status.get("near") or []:
            if x.get("id") == to:
                x["asked"] = int(time.time())
        log.info("🔗 Предложила «%s» стать одной Лирой", n.get("name") or to)
        return dict(self.devices_public(fresh=False), asked=n.get("name") or "")

    def near_answer(self, ask_id, yes):
        """Ответ на «давай станем одной Лирой». Да — данные этого устройства и того сливаются на сервере (ключи и балансы —
        у каждого свои), и синхронизация сразу забирает всё общее с начала."""
        d = self._near_post("/sync/near/answer", {"id": ask_id, "yes": bool(yes)})
        ask = next((x for x in self.sync.status.get("asks") or [] if x.get("id") == ask_id), {})
        self.sync.status["asks"] = [x for x in self.sync.status.get("asks") or [] if x.get("id") != ask_id]
        if d.get("linked"):
            self.sync.state["rev"] = 0
            if d.get("sid"):
                self.sync.state["sid"] = d["sid"]
            self.sync.soon.set()
            log.info("🔗 Одна Лира с «%s» — забираю общее", ask.get("from") or "другим устройством")
        return dict(self.devices_public(fresh=False), linked=bool(d.get("linked")), with_name=ask.get("from") or "")

    def near_asked(self, asks):
        """Синхронизация принесла новое «давай станем одной Лирой» — сказать человеку (раз на просьбу)."""
        for a in asks[:2]:
            name = a.get("from") or "другое устройство"
            try:
                self.chat.notify(f"🔗 «{name}» в этой же сети предлагает стать одной Лирой. Если это ваше устройство — ответьте "
                                 f"в студии, «Устройства»: память, заметки, дела и напоминания станут общими.")
            except Exception:  # noqa: BLE001
                log.info("🔗 «%s» предлагает стать одной Лирой", name)
            self.emit("devices_near", asks=asks)

    def last_act(self):
        """Когда человек последний раз говорил с Лирой здесь (сам, не через Telegram) — секунды эпохи или 0."""
        return int(getattr(self, "local_act", 0) or 0)

    def others_act(self):
        """Самый свежий разговор на других своих устройствах (по синхронизации) — секунды эпохи или 0."""
        me = self.sync.state.get("device", "")
        acts = [int(d.get("act") or 0) for d in self.sync.status.get("all") or [] if not d.get("me") and d.get("id") != me]
        hs = getattr(self, "home_sync", None)
        if hs is not None:
            acts += [int(d.get("act") or 0) for d in hs.status.get("all") or [] if not d.get("me")]
        return max(acts or [0])

    def sync_public(self):
        st = dict(self.sync.status)
        if st.get("error") and disk_full(st["error"]):    # пакет 04.11: «[Errno 28] No space left on device» — по-человечески
            st["error"] = "на диске нет места — синхронизация ждёт, пока его освободят (хотя бы 1 ГБ)"
        tok, _, _ = self.credentials()
        st["available"] = bool(tok)
        st["on"] = self.s.get("sync", "enabled") is not False
        st["e2e"] = self.sync.e2e_status()
        st["via"] = "аккаунту dewiar.pro" if self.account.logged_in() else ("ключу Dewiar …" + (self.s.get("cloud", "key") or "")[-4:] if tok else "")
        hid = self.s.get("sync", "near_hide") or {}
        st["near"] = [x for x in st.get("near") or [] if x.get("id") not in hid]
        return st
