"""№854 (18.11): «Лира, ответь одним словом: сколько будет 2 + 3? Не используй инструменты и навыки.» — запрет
приняли за просьбу к своему плагину «Навыки Dewiar» (над ответом — его значок). Куски «не используй / не запускай …»
плагин больше не узнают; просьба к нему по имени — как раньше."""
import json, os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


pd = tmp / "cfg/plugins/dwskills"
pd.mkdir(parents=True)
(pd / "plugin.json").write_text(json.dumps({"id": "dwskills", "name": "Навыки Dewiar", "icon": "🧩", "category": "Разное",
                                            "tagline": "Аудит и проверка навыков", "description": "Проверяет навыки Dewiar."},
                                           ensure_ascii=False), encoding="utf-8")
import settings as ST  # noqa: E402
import plugins as PL  # noqa: E402
P = PL.Plugins(ST.Settings(tmp / "s.json"))
P.install("dwskills")
ok((P.match("Проверь мои навыки Dewiar") or {}).get("id") == "dwskills", "просьба к «Навыкам Dewiar» — узнаётся")
ok(P.match("Лира, ответь одним словом: сколько будет 2 + 3? Не используй инструменты и навыки.") is None,
   "«Не используй инструменты и навыки» — не просьба к плагину")
ok(P.match("Ответь на один вопрос. Не запускай навыки и инструменты. Если путь неизвестен, ответь: «Путь неизвестен».") is None,
   "«Не запускай навыки» — тоже")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
