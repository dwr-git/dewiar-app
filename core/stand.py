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


# Опыт 0 (аудит Fable 25.11: «стенд шумит сильнее, чем меняются гипотезы»): сбой сети или судьи — не провал сценария, а «не
# считается» (стенд 24.11: «судья не ответил: Сервер модели: нет связи» решил «Честность» 31 → 33)
NET_RX = __import__("re").compile(r"нет связи|не ответил вовремя|соединени\w* не установ|ConnectError|ConnectTimeout|ReadTimeout|"
                                  r"RemoteProtocolError|Server disconnected|судья не ответил|ошибкой 50[234]|занят", __import__("re").I)


def net_fail(r):
    """Прогон оборвала сеть или не ответил судья — не модель ошиблась."""
    if r.get("passed"):
        return False
    why = " ".join([str(r.get("error") or ""), str((r.get("judge") or {}).get("why") or "")])
    return bool(NET_RX.search(why)) and (r.get("judge") or {}).get("score") is None


def dispute(r):
    """Проверки и судья разошлись: проверка не сдана, а судья поставил 8+ — или наоборот (стенд 25.11: sit_preference —
    «курицей» в самоисправлении, судья 10/10). Такие прогоны — отдельной строкой, их решает человек."""
    sc_ = (r.get("judge") or {}).get("score")
    bad = [c for c in r.get("checks") or [] if not c.get("ok")]
    if sc_ is None:
        return ""
    if bad and sc_ >= 8:
        return f"проверка «{bad[0]['name'][:60]}» не сдана, судья {sc_:g}/10"
    if not bad and sc_ <= 3 and r.get("checks"):
        return f"проверки сданы, судья {sc_:g}/10"
    return ""


def noise(a_ok, a_n, b_ok, b_n):
    """Разница «до → после» больше разброса? Двухсторонняя оценка по долям (2 стандартные ошибки)."""
    if not a_n or not b_n:
        return True
    pa, pb = a_ok / a_n, b_ok / b_n
    p = (a_ok + b_ok) / (a_n + b_n)
    se = (p * (1 - p) * (1 / a_n + 1 / b_n)) ** 0.5
    return abs(pb - pa) <= 2 * se if se else pa == pb


def aggregate(runs):
    """runs: {"A": [rep, …], "B": [rep, …]} -> по сценариям и группам."""
    sc, gr = {}, {}
    for side, reps in runs.items():
        for rep in reps:
            for r in rep["scenarios"]:
                if r.get("skipped"):
                    continue
                e = sc.setdefault(r["id"], {"group": r["group"], "title": r["title"], "A": [], "B": [], "why": {"A": [], "B": []},
                                            "net": {"A": 0, "B": 0}, "dispute": {"A": [], "B": []}})
                if net_fail(r):
                    e["net"][side] += 1                  # не считается: ни в сданные, ни в проваленные
                    gr.setdefault(r["group"], {"A": [0, 0, []], "B": [0, 0, []]}).setdefault("net", {"A": 0, "B": 0})[side] += 1
                    continue
                d = dispute(r)
                if d:
                    e["dispute"][side].append(d)
                e[side].append({"ok": bool(r["passed"]), "t": r.get("time_s"), "score": r.get("score"),
                                "fail": "" if r["passed"] else fail_line(r)})
                e["why"][side].append(r.get("xray") or [])
                g = gr.setdefault(r["group"], {"A": [0, 0, []], "B": [0, 0, []]})
                g[side][0] += bool(r["passed"]); g[side][1] += 1
                if r.get("time_s") is not None:
                    g[side][2].append(r["time_s"])
    return sc, gr


