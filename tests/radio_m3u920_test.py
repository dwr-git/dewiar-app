"""№920 (ПК 1.0.48): «Раздел „Музыка“: не воспроизводит поток https://sovietwave.su/sovietwave.m3u — в VLC играет».
ffmpeg не открывает список воспроизведения («Invalid data found»): ссылку на .m3u/.pls/.asx Лира раскрывает сама и
играет первый поток из списка; .m3u8 (HLS) и обычные потоки — как раньше."""
import http.server, os, socketserver, sys, threading
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import radio as R  # noqa: E402

bad = 0
def ok(c, m):
    global bad
    bad += 0 if c else 1
    print(("✅ " if c else "❌ ") + m)

FILES = {"/sw.m3u": "#EXTM3U\n#EXTINF:-1,Советская волна\nhttps://stream.example.org/sovietwave.mp3\n",
         "/r.pls": "[playlist]\nNumberOfEntries=1\nFile1=http://ice.example.org:8000/live\nTitle1=Live\n",
         "/bad.m3u": "#EXTM3U\n"}


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        b = FILES.get(self.path)
        self.send_response(200 if b is not None else 404); self.end_headers()
        if b is not None:
            self.wfile.write(b.encode())
    def log_message(self, *a): pass


srv = socketserver.TCPServer(("127.0.0.1", 0), H); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{port}"
ok(R.playlist_stream(base + "/sw.m3u") == "https://stream.example.org/sovietwave.mp3", "m3u — первый поток из списка")
ok(R.playlist_stream(base + "/r.pls") == "http://ice.example.org:8000/live", "pls — File1")
ok(R.playlist_stream(base + "/bad.m3u") == "", "пустой список — играем как есть (ничего не ломаем)")
ok(R.playlist_stream("https://x.example/live.m3u8") == "" and R.playlist_stream("https://ice5.somafm.com/lush-128-mp3") == "",
   "HLS (.m3u8) и обычный поток — не трогаем")
ok(R.playlist_stream("/home/me/Музыка/list.m3u") == "", "локальный файл — не скачиваем")
src = (ROOT / "core/radio.py").read_text(encoding="utf-8")
ok("real = playlist_stream(station.get(\"url\") or \"\")" in src, "play() раскрывает список перед запуском ffmpeg")
srv.shutdown()
print("ALL OK" if not bad else f"FAILED {bad}")
sys.exit(1 if bad else 0)
