"""«ИИ Академия Лиры» — мультфильм-урок из сцены HTML (владелец 28.10: «мультфильмы по 45–90 с — по суперспособности на
ролик, на YouTube и внутри Лиры»). Один урок — папка lessons/<имя>/: lesson.json (реплики по сценам: кто говорит, титр,
текст для голоса) и film.html (сцена 1920×1080: window.render(T, кадр) рисует момент T по таймлайну TL).

    python3 tools/academy/build.py lessons/01-council            # голос → таймлайн → звук → видео (MP4 1080p)
    python3 tools/academy/build.py lessons/01-council 4 27 53    # только кадры в эти секунды (still-*.png) — проверить вёрстку
    python3 tools/academy/build.py lessons/01-council --voices voices-01-council.zip   # голоса с сервера (voices_server.py)

Голоса — те же, что у персонажей в программе (Piper: Лира — irina, Патрик — denis; core/personas.py). Модели берутся из
выпусков sherpa-onnx на GitHub в ~/.cache/dewiar-academy. Облики — настоящие (ui/assets/entities.js, живые лица), рот
движется по громкости реплики. Время в странице подменено (performance.now, rAF, setTimeout): кадры снимаются по одному,
ровно 30 в секунду, сколько бы ни длился снимок. Музыка — тихий пэд, сам приглушается под голос. Всё — в папке урока: out/.
"""
import json
import math
import struct
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = Path.home() / ".cache/dewiar-academy"
VOICES = {"lira": ("ru_RU-irina-medium", 1.0), "patrik": ("ru_RU-denis-medium", 1.02)}
EQ = {"lira": "highpass=f=80,equalizer=f=4500:t=q:w=1:g=3,equalizer=f=250:t=q:w=1:g=-2",
      "patrik": "highpass=f=60,equalizer=f=180:t=q:w=1:g=3,equalizer=f=5000:t=q:w=1:g=-1"}
URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-{}.tar.bz2"
SR = 44100


def voice_model(name):
    d = CACHE / f"vits-piper-{name}"
    if not (d / f"{name}.onnx").exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        tar = CACHE / f"{name}.tar.bz2"
        print("голос", name, "— скачиваю…", flush=True)
        urllib.request.urlretrieve(URL.format(name), tar)
        subprocess.run(["tar", "-xjf", str(tar), "-C", str(CACHE)], check=True)
        tar.unlink()
    return d / f"{name}.onnx"


def dur(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                                capture_output=True, text=True).stdout)


