"""Плагин «Jira команды» (25.11, владелец: «Jira — своя… я бы сейчас сделал плагин»; по образцу его «Аналитики Jira»).

Свой сервер Jira (Server / Data Center) по личному токену (PAT, заголовок Bearer); облачная Jira — «почта:токен» (Basic).
Задачи с историей статусов кладутся в папку данных плагина (jira.json) — дальше всё считается без сети:
- кто ДЕЛАЛ работу — исполнитель в момент закрытия (а не тот, кто завёл задачу);
- вехи: создано → взято в работу (первый переход в статус категории «в работе») → завершено (последний переход в «готово»
  или resolutiondate); категории статусов берутся из самой Jira (new / indeterminate / done) — не зависят от языка и
  названий;
- дообновление — только изменённое (updated >= прошлый раз − запас), постранично, с курсором: прерванная загрузка
  продолжается с места обрыва.
Только чтение: в Jira плагин ничего не меняет. Токен приходит из настройки «secret» — модель его не видит
(core/plugins.py: не попадает ни в текст навыка, ни в поручения дел).

Помощнице видно ОДНО действие — jira (what: overview / people / person / stuck / changes / mine / find / issue), чтобы не
раздувать подсказку; странице — jira_page, jira_sync, jira_check (dewiar/page)."""
import base64
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA = Path(os.environ.get("DEWIAR_PLUGIN_DATA") or Path.home() / ".dewiar-jira")
STORE = DATA / "jira.json"
FIELDS = "summary,status,assignee,reporter,issuetype,project,priority,created,updated,resolutiondate,duedate"
STORE_V = 2                   # 1.0.81: отсутствия (поля дат) — прежний учёт перезагружается целиком один раз
PAGE = 50
EV_DAYS = 120                 # события статусов храним за 4 месяца — «что делал за неделю», «изменения за сутки»
STALE_DAYS = 14               # «застряло»: в работе и без движения столько дней
AUTO_SYNC_MIN = 10            # помощница спрашивает — сначала дообновить, если прошло больше
BUG_RX = re.compile(r"bug|ошиб|дефект|баг", re.I)
DAY = 86400


# ---------- настройки и хранилище ----------
def settings():
    try:
        s = json.loads(os.environ.get("DEWIAR_PLUGIN_SETTINGS") or "{}")
    except ValueError:
        s = {}
    url = str(s.get("url") or "").strip().rstrip("/")
    if url and not re.match(r"https?://", url):
        url = "https://" + url
    # вставили ссылку на задачу или доску — берём адрес самой Jira (с путём, если Jira стоит не в корне: …/jira)
    url = re.sub(r"[?#].*$", "", url)
    url = re.sub(r"/(browse|secure|projects|issues|jira/software|plugins|rest|login\.jsp|Dashboard\.jspa)(/.*)?$", "", url, flags=re.I).rstrip("/")
    # «Доски или проекты» (владелец 25.11: «права на просмотр доски или нескольких досок»): ссылка на доску
    # (…RapidBoard.jspa?rapidView=25, …/boards/25), номер доски или ключ проекта — через точку с запятой
    projects, boards = [], []
    for w in re.split(r"[;\s]+", str(s.get("projects") or "")):
        w = w.strip().strip(",")
        b = re.search(r"(?:rapidView=|/boards/)(\d+)", w) or re.fullmatch(r"#?(\d+)", w)
        if b:
            boards.append(int(b.group(1)))
        elif re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,30}", w):
            projects.append(w.upper())
    return {"url": url, "token": str(s.get("token") or "").strip(), "projects": sorted(set(projects)), "boards": sorted(set(boards))}


