"""«Сеть Лиры» в программе (шаг 1, 04.11): правила сети с подписью, «Мой узел», «Поделиться мощностью» и переключатель
«Пускать мои общие вопросы в Сеть Лиры». Серверная часть — server/dwrapp/liranet.php, агент узла — server/dwrapp/lira-node.py.

Правила сети подписывает только владелец Dewiar (ключ Ed25519 лежит на сайте). Программа берёт /net/rules и проверяет
подпись сама — здесь, на чистом Python (RFC 8032, только проверка). Открытый ключ сети: «доверие при первом
использовании» — запоминается в настройках (cloud.net_pub) при первом получении, его отпечаток человек видит в студии и
может сверить с кабинетом владельца или с объявлением Dewiar; потом правила с другим ключом не принимаются («ключ сети
сменился» — принять новый можно только кнопкой). Почему не вшит в программу: ключ создаётся на сайте при первом сохранении
пульта, до выпуска его нет. Когда владелец его опубликует — его отпечаток кладётся в PINNED_FP, и он главнее запомненного.

Переключатель — cloud.net_share (по умолчанию выключено) и флаг net у профиля модели dewiar-cloud: llm._headers
добавляет заголовок X-Dewiar-Net: 1 только к запросам в облако Dewiar и только к основному ходу разговора (флаг _net_turn
ставит engine_answer._run_turn; не в детском режиме и не «Для старших»). Без заголовка сайт на узлы ничего не отправит.
Узлу уходит только текст самого вопроса — без истории, личной справки и справки к вопросу (liranet.php net_clean)."""
import base64
import hashlib
import json
import logging
import threading
import time

log = logging.getLogger("dewiar.liranet")
PINNED_FP = ""          # отпечаток ключа сети «7F3A-91C2-…», когда владелец его опубликует (пусто — доверие при первом использовании)


class NetError(Exception):
    pass


# ---------------------------------------------- Ed25519: только проверка (RFC 8032) ----------------------------------------------
_P = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _P - 2, _P) % _P
_I = pow(2, (_P - 1) // 4, _P)


def _xrec(y, sign):
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P:
        x = x * _I % _P
    if (x * x - x2) % _P:
        return None
    return _P - x if (x & 1) != sign else x


def _add(a, b):
    A = (a[1] - a[0]) * (b[1] - b[0]) % _P
    B = (a[1] + a[0]) * (b[1] + b[0]) % _P
    C = 2 * a[3] * b[3] * _D % _P
    D = 2 * a[2] * b[2] % _P
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % _P, G * H % _P, F * G % _P, E * H % _P)


def _mul(s, pt):
    q = (0, 1, 1, 0)
    while s:
        if s & 1:
            q = _add(q, pt)
        pt = _add(pt, pt)
        s >>= 1
    return q


def _dec(b):
    y = int.from_bytes(b, "little")
    sign, y = y >> 255, y & ((1 << 255) - 1)
    if y >= _P:
        return None
    x = _xrec(y, sign)
    return None if x is None else (x, y, 1, x * y % _P)


_GY = 4 * pow(5, _P - 2, _P) % _P
_GX = _xrec(_GY, 0)
_G = (_GX, _GY, 1, _GX * _GY % _P)


def ed25519_verify(pub: bytes, msg: bytes, sig: bytes) -> bool:
    if len(pub) != 32 or len(sig) != 64:
        return False
    a, r = _dec(pub), _dec(sig[:32])
    s = int.from_bytes(sig[32:], "little")
    if a is None or r is None or s >= _L:
        return False
    h = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), "little") % _L
    x, y = _mul(s, _G), _add(r, _mul(h, a))
    return (x[0] * y[2] - y[0] * x[2]) % _P == 0 and (x[1] * y[2] - y[1] * x[2]) % _P == 0


def fingerprint(pub: bytes) -> str:
    h = hashlib.sha256(pub).hexdigest()[:16].upper()
    return "-".join(h[i:i + 4] for i in range(0, 16, 4))


