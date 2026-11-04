#!/bin/bash
# Сборка Dewiar для Mac (запускать на macOS — в GitHub Actions это задание mac, .github/workflows/mac.yml):
#   tools/build_mac.sh            → dist/Dewiar-X.Y.Z-mac.dmg        Apple Silicon (M1 и новее)
#   DEWIAR_MAC_ARCH=x86_64 …      → dist/Dewiar-X.Y.Z-mac-intel.dmg  Mac на Intel (собирать на Mac с Intel)
# Внутри образа — Dewiar.app (свой Python из python-build-standalone + библиотеки по requirements-mac.lock + программа)
# и ярлык «Программы». Подпись: есть сертификат Apple в окружении (MAC_CERT_P12_B64, MAC_CERT_PASS; для нотаризации —
# APPLE_ID, APPLE_TEAM_ID, APPLE_APP_PASSWORD) — подписываем и нотаризуем; нет — подпись «для себя» (ad-hoc), и
# при первом запуске Mac попросит «Всё равно открыть» в настройках.
# Перед упаковкой — проверка (packaging/macos/smoke.py): библиотеки грузятся, ядро отвечает; DEWIAR_MAC_UI_SMOKE=1 —
# ещё и сами окна. Не прошла — образа нет.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION=$(sed -n 's/^VERSION = "\(.*\)"/\1/p' "$ROOT/core/version.py")
ARCH=${DEWIAR_MAC_ARCH:-$(uname -m)}
PYREL=${DEWIAR_MAC_PYREL:-20260929}
PYVER=${DEWIAR_MAC_PYVER:-3.12.14}
case "$ARCH" in
  arm64|aarch64) ARCH=arm64; TRIPLE=aarch64-apple-darwin; SUFFIX=""
                 PYSHA=${DEWIAR_MAC_PYSHA:-1bb3e53d231ee2c8881e8daf6426f4dd95bff0dda496af0f3af300357aa998d0} ;;
  x86_64)        TRIPLE=x86_64-apple-darwin; SUFFIX="-intel"
                 PYSHA=${DEWIAR_MAC_PYSHA:-62891cf4a32ed18b6b4174def999184b5186371422c52dd92d941401db0f0e41} ;;
  *) echo "Неизвестная архитектура: $ARCH" >&2; exit 1 ;;
esac
[ "$(uname -s)" = Darwin ] || { echo "Собирать на macOS (нужны clang, codesign, hdiutil)" >&2; exit 1; }
CACHE=${DEWIAR_MAC_CACHE:-$HOME/maccache}
OUTDIR=${1:-$ROOT/dist}
TAR="cpython-${PYVER}+${PYREL}-${TRIPLE}-install_only_stripped.tar.gz"
STAGE=$(mktemp -d); trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$CACHE" "$OUTDIR"
OUTDIR=$(cd "$OUTDIR" && pwd)
sha() { shasum -a 256 "$1" | cut -d' ' -f1; }

if [ ! -f "$CACHE/$TAR" ]; then
  echo "Скачиваю Python для Mac ($TRIPLE)…"
  curl -fL --retry 3 -o "$CACHE/$TAR.part" "https://github.com/astral-sh/python-build-standalone/releases/download/$PYREL/$TAR"
  [ "$(sha "$CACHE/$TAR.part")" = "$PYSHA" ] || { rm -f "$CACHE/$TAR.part"; echo "Архив Python не совпал с контрольной суммой" >&2; exit 1; }
  mv "$CACHE/$TAR.part" "$CACHE/$TAR"
fi
[ "$(sha "$CACHE/$TAR")" = "$PYSHA" ] || { echo "Архив Python в кэше ($CACHE/$TAR) не совпал с контрольной суммой — удалите его" >&2; exit 1; }

APPD="$STAGE/Dewiar.app"
C="$APPD/Contents"
RES="$C/Resources"
mkdir -p "$C/MacOS" "$RES"
tar -xzf "$CACHE/$TAR" -C "$RES"                          # → Resources/python
PY="$RES/python/bin/python3"
"$PY" -c 'import sys; print("Python", sys.version.split()[0], sys.platform)'