def load():
    try:
        d = json.loads(STORE.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            return d
    except (OSError, ValueError):
        pass
    return {}


def save(d):
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(STORE)


def fresh_store(cfg):
    """Сменили адрес Jira или список проектов — прежний учёт не годится."""
    d = load()
    sig = f"v{STORE_V}|" + cfg["url"] + "|" + ",".join(cfg["projects"]) + "|" + ",".join(map(str, cfg["boards"]))
    if d.get("sig") != sig:
        d = {"sig": sig, "issues": {}, "statuses": {}, "since": "", "cursor": None, "synced": 0, "me": {}}
    return d


# ---------- Jira ----------
class JiraError(Exception):
    pass


def get(cfg, path, query=None, timeout=40):
    if not cfg["url"]:
        raise JiraError("не указан адрес Jira — заполните его в настройках плагина")
    if not cfg["token"]:
        raise JiraError("нет токена — создайте личный токен в Jira (Профиль → Персональные токены доступа) и вставьте в настройки")
    url = cfg["url"] + path + ("?" + urllib.parse.urlencode(query) if query else "")
    tok = cfg["token"]
    auth = "Basic " + base64.b64encode(tok.encode()).decode() if ":" in tok else "Bearer " + tok   # облако: почта:токен
    req = urllib.request.Request(url, headers={"Accept": "application/json", "Authorization": auth, "User-Agent": "Dewiar-Jira/1.0"})
    err = ""
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
                body = r.read()
            try:
                return json.loads(body.decode("utf-8"))
            except ValueError:
                raise JiraError("Jira ответила не данными, а страницей — проверьте адрес (нужен адрес самой Jira, например https://jira.company.ru)") from None
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise JiraError(f"Jira не пускает (HTTP {e.code}) — проверьте токен и что у него есть доступ к проектам") from None
            if e.code == 404:
                raise JiraError("по этому адресу Jira не нашлась (HTTP 404) — проверьте адрес") from None
            if e.code == 400:
                try:
                    msg = "; ".join(json.loads(e.read().decode("utf-8")).get("errorMessages") or [])
                except (ValueError, OSError):
                    msg = ""
                raise JiraError("Jira не приняла запрос" + (f": {msg}" if msg else "") + " — проверьте ключи проектов в настройках") from None
            err = f"HTTP {e.code}"
        except urllib.error.URLError as e:
            r = str(getattr(e, "reason", e))
            if "CERTIFICATE_VERIFY_FAILED" in r:
                raise JiraError("сертификат сервера Jira не проходит проверку — нужен действующий сертификат (https)") from None
            err = r
        except (TimeoutError, OSError) as e:
            err = str(e) or "нет ответа"
        time.sleep(0.6 * (attempt + 1))
    raise JiraError(f"Jira не отвечает ({err}) — проверьте адрес и что компьютер в сети компании (VPN)")


def ts(s):
    """'2026-11-25T14:03:11.000+0300' -> секунды."""
    if not s:
        return 0
    try:
        return int(datetime.strptime(str(s)[:28], "%Y-%m-%dT%H:%M:%S.%f%z").timestamp())
    except ValueError:
        try:
            return int(datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp())
        except ValueError:
            return 0


def jql_time(s, back_min=5):
    """Время задачи в её же часовом поясе (Jira пишет в поясе пользователя токена — в нём же понимает JQL) минус запас."""
    try:
        d = datetime.strptime(str(s)[:28], "%Y-%m-%dT%H:%M:%S.%f%z") - timedelta(minutes=back_min)
        return d.strftime("%Y/%m/%d %H:%M")
    except ValueError:
        return ""


def person(u):
    if not isinstance(u, dict):
        return ""
    return str(u.get("displayName") or u.get("name") or u.get("key") or u.get("accountId") or "")[:80]


def statuses(cfg):
    out = {}
    for st in get(cfg, "/rest/api/2/status") or []:
        out[str(st.get("id"))] = [str(st.get("name") or ""), ((st.get("statusCategory") or {}).get("key") or "new")]
    return out


def digest(it, stmap, now, dfields=None):
    """Задача из Jira -> короткая запись учёта."""
    f = it.get("fields") or {}
    st = f.get("status") or {}
    cat = ((st.get("statusCategory") or {}).get("key")) or (stmap.get(str(st.get("id"))) or ["", "new"])[1]
    hist = sorted(((it.get("changelog") or {}).get("histories") or []), key=lambda h: str(h.get("created") or ""))
    cur_a = person(f.get("assignee"))
    a_changes = [(h, i) for h in hist for i in (h.get("items") or []) if i.get("field") == "assignee"]
    assignee = str(a_changes[0][1].get("fromString") or "") if a_changes else cur_a
    started = done = 0
    done_by = done_author = ""
    ev = []
    for h in hist:
        t = ts(h.get("created"))
        for i in h.get("items") or []:
            if i.get("field") == "assignee":
                assignee = str(i.get("toString") or "")
            elif i.get("field") == "status":
                name, c = stmap.get(str(i.get("to")), [str(i.get("toString") or ""), ""])
                if not c:
                    c = "done" if re.search(r"done|готов|закры|выполн|resolved|closed", name, re.I) else \
                        "indeterminate" if re.search(r"progress|работ|review|ревью|тест", name, re.I) else "new"
                if c == "indeterminate" and not started:
                    started = t
                if c == "done":
                    done, done_by, done_author = t, assignee, person(h.get("author"))
                elif done:                               # переоткрыли — снова не готово
                    done, done_by = 0, ""
                if now - t <= EV_DAYS * DAY:
                    ev.append([t, person(h.get("author")), name[:40], c])
    if cat == "done":
        done = done or ts(f.get("resolutiondate")) or ts(f.get("updated"))
        done_by = done_by or done_author or cur_a
    else:
        done, done_by = 0, ""
    typ = str((f.get("issuetype") or {}).get("name") or "")
    return {"k": it.get("key"), "p": str((f.get("project") or {}).get("key") or str(it.get("key") or "").split("-")[0]),
            "s": str(f.get("summary") or "")[:220], "t": typ[:30], "bug": bool(BUG_RX.search(typ)),
            "st": str(st.get("name") or "")[:40], "c": cat, "a": cur_a, "r": person(f.get("reporter")),
            "pr": str((f.get("priority") or {}).get("name") or "")[:20],
            "cr": ts(f.get("created")), "up": ts(f.get("updated")), "upr": str(f.get("updated") or ""),
            "go": started, "dn": done, "by": done_by, "ev": ev[-30:], "ab": absence(f, dfields)}


def sync(full=False, budget=40):
    """Дообновить учёт. -> {done, loaded, total, issues, synced}. Не уложились в budget секунд — done=False, курсор
    сохранён, следующий вызов продолжит."""
    cfg = settings()
    d = fresh_store(cfg)
    if full:
        d.update(issues={}, since="", cursor=None)
    t0, now = time.time(), int(time.time())
    if not d.get("statuses") or not d.get("cursor"):
        d["statuses"] = statuses(cfg)
        d["dfields"] = date_fields(cfg)
        d["scope"] = scope(cfg)                         # фильтр досок мог измениться — берём заново при каждой новой загрузке
        if not d.get("me"):
            me = get(cfg, "/rest/api/2/myself")
            d["me"] = {"name": person(me), "key": str(me.get("name") or me.get("key") or me.get("accountId") or "")}
    cur = d.get("cursor") or {"jql": build_jql(d.get("scope", ""), d.get("since")), "at": 0, "started": now, "max": ""}
    loaded, total = 0, None
    while True:
        fl = ",".join([FIELDS] + [x for x in (d.get("dfields") or []) if x])
        r = get(cfg, "/rest/api/2/search", {"jql": cur["jql"], "startAt": cur["at"], "maxResults": PAGE, "fields": fl, "expand": "changelog"}, timeout=60)
        items = r.get("issues") or []
        total = int(r.get("total") or 0)
        for it in items:
            rec = digest(it, d["statuses"], now, d.get("dfields"))
            if rec["k"]:
                d["issues"][rec["k"]] = rec
                if rec["upr"] > cur["max"]:
                    cur["max"] = rec["upr"]
        loaded += len(items)
        cur["at"] += len(items)
        if not items or cur["at"] >= total:
            d["since"] = jql_time(cur["max"]) if cur["max"] else d.get("since", "")
            d["cursor"], d["synced"] = None, int(time.time())
            save(d)
            return {"done": True, "loaded": loaded, "total": total, "issues": len(d["issues"]), "synced": d["synced"]}
        d["cursor"] = cur
        save(d)
        if time.time() - t0 > budget:
            return {"done": False, "loaded": loaded, "left": max(0, total - cur["at"]), "total": total, "issues": len(d["issues"]), "synced": d.get("synced", 0)}


def scope(cfg):
    """Что загружать: проекты и доски (фильтр доски — тот же JQL, что видит доска в Jira) -> JQL без сортировки."""
    parts = []
    if cfg["projects"]:
        parts.append("project in (" + ",".join(f'"{p}"' for p in cfg["projects"]) + ")")
    for b in cfg["boards"]:
        try:
            fid = (get(cfg, f"/rest/agile/1.0/board/{b}/configuration").get("filter") or {}).get("id")
            jql = str(get(cfg, f"/rest/api/2/filter/{fid}").get("jql") or "") if fid else ""
        except JiraError:
            raise JiraError(f"доска {b} не открылась: такой нет или у токена нет к ней доступа — проверьте, что она открывается "
                            "в Jira под тем же входом, что и токен") from None
        jql = re.sub(r"\s+ORDER\s+BY\s+.*$", "", jql, flags=re.I | re.S).strip()
        if jql:
            parts.append(f"({jql})")
    return " OR ".join(parts)


def build_jql(sc, since):
    parts = [f"({sc})"] if sc else []
    if since:
        parts.append(f'updated >= "{since}"')
    return " AND ".join(parts) + " ORDER BY updated ASC"


def ensure(max_age_min=AUTO_SYNC_MIN, budget=20):
    """Перед ответом помощнице — дообновить, если давно. Нет связи — считаем по тому, что есть (и говорим об этом)."""
    d = load()
    note = ""
    if time.time() - float(d.get("synced") or 0) > max_age_min * 60 or d.get("cursor"):
        try:
            r = sync(budget=budget)
            if not r["done"]:
                note = f"загружено не всё: осталось {r['left']} задач — продолжу при следующем запросе"
        except JiraError as e:
            if not d.get("issues"):
                raise
            note = f"Jira сейчас недоступна ({e}) — данные на {fmt_dt(d.get('synced'))}"
        d = load()
    return d, note


# ---------- отсутствия (по образцу «Аналитики Jira» владельца: lib/Absences.php) ----------
# Отпуск, больничный… — это обычные задачи Jira. Тип — по словам в названии (частное раньше общего: «отпуск за свой счёт» —
# «За свой счёт»), человек — исполнитель, даты — из полей «начало / окончание» (их же заполняет Календарь Jira), иначе из
# названия: «Отпуск 15 - 28 июня», «28 мая - 10 июня», «15.06 - 28.06», «с 3 по 14 августа», «до 6 июня», «6 июня».
AB_TYPES = [("sick", "Больничный", ("больничн", "sick leave", "sick-leave")),
            ("unpaid", "За свой счёт", ("за свой счет", "без содержания", "unpaid leave")),
            ("dayoff", "Отгул", ("отгул", "day off", "day-off")),
            ("trip", "Командировка", ("командировк", "business trip")),
            ("decree", "Декрет", ("декрет", "по уходу за ребен")),
            ("vacation", "Отпуск", ("отпуск", "vacation", "holiday"))]
AB_LABEL = {k: l for k, l, _ in AB_TYPES}
MON = [("янв", 1), ("фев", 2), ("мар", 3), ("апр", 4), ("июн", 6), ("июл", 7), ("авг", 8), ("сен", 9), ("окт", 10), ("ноя", 11),
       ("дек", 12), ("ма", 5)]
M_RE = r"(январ\w*|янв\.?|феврал\w*|фев\.?|март\w*|мар\.?|апрел\w*|апр\.?|ма[йя]|июн\w*|июл\w*|август\w*|авг\.?|сентябр\w*|сент?\.?|октябр\w*|окт\.?|ноябр\w*|ноя\.?|декабр\w*|дек\.?)"
D_RE = r"(?:[-–—]|по)"
START_NAMES = ("дата начала", "начало", "start date", "target start", "planned start")
END_NAMES = ("дата окончания", "окончание", "end date", "target end", "planned end")


def date_fields(cfg):
    """Поля «начало / окончание» в этой Jira (по названию) -> [id начала, id окончания]."""
    try:
        fs = get(cfg, "/rest/api/2/field") or []
    except JiraError:
        return []

    def find(names):
        for n in names:
            for x in fs:
                if str(x.get("name") or "").strip().lower() == n and str((x.get("schema") or {}).get("type")) in ("date", "datetime"):
                    return str(x.get("id"))
        return ""
    return [find(START_NAMES), find(END_NAMES)]


def ab_type(summary):
    s = norm(summary)
    for k, _, words in AB_TYPES:
        if any(w in s for w in words):
            return k
    return ""


def month(w):
    w = norm(w)
    return next((n for p, n in MON if w.startswith(p)), 0)


def mk(y, m, d):
    try:
        return datetime(y, m, d).date()
    except ValueError:
        return None


def near_year(m, d, ref):
    best = None
    for y in (ref.year - 1, ref.year, ref.year + 1):
        x = mk(y, m, d)
        if x and (best is None or abs((x - ref).days) < abs((best - ref).days)):
            best = x
    return best.year if best else ref.year


def fix_y(y):
    return y if y >= 1000 else y + (2000 if y < 70 else 1900)


def parse_range(summary, ref):
    """Период из названия -> (начало, конец) или None. ref — дата создания задачи (год — ближайший к ней)."""
    s = norm(summary)
    m = re.search(rf"(\d{{1,2}})\s*{M_RE}\s*{D_RE}\s*(\d{{1,2}})\s*{M_RE}", s)
    if m and month(m.group(2)) and month(m.group(4)):
        y = near_year(month(m.group(2)), int(m.group(1)), ref)
        a, b = mk(y, month(m.group(2)), int(m.group(1))), mk(y, month(m.group(4)), int(m.group(3)))
        if a and b:
            return a, (b if b >= a else mk(y + 1, month(m.group(4)), int(m.group(3))) or b)
    m = re.search(rf"(\d{{1,2}})\s*{D_RE}\s*(\d{{1,2}})\s*{M_RE}", s)
    if m and month(m.group(3)):
        mm = month(m.group(3))
        y = near_year(mm, int(m.group(1)), ref)
        a, b = mk(y, mm, int(m.group(1))), mk(y, mm, int(m.group(2)))
        if a and b and b >= a:
            return a, b
    m = re.search(rf"(\d{{1,2}})[./](\d{{1,2}})(?:[./](\d{{2,4}}))?\s*{D_RE}\s*(\d{{1,2}})[./](\d{{1,2}})(?:[./](\d{{2,4}}))?", s)
    if m:
        y1 = fix_y(int(m.group(3))) if m.group(3) else near_year(int(m.group(2)), int(m.group(1)), ref)
        a = mk(y1, int(m.group(2)), int(m.group(1)))
        y2 = fix_y(int(m.group(6))) if m.group(6) else y1
        b = mk(y2, int(m.group(5)), int(m.group(4)))
        if a and b and b < a and not m.group(6):
            b = mk(y2 + 1, int(m.group(5)), int(m.group(4)))
        if a and b and b >= a:
            return a, b
    m = re.search(rf"(?:до|по)\s+(\d{{1,2}})\s*{M_RE}", s)
    if m and month(m.group(2)):
        b = mk(near_year(month(m.group(2)), int(m.group(1)), ref), month(m.group(2)), int(m.group(1)))
        if b:
            return min(ref, b), b
    for rx in (rf"с\s+(\d{{1,2}})\s*{M_RE}", rf"(\d{{1,2}})\s*{M_RE}"):
        m = re.search(rx, s)
        if m and month(m.group(2)):
            a = mk(near_year(month(m.group(2)), int(m.group(1)), ref), month(m.group(2)), int(m.group(1)))
            if a:
                return a, a
    m = re.search(r"(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?", s)
    if m:
        y = fix_y(int(m.group(3))) if m.group(3) else near_year(int(m.group(2)), int(m.group(1)), ref)
        a = mk(y, int(m.group(2)), int(m.group(1)))
        if a:
            return a, a
    return None


def fdate(v):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(v or ""))
    return mk(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def absence(f, dfields):
    """-> [тип, начало, конец, откуда] для задачи-отсутствия; иначе None."""
    k = ab_type(f.get("summary"))
    if not k:
        return None
    st_id, en_id = (list(dfields or []) + ["", ""])[:2]
    a, b = fdate(f.get(st_id)) if st_id else None, fdate(f.get(en_id)) if en_id else None
    b = b or fdate(f.get("duedate")) if a else b
    if a and b and b >= a:
        return [k, a.isoformat(), b.isoformat(), "поля"]
    ref = datetime.fromtimestamp(ts(f.get("created")) or time.time()).date()
    r = parse_range(f.get("summary"), ref)
    if r:
        return [k, r[0].isoformat(), r[1].isoformat(), "название"]
    return [k, "", "", ""]


def workdays(a, b):
    return sum(1 for i in range((b - a).days + 1) if (a + timedelta(days=i)).weekday() < 5)


def absences(d, start=None, end=None, project=""):
    """Отсутствия в окне [start, end] (по умолчанию — 90 дней назад и 60 вперёд)."""
    today = datetime.now().date()
    start = start or today - timedelta(days=90)
    end = end or today + timedelta(days=60)
    rows, loose = [], []
    for x in pick(d, project, True):
        ab = x.get("ab")
        if not ab:
            continue
        who = x["a"] or x["r"] or "—"
        if not ab[1]:
            loose.append({"key": x["k"], "title": x["s"], "who": who, "type": AB_LABEL.get(ab[0], "")})
            continue
        a, b = datetime.fromisoformat(ab[1]).date(), datetime.fromisoformat(ab[2]).date()
        if b < start or a > end:
            continue
        rows.append({"key": x["k"], "who": who, "type": ab[0], "label": AB_LABEL.get(ab[0], ""), "from": ab[1], "to": ab[2],
                     "days": (b - a).days + 1, "work": workdays(a, b), "src": ab[3], "now": a <= today <= b})
    rows.sort(key=lambda r: (r["who"], r["from"]))
    P = {}
    for r in rows:
        p = P.setdefault(r["who"], {"name": r["who"], "vacation": 0, "sick": 0, "other": 0, "days": 0, "work": 0, "periods": 0, "now": ""})
        p["vacation" if r["type"] == "vacation" else "sick" if r["type"] == "sick" else "other"] += r["days"]
        p["days"] += r["days"]
        p["work"] += r["work"]
        p["periods"] += 1
        if r["now"]:
            p["now"] = r["label"]
    people_ = sorted(P.values(), key=lambda p: -p["days"])
    return {"from": start.isoformat(), "to": end.isoformat(), "today": today.isoformat(), "items": rows, "people": people_,
            "loose": loose[:20], "now": [{"who": r["who"], "label": r["label"], "to": r["to"]} for r in rows if r["now"]],
            "soon": [{"who": r["who"], "label": r["label"], "from": r["from"], "to": r["to"]} for r in rows
                     if today < datetime.fromisoformat(r["from"]).date() <= today + timedelta(days=14)]}


# ---------- связи: кто с кем работал над одними задачами ----------
def graph(d, days=180, project=""):
    """Люди и связи. Сильная связь — общие задачи (вели, двигали, закрывали одну задачу); слабая — одна «команда»
    (проект, где человек работал больше всего): она собирает команды в облака, даже если над одной задачей не сходились."""
    now = int(time.time())
    t0 = now - days * DAY
    done, links, proj = {}, {}, {}
    for x in pick(d, project):
        if x["up"] < t0:
            continue
        ppl = sorted({n for n in [x["a"], x.get("by")] + [e[1] for e in x["ev"]] if n})
        if x["dn"] >= t0 and x.get("by"):
            done[x["by"]] = done.get(x["by"], 0) + 1
        for n in ppl:
            done.setdefault(n, 0)
            proj.setdefault(n, {})[x["p"]] = proj.get(n, {}).get(x["p"], 0) + 1
        for i in range(len(ppl)):
            for j in range(i + 1, len(ppl)):
                links[(ppl[i], ppl[j])] = links.get((ppl[i], ppl[j]), 0) + 1
    top = sorted(done, key=lambda n: (-done[n], n))[:40]
    keep = set(top)
    team = {n: max(proj[n].items(), key=lambda kv: kv[1])[0] for n in top}
    edges = [{"a": a, "b": b, "w": w} for (a, b), w in sorted(links.items(), key=lambda kv: -kv[1]) if a in keep and b in keep][:160]
    have = {(e["a"], e["b"]) for e in edges}
    for i, a in enumerate(top):
        for b in top[i + 1:]:
            k = (min(a, b), max(a, b))
            if team[a] == team[b] and k not in have and len(edges) < 260:
                edges.append({"a": k[0], "b": k[1], "w": 0, "team": True})
    return {"days": days, "nodes": [{"name": n, "done": done[n], "team": team[n]} for n in top], "edges": edges,
            "teams": sorted(set(team.values()), key=lambda t: -sum(team[n] == t for n in top))}


# ---------- счёт ----------
def fmt_dt(t):
    return datetime.fromtimestamp(int(t or 0)).strftime("%d.%m %H:%M") if t else "—"


def fmt_d(t):
    return datetime.fromtimestamp(int(t)).strftime("%d.%m.%Y") if t else ""


def dur(sec):
    if sec < 0:
        return "—"
    h = sec / 3600
    return f"{h:.1f} ч".replace(".", ",") if h < 48 else f"{round(h / 24)} дн"


def pct(vals, q):
    if not vals:
        return 0
    v = sorted(vals)
    return v[min(len(v) - 1, int(round(q * (len(v) - 1))))]


def pick(d, project="", with_absences=False):
    """Задачи учёта (проект — по ключу). Отпуска и больничные — тоже задачи Jira, но не работа: в счёт не идут."""
    pr = str(project or "").strip().upper()
    return [x for x in d.get("issues", {}).values() if (not pr or x["p"] == pr) and (with_absences or not x.get("ab"))]


def row(x, now):
    return {"key": x["k"], "title": x["s"], "status": x["st"], "cat": x["c"], "who": x["a"] or "—", "type": x["t"],
            "days": round((now - (x["go"] or x["cr"])) / DAY) if x["c"] != "done" else None,
            "done": fmt_d(x["dn"]) if x["dn"] else "", "by": x.get("by") or ""}


def overview(d, days=30, project=""):
    now, xs = int(time.time()), pick(d, project)
    t0 = now - days * DAY
    done_p = [x for x in xs if x["dn"] >= t0]
    prog = sorted((x for x in xs if x["c"] == "indeterminate"), key=lambda x: x["go"] or x["cr"])
    cyc = [x["dn"] - (x["go"] or x["cr"]) for x in done_p if x["dn"] >= (x["go"] or x["cr"])]
    weeks = min(26, max(6, days // 7 + 1))
    mon = datetime.fromtimestamp(now).date() - timedelta(days=datetime.fromtimestamp(now).weekday())
    starts = [int(datetime.combine(mon - timedelta(weeks=weeks - 1 - i), datetime.min.time()).timestamp()) for i in range(weeks)]

    def wk(t):
        for i in range(len(starts) - 1, -1, -1):
            if t >= starts[i]:
                return i
        return -1
    cr, dn = [0] * weeks, [0] * weeks
    for x in xs:
        if x["cr"] >= starts[0]:
            cr[wk(x["cr"])] += 1
        if x["dn"] and x["dn"] >= starts[0]:
            dn[wk(x["dn"])] += 1
    stale = [x for x in prog if now - (max(e[0] for e in x["ev"]) if x["ev"] else x["up"]) > STALE_DAYS * DAY]
    mix = {}
    for x in xs:
        mix[(x["st"], x["c"])] = mix.get((x["st"], x["c"]), 0) + 1
    return {"period_days": days, "project": project or "все",
            "done_prev": sum(t0 - days * DAY <= x["dn"] < t0 for x in xs),
            "statuses": [{"name": n, "cat": c, "count": v} for (n, c), v in sorted(mix.items(), key=lambda kv: -kv[1])[:8]],
            "total": len(xs), "done": sum(x["c"] == "done" for x in xs), "in_progress": len(prog),
            "todo": sum(x["c"] == "new" for x in xs), "done_period": len(done_p),
            "created_period": sum(x["cr"] >= t0 for x in xs),
            "bugs_open": sum(x["bug"] and x["c"] != "done" for x in xs),
            "people_period": len({x["by"] for x in done_p if x["by"]}),
            "cycle": {"median": dur(pct(cyc, .5)) if cyc else "—", "p85": dur(pct(cyc, .85)) if cyc else "—",
                      "max": dur(max(cyc)) if cyc else "—"},
            "weeks": [datetime.fromtimestamp(s).strftime("%d.%m") for s in starts], "created_w": cr, "done_w": dn,
            "oldest": [row(x, now) for x in prog[:12]], "stale": len(stale),
            "projects": sorted({x["p"] for x in d.get("issues", {}).values()})}


def people(d, days=30, project=""):
    now, xs = int(time.time()), pick(d, project)
    t0 = now - days * DAY
    P = {}

    def g(n):
        return P.setdefault(n, {"name": n, "done": 0, "in_progress": 0, "started": 0, "bugs": 0, "_cyc": []})
    for x in xs:
        if x["dn"] >= t0 and x["by"]:
            p = g(x["by"])
            p["done"] += 1
            p["bugs"] += x["bug"]
            if x["dn"] >= (x["go"] or x["cr"]):
                p["_cyc"].append(x["dn"] - (x["go"] or x["cr"]))
        if x["c"] == "indeterminate" and x["a"]:
            g(x["a"])["in_progress"] += 1
        if x["go"] >= t0 and x["a"]:
            g(x["a"])["started"] += 1
    out = []
    for p in P.values():
        c = p.pop("_cyc")
        p["cycle"] = dur(pct(c, .5)) if c else "—"
        out.append(p)
    out.sort(key=lambda p: (-p["done"], -p["in_progress"], p["name"]))
    return {"period_days": days, "people": out}


def norm(s):
    return re.sub(r"\s+", " ", str(s or "").lower().replace("ё", "е")).strip()


TRANSLIT = str.maketrans({"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ж": "zh", "з": "z", "и": "i", "й": "i",
                          "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
                          "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ы": "y", "э": "e", "ю": "yu", "я": "ya",
                          "ь": "", "ъ": ""})


def match_person(d, name):
    """«Иван», «Kudelevich», «Марию» -> имя из Jira. Имена в Jira часто латиницей — сравниваем и в транслите."""
    names = {x[k] for x in d.get("issues", {}).values() for k in ("a", "by") if x.get(k)}
    q = norm(name)
    if not q:
        return ""
    qs = [w for w in re.findall(r"\w+", q) if len(w) > 2]
    best, score = "", 0
    for n in names:
        nn = norm(n)
        words = re.findall(r"\w+", nn)
        sc = 0
        for w in qs:
            for v in (w, w.translate(TRANSLIT)):
                stem = v[:max(3, len(v) - 2)]
                if any(x.startswith(stem) for x in words):
                    sc += 2 if v == w else 1.5
                    break
        if q == nn:
            sc += 10
        if sc > score:
            best, score = n, sc
    return best


def person_card(d, name, days=7):
    who = match_person(d, name)
    if not who:
        return {"error": f"в задачах Jira не нашла «{name}»"}
    now = int(time.time())
    t0 = now - days * DAY
    xs = pick(d)
    done = sorted((x for x in xs if x.get("by") == who and x["dn"] >= t0), key=lambda x: -x["dn"])
    prog = sorted((x for x in xs if x["a"] == who and x["c"] == "indeterminate"), key=lambda x: x["go"] or x["cr"])
    moved = sorted(({"key": x["k"], "title": x["s"], "to": e[2], "at": fmt_dt(e[0])} for x in xs for e in x["ev"]
                    if e[1] == who and e[0] >= t0), key=lambda m: m["at"], reverse=True)
    return {"name": who, "period_days": days, "done": [row(x, now) for x in done[:15]], "done_count": len(done),
            "in_progress": [row(x, now) for x in prog[:10]], "moves": moved[:15]}


def stuck(d, days=STALE_DAYS, project=""):
    now = int(time.time())
    out = []
    for x in pick(d, project):
        if x["c"] != "indeterminate":
            continue
        last = max([e[0] for e in x["ev"]] + [x["up"]])
        if now - last > days * DAY:
            out.append(dict(row(x, now), quiet_days=round((now - last) / DAY)))
    out.sort(key=lambda r: -r["quiet_days"])
    return {"days": days, "count": len(out), "items": out[:15]}


def changes(d, hours=24, project=""):
    now = int(time.time())
    t0 = now - hours * 3600
    xs = pick(d, project)
    return {"hours": hours,
            "done": [row(x, now) for x in sorted(xs, key=lambda x: -x["dn"]) if x["dn"] >= t0][:15],
            "started": [row(x, now) for x in xs if x["go"] >= t0 and x["c"] == "indeterminate"][:15],
            "created": [row(x, now) for x in sorted(xs, key=lambda x: -x["cr"]) if x["cr"] >= t0][:15],
            "new_bugs": sum(x["bug"] and x["cr"] >= t0 for x in xs)}


def mine(d):
    me = (d.get("me") or {}).get("name") or ""
    now = int(time.time())
    xs = [x for x in pick(d) if x["a"] == me and x["c"] != "done"]
    xs.sort(key=lambda x: (x["c"] != "indeterminate", x["cr"]))
    return {"me": me, "count": len(xs), "items": [row(x, now) for x in xs[:20]]}


def find(d, q):
    words = [w for w in re.findall(r"\w+", norm(q)) if len(w) > 1]
    key = re.search(r"[A-Za-z][A-Za-z0-9_]*-\d+", q or "")
    now = int(time.time())
    xs = d.get("issues", {}).values()
    if key:
        hit = [x for x in xs if x["k"].upper() == key.group(0).upper()]
    else:
        hit = [x for x in xs if all(w[:max(3, len(w) - 2)] in norm(x["s"]) for w in words)] if words else []
    hit.sort(key=lambda x: (x["c"] == "done", -x["up"]))
    return {"query": q, "count": len(hit), "items": [row(x, now) for x in hit[:15]]}


def issue(key):
    cfg = settings()
    k = str(key or "").strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*-\d+", k):
        raise JiraError("нужен номер задачи, например AI-177")
    r = get(cfg, f"/rest/api/2/issue/{k}", {"fields": FIELDS + ",description,comment,labels"})
    f = r.get("fields") or {}
    com = ((f.get("comment") or {}).get("comments") or [])[-3:]
    return {"key": k, "title": f.get("summary"), "status": (f.get("status") or {}).get("name"), "who": person(f.get("assignee")) or "—",
            "author": person(f.get("reporter")), "type": (f.get("issuetype") or {}).get("name"), "created": fmt_d(ts(f.get("created"))),
            "updated": fmt_dt(ts(f.get("updated"))), "labels": f.get("labels") or [],
            "description": re.sub(r"\s+", " ", str(f.get("description") or ""))[:1500],
            "comments": [{"who": person(c.get("author")), "at": fmt_dt(ts(c.get("created"))), "text": re.sub(r"\s+", " ", str(c.get("body") or ""))[:400]} for c in com],
            "url": f"{cfg['url']}/browse/{k}"}


def ask(a):
    """Единственное действие помощницы."""
    what = str(a.get("what") or "overview")
    if what == "issue":
        return issue(a.get("q") or a.get("key"))
    d, note = ensure()
    days = int(a.get("days") or (7 if what == "person" else 30))
    pr = str(a.get("project") or "")
    if what == "people":
        r = people(d, days, pr)
        r["people"] = r["people"][:15]
    elif what == "person":
        r = person_card(d, str(a.get("q") or ""), days)
    elif what == "stuck":
        r = stuck(d, int(a.get("days") or STALE_DAYS), pr)
    elif what == "changes":
        r = changes(d, int(a.get("hours") or 24), pr)
    elif what == "mine":
        r = mine(d)
    elif what == "find":
        r = find(d, str(a.get("q") or ""))
    elif what == "away":
        ab = absences(d, project=pr)
        r = {"now": ab["now"], "next_14_days": ab["soon"], "no_dates": len(ab["loose"])}
    else:
        r = overview(d, days, pr)
        r["oldest"] = r["oldest"][:5]
        for k in ("weeks", "created_w", "done_w"):
            r.pop(k, None)
    r["data_at"] = fmt_dt(d.get("synced"))
    if note:
        r["note"] = note
    return r


def page(a):
    """Всё для страницы плагина одним вызовом."""
    d = load()
    cfg = settings()
    days, pr = int(a.get("days") or 30), str(a.get("project") or "")
    out = {"configured": bool(cfg["url"] and cfg["token"]), "url": cfg["url"], "synced": d.get("synced", 0),
           "synced_at": fmt_dt(d.get("synced")), "pending": bool(d.get("cursor")), "me": (d.get("me") or {}).get("name", ""),
           "issues": len(d.get("issues", {}))}
    if d.get("issues"):
        out["overview"] = overview(d, days, pr)
        out["people"] = people(d, days, pr)["people"]
        out["stuck"] = stuck(d, STALE_DAYS, pr)["items"]
        out["changes"] = changes(d, 24, pr)
        out["busy"] = busy(d, pr)
        out["absences"] = absences(d, project=pr)
        out["graph"] = graph(d, max(90, days), pr)
        if a.get("person"):
            out["person"] = person_card(d, str(a["person"]), days)
    return out


def busy(d, project=""):
    """Кто чем занят сейчас: люди и их задачи в работе (дольше в работе — выше)."""
    now, P = int(time.time()), {}
    for x in pick(d, project):
        if x["c"] == "indeterminate":
            P.setdefault(x["a"] or "Без исполнителя", []).append(x)
    out = [{"name": n, "count": len(xs), "items": [row(x, now) for x in sorted(xs, key=lambda x: x["go"] or x["cr"])[:8]]}
           for n, xs in P.items()]
    out.sort(key=lambda p: (p["name"] == "Без исполнителя", -p["count"], p["name"]))
    return out


def task(key):
    """Карточка задачи для страницы: из Jira (описание, комментарии) + ход по статусам из учёта."""
    d = load()
    x = d.get("issues", {}).get(str(key or "").upper()) or {}
    try:
        r = issue(key)
    except JiraError as e:
        if not x:
            raise
        cfg = settings()
        r = {"key": x["k"], "title": x["s"], "status": x["st"], "who": x["a"] or "—", "author": x["r"], "type": x["t"],
             "created": fmt_d(x["cr"]), "updated": fmt_dt(x["up"]), "labels": [], "description": "", "comments": [],
             "url": f"{cfg['url']}/browse/{x['k']}", "note": f"Jira сейчас недоступна ({e}) — показано из учёта"}
    if x:
        now = int(time.time())
        r["history"] = [{"at": fmt_dt(e[0]), "who": e[1], "to": e[2], "cat": e[3]} for e in x["ev"]]
        r["cat"] = x["c"]
        r["started"] = fmt_d(x["go"]) if x["go"] else ""
        r["done"] = fmt_d(x["dn"]) if x["dn"] else ""
        r["done_by"] = x.get("by") or ""
        r["age"] = dur((x["dn"] or now) - (x["go"] or x["cr"])) if x["go"] or x["cr"] else ""
    return r


def check():
    cfg = settings()
    me = get(cfg, "/rest/api/2/myself")
    try:
        info = get(cfg, "/rest/api/2/serverInfo")
    except JiraError:
        info = {}
    return {"ok": True, "me": person(me), "server": str(info.get("serverTitle") or ""), "version": str(info.get("version") or ""),
            "type": "облако" if str(info.get("deploymentType") or "").lower() == "cloud" else "свой сервер"}


# ---------- MCP ----------
RO = {"readOnlyHint": True}
TOOLS = [
    {"name": "jira", "annotations": dict(RO, title="Jira команды"),
     "description": "Jira команды (только чтение). what: overview — сводка (в работе, сделано и создано за период, ошибки, "
                    "время цикла, дольше всего в работе); people — кто сколько сделал; person — что делал человек (q — имя); "
                    "stuck — застряло (в работе без движения); changes — что изменилось за сутки; mine — мои задачи; "
                    "find — найти задачи (q — слова или номер); issue — одна задача подробно (q — номер, например AI-177); "
                    "away — кто в отпуске, на больничном, отсутствует сейчас и в ближайшие две недели.",
     "inputSchema": {"type": "object", "properties": {
         "what": {"type": "string", "enum": ["overview", "people", "person", "stuck", "changes", "mine", "find", "issue", "away"]},
         "q": {"type": "string", "description": "имя человека, слова или номер задачи"},
         "days": {"type": "integer", "description": "за сколько дней (по умолчанию 30; для person — 7)"},
         "project": {"type": "string", "description": "ключ проекта, пусто — все"}}, "required": ["what"]}},
    {"name": "jira_page", "annotations": dict(RO, title="Страница"), "_meta": {"dewiar/page": True},
     "inputSchema": {"type": "object", "properties": {"days": {"type": "integer"}, "project": {"type": "string"}, "person": {"type": "string"}}}},
    {"name": "jira_sync", "annotations": dict(RO, title="Загрузить из Jira"), "_meta": {"dewiar/page": True},
     "inputSchema": {"type": "object", "properties": {"full": {"type": "boolean"}}}},
    {"name": "jira_task", "annotations": dict(RO, title="Задача"), "_meta": {"dewiar/page": True},
     "inputSchema": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}},
    {"name": "jira_check", "annotations": dict(RO, title="Проверить связь"), "_meta": {"dewiar/page": True},
     "inputSchema": {"type": "object", "properties": {}}},
]


def call(name, a):
    try:
        if name == "jira":
            return ask(a)
        if name == "jira_page":
            return page(a)
        if name == "jira_sync":
            return sync(bool(a.get("full")), budget=35)
        if name == "jira_task":
            return task(a.get("key"))
        if name == "jira_check":
            return check()
    except JiraError as e:
        raise ValueError(str(e)) from None
    raise ValueError("нет такого действия")


def handle(msg):
    m, i = msg.get("method"), msg.get("id")
    if i is None:
        return None
    if m == "initialize":
        return {"jsonrpc": "2.0", "id": i, "result": {"protocolVersion": (msg.get("params") or {}).get("protocolVersion", "2024-11-05"),
                                                       "capabilities": {"tools": {}}, "serverInfo": {"name": "dewiar-jira", "version": "1.0"}}}
    if m == "tools/list":
        return {"jsonrpc": "2.0", "id": i, "result": {"tools": TOOLS}}
    if m == "tools/call":
        p = msg.get("params") or {}
        try:
            res = call(p.get("name"), p.get("arguments") or {})
            return {"jsonrpc": "2.0", "id": i, "result": {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}]}}
        except Exception as e:  # noqa: BLE001
            return {"jsonrpc": "2.0", "id": i, "result": {"isError": True, "content": [{"type": "text", "text": f"Ошибка: {e}"}]}}
    if m == "ping":
        return {"jsonrpc": "2.0", "id": i, "result": {}}
    return {"jsonrpc": "2.0", "id": i, "error": {"code": -32601, "message": "нет такого метода"}}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            r = handle(json.loads(line))
        except ValueError:
            continue
        if r is not None:
            sys.stdout.write(json.dumps(r, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