def speak(les, out):
    """Реплики → wav (кэш по тексту), длительности → таймлайн, громкость по кадрам → рот обликов."""
    L, fps = les["lines"], les["fps"]
    for l in L:
        name, ls = VOICES[l["who"]]
        wav = out / f"{l['id']}.wav"
        key = out / f"{l['id']}.txt"
        if not wav.exists() or not key.exists() or key.read_text(encoding="utf-8") != l["tts"]:
            m = voice_model(name)
            subprocess.run(["piper", "-m", str(m), "-c", f"{m}.json", "-f", str(wav), "--length-scale", str(ls), "--sentence-silence", "0.25"],
                           input=l["tts"].encode(), capture_output=True, check=True)
            key.write_text(l["tts"], encoding="utf-8")
        l["dur"] = round(dur(wav), 3)
    t, prev, scenes = 0.0, None, []
    for l in L:
        if l["scene"] != prev:
            if prev:
                t += les["gap_scene"]
            scenes.append({"id": l["scene"], "start": round(t, 3)})
            t += les["lead"].get(l["scene"], 0.6)
            prev = l["scene"]
        else:
            t += les["gap_in"]
        l["start"] = round(t, 3)
        t += l["dur"]
    total = round(t + les["tail"], 3)
    for i, s in enumerate(scenes):
        s["end"] = scenes[i + 1]["start"] if i + 1 < len(scenes) else total
    n = int(math.ceil(total * fps)) + 1
    env = {w: [0.0] * n for w in VOICES}
    for l in L:
        pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(out / f"{l['id']}.wav"), "-f", "s16le", "-ac", "1", "-ar", "24000", "-"],
                             capture_output=True).stdout
        sm = struct.unpack("<%dh" % (len(pcm) // 2), pcm)
        step, f0 = 24000 // fps, int(round(l["start"] * fps))
        for k in range(len(sm) // step):
            seg = sm[k * step:(k + 1) * step]
            if f0 + k < n:
                env[l["who"]][f0 + k] = round(min(1, math.sqrt(sum(x * x for x in seg) / len(seg)) / 32768 * 5), 3)
    tl = {"fps": fps, "total": total, "scenes": scenes, "lines": L, "env": env}
    (out / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False), encoding="utf-8")
    (out / "timeline.js").write_text("window.TL=" + json.dumps(tl, ensure_ascii=False) + ";", encoding="utf-8")
    print(f"таймлайн: {total:.1f} с, реплик {len(L)}", flush=True)
    return tl


def mix(tl, out, pad_gain=0.28):
    """Голоса по таймлайну (тембр — как в программе) + тихий пэд Am–F–C–G, приглушённый под голос; −16 LUFS."""
    import numpy as np
    total = tl["total"] + 0.5
    N = int(total * SR)
    voice = np.zeros(N, np.float32)
    for l in tl["lines"]:
        pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(out / f"{l['id']}.wav"), "-af", EQ[l["who"]], "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                             capture_output=True).stdout
        a = np.frombuffer(pcm, np.float32)
        i = int(l["start"] * SR)
        voice[i:i + len(a)] += a[:max(0, N - i)]
    t = np.arange(N) / SR
    chords = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [130.81, 196.0, 261.63], [196.0, 246.94, 293.66]]
    pad, L = np.zeros(N, np.float32), 4.0
    for k in range(int(total / L) + 1):
        s0, s1 = int(k * L * SR), min(N, int((k + 1) * L * SR + 1.5 * SR))
        if s0 >= N:
            break
        tt = np.arange(s1 - s0) / SR
        e = np.minimum(1, tt / 1.2) * np.exp(-np.maximum(0, tt - L) / 0.6)
        for f in chords[k % 4]:
            for det in (1.0, 1.003):
                pad[s0:s1] += (np.sin(2 * np.pi * f * det * tt) + 0.25 * np.sin(2 * np.pi * 2 * f * det * tt)) * e * 0.05
        pad[s0:s1] += np.sin(2 * np.pi * chords[k % 4][0] / 2 * tt) * e * 0.06
    pad *= 0.85 + 0.15 * np.sin(2 * np.pi * t / 7)
    pad = np.convolve(pad, np.ones(24) / 24, mode="same").astype(np.float32)
    pad *= np.minimum(1, t / 2.5) * np.minimum(1, (total - t) / 3.0)
    w = int(0.25 * SR)
    duck = 1 - 0.6 * np.clip(np.convolve(np.abs(voice), np.ones(w) / w, mode="same") * 12, 0, 1)
    m = voice + pad * duck * pad_gain
    m /= max(1e-6, np.abs(m).max()) * 1.12
    m.astype(np.float32).tofile(out / "mix.f32")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", str(out / "mix.f32"),
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "48000", "-ac", "2", str(out / "audio.wav")], check=True)
    (out / "mix.f32").unlink()


