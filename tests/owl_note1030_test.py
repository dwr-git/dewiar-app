"""«Научите меня имени «Совенок, Совёнок»» каждый день (30.10, владелец: «Лира постоянно пишет про Совёнка, большинству это
не нужно — я и вчера его видел, и сегодня»). Совёнок Уго — друг ребёнка: на имя откликается только в детском режиме,
вне его не попадает в список имён и не просит учить его имя. Совет «научите имени» — один раз на тот же набор имён."""
import os, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import personas as P  # noqa: E402
from engine_audio import AudioMixin  # noqa: E402

PS = [{"id": "lira", "name": "Лира", "wake": ["лира"]}, {"id": "patrik", "name": "Патрик", "wake": ["патрик"]},
      dict(P.GALLERY["ugo"], id="ugo"), {"id": "zevs", "name": "Зевс", "wake": ["зевс"]}]
fake = types.SimpleNamespace(all=lambda: PS)
wm = P.Personas.wake_map(fake)
ok("лира" in wm and "совенок" not in wm and "уго" not in wm, f"вне детского режима Совёнка в списке имён нет: {sorted(wm)}")
ok(P.Personas.wake_map(fake, kids=True).get("совенок") == "ugo" and P.Personas.wake_map(fake, only="ugo").get("уго") == "ugo",
   "в детском режиме — откликается")

notes, store = [], {}
S = types.SimpleNamespace(get=lambda *k: (store.get(k[1]) if k[0] == "ui" and len(k) > 1 else ({"asr_wake": True}.get(k[1]) if k[0] == "audio" else None)),
                          update=lambda patch: store.update(patch.get("ui", {})))
eng = types.SimpleNamespace(s=S, personas=types.SimpleNamespace(wake_map=lambda only=None, kids=False: P.Personas.wake_map(fake, only, kids)),
                            voiceprints=types.SimpleNamespace(has=lambda pid: False), note=notes.append, kids=types.SimpleNamespace(on=lambda: False),
                            wake_checker=lambda: None, asr_names=["зевс", "совенок", "совёнок"])
AudioMixin._names_note(eng)
ok(len(notes) == 1 and "Зевс" in notes[0] and "оён" not in notes[0].lower() and "совен" not in notes[0].lower(), f"совет — только про имена взрослых персонажей: {notes}")
AudioMixin._names_note(eng); AudioMixin._names_note(eng)
ok(len(notes) == 1, "тот же совет при следующих запусках — не повторяется")
eng.asr_names = ["зевс", "гермес"]; PS.append({"id": "germes", "name": "Гермес", "wake": ["гермес"]})
AudioMixin._names_note(eng)
ok(len(notes) == 2 and "Гермес" in notes[-1], "появилось новое имя — совет снова, один раз")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
