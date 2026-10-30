#!/bin/bash
# Поднять рабочую среду Dewiar с нуля (30.10: среда перезапустилась — пропали библиотеки, сборка Android и ключ).
# Запуск из корня исходников:  bash tools/setup_env.sh
# Ставит: инструменты сборки Android, PHP, ffmpeg, Python-библиотеки программы и проверок. Ключ подписи сам не появится —
# его даёт владелец (см. docs/RESTART.md → «Если пропала рабочая среда»).
set -u
cd "$(dirname "$0")/.."
SUDO=""; [ "$(id -u)" = 0 ] || SUDO="sudo"
say() { printf '\n== %s\n' "$*"; }

say "Пакеты системы: сборка Android, PHP, ffmpeg"
$SUDO apt-get update -qq || true
DEBIAN_FRONTEND=noninteractive $SUDO apt-get install -y -qq \
  android-sdk android-sdk-platform-23 android-framework-res dalvik-exchange \
  php-cli php-sqlite3 php-curl php-mbstring php-gd ffmpeg zip unzip >/dev/null || echo "часть пакетов не встала — смотрите выше"

say "Python: библиотеки программы"
pip install -q --break-system-packages -r requirements.txt || echo "requirements.txt — не всё встало"
for p in $(grep -v '^#' requirements-extra.txt | tr ' ' '\n' | grep -v '^$'); do
  pip install -q --break-system-packages "$p" >/dev/null 2>&1 || echo "необязательное не встало: $p"
done
pip install -q --break-system-packages playwright >/dev/null 2>&1 || true
python3 -c "import playwright" 2>/dev/null && { python3 -m playwright install chromium >/dev/null 2>&1 || echo "Chromium для проверок — поставьте: python3 -m playwright install chromium"; }

say "Ключ подписи Android"
K=/home/claude/dewiar-keys/dewiar-release.jks
if [ -f "$K" ] && [ -f "$K.pass" ]; then
  chmod 600 "$K" "$K.pass"
  keytool -list -keystore "$K" -storepass:file "$K.pass" >/dev/null 2>&1 && echo "ключ на месте, пароль подходит" || echo "ключ есть, но пароль не подходит"
else
  echo "ключа нет: положите dewiar-release.jks и файл с паролем dewiar-release.jks.pass в /home/claude/dewiar-keys/ (права 600)"
fi

say "Проверка"
for c in php ffmpeg keytool /usr/lib/android-sdk/build-tools/debian/apksigner dalvik-exchange; do
  command -v "$c" >/dev/null 2>&1 || [ -x "$c" ] && echo "есть: $c" || echo "НЕТ: $c"
done
python3 -c "import httpx, numpy, vosk; print('Python-библиотеки: есть')" 2>/dev/null || echo "Python-библиотеки: НЕТ"
echo; echo "Дальше: bash tests/run_quick.sh — всё ли цело."
