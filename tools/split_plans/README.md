# Планы раскладки ядра (чистое ядро, docs/CORE_PLAN.md)

По этим планам большие модули разложены на части — слово в слово, без изменения поведения. Их можно перечитать, чтобы
понять, что куда переехало, или взять за образец для следующей раскладки.

| План | Инструмент | Выпуск |
|---|---|---|
| `1.0.8-tools.json` | `python3 tools/split_module.py <план> [--write]` | `core/tools.py` → `tools_*` |
| `1.0.9-engine_commands.py` | разовый скрипт (ветки `command()` → `commands_*`) | `core/engine_commands.py` |
| `1.0.9-engine_answer.json` | `python3 tools/split_class.py <план> [--write]` | `core/engine_answer.py` → `answer_*` |
| `1.0.10-tasks.json` | `python3 tools/split_class.py <план> [--write]` | `core/tasks.py` → `tasks_*` |
| `1.0.13-quality.json` | `python3 tools/split_module.py <план> [--write]` (заголовки разделов — вручную) | `core/quality.py` → `quality_*` |

Повторно запускать не нужно — раскладка уже сделана. Новый план: тот же формат; сначала без `--write` (отчёт), потом
с ним, затем `tests/core_snap_test.py` и `tests/run_fast.py`.