echo "Библиотеки (requirements-mac.lock)…"
# у двух крошечных библиотек на PyPI только исходники — колёса лежат готовыми (те же, что для Windows); у zeroconf для
# Intel колеса нет — соберётся из исходников (--prefer-binary: остальное — только колёса)
"$PY" -m pip install --disable-pip-version-check --no-warn-script-location --no-cache-dir --progress-bar off -q \
      --prefer-binary --no-deps --find-links "$ROOT/packaging/windows/wheels" -r "$ROOT/requirements-mac.lock"

echo "Программа…"
mkdir -p "$RES/app"
cp -R "$ROOT/core" "$ROOT/ui" "$ROOT/data" "$ROOT/icons" "$RES/app/"
cp "$ROOT/requirements-mac.lock" "$RES/app/"
find "$APPD" -name __pycache__ -path "*/app/*" -type d -prune -exec rm -rf {} +
SP="$RES/python/lib/python${PYVER%.*}/site-packages"
rm -rf "$SP"/PyObjCTest "$SP"/onnxruntime/transformers "$SP"/onnxruntime/tools "$SP"/onnxruntime/quantization "$SP"/numpy/*/tests "$SP"/numpy/tests 2>/dev/null || true
L="$RES/python/lib/python${PYVER%.*}"
rm -rf "$L/test" "$L/idlelib" "$L/tkinter" "$L/turtledemo" "$L/ensurepip" "$RES/python/lib/"tcl* "$RES/python/lib/"tk* \
       "$RES/python/lib/"itcl* "$RES/python/share" "$RES/python/include" 2>/dev/null || true
rm -f "$RES/app/ui/winshell.py" "$RES/app/ui/selfcheck.py" "$RES/app/ui/stop_dewiar.py"      # только для Windows
# процесс интерфейса называется «Dewiar» (Док, «Мониторинг системы») — копия python3 под этим именем рядом с ним:
# @executable_path/../lib у неё тот же, Python находит себя так же
cp -p "$(cd "$RES/python/bin" && "$PY" -c 'import os,sys; print(os.path.realpath(sys.executable))')" "$RES/python/bin/Dewiar"

echo "Пускач, Info.plist, значок…"
clang -O2 -Wall -fobjc-arc -arch "$ARCH" -mmacosx-version-min=11.0 -framework Cocoa -o "$C/MacOS/Dewiar" "$ROOT/packaging/macos/launcher.m"
sed "s/@VERSION@/$VERSION/g" "$ROOT/packaging/macos/Info.plist" > "$C/Info.plist"
plutil -lint "$C/Info.plist" >/dev/null
printf 'APPL????' > "$C/PkgInfo"
ICONSET="$STAGE/Dewiar.iconset"
mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z $s $s "$ROOT/icons/dewiar-512.png" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  d=$((s * 2)); [ $d -le 512 ] && sips -z $d $d "$ROOT/icons/dewiar-512.png" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns -o "$RES/Dewiar.icns" "$ICONSET"
rm -rf "$ICONSET"

echo "Размер приложения: $(du -sh "$APPD" | cut -f1); крупнее всего:"
du -sk "$SP"/* "$RES/python/lib/python${PYVER%.*}" "$RES/app"/* 2>/dev/null | sort -rn | head -14 | awk '{printf "  %6.1f МБ  %s\n", $1/1024, $2}' | sed "s#$RES/##"

# ---------- подпись ----------
SIGNED=0
if [ -n "${MAC_CERT_P12_B64:-}" ] && [ -n "${MAC_CERT_PASS:-}" ]; then
  echo "Подпись сертификатом Apple…"
  KC="$STAGE/sign.keychain-db"; KCP=$(uuidgen)
  security create-keychain -p "$KCP" "$KC"
  security set-keychain-settings -lut 3600 "$KC"
  security unlock-keychain -p "$KCP" "$KC"
  echo "$MAC_CERT_P12_B64" | base64 -D > "$STAGE/cert.p12"
  security import "$STAGE/cert.p12" -k "$KC" -P "$MAC_CERT_PASS" -T /usr/bin/codesign >/dev/null
  rm -f "$STAGE/cert.p12"
  security set-key-partition-list -S apple-tool:,apple: -s -k "$KCP" "$KC" >/dev/null
  security list-keychains -d user -s "$KC" $(security list-keychains -d user | tr -d '"')
  IDENT=$(security find-identity -v -p codesigning "$KC" | sed -n 's/.*"\(Developer ID Application[^"]*\)".*/\1/p' | head -1)
  [ -n "$IDENT" ] || { echo "В сертификате нет «Developer ID Application»" >&2; exit 1; }
  ENT="$ROOT/packaging/macos/entitlements.plist"
  # изнутри наружу: библиотеки и исполняемые файлы, потом пускач и само приложение
  find "$RES" -type f \( -name "*.so" -o -name "*.dylib" -o -perm -u+x \) -print0 | while IFS= read -r -d '' f; do
    if file "$f" | grep -q "Mach-O"; then
      codesign --force --timestamp --options runtime --entitlements "$ENT" -s "$IDENT" "$f"
    fi
  done
  codesign --force --timestamp --options runtime --entitlements "$ENT" -s "$IDENT" "$C/MacOS/Dewiar"
  codesign --force --timestamp --options runtime --entitlements "$ENT" -s "$IDENT" "$APPD"
  SIGNED=1