def import_voices(lesson, out, vz):
    """Голоса из архива (voices_server.py или страница «Академия» в кабинете) -> out/<id>.wav и .txt; новый урок — его реплики."""
    import zipfile
    les0 = json.loads((lesson / "lesson.json").read_text(encoding="utf-8")) if (lesson / "lesson.json").exists() else None
    with zipfile.ZipFile(vz) as z:
        names = set(z.namelist())
        zl = json.loads(z.read("lesson.json")) if "lesson.json" in names else None
        # архив со страницы «Академия» (cloud.php): реплики l01, l02… — по порядку сопоставляем с репликами урока;
        # урока ещё нет (новый) — его реплики берём из архива
        if zl and les0 and len(zl["lines"]) == len(les0["lines"]):
            ren = {a["id"]: b["id"] for a, b in zip(zl["lines"], les0["lines"])}
            for a, b in zip(zl["lines"], les0["lines"]):
                b["tts"] = a["tts"]                       # как произносить — как озвучено
        else:
            ren = {}
            if zl and not les0:
                (lesson / "lesson.json").write_text(json.dumps(zl, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            elif zl:
                sys.exit(f"в архиве {len(zl['lines'])} реплик, а в уроке {len(les0['lines'])} — сверьте текст урока")
        for n in names:
            if n.endswith((".wav", ".txt")) and "/" not in n and ".." not in n:
                stem, ext = n.rsplit(".", 1)
                (out / f"{ren.get(stem, stem)}.{ext}").write_bytes(z.read(n))
    if les0 and ren:
        (lesson / "lesson.json").write_text(json.dumps(les0, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


CLOCK = """(() => { let now = 0; let q = []; let timers = []; let tid = 1;
performance.now = () => now; const D0 = 1793260000000; Date.now = () => D0 + now;
window.requestAnimationFrame = (cb) => { q.push(cb); return q.length; }; window.cancelAnimationFrame = () => {};
window.setTimeout = (cb, ms, ...a) => { const id = tid++; timers.push({ id, at: now + (ms || 0), cb, a }); return id; };
window.clearTimeout = (id) => { timers = timers.filter(t => t.id !== id); };
window.__tick = (ms) => { now += ms; const due = timers.filter(t => t.at <= now); timers = timers.filter(t => t.at > now);
  due.forEach(t => { try { t.cb(...t.a); } catch (e) {} }); const cbs = q.splice(0); cbs.forEach(cb => { try { cb(now); } catch (e) {} }); };
})();"""


def render(lesson, out, tl, stills=None):
    from playwright.sync_api import sync_playwright
    fps = tl["fps"]
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--allow-file-access-from-files"])
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.add_init_script(CLOCK)
        pg.goto((lesson / "film.html").as_uri() + "?tl=" + (out / "timeline.js").as_uri())
        pg.wait_for_function("window.__ready === true")
        pg.evaluate("document.fonts.ready")
        time.sleep(1.5)                                    # портреты и живые лица
        for _ in range(30):
            pg.evaluate("__tick(33.3)")
        if stills:
            for t in stills:
                pg.evaluate(f"render({t}, {int(t * fps)})")
                for _ in range(20):
                    pg.evaluate("__tick(33.3)")
                pg.screenshot(path=str(out / f"still-{t:05.1f}.png"))
        else:
            n = int(tl["total"] * fps)
            ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-",
                                   "-i", str(out / "audio.wav"), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                                   "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out / "lesson.mp4")], stdin=subprocess.PIPE)
            t0 = time.time()
            for f in range(n):
                pg.evaluate(f"render({f / fps}, {f})")
                pg.evaluate(f"__tick({1000 / fps})")
                ff.stdin.write(pg.screenshot(type="jpeg", quality=93))
                if f % 300 == 0:
                    print(f"кадр {f} из {n}, {time.time() - t0:.0f} с", flush=True)
            ff.stdin.close()
            ff.wait()
        b.close()
        if errs:
            print("ошибки на странице:", errs[:3])


if __name__ == "__main__":
    args = sys.argv[1:]
    vz = None
    if "--voices" in args:                                   # голоса с сервера голосов: wav + txt по номеру реплики
        i = args.index("--voices")
        vz = Path(args[i + 1]).resolve()
        del args[i:i + 2]
    sys.argv = [sys.argv[0]] + args
    lesson = (HERE / sys.argv[1]).resolve() if not Path(sys.argv[1]).is_absolute() else Path(sys.argv[1])
    out = lesson / "out"
    out.mkdir(exist_ok=True)
    if vz:
        import_voices(lesson, out, vz)
        # голос Qwen — не Piper: нормализуем в моно 24 кГц, чтобы громкость и рот считались одинаково
        for w in out.glob("*.wav"):
            tmp = w.with_suffix(".tmp.wav")
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(w), "-ac", "1", "-ar", "24000", str(tmp)], check=True)
            tmp.replace(w)
    les = json.loads((lesson / "lesson.json").read_text(encoding="utf-8"))
    tl = speak(les, out)
    if len(sys.argv) > 2:
        render(lesson, out, tl, [float(x) for x in sys.argv[2:]])
    else:
        mix(tl, out)
        render(lesson, out, tl)
        # обложка для «Видеоуроков» (server/dwrapp/academy/<урок>.jpg): заставка до первого титра, 960×540
        at = max(0.6, les["lead"].get(tl["scenes"][0]["id"], 1.4) - 0.25)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.2f}", "-i", str(out / "lesson.mp4"), "-frames:v", "1",
                        "-vf", "scale=960:-2", "-q:v", "4", str(out / "poster.jpg")], check=True)
        print("готово:", out / "lesson.mp4", "и обложка", out / "poster.jpg")
