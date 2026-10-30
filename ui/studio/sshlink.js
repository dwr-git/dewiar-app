/* Студия → «Dewiar.pro» → «Сеть» → «Запасной вход через SSH» (29.10, владелец: «домен не восстанавливается, а на сервер
   Лиры по SSH захожу — можно, чтобы Лира работала через SSH?»; «только для меня»). Видно только на компьютере, который
   хоть раз ходил к сайту напрямую в сети сервера (net.lan_seen), или если уже настроено. Ядро — core/sshlink.py:
   sshlink (состояние), sshlink_save (включить/выключить с полями), sshlink_test («Проверить»: туннель и подпись сайта). */
const SSH_F = ["host", "user", "port", "target", "key"];
const sshVals = () => Object.fromEntries(SSH_F.map(k => [k, $("#sl-" + k).value.trim()]));
function sshRender(d, keepFields) {
  const box = $("#dw-ssh"); if (!box || !d) return;
  box.hidden = !d.visible;
  if (!keepFields) SSH_F.forEach(k => { $("#sl-" + k).value = d[k] == null || (k === "port" && +d[k] === 22) ? "" : d[k]; });
  $("#sl-on").checked = !!d.on;
  const r = $("#sl-res");
  if (!d.ssh) { r.className = "res bad"; r.textContent = "На этом компьютере нет программы ssh — в Windows: «Параметры» → «Дополнительные компоненты» → «Клиент OpenSSH»."; return; }
  r.className = "res" + (d.state === "error" ? " bad" : d.state === "up" ? " ok" : "");
  r.textContent = d.state === "up" ? "Сейчас Лира работает через SSH: домен не отвечает. Вернётся — туннель закроется сам."
    : d.state === "error" ? d.error : d.on ? "Включено: домен отвечает — туннель не нужен. Проверяю раз в 30 секунд." : "";
}
async function sshLoad() { try { sshRender(await core.call("sshlink")); } catch (e) { } }
$("#sl-on").onchange = async (ev) => {
  const on = ev.target.checked, r = $("#sl-res"); ev.target.disabled = true;
  try { sshRender(await core.call("sshlink_save", Object.assign(sshVals(), { on })), true); if (on) toast("Запасной вход через SSH включён"); }
  catch (e) { ev.target.checked = !on; r.className = "res bad"; r.textContent = e.message; }
  ev.target.disabled = false;
};
$("#sl-test").onclick = async (ev) => {
  const r = $("#sl-res"); ev.target.disabled = true; r.className = "res"; r.textContent = "поднимаю туннель и проверяю сайт за ним…";
  try { const d = await core.call("sshlink_test", sshVals());
    if (d.ok) { await core.call("sshlink_save", Object.assign(sshVals(), { on: $("#sl-on").checked })).catch(() => { }); }
    sshRender(d, true); r.className = "res " + (d.ok ? "ok" : "bad");
    r.textContent = d.ok ? "Работает: сервер пустил по ключу, за туннелем — наш сайт." + ($("#sl-on").checked ? "" : " Включите переключатель — и при сбое домена Лира перейдёт сама.") : d.error; }
  catch (e) { r.className = "res bad"; r.textContent = e.message; }
  ev.target.disabled = false;
};
$("#dw-more") && $("#dw-more").addEventListener("toggle", () => { if ($("#dw-more").open) sshLoad(); });
core.on("hello", () => setTimeout(sshLoad, 400));
window.sshLoad = sshLoad;
