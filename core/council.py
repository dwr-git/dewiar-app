"""«Совет ИИ» (0.67; владелец 28.10: «несколько персонажей с разными ИИ-моделями — раздел, где выносим идею, а они все
вместе отвечают, спорят и помогают; чтобы как живые, захватывающе и убедительно»). Развитие «Спора моделей» (debate.py):
за столом — персонажи (у каждого свой характер и, если задан, свой мозг: llm.persona[id]), ведёт совет главный персонаж.

Три круга, всё — потоком в студию (событие «council»: {sid, phase, who, delta | text, done}):
  1) «Мнения» — каждый отвечает сам, одновременно, в своём характере (4–6 предложений, своя позиция);
  2) «Спор» — каждый видит остальных и отвечает им по имени: с чем согласен, с чем нет и почему (2–4 предложения);
  3) «Итог» — ведущий подводит: в чём сошлись, где разошлись, что советует совет и первый шаг.
Протокол — Markdown в папке ассистента «Совет/‹дата› ‹вопрос›.md» (список прошлых — council_list). Остановить — stop().
Модель участника не ответила — его место помечается «не ответил», совет идёт дальше; не ответил никто — честная ошибка."""

import logging
import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from llm import stream_chat

log = logging.getLogger("dewiar.council")
MAX_MEMBERS = 5

R1 = ("Ты — {name}, участник «Совета ИИ»: несколько помощников с разными характерами и моделями вместе обсуждают вопрос "
      "человека. Твой характер: {char} Ответь на вопрос по существу и со своей позицией — 4–6 предложений, главные доводы, "
      "живо и в своём стиле, без воды, без списков и заголовков. Не пиши, что ты модель ИИ, не здоровайся.")
R2 = ("Ты — {name}, участник «Совета ИИ». Твой характер: {char} Ниже вопрос и ответы всех участников. Ответь коллегам — 2–4 "
      "предложения, обращаясь по имени: с кем и в чём согласен, с чем не согласен и почему; можешь уточнить свою позицию. "
      "Спорь по делу, уважительно, без повторов своего ответа и без списков.")
R3 = ("Ты — {name}, ведущий «Совета ИИ». Подведи итог обсуждения для человека, который задал вопрос: 1) в чём участники "
      "сошлись; 2) где разошлись и почему; 3) что советует совет — ясная рекомендация; 4) первый шаг, который можно сделать "
      "сегодня. Коротко (до 120 слов), четыре абзаца с этими подзаголовками жирным: **Сошлись**, **Разошлись**, **Совет**, "
      "**Первый шаг**. Называй участников по имени.")


def spoken_summary(md):
    """Итог вслух — коротко: «Совет» и «Первый шаг» (весь разбор — на экране и в протоколе)."""
    secs, cur = {}, None
    for line in str(md or "").splitlines():
        m = re.match(r"^\s*(?:\*\*|#+\s*)?([^*#:]{3,20}?)(?:\*\*)?\s*:?\s*$", line)
        if m and m.group(1).strip().lower() in ("сошлись", "разошлись", "совет", "первый шаг"):
            cur = m.group(1).strip().lower(); secs[cur] = ""
        elif cur:
            secs[cur] += " " + line.strip()
    adv, step = secs.get("совет", "").strip(), secs.get("первый шаг", "").strip()
    if not adv and not step:
        txt = re.sub(r"[*#]+", "", str(md or "")).strip()
        return "Совет закончил. " + (txt[:280].rsplit(" ", 1)[0] + "…" if len(txt) > 280 else txt)
    out = "Совет закончил. " + (f"Советуют {adv[0].lower() + adv[1:].rstrip('.')}. " if adv else "") + (f"Первый шаг — {step[0].lower() + step[1:]}" if step else "")
    return re.sub(r"[*_`]+", "", out).strip()


class CouncilError(Exception):
    pass


def _clean(t):
    t = re.sub(r"<think>.*?</think>", "", str(t or ""), flags=re.S)
    return t.strip()


