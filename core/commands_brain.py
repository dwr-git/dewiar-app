"""Команды окон (студия, виджет, телефон): настройки, «Мозг» (проверка, модели, запасной), облако Dewiar, звонки, «Близкие», приглашения и
заявки, Сеть Лиры, сеть и прокси, SSH, устройство, антивирус, папка ассистента (дерево).
Часть разбора CommandsMixin.command (core/engine_commands.py; чистое ядро, 1.0.9 — docs/CORE_PLAN.md): ветки
проверяются по порядку, как раньше в одном методе; команда не своя — NotImplemented, и разбор идёт дальше."""
from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка


class BrainCommands:
    def _cmd_brain(self, cmd, a):
        if cmd == "settings_save":
            before = self.s.snapshot()
            self.s.update(a["patch"])
            after = self.s.snapshot()
            if "audio" in a["patch"] and hasattr(self, "_end_frames"):
                self._pause_apply()                              # пауза конца фразы — сразу, без перезапуска слуха
            if before["llm"].get("active") != after["llm"].get("active") or \
                    before["llm"].get("profiles") != after["llm"].get("profiles"):
                self.probe_tools_bg()
            if before["llm"].get("active") != after["llm"].get("active"):
                self._brain_manual = time.monotonic()           # модель выбрали сами — автоматика час её не трогает
                if after["llm"].get("auto_from"):
                    self.s.update({"llm": {"auto_from": ""}})
            if "engine" in (a["patch"].get("stt") or {}) and after["stt"].get("auto_from"):
                self.s.update({"stt": {"auto_from": ""}})       # №513: распознавание выбрали сами — временной замены больше нет
            if before["tts"].get("engine") != after["tts"].get("engine") and "engine" in (a["patch"].get("tts") or {}) \
                    and "auto_piper" not in (a["patch"].get("tts") or {}) and after["tts"].get("auto_piper"):
                self.s.update({"tts": {"auto_piper": 0}})       # голос выбрали сами — автоматика больше не решает
            if before["all_names"] != after["all_names"]:
                self.build_spotter()
            if before["audio"]["input"] != after["audio"]["input"] or \
               before["audio"]["output"] != after["audio"]["output"] or \
               before["audio"]["echo_cancel"] != after["audio"]["echo_cancel"] or \
               before["audio"].get("headphones") != after["audio"].get("headphones") or \
               before["audio"].get("soft_aec") != after["audio"].get("soft_aec"):
                self.restart_audio.set()                         # устройства звука меняются только перезапуском потока звука
            self.apply_engines()
            self.voiceprints.sensitivity = float(self.s.get("audio", "name_sensitivity") or 1.0)
            self.mcp.reconcile()
            if isinstance(self.stt, GigaAMSTT) and not self.stt.ready and not self.stt.loading:
                threading.Thread(target=self._background_loads, daemon=True).start()
            elif after["tts"]["engine"] == "piper":
                threading.Thread(target=self.ensure_voice, args=(after["persona"],), daemon=True).start()
            self.emit("settings", settings=after)
            return after
        if cmd == "llm_test":
            prof = a.get("profile") or {}
            import net
            with net.profile_proxy(prof):                # свой прокси профиля (21.11) — и в проверке до сохранения
                r = test_profile(prof)
            if r.get("tools_mode"):
                key = self._tools_key(dict(prof, model=prof.get("model") or ""))
                # проверка заодно узнала, как этот сервер принимает инструменты, — запомним, чтобы не проверять снова
                self.s.update({"llm": {"tools_modes": {key: r["tools_mode"]}}})
            return r
        if cmd == "own_fallback":                         # «Если своя модель не отвечает — отвечать через Dewiar» (29.10)
            on = bool(a.get("on"))
            self.s.update({"llm": {"own_fallback": on}})
            ready = bool((self.s.get("llm", "profiles") or {}).get("dewiar-cloud"))
            if on and not ready:
                try:
                    ready = self.standby_join()
                except Exception as e:  # noqa: BLE001 — нет сети: настройка остаётся, подключим, когда спросят снова
                    return {"on": on, "ready": False, "error": f"не получилось подключить мозг Dewiar: {e}"}
            return {"on": on, "ready": ready}
        if cmd == "llm_models":
            import net
            with net.profile_proxy(a.get("profile") or {}):
                return list_models(a.get("profile") or {})
        if cmd == "llm_economy_suggest":                  # экономный режим: недорогая модель того же сервиса (economy.py)
            import economy
            pr = a.get("profile") or {}
            try:
                import net
                with net.profile_proxy(pr):
                    ms = list_models(pr)
            except Exception as e:  # noqa: BLE001
                return {"model": "", "error": str(e)[:200]}
            return {"model": economy.suggest(ms, pr.get("model") or ""), "count": len(ms)}
        if cmd == "llm_no_chat":                          # №258: в списке нет ни одной модели для разговора — что делать
            from llm import no_chat_help
            return no_chat_help((a.get("profile") or {}).get("base_url", ""), a.get("models") or [])
        if cmd in ("cloud_usage", "cloud_topup", "cloud_topup_send", "cloud_limits", "cloud_autopay", "cloud_company", "cloud_models", "cloud_model", "cloud_stt", "cloud_tts", "cloud_fallback"):
            from cloud import CloudError
            try:
                if cmd == "cloud_usage":
                    return self.cloud.usage()
                if cmd == "cloud_topup":
                    return self.cloud.topup_info()
                if cmd == "cloud_company":                 # «Компания»: войти по коду, места, приглашения, лимиты (пилот 18.11)
                    return self.cloud.company(a)
                if cmd == "cloud_autopay":                 # 1.0.32: автопополнение (правила, вкл/выкл, забыть карту)
                    return self.cloud.autopay_set(a)
                if cmd == "cloud_limits":                  # 1.0.31: свои лимиты трат — день и месяц (0 — без лимита)
                    return self.cloud.limits_set(a.get("day"), a.get("month"))
                if cmd == "cloud_topup_send":
                    return self.cloud.topup_request(a.get("amount") or 0, a.get("note", ""), a.get("image", ""))
                if cmd == "cloud_models":
                    return self.cloud.models()
                if cmd == "cloud_model":
                    r = self.cloud.set_model(a.get("id", ""))
                elif cmd == "cloud_stt":
                    r = self.cloud.set_stt(bool(a.get("on")))
                    self.s.update({"stt": {"auto_from": ""}})   # №513: выбрали сами — это уже не временная замена
                    if not a.get("on") and self._stt_local() != "gigaam":
                        self.s.update({"stt": {"engine": self._stt_local()}})
                        r = self.s.get("stt")
                    self.apply_engines()
                elif cmd == "cloud_tts":                  # «Голос Dewiar» — тот же, что на телефоне
                    r = self.cloud.set_tts(bool(a.get("on")), self._tts_local())
                    self.apply_engines()
                else:
                    self.s.update({"llm": {"fallback": a.get("id") or ""}})
                    r = {"fallback": a.get("id") or ""}
                self.emit("settings", settings=self.s.snapshot())
                return r
            except CloudError as e:
                raise ValueError(str(e)) from e
        if cmd in ("call_info", "call_sig", "call_ice", "call_fast", "call_done"):    # страница звонка (ui/call.html)
            from close import CloseError
            try:
                return self.close.call_cmd(cmd, a)
            except CloseError as e:
                raise ValueError(str(e)) from e
        if cmd.startswith("close_"):                   # «Близкие» (close.py): студия
            from close import CloseError
            c = self.close
            try:
                if cmd == "close_state":
                    if a.get("hello") or not c.st.get("me"):
                        try:
                            c.hello()
                        except CloseError as e:
                            c.error = str(e)
                    return c.state()
                if cmd == "close_invite":
                    return c.invite(bool(a.get("renew")))
                if cmd == "close_peek":
                    return c.peek(a.get("link", ""))
                if cmd == "close_accept":
                    return c.accept(a.get("link", ""))
                if cmd == "close_refs":
                    return c.ref_map(a.get("rids") or [])
                if cmd == "close_ref":
                    return c.ref_close(a.get("rid", ""))
                if cmd == "close_offer":
                    return c.offer(a.get("pid", ""), a.get("yes"))
                if cmd == "close_remove":
                    return c.remove(a.get("pid", ""))
                if cmd == "close_rename":           # №128: своё имя близкого (только здесь); пустое — как он сам себя назвал
                    return c.rename(a.get("pid", ""), a.get("name", ""))
                if cmd == "close_forget":           # убрать сообщения у себя: mids — выбранные, без mids — всю переписку
                    mids = a.get("mids")
                    return c.forget(a.get("pid", ""), None if mids is None else list(mids))
                if cmd == "close_history":           # read: false — окно студии скрыто, «прочитано» не ставим
                    return c.history(a.get("pid", ""), mark_read=a.get("read", True) is not False)
                if cmd == "close_send":
                    files = list(a.get("files") or [])
                    if a.get("files_b64"):                # студия: файл, выбранный в окне, — во временную папку и отправить
                        import base64 as _b64
                        import re as _re
                        # 28.10 (владелец: «отправил фото в группу — не отображается»): файл лежал во временной папке
                        # программы, а студия показывает фото только из «Близких» — теперь отправленное хранится там же
                        out = Path(self.workspace.ensure()) / "Близкие" / "Отправленные" / time.strftime("%Y-%m-%d %H-%M-%S")
                        out.mkdir(parents=True, exist_ok=True)
                        for f in a["files_b64"][:5]:
                            name = _re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", str(f.get("name") or "файл"))[:120] or "файл"
                            (out / name).write_bytes(_b64.b64decode(f.get("b64") or ""))
                            files.append(str(out / name))
                    return c.send(a.get("pid", ""), a.get("text", ""), files)
                if cmd == "close_meet":             # «Встречи» в студии (studio/meet.js) — через то же пространство, что телефон
                    return c.meet(a.get("path", ""), a.get("body") or {})
                if cmd == "close_forward":          # «Переслать» (0.62): {pid — откуда, mid, to — кому: pid или gid}
                    return c.forward(a.get("pid", ""), a.get("mid", ""), a.get("to", ""))
                if cmd == "close_group":            # «Группы своих»: create / rename / icon / add / drop / leave / delete
                    return c.group(str(a.get("op") or ""), **{k: a[k] for k in ("gid", "name", "pids", "pid", "icon") if k in a})
                if cmd == "close_thumb":            # фото из переписки — картинкой в студии (0.61): только скачанное в «Близкие», до 6 МБ
                    import base64 as _b64
                    import mimetypes as _mt
                    bases = ((Path(self.workspace.root) / "Близкие").resolve(), (STATE_DIR / "close_out").resolve())   # и отправленное до 0.66
                    p = Path(str(a.get("path") or "")).resolve()
                    t = _mt.guess_type(p.name)[0] or ""
                    if not any(b in p.parents for b in bases) or not t.startswith("image/") or not p.is_file() or p.stat().st_size > 6 * 1024 * 1024:
                        return {"data": ""}
                    return {"data": f"data:{t};base64," + _b64.b64encode(p.read_bytes()).decode()}
                if cmd == "close_wave":             # 👋 с радара «Рядом»
                    return c.wave(a.get("pid", ""))
                if cmd == "close_react":            # реакция на сообщение (👍 ❤️ …)
                    return c.react(a.get("pid", ""), a.get("mid", ""), a.get("e", ""))
                if cmd == "close_call":
                    return c.call(a.get("pid", ""), bool(a.get("video")))
                if cmd == "close_name":
                    return c.set_name(a.get("name", ""))
                if cmd == "close_card":             # карточка «Я»: имя, о себе, фото, фото во «Встречах»
                    return c.set_card(**{k: a[k] for k in ("name", "about", "face", "face_meet") if k in a})
                if cmd == "close_face":             # фото близкого (или во «Встречах»: meet) -> data URI
                    return c.face(a.get("pid", ""), a.get("v", 0), meet=bool(a.get("meet")))
                if cmd == "close_speak":
                    self.s.update({"close": {"speak": bool(a.get("on"))}})
                    return {"speak": bool(a.get("on"))}
                if cmd == "close_poll":
                    c.soon.set()
                    return {"ok": True}
            except CloseError as e:
                raise ValueError(str(e)) from e
            raise ValueError("неизвестная команда «Близких»")
        if cmd in ("ref_info", "ref_use"):              # приглашения друзей (cloud.php ?p=/ref): мой код, кто пришёл, чужой код
            from cloud import CloudError, fetch
            token, _, base = self.credentials()
            if not token:
                raise ValueError("сначала подключите Dewiar: вход аккаунтом dewiar.pro или ключ")
            try:
                if cmd == "ref_info":
                    return fetch(base, token, "/ref")
                code = "".join(ch for ch in str(a.get("code", "")).upper() if ch.isalnum())
                if len(code) < 4:
                    raise ValueError("введите код из приглашения — 6 букв и цифр")
                r = fetch(base, token, "/ref/use", body={"code": code})
                try:
                    self.cloud.refresh()
                except Exception:  # noqa: BLE001
                    pass
                return r
            except CloudError as e:
                raise ValueError(str(e)) from e
        if cmd in ("join_send", "join_check", "join_forget", "pair_new", "contact_get", "contact_set", "auto_join"):   # Dewiar по заявке и перенос кодом
            from cloud import CloudError
            try:
                if cmd == "contact_get":            # автоподключение (0.69): как к вам обращаться и как связаться — дополнить позже
                    return self.contact_get()
                if cmd == "contact_set":
                    return self.contact_set(a.get("name", ""), a.get("contact", ""))
                if cmd == "auto_join":
                    self.s.update({"cloud": {"auto_tried": 0}})
                    return {"ok": self.auto_join("кнопкой"), "llm": bool(self.s.get("llm", "active"))}
                if cmd == "join_send":
                    return self.join_send(a.get("name", ""), a.get("contact", ""), a.get("note", ""))
                if cmd == "join_check":
                    return self.join_check()
                if cmd == "join_forget":
                    self.s.update({"cloud": {"join": {"id": 0, "secret": "", "url": ""}}})
                    return True
                return self.pair_new()
            except CloudError as e:
                raise ValueError(str(e)) from e
        if cmd.startswith("lnode_"):                  # «Нода Лиры» (0.87): компьютер сам отвечает на общие вопросы сети (liranode.py)
            import liranode
            return liranode.command(self, cmd, a)
        if cmd.startswith("lnet_"):                   # «Сеть Лиры»: правила с подписью, «Мой узел», приглашение узла (liranet.py)
            import liranet
            try:
                return liranet.command(self, cmd, a)
            except liranet.NetError as e:
                raise ValueError(str(e)) from e
        if cmd in ("cloud_connect", "cloud_status", "cloud_forget"):
            from cloud import CloudError
            try:
                if cmd == "cloud_connect" and (a.get("use") or not (a.get("key") or "").strip()):
                    return self._cloud_use()             # «Отвечать моделями Dewiar»: своим ключом или по аккаунту
                if cmd == "cloud_connect":
                    key = (a.get("key") or "").strip()
                    if re.fullmatch(r"\d[\d\s-]{4,8}\d", key):          # 6 цифр — код с другого устройства
                        return self.pair_claim(key, a.get("url", ""))
                    r = self.cloud.connect(key, a.get("url", ""))
                    return self._cloud_connected(r, "ключ Dewiar")      # студия сразу видит новый профиль
                if cmd == "cloud_forget":
                    own_key = not self.s.get("cloud", "account")
                    was_active = self.s.get("llm", "active") == "dewiar-cloud"
                    r = self.cloud.forget()
                    if own_key:                          # 0.82.1: сами больше не подключаемся (раньше — новый ключ с новым подарком)
                        self.s.update({"cloud": {"forgot": time.time()}})
                    if own_key and self.account.logged_in():   # убрали свой ключ, а вход аккаунтом есть — модели Dewiar по аккаунту
                        self._account_cloud(force_active=was_active, quiet=True)
                        r = self.cloud.status()
                    if self.s.get("stt", "engine") == "remote" and self.s.get("stt", "remote", "cloud"):
                        self.s.update({"stt": {"engine": self._stt_local(), "remote": {"cloud": False}}})
                        self.apply_engines()                 # ключа больше нет — распознаём у себя
                    if self.s.get("tts", "engine") == "remote" and self.s.get("tts", "remote", "cloud") and not self.s.get("cloud", "key"):
                        self.cloud.set_tts(False, self._tts_local())
                        self.apply_engines()                 # и говорим своим голосом
                    elif self.s.get("tts", "engine") == "remote" and self.s.get("tts", "remote", "cloud"):
                        self.cloud.set_tts(True)
                        self.apply_engines()                 # ключ сменился на вход аккаунтом — голос по нему
                    self.emit("settings", settings=self.s.snapshot())
                    return r
                return self.cloud.status(refresh=bool(a.get("refresh")))
            except CloudError as e:
                raise ValueError(str(e)) from e
        if cmd in ("net", "net_proxy", "net_check", "net_dewiar", "net_reserve"):   # dewiar.pro заблокирован провайдером — прокси
            return self.net_cmd(cmd, a)
        if cmd in ("sshlink", "sshlink_save", "sshlink_test"):     # запасной вход через SSH (владелец сервера, 29.10)
            if cmd == "sshlink_save":
                return self.sshlink.save(a)
            if cmd == "sshlink_test":
                return dict(self.sshlink.test(a), **self.sshlink.public())
            return self.sshlink.public()
        if cmd == "device":
            if a.get("fresh"):                         # раздел «Голос» открыт — что умеет облако сейчас (озвучку могли включить)
                self._cloud_caps()
            return self.device_status()
        if cmd in ("av_status", "av_exclude", "av_copy"):     # Windows: антивирус и исключения для Dewiar
            import winav
            root = Path(__file__).resolve().parent.parent
            if cmd == "av_status":
                return winav.status(root)
            if cmd == "av_copy":
                return {"ok": winav.copy_text(winav.install_paths(root)[0])}
            return {"ok": winav.defender_exclude(winav.install_paths(root))}
        if cmd == "device_light":
            if not a.get("on"):                        # выключили сами — сам больше не включаю (тесно — только совет)
                self.s.update({"device": {"auto_light": False}})
            done = self.set_light(bool(a.get("on")))
            return dict(self.device_status(), done=done)
        if cmd == "probe_server":
            from llm import probe_server
            return probe_server(a.get("address", ""), a.get("port", ""))
        if cmd == "discover":                                   # «Найти Ollama или LM Studio»: выключенный сервер LM Studio — включить
            return discover_local(start=True)
        if cmd == "ws_tree":
            t = self.workspace.tree()
            o = self.obsidian.public()
            t["obsidian"] = {k: o.get(k) for k in ("connected", "name", "folder", "open", "last")}
            t["obsidian"]["folders"] = ["Заметки", "Дневник", "Память"] if o.get("connected") else []
            return t
        if cmd == "ws_delete_dir":                              # «Папка»: подпапку целиком — в корзину
            try:
                return self.workspace.remove_dir(a.get("path", ""))
            except (WorkspaceError, OSError) as e:
                raise ValueError(str(e)) from e
            except Exception as e:  # noqa: BLE001 — защита корзины
                raise ValueError(str(e)) from e
        return NotImplemented

    def _max_shared_ok(self):
        """Бот Dewiar в MAX настроен на сайте? (№748, 15.11: «пишет, что MAX не подключён к сервису» — на сайте нет токена
        бота, а студия предлагала «Подключить MAX»). Сайт без токена отвечает 503 «MAX пока не подключён». Кэш 30 минут;
        не узнали (нет связи) — None: студия показывает кнопку как раньше. -> {"ok": True | False | None}"""
        c = getattr(self, "_max_shared_c", None)
        if c and time.time() - c[0] < 1800:
            return {"ok": c[1]}
        ok = None
        try:
            import httpx
            from maxbot import SHARED_URL
            u = self.s.get("max_url") or self.account.service_url("max") or SHARED_URL
            r = httpx.get(u, timeout=8)
            ok = False if (r.status_code == 503 and "не подключён" in r.text) else True
        except Exception:  # noqa: BLE001
            ok = None
        if ok is not None:
            self._max_shared_c = (time.time(), ok)
        return {"ok": ok}
