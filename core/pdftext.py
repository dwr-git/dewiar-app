"""Текст PDF — в отдельном процессе с пределами (четвёртая рецензия выпуска 5, 05.11).

PDF-бомба: 500 страниц ссылаются на один сжатый поток (200 КБ на диске → десятки мегабайт операторов текста на
каждую страницу) — pypdf в процессе ядра съедал память и минуты. Теперь pypdf работает в дочернем Python:
адресное пространство — не больше MEM (RLIMIT_AS; на Windows — Job Object с тем же пределом), время — не больше
timeout, текст — не больше cap знаков всего. Не уложился — PdfTextError («слишком тяжёлый»), ядро живо.

Пути модулей родителя передаются ребёнку (python -I -S: ни переменных окружения, ни site, ни текущей папки), так
что pypdf находится там же, где у самой программы. Пользуются: knowledge.extract, ocr.pdf_texts, quality.file_text,
quality.count_of."""
import json
import logging
import os
import subprocess
import sys

log = logging.getLogger("dewiar.pdftext")
WIN = os.name == "nt"
MEM = 1 << 30                       # адресное пространство разбора — не больше 1 ГБ
TIMEOUT = 25                        # секунд на один PDF
CAP = 32 << 20                      # знаков текста всего (как knowledge.TEXT_MAX)


class PdfTextError(RuntimeError):
    pass


CHILD = r'''
import sys, json
try:
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (int(sys.argv[5]), int(sys.argv[5])))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
except Exception:
    pass
sys.path[:0] = json.loads(sys.stdin.readline())
path, limit, cap, mode = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
try:
    from pypdf import PdfReader
except ImportError:
    sys.stdout.write(json.dumps({"error": "nopypdf"})); sys.exit(0)
r = PdfReader(path)
if mode == "count":
    sys.stdout.write(json.dumps({"count": len(r.pages)})); sys.exit(0)
out, total = [], 0
for pg in r.pages[:limit]:
    try:
        t = pg.extract_text() or ""
    except Exception:
        t = ""
    t = t[:max(0, cap - total)]
    out.append(t)
    total += len(t)
    if total >= cap:
        break
sys.stdout.write(json.dumps({"pages": out}, ensure_ascii=False))
'''


def _run(path, mode, limit=500, cap=CAP, timeout=None, mem=None):
    timeout, mem, job = timeout or TIMEOUT, mem or MEM, None
    try:
        p = subprocess.Popen([sys.executable, "-I", "-S", "-c", CHILD, str(path), str(int(limit)), str(int(cap)), mode, str(int(mem))],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             creationflags=0x08000000 if WIN else 0)
    except OSError as e:
        raise PdfTextError(f"PDF не прочитать: {e}") from e
    if WIN:                                            # Windows: тот же предел памяти — Job Object (как у песочницы задач)
        try:
            import sandbox as S
            job = S._win_job(mem)
            if job:
                S._win_assign(job, p)
        except Exception as e:  # noqa: BLE001
            log.debug("Job Object для PDF: %s", e)
    try:
        out, err = p.communicate(json.dumps([x for x in sys.path if x]).encode() + b"\n", timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        p.communicate()
        raise PdfTextError(f"PDF слишком тяжёлый — не разобрался за {timeout} с") from None
    finally:
        if job:
            try:
                import sandbox as S
                S._win_close(job, kill=True)
            except Exception:  # noqa: BLE001
                pass
    try:
        d = json.loads(out.decode("utf-8", "replace") or "{}")
    except ValueError:
        d = {}
    if d.get("error") == "nopypdf":
        raise PdfTextError("для PDF нужна библиотека pypdf")
    if p.returncode or not d:
        tail = err.decode("utf-8", "replace").strip().splitlines()[-1:] if err else []
        why = "не хватило памяти" if (tail and "MemoryError" in tail[0]) or p.returncode in (-9, 137) else (tail[0][:160] if tail else f"код {p.returncode}")
        raise PdfTextError(f"PDF не прочитался ({why})")
    return d


def pages(path, limit=500, cap=CAP, timeout=None):
    """Текст PDF постранично: [текст страницы, …] — не больше limit страниц и cap знаков всего."""
    return [str(x) for x in _run(path, "text", limit, cap, timeout).get("pages") or []]


def count(path, timeout=None):
    """Сколько страниц в PDF -> число."""
    return int(_run(path, "count", timeout=timeout).get("count") or 0)
