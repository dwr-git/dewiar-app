"""«Платежи» в ядре (payments.py): команды окна (студия → «Платежи»), голосом без модели («оплатил газ 47,84, показания
28135», «что не оплачено?», «как платить за свет?», «сколько я заплатил за газ в этом году?»), напоминание о сроке
(накануне и в день срока — раз в 10 минут проверка), перенос из старого органайзера (разбор текста сам или моделью)."""
import base64
import json
import logging
import re
import threading

from payments import fmt_money, fmt_num, import_apply, parse_import, parse_voice, year_sum

log = logging.getLogger("dewiar.pay")

IMPORT_PROMPT = (
    "Тебе дают текст из личного органайзера, где человек годами записывает обязательные платежи (коммунальные, связь, "
    "кредиты): разделы по каждому платежу, строки вида «ДД.ММ.ГГ — показание (расход = сумма)», реквизиты, телефоны. "
    "Разложи это в JSON — массив разделов, без пояснений и без ```: "
    '[{"name": "короткое название платежа («Газ», «Электричество», «Интернет», «Кредит»)", '
    '"kind": "meter (есть счётчик/показания) | fixed (постоянная сумма) | loan (кредит, рассрочка) | yearly (раз в год) | other", '
    '"how": "реквизиты, номер абонента, путь оплаты, телефоны — как в тексте, построчно", "day": число месяца, когда обычно платят, '
    '"autopay": true/false, "pays": [{"date": "ГГГГ-ММ-ДД", "reading": показание или null, "used": расход или null, '
    '"amount": сумма в рублях или null, "note": "короткая пометка или пусто", "status": "paid" или "unpaid" (если «не погашено»)}]}]. '
    "Числа — числами (точка как разделитель). Ничего не выдумывай: нет суммы — null. Года «26» — это 2026.")


class PayMixin:
    def _pay_cmd(self, cmd, a):
        pm = self.payments
        if cmd == "pay_overview":
            return pm.overview()
        if cmd == "pay_grid":
            return pm.year_grid(int(a.get("year") or 0) or __import__("datetime").date.today().year)
        if cmd == "pay_stats":
            return pm.stats(int(a.get("year") or 0) or __import__("datetime").date.today().year)
        if cmd == "pay_list":
            return pm.pays_of(a.get("bill") or "")
        if cmd == "pay_bill_save":
            r = pm.bill_save(a.get("bill") or a)
        elif cmd == "pay_bill_delete":
            r = pm.bill_delete(a.get("id") or "")
        elif cmd == "pay_reorder":
            r = pm.reorder(a.get("ids") or [])
        elif cmd == "pay_save":
            r = pm.pay_save(a.get("pay") or a)
        elif cmd == "pay_delete":
            r = pm.pay_delete(a.get("id") or "")
        elif cmd == "pay_attach":                         # вложение: из буфера (Ctrl+V), перетаскиванием или кнопкой
            raw = str(a.get("data") or "")
            raw = raw.split(",", 1)[1] if raw.startswith("data:") else raw
            data = base64.b64decode(raw)
            if len(data) > 25 * 1024 * 1024:
                raise ValueError("файл больше 25 МБ")
            r = pm.attach(a.get("target") or "bill", a.get("id") or "", a.get("name") or "файл.png", data)
        elif cmd == "pay_detach":
            r = pm.detach(a.get("target") or "bill", a.get("id") or "", a.get("aid") or "")
        elif cmd == "pay_file":                           # картинка вложения -> data: для показа в окне (как у заметок)
            from workspace import WorkspaceError
            try:
                return self.workspace.note_file(a.get("path") or "")
            except (WorkspaceError, OSError) as e:
                raise ValueError(str(e)) from e
        elif cmd == "pay_import_parse":
            return {"items": parse_import(a.get("text") or "")}
        elif cmd == "pay_import_ai":
            return {"items": self._pay_import_ai(a.get("text") or "")}
        elif cmd == "pay_import_apply":
            r = import_apply(pm, a.get("items") or [])
        else:
            raise ValueError("неизвестная команда")
        self.emit("pay_saved", what=cmd)
        return r

    def _pay_import_ai(self, text):
        """Разбор текста моделью (для неровных записей); не вышло — тот же разбор правилами."""
        prof = self.s.active_llm()
        if not prof or len(text) > 60000:
            return parse_import(text)
        from llm import LLMError, stream_events
        out = ""
        try:
            for kind, val in stream_events(dict(prof, temperature=0.1, max_tokens=12000), IMPORT_PROMPT,
                                           [{"role": "user", "content": text}], tools=None):
                if kind == "text":
                    out += val
        except (LLMError, Exception) as e:  # noqa: BLE001
            log.info("Платежи: разбор моделью не вышел (%s) — правилами", e)
            return parse_import(text)
        m = re.search(r"\[[\s\S]*\]", out)
        try:
            items = json.loads(m.group(0)) if m else None
        except ValueError:
            items = None
        if not isinstance(items, list) or not items:
            return parse_import(text)
        clean = []
        for it in items:
            if not isinstance(it, dict) or not str(it.get("name") or "").strip():
                continue
            pays = [p for p in it.get("pays") or [] if isinstance(p, dict) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(p.get("date") or ""))]
            clean.append({"name": str(it["name"]).strip()[:40], "kind": it.get("kind") if it.get("kind") in
                          ("meter", "fixed", "loan", "yearly", "other") else "fixed", "how": str(it.get("how") or "")[:4000],
                          "day": it.get("day") if isinstance(it.get("day"), int) else None, "autopay": bool(it.get("autopay")),
                          "pays": pays})
        return clean or parse_import(text)

    def _pay_voice(self, text, via=None):
        """Платежи голосом без модели. -> True, если ответили."""
        pm = getattr(self, "payments", None)
        if pm is None:
            return False
        c = parse_voice(text, pm)
        if not c:
            return False
        if c["op"] == "open":
            msg = pm.text_report("open")
        elif c["op"] == "how":
            msg = pm.text_report(c["bill"]["id"])
        elif c["op"] == "sum":
            s, n = year_sum(pm, c["bill"]["id"], c["year"])
            msg = (f"За {c['year']} год за «{c['bill']['name']}» — {fmt_money(s)}, оплат: {n}." if n
                   else f"За {c['year']} год оплат за «{c['bill']['name']}» не записано.")
        else:
            b = c["bill"]
            p = pm.pay_save({"bill": b["id"], "date": c["date"], "amount": c["amount"], "reading": c["reading"],
                             "used": c["used"], "status": c["status"]})
            bits = [f"«{b['name']}»"]
            if p.get("amount") is not None:
                bits.append(fmt_money(p["amount"]))
            if p.get("reading") is not None:
                bits.append(f"показание {fmt_num(p['reading'])}")
            if p.get("used") is not None:
                bits.append(f"расход {fmt_num(p['used'])} {b.get('unit') or ''}".rstrip())
            msg = "Записал оплату: " + ", ".join(bits) + "."
            if p.get("status") == "unpaid":
                msg = "Записал: «" + b["name"] + "» — не погашено."
            self.emit("tool", name="payment_add", title="Платежи: оплата", status="done", args={"bill": b["name"], "amount": p.get("amount")},
                      detail=msg, result=msg)
            self.emit("pay_saved", what="pay_save")
        self._say_quick(msg, text, via)
        return True

    def _pay_loop(self):
        """Раз в 10 минут: срок оплаты завтра или сегодня, а не оплачено — сказать один раз (и уведомлением)."""
        if self.stopping.wait(120 if not self.wav_input else 3600 * 24):
            return
        while not self.stopping.is_set():
            try:
                for b, text in self.payments.check_due():
                    log.info("💳 %s", text)
                    self.push("Платежи", text)
                    if not getattr(self, "server", False) and self.state == "idle":
                        self.announce(text)
            except Exception as e:  # noqa: BLE001
                log.warning("Платежи: проверка сроков — %s", e)
            if self.stopping.wait(600):
                return


