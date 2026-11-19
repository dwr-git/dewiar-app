"""Основа русского слова — алгоритм Snowball (Портер) для русского, без зависимостей. Нужен поиску по документам
(knowledge.py): «Анны» и «Анна», «кучера» и «кучер», «подарил» и «подарок» должны находиться друг по другу. Прежнее
отрезание одного окончания не трогало слова до 4 букв и путало формы (замер 19.11 на 12 книгах: нужный отрывок — в 16
из 36 вопросов). Описание алгоритма: snowballstem.org/algorithms/russian/stemmer.html."""

_V = set("аеиоуыэюя")


def _ends(groups):
    return [tuple(sorted(g, key=len, reverse=True)) for g in groups]


PERF1, PERF2 = _ends([("в", "вши", "вшись"), ("ив", "ивши", "ившись", "ыв", "ывши", "ывшись")])
REFL = ("ся", "сь")
ADJ = tuple(sorted(("ее", "ие", "ые", "ое", "ими", "ыми", "ей", "ий", "ый", "ой", "ем", "им", "ым", "ом", "его", "ого",
                    "ему", "ому", "их", "ых", "ую", "юю", "ая", "яя", "ою", "ею"), key=len, reverse=True))
PART1, PART2 = _ends([("ем", "нн", "вш", "ющ", "щ"), ("ивш", "ывш", "ующ")])
VERB1, VERB2 = _ends([("ла", "на", "ете", "йте", "ли", "й", "л", "ем", "н", "ло", "но", "ет", "ют", "ны", "ть", "ешь", "нно"),
                      ("ила", "ыла", "ена", "ейте", "уйте", "ите", "или", "ыли", "ей", "уй", "ил", "ыл", "им", "ым", "ен",
                       "ило", "ыло", "ено", "ят", "ует", "уют", "ит", "ыт", "ены", "ить", "ыть", "ишь", "ую", "ю")])
NOUN = tuple(sorted(("а", "ев", "ов", "ие", "ье", "е", "иями", "ями", "ами", "еи", "ии", "и", "ией", "ей", "ой", "ий", "й",
                     "иям", "ям", "ием", "ем", "ам", "ом", "о", "у", "ах", "иях", "ях", "ы", "ь", "ию", "ью", "ю", "ия",
                     "ья", "я"), key=len, reverse=True))
DERIV = ("ость", "ост")
SUPER = ("ейше", "ейш")


def _regions(w):
    """-> (rv, r2): индексы начала областей RV и R2."""
    n = len(w)
    rv = next((i + 1 for i, c in enumerate(w) if c in _V), n)
    r1 = next((i + 1 for i in range(1, n) if w[i] not in _V and w[i - 1] in _V), n)
    r2 = next((i + 1 for i in range(r1 + 1, n) if w[i] not in _V and w[i - 1] in _V), n)
    return rv, r2


def _cut(w, start, ends, after_ay=False):
    """Самое длинное окончание из ends, целиком в области [start:]; after_ay — перед ним «а» или «я» (тоже в области).
    -> слово без окончания или None."""
    for e in ends:
        if w.endswith(e) and len(w) - len(e) >= start:
            if after_ay:
                k = len(w) - len(e) - 1
                if k < start or w[k] not in "ая":
                    continue
            return w[:len(w) - len(e)]
    return None


def stem(word):
    w = word.lower().replace("ё", "е")
    if not w or not ("а" <= w[0] <= "я"):
        return w
    rv, r2 = _regions(w)
    # шаг 1
    x = _cut(w, rv, PERF1, True) or _cut(w, rv, PERF2)
    if x is not None:
        w = x
    else:
        w = _cut(w, rv, REFL) or w
        x = _cut(w, rv, ADJ)
        if x is not None:
            w = _cut(x, rv, PART1, True) or _cut(x, rv, PART2) or x
        else:
            x = _cut(w, rv, VERB1, True) or _cut(w, rv, VERB2)
            if x is not None:
                w = x
            else:
                w = _cut(w, rv, NOUN) or w
    # шаг 2
    if w.endswith("и") and len(w) - 1 >= rv:
        w = w[:-1]
    # шаг 3
    w = _cut(w, r2, DERIV) or w
    # шаг 4
    x = _cut(w, rv, SUPER)
    if x is not None:
        w = x
    if w.endswith("нн") and len(w) - 2 >= rv:
        w = w[:-1]
    elif w.endswith("ь") and len(w) - 1 >= rv:
        w = w[:-1]
    return w