def check(d: dict, pinned_b64: str = "", pinned_fp: str = PINNED_FP) -> dict:
    """Ответ /net/rules -> {rules, pub (base64), fp, new: впервые}; подпись неверна, ключ не тот, срок вышел — NetError."""
    if not isinstance(d, dict) or not d.get("ok"):
        raise NetError((d or {}).get("error") or "сайт не дал правила сети")
    try:
        pub = base64.b64decode(d.get("pub") or "")
        sig = base64.b64decode(d.get("sig") or "")
    except ValueError as e:
        raise NetError("правила сети пришли испорченными") from e
    fp = fingerprint(pub)
    if pinned_fp and fp.replace("-", "") != pinned_fp.replace("-", "").upper():
        raise NetError("правила подписаны не ключом Dewiar (отпечаток не совпал) — не принимаю")
    if pinned_b64 and pinned_b64 != base64.b64encode(pub).decode():
        raise NetError(f"ключ сети сменился (новый отпечаток {fp}) — правила не приняты. Если владелец Dewiar объявил о новом ключе, нажмите «Доверять новому ключу»")
    txt = d.get("rules") or ""
    if not ed25519_verify(pub, txt.encode(), sig):
        raise NetError("подпись правил сети неверна — не принимаю")
    r = json.loads(txt)
    if r.get("net") != "lira":
        raise NetError("это не правила Сети Лиры")
    if int(r.get("expires") or 0) < time.time():
        raise NetError("правила сети просрочены — сайт давно их не продлевал")
    return {"rules": r, "pub": base64.b64encode(pub).decode(), "fp": fp, "new": not pinned_b64}


# ------------------------------------------------------- команды студии -------------------------------------------------------
def _share_set(engine, on: bool):
    """Переключатель и флаг у профиля облака (по нему llm._headers добавит X-Dewiar-Net: 1)."""
    profiles = dict(engine.s.get("llm", "profiles") or {})
    if "dewiar-cloud" in profiles:
        profiles["dewiar-cloud"] = dict(profiles["dewiar-cloud"], net=bool(on))
    engine.s.update({"cloud": {"net_share": bool(on)}, "llm": {"profiles": profiles}})
    engine.emit("settings", settings=engine.s.snapshot())


def rules(engine, trust_new=False):
    """Правила сети с проверенной подписью -> dict для студии (ошибка — в поле error, не исключением)."""
    from cloud import public, CloudError
    url = engine.cloud.url
    try:
        d = public(url, "/net/rules", timeout=15)
    except CloudError as e:
        return {"ok": False, "error": str(e)}
    pinned = "" if trust_new else (engine.s.get("cloud", "net_pub") or "")
    try:
        r = check(d, pinned)
    except NetError as e:
        return {"ok": False, "error": str(e), "fp": fingerprint(base64.b64decode(d.get("pub") or "")) if d.get("pub") else ""}
    if r["new"] or trust_new:
        engine.s.update({"cloud": {"net_pub": r["pub"]}})
        log.info("🌐 Сеть Лиры: доверяю ключу сети %s", r["fp"])
    return {"ok": True, "fp": r["fp"], "rules": r["rules"], "first": r["new"]}


_rules_cache = {"at": 0.0, "ok": False, "busy": False}


def rules_ok(engine):
    """Действующие правила сети проверены подписью и сеть включена — только тогда программа ставит X-Dewiar-Net (рецензия
    04.11, третья). Не ждёт сети: раз в час проверяет в фоне, до первой проверки — нет."""
    c, now = _rules_cache, time.time()
    if now - c["at"] > 3600 and not c["busy"]:
        c["busy"] = True

        def run():
            try:
                r = rules(engine)
                d = r.get("rules") or {}
                c["ok"] = bool(r.get("ok") and d.get("on") and int(d.get("expires") or 0) > time.time())
            except Exception:  # noqa: BLE001
                c["ok"] = False
            finally:
                c["at"], c["busy"] = time.time(), False
        threading.Thread(target=run, name="lnet-rules", daemon=True).start()
    return bool(c["ok"])


def command(engine, cmd, a):
    from cloud import fetch, CloudError
    c = engine.cloud
    if cmd == "lnet_share":
        _share_set(engine, bool(a.get("on")))
        return {"share": bool(engine.s.get("cloud", "net_share"))}
    if cmd == "lnet_info":
        out = {"share": bool(engine.s.get("cloud", "net_share")), "connected": bool(c.key)}
        out["signed"] = rules(engine, trust_new=bool(a.get("trust_new")))
        if c.key:
            try:
                out["me"] = fetch(c.url, c.key, "/net/me")
            except CloudError as e:
                out["me"] = {"ok": False, "error": str(e)}
        return out
    if not c.key:
        raise NetError("сначала подключите Dewiar.pro: аккаунт или ключ")
    try:
        if cmd == "lnet_invite":
            return fetch(c.url, c.key, "/net/invite", timeout=20, body={})
        if cmd == "lnet_pause":
            return fetch(c.url, c.key, "/net/pause", timeout=20, body={"on": bool(a.get("on"))})
    except CloudError as e:
        raise NetError(str(e)) from e
    raise NetError("нет такой команды: " + cmd)
