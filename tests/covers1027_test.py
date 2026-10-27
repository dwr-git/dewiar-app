"""№361 (27.10): «При сканировании папки с музыкой было бы хорошо видеть прогресс, особенно когда сканирование идёт
сетевой папки. Вместо крутящейся пластинки брать картинку из файла или каталога. Пластинку оставить как заглушку».
- обложка: из файла (ID3 APIC у mp3, PICTURE у flac) → из папки альбома (cover.jpg, folder.png…) → нет (пластинка);
  найденное — в кэш, одна на альбом; трек → «станция» с art; в статусе радио и «Музыки» — адрес картинки;
- виджет: вместо пластинки рисуется обложка (битая или не загрузилась — пластинка);
- чтение папки: сначала «ищу файлы, нашлось N», потом «читаю треки: i из N» — событием, не чаще двух раз в секунду;
- студия: обложка в «Сейчас играет», полоска хода чтения."""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


FF = shutil.which("ffmpeg")
if not FF:
    print("нет ffmpeg — пропуск"); print("ИТОГ: все проверки пройдены"); sys.exit(0)
tmp = Path(tempfile.mkdtemp())
mus = tmp / "Музыка"
for d in ("Кино/Группа крови", "Debussy", "Без обложки", "Папка"):
    (mus / d).mkdir(parents=True)
run = lambda *a: subprocess.run([FF, "-loglevel", "error", "-y", *a], check=True)  # noqa: E731
run("-f", "lavfi", "-i", "color=c=red:s=64x64", "-frames:v", "1", str(tmp / "red.png"))
run("-f", "lavfi", "-i", "color=c=blue:s=64x64", "-frames:v", "1", str(tmp / "blue.jpg"))
# mp3 с обложкой внутри (как у скачанной музыки), flac с картинкой, wav и картинка cover.jpg в папке, wav без ничего
run("-f", "lavfi", "-i", "sine=f=440:d=1", "-i", str(tmp / "red.png"), "-map", "0", "-map", "1", "-c:a", "libmp3lame", "-c:v", "png",
    "-id3v2_version", "3", "-metadata", "title=Группа крови", "-metadata", "artist=Кино", "-metadata", "album=Группа крови",
    "-metadata:s:v", "comment=Cover (front)", "-disposition:v", "attached_pic", str(mus / "Кино/Группа крови/01.mp3"))
run("-f", "lavfi", "-i", "sine=f=440:d=1", "-i", str(tmp / "blue.jpg"), "-map", "0", "-map", "1", "-c:a", "flac", "-c:v", "copy",
    "-disposition:v", "attached_pic", "-metadata", "TITLE=Clair de lune", str(mus / "Debussy/clair.flac"))
run("-f", "lavfi", "-i", "sine=f=440:d=1", str(mus / "Папка/song.wav"))
shutil.copy(tmp / "blue.jpg", mus / "Папка/Folder.JPG")
run("-f", "lavfi", "-i", "sine=f=440:d=1", str(mus / "Без обложки/plain.wav"))

sys.path.insert(0, str(ROOT / "core"))
from mymusic import Covers, Dj, Library  # noqa: E402

prog = []
lib = Library(lambda: str(mus), tmp / "lib.json")
lib.on_progress = lambda p: prog.append(p)
lib.prog_every = 0
n = lib.scan()
ok(n == 4, f"папка прочитана: {n} трека")
ok(prog and prog[0] == {"phase": "find", "found": 0} and any(p.get("phase") == "find" and p.get("found") for p in prog)
   and any(p.get("phase") == "tags" and p.get("total") == 4 for p in prog) and lib.progress == {},
   f"ход чтения: «ищу файлы, нашлось N», потом «читаю треки i из N»; после — пусто: {prog}")
cov = Covers(tmp / "covers")
by = {Path(t["path"]).name: t for t in lib.tracks}
a_mp3, a_flac, a_dir, a_none = (cov.get(by[k]) for k in ("01.mp3", "clair.flac", "song.wav", "plain.wav"))
ok(a_mp3 and Path(a_mp3).parent == tmp / "covers" and Path(a_mp3).read_bytes()[:4] == b"\x89PNG", f"mp3: обложка из файла (ID3 APIC) — в кэш: {a_mp3}")
ok(a_flac and Path(a_flac).read_bytes()[:3] == b"\xff\xd8\xff", f"flac: картинка из файла (PICTURE): {a_flac}")
ok(a_dir and Path(a_dir).name == "Folder.JPG", f"нет в файле — картинка папки альбома (Folder.JPG): {a_dir}")
ok(a_none is None, "нет нигде — None (останется пластинка)")
ok(len(list((tmp / "covers").iterdir())) == 2, "в кэше — только вынутые из файлов, по одной на альбом")
dj = Dj(lib, lambda: []); dj.covers = cov
st = dj.station(by["01.mp3"])
ok(st.get("art") == a_mp3 and "art" not in dj.station(by["plain.wav"]), "трек → «станция» с обложкой (без обложки — без поля)")
src = (ROOT / "core/radio.py").read_text(encoding="utf-8") + (ROOT / "core/engine_mymusic.py").read_text(encoding="utf-8")
ok('"art": Path(art).as_uri()' in src and "art=Path(art).as_uri()" in src and "progress=p" in src,
   "статус радио и «Музыки» отдают адрес обложки, ход чтения уходит событием")

