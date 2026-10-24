#!/bin/bash
# Собрать интерфейс телефона (папка www) в $1: свои файлы android/assets/www + общие с компьютером (облики, темы,
# шифрование «Близких», звонки, сканер, руководство, «Что я умею», «Что нового», радио). Один набор для APK
# (build_apk.sh) и для веб-версии (tools/build_web.sh) — чтобы они не расходились.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
W="$1"; mkdir -p "$W"
cp -r "$HERE/assets/www/." "$W/"
cp "$ROOT/ui/assets/entities.js" "$W/entities.js"
cp "$ROOT/ui/assets/skins.css" "$ROOT/ui/assets/skins.js" "$W/"     # темы оформления — те же, что у виджета
cp "$ROOT/ui/assets/privacy.js" "$W/"                    # «Ваши данные» — тот же текст, что в студии
cp "$ROOT/ui/assets/closecrypto.js" "$W/"                # «Близкие»: шифрование — то же, что у компьютера (core/closecrypto.py)
cp "$ROOT/ui/assets/qrcode.js" "$W/"                     # QR-код приглашения в «Близкие»
cp "$ROOT/ui/assets/call.js" "$W/"                       # звонки «Близким» (WebRTC) — тот же код, что у компьютера
cp "$ROOT/ui/assets/codes.js" "$ROOT/ui/assets/vendor/zxing.min.js" "$W/"   # печать Dewiar (Aztec) и сканер кодов
cp "$ROOT/ui/assets/refnet.js" "$W/"                     # «Моё созвездие» — приглашённые друзья картиной
cp "$ROOT/ui/assets/speechnorm.js" "$W/"                 # числа словами для голоса сервера — как core/speechnorm.py
cp "$ROOT/ui/assets/rich.js" "$W/"                       # схемы Mermaid и картинки к рассказу — тот же код, что у компьютера
cp -r "$ROOT/ui/assets/arcade" "$W/arcade"               # «Досуг»: игры и полка (arcade/shelf.js) — те же, что у компьютера
mkdir -p "$W/vendor" && cp "$ROOT/ui/assets/vendor/mermaid.min.js" "$ROOT/ui/assets/vendor/mermaid.LICENSE-MIT" "$W/vendor/"
cp "$ROOT/ui/assets/vendor/zxing.LICENSE-APACHE-2.0" "$W/"
cp -r "$ROOT/ui/assets/skins" "$W/skins"
cp -r "$ROOT/ui/assets/live" "$W/live"                # слои живого лица Эвы (entities.js берёт их из live/)
python3 "$HERE/tools/personas_json.py" "$ROOT" > "$W/personas.js"
python3 -c 'import json,sys; print("window.RADIO_LIST = " + json.dumps(json.load(open(sys.argv[1], encoding="utf-8")), ensure_ascii=False) + ";")' \
    "$ROOT/data/radio.json" > "$W/radio.js"         # свой список радиостанций (тот же, что у компьютера)
python3 -c 'import json,sys; print("window.DEWIAR_GUIDE = " + json.dumps(json.load(open(sys.argv[1], encoding="utf-8")), ensure_ascii=False) + ";")' \
    "$ROOT/data/guide.json" > "$W/guide.js"         # руководство — Лира отвечает «как…» по нему (app_help), как на компьютере
python3 -c 'import json,sys; print("window.DEWIAR_TRICKS = " + json.dumps(json.load(open(sys.argv[1], encoding="utf-8")), ensure_ascii=False) + ";")' \
    "$ROOT/data/tricks.json" > "$W/tricks.js"       # «Что я умею» — те же фразы, что в студии
python3 -c 'import json,sys; print("window.DEWIAR_NEWS = " + json.dumps(json.load(open(sys.argv[1], encoding="utf-8")), ensure_ascii=False) + ";")' \
    "$ROOT/data/whatsnew.json" > "$W/whatsnew.js"   # «Что нового» после обновления — тот же текст, что у компьютера
