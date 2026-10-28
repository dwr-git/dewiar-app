"""Ядро собрано из примесей (Engine = AudioMixin + AnswerMixin + … + HealthMixin): у всех общий self. Если одна примесь
кладёт в self.X данные, а другая объявляет метод X, — данные затирают метод (так в 0.38.x кэш «помощников проекта»
self._thanks сломал ответ на «спасибо» и список жалоб). Проверка по исходникам: ни одно self.X = … и getattr(self, "X")
не совпадает с именем метода Engine или примеси, и два метода с одним именем в разных примесях — тоже ошибка."""
import ast, os, re, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


eng = (ROOT / "core/engine.py").read_text(encoding="utf-8")
bases = re.search(r"class Engine\(([^)]*)\)", eng).group(1).replace(" ", "").split(",")
files = [ROOT / "core/engine.py"] + [p for p in (ROOT / "core").glob("*.py") if re.search(r"^class (" + "|".join(bases) + r")\b", p.read_text(encoding="utf-8"), re.M)]
methods, attrs = {}, {}
for f in files:
    tree = ast.parse(f.read_text(encoding="utf-8"))
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef) and (n.name == "Engine" or n.name in bases)]:
        for n in cls.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.setdefault(n.name, []).append(f"{f.name}:{cls.name}")
        for n in ast.walk(cls):
            if isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                    for e in ast.walk(t):
                        if isinstance(e, ast.Attribute) and isinstance(e.value, ast.Name) and e.value.id == "self":
                            attrs.setdefault(e.attr, set()).add(f"{f.name}:{n.lineno}")
            # getattr(self, "X", lambda: …)() — это обращение к методу, не к данным
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") in ("getattr", "setattr") and len(n.args) >= 2 \
                    and not (len(n.args) > 2 and isinstance(n.args[2], ast.Lambda)) \
                    and isinstance(n.args[0], ast.Name) and n.args[0].id == "self" and isinstance(n.args[1], ast.Constant) and isinstance(n.args[1].value, str):
                attrs.setdefault(n.args[1].value, set()).add(f"{f.name}:{n.lineno}")
clash = {a: (sorted(attrs[a]), methods[a]) for a in attrs if a in methods}
ok(not clash, f"данные в self не затирают методы ядра ({len(attrs)} полей, {len(methods)} методов): {clash}")
dup = {m: w for m, w in methods.items() if len({x.split(':')[1] for x in w}) > 1 and m not in ("__init__",)}
ok(not dup, f"метод с одним именем — только в одной примеси: {dup}")
# студия: все ui/studio/*.js — общие глобальные имена; вторая function с тем же именем молча заменяет первую
# (так «Заметки» в «Календаре» звали загрузку «Папки», 0.38.8)
seen = {}
for f in sorted((ROOT / "ui/studio").glob("*.js")):
    for m in re.finditer(r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", f.read_text(encoding="utf-8"), re.M):
        seen.setdefault(m.group(1), []).append(f.name)
twice = {k: v for k, v in seen.items() if len(v) > 1}
ok(not twice, f"студия: глобальные функции не повторяются в разных файлах ({len(seen)}): {twice}")
seen = {}
for f in [*sorted((ROOT / "android/assets/www").glob("*.js")), *(ROOT / "ui/assets" / n for n in ("codes.js", "call.js", "refnet.js", "closecrypto.js", "privacy.js"))]:
    for m in re.finditer(r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", f.read_text(encoding="utf-8"), re.M):
        seen.setdefault(m.group(1), []).append(f.name)
twice = {k: v for k, v in seen.items() if len(v) > 1}
ok(not twice, f"телефон: глобальные функции не повторяются ({len(seen)}): {twice}")
# студия: id в settings.html не повторяются (0.67: «Бот персонажа» взял #pb-name, а он уже был у «Платежей» — поле
# нового платежа стало невидимым)
import collections as _co  # noqa: E402
_ids = _co.Counter(re.findall(r'\sid="([^"]+)"', (ROOT / "ui/settings.html").read_text(encoding="utf-8")))
ok(not {k: v for k, v in _ids.items() if v > 1}, f"студия: id не повторяются ({len(_ids)}): {[k for k, v in _ids.items() if v > 1][:5]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
