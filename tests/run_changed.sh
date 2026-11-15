#!/bin/bash
# Проверки, задетые изменением (15.11, владелец: «выпуски стали очень долгими»): выбирает их tools/test_impact.py по карте
# tests/impact.json (какая проверка какие файлы читает) — плюс «дымовые». Когда выбору доверять нельзя (изменился сам
# прогон, файл кода, который не читает ни одна проверка, нет карты), — весь набор.
#   bash tests/run_changed.sh [с чего — метка или коммит; по умолчанию последняя метка v*]
# Перед выпуском — это; полный набор (bash tests/run_quick.sh) — после выпуска, в фоне, и с записью для новой карты:
#   DEWIAR_TRACE_DIR=<папка> DEWIAR_JOBS=2 bash tests/run_quick.sh && python3 tools/test_impact.py build <папка>
T="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$T")"
LIST=$(mktemp); trap 'rm -f "$LIST"' EXIT
python3 "$ROOT/tools/test_impact.py" pick "$1" > "$LIST" || exit 2
if grep -qx ALL "$LIST"; then
  echo "== Весь набор (почему — выше)"; exec bash "$T/run_quick.sh"
fi
echo "== Проверок, задетых изменением: $(grep -c . "$LIST")"
DEWIAR_ONLY="$LIST" bash "$T/run_quick.sh"
