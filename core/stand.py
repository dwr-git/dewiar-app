#!/usr/bin/env python3
"""Стенд гипотез (план «Качество», шаг 2; владелец 21.11: «отдельные группы экзаменов с переключателями, чтобы не всё время
гонять экзамены по всему, а проверять отдельные улучшения»).

Берёт группы сценариев экзамена (core/exam.py, data/exam/scenarios.json), гоняет их «до» (как сейчас) и «после» (с
переключателями гипотезы) по N раз на выбранном мозге и печатает таблицу «было → стало»:
  - по сценарию: сдано k из N до и после — разброс и есть непредсказуемость («то сдаёт, то нет»);
  - по группе: доля сданных, среднее время;
  - почему: из рентгена ходов (core/xray.py) — путь (команда или модель), вес подсказки, вызванные действия, проверки.

    python3 tools/stand.py --key dw-… --group "Напоминания,Честность" --set llm.scene=true --repeat 3
    (кабинет → «Экзамен» → «Стенд гипотез»: группы, переключатель, повторы — исполнитель зовёт core/exam.py --group/--set/--repeat)
    python3 tools/stand.py --llm '{"kind":"openai","base_url":"http://127.0.0.1:1234/v1","model":"qwen3-4b"}' \\
        --group Память --repeat 5                    # без --set: только «как сейчас» — разброс одной модели
    python3 tools/stand.py --list                    # какие группы есть и сколько в них сценариев

--set ключ=значение (можно несколько): настройки ядра «после» (true/false/числа — как JSON, иначе строкой).
--base ключ=значение: настройки «до» (по умолчанию — как у людей). Отчёт — stand-ГГГГММДД-ЧЧММ.md и .json в --out."""
import argparse
import asyncio
import datetime as dt
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))
SCEN = ROOT / "data" / "exam" / "scenarios.json"


def parse_sets(items):
    out = {}
    for it in items or []:
        k, _, v = str(it).partition("=")
        if not k or not _:
            raise SystemExit(f"--set/--base: нужно ключ=значение, а не «{it}»")
        try:
            out[k.strip()] = json.loads(v)
        except ValueError:
            out[k.strip()] = v
    return out


def groups_list():
    data = json.loads(SCEN.read_text(encoding="utf-8"))
    by = {}
    for sc in data["scenarios"]:
        if not sc.get("big"):
            by.setdefault(sc["group"], []).append(sc["id"])
    return by


def aggregate(runs):
    """runs: {"A": [rep, …], "B": [rep, …]} -> по сценариям и группам."""
    sc, gr = {}, {}
    for side, reps in runs.items():
        for rep in reps:
            for r in rep["scenarios"]:
                if r.get("skipped"):
                    continue
                e = sc.setdefault(r["id"], {"group": r["group"], "title": r["title"], "A": [], "B": [], "why": {"A": [], "B": []}})
                e[side].append({"ok": bool(r["passed"]), "t": r.get("time_s"), "score": r.get("score")})
                e["why"][side].append(r.get("xray") or [])
                g = gr.setdefault(r["group"], {"A": [0, 0, []], "B": [0, 0, []]})
                g[side][0] += bool(r["passed"]); g[side][1] += 1
                if r.get("time_s") is not None:
                    g[side][2].append(r["time_s"])
    return sc, gr


def why_line(xs):
    """Рентген прогонов сценария одной строкой: путь, средний вес подсказки, действия, проверки."""
    turns = [t for x in xs for t in x]
    if not turns:
        return ""
    routes = {}
    for t in turns:
        routes[t.get("route") or "?"] = routes.get(t.get("route") or "?", 0) + 1
    toks = [t["tokens"] for t in turns if t.get("tokens")]
    acts = {}
    for t in turns:
        for name, ok in t.get("acts") or []:
            a = acts.setdefault(name, [0, 0]); a[0] += ok; a[1] += 1
    checks = sum(t.get("checks") or 0 for t in turns)
    return (", ".join(f"{k} {v}" for k, v in routes.items())
            + (f"; подсказка ≈{round(statistics.mean(toks))} ток." if toks else "")
            + (f"; действия: " + ", ".join(f"{k} {v[0]}/{v[1]}" for k, v in acts.items()) if acts else "; без действий")
            + (f"; проверки поправили {checks}" if checks else ""))