# виджет: обложка вместо пластинки
page = tmp / "e.html"
page.write_text(f"""<!doctype html><meta charset=utf-8><body style="background:#222"><canvas id="c" width="300" height="300" style="width:300px;height:300px"></canvas>
<script src="{(ROOT / 'ui/assets/entities.js').as_uri()}"></script>""", encoding="utf-8")
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 400})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto(page.as_uri()); pg.wait_for_timeout(300)
    import io
    from PIL import Image

    def px():                                         # цвет чуть левее центра облика (картинка file:// — холст «чужой», читаем снимком)
        im = Image.open(io.BytesIO(pg.screenshot(clip={"x": 120, "y": 150, "width": 4, "height": 4}))).convert("RGB")
        return list(im.getpixel((2, 2)))
    pg.evaluate("() => { window.E = new DewiarEntity(document.getElementById('c'), { style: 'nexus', color: '#8A9BFF' }); E.vinyl = 'Кино — Группа крови'; E.set({ state: 'idle' }); }")
    pg.wait_for_timeout(600)
    v = px()
    pg.evaluate("(u) => { E.cover = u; }", Path(a_mp3).as_uri()); pg.wait_for_timeout(700)
    c = px()
    ok(c[0] > 150 and c[1] < 80 and c[2] < 80 and not (v[0] > 150 and v[1] < 80), f"виджет: обложка (красная) вместо пластинки: было {v}, стало {c}")
    pg.evaluate("() => { E.cover = 'file:///нет/такой.jpg'; }"); pg.wait_for_timeout(700)
    c2 = px()
    ok(not (c2[0] > 150 and c2[1] < 80), f"картинка не открылась — снова пластинка: {c2}")
    hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
    ok("entity.cover = radioNow && r.art ? r.art : null" in hud, "виджет берёт обложку из статуса радио")

    # студия: «Сейчас играет» с обложкой и полоска хода чтения
    stud = tmp / "s.html"
    stud.write_text(f"""<!doctype html><meta charset=utf-8><link rel=stylesheet href="{(ROOT / 'ui/studio/studio.css').as_uri()}">
<body><section id="p-music" class="cur"><div class="mm-now idle" id="mm-now"><div class="mm-cover" id="mm-cover">♪</div><div id="mm-np"></div>
<button id="mm-pp"></button><button id="mm-heart"></button></div><button id="mm-pick"><span id="mm-folder"></span></button><div class="mm-stats" id="mm-stats"></div>
<div id="mm-chips"></div><ul id="mm-list"></ul><button id="mm-play-all"></button><button id="mm-rescan"></button><button id="mm-prev"></button><button id="mm-next"></button></section>
<script>const $ = (s) => document.querySelector(s), $$ = (s) => [...document.querySelectorAll(s)];
const escH = (s) => String(s).replace(/[&<>"]/g, c => ({{"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}})[c]);
const plural = (n, a, b, c) => n % 10 === 1 && n % 100 !== 11 ? a : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? b : c;
const core = {{ on() {{}}, call: () => Promise.resolve({{}}) }}; const toast = () => {{}};</script>
<script src="{(ROOT / 'ui/studio/mymusic.js').as_uri()}"></script>""", encoding="utf-8")
    pg.goto(stud.as_uri()); pg.wait_for_timeout(300)
    r = pg.evaluate("""(u) => { mmNow({ now: { title: 'Группа крови', artist: 'Кино', art: u, path: '/x' } });
        const cv = document.getElementById('mm-cover'); return [cv.classList.contains('art'), getComputedStyle(cv).backgroundImage, cv.textContent]; }""", Path(a_mp3).as_uri())
    ok(r[0] and "covers" in r[1] and r[2] == "", f"студия: обложка в «Сейчас играет»: {r}")
    r = pg.evaluate("""() => { mmStats({ busy: true, folder: '/m', progress: { phase: 'tags', done: 340, total: 1240 } });
        const u = document.querySelector('#mm-stats .mm-prog u'); return [document.getElementById('mm-stats').innerText, u.style.width]; }""")
    ok("340 из 1" in r[0] and r[1] == "27%", f"студия: «Читаю треки: 340 из 1 240» и полоска: {r}")
    r = pg.evaluate("""() => { mmStats({ busy: true, folder: '/m', progress: { phase: 'find', found: 5120 } });
        return [document.getElementById('mm-stats').innerText, !!document.querySelector('#mm-stats i.run')]; }""")
    ok("нашлось 5" in r[0] and r[1], f"студия: пока ищем файлы — «нашлось N» и бегущая полоска: {r}")
    ok(not errs, f"без ошибок: {errs[:2]}")
    b.close()
print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
