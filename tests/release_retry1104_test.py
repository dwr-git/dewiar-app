"""Выпуск открытой копии (release.yml, задание «Метка и выпуск»), 04.11 — 0.82.0: метка встала, а GitHub на создание
выпуска ответил HTTP 502; повтор задания видел метку и молча пропускал выпуск — файлам (задание files) не к чему было
прикладываться. Теперь: метка есть, выпуска нет — выпуск создаётся; выпуск есть — ничего не делается; 502 — до трёх попыток.

Скрипт шага берётся из самого release.yml и запускается с подменными git и gh."""
import os, shutil, stat, subprocess, sys, tempfile
from pathlib import Path
import yaml
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


y = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8"))
import re
CUR = re.search(r'VERSION = "([^"]+)"', (ROOT / "core/version.py").read_text()).group(1)
run = [s for s in y["jobs"]["tag"]["steps"] if s.get("name") == "Метка и выпуск"][0]["run"]
FAKE_GIT = """#!/bin/bash
echo "git $*" >> "$LOG"
case "$1" in
  rev-parse) v="${4#refs/tags/}"; [ "$v" != "v$CUR" ] || [ -f "$STATE/tag-$v" ] && exit 0 || exit 1 ;;
  tag) touch "$STATE/tag-$3" ;;
esac
exit 0
"""
FAKE_GH = """#!/bin/bash
echo "gh $*" >> "$LOG"
if [ "$1" = api ]; then
  case "$2" in */releases/tags/*) v="${2##*/}"; [ "$v" = v0.28.3 ] && exit 1; [ "$v" != "v$CUR" ] || [ -f "$STATE/rel-$v" ] && exit 0 || exit 1 ;; esac
  echo '[]'; exit 0
fi
if [ "$1 $2" = "release create" ]; then
  n=$(cat "$STATE/fail" 2>/dev/null || echo 0)
  if [ "$n" -gt 0 ]; then echo $((n - 1)) > "$STATE/fail"; echo "HTTP 502: Server Error" >&2; exit 1; fi
  touch "$STATE/rel-$3"; exit 0
fi
exit 0
"""


def go(tag, rel, fail=0):
    tmp = Path(tempfile.mkdtemp()); st = tmp / "st"; st.mkdir(); b = tmp / "bin"; b.mkdir()
    for n, t in (("git", FAKE_GIT), ("gh", FAKE_GH), ("sleep", "#!/bin/bash\nexit 0\n")):
        (b / n).write_text(t); (b / n).chmod(0o755)
    vs = [l.split()[1] for l in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines() if l.startswith("## ") and l[3:4].isdigit()]
    for v in vs:                                    # прошлые версии — с метками и выпусками, как в настоящей копии
        if v != CUR:
            (st / f"tag-v{v}").touch(); (st / f"rel-v{v}").touch()
    (st / "tag-v0.28.3").touch()                    # старая метка без выпуска — выпуск у неё не появляется
    (st / "rel-v0.28.3").unlink(missing_ok=True)
    if tag: (st / f"tag-v{CUR}").touch()
    if rel: (st / f"rel-v{CUR}").touch()
    if fail: (st / "fail").write_text(str(fail))
    (tmp / "core").mkdir(); (tmp / "tools").mkdir()
    shutil.copy(ROOT / "core/version.py", tmp / "core/version.py")
    shutil.copy(ROOT / "CHANGELOG.md", tmp / "CHANGELOG.md")
    shutil.copy(ROOT / "tools/release_refresh.py", tmp / "tools/release_refresh.py")
    r = subprocess.run(["bash", "-e", "-c", run], cwd=tmp, capture_output=True, text=True, timeout=120,
                       env=dict(os.environ, PATH=f"{b}:{os.environ['PATH']}", LOG=str(tmp / "log"), STATE=str(st),
                                GITHUB_SHA="abc123", CUR=CUR, GITHUB_REPOSITORY="dwr-git/dewiar-app", GH_TOKEN="x"))
    log = (tmp / "log").read_text() if (tmp / "log").exists() else ""
    res = (r.returncode, r.stdout + r.stderr, log, (st / f"rel-v{CUR}").exists(), log.count(f"release create v{CUR}"), (st / "rel-v0.28.3").exists())
    shutil.rmtree(tmp, ignore_errors=True)
    return res


rc, out, log, rel, n, old = go(tag=False, rel=False)
ok(rc == 0 and rel and "git tag -a" in log and "--draft" in log, f"новая версия: метка и выпуск-черновик: {out[-200:]!r}")
rc, out, log, rel, n, old = go(tag=True, rel=False)
ok(not old, "старая метка без выпуска — выпуск ей не создаётся (могли убрать нарочно)")
ok(rc == 0 and rel and "git tag -a" not in log and "метка есть, выпуска нет" in out, f"метка есть, выпуска нет (502 в прошлый раз) — выпуск создан: {out[-200:]!r}")
rc, out, log, rel, n, old = go(tag=True, rel=True)
ok(rc == 0 and n == 0 and "уже есть" in out, "метка и выпуск есть — ничего не делает")
rc, out, log, rel, n, old = go(tag=False, rel=False, fail=2)
ok(rc == 0 and rel and n == 3, f"GitHub дважды ответил 502 — третья попытка удалась: попыток {n}")
rc, out, log, rel, n, old = go(tag=False, rel=False, fail=5)
ok(rc != 0 and not rel and n == 3, "502 трижды — задание красное (видно в Actions), а не «зелёное без выпуска»")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