def markdown(meta, sc, gr):
    ab = bool(meta["B"])
    L = [f"# Стенд гипотез — {meta['started'][:16].replace('T', ' ')}", "",
         f"Модель: {meta['model']}. Повторов: {meta['repeat']}. Группы: {', '.join(meta['groups'])}.",
         f"До: {json.dumps(meta['A'], ensure_ascii=False) if meta['A'] else 'как у людей'}."
         + (f" После: {json.dumps(meta['B'], ensure_ascii=False)}." if ab else ""), ""]
    L += ["## Группы", "", "| группа | " + ("до | после | разница |" if ab else "сдано | время, с |"),
          "|---|" + ("---|---|---|" if ab else "---|---|")]
    for g, v in sorted(gr.items()):
        pa = v["A"][0] / v["A"][1] if v["A"][1] else 0
        if ab:
            pb = v["B"][0] / v["B"][1] if v["B"][1] else 0
            L.append(f"| {g} | {v['A'][0]}/{v['A'][1]} ({pa:.0%}) | {v['B'][0]}/{v['B'][1]} ({pb:.0%}) | {(pb - pa) * 100:+.0f} п. |")
        else:
            t = round(statistics.mean(v["A"][2]), 1) if v["A"][2] else "—"
            L.append(f"| {g} | {v['A'][0]}/{v['A'][1]} ({pa:.0%}) | {t} |")
    unstable = [k for k, e in sc.items() if 0 < sum(x["ok"] for x in e["A"]) < len(e["A"])
                or (ab and 0 < sum(x["ok"] for x in e["B"]) < len(e["B"]))]
    L += ["", f"Непредсказуемых сценариев (то сдаёт, то нет): {len(unstable)} из {len(sc)}.", "", "## Сценарии", ""]
    for k, e in sorted(sc.items(), key=lambda kv: (kv[1]["group"], kv[0])):
        a = f"{sum(x['ok'] for x in e['A'])}/{len(e['A'])}"
        b = f" → {sum(x['ok'] for x in e['B'])}/{len(e['B'])}" if ab else ""
        mark = " ⚠ разброс" if k in unstable else ""
        L.append(f"- **{k}** · {e['group']} · {e['title']}: {a}{b}{mark}")
        wa = why_line(e["why"]["A"])
        if wa:
            L.append(f"  - до: {wa}")
        if ab:
            wb = why_line(e["why"]["B"])
            if wb:
                L.append(f"  - после: {wb}")
    return "\n".join(L) + "\n"


async def run_stand(prof, jp, groups, A, B, repeat, log=print):
    """До (A) и после (B) по очереди, repeat раз -> отчёт в виде отчёта экзамена (кабинет его принимает как есть):
    сценарии и итог — последнего прогона «после» (или «до»), а таблица стенда — в stand и stand_md."""
    from exam import run_exam, summary
    started = dt.datetime.now()
    runs = {"A": [], "B": []}
    for i in range(repeat):                         # до и после — по очереди: время суток и нагрузка сервера поровну
        for side, ov in (("A", A), ("B", B)) if B else (("A", A),):
            log(f"=== Прогон {i + 1}/{repeat} · {'после' if side == 'B' else 'до'} ===")
            rep = await run_exam(prof, jp, None, False, log=log, groups=groups, overrides=ov,
                                 label=("после" if side == "B" else "до"))
            runs[side].append(rep)
    sc, gr = aggregate(runs)
    meta = {"started": started.isoformat(timespec="seconds"), "model": prof.get("title") or prof.get("model"), "repeat": repeat,
            "groups": list(groups), "A": A, "B": B}
    last = (runs["B"] or runs["A"])[-1]
    allr = [r for side in ("A", "B") for rep in runs[side] for r in rep["scenarios"]]
    md = markdown(meta, sc, gr)
    return dict(last, started=meta["started"], duration_s=round((dt.datetime.now() - started).total_seconds()),
                model=f"{meta['model']} · стенд ×{repeat}" + (" · " + ", ".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in B.items()) if B else ""),
                summary=summary(allr), stand={"meta": meta, "scenarios": sc, "groups": gr}, stand_md=md)


def main():
    ap = argparse.ArgumentParser(description="Стенд гипотез Dewiar (см. начало файла)")
    ap.add_argument("--key", help="ключ Dewiar (dw-…): модель облака Dewiar")
    ap.add_argument("--url", default="", help="адрес облака (по умолчанию dewiar.pro)")
    ap.add_argument("--model", default="", help="модель облака")
    ap.add_argument("--llm", help="профиль модели JSON: {kind, base_url, model, api_key}")
    ap.add_argument("--judge", help="профиль судьи JSON (по умолчанию — та же модель)")
    ap.add_argument("--group", default="", help="группы сценариев через запятую (см. --list)")
    ap.add_argument("--set", action="append", help="переключатель «после»: ключ=значение (можно несколько)")
    ap.add_argument("--base", action="append", help="настройка «до»: ключ=значение")
    ap.add_argument("--repeat", type=int, default=3, help="сколько раз гонять каждую сторону (разброс)")
    ap.add_argument("--out", default=".", help="куда положить отчёт")
    ap.add_argument("--list", action="store_true", help="какие группы есть")
    a = ap.parse_args()
    if a.list:
        for g, ids in sorted(groups_list().items()):
            print(f"{g} — {len(ids)}: {', '.join(ids)}")
        return
    if not a.group:
        ap.error("нужно --group (см. --list)")
    if a.llm:
        prof = json.loads(a.llm)
    elif a.key:
        from cloud import api_base, fetch, norm_key
        key = norm_key(a.key)
        models = (fetch(a.url, key, "/models").get("data") or [])
        m = next((x for x in models if x["id"] == a.model), models[0] if models else {"id": a.model or "chat"})
        prof = {"name": "Dewiar Облако", "kind": "openai", "base_url": api_base(a.url), "api_key": key, "model": m["id"],
                "cloud": True, "title": m.get("title") or m["id"]}
    else:
        ap.error("нужен --key или --llm")
    jp = json.loads(a.judge) if a.judge else None
    groups = [g.strip() for g in a.group.split(",") if g.strip()]
    rep = asyncio.run(run_stand(prof, jp, groups, parse_sets(a.base), parse_sets(a.set), a.repeat, log=lambda t: print(t, flush=True)))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = "stand-" + rep["started"][:16].replace("-", "").replace(":", "").replace("T", "-")
    md = rep["stand_md"]
    (out / f"{stem}.md").write_text(md, encoding="utf-8")
    (out / f"{stem}.json").write_text(json.dumps(rep["stand"], ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n" + md, flush=True)
    print(f"Отчёт: {out / stem}.md", flush=True)


if __name__ == "__main__":
    main()