def t_payments(a, ctx):
    """Инструмент модели «payments»: отчёт, оплата, новый счёт."""
    eng = ctx.get("engine")
    pm = getattr(eng, "payments", None)
    if pm is None:
        from tools import ToolError
        raise ToolError("платежи недоступны")
    act = a.get("action") or "report"
    if act == "add_payment":
        b = pm.bill(a.get("bill") or "")
        if not b:
            from tools import ToolError
            raise ToolError("нет такого платежа. Есть: " + ", ".join(x["name"] for x in pm.bills if not x.get("archived")))
        p = pm.pay_save({"bill": b["id"], "date": a.get("date") or None, "amount": a.get("amount"), "reading": a.get("reading"),
                         "used": a.get("used"), "note": a.get("note") or "", "status": a.get("status") or "paid"})
        eng.emit("pay_saved", what="pay_save")
        return f"Записано в «{b['name']}»: {p['date']}, " + ", ".join(
            x for x in [fmt_money(p.get("amount")) if p.get("amount") is not None else "", f"показание {fmt_num(p['reading'])}" if p.get("reading") is not None else "",
                        f"расход {fmt_num(p['used'])}" if p.get("used") is not None else ""] if x) + "."
    if act == "add_bill":
        b = pm.bill_save({"name": a.get("bill") or a.get("name") or "", "kind": a.get("kind"), "day": a.get("day"),
                          "month": a.get("month"), "autopay": a.get("autopay"), "how": a.get("how") or "", "amount": a.get("amount")})
        eng.emit("pay_saved", what="pay_bill_save")
        return f"Платёж «{b['name']}» добавлен" + (f", срок — {b['day']}-е число" if b.get("day") else "") + ". Он в студии, «Платежи»."
    if act == "year":
        import datetime as _dt
        st = pm.stats(int(a.get("year") or _dt.date.today().year))
        return (f"За {st['year']} год: {fmt_money(st['total'])}" + (f" (за прошлый — {fmt_money(st['total_prev'])})" if st["total_prev"] else "")
                + ". По платежам: " + "; ".join(f"{x['name']} — {fmt_money(x['sum'])}" for x in st["by_bill"]) + ".")
    return pm.text_report(a.get("bill") or ("open" if act == "open" else ""))
