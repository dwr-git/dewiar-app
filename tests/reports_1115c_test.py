"""Отчёты людей 15.11 (третья пачка):
№739 (Windows, памяти почти нет): «Устройства» → «Телефон дома по Wi-Fi» — вместо кода пустой белый квадрат. Ссылка с
     четырьмя адресами (Hyper-V, WSL) — ~2000 точек, каждая отдельным <rect> (116 КБ разметки). Теперь точки — одним путём
     (в 2+ раза меньше, один элемент), а не нарисовался код — честная строка вместо пустого квадрата.
№741: «Свой сервис» с адресом «192.168.1.106:5000/v1» (OmniRoute) записывался как https://… — свой сервер в сети без
     сертификата «не отвечает». Адрес домашней сети без схемы — http://; https:// к открытому порту в сети — подсказка
     «впишите с http://»."""
import json, os, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# №739: QR — одним путём, данные те же, отказ — строкой
js = r"""
const fs = require('fs'), R = process.argv[2];
eval(fs.readFileSync(R + '/ui/assets/qrcode.js', 'utf8') + ';global.qrcode = qrcode;');
const day = fs.readFileSync(R + '/ui/studio/day.js', 'utf8');
eval(day.slice(day.indexOf('function qrPretty'), day.indexOf('/* Первый код')) + ';global.qrPretty = qrPretty; global.qrSvg = qrSvg;');
const us = ['192.168.1.101', '172.25.208.1', '192.168.128.1', '172.21.240.1'].map(i => `http://${i}:8766/`).join(',');
const link = `dewiar://home?u=${encodeURIComponent(us)}&t=abcdef0123456789&k=${'A'.repeat(44)}&h=0123456789abcdef&n=Serg`;
const svg = qrSvg(link);
const q = qrcode(0, 'M'); q.addData(link); q.make();
const n = q.getModuleCount(); let dark = 0;
const eye = (r, c) => (r < 7 && c < 7) || (r < 7 && c >= n - 7) || (r >= n - 7 && c < 7);
for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (q.isDark(r, c) && !eye(r, c)) dark++;
const gone = qrSvg('x'.repeat(5000));     // не влезает в код — библиотека бросает ошибку
console.log(JSON.stringify({len: svg.length, rects: (svg.match(/<rect/g) || []).length, paths: (svg.match(/<path/g) || []).length,
  dots: (svg.match(/M[\d.]+ [\d.]+h\.56v\.56h-\.56z/g) || []).length, dark, gone}));
"""
f = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8")
f.write(js)
f.close()
r = subprocess.run(["node", f.name, str(ROOT)], capture_output=True, text=True)
d = json.loads(r.stdout or "{}") if r.returncode == 0 else {}
ok(d.get("paths") == 1 and d.get("rects", 99) <= 7 and d.get("dots") == d.get("dark") and d.get("dark", 0) > 1500,
   f"код домашнего Wi-Fi: все {d.get('dark')} точек — одним путём, элементов {d.get('rects')} + 1 ({r.stderr[-200:]})")
ok(0 < d.get("len", 10**6) < 60_000, f"разметка кода — {d.get('len')} знаков (было ~116 тыс.)")
ok("Код не нарисовался" in d.get("gone", "") and "<svg" not in d.get("gone", ""), "код не нарисовался — честная строка, а не пустой квадрат")
css = (ROOT / "ui/studio/studio.css").read_text(encoding="utf-8")
ok(".qr-fail" in css, "у строки отказа свой стиль")

# №741: адрес своего сервиса
js2 = r"""
const fs = require('fs'), R = process.argv[2];
const src = fs.readFileSync(R + '/ui/studio/connect.js', 'utf8');
eval(src.slice(src.indexOf('function ckUrl'), src.indexOf('function ckPreset')) + ';global.ckUrl = ckUrl;');
console.log(JSON.stringify(['192.168.1.106:5000/v1', '10.0.0.5:8000/v1/', 'localhost:4000/v1', 'omni:5000/v1', 'nas.local:5000/v1',
  '172.20.1.2:5000/v1/chat/completions', 'api.example.com/v1', 'http://192.168.1.106:5000/v1', 'https://my.ru/v1', '172.40.1.1/v1'].map(ckUrl)));
"""
f2 = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8")
f2.write(js2)
f2.close()
r = subprocess.run(["node", f2.name, str(ROOT)], capture_output=True, text=True)
u = json.loads(r.stdout or "[]") or [""] * 10
ok(u[:6] == ["http://192.168.1.106:5000/v1", "http://10.0.0.5:8000/v1", "http://localhost:4000/v1", "http://omni:5000/v1",
             "http://nas.local:5000/v1", "http://172.20.1.2:5000/v1"], f"адрес домашней сети без схемы — http:// ({u[:6]})")
