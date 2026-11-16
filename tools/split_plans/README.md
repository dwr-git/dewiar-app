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
| `1.0.15-llm.json` | `python3 tools/split_module.py <план> [--write]` | `core/llm.py` → `llm_*` (поток и свои серверы — в llm.py: их подменяют проверки) |
| `1.0.16-sites_render.json` | `python3 tools/split_module.py <план> [--write]` | `core/sites_render.py` → `sites_parts`, `_style`, `_art`, `_blocks` |
| `1.0.16-engine_audio.json` | `python3 tools/split_class.py <план> [--write]`, затем `tools/split_headers.py` | `core/engine_audio.py` → `ears_*` |
| `1.0.16-engine_tools.json` | `python3 tools/split_class.py <план> [--write]`, затем `tools/split_headers.py` | `core/engine_tools.py` → `acts_*` |
| `1.0.16-sync.json` | `python3 tools/split_class.py <план> [--write]`, затем `tools/split_headers.py` | `core/sync.py` → `sync_*` (`_version`, `default_device_name` — заранее подняты выше класса) |

Повторно запускать не нужно — раскладка уже сделана. Новый план: тот же формат; сначала без `--write` (отчёт), потом
с ним; заголовки разделов — `python3 tools/split_headers.py <копия прежнего файла> <исходный> <модули…>`; проверки,
читающие исходник текстом, — `python3 tools/srctext_tests.py core/X.py --write` и строка в `tests/srctext.py`; затем
`tests/core_snap_test.py` и `tests/run_fast.py` (отдельные проверки вне набора — с `DEWIAR_SYS_LANG=ru`).
