"""0.96 (владелец 13.11: «приложение на 100 % английским»; «ГигаАМ — только для русского языка»). Программа по-английски:
точное распознавание на компьютере — Parakeet TDT v3 (та же onnx-asr, английский и ещё 24 европейских языка), а не
GigaAM; облачное распознавание получает language=en (сервер отдаст английской модели). По-русски — всё как было."""
import os, sys, tempfile, types
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


import stt as ST  # noqa: E402
import engine_audio as EA  # noqa: E402
cls = next(c for c in vars(EA).values() if isinstance(c, type) and hasattr(c, "_asr_name"))


class S:
    def __init__(self, lang): self.d = {"ui": {"lang": lang}, "stt": {"gigaam_model": "gigaam-v3-e2e-rnnt"}}
    def get(self, a, k=None): v = self.d.get(a); return v if k is None else (v or {}).get(k)


for lang, want in (("en", ST.EN_ASR), ("ru", "gigaam-v3-e2e-rnnt")):
    e = types.SimpleNamespace(s=S(lang))
    e._ui_en = types.MethodType(cls._ui_en, e)
    ok(cls._asr_name(e) == want, f"программа «{lang}» — распознаёт {want}")

g = ST.GigaAMSTT(ST.EN_ASR)
ok(g.title == "Parakeet" and g.mb >= 600 and g.hub_key == "parakeet-tdt-0.6b-v3" and g.name.startswith("Parakeet"), f"Parakeet: {g.name}, ~{g.mb} МБ")
ok(ST.GigaAMSTT().title == "GigaAM" and ST.GigaAMSTT().hub_key == "gigaam", "GigaAM — как был")
# кэш Hugging Face: полный снимок Parakeet узнаётся, оборванный (без кодера) — нет
hub = ST.MODELS_DIR / "hf" / "hub" / "models--istupakov--parakeet-tdt-0.6b-v3-onnx" / "snapshots" / "abc"
hub.mkdir(parents=True, exist_ok=True)
(hub / "decoder_joint-model.int8.onnx").write_bytes(b"0" * 2048)
(hub / "vocab.txt").write_text("a\n")
ok(not g.cached(), "без кодера — не скачано (докачаем)")
(hub / "encoder-model.int8.onnx").write_bytes(b"0" * 2048)
ok(g.cached(), "кодер, декодер и словарь — скачано")

src = (ROOT / "core/engine_audio.py").read_text(encoding="utf-8")
ok('rc["language"] = "en"' in src and "self._ui_en()" in src, "облачное распознавание — language=en, когда программа по-английски")
ok("Parakeet v3 — точное распознавание речи" in src, "в «Моделях» студии — Parakeet, а не GigaAM")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
