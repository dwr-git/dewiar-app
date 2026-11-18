//@ Телефон и веб-версия, часть 23: «Компания» — кто платит за ответы, код от компании.
//@ Собирается в android/assets/www/app.js (tools/app_join.py) — порядок частей = порядок исполнения; шапка «//@» в app.js не попадает.
/* ---------- «Компания» на телефоне (пилот 18.11; сервер — server/dwrapp/cloud/company.php, студия — ui/studio/company.js).
   «Мозг» → «Баланс»: в компании — кто платит, свой лимит и потрачено, «Пополнить» прячется у сотрудника (пополняет
   руководитель), «Выйти из компании»; не в компании — «Код от компании». Места и приглашения — у руководителя на компьютере. */
const coNumP = (v) => { const n = +v || 0; return (Math.abs(n) < 0.01 && n ? n.toFixed(4) : n.toFixed(2)).replace(/\.?0+$/, "").replace(".", ","); };
function coPhoneFill(c) {
  const box = $("#cl-co"), join = $("#cl-join");
  if (!box || !join) return;
  const co = c && c.company;
  join.hidden = !!co || !!c.site || !!S.llm.account;
  box.hidden = !co;
  if (!co) return;
  const lim = +co.lim || 0;
  $("#cl-sub").textContent = `Компания «${co.name}»`;
  $("#cl-co-t").textContent = co.role === "owner"
    ? `Вы — руководитель. Котёл компании: доля месяца ${coNumP(co.month_left)} + начислено ${coNumP(co.bought)} тал. Мест: ${co.seats_n}. Места и приглашения — в Лире на компьютере: «Поручения».`
    : `За ответы Лиры платит компания «${co.name}». ` + (lim ? `Ваш лимит — ${coNumP(lim)} тал. в месяц, потрачено ${coNumP(co.spent_month)}.` : `Потрачено в этом месяце: ${coNumP(co.spent_month)} тал.`);
  const go = $("#cl-co-go");
  go.hidden = co.role === "owner";
  go.onclick = async () => {
    if (!confirm(`Выйти из компании «${co.name}»? Ответы Лиры снова будет оплачивать ваш собственный баланс.`)) return;
    try { await cloudPost("/company", { op: "leave" }); toast("Вы вышли из компании"); cloudBalance(true).then(cloudFill).catch(() => {}); } catch (e) { toast(e.message); }
  };
  if (co.role !== "owner") { const how = $("#cl-how"); if (how) how.style.display = "none"; const pay = $("#cl-pay"); if (pay) pay.style.display = "none"; }
}
document.addEventListener("click", async (e) => {
  if (!e.target.closest || !e.target.closest("#cl-join-go")) return;
  const res = $("#cl-join-res"), code = ($("#cl-join-code").value || "").trim();
  if (!/^[A-Za-z0-9]{4}-?[A-Za-z0-9]{4}$/.test(code)) { res.textContent = "Код — 8 знаков, как его дал руководитель: XXXX-XXXX"; return; }
  e.target.disabled = true;
  try {
    const r = await cloudPost("/company", { op: "join", code });
    res.textContent = r.message || "Вы в компании";
    $("#cl-join-code").value = "";
    setTimeout(() => cloudBalance(true).then(cloudFill).catch(() => {}), 300);
  } catch (x) { res.textContent = x.message; }
  finally { e.target.disabled = false; }
});
