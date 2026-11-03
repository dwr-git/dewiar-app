"""Персонажи из настольного Dewiar → personas.js для телефона: та же команда, те же характеры и облики.

Источник — core/personas.py (BUILTIN, VOICE_RULES) и core/gender.py (женские формы глаголов, правило рода для модели),
аватары — data/avatars/<id>.webp|png|jpg (встраиваются как data:-адреса). Печатает JavaScript в stdout:
window.DEWIAR_PERSONAS, DEWIAR_VOICE_RULES, DEWIAR_FEM, DEWIAR_GENDER_RULES — их читает app.js.
Запускают tools/build_apk.sh и тесты tests/android_*: python3 personas_json.py [корень репозитория] > personas.js.
Новое поле персонажа, нужное телефону, добавляй и сюда."""
import base64
import json
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[2])
sys.path.insert(0, str(root / "core"))
import personas as P  # noqa: E402

out = []
for pid, p in P.BUILTIN.items():
    av = ""
    for ext, mime in ((".webp", "image/webp"), (".png", "image/png"), (".jpg", "image/jpeg")):
        f = root / "data" / "avatars" / f"{pid}{ext}"
        if f.exists():
            av = f"data:{mime};base64," + base64.b64encode(f.read_bytes()).decode()
            break
    out.append({"id": pid, "name": p["name"], "gender": p.get("gender", "male"), "style": p.get("style", "nexus"),
                "color": p.get("color", "#8A9BFF"), "role": p.get("role", ""), "tagline": p.get("tagline", ""),
                "main": bool(p.get("main")), "skills": p.get("skills", []), "character": p.get("character", ""),
                "focus": p.get("focus", ""), "aliases": p.get("aliases") or p.get("wake") or [p["name"].lower()],
                "voice_remote": (p.get("voice") or {}).get("remote", ""), "avatar": av, "live": p.get("live", "")})
print("window.DEWIAR_PERSONAS = " + json.dumps(out, ensure_ascii=False) + ";")

# «Готовые персонажи» (идея №56, 03.11): шаблоны (Агент, Джарвис, Эва, Кодер) и специалисты галереи (Фемида, Доктор,
# Профессор…) — те же, что на компьютере в «Персонажи» → «Готовые». Телефон добавляет их одной кнопкой (app.js galPersonas).
# Пакетов знаний и инструментов компьютера здесь нет: специализация — словами в focus; упоминания инструментов, которых у
# телефона нет (search_documents, lab_write, lab_run), убираем вместе со скобками.
PHONE_NO_TOOLS = ("search_documents", "lab_write", "lab_run")
PHONE_FOCUS = {   # роль, которая на телефоне звучит иначе: у телефона нет «компьютера» и лаборатории
    "jarvis": "Твоя роль в команде — телефон и дом: открыть приложение или сайт, включить радио, громкость, фонарик, "
              "умный дом, звонки и сообщения. Делаешь инструментами, а не объясняешь, как сделать.",
}


PHONE_ROLE = {"jarvis": "Телефон и дом"}


def phone_focus(t, pid=""):
    import re
    if pid in PHONE_FOCUS:
        return PHONE_FOCUS[pid]
    t = (t or "").replace("Код — в лабораторию или заметку", "Код — в заметку")
    t = re.sub(r"\s*\([^()]*\b(?:" + "|".join(PHONE_NO_TOOLS) + r")\b[^()]*\)", "", t or "")
    return re.sub(r"\s{2,}", " ", t).strip()


def avatar_of(pid):
    for ext, mime in ((".webp", "image/webp"), (".png", "image/png"), (".jpg", "image/jpeg")):
        f = root / "data" / "avatars" / f"{pid}{ext}"
        if f.exists():
            return f"data:{mime};base64," + base64.b64encode(f.read_bytes()).decode()
    return ""


gal = []
for kind, src in (("template", P.TEMPLATES), ("gallery", P.GALLERY)):
    for pid, p in src.items():
        if p.get("kids") or pid in P.BUILTIN:
            continue
        gal.append({"id": pid, "name": p["name"], "gender": p.get("gender", "male"), "style": p.get("style", "nexus"),
                    "color": p.get("color", "#8A9BFF"), "role": PHONE_ROLE.get(pid, p.get("role", "")), "tagline": p.get("tagline", ""),
                    "skills": p.get("skills", []), "character": p.get("character", ""), "focus": phone_focus(p.get("focus", ""), pid),
                    "aliases": p.get("aliases") or p.get("wake") or [p["name"].lower()], "kind": kind,
                    "voice_remote": (p.get("voice") or {}).get("remote", ""), "avatar": avatar_of(pid), "live": p.get("live", "")})
print("window.DEWIAR_GALLERY = " + json.dumps(gal, ensure_ascii=False) + ";")
# детский режим (телефон, 28.10): Совёнок Уго из галереи — друг ребёнка
k = P.GALLERY["ugo"]
kav = ""
for ext, mime in ((".webp", "image/webp"), (".png", "image/png"), (".jpg", "image/jpeg")):
    f = root / "data" / "avatars" / f"ugo{ext}"
    if f.exists():
        kav = f"data:{mime};base64," + base64.b64encode(f.read_bytes()).decode()
        break
print("window.DEWIAR_KIDS_PERSONA = " + json.dumps({"id": "ugo", "name": k["name"], "gender": k.get("gender", "male"), "style": k.get("style", "aura"),
      "color": k.get("color", "#8A6BD8"), "role": k.get("role", ""), "tagline": k.get("tagline", ""), "skills": k.get("skills", []),
      "character": k.get("character", ""), "focus": k.get("focus", ""), "aliases": k.get("aliases") or k.get("wake") or [],
      "voice_remote": (k.get("voice") or {}).get("remote", ""), "avatar": kav, "kids": True}, ensure_ascii=False) + ";")
print("window.DEWIAR_VOICE_RULES = " + json.dumps(P.VOICE_RULES, ensure_ascii=False) + ";")
print("window.DEWIAR_TALK_RULES = " + json.dumps(P.TALK_RULES, ensure_ascii=False) + ";")
import gender as G  # noqa: E402
print("window.DEWIAR_FEM = " + json.dumps(G._FORMS, ensure_ascii=False) + ";")            # «включил» → «включила»
print("window.DEWIAR_GENDER_RULES = " + json.dumps({g: G.prompt_rule(g) for g in ("female", "male")}, ensure_ascii=False) + ";")
