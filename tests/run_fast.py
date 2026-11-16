"""Быстрый набор проверок (чистое ядро, шаг 0 — docs/CORE_PLAN.md): на каждое изменение во время перестройки — те проверки
из tests/run_quick.sh, что не открывают окон браузера, не запускают ядро целиком и не ждут сеть. Параллельно, по числу ядер.

    python3 tests/run_fast.py            — весь быстрый набор
    python3 tests/run_fast.py tools      — только проверки, в имени или тексте которых есть «tools»
Полный набор (tests/run_quick.sh) — по-прежнему перед каждым выпуском."""
import os, re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEAVY = re.compile(r"sync_playwright|core/main\.py|mock_llm|Popen\(|php\"?, \"-S\"|\"php\", \"-S\"|http\.server|socket\.socket\(")


def fast_tests(word=""):
    seen, out = set(), []
    for ln in (ROOT / "tests/run_quick.sh").read_text(encoding="utf-8").splitlines():
        m = re.search(r'\$T/([\w.-]+_test\.py)"', ln)
        if not m or m[1] in seen:
            continue
        seen.add(m[1])
        p = ROOT / "tests" / m[1]
        if not p.is_file():
            continue
        src = p.read_text(encoding="utf-8")
        if HEAVY.search(src) or (word and word not in m[1] and word not in src):
            continue
        out.append(p)
    return out


def run(p):
    """Как one() в run_quick.sh: своя папка и TMPDIR, русский язык системы, «машина» 16 ГБ и 8 ядер; прошла — код 0,
    ни одного ❌ и хотя бы один ✅ (или ALL OK)."""
    import tempfile
    t = time.time()
    with tempfile.TemporaryDirectory() as ws:
        os.makedirs(ws + "/tmp")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1", DEWIAR_SYS_LANG=os.environ.get("DEWIAR_TEST_LANG", "ru"),
                   DEWIAR_PY=sys.executable, DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8", DEWIAR_WORKSPACE_DIR=ws, TMPDIR=ws + "/tmp")
        try:
            r = subprocess.run([sys.executable, str(p)], capture_output=True, text=True, timeout=240, cwd=str(ROOT), env=env)
            out = (r.stdout + r.stderr).replace("\r", "")
            good = r.returncode == 0 and "❌" not in out and ("✅" in out or re.search(r"ALL OK|^OK$", out, re.M))
            return p.name, 0 if good else (r.returncode or 1), time.time() - t, out[-1500:]
        except subprocess.TimeoutExpired:
            return p.name, 124, time.time() - t, "время вышло (240 с)"


if __name__ == "__main__":
    tests = fast_tests(sys.argv[1] if len(sys.argv) > 1 else "")
    t0 = time.time()
    bad = []
    with ThreadPoolExecutor(max_workers=int(os.environ.get("DEWIAR_JOBS") or os.cpu_count() or 2)) as ex:
        for name, rc, sec, out in ex.map(run, tests):
            if rc:
                bad.append(name)
                print(f"❌ {name} ({sec:.0f} с)\n" + "\n".join("   " + x for x in out.strip().splitlines()[-12:]))
    print(f"Быстрый набор: {len(tests)} проверок за {time.time() - t0:.0f} с — " + ("всё прошло" if not bad else f"провалов {len(bad)}: {', '.join(bad)}"))
    sys.exit(1 if bad else 0)
