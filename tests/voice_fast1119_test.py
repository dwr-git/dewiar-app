"""«Голос без пауз» (идея №5, 117 голосов; пакет 19.11: до первого звука 7,9 с, у облака Dewiar 8,8 с; подсказка ~19,5 тыс.
ток., из них описания действий 9,7 тыс.). 1.0.38: фоновые задачи, музыка и плеер, картинки/ссылки/страницы, идеи и «Пишу» —
из ядра в группы по словам: в простом разговоре описаний действий меньше почти вдвое, а просьбы экзамена получают свои действия."""
import json, os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"))
sys.path.insert(0, str(ROOT / "core"))
import modules  # noqa: E402
import tools  # noqa: E402
from settings import Settings  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


s = Settings(tmp / "s.json")
size = lambda sp: sum(len(json.dumps(x, ensure_ascii=False)) for x in sp)  # noqa: E731
names = lambda sp: {x["name"] for x in sp}  # noqa: E731
chat = tools.Toolbox(s, None).specs("Привет, как дела?")
ok(size(chat) <= 12500, f"простой разговор — описаний действий до 12,5 тыс. знаков (было ~19 тыс.): {size(chat)}")
ok(not names(chat) & {"start_task", "play_radio", "yandex_music", "media_control", "show_page", "show_images", "save_link", "suggest_idea", "writing_today"},
   "в простом разговоре — без задач, музыки, плеера, страниц, идей")
ok({"set_reminder", "web_search", "weather", "calc", "save_note", "find_notes", "app_help", "more_tools"} <= names(chat), "главное — на месте")
mt = next(x for x in chat if x["name"] == "more_tools")["description"]
ok(all(g in mt for g in ("tasks — Фоновые задачи", "music — Музыка и радио", "web — Картинки, ссылки, страницы", "ideas —", "player —")),
   "more_tools называет новые группы — модель может их попросить")
EXAM = {"Расскажи в двух словах про руническую вязь и покажи, как она выглядит.": {"show_images"},
        "включи смешное видео на ютубе": {"play_youtube"},
        "Удали задачу «Исследование», она мне больше не нужна.": {"remove_task"},
        "Ту задачу про подарки я удалил, она зависла. Запусти её заново: три идеи подарка маме на день рождения, итог — в заметку.": {"start_task"},
        "Сохрани это видео, посмотрю потом: https://youtu.be/dQw4w9WgXcQ": {"save_link"},
        "Найди у меня в заметках рецепты и покажи их в браузере красиво оформленными.": {"show_page"},
        "Найди мою заметку «Тёмное дело» и выведи её в браузере целиком.": {"show_page"},
        "Сколько я написал сегодня?": {"writing_today"},
        "Проанализируй мой компьютер, папки, диски, покажи, что есть, и предложи структуру.": {"start_task"},
        "Что сейчас играет?": {"media_control", "play_music"}, "стоп": {"media_control"}, "Поставь Кино": {"play_music"},
        "Хочу предложить идею: тёмная тема": {"suggest_idea"}, "Как там моя задача?": {"task_status"}}
for q, need in EXAM.items():
    got = names(tools.Toolbox(s, None).specs(q))
    ok(need <= got, f"«{q[:48]}» — есть {sorted(need)}")
tb = tools.Toolbox(s, None)
tb.specs("включи радио")
again = names(tb.specs("а теперь расскажи анекдот"))
ok("play_radio" in again, "предложенная группа остаётся (6 часов) — начало запроса не меняется, кэш живёт")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
