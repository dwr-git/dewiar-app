#!/bin/bash
# Сборка Dewiar для Android без Gradle и Google Maven: инструменты из пакетов Ubuntu
#   sudo apt install android-sdk android-sdk-platform-23 android-framework-res dalvik-exchange
# Ресурсы линкуются с framework-res из пакетов (атрибуты манифеста до Android 11; новее — fgs_type.py), Java — против android.jar API 23
# (новые API — отражением, см. Compat.java). Подпись — ключом DEWIAR_KEYSTORE (по умолчанию ~/dewiar-keys).
# Использование: android/tools/build_apk.sh [папка-результата]
#                android/tools/build_apk.sh --check   — только проверить сборку (ресурсы, манифест, Java, dex) без ключа
#                                                       подписи и без APK: для проверок (tests/phone_alarm_late087_test.py)
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$HERE/.." && pwd)"
CHECK=""; [ "${1:-}" = "--check" ] && { CHECK=1; shift; }
OUT="${1:-$ROOT/dist}"; [ -n "$CHECK" ] || mkdir -p "$OUT"
BT=/usr/lib/android-sdk/build-tools/debian
FR=/usr/share/android-framework-res/framework-res.apk
AJ=/usr/lib/android-sdk/platforms/android-23/android.jar
KS="${DEWIAR_KEYSTORE:-/home/claude/dewiar-keys/dewiar-release.jks}"
KP="${DEWIAR_KEYPASS:-}"                                  # пароль — только из окружения или файла рядом с ключом (<ключ>.pass), не из кода
[ -z "$KP" ] && [ -f "$KS.pass" ] && KP=$(cat "$KS.pass")
[ -n "$KP" ] || [ -n "$CHECK" ] || { echo "нет пароля ключа подписи: задайте DEWIAR_KEYPASS или положите его в $KS.pass" >&2; exit 1; }
VER=$(sed -n 's/.*static final String VERSION = "\([0-9.]*\)".*/\1/p' "$HERE/src/pro/dewiar/app/BuildInfo.java")
CODE=$(echo "$VER" | awk -F. '{print $1*10000+$2*100+$3}')
B=$(mktemp -d); trap 'rm -rf "$B"' EXIT
mkdir -p "$B/gen" "$B/classes" "$B/assets/www"
# интерфейс: свои файлы + облики персонажей из настольного Dewiar
bash "$HERE/tools/www_assemble.sh" "$B/assets/www"             # интерфейс: тот же набор, что у веб-версии (tools/build_web.sh)

"$BT/aapt2" compile --dir "$HERE/res" -o "$B/res.zip"
# Две сборки из одного кода, одной подписью (ставятся друг поверх друга, данные сохраняются):
#   Dewiar-X.Y.Z.apk        — основная, без службы специальных возможностей: Android и Play Защита ставят её без
#                             блокировок (приложение не из магазина со службой спец. возможностей — «опасное»);
#   Dewiar-X.Y.Z-hands.apk  — с «руками» (Hands.java) для тех, кто хочет управление другими приложениями.
python3 - "$HERE/AndroidManifest.xml" "$B/AndroidManifest-base.xml" <<'PY'
import re, sys
t = open(sys.argv[1], encoding="utf-8").read()
t2 = re.sub(r'\s*<service android:name="\.Hands".*?</service>', "", t, flags=re.S)
assert t2 != t, "в манифесте не нашлась служба .Hands"
open(sys.argv[2], "w", encoding="utf-8").write(t2)
PY
for V in hands base; do
  M="$HERE/AndroidManifest.xml"; [ "$V" = base ] && M="$B/AndroidManifest-base.xml"
  "$BT/aapt2" link -I "$FR" --manifest "$M" --java "$B/gen" -A "$B/assets" -o "$B/base-$V.apk" \
    --min-sdk-version 24 --target-sdk-version 34 --version-code "$CODE" --version-name "$VER" "$B/res.zip"
done
python3 "$HERE/tools/fgs_type.py" "$B/base-hands.apk" "$B/base-base.apk"   # тип службы CloseLive — remoteMessaging (см. сам файл)
cp "$B/base-hands.apk" "$B/base.apk"                    # R.java — из полной сборки (в ней есть все ресурсы)
javac -nowarn -Xlint:-options -encoding UTF-8 -source 8 -target 8 -bootclasspath "$AJ" -d "$B/classes" \
  $(find "$HERE/src" "$B/gen" -name "*.java") 2>&1 | grep -v "JAVA_TOOL_OPTIONS" | tee "$B/javac.log" || true
if grep -q "exception has occurred in the compiler\|error:" "$B/javac.log"; then echo "Java не скомпилировалась (см. выше)"; rm -f "$ROOT"/javac.*.args; exit 1; fi
[ -n "$(find "$B/classes" -name '*.class' | head -1)" ] || { echo "Java не скомпилировалась"; exit 1; }
dalvik-exchange --dex --min-sdk-version=24 --output="$B/classes.dex" "$B/classes" 2>&1 | grep -v JAVA_TOOL_OPTIONS || true
if [ -n "$CHECK" ]; then
  [ -s "$B/classes.dex" ] || { echo "dex не собрался" >&2; exit 1; }
  echo "сборка проходит: ресурсы, манифест, Java и dex — без подписи, APK не создан"; exit 0
fi
for V in base hands; do
  cp "$B/base-$V.apk" "$B/u.apk"; (cd "$B" && zip -q u.apk classes.dex)
  "$BT/zipalign" -f -p 4 "$B/u.apk" "$B/a.apk"
  APK="$OUT/Dewiar-$VER.apk"; [ "$V" = hands ] && APK="$OUT/Dewiar-$VER-hands.apk"
  "$BT/apksigner" sign --ks "$KS" --ks-pass "pass:$KP" --ks-key-alias dewiar --out "$APK" "$B/a.apk" 2>&1 | grep -v JAVA_TOOL_OPTIONS || true
  "$BT/apksigner" verify "$APK" >/dev/null 2>&1 || { echo "подпись $APK не прошла проверку" >&2; exit 1; }   # неподписанный файл в выпуск не уходит
  ls -la "$APK"
done
