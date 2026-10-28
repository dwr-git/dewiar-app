"""Микрофон выключен и ложные срабатывания (отзыв 14.10: «часто удобно, чтобы Лира была, но не слушала фон — выключаю
микрофон, а виджет темнеет и некрасив»; «ложно сработала — нажимаю на лицо, замолкает, и опять начинает»):
— «микрофон выключен»: портрет в полную яркость и цвет, как в покое (видно по значку и подписи); «нет связи» — тусклый;
— остановили нажатием ответ, начатый по голосу, в первые секунды — минуту не откликаемся на голос, нажатие работает;
  остановили ответ, начатый кнопкой, — ничего не глушим."""
import io, os, shutil, subprocess, sys, tempfile, time
from PIL import Image, ImageStat
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# ── 1. яркость портрета: покой / микрофон выключен / нет связи ──
tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
shutil.copy(ROOT / "ui/assets/entities.js", www / "entities.js")
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 240, "height": 240})
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(2500)          # Лира с живым лицом, как в приложении
    def lum(state):
        pg.evaluate(f"() => {{ orb.set({{ state: '{state}' }}); }}"); pg.wait_for_timeout(1800)
        img = Image.open(io.BytesIO(pg.locator("#orb").screenshot())).convert("L")      # file:// — getImageData нельзя
        return ImageStat.Stat(img).mean[0]
    L = {s: lum(s) for s in ("idle", "muted", "offline", "idle")}
    b.close()
ok(L["muted"] >= L["idle"] * 0.9, f"микрофон выключен — портрет не темнеет: покой {L['idle']:.1f}, выключен {L['muted']:.1f}")
ok(L["offline"] < L["idle"] * 0.9, f"нет связи — портрет притушен: {L['offline']:.1f}")
shutil.rmtree(tmp, ignore_errors=True)

# ── 2. минута тишины после ложного срабатывания ──
import engine_commands as EC  # noqa: E402


class E(EC.CommandsMixin):
    def __init__(self):
        self.muted, self.state, self.wake_time, self._quiet_until = False, "speaking", 0.0, 0.0
        self.status, self.follow_up_until, self.calls = {"note": ""}, 0.0, []
    def interrupt(self, reason, follow=True): self.calls.append(("interrupt", reason, follow)); self.state = "idle"
    def play_tone(self, t): self.calls.append(("tone", t))
    def note(self, t): self.status["note"] = t
    def _g(self, t): return t
    def listen_for_command(self, s=8): self.calls.append(("listen", s)); self.state = "listening"
    def go_sleep(self, word="", media=True): self.calls.append(("sleep", word)); self.state = "idle"


e = E(); e.wake_time = time.monotonic() - 6                      # имя услышано 6 с назад, отвечает
r = e.command("ptt", {})
ok(r == "sleep" and ("interrupt", "кнопка", False) in e.calls and e._quiet_until - time.monotonic() > 55,
   f"остановили ответ по голосу в первые секунды — минуту не откликаемся на голос: {e._quiet_until - time.monotonic():.0f} с")
ok("нажатием на лицо" in e.status["note"], f"и об этом сказано в виджете: {e.status['note']}")
r1 = e.command("ptt", {})
ok(r1 == "sleep" and ("listen", 8) not in e.calls, "28.10: судорожное второе нажатие сразу после «стоп» — тоже «стоп», а не «слушай»")
e._ptt_stop_at -= 3
r2 = e.command("ptt", {})
ok(r2 == "listening" and ("listen", 8) in e.calls, "нажатие на лицо в эту минуту (не сразу) — слушает как обычно")
e4 = E(); e4.state = "listening"; e4.wake_time = time.monotonic() - 2      # 28.10: сработала сама по голосу и слушает разговор
r4 = e4.command("ptt", {})
ok(r4 == "sleep" and ("sleep", "кнопка") in e4.calls and e4._quiet_until - time.monotonic() > 55,
   "сработала сама и слушает — нажатие: перестала слушать и минуту не откликается на голос (разговор рядом её не будит)")
e5 = E(); e5.state = "listening"; e5.wake_time = 0.0                       # слушает, потому что нажали
e5.command("ptt", {})
ok(e5._quiet_until == 0.0 and ("sleep", "кнопка") in e5.calls, "слушала по нажатию — второе нажатие просто «стоп», голос не глушим")
e2 = E(); e2.wake_time = 0.0                                      # ответ начат кнопкой (имени не было)
e2.command("ptt", {})
ok(e2._quiet_until == 0.0 and not e2.status["note"], "ответ, начатый кнопкой, остановили — голос не глушим")
e3 = E(); e3.wake_time = time.monotonic() - 60                    # долгий разговор по голосу — остановили спустя минуту
e3.command("ptt", {})
ok(e3._quiet_until == 0.0, "остановили спустя минуту разговора — это не ложное срабатывание")
src = (ROOT / "core/engine_audio.py").read_text(encoding="utf-8")
ok('if kind == "wake" and self.state == "idle" and now < self._quiet_until:' in src, "быстрый слух: имя в эту минуту пропускается")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
