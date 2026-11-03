"""№431 (31.10, Windows, тема «Графит», свой размер карточки 280×360): «у окна Лиры видны острые углы — не скрыты».
Форма окна (SetWindowRgn) осталась от прежнего, большего размера: её скруглённые углы — за краями окна, а сторож
формы проверял только «форма есть». Теперь сторож сверяет рамку формы с окном (winshell.shape_fits → fits_box) и
ставит форму заново, если размер не тот."""
import ast, os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


src = (ROOT / "ui/winshell.py").read_text(encoding="utf-8")
fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "fits_box")
ns = {}
exec(compile(ast.Module([fn], []), "fits_box", "exec"), ns)
fits = ns["fits_box"]
ok(fits((0, 0, 281, 361), 280, 360), "форма по размеру окна (у CreateRoundRectRgn рамка на 1 px больше) — в порядке")
ok(not fits((0, 0, 341, 441), 280, 360), "форма от прежнего, большего окна — не подходит: углы за краями, ставим заново")
ok(not fits((0, 0, 201, 301), 280, 360), "форма меньше окна — тоже не подходит")
ok(fits((12, 0, 109, 97), 120, 96), "круглый значок — круг по меньшей стороне по центру — в порядке")
app = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ok("not winshell.shape_fits(h)" in app and "def shape_fits(h):" in src and "GetRgnBox" in src, "сторож формы сверяет размер, а не только наличие")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