else
  echo "Сертификата Apple нет — подпись ad-hoc (при первом запуске: «Всё равно открыть»)"
  codesign --force --deep -s - "$APPD"
fi
codesign --verify --deep --strict "$APPD"

# ---------- проверка ----------
echo "Проверка собранного приложения…"
PYTHONDONTWRITEBYTECODE=1 "$PY" -B "$ROOT/packaging/macos/smoke.py" "$APPD" $([ "${DEWIAR_MAC_UI_SMOKE:-}" = 1 ] && echo --ui)
codesign --verify --deep --strict "$APPD" || { echo "Проверка что-то записала внутрь приложения — подпись сломана" >&2; exit 1; }

# ---------- образ диска ----------
echo "Образ диска…"
DMGROOT="$STAGE/dmg"
mkdir -p "$DMGROOT"
ditto "$APPD" "$DMGROOT/Dewiar.app"
ln -s /Applications "$DMGROOT/Программы"
cat > "$DMGROOT/Если Mac не открывает Dewiar.txt" <<'TXT'
Как установить Dewiar на Mac

1. Перетащите Dewiar в папку «Программы» (ярлык рядом).
2. Откройте Dewiar из «Программ».

Mac пишет «Не удалось проверить разработчика» или «Apple не может проверить Dewiar»?
Это потому, что Dewiar пока не подписан сертификатом Apple. Нажмите «Готово» (или «Отменить»), затем:
Системные настройки → Конфиденциальность и безопасность → внизу «Dewiar заблокирован…» → «Всё равно открыть».
Введите пароль Mac — и больше Mac об этом не спросит.

При первом разговоре Mac спросит доступ к микрофону — разрешите: так Лира услышит своё имя.
Обновления Dewiar ставит сам: «Доступна версия…» → «Обновить».

