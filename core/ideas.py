"""«Идеи Лиры» в программе (0.59): что сделать дальше — решаем вместе. Студия и виджет ходят сюда, отсюда — на сайт
(cloud.php ?p=/ideas…). Голос — с устройства: X-Dewiar-Dev — номер этого компьютера в синхронизации (сайт хранит только
отпечаток). Стоп-кран «Ничего не уходит в интернет» — не ходим."""
import httpx

from cloud import base_of


class IdeasError(Exception):
    pass


def call(url, dev, path, params=None, body=None, timeout=15):
    import egress
    if egress.local_only():
        raise IdeasError("включён режим «Ничего не уходит в интернет» — идеи живут на сайте Dewiar")
    p = {"p": path, **{k: v for k, v in (params or {}).items() if v not in (None, "")}}
    h = {"X-Dewiar-Dev": dev}
    try:
        r = (httpx.post(base_of(url), params=p, json=body or {}, headers=h, timeout=timeout) if body is not None
             else httpx.get(base_of(url), params=p, headers=h, timeout=timeout))
    except httpx.HTTPError as e:
        raise IdeasError(f"сайт Dewiar не ответил: {e}") from e
    try:
        d = r.json()
    except ValueError:
        d = {}
    if r.status_code >= 400:
        raise IdeasError(((d.get("error") or {}).get("message")) or f"сайт ответил {r.status_code}")
    return d


def suggest(eng, title, text=""):
    """«Предложи идею: …» (голосом, 0.61): похожая уже есть — голос за неё; нет — новая, «на рассмотрении». -> фраза для модели."""
    url = eng.s.get("cloud", "url") or ""
    dev = eng.sync.state.get("device", "") if getattr(eng, "sync", None) else ""
    title = " ".join(str(title or "").split())[:120]
    if len(title) < 4:
        raise IdeasError("скажите идею хотя бы в несколько слов")
    sim = [x for x in (call(url, dev, "/ideas/similar", {"q": title}).get("items") or []) if x.get("status") in ("plan", "doing", "new", "done")]
    if sim:
        x = sim[0]
        if x["status"] == "done":
            return f"Это уже сделано в версии {x.get('ver') or 'новее вашей'}: «{x['title']}». Скажи об этом и предложи обновиться."
        if not x.get("voted"):
            x = dict(x, **call(url, dev, "/ideas/vote", body={"id": x["id"], "on": True}))
        return (f"Похожая идея уже есть: «{x['title']}» — голос за неё отдан (теперь голосов: {x.get('votes')}). Скажи коротко: "
                "такую уже предлагали, проголосовала — чем больше голосов, тем раньше её сделают; все идеи — в «Идеях Лиры».")
    d = call(url, dev, "/ideas/new", body={"title": title, "text": str(text or "")[:2000], "who": eng.s.get("user_name") or "", "app": "pc"})
    return (f"Идея «{d['item']['title']}» отправлена разработчику — она на рассмотрении. Скажи коротко, что предложила; когда её "
            "возьмут в план, за неё смогут голосовать все — видно в «Идеях Лиры».")


def command(eng, cmd, a):
    url = eng.s.get("cloud", "url") or ""
    dev = eng.sync.state.get("device", "") if getattr(eng, "sync", None) else ""
    try:
        if cmd == "ideas_list":
            return call(url, dev, "/ideas", {"tab": a.get("tab") or "plan", "q": a.get("q") or "", "page": int(a.get("page") or 1)})
        if cmd == "ideas_similar":
            return call(url, dev, "/ideas/similar", {"q": a.get("q") or ""})
        if cmd == "ideas_vote":
            return call(url, dev, "/ideas/vote", body={"id": int(a.get("id") or 0), "on": bool(a.get("on"))})
        if cmd == "ideas_new":
            who = (eng.s.get("ui", "who") or "") if hasattr(eng, "s") else ""
            return call(url, dev, "/ideas/new", body={"title": str(a.get("title") or ""), "text": str(a.get("text") or ""),
                                                       "who": str(a.get("who") or who)[:40], "app": "pc"})
    except IdeasError as e:
        raise ValueError(str(e)) from e
    raise ValueError("неизвестная команда " + cmd)