def fail_line(r):
    """Почему прогон не сдан — одной строкой (владелец 21.11: «все эти вещи ты должен видеть из отчётов»): какие проверки
    не прошли, что сказал судья и чем кончился ответ — чтобы разбирать провалы по отчёту стенда, без повторного прогона."""
    bad = [c["name"] for c in r.get("checks") or [] if not c.get("ok")]
    j = (r.get("judge") or {}).get("why") or ""
    last = next((s.get("answer") or "" for s in reversed(r.get("steps") or []) if s.get("answer")), "")
    parts = ([r["error"][:120]] if r.get("error") else []) + (["проверки: " + ", ".join(bad[:3])] if bad else []) \
        + ([f"судья {r.get('score') if r.get('score') is not None else '—'}/10: {j[:220]}"] if j else []) \
        + ([f"ответ: «{' '.join(last.split())[:160]}»"] if last else [])
    return " · ".join(parts)


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
    if meta.get("judge"):
        L[-1:-1] = [f"Судья: {meta['judge']}."]
    if int(meta.get("repeat") or 1) < 5:
        L += [f"⚠ Повторов {meta['repeat']} — меньше 5: разница меньше 20 п. почти всегда — разброс (аудит 25.11).", ""]
    L += ["## Группы", "", "| группа | " + ("до | после | разница | вывод |" if ab else "сдано | время, с |"),
          "|---|" + ("---|---|---|---|" if ab else "---|---|")]
    for g, v in sorted(gr.items()):
        pa = v["A"][0] / v["A"][1] if v["A"][1] else 0
        if ab:
            pb = v["B"][0] / v["B"][1] if v["B"][1] else 0
            verdict = "в пределах разброса" if noise(v["A"][0], v["A"][1], v["B"][0], v["B"][1]) else ("лучше" if pb > pa else "хуже")
            L.append(f"| {g} | {v['A'][0]}/{v['A'][1]} ({pa:.0%}) | {v['B'][0]}/{v['B'][1]} ({pb:.0%}) | {(pb - pa) * 100:+.0f} п. | {verdict} |")
        else:
            t = round(statistics.mean(v["A"][2]), 1) if v["A"][2] else "—"
            L.append(f"| {g} | {v['A'][0]}/{v['A'][1]} ({pa:.0%}) | {t} |")
    unstable = [k for k, e in sc.items() if 0 < sum(x["ok"] for x in e["A"]) < len(e["A"])
                or (ab and 0 < sum(x["ok"] for x in e["B"]) < len(e["B"]))]
    nets = sum(e["net"]["A"] + e["net"]["B"] for e in sc.values())
    disp = sum(len(e["dispute"]["A"]) + len(e["dispute"]["B"]) for e in sc.values())
    L += ["", f"Непредсказуемых сценариев (то сдаёт, то нет): {len(unstable)} из {len(sc)}."]
    if nets:
        L.append(f"Не считаются (сбой сети или судьи — не ошибка модели): {nets} прогонов.")
    if disp:
        L.append(f"Проверка и судья разошлись: {disp} прогонов — решает человек (строки «спор» ниже).")
    L += ["", "## Сценарии", ""]
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
        for side, name in (("A", "до"), ("B", "после")) if ab else (("A", "прогон"),):
            fails = list(dict.fromkeys(x["fail"] for x in e[side] if x.get("fail")))[:2]   # не больше двух разных причин
            for f in fails:
                L.append(f"  - ✗ {name}: {f}")
            for d in list(dict.fromkeys(e["dispute"][side]))[:2]:
                L.append(f"  - ⚖ спор, {name}: {d}")
            if e["net"][side]:
                L.append(f"  - ⌁ {name}: не считается {e['net'][side]} (сбой сети или судьи)")
    return "\n".join(L) + "\n"


async def run_stand(prof, jp, groups, A, B, repeat, log=print, partial=None, resume=False):
    """До (A) и после (B) по очереди, repeat раз -> отчёт в виде отчёта экзамена (кабинет его принимает как есть):
    сценарии и итог — последнего прогона «после» (или «до»), а таблица стенда — в stand и stand_md.
    partial / resume (владелец 25.11: «экзамен почти закончился — и запустился заново… я оплачиваю токены большой модели»):
    исполнитель перезапускался (опубликовали архив сервера) — обычный экзамен продолжал с места, а стенд начинал с нуля.
    Теперь после каждого прогона он записан в partial (и внутри прогона — каждый сценарий, в своём файле), а с resume
    сделанное не повторяется."""
    from exam import run_exam, summary
    started = dt.datetime.now()
    runs = {"A": [], "B": []}
    pf = Path(partial) if partial else None
    done = {}
    if pf and resume and pf.is_file():
        try:
            st = json.loads(pf.read_text(encoding="utf-8"))
            started = dt.datetime.fromisoformat(st.get("started") or started.isoformat())
            done = {f"{x['i']}{x['side']}": x["rep"] for x in st.get("done") or []}
        except (ValueError, KeyError, TypeError):
            done = {}

    def keep():
        if pf:
            pf.write_text(json.dumps({"started": started.isoformat(timespec="seconds"),
                                      "done": [{"i": int(k[:-1]), "side": k[-1], "rep": v} for k, v in done.items()]},
                                     ensure_ascii=False), encoding="utf-8")
    if done:
        log(f"Продолжаю стенд: готово прогонов — {len(done)}")
    for i in range(repeat):                         # до и после — по очереди: время суток и нагрузка сервера поровну
        for side, ov in (("A", A), ("B", B)) if B else (("A", A),):
            k = f"{i}{side}"
            log(f"=== Прогон {i + 1}/{repeat} · {'после' if side == 'B' else 'до'} ===")
            if k in done:
                runs[side].append(done[k])
                continue
            one = (str(pf) + f".{k}") if pf else None              # сценарии этого прогона — по одному, тоже с продолжением
            rep = await run_exam(prof, jp, None, False, log=log, groups=groups, overrides=ov,
                                 label=("после" if side == "B" else "до"), partial=one, resume=bool(resume and one))
            runs[side].append(rep)
            done[k] = rep
            keep()
            if one:
                Path(one).unlink(missing_ok=True)
    sc, gr = aggregate(runs)
    meta = {"started": started.isoformat(timespec="seconds"), "model": prof.get("title") or prof.get("model"), "repeat": repeat,
            "groups": list(groups), "A": A, "B": B,
            "judge": ((jp or {}).get("title") or (jp or {}).get("model")) if jp else "та же модель (лучше — другая: аудит 25.11)"}
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
