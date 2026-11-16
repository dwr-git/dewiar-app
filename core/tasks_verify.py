"""Фоновые задачи, часть «проверка» (примесь TaskManager, core/tasks.py; чистое ядро 1.0.10 — docs/CORE_PLAN.md):
критерии (команда, адрес, страница), доказательства и источники, судья, осмотр результата («глаза»), ворота перед «готово»."""
import json
import re
from pathlib import Path

import quality as Q
from codework import CodeError
from llm import LLMError, stream_chat
from tasks_base import log, _now, _rd, SELF_MADE, TINY_WIN, VERIFY_LOOKS, WIN_DEFAULT, _wr
import tasks_base as TB  # подменяемые в проверках имена — через основу


class VerifyMixin:
    def _crit_path(self, t, rel):
        p, _f = self._area(t, rel)
        if not p.exists():
            code = t.code()
            if code is not None and not Path(str(rel)).is_absolute():
                for root in (code.work, code.project):
                    q = Path(root) / str(rel)
                    if q.exists():
                        return q
        return p

    def _crit_cmd(self, t, cmd):
        """Критерий «команда проходит»: та же защита, что у code_run; без разрешения на запуск кода — не проверяется."""
        import subprocess
        import guard
        if not self.host.code_auto_run():               # разрешение на run_python — не разрешение на любые команды
            return None, "проверит проверяющий"
        code = t.code()
        cwd = str(code.work) if code is not None and Path(code.work).exists() else str(t.dir)
        v = guard.check_command(cmd, cwd=cwd)
        if v["level"] != "ok":
            return None, f"команду не запускаю без человека: {v.get('reason') or v['level']}"
        t.journal(f"▶ команда критерия: {cmd[:300]}")
        try:
            r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=120, stdin=subprocess.DEVNULL, env=self._py_env(t, ""))
        except subprocess.TimeoutExpired:
            return False, "не уложилась в 120 с"
        tail = (r.stdout + r.stderr).strip()[-300:]
        # экзамен 0.84.1: «grep -c 'class="slide' …» вывел 5, а в справке было только «код 0» — проверяющий прочёл «вернул 0
        # слайдов» и вернул итог трижды. Теперь — «прошла (код выхода 0), вывод: 5»
        if r.returncode == 0:
            return True, "прошла (код выхода 0)" + (f", вывод: {tail}" if tail else "")
        return False, f"не прошла (код выхода {r.returncode})" + (f", вывод: {tail}" if tail else "")

    @staticmethod
    def _url_inner(t, url):
        """Адрес внутренней сети (loopback, частные сети, link-local…) -> причина или "". Свой поиск задачи (search_url —
        экзамен Б1) — можно. Рецензия 0.84: критерий «ссылка открывается» ходил куда угодно, в том числе на 127.0.0.1."""
        import ipaddress
        import socket
        from urllib.parse import urlparse
        u = urlparse(str(url or ""))
        if u.scheme not in ("http", "https") or not u.hostname:
            return "нужен адрес http(s)://"
        su = t.data.get("search_url")
        if su and urlparse(su).netloc == u.netloc:
            return ""
        try:
            infos = socket.getaddrinfo(u.hostname, u.port or (443 if u.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
        except (OSError, UnicodeError, ValueError):
            return ""                                      # не нашёлся адрес — откроется с ошибкой (или через прокси)
        for *_x, sa in infos:
            try:
                ip = ipaddress.ip_address(sa[0])
            except ValueError:
                continue
            if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
                return "адрес внутренней сети"
        return ""

    def _crit_url(self, t, url):
        """Критерий «ссылка открывается»: GET без автоперехода — каждая переадресация проверяется на внутреннюю сеть."""
        import httpx
        from urllib.parse import urljoin
        cur = str(url)
        try:
            with httpx.Client(follow_redirects=False, timeout=15, headers={"User-Agent": "Mozilla/5.0 (Dewiar)"}) as c:
                for _ in range(6):
                    why = self._url_inner(t, cur)
                    if why:
                        return False, f"{why} — такие адреса не открываю"
                    r = c.get(cur)
                    if 300 <= r.status_code < 400 and r.headers.get("location"):
                        cur = urljoin(cur, r.headers["location"])
                        continue
                    return r.status_code < 400, f"HTTP {r.status_code}"
        except httpx.HTTPError as e:
            return False, f"не открылась: {e.__class__.__name__}"
        return False, "слишком много переадресаций"

    @staticmethod
    def _page_roots(t):
        """Откуда странице задачи можно брать файлы в браузере проверки: папка задачи и рабочая копия проекта."""
        code = t.code()
        return [str(t.dir)] + ([str(code.work), str(code.project)] if code is not None else [])

    @staticmethod
    def _browser_ok(paths, roots=None):
        res = Q.html_check([str(p) for p in paths], roots=roots)
        if res is None:
            return None
        return {k: (None if v.get("unchecked") or v.get("soft") else not v["errors"],
                    v.get("unchecked") or "; ".join(v["errors"]) or "ошибок нет") for k, v in res.items()}

    def _check_criteria(self, t, quick=False):
        """Проверить критерии (или файлы из цели, если критериев нет) -> результаты; полная проверка сохраняется в критерии.json."""
        d = t.criteria()
        own = d.get("items") or []
        have = {str(c.get("target") or "").strip("./") for c in own}
        crits = own + [c for c in self._auto_criteria(t) if c["target"].strip("./") not in have]
        if not crits:
            return []
        res = Q.check_criteria(crits, lambda rel: self._crit_path(t, rel), run_cmd=lambda c: self._crit_cmd(t, c),
                               http_ok=lambda u: self._crit_url(t, u), browser=lambda ps: self._browser_ok(ps, self._page_roots(t)), quick=quick)
        if not quick and d.get("items"):
            d.update(results=res, checked=_now())
            t.put_json("критерии.json", d)
        return res

    def _prose(self, t):
        """Тексты отчётов задачи (outputs/*.md, .txt, .html) — то, что модель написала сама: опорой они не бывают."""
        out = []
        d = t.dir / "outputs"
        for p in sorted(d.rglob("*")) if d.is_dir() else []:
            if p.is_file() and not p.is_symlink() and p.suffix.lower() in self.PROSE:
                out.append(Q.file_text(p, limit=500000))
        return "\n".join(out)

    def _own_path(self, t, path):
        """Путь чтения указывает на результаты (outputs/) или служебные файлы задачи — то, что пишет сама модель."""
        raw = str(path or "").strip()
        if not raw:
            return False
        try:
            p = Path(raw).expanduser()
            p = (p if p.is_absolute() else t.dir / raw.lstrip("/\\")).resolve()
            rel = p.relative_to(t.dir.resolve())
        except (OSError, ValueError):
            return False
        return bool(rel.parts) and (rel.parts[0] == "outputs" or rel.parts[0] in Q.SERVICE)

    @staticmethod
    def _blind_overwrite(t, p, args):
        """Выпуск 8, п.5 (как в среде Claude: файл не перезаписывают, не прочитав). write_file поверх файла, который задача
        не создавала и в этой задаче не читала (присланный человеком, его папка), — отказ с подсказкой: прочитать и править
        точечно (file_edit) или писать новый файл рядом. Дописывание (append) и свои файлы — как раньше. -> текст отказа или ""."""
        try:
            if args.get("append") or not p.is_file() or p.stat().st_size == 0:
                return ""
            rel = p.relative_to(t.dir).as_posix() if str(p.resolve()).startswith(str(t.dir.resolve())) else ""
        except (OSError, ValueError):
            return ""
        if rel and rel in (t.data.get("authored") or []):
            return ""
        if str(p.resolve()) in (t.data.get("seen") or []):
            return ""
        t.journal(f"✋ не перезаписал «{p.name}» вслепую — файл не читали в этой задаче")
        return (f"Ошибка: файл «{p.name}» уже есть, и в этой задаче ты его не читал — перезапись вслепую сотрёт чужое. "
                "Как исправить: прочитай его (file_read) и правь точечно (file_edit), или запиши результат новым файлом рядом.")

    def _evidence_piece(self, t, name, args, r):
        """Что из результата инструмента — опора для сверки -> (заголовок, текст) или None. Не опора (рецензия 0.84): то,
        что пишет сама модель; чтение своих outputs/ и служебных файлов; строки вывода run_python, которые есть в её же
        отчётах (скрипт печатает собственный отчёт); код run_python."""
        if name in SELF_MADE or not isinstance(r, str) or not r.strip():
            return None
        args = args if isinstance(args, dict) else {}
        if name in ("file_read", "read_file") and self._own_path(t, args.get("path")):
            return None
        if name == "file_grep":
            if self._own_path(t, args.get("path")):
                return None
            r = "\n".join(ln for ln in r.splitlines() if not ln.startswith(("outputs/", "_src/", "задачи.json", "критерии.json")))
        if name in ("run_python", "code_run"):
            prose = self._prose(t)
            if prose:
                r = "\n".join(ln for ln in r.splitlines() if len(ln.strip()) < 12 or ln.strip() not in prose)
            return (name, r) if r.strip() else None
        return (f"{name} {json.dumps(args, ensure_ascii=False)[:5000]}", r)

    def _src_log(self, t, name, args, r):
        """Опора (_evidence_piece) — в _src/результаты.txt: по ней проверяющий сверяет ссылки и цифры итога. Пишется ДО
        обрезки вывода (_offload) — целиком; после SRC_MAX — только заголовок с аргументами (адреса не теряются).
        Задача по коду — без опоры: её итог проверяют тесты и diff."""
        if t.code() is not None:
            return
        piece = self._evidence_piece(t, name, args, r)
        if not piece:
            return
        f = t.dir / "_src" / "результаты.txt"
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            full = f.exists() and f.stat().st_size > TB.SRC_MAX
            _wr(f, f"\n\n### {piece[0]}\n" + ("(вывод не сохранён: опора переполнена)" if full else piece[1][:400000]) + "\n",
                append=True, root=t.dir)
        except OSError:
            pass

    def _src_backfill(self, t):
        """Опоры нет (задача начата до 0.84 или опору стёрли) — собрать её из история.json и _out/ (рецензия 0.84)."""
        try:
            msgs = json.loads(_rd(t.dir / "история.json") or "[]")
        except (OSError, ValueError):
            msgs = []
        calls, last, parts = {}, [], []

        def add(nm, a, txt):
            piece = self._evidence_piece(t, nm, a, txt)
            if piece:
                parts.append(f"### {piece[0]}\n{piece[1]}")
        for m in msgs if isinstance(msgs, list) else []:
            if not isinstance(m, dict):
                continue
            if m.get("role") == "assistant":
                cs = self._calls_of(m)
                if cs:
                    last = cs
                    for cid, nm, a in cs:
                        calls[cid] = (nm, a)
                        if nm not in SELF_MADE and nm not in ("run_python", "code_run"):   # адреса из вызовов чтения — тоже видены
                            parts.append(f"### {nm} {json.dumps(a, ensure_ascii=False)[:5000]}")
                continue
            c = m.get("content")
            if m.get("role") == "tool":
                nm, a = calls.get(m.get("tool_call_id"), ("?", {}))
                add(nm, a, c if isinstance(c, str) else json.dumps(c, ensure_ascii=False))
            elif isinstance(c, list):
                for b in c:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        nm, a = calls.get(b.get("tool_use_id"), ("?", {}))
                        bc = b.get("content")
                        add(nm, a, "".join(x.get("text", "") for x in bc if isinstance(x, dict)) if isinstance(bc, list) else str(bc or ""))
            elif isinstance(c, str) and "<tool_response>" in c:
                for k, body in enumerate(re.findall(r"<tool_response>\n?(.*?)\n?</tool_response>", c, re.S)):
                    nm, a = (last[k][1], last[k][2]) if k < len(last) else ("?", {})
                    add(nm, a, body)
        for f in sorted((t.dir / "_out").glob("*.txt")) if (t.dir / "_out").is_dir() else []:
            nm = re.sub(r"-\d+(?:-\d+)?$", "", f.stem)
            add(nm, {}, _rd(f)[:400000])
        return "\n\n".join(parts)

    def _given(self, t, limit=8 << 20):
        """Тексты, которые дала не модель этой задачи: итоги частей (parts/), скачанное (downloads/), файлы человека в папке
        задачи (заготовки, материалы) — тоже опора (рецензия 0.84)."""
        out, size = [], 0
        for p in sorted(t.dir.rglob("*")):
            try:
                rel = p.relative_to(t.dir)
            except ValueError:
                continue
            if not p.is_file() or rel.parts[0] in Q.SERVICE or rel.parts[0] == "outputs" or rel.parts[0].startswith("рабочая копия") \
                    or p.name.endswith(".tmp") or rel.as_posix() in (t.data.get("authored") or []):
                continue
            txt = Q.file_text(p, limit=2_000_000)
            size += len(txt)
            out.append(txt)
            if size > limit:
                break
        return "\n".join(out)

    def _evidence(self, t):
        """Опора для ссылок и цифр: результаты инструментов (_src, а если его нет — из истории), тексты частей, скачанного и
        файлов человека, цель, слова человека."""
        try:
            src = (t.dir / "_src" / "результаты.txt").read_text(encoding="utf-8")
        except OSError:
            src = self._src_backfill(t)
        nb = t.notebook()
        human = nb.split("## Ответы человека", 1)[1].split("\n## ", 1)[0] if "## Ответы человека" in nb else ""
        return f"{t.goal}\n{human}\n{src}\n{self._given(t)}"

    def _data_files(self, t, limit=16 << 20):
        """Файлы с данными для сверки цифр: в outputs/ — только сделанные скриптом (не write_file / file_edit) и не отчёты
        (.md, .html); остальное — в опоре (_given). -> [(путь, текст)]."""
        out, size = [], 0
        d = t.dir / "outputs"
        authored = set(t.data.get("authored") or [])
        for p in sorted(d.rglob("*")) if d.is_dir() else []:
            rel = p.relative_to(t.dir).as_posix()
            if not p.is_file() or p.is_symlink() or p.suffix.lower() in (".md", ".html", ".htm") or rel in authored:
                continue
            txt = Q.file_text(p, limit=2_000_000)
            size += len(txt)
            out.append((p, txt))
            if size > limit:
                break
        return out

    def _ask_with(self, prof, system, messages, max_tokens=900):
        if not prof:
            return ""
        return "".join(stream_chat(dict(prof, max_tokens=max_tokens, temperature=0.1), system, messages))

    def _judge(self, t):
        """Сильная модель проверяющего (tasks.judge_llm), если настроена -> профиль или None (тогда — модель задачи)."""
        pid = self._opt("judge_llm") or ""
        if not pid:
            return None
        try:
            profs = self.host.s.get("llm", "profiles") or {}
        except Exception:  # noqa: BLE001
            return None
        return dict(profs[pid], id=pid) if pid in profs else None

    def _verify(self, t, summary, q, files, facts, diff):
        """Проверка по существу перед «готово» (выпуск 3): критерии кодом -> выдуманные ссылки -> ошибки страниц в браузере ->
        цифры без опоры (один раз) -> проверяющий с чистым контекстом (один вызов). -> текст для модели или None (принять)."""
        res = self._check_criteria(t)
        if any(r.get("ok") is False for r in res):
            q["verify_fail"] += 1
            t.journal("🎯 Критерии готовности не выполнены: " + "; ".join(f"{Q.crit_label(r)} — {r.get('detail')}" for r in res if r.get("ok") is False)[:600])
            return Q.criteria_note(res)
        outs = sorted(p for p in (t.dir / "outputs").rglob("*") if p.is_file() and not p.is_symlink()) if (t.dir / "outputs").is_dir() else []
        reports = [p for p in outs if p.suffix.lower() == ".md"][:10]
        claims = summary + "\n" + "\n".join(Q.file_text(p, limit=200000) for p in reports)
        evidence = self._evidence(t)
        code = t.code() is not None
        ghost = [] if code else Q.unseen_urls(claims, evidence)
        findings = []
        if ghost and set(ghost) <= set(t.data.get("ghost_checked") or []):
            findings.append("Ссылки, которых задача не открывала (она предупреждена и не исправила): " + ", ".join(ghost[:8]))
            ghost = []                                     # один возврат на тот же список — дальше решает проверяющий
        if ghost:
            t.data["ghost_checked"] = sorted(set(t.data.get("ghost_checked") or []) | set(ghost))[:60]
            q["verify_fail"] += 1
            t.journal("🔗 В итоге ссылки, которых задача не открывала и не видела: " + ", ".join(ghost[:6]))
            return ("ССЫЛКИ БЕЗ ИСТОЧНИКА: в итоге или отчёте есть адреса, которых нет ни в одном прочитанном (поиск, страницы, "
                    "файлы): " + ", ".join(ghost[:8]) + ". Ссылка, которую ты не открывал(а), — догадка. Открой каждую "
                    "read_webpage и проверь, что факт или цифра там есть, — или убери её (замени ссылкой, которую читал(а)). "
                    "Затем снова вызови finish.")
        html = [p for p in outs if p.suffix.lower() in (".html", ".htm")][:4]
        hc = Q.html_check(html, roots=self._page_roots(t)) if html else None
        if hc:
            bad = {Path(k).relative_to(t.dir).as_posix(): v["errors"] for k, v in hc.items() if v["errors"] and not v.get("soft") and not v.get("unchecked")}
            for k, v in hc.items():                        # не загрузилась или ошибки из-за внешних ресурсов — замечание, не брак
                rel = Path(k).relative_to(t.dir).as_posix()
                if v.get("unchecked"):
                    findings.append(f"{rel}: в браузере не проверена ({v['unchecked'][:120]})")
                elif v.get("soft") and v["errors"]:
                    findings.append(f"{rel}: ошибки скриптов, возможно, из-за внешних ресурсов без сети ({', '.join(v.get('external') or [])[:160]}): "
                                    + " | ".join(v["errors"][:2]))
            if bad:
                q["verify_fail"] += 1
                t.journal("🌐 Браузер: ошибки на страницах — " + "; ".join(f"{k}: {v[0]}" for k, v in bad.items())[:500])
                return ("СТРАНИЦА С ОШИБКАМИ (открыта в браузере, проверено кодом):\n" + "\n".join(
                    f"- {k}: " + " | ".join(v[:3]) for k, v in bad.items()) + "\nПочини скрипт страницы (file_edit) и снова вызови finish.")
        look = self._eyes(t, hc, q)                         # HARNESS 8: посмотреть на страницу глазами (модель со зрением)
        if look:
            return look
        data = self._data_files(t)
        nums = []
        if not code:
            # №700 (пакет 14.11): «17.4 МБ» в итоге — это размер файла (17 365 198 байт), не выдумка; опора — и в КБ/МБ/ГБ
            sizes = " ".join(f"{n} {n / 1e3:.3f} {n / 1e6:.3f} {n / 1e9:.3f} {n / 1024:.3f} {n / 1024 ** 2:.3f} {n / 1024 ** 3:.3f}"
                             for n in (p.stat().st_size for p in outs))
            pool = Q.number_pool("\n".join([evidence, facts, sizes] + [x for _, x in data]))
            nums = Q.unsupported_numbers(claims, pool)
        if nums and not t.data.get("nums_checked"):
            t.data["nums_checked"] = True
            q["verify_fail"] += 1
            t.journal("🔢 Числа итога без опоры в источниках и файлах: " + ", ".join(nums))
            return ("ЦИФРЫ БЕЗ ОПОРЫ: в итоге или отчёте есть числа, которых нет ни в прочитанных источниках, ни в файлах с "
                    "данными: " + ", ".join(nums) + ". Сверь каждое: неверное — исправь по источнику или файлу; посчитанное — "
                    "посчитай в run_python (расчёт и вывод останутся опорой); без опоры — убери. Затем снова вызови finish.")
        judge = self._judge(t)
        got = self._review(t, summary, files, facts, diff, res, outs, hc, claims, findings)   # выпуск 6: проверяющий-подагент
        if got is None:
            return None                                    # проверяющий выключен (или окно крошечное) — решают машинные проверки
        verdict, problems = got
        if verdict == "ok":
            t.journal("🧐 Проверяющий: итог подтверждён" + (f" (модель {judge.get('name') or judge.get('id')})" if judge else "") + ".")
            return None
        if verdict == "revise":
            q["critic"] += 1
            t.data["verify_revise"] = int(t.data.get("verify_revise") or 0) + 1
            t.journal(f"🧐 Самопроверка вернула итог на доработку: {problems}")
            return Q.critic_note(problems)
        # непонятный ответ или сбой проверяющего — не «ок»: решают машинные проверки
        if nums and not t.data.get("nums_unclear"):
            t.data["nums_unclear"] = True
            t.journal("🧐 Проверяющий ответил непонятно — решают машинные проверки: есть числа без опоры.")
            return ("Проверить итог по существу не удалось, а машинная проверка нашла числа без опоры: " + ", ".join(nums) +
                    ". Подтверди каждое источником или расчётом (run_python) или убери, затем снова вызови finish.")
        t.journal("🧐 Проверяющий дважды ответил непонятно — решили машинные проверки: " + ("прошли" if not nums else "числа без опоры уже показаны задаче дважды")
                  + (f". Замечание проверяющего: {problems[:300]}" if problems else "") + (f". Замечания: {'; '.join(findings)[:300]}" if findings else "") + ".")
        return None

    def _src_block(self, t, url):
        """Выдержка источника из _src: что вернул read_webpage (или download) по этому адресу."""
        try:
            src = (t.dir / "_src" / "результаты.txt").read_text(encoding="utf-8")
        except OSError:
            return ""
        key = url.rstrip("/")
        for part in src.split("\n\n### ")[1:]:
            head, _, body = part.partition("\n")
            if head.startswith(("read_webpage", "download", "read_page")) and key in head:
                return re.sub(r"\s+", " ", body).strip()
        return ""

    def _fetch_src(self, t, url):
        """Ссылку итога задача не читала (видела только в выдаче поиска) — проверяющий открывает её сам (read_webpage)."""
        if self._url_inner(t, url):
            return ""
        try:
            on, _need = self.host.toolbox.policy("read_webpage")
            if not on:
                return ""
            r = self.host.toolbox.run("read_webpage", {"url": url})
        except Exception as e:  # noqa: BLE001
            return f"(не открылась: {str(e)[:120]})"
        return re.sub(r"\s+", " ", str(r or "")).strip()

    def _eyes(self, t, hc, q):
        """Снимки готовых страниц (html_check, экран телефона) — модели со зрением: видно ли пустоту, наложения, обрезанное,
        заглушки (HARNESS 8, владелец 12.11: «у тебя сила и в том, что ты смотришь скриншоты результата — было бы здорово,
        если бы и Лира так умела»). Один раз на задачу; модель не видит картинок — молча пропускаем (и запоминаем).
        -> текст для задачи (поправить) или None."""
        if t.data.get("look_done") or not hc:
            return None
        shots = [(Path(k), v["shot"]) for k, v in hc.items() if v.get("shot") and not v.get("errors")][:2]
        if not shots:
            return None
        prof = self._judge(t) or self.host.llm_profile()
        if not prof:
            return None
        blind = getattr(self.host, "_blind", None)
        key = f"{prof.get('base_url')}|{prof.get('model')}"
        if isinstance(blind, set) and key in blind:
            t.data["look_done"] = True
            return None
        from llm import LLMError, stream_chat, user_message
        bad = []
        for path, shot in shots:
            try:
                rel = path.relative_to(t.dir).as_posix()
            except ValueError:
                rel = path.name
            try:
                raw = "".join(stream_chat(dict(prof, max_tokens=400, temperature=0, think="off"), Q.LOOK,
                                          [user_message(prof, f"Цель задачи: {t.goal[:600]}\nФайл: {rel}", [shot])], cancel=t.cancel))
            except LLMError as e:
                if re.search(r"image|vision|multimodal|картин|изображ", str(e), re.I) and isinstance(blind, set):
                    blind.add(key)
                t.data["look_done"] = True
                return None
            except Exception as e:  # noqa: BLE001 — сбой просмотра не валит задачу
                log.info("Задача %s: просмотр страницы не удался: %s", t.id, e)
                t.data["look_done"] = True
                return None
            v = Q.look_verdict(raw)
            if v and v[0] == "revise" and v[1]:
                bad.append(f"{rel}: {v[1]}")
        t.data["look_done"] = True
        if not bad:
            t.journal("👀 Посмотрела на страницу глазами (экран телефона) — видно как надо.")
            return None
        q["verify_fail"] = q.get("verify_fail", 0) + 1
        t.journal("👀 Посмотрела на страницу глазами — видно проблему: " + "; ".join(bad)[:400])
        return ("ПОСМОТРЕЛА НА СТРАНИЦУ (снимок экрана телефона, ширина 375): " + "; ".join(bad) + ". Поправь вёрстку "
                "(file_edit), открой страницу снова, если нужно, и снова вызови finish.")

    def _promised_missing(self, t, summary):
        """Файлы, названные в итоге, которых нет ни в папке задачи, ни в «Лаборатории», ни в папке ассистента.
        Названный, но не созданный результат — не результат (№368)."""
        names, text = [], summary or ""
        for m in self.PROMISE_RX.finditer(text):
            before = text[max(0, m.start() - 120):m.start()].split()
            if before and ("://" in before[-1] or before[-1].startswith("www.")) and not text[m.start() - 1:m.start()].isspace():
                continue                                   # часть ссылки на сайт — не наш файл
            n = Path(m.group(1).strip().split("/")[-1].split("\\")[-1]).name.strip(" .«»\"'")
            words = n.split()
            cands = [" ".join(words[-k:]) for k in range(1, min(len(words), 12) + 1)]   # «в файле продажи.csv» → «продажи.csv», …
            # рецензия 0.82: «сохранён в файл 'report.md'» — кавычки по краям не часть имени (апостроф внутри — часть: «Don't.md»)
            cands = list(dict.fromkeys(c.strip(" '’\"«»“”„`") for c in cands))
            cands = [c for c in cands if c]
            if cands and cands not in names:
                names.append(cands)
        if not names:
            return []
        have = {p.name.lower() for p in t.dir.rglob("*") if p.is_file() and not p.is_symlink()} | {p.name.lower() for p in self._lab_files(t)}
        code = t.code()
        if code is not None:                               # задача по коду: файлы проекта (рабочая копия и сам проект)
            for root in (getattr(code, "work", None), getattr(code, "project", None)):
                try:
                    if root and Path(root).is_dir():
                        for i, p in enumerate(Path(root).rglob("*")):
                            if i > 20000:
                                break
                            have.add(p.name.lower())
                except OSError:
                    pass
        miss = []
        for cands in names[:20]:
            if any(c.lower() in have for c in cands):
                continue
            try:
                import glob as _glob
                if any(any(True for _ in self.host.workspace.root.rglob(_glob.escape(c))) for c in cands):
                    continue
            except (OSError, ValueError):
                pass
            miss.append(cands[0])
        return miss

    def _finish_gates(self, t, summary):
        """Проверки перед итогом: ложный отказ -> машинная проверка файлов (и что они показаны), названные в итоге файлы
        существуют -> самопроверка моделью. №368 (28.10): проверки идут при КАЖДОМ finish — отклонённый итог не
        «запоминается проверенным»; спор не бесконечен: после GATE_MAX отказов задача останавливается «не выполнено»
        (t.data["unfinished"]), а не «готово». force_finish (завершаем сами из-за повтора) — тоже «не выполнено».
        -> текст для модели (итог не принят) или None (принимаем — или останавливаем, если стоит unfinished)."""
        q = self._q(t)
        if t.data.get("force_finish"):
            t.data["unfinished"] = t.data.get("unfinished") or self._stop_why(t)
            return None
        note = self._gates(t, summary, q)
        if note is None:
            return None
        t.data["gate_rejects"] = int(t.data.get("gate_rejects") or 0) + 1
        if t.data["gate_rejects"] > self.GATE_MAX:
            why = re.sub(r"^САМОПРОВЕРКА отклонила итог:\s*|^МАШИННАЯ ПРОВЕРКА ФАЙЛОВ НАШЛА БРАК:\s*", "", note).split("\nИсправь")[0].split("\nЭто ОБЪЕКТИВНЫЕ")[0]
            t.data["unfinished"] = f"проверка итога не согласилась {self.GATE_MAX} раза — {why.strip()[:240]}"
            t.journal("⛔ Итог отклонён много раз — останавливаю задачу как «не выполнено».")
            return None
        return note

    def _stop_why(self, t):
        """Понятная причина остановки «не выполнено» (force_finish) и что задача успела: человеку — не «повторяла одно и
        то же или перестала действовать» на всё подряд (№448, №460), а что именно случилось и сколько сделано."""
        why = {"loop": "задача несколько раз повторила одно и то же действие с тем же результатом",
               "idle": "модель перестала выполнять действия — несколько раз подряд отвечала только текстом",
               "badcall": "модель пишет действия в виде, который Dewiar не смог разобрать",
               "budget": "у части кончился бюджет шагов или токенов"}.get(
            t.data.get("force_why") or "", "задача повторяла одно и то же или перестала действовать")
        did = {}
        for k, n in (self._q(t).get("tools") or {}).items():
            if k in self.DID_RU:
                did[self.DID_RU[k]] = did.get(self.DID_RU[k], 0) + int(n or 0)
        done, total = (t.data.get("progress") or [0, 0])[:2]
        parts = [f"{k} ×{n}" for k, n in sorted(did.items(), key=lambda x: -x[1])[:4]]
        if total:
            parts.append(f"план — {done} из {total}")
        return why + (f" (успела: {', '.join(parts)})" if parts else "") + " — цель не подтверждена"

    def _gates(self, t, summary, q):
        if not t.data.get("refusal_nudged") and Q.looks_like_refusal(summary) and self._web_available(t) and not self._web_used(t):
            t.data["refusal_nudged"] = True
            q["refusal"] += 1
            t.journal("✋ Проверка перед итогом: отказ «нет доступа», а поиском не пользовался — напоминаю про web_search.")
            return Q.REFUSAL_NUDGE
        shown = [o.get("path") for o in t.data.get("outputs") or []]
        miss = self._promised_missing(t, summary)
        if miss:
            q["verify_fail"] += 1
            t.journal("🔎 В итоге названы файлы, которых нет: " + ", ".join(miss[:8]))
            return ("В итоге назван результат, которого нет на диске: " + ", ".join(miss[:8]) + ". Названный файл — не "
                    "доказательство. Создай его (write_file или run_python в папке задачи, outputs/), проверь (file_read) и "
                    "покажи (show) — или честно напиши в итоге, что сделать не удалось, и снова вызови finish.")
        if True:
            probs = Q.verify_outputs(t.dir, shown)
            if probs:
                q["verify_fail"] += 1
                t.journal("🔎 Машинная проверка файлов нашла брак:\n" + "\n".join("- " + x for x in probs[:8]))
                return Q.summarize(probs)
            outs = [p for p in (t.dir / "outputs").rglob("*") if p.is_file() and not p.is_symlink()] if (t.dir / "outputs").is_dir() else []
            if outs and not shown:
                t.journal("✋ Проверка перед итогом: файлы готовы, но пользователю не показаны.")
                return ("Файлы в outputs/ готовы, но ты не показал их пользователю — он их не увидит. Вызови show для главных "
                        "файлов (страница, таблица, документ…), затем снова finish.")
        code = t.code()
        if code is not None and int(t.data.get("tests_gate") or 0) < 2 and self.host.code_auto_run():
            from codework import test_command
            try:
                code.prepare()                            # finish без единого code_* — копии ещё нет
                cmd = test_command(code.work)
            except (CodeError, OSError) as e:
                log.info("проверка тестов перед итогом: %s", e)
                cmd = None
            if cmd:                                       # итог по коду — только когда тесты проекта проходят (два раза спорим)
                out = code.run(cmd, 600)
                if not out.startswith("Код завершения 0"):
                    t.data["tests_gate"] = int(t.data.get("tests_gate") or 0) + 1
                    q["verify_fail"] += 1
                    t.journal(f"🧪 Проверка перед итогом: тесты не проходят ({cmd}).")
                    return (f"Тесты проекта не проходят — итог не принят. Команда: {cmd}\n{out[-2500:]}\n\nИсправь код "
                            "(тесты не меняй, если тебя об этом не просили) и снова запусти тесты. Если падение не связано "
                            "с задачей и было до тебя — объясни это в итоге и снова вызови finish.")
                t.data["tests_gate"] = 9                  # прошли — больше не проверяем
                t.journal(f"🧪 Проверка перед итогом: тесты проходят ({cmd}).")
        if True:                                          # выпуск 3: проверка по существу (критерии, ссылки, цифры, проверяющий)
            files = []
            for p in sorted(t.dir.rglob("*")):
                rel = p.relative_to(t.dir)
                if p.is_file() and not p.is_symlink() and rel.parts[0] not in Q.SERVICE and not rel.parts[0].startswith("рабочая копия"):
                    files.append(f"{rel.as_posix()} — {p.stat().st_size} байт")
            files += [f"Лаборатория/{p.relative_to(self.host.workspace.root / 'Лаборатория').as_posix()} — {p.stat().st_size} байт"
                      for p in self._lab_files(t)]
            facts = (f"Шагов: {t.data.get('steps', 0)}. Инструменты: " +
                     ", ".join(f"{k}×{v}" for k, v in sorted(q["tools"].items(), key=lambda x: -x[1])[:12]) +
                     (f". Показано пользователю: {', '.join(shown)}" if shown else "") +
                     (". Это задача по коду: изменения пользователь примет сам (рабочая копия)." if t.data.get("project") else ""))
            diff = ""
            if code is not None and code.work.exists():
                try:                                      # экзамен 0.84.1: «файлы не созданы» — их искали среди готовых файлов
                    ch = code.changes()
                    if ch:
                        ru = {"added": "новый", "modified": "изменён", "deleted": "удалён"}
                        files = [f"Изменено в рабочей копии: {rel} ({ru.get(st, st)})" for st, rel in ch[:40]] + files
                except Exception:  # noqa: BLE001
                    log.debug("изменения рабочей копии для самопроверки", exc_info=True)
                try:
                    diff = code.diff(limit=max(3000, min(20000, int(int(t.data.get("win") or WIN_DEFAULT) * 3 * 0.3))))
                except Exception:  # noqa: BLE001
                    log.debug("diff для самопроверки", exc_info=True)
            return self._verify(t, summary, q, files, facts, diff)
        return None

    def _verify_tool(self, t, args):
        """verify — проверяющий с чистым контекстом по ходу работы (до finish): машинные критерии + проверяющий-подагент
        (_review), который сам дочитывает файлы и источники. Ничего не меняет, итог не принимает и не отклоняет."""
        what = re.sub(r"\s+", " ", str(args.get("what") or "")).strip()[:400]
        crit = re.sub(r"\s+", " ", str(args.get("criteria") or "")).strip()[:1200]
        win = int(t.data.get("win") or WIN_DEFAULT)
        if win < TINY_WIN and not self._judge(t):
            return "Проверяющий недоступен: окно модели слишком маленькое. Проверь сама: file_read главных файлов, критерии — в «Состоянии задачи»."
        res = self._check_criteria(t)
        outs = sorted(p for p in (t.dir / "outputs").rglob("*") if p.is_file() and not p.is_symlink()) if (t.dir / "outputs").is_dir() else []
        focus = []
        for w in re.findall(r"[\wА-Яа-яЁё./\\: -]+\.[A-Za-z0-9]{1,5}\b", what):
            try:
                p, _f = self._area(t, w.strip())
                if p.is_file() and p not in focus:
                    focus.append(p)
            except (ValueError, OSError):
                continue
        reports = [p for p in focus + outs if p.suffix.lower() == ".md"][:10]
        claims = "\n".join(Q.file_text(p, limit=200000) for p in reports)
        files, facts = self._files_facts(t)
        summary = ("(Проверка по ходу работы — итога ещё нет.) Что проверить: " + (what or "всё сделанное") + ". "
                   + (f"По чему: {crit}" if crit else "По цели и критериям готовности задачи."))
        got = self._review(t, summary, files, facts, "", res, focus + [p for p in outs if p not in focus], None, claims, [], what or "по ходу работы")
        bad = [r for r in res if r.get("ok") is False]
        head = ("Критерии кодом: " + "; ".join(("✓ " if r.get("ok") else "✗ " if r.get("ok") is False else "? ") + Q.crit_label(r)
                                               + (f" ({r.get('detail')})" if r.get("ok") is False and r.get("detail") else "") for r in res)[:900] + "\n") if res else ""
        if got is None:
            return head + "Проверяющий выключен в настройках — решают машинные проверки." + (" Есть невыполненные критерии." if bad else "")
        verdict, problems = got
        if verdict == "ok":
            return head + "Проверяющий: всё подтверждено" + (", но критерии с ✗ ещё не выполнены." if bad else ".")
        if verdict == "revise":
            return head + f"Проверяющий нашёл: {problems}\nИсправь это и продолжай (finish проверит снова)."
        return head + "Проверяющий ответил непонятно — проверь главные файлы сама (file_read)." + (f" Его замечание: {problems}" if problems else "")

    def _files_facts(self, t):
        """Файлы задачи (кроме служебного) с размерами и «факты от системы» для проверяющего."""
        q = self._q(t)
        files = []
        for p in sorted(t.dir.rglob("*")):
            rel = p.relative_to(t.dir)
            if p.is_file() and not p.is_symlink() and rel.parts[0] not in Q.SERVICE and not rel.parts[0].startswith("рабочая копия"):
                files.append(f"{rel.as_posix()} — {p.stat().st_size} байт")
            if len(files) >= 300:
                break
        shown = [o.get("path") for o in t.data.get("outputs") or []]
        facts = (f"Шагов: {t.data.get('steps', 0)}. Инструменты: " +
                 ", ".join(f"{k}×{v}" for k, v in sorted(q["tools"].items(), key=lambda x: -x[1])[:12]) +
                 (f". Показано пользователю: {', '.join(shown)}" if shown else "") +
                 (". Это задача по коду: изменения пользователь примет сам (рабочая копия)." if t.data.get("project") else ""))
        return files, facts

    def _look(self, t, items, per, short, sub):
        """Проверяющий просит дочитать (verdict «look»): «путь[:a-b]» — file_read задачи (только чтение, те же права); адрес —
        выдержка из прочитанного задачей, а не прочитанное — открыть (не в лёгком режиме). Это не опора для сверки (_src)."""
        out = []
        for it in items[:4]:
            s = str(it or "").strip().strip("`«»\"'")
            if not s:
                continue
            sub["steps"] += 1
            if re.match(r"https?://", s, re.I):
                b = self._src_block(t, s) or ("" if short else self._fetch_src(t, s))
                out.append(f"### {s}\n{(b or '(не открылась или недоступна)')[:per]}")
                continue
            m = re.match(r"(.+?)(?::(\d+)(?:\s*[-–]\s*(\d+))?)?$", s)
            path, a, b = (m.group(1), m.group(2), m.group(3)) if m else (s, None, None)
            try:
                r = self._tool_raw(t, "file_read", {"path": path.strip(), "start": int(a) if a else None, "end": int(b) if b else None})
            except Exception as e:  # noqa: BLE001
                r = f"(не прочитать: {e})"
            out.append(f"### {s}\n{str(r)[:per]}")
        self._emit(t)
        return "\n\n".join(out) or "(ничего не прочитано)"

    def _review(self, t, summary, files, facts, diff, res, outs, hc, claims, findings, what="итог"):
        """Проверяющий-подагент (выпуски 3 и 6): чистый контекст — цель, критерии, выдержки файлов и источников; может
        дочитать (VERIFY_LOOKS раз: файлы задачи и ссылки — только чтение, те же права). Сильная модель — tasks.judge_llm.
        -> ("ok" | "revise" | "unclear", замечания) или None (проверяющий выключен или окно крошечное без judge_llm)."""
        win = int(t.data.get("win") or WIN_DEFAULT)
        judge = self._judge(t)
        light = bool(t.data.get("light"))
        if self._opt("self_check") is False or (win < TINY_WIN and not judge):
            return None
        if judge:
            if not t.data.get("judge_win"):
                t.data["judge_win"] = self._window(judge)
            jwin, short = int(t.data["judge_win"]), False
        else:
            jwin, short = win, light
        budget = int(max(2500, min(30000, jwin * 3 * (0.3 if short else 0.35))))
        ex, used = [], 0
        per = max(500, min(3000, budget // max(1, min(6, len(outs) or 1)) // (2 if Q.claim_urls(claims) else 1)))
        for p in outs[:8]:
            try:
                rel = p.relative_to(t.dir).as_posix()
            except ValueError:
                rel = str(p)
            if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp3", ".wav", ".mp4", ".zip"):
                continue
            if hc and str(p) in hc:
                body = "[в браузере] " + (hc[str(p)]["text"] or "(пусто)") + (" [есть горизонтальная прокрутка на телефоне]" if hc[str(p)]["overflow"] else "")
            else:
                body = Q.file_text(p, limit=per * 2)
                if p.suffix.lower() in (".html", ".htm"):
                    body = re.sub(r"\s+", " ", re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>|<[^>]+>", " ", body))
            body = body.strip()
            if len(body) > per:                            # экзамен 0.84.1: обрезанную выдержку проверяющий принимал за обрыв файла
                body = body[:per] + f"\n…[выдержка обрезана: показано {per} из {len(body)} знаков, файл целиком больше — это не обрыв]"
            if used + len(body) > budget:
                break
            used += len(body)
            ex.append(f"### {rel}\n{body or '(пусто)'}")
        srcs = []
        for u in Q.claim_urls(claims)[:6 if not short else 3]:
            block = self._src_block(t, u)
            if not block and not short and len(srcs) < 6:
                block = self._fetch_src(t, u)
            if block:
                srcs.append(f"- {u}\n{block[:max(400, (budget - used) // 6)]}")
        crit_txt = "\n".join(("✓ " if r.get("ok") else "? ") + Q.crit_label(r) + (f" ({r['detail']})" if r.get("detail") else "") for r in res)
        if t.criteria().get("was"):
            crit_txt += "\n(критерии менялись после непройденной проверки; прежние: " + " / ".join("; ".join(x) for x in t.criteria()["was"])[:400] + ")"
        sub = self._sub_begin(t, "verify", what)
        t.data["activity"] = "проверяющий сверяет " + ("итог" if what == "итог" else "сделанное")
        self._emit(t)

        def ask(s_, m_):
            if t.cancel.is_set():
                raise LLMError("задачу остановили")
            self._beat(t, "verify")
            r = self._ask_with(judge, s_, m_) if judge else self._ask(s_, m_)
            sub["steps"] += 1
            self._sub_usage(t, sub, s_ + json.dumps(m_, ensure_ascii=False), r)
            return r
        looks = 1 if short else VERIFY_LOOKS
        per_look = max(600, min(4000, budget // 4))
        verdict, problems = Q.verify_task(ask, f"{t.title}\n{t.goal}", summary, files, facts, diff=diff, criteria=crit_txt,
                                          excerpts="\n\n".join(ex), sources="\n".join(srcs), findings="\n".join(findings), short=short,
                                          look=lambda items: self._look(t, items, per_look, short, sub), looks=looks)
        self._sub_end(t, sub, "stopped" if t.cancel.is_set() else "done", {"ok": "подтверждено", "revise": problems}.get(verdict, "непонятный ответ"))
        sub["verdict"] = verdict
        t.data["activity"] = ""
        return verdict, problems
