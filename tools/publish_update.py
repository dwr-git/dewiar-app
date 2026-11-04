#!/usr/bin/env python3
"""Выложить Dewiar на свой сайт: новая версия и все модели — клиенты берут их оттуда сами.

    # первый раз: скачать на сервер все модели (≈0,7 ГБ) и выложить пакет
    python3 publish_update.py dewiar-assistant_X.Y.Z_all.deb /var/www/dewiar.pro/dwrapp --models

    # дальше — только новые версии
    python3 publish_update.py dewiar-assistant_X.Y.Z_all.deb /var/www/dewiar.pro/dwrapp --notes "Что нового"

    # установщик Windows — так же (можно вместе с .deb одной командой)
    python3 publish_update.py Dewiar-Setup-X.Y.Z.exe dewiar-assistant_X.Y.Z_all.deb .

    # приложение для Android — так же (Dewiar-X.Y.Z.apk); --notes к нему не меняет «что нового» на компьютере;
    # рядом можно сборку с «руками» (Dewiar-X.Y.Z-hands.apk → постоянная ссылка …/dwrapp/Dewiar-hands.apk)
    python3 publish_update.py Dewiar-X.Y.Z.apk Dewiar-X.Y.Z-hands.apk .

    # уже находитесь в папке сайта и пакет лежит здесь же — папку можно не указывать
    python3 publish_update.py dewiar-assistant_X.Y.Z_all.deb

    # только обновить модели, без пакета
    python3 publish_update.py /var/www/dewiar.pro/dwrapp --models

Версия .deb берётся из пакета (dpkg-deb, иначе из имени файла), .exe и .apk — из имени файла.

Что получается в папке (сайт отдаёт её как https://dewiar.pro/dwrapp/):
    latest.json                         версия, sha256 пакета, что нового, список моделей;
                                        разделы "windows" и "android" — для установщика и телефона;
                                        "github" — запасной адрес того же файла (только если sha256 на GitHub тот же)
    dewiar-assistant_X.Y.Z_all.deb      пакеты, установщики, .apk (старые не удаляются — можно откатиться)
    Dewiar.apk                          копия последнего .apk — постоянная ссылка для телефона
    models/                             распознавание имён (Vosk), GigaAM, голоса Vosk TTS и Piper

Нужен только Python 3 (стандартная библиотека) и интернет на сервере — модели скачиваются с исходных сайтов
(alphacephei.com, huggingface.co; другие адреса — DEWIAR_SRC_ALPHACEPHEI, DEWIAR_SRC_HF) один раз и дальше
раздаются вашим пользователям с вашего сервера. Модель, которую скачать не удалось, клиенты берут с исходного сайта.
Секретов здесь нет: в папке только публичные файлы. Не кладите в неё .env и ничего служебного.
"""
import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ALPHA = os.environ.get("DEWIAR_SRC_ALPHACEPHEI", "https://alphacephei.com/vosk/models").rstrip("/")
HF = os.environ.get("DEWIAR_SRC_HF", "https://huggingface.co").rstrip("/")

VOSK_SMALL = "vosk-model-small-ru-0.22"
VOSK_SMALL_SHA = "961d5ff98a17f4aa6de69864d0aa71fa5bac682301d2b5d17a3f24c5c99a46d4"
VOSK_TTS_DEFAULT = "vosk-model-tts-ru-0.9-multi"
GIGAAM_REPO = "istupakov/gigaam-v3-onnx"
GIGAAM_NAME = "gigaam-v3-e2e-rnnt"
GIGAAM_PATTERNS = ["config.json", "v3_e2e_rnnt_encoder?int8.onnx", "v3_e2e_rnnt_decoder?int8.onnx",
                   "v3_e2e_rnnt_joint?int8.onnx", "v3_e2e_rnnt_vocab.txt"]
PIPER = ["ru_RU-denis-medium", "ru_RU-dmitri-medium", "ru_RU-ruslan-medium", "ru_RU-irina-medium"]


def say(msg):
    print(msg, flush=True)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


SPEAKER_NAME = "3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx"
SPEAKER_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/" + SPEAKER_NAME
SPEAKER_SHA = "aa3cfc16963a10586a9393f5035d6d6b57e98d358b347f80c2a30bf4f00ceba2"


