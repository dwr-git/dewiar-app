"""Общее для частей llm.py: журнал, «модель на этом компьютере или в своей сети», что сервер уже отверг (инструменты,
поле usage, ключевые слова…) и описывать ли действия текстом."""

import logging
import re
import threading


log = logging.getLogger("dewiar.llm")


_LOCAL_HOST = re.compile(r"^(?:localhost|127\.|0\.0\.0\.0|10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.|\[?::1)|\.local$|\.lan$")


def _local_base(base):
    """Адрес модели — этот компьютер или своя сеть (Ollama, LM Studio, llama.cpp, свой vLLM)."""
    host = (re.match(r"^\w+://\[?([^/:?#\]]+)", str(base or "")) or [None, ""])[1]
    return bool(host) and bool(_LOCAL_HOST.search(host))


# Признаки того, что сервер отклонил сам запрос (формат, роли, функции), а не упал: тогда упрощаем и повторяем.
_REJECT = re.compile(r"\b4(00|22)\b|invalid|unsupported|roles must alternate|cannot parse|bad request|tool|function", re.I)


_no_tools = set()          # серверы, которые отказались принимать инструменты (vLLM без --enable-auto-tool-choice)


_flat = set()              # серверы, которые не принимают историю вызовов (роль tool, tool_calls) — пишем её текстом


_no_kw = set()             # серверы, которые отклоняют запрос с chat_template_kwargs (облако Ollama: «upstream returned HTTP 400»)


_no_usage = set()          # серверы, которые отклонили stream_options (подсчёт токенов в конце потока)


_llamacpp = set()          # серверы llama.cpp (в ответе были timings): им — cache_prompt (0.87, кэш подсказки)


_usage = threading.local()


def prompt_tools_mode(p):
    """Описывать инструменты текстом: так задано в профиле (tools_mode) или сервер уже отказался от поля tools.
    Для Anthropic и явного "native" — никогда."""
    if p.get("kind") == "anthropic" or p.get("tools_mode") == "native":
        return False
    return p.get("tools_mode") == "prompt" or str(p.get("base_url") or "").rstrip("/") in _no_tools