dewiar.pro/dwrapp/download.php
TXT
OUT="$OUTDIR/Dewiar-$VERSION-mac$SUFFIX.dmg"
rm -f "$OUT"
# Образ. На раннерах GitHub hdiutil капризен (04.11): на Intel «create -srcfolder» виснет намертво, на Apple Silicon
# подключённый диск не отключается («timeout for DiskArbitration»). Поэтому два способа по очереди, каждый шаг — не
# дольше 5 минут (perl alarm): A — «create -srcfolder»; B — пустой диск → подключить без Spotlight → ditto → отключить
# (с повторами) → сжать. Сжатие — LZMA (ULMO, macOS 10.15+). На раннерах GitHub — sudo и без XProtect (на своём Mac
# не нужно).
lim() { perl -e 'alarm shift; exec @ARGV' "$@"; }
SUDO=""; [ -n "${GITHUB_ACTIONS:-}" ] && SUDO="sudo"
calm() {                                                   # раннер GitHub: остановить XProtect и зависший hdiutil
  if [ -n "${GITHUB_ACTIONS:-}" ]; then sudo pkill -9 XProtect >/dev/null 2>&1 || true; sudo pkill -9 hdiutil >/dev/null 2>&1 || true; fi
  return 0
}
# раннер GitHub: Spotlight индексирует каждый подключённый диск и держит его — отключить на время сборки (у себя не нужно)
if [ -n "${GITHUB_ACTIONS:-}" ]; then sudo mdutil -a -i off >/dev/null 2>&1 || true; fi
off() {                                                     # отключить диск: несколько раз, затем силой
  local k
  for k in 1 2 3 4 5; do
    lim 60 $SUDO hdiutil detach "$1" >/dev/null 2>&1 && return 0
    sleep 3; lim 60 $SUDO diskutil unmount force "$1" >/dev/null 2>&1
    lim 60 $SUDO hdiutil detach "$1" -force >/dev/null 2>&1 && return 0
    sleep $((k * 3))
  done
  return 1
}
way_a() {
  rm -f "$OUT"
  lim 300 $SUDO hdiutil create -volname "Dewiar" -srcfolder "$DMGROOT" -ov -format ULMO -fs HFS+ "$OUT" >/dev/null
}
way_b() {
  local raw="$STAGE/raw.dmg" mnt="$STAGE/mnt" mb
  mb=$(( $(du -sm "$DMGROOT" | cut -f1) * 12 / 10 + 40 ))
  rm -f "$raw" "$OUT"; mkdir -p "$mnt"
  lim 300 $SUDO hdiutil create -size "${mb}m" -fs HFS+ -volname "Dewiar" -type UDIF -layout SPUD "$raw" >/dev/null || return 1
  lim 300 $SUDO hdiutil attach -nobrowse -noautoopen -noverify -mountpoint "$mnt" "$raw" >/dev/null || return 1
  $SUDO touch "$mnt/.metadata_never_index"; $SUDO mdutil -i off "$mnt" >/dev/null 2>&1 || true
  $SUDO ditto "$DMGROOT" "$mnt" || { off "$mnt"; return 1; }
  $SUDO rm -rf "$mnt/.fseventsd" "$mnt/.Spotlight-V100" 2>/dev/null; sync
  off "$mnt" || return 1
  lim 600 $SUDO hdiutil convert "$raw" -format ULMO -o "$OUT" >/dev/null || return 1
  rm -f "$raw"
}
ORDER="a b"; if [ "$ARCH" = x86_64 ]; then ORDER="b a"; fi    # на Intel «-srcfolder» виснет — сразу способ B
done_dmg=0
for i in 1 2; do
  for w in $ORDER; do
    if "way_$w"; then done_dmg=1; break; fi
    echo "hdiutil (способ $w): попытка $i не удалась"; calm
  done
  [ "$done_dmg" = 1 ] && break
  sleep $((i * 5))
done
if [ -n "$SUDO" ] && [ -f "$OUT" ]; then sudo chown "$(id -u):$(id -g)" "$OUT"; fi
[ -f "$OUT" ] || { echo "Образ диска не собрался" >&2; exit 1; }
if [ "$SIGNED" = 1 ]; then
  codesign --force --timestamp -s "$IDENT" "$OUT"
  if [ -n "${APPLE_ID:-}" ] && [ -n "${APPLE_TEAM_ID:-}" ] && [ -n "${APPLE_APP_PASSWORD:-}" ]; then
    echo "Нотаризация (Apple проверяет образ, до 15 минут)…"
    xcrun notarytool submit "$OUT" --apple-id "$APPLE_ID" --team-id "$APPLE_TEAM_ID" --password "$APPLE_APP_PASSWORD" --wait --timeout 30m
    xcrun stapler staple "$OUT"
  else
    echo "Нотаризации нет (нужны APPLE_ID, APPLE_TEAM_ID, APPLE_APP_PASSWORD) — Mac всё равно спросит при первом запуске"
  fi
  security delete-keychain "$KC" || true
fi
ls -la "$OUT"
echo "sha256 $(sha "$OUT")"
