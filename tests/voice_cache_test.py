"""Голос сервера на телефоне без пауз (отзыв 11.10: «как у Алисы»). Обычная Java против настоящего HTTP-сервера:
— VoiceCache.get: короткая фраза второй раз — из памяти, без запроса; длинная — каждый раз с сервера, во временный файл;
  другой голос или скорость (другое тело запроса) — новый звук; запомненных не больше CACHE_MAX, старые — прочь;
— Tts.java: следующая фраза скачивается, пока звучит текущая (пул на две), играют строго по очереди; stop() отменяет
  скачивание; запомненный файл после проигрыша не удаляется."""
import http.server, os, shutil, subprocess, sys, tempfile, threading
from pathlib import Path
SRC = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


if not shutil.which("javac") or not shutil.which("java"):
    print("нет javac — пропуск"); sys.exit(0)
hits = []


class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        hits.append((self.headers.get("Authorization"), body.decode()))
        data = b"RIFF" + body[:40]
        self.send_response(200); self.send_header("Content-Type", "audio/wav"); self.send_header("Content-Length", str(len(data))); self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a): pass


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{srv.server_address[1]}/v1/audio/speech"
tmp = Path(tempfile.mkdtemp())
(tmp / "src/pro/dewiar/app").mkdir(parents=True)
for f in ("VoiceCache.java", "NetProxy.java"):
    shutil.copy(SRC / "android/src/pro/dewiar/app" / f, tmp / "src/pro/dewiar/app" / f)
(tmp / "src/pro/dewiar/app/T.java").write_text("""package pro.dewiar.app;
import java.io.File;
public class T {
  public static void main(String[] a) throws Exception {
    File cache = new File(a[0]); String url = a[1];
    String shortBody = "{\\"input\\":\\"Хорошо.\\",\\"voice\\":\\"serena\\",\\"speed\\":1}";
    StringBuilder lb = new StringBuilder("{\\"input\\":\\""); for (int i = 0; i < 80; i++) lb.append("длинная фраза "); String longBody = lb.append("\\"}").toString();
    File f1 = VoiceCache.get(cache, "s1", url, "dw-k", shortBody);
    File f2 = VoiceCache.get(cache, "s2", url, "dw-k", shortBody);
    File f3 = VoiceCache.get(cache, "s3", url, "dw-k", shortBody.replace("serena", "aiden"));
    File f4 = VoiceCache.get(cache, "s4", url, "dw-k", longBody);
    File f5 = VoiceCache.get(cache, "s5", url, "dw-k", longBody);
    System.out.println("short " + VoiceCache.cached(f1) + " " + f1.equals(f2) + " " + f2.length());
    System.out.println("voice " + (!f3.equals(f1)) + " " + VoiceCache.cached(f3));
    System.out.println("long " + VoiceCache.cached(f4) + " " + f4.getName() + " " + f5.getName());
    for (int i = 0; i < VoiceCache.CACHE_MAX + 15; i++) { File x = VoiceCache.get(cache, "k" + i, url, "", "{\\"input\\":\\"фраза " + i + "\\"}"); x.setLastModified(1000000L + i * 1000L); }
    System.out.println("lru " + new File(cache, "tts").listFiles().length);
  }
}
""", encoding="utf-8")
c = subprocess.run(["javac", "-nowarn", "-encoding", "UTF-8", "-d", str(tmp / "cls"), *map(str, (tmp / "src/pro/dewiar/app").glob("*.java"))], capture_output=True, text=True)
clean = lambda t: "\n".join(x for x in t.splitlines() if "JAVA_TOOL_OPTIONS" not in x and "Note:" not in x)[-300:]
ok(c.returncode == 0, f"VoiceCache собирается обычной Java {clean(c.stderr)}")
r = subprocess.run(["java", "-cp", str(tmp / "cls"), "pro.dewiar.app.T", str(tmp / "cache"), URL], capture_output=True, text=True, timeout=120)
out = dict(ln.split(" ", 1) for ln in r.stdout.splitlines() if " " in ln)
ok(out.get("short", "").startswith("true true") and sum(1 for _, b in hits[:3] if "serena" in b) == 1,
   f"короткая фраза: второй раз — из памяти, без запроса к серверу: {out.get('short')} {clean(r.stderr)}")
ok(out.get("voice") == "true true", "другой голос — свой звук")
ok(out.get("long") == "false say-s4.audio say-s5.audio" and sum(1 for _, b in hits if "длинная" in b) == 2, f"длинная — каждый раз с сервера, во временный файл: {out.get('long')}")
ok(hits[0][0] == "Bearer dw-k", "ключ — в заголовке Authorization")
ok(out.get("lru") == "200", f"запомненных не больше 200: {out.get('lru')}")
srv.shutdown()
tts = (SRC / "android/src/pro/dewiar/app/Tts.java").read_text(encoding="utf-8")
ok("newFixedThreadPool(2)" in tts and "VoiceCache.get(" in tts and "x.cancel(true)" in tts and "if (temp)" in tts and "got.get()" in tts,
   "Tts: скачивание наперёд (две фразы), очередь проигрыша, stop() отменяет, запомненное не удаляется")
src_vc = (SRC / "android/src/pro/dewiar/app/VoiceCache.java").read_text(encoding="utf-8")
ok("long slot = System.currentTimeMillis() / SLOT_MS;" in src_vc and 'body + "\\n" + slot' in src_vc and "SLOT_MS = 12L * 3600 * 1000" in src_vc,
   "запомненная фраза живёт не дольше полудня — новый голос персонажа на сервере слышен и в коротких фразах (владелец 11.11)")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