class Council:
    """host: personas, s (настройки), emit(type, **kw), workspace (root). Одновременно — один совет."""

    def __init__(self, host):
        self.host = host
        self.cur = None
        self._lock = threading.Lock()

    # ---------- кто за столом ----------
    def profile_for(self, pid):
        """Мозг персонажа: свой (llm.persona[id]) или общий. -> (профиль, имя модели для подписи)."""
        llm = self.host.s.get("llm") or {}
        profs = llm.get("profiles") or {}
        own = (llm.get("persona") or {}).get(pid) or ""
        p = dict(profs.get(own) or profs.get(llm.get("active")) or {})
        label = "Dewiar" if p.get("cloud") else (str(p.get("model") or "").split("/")[-1] or p.get("name") or "")
        return p, label

    def members(self):
        """Персонажи для выбора: {id, name, role, color, style, avatar_url, live, model, own} — сначала со своим мозгом."""
        llm = self.host.s.get("llm") or {}
        own = llm.get("persona") or {}
        out = []
        pub = getattr(self.host.personas, "public", None)
        for p in (pub() if callable(pub) else self.host.personas.all()):
            if p.get("kids"):
                continue
            _, label = self.profile_for(p["id"])
            out.append({"id": p["id"], "name": p.get("name", ""), "role": p.get("role", ""), "color": p.get("color", "#8B7CFF"),
                        "style": p.get("style", "nexus"), "avatar_url": p.get("avatar_url") or "", "live": p.get("live") or "",
                        "model": label, "own": bool(own.get(p["id"]))})
        main = self.host.s.get("persona")
        out.sort(key=lambda m: (m["id"] != main, not m["own"]))
        return out

    def default_pick(self):
        """Кого позвать, если не выбрали: ведущий и до трёх со своим мозгом; своих мозгов нет — ещё двое самых разных."""
        ms = self.members()
        main = self.host.s.get("persona")
        pick = [m["id"] for m in ms if m["id"] == main]
        pick += [m["id"] for m in ms if m["own"] and m["id"] != main][:3]
        if len(pick) < 3:
            pick += [m["id"] for m in ms if m["id"] not in pick][:3 - len(pick)]
        return pick[:MAX_MEMBERS]

    # ---------- ход совета ----------
    def start(self, question, pids=None, announce=False):
        """announce — позвали голосом: итог Лира скажет сама, когда совет закончит (ждать молча минуту-две — нельзя)."""
        q = re.sub(r"\s+", " ", str(question or "")).strip()
        if len(q) < 5:
            raise CouncilError("о чём совет? напишите вопрос или идею целиком")
        with self._lock:
            if self.cur and not self.cur["done"]:
                raise CouncilError("совет уже идёт — дождитесь итога или остановите")
            known = {m["id"]: m for m in self.members()}
            pids = [p for p in (pids or self.default_pick()) if p in known][:MAX_MEMBERS]
            if len(pids) < 2:
                raise CouncilError("для совета нужно хотя бы двое — выберите участников")
            if not any(self.profile_for(p)[0].get("base_url") for p in pids):
                raise CouncilError("сначала подключите мозг — студия → «Мозг»")
            sid = uuid.uuid4().hex[:10]
            chair = self.host.s.get("persona") if self.host.s.get("persona") in pids else pids[0]
            self.cur = {"sid": sid, "q": q, "pids": pids, "chair": chair, "t": time.time(), "done": False, "cancel": threading.Event(),
                        "said": {p: {} for p in pids}, "summary": "", "file": "", "announce": bool(announce)}
        threading.Thread(target=self._run, args=(self.cur,), name="council", daemon=True).start()
        return {"sid": sid, "pids": pids, "chair": chair, "members": [known[p] for p in pids]}

    def stop(self):
        c = self.cur
        if c and not c["done"]:
            c["cancel"].set()
            return True
        return False

    def state(self):
        c = self.cur
        if not c:
            return None
        return {k: c[k] for k in ("sid", "q", "pids", "chair", "done", "summary", "file")} | {"said": c["said"]}

    def _emit(self, c, **kw):
        try:
            self.host.emit("council", sid=c["sid"], **kw)
        except Exception:  # noqa: BLE001
            log.debug("совет: событие", exc_info=True)

    def _say(self, c, pid, phase, system, text, max_tokens):
        """Один участник говорит потоком: куски — в студию не чаще ~10 раз в секунду. -> текст или ""."""
        prof, _ = self.profile_for(pid)
        buf, last, sent = "", 0.0, 0
        self._emit(c, phase=phase, who=pid, start=True)
        try:
            for chunk in stream_chat(dict(prof, max_tokens=max_tokens, temperature=0.75), system,
                                     [{"role": "user", "content": text}], c["cancel"]):
                buf += chunk
                now = time.monotonic()
                if now - last > 0.1:
                    vis = _clean(buf)
                    if len(vis) > sent:
                        self._emit(c, phase=phase, who=pid, delta=vis[sent:])
                        sent = len(vis)
                    last = now
            out = _clean(buf)
            if len(out) > sent:
                self._emit(c, phase=phase, who=pid, delta=out[sent:])
            if not out and not c["cancel"].is_set():
                raise RuntimeError("модель ответила пустотой")
            self._emit(c, phase=phase, who=pid, done=True, text=out)
            return out
        except Exception as e:  # noqa: BLE001
            log.info("Совет: %s не ответил(а): %s", pid, e)
            self._emit(c, phase=phase, who=pid, done=True, text="", error=str(e)[:160])
            return ""

    def _round(self, c, phase, make):
        """Все участники одновременно. make(pid) -> (system, text, max_tokens) или None (пропустить)."""
        ths = []
        for pid in c["pids"]:
            m = make(pid)
            if m is None:
                continue

            def go(pid=pid, m=m):
                c["said"][pid][phase] = self._say(c, pid, phase, *m)
            t = threading.Thread(target=go, daemon=True)
            t.start()
            ths.append(t)
            time.sleep(0.35)                              # не все разом — живее и легче для сервиса моделей
        for t in ths:
            t.join()

    def _run(self, c):
        names = {p["id"]: p for p in self.host.personas.all()}
        nm = lambda pid: (names.get(pid) or {}).get("name", pid)  # noqa: E731
        ch = lambda pid: re.sub(r"\s+", " ", str((names.get(pid) or {}).get("character") or "")).strip()[:600]  # noqa: E731
        try:
            self._emit(c, phase="r1", begin=True)
            self._round(c, "r1", lambda pid: (R1.format(name=nm(pid), char=ch(pid)), "Вопрос: " + c["q"], 600))
            ok = [p for p in c["pids"] if c["said"][p].get("r1")]
            if c["cancel"].is_set():
                return self._finish(c, stopped=True)
            if not ok:
                return self._finish(c, error="никто из участников не ответил — проверьте мозг в студии → «Мозг»")
            first = "\n\n".join(f"{nm(p)}: {c['said'][p]['r1']}" for p in ok)
            if len(ok) >= 2:
                self._emit(c, phase="r2", begin=True)
                self._round(c, "r2", lambda pid: (R2.format(name=nm(pid), char=ch(pid)),
                                                  f"Вопрос: {c['q']}\n\nОтветы участников:\n\n{first}", 350) if pid in ok else None)
            if c["cancel"].is_set():
                return self._finish(c, stopped=True)
            talk = first + "\n\n" + "\n\n".join(f"{nm(p)} (ответ коллегам): {c['said'][p]['r2']}" for p in ok if c["said"][p].get("r2"))
            self._emit(c, phase="sum", begin=True)
            chair = c["chair"] if c["said"][c["chair"]].get("r1") else ok[0]
            c["summary"] = self._say(c, chair, "sum", R3.format(name=nm(chair)), f"Вопрос: {c['q']}\n\nОбсуждение:\n\n{talk}", 700)
            self._finish(c)
        except Exception as e:  # noqa: BLE001
            log.exception("совет")
            self._finish(c, error=str(e)[:200])

    def _finish(self, c, stopped=False, error=""):
        c["done"] = True
        try:
            c["file"] = self._save(c)
        except Exception as e:  # noqa: BLE001
            log.info("Совет: протокол не сохранился: %s", e)
        self._emit(c, phase="end", stopped=stopped, error=error, file=c["file"], summary=c["summary"])
        if c.get("announce") and not stopped and hasattr(self.host, "announce"):
            try:
                self.host.announce(spoken_summary(c["summary"]) if c["summary"] else
                                   "Совет не смог подвести итог: модели не ответили. Проверьте «Мозг» в студии.")
            except Exception:  # noqa: BLE001
                log.info("Совет: итог вслух не прозвучал", exc_info=True)

    def _save(self, c):
        """Протокол — «Совет/‹дата› ‹вопрос›.md». -> относительный путь."""
        if not any(v for s in c["said"].values() for v in s.values()):
            return ""
        names = {p["id"]: p for p in self.host.personas.all()}
        nm = lambda pid: (names.get(pid) or {}).get("name", pid)  # noqa: E731
        root = Path(self.host.workspace.ensure()) / "Совет"
        root.mkdir(parents=True, exist_ok=True)
        title = re.sub(r'[\\/:*?"<>|\n\r\t]+', " ", c["q"])[:60].strip(" .") or "Совет"
        f = root / f"{datetime.fromtimestamp(c['t']).strftime('%Y-%m-%d %H-%M')} {title}.md"
        lines = [f"# Совет ИИ: {c['q']}", "", "Участники: " + ", ".join(f"{nm(p)} ({self.profile_for(p)[1] or 'модель'})" for p in c["pids"]), ""]
        for ph, head in (("r1", "Мнения"), ("r2", "Спор")):
            items = [(p, c["said"][p].get(ph)) for p in c["pids"] if c["said"][p].get(ph)]
            if items:
                lines += [f"## {head}", ""] + [f"**{nm(p)}.** {t}\n" for p, t in items]
        if c["summary"]:
            lines += ["## Итог", "", c["summary"], ""]
        f.write_text("\n".join(lines), encoding="utf-8")
        return f"Совет/{f.name}"

    def history(self, limit=20):
        """Прошлые советы: [{file, title, t}] — новые сверху."""
        root = Path(self.host.workspace.ensure()) / "Совет"
        if not root.is_dir():
            return []
        fs = sorted(root.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
        return [{"file": f"Совет/{f.name}", "title": re.sub(r"^\d{4}-\d{2}-\d{2} \d{2}-\d{2} ", "", f.stem), "t": int(f.stat().st_mtime)} for f in fs]
