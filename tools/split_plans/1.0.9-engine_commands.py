import re
from pathlib import Path
P = Path("core/engine_commands.py")
src = P.read_text(encoding="utf-8")
lines = src.splitlines(keepends=True)
CH = [  # (модуль, класс, метод, от строки, до строки, описание)
 ("commands_work", "WorkCommands", "_cmd_work", 1207, 1363, "«Мой месяц», «Спросит потом», Радар, идеи, дом по Wi-Fi, «Дозор», режимы «Для старших», команда,\nклиенты, видеоуроки, чат для сайта, «Сайты», CRM, рассылка"),
 ("commands_sync", "SyncCommands", "_cmd_sync", 1364, 1532, "приветствие окна, синхронизация и устройства, мозги других устройств, «Знания», отчёты и жалобы,\nсуфлёр"),
 ("commands_services", "ServicesCommands", "_cmd_services", 1533, 1958, "умный дом, Home Assistant, календари, сейф, резервные копии, почта, курс, справка, объявления и\nновости, дела и напоминания, «Утро», платежи, деньги, Obsidian, серверы, MAX, письма, посты в каналы"),
 ("commands_account", "AccountCommands", "_cmd_account", 1959, 2137, "Telegram, карта памяти, экзамен, память персонажей, «Мои файлы» (mm_), аккаунт dewiar.pro"),
 ("commands_talk", "TalkCommands", "_cmd_talk", 2138, 2342, "разговор и голос: выход, «скажи», снимок экрана в разговор, обучение имени, камеры, игры, кнопка\nмикрофона, «Чат», стоп и тишина, отдых, «отвечать текстом», безопасность, персонажи, галерея"),
 ("commands_brain", "BrainCommands", "_cmd_brain", 2343, 2650, "настройки, «Мозг» (проверка, модели, запасной), облако Dewiar, звонки, «Близкие», приглашения и\nзаявки, Сеть Лиры, сеть и прокси, SSH, устройство, антивирус, папка ассистента (дерево)"),
 ("commands_files", "FilesCommands", "_cmd_files", 2651, 2809, "блокнот, «Ножницы», распознавание текста, заметки, вложения, «Мои файлы», рисунки, «Душа»,\nдневник, экспорт и перенос папки, обновления"),
 ("commands_tasks", "TasksCommands", "_cmd_tasks", 2810, 3104, "фоновые задачи, голоса, знакомство, проба голоса, питание, радио, «Совет ИИ», подкасты, устройства,\nдействия, «Пульт», «Выполнить?», телефон и перенос настроек, советы, навыки, плагины, MCP, состояние"),
]
mods = []
for mod, cls, meth, a, b, doc in CH:
    body = "".join(lines[a - 1:b]).rstrip("\n") + "\n"
    needs_chat = "CHAT_CMDS" in body
    text = (f'"""Команды окон (студия, виджет, телефон): {doc}.\nЧасть разбора CommandsMixin.command (core/engine_commands.py; чистое ядро, 1.0.9 — docs/CORE_PLAN.md): ветки\n'
            f'проверяются по порядку, как раньше в одном методе; команда не своя — NotImplemented, и разбор идёт дальше."""\n'
            "from engine_base import *  # noqa: F401,F403 — общие импорты и помощники движка\n"
            + ("from engine_chat import CHAT_CMDS\n" if needs_chat else "")
            + f"\n\nclass {cls}:\n    def {meth}(self, cmd, a):\n" + body + "        return NotImplemented\n")
    Path(f"core/{mod}.py").write_text(text, encoding="utf-8")
    mods.append((mod, cls, meth))
first, last = CH[0][3], CH[-1][4]
assert lines[last].strip() == 'raise ValueError(f"неизвестная команда {cmd}")', lines[last]
disp = ("        for part in (" + ", ".join(f"self.{m}" for _, _, m in mods) + "):\n"
        "            r = part(cmd, a)                   # ветки по темам — в модулях commands_*: та же очередь проверок, что была\n"
        "            if r is not NotImplemented:\n"
        "                return r\n")
new = lines[:first - 1] + [disp] + lines[last:]
s = "".join(new)
imp = "".join(f"from {m} import {c}\n" for m, c, _ in mods)
s = s.replace("from engine_chat import CHAT_CMDS\n", "from engine_chat import CHAT_CMDS  # noqa: F401\n" + imp, 1)
s = s.replace("class CommandsMixin:", "class CommandsMixin(" + ", ".join(c for _, c, _ in mods) + "):", 1)
P.write_text(s, encoding="utf-8")
print("ok", len(s.splitlines()))