def fetch(url, dst, expect_sha=None):
    """Скачать url → dst (через .part). Уже есть и сумма та — не качаем заново."""
    dst = Path(dst)
    if dst.exists() and (not expect_sha or sha256(dst) == expect_sha):
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".part")
    say(f"  ↓ {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "dewiar-publish"})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)
    if expect_sha and sha256(tmp) != expect_sha:
        tmp.unlink()
        raise RuntimeError(f"{url}: контрольная сумма не совпала")
    tmp.replace(dst)
    return dst


GH_REPO = os.environ.get("DEWIAR_GH_REPO") or "dwr-git/dewiar-app"
GH_API = (os.environ.get("DWR_GH_API") or "https://api.github.com").rstrip("/")
_gh_rel = {}


def gh_mirror(name, ver, sha):
    """Запасной путь скачивания (0.82.2): тот же файл в выпуске v<ver> открытой копии на GitHub -> (адрес или "", пояснение).
    Только при совпадении sha256 (digest, его даёт GitHub); нет связи, выпуска или файл другой — "" (программы берут только
    с сайта). Как upd_gh_mirror в cloud.php."""
    if ver not in _gh_rel:
        try:
            req = urllib.request.Request(f"{GH_API}/repos/{GH_REPO}/releases/tags/v{ver}",
                                         headers={"User-Agent": "dewiar-publish", "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=8) as r:
                _gh_rel[ver] = json.load(r)
        except Exception as e:  # noqa: BLE001
            _gh_rel[ver] = f"GitHub не ответил ({e})" if "404" not in str(e) else f"на GitHub нет выпуска v{ver}"
    rel = _gh_rel[ver]
    if not isinstance(rel, dict):
        return "", rel
    for a in rel.get("assets") or []:
        if a.get("name") == name:
            url, dg = str(a.get("browser_download_url") or ""), str(a.get("digest") or "")
            if not dg.startswith("sha256:") or not url.startswith("https://"):
                return "", "GitHub не сообщил сумму файла"
            return (url, "тот же файл") if dg[7:].lower() == sha else ("", "на GitHub другой файл")
    return "", f"на GitHub нет {name}"


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "dewiar-publish"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def entry(target, path, **extra):
    return dict({"url": path.relative_to(target).as_posix(), "sha256": sha256(path), "size": path.stat().st_size}, **extra)


def models_vosk_small(target, md):
    z = fetch(f"{ALPHA}/{VOSK_SMALL}.zip", md / f"{VOSK_SMALL}.zip", VOSK_SMALL_SHA)
    return entry(target, z, name=VOSK_SMALL)


def models_vosk_tts(target, md):
    name = VOSK_TTS_DEFAULT
    try:
        ru = [m for m in get_json(f"{ALPHA}/model-list.json")
              if "tts-ru" in m.get("name", "") and str(m.get("obsolete", "false")) != "true"]
        if ru:
            name = sorted(ru, key=lambda m: [int(n) for n in re.findall(r"\d+", m["name"])])[-1]["name"]
    except Exception as e:  # noqa: BLE001
        say(f"  (список моделей alphacephei недоступен: {e} — беру {name})")
    z = fetch(f"{ALPHA}/{name}.zip", md / f"{name}.zip")
    with zipfile.ZipFile(z) as zz:
        if zz.testzip():
            z.unlink()
            raise RuntimeError(f"{name}.zip повреждён — запустите ещё раз")
    return entry(target, z, name=name)


def models_gigaam(target, md):
    info = get_json(f"{HF}/api/models/{GIGAAM_REPO}")
    names = [s["rfilename"] for s in info.get("siblings", [])]
    want = []
    for pat in GIGAAM_PATTERNS:
        hit = [n for n in names if fnmatch.fnmatch(n, pat)]
        if not hit and pat != "config.json":
            raise RuntimeError(f"в {GIGAAM_REPO} нет файла {pat}")
        want += hit
        base = pat.removesuffix(".onnx")                      # большие модели — с внешними данными .onnx.data
        want += [n for n in names if pat.endswith(".onnx") and fnmatch.fnmatch(n, base + ".onnx?data")]
    tmp = md / f".{GIGAAM_NAME}"
    for n in want:
        fetch(f"{HF}/{GIGAAM_REPO}/resolve/main/{n}", tmp / Path(n).name)
    z = md / f"{GIGAAM_NAME}-int8.zip"
    part = z.with_name(z.name + ".part")
    with zipfile.ZipFile(part, "w", zipfile.ZIP_STORED) as zz:
        for n in want:
            zz.write(tmp / Path(n).name, Path(n).name)
    part.replace(z)
    shutil.rmtree(tmp, ignore_errors=True)
    return entry(target, z, name=GIGAAM_NAME)


def models_piper(target, md):
    d = md / "piper"
    files = {}
    for vid in PIPER:
        _, name, quality = vid.split("-", 2)
        for ext in (".onnx.json", ".onnx"):
            p = fetch(f"{HF}/rhasspy/piper-voices/resolve/main/ru/ru_RU/{name}/{quality}/{vid}{ext}", d / f"{vid}{ext}")
            files[p.name] = sha256(p)
    return {"url": d.relative_to(target).as_posix() + "/", "files": files}


def models_speaker(target, md):
    """Голос владельца для суфлёра на очной встрече (core/speaker.py): CAM++ 3D-Speaker, ~28 МБ.
    Имя, адрес и сумма — те же, что MODEL_NAME, MODEL_URL, MODEL_SHA256 в core/speaker.py."""
    p = fetch(SPEAKER_URL, md / "speaker" / SPEAKER_NAME, SPEAKER_SHA)
    return entry(target, p, name=SPEAKER_NAME)


def fill_models(target, data):
    md = target / "models"
    models = dict(data.get("models") or {})
    for key, fn, what in [("vosk_small", models_vosk_small, "распознавание имён Vosk (45 МБ)"),
                          ("gigaam", models_gigaam, "распознавание речи GigaAM (≈250 МБ)"),
                          ("vosk_tts", models_vosk_tts, "голоса Vosk TTS"),
                          ("piper", models_piper, "голоса Piper (4 × 60 МБ)"),
                          ("speaker", models_speaker, "голос владельца для суфлёра (28 МБ)")]:
        say(f"• {what}")
        try:
            models[key] = fn(target, md)
            say("  готово")
        except Exception as e:  # noqa: BLE001
            say(f"  не получилось: {e}. Клиенты будут брать эту модель с исходного сайта.")
    data["models"] = models
    if "vosk_tts" in models:                  # старые клиенты читают зеркало Vosk TTS только строкой из mirrors
        data.setdefault("mirrors", {})["vosk_tts"] = models["vosk_tts"]["url"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", metavar="[пакет.deb] папка", help="пакет (необязательно) и папка сайта")
    ap.add_argument("--notes", default=None, help="что нового (Markdown)")
    ap.add_argument("--models", action="store_true", help="скачать все модели в папку сайта (models/)")
    ap.add_argument("--no-github", action="store_true",
                    help="не давать программам запасной путь на GitHub (по умолчанию — даётся, если там тот же файл)")
    ap.add_argument("--model", help=argparse.SUPPRESS)                   # скрытый: выложить готовый архив Vosk TTS вместо скачивания
    a = ap.parse_args()
    exes = [Path(p) for p in a.paths if p.lower().endswith(".exe")]
    allapk = [Path(p) for p in a.paths if p.lower().endswith(".apk")]
    hands = [p for p in allapk if p.stem.endswith("-hands")]           # Dewiar-X.Y.Z-hands.apk — сборка с «руками»
    apks = [p for p in allapk if p not in hands]
    debs = [Path(p) for p in a.paths if p.endswith(".deb")]
    rest = [Path(p) for p in a.paths if not p.endswith(".deb") and not p.lower().endswith((".exe", ".apk"))]
    if len(debs) > 1 or len(exes) > 1 or len(apks) > 1 or len(hands) > 1 or (hands and not apks) or len(rest) > 1 \
            or not (debs or exes or apks or rest):
        sys.exit("укажите пакет и папку сайта, например:\n"
                 "  python3 publish_update.py dewiar-assistant_0.11.2_all.deb . --models")
    target = rest[0] if rest else (debs or exes or apks)[0].resolve().parent   # папку не указали — та, где лежит пакет
    say(f"Папка сайта: {target.resolve()}")
    target.mkdir(parents=True, exist_ok=True)
    if (target / ".env").exists():
        say("ВНИМАНИЕ: в папке сайта лежит .env — уберите его, эта папка публичная!")
    data = {}
    if (target / "latest.json").exists():
        try:
            data = json.loads((target / "latest.json").read_text(encoding="utf-8"))
        except ValueError:
            data = {}
    data["name"] = "Dewiar"
    if debs:
        deb = debs[0]
        if not deb.is_file():
            sys.exit(f"нет файла {deb}")
        try:
            ver = subprocess.run(["dpkg-deb", "-f", str(deb), "Version"], capture_output=True, text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            m = re.search(r"_(\d+(?:\.\d+)+)_", deb.name)
            ver = m.group(1) if m else ""
        if not ver:
            sys.exit("не понял версию пакета")
        if deb.resolve() != (target / deb.name).resolve():
            shutil.copy2(deb, target / deb.name)
        data.update(version=ver, date=dt.date.today().isoformat(), deb=deb.name, sha256=sha256(deb),
                    size=deb.stat().st_size, notes=a.notes or "")
        data.pop("github", None)                          # прежний запасной адрес — от прежней версии
        gu, why = ("", "выключен") if a.no_github else gh_mirror(deb.name, ver, data["sha256"])
        if gu:
            data["github"] = gu
        say(f"Linux: запасной путь на GitHub — {'есть' if gu else 'нет (' + why + ')'}")
    elif a.notes is not None and not apks:            # заметки к телефону не трогают «что нового» на компьютере
        data["notes"] = a.notes
    if a.model:
        mp = Path(a.model)
        (target / "models").mkdir(exist_ok=True)
        shutil.copy2(mp, target / "models" / mp.name)
        e = entry(target, target / "models" / mp.name, name=mp.name.removesuffix(".zip"))
        data.setdefault("models", {})["vosk_tts"] = e
        data.setdefault("mirrors", {})["vosk_tts"] = e["url"]
    if a.models:
        fill_models(target, data)
    data.setdefault("mirrors", {})
    if exes:                            # установщик Windows: свой раздел, Linux-клиенты его не видят
        exe = exes[0]
        if not exe.is_file():
            sys.exit(f"нет файла {exe}")
        m = re.search(r"(\d+(?:\.\d+)+)", exe.name)
        if not m:
            sys.exit("не понял версию из имени установщика (ожидается Dewiar-Setup-X.Y.Z.exe)")
        onl = exe.with_name(f"Dewiar-Setup-{m.group(1)}-online.exe")
        if not exe.name.endswith("-online.exe"):
            # обновление из программы — компактным: полный (~155 МБ) тихо не вставал (отчёты 19.10) — как upd_publish в cloud.php
            if onl.is_file():
                say(f"Windows: для обновления беру компактный {onl.name} (полный тихо не встаёт)")
                exe = onl
            else:
                say(f"⚠ Windows: {exe.name} — полный установщик; обновление из программы им не встаёт — опубликуйте {onl.name}")
        if exe.resolve() != (target / exe.name).resolve():
            shutil.copy2(exe, target / exe.name)
        data["windows"] = {"version": m.group(1), "date": dt.date.today().isoformat(), "exe": exe.name,
                           "sha256": sha256(exe), "size": exe.stat().st_size, "notes": a.notes or ""}
        gu, why = ("", "выключен") if a.no_github else gh_mirror(exe.name, m.group(1), data["windows"]["sha256"])
        if gu:
            data["windows"]["github"] = gu
        say(f"Windows: запасной путь на GitHub — {'есть' if gu else 'нет (' + why + ')'}")
        say(f"Windows: {exe.name} ({exe.stat().st_size / 1e6:.0f} МБ)")
    if apks:                            # Android: свой раздел — телефон проверяет его сам
        apk = apks[0]
        if not apk.is_file():
            sys.exit(f"нет файла {apk}")
        m = re.search(r"(\d+(?:\.\d+)+)", apk.name)
        if not m:
            sys.exit("не понял версию из имени (ожидается Dewiar-X.Y.Z.apk)")
        if apk.resolve() != (target / apk.name).resolve():
            shutil.copy2(apk, target / apk.name)
        shutil.copy2(target / apk.name, target / "Dewiar.apk")       # постоянная ссылка: …/dwrapp/Dewiar.apk — всегда последняя
        data["android"] = {"version": m.group(1), "date": dt.date.today().isoformat(), "apk": apk.name,
                           "sha256": sha256(apk), "size": apk.stat().st_size, "notes": a.notes or ""}
        say(f"Android: {apk.name} ({apk.stat().st_size / 1e6:.1f} МБ) — ссылка для телефона: …/dwrapp/{apk.name}")
        if hands:
            hk = hands[0]
            if hk.resolve() != (target / hk.name).resolve():
                shutil.copy2(hk, target / hk.name)
            shutil.copy2(target / hk.name, target / "Dewiar-hands.apk")   # постоянная ссылка на версию с «руками»
            data["android"].update(hands_apk=hk.name, hands_sha256=sha256(hk), hands_size=hk.stat().st_size)
            say(f"Android с «руками»: {hk.name} — постоянная ссылка …/dwrapp/Dewiar-hands.apk")
    tmp = target / "latest.json.part"
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(target / "latest.json")
    say(f"Опубликовано → {target}/latest.json" + (f" (Dewiar {data['version']})" if data.get("version") else ""))
    if data.get("models"):
        say("Модели на сайте: " + ", ".join(sorted(data["models"])))
    say("Клиенты увидят обновление при следующей проверке (запуск программы или раз в 6 часов) и скачают его")
    say("в течение 6 часов — каждый в своё время (0.82.2+), чтобы не забить канал сайта;")
    say("или сразу — студия → «О программе» → «Проверить сейчас».")


if __name__ == "__main__":
    main()
