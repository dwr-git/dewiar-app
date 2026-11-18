"""№878 (18.11): «Лира не может открыть Photoshop или Корел; ворд — со второй попытки и если сказать „Майкрософт ворд“».
В журнале: open_app «CorelDRAW» → «Corel CAPTURE 2020 (64-Bit)» и «[WinError 2] Не удается найти указанный файл»: (1)
кусок «Corel» (папка ярлыка) весил столько же, сколько настоящее название; (2) в Windows ярлык запускался по имени, а не
по пути. Теперь название, которое содержит запрос, выше куска; годы и «(64-Bit)» не мешают; русские имена программ —
фотошоп, корел, ворд, эксель, пауэрпоинт…; в Windows — путь к ярлыку."""
import json, os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import tools_pc as T  # noqa: E402
import tools_base as B  # noqa: E402

M = r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"
win = [{"name": n, "ru": "", "keywords": kw, "id": n, "path": fr"{M}\{kw + chr(92) if kw else ''}{n}.lnk"} for n, kw in [
    ("Corel CAPTURE 2020 (64-Bit)", "CorelDRAW Graphics Suite 2020 (64-Bit)"), ("CorelDRAW 2020 (64-Bit)", "CorelDRAW Graphics Suite 2020 (64-Bit)"),
    ("Corel PHOTO-PAINT 2020 (64-Bit)", "CorelDRAW Graphics Suite 2020 (64-Bit)"), ("Adobe Photoshop 2024", ""), ("Adobe Bridge 2024", ""),
    ("Word", ""), ("Excel", ""), ("PowerPoint", ""), ("Outlook (classic)", ""), ("Google Chrome", "")]]
for q, exp in [("CorelDRAW", "CorelDRAW 2020 (64-Bit)"), ("корел", "CorelDRAW 2020 (64-Bit)"), ("корел дро", "CorelDRAW 2020 (64-Bit)"),
               ("Coral Draw", "CorelDRAW 2020 (64-Bit)"), ("фотошоп", "Adobe Photoshop 2024"), ("Photoshop", "Adobe Photoshop 2024"),
               ("ворд", "Word"), ("майкрософт ворд", "Word"), ("эксель", "Excel"), ("пауэр поинт", "PowerPoint"),
               ("программу ворд", "Word"), ("аутлук", "Outlook (classic)"), ("хром", "Google Chrome"), ("Corel Capture", "Corel CAPTURE 2020 (64-Bit)")]:
    a = T.find_app(q, win)
    ok((a or {}).get("name") == exp, f"«{q}» → {(a or {}).get('name')}")
# в Windows — запуск по пути ярлыка
log = Path(tempfile.mkdtemp()) / "launch.jsonl"
B.DRY, B.WIN = str(log), True
T.desktop_apps = lambda: win
T.t_open_app({"name": "CorelDRAW"}, {})
cmd = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
ok(cmd[-1].endswith(r"\CorelDRAW 2020 (64-Bit).lnk"), f"Windows: запуск по пути ярлыка, а не по имени: {cmd[-1][-40:]}")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
