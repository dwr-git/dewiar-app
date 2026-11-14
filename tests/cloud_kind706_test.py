"""№706 (пакет 14.11): «Раздел «Мозг»: при обновлении слетел адрес сервера для модели» — на снимке у «Dewiar Облака»
протокол Anthropic и «не найдено: проверьте адрес». Облако Dewiar отвечает только по OpenAI-протоколу: профиль облака
приводится к openai при загрузке и при каждом сохранении настроек, а в студии протокол облака не меняется."""
import json, os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import settings as S  # noqa: E402
d = Path(tempfile.mkdtemp())
f = d / "settings.json"
CLOUD = {"name": "Dewiar Облако", "kind": "anthropic", "base_url": "https://dewiar.pro/dwrapp/cloud.php?p=", "api_key": "k",
         "model": "chat", "cloud": True}
OWN = {"name": "ProxyAPI", "kind": "anthropic", "base_url": "https://api.proxyapi.ru", "model": "x"}
f.write_text(json.dumps({"llm": {"active": "dewiar-cloud", "profiles": {"dewiar-cloud": CLOUD, "own": OWN}}}), encoding="utf-8")
st = S.Settings(f)
ok(st.get("llm", "profiles", "dewiar-cloud", "kind") == "openai", "при загрузке облако — снова OpenAI-протокол")
ok(st.get("llm", "profiles", "own", "kind") == "anthropic", "свой Anthropic-сервер не трогаем")
st.update({"llm": {"profiles": {"dewiar-cloud": dict(CLOUD)}}})
ok(json.loads(f.read_text(encoding="utf-8"))["llm"]["profiles"]["dewiar-cloud"]["kind"] == "openai",
   "переключили в студии на Anthropic — сохраняется OpenAI")
js = (ROOT / "ui/studio/brain.js").read_text(encoding="utf-8")
ok('p.cloud && k === "kind"' in js and "inp.disabled = true" in js, "в студии протокол облака не выбирается")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