ok(u[6:] == ["https://api.example.com/v1", "http://192.168.1.106:5000/v1", "https://my.ru/v1", "https://172.40.1.1/v1"],
   f"сервисы в интернете — https://, вписанная схема — как есть ({u[6:]})")

import llm  # noqa: E402
real = llm._port_open
try:
    llm._port_open = lambda h, p, timeout=0.35: True
    h = llm.connect_hint("https://192.168.1.106:5000/v1")
    ok("http://192.168.1.106:5000/v1" in h and "без https" in h, f"https:// к открытому порту в сети — «впишите с http://» ({h[:90]})")
    llm._port_open = lambda h, p, timeout=0.35: False
    ok("не отвечает на порту 5000" in llm.connect_hint("https://192.168.1.106:5000/v1"), "порт закрыт — прежняя подсказка")
    ok("не отвечает на порту" in llm.connect_hint("http://192.168.1.106:5000/v1"), "http:// — прежняя подсказка")
finally:
    llm._port_open = real
# радио (из журналов №739 и №741: «молчат: Русское Радио, Маруся ФМ, NRJ, Relax FM…» — у станций сменились адреса):
# станция списка молчит — та же станция по новому адресу из каталога, а не сразу другая; удачный адрес запоминается
import radio as RD  # noqa: E402
import engine_music as EM  # noqa: E402
H = RD.StationHealth(Path(tempfile.mkdtemp()) / "h.json")
old = "https://pub0101.101.ru:8000/stream/air/aac/64/100"
H.mark(old, False, "не отвечает")
calls = []


def fake_search(q, limit=8, as_tag=False):
    calls.append(q)
    return [{"name": "Русское Радио Хиты 90-х", "url": "https://x/hits"}, {"name": "Русское Радио", "url": "https://new/rr"},
            {"name": "Русское радио (Москва)", "url": "https://new/msk"}, {"name": "Другое", "url": "https://y"}]


real_search = RD.search
RD.search = fake_search
try:
    E = type("E", (), {"radio_health": H})()
    got = EM.MusicMixin._station_renew(E, {"name": "Русское Радио", "url": old, "tags": "русское поп"})
    ok([x["url"] for x in got][0] == "https://new/rr" and len(got) == 3,
       f"молчит — та же станция из каталога по новому адресу ({[x['url'] for x in got]})")
    ok(all(x["name"] == "Русское Радио" and x["_cat"] for x in got) and "https://y" not in [x["url"] for x in got],
       "название прежнее, чужие станции не подставляются")
    H.alias(old, "https://new/rr")
    ok(H.alias(old) == "https://new/rr" and EM.MusicMixin._station_renew(E, {"name": "Русское Радио", "url": old})[0]["url"] == "https://new/rr",
       "удачный новый адрес запоминается и идёт первым")
    ok(not H.dead("alias:" + old) and RD.StationHealth(H.path).alias(old) == "https://new/rr", "память переживает перезапуск")
finally:
    RD.search = real_search
em = (ROOT / "core/engine_music.py").read_text(encoding="utf-8")
ok("fresh = self._station_renew(renew)" in em and "first = renew or cands[0]" in em, "в проигрывании: сначала та же станция, потом другая")
# владелец 15.11 (Ubuntu): ссылка «растёт тренд» из виджета открыла «Радар» — «Пульс» пустой, пока не переключишь вкладку.
# Студия открылась на «Радаре» раньше связи с ядром: load() выходил молча. Связь появилась — грузим открытое.
ins = (ROOT / "ui/studio/insight.js").read_text(encoding="utf-8")
ok('core.on("hello", () => { if (q("#p-insight").classList.contains("cur")) load(); });' in ins and "if (!core.connected) return;" in ins,
   "«Радар», открытый до связи с ядром, загружается, как только связь есть")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
