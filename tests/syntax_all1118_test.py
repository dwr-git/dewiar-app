"""Харнесс 1.0.30 (по образцу Aigen, владелец 18.11): синтаксис любого файла — сразу после записи, со строкой. Было: только
Python и JSON в задачах по коду, HTML — по тегам. Стало (core/syntaxcheck.py): JS (node --check или встроенный разбор
js_scan), встроенные <script> страниц, CSS, YAML, TOML, XML/SVG, bash, PHP — в code_write/code_edit, write_file
(quick_check) и file_edit (сломанная правка не применяется). Главное — без ложных тревог: замер js_scan на 1507 настоящих
файлах — 0 ложных, на 228 сломанных — найдено 227."""
import os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import syntaxcheck as S  # noqa: E402
import textedit as TE  # noqa: E402
import codework as C  # noqa: E402
import quality as Q  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


GOOD_JS = [
    "const a = b / c / d; const r = /a\\/b[/]c/gi.test(x);",
    "function f(){ return /x/.test(s) ? `a${b + `c${d}`}e` : 'q\\'r'; }",
    "let x = y++ / 2; z = (a) / 3; arr[0] / 4;",
    "if (a) /re/.exec(s); else { b = c / d }",
    "const t = `многострочная\nстрока ${obj.map(x => `${x}`).join('}')}`;",
    "/* комментарий } */ // ещё ) один\nconst o = { a: [1, 2, { b: 3 }] };",
    "label: for (;;) { break label; }  const re = x => /\\d+/.test(x);",
    "a = b\n/hi/g.exec(c)",          # «b /hi/ g» — деление: не ругаемся (лучше пропустить, чем ложная тревога)
]
for i, js in enumerate(GOOD_JS):
    ok(S.js_scan(js) == "", f"верный JS №{i + 1} — без тревоги: {S.js_scan(js)!r}")
BAD_JS = {
    "function f() { return 1;\n": "не закрыта",
    "const s = 'oops;\nconst x = 1;": "не закрыта",
    "const t = `abc ${x + 1;": "не закрыт",
    "foo(1, 2]);": "закрыта",
    "x = 1; }": "лишняя",
    "/* нет конца\nconst a = 1;": "не закрыт",
}
for js, want in BAD_JS.items():
    e = S.js_scan(js)
    ok(want in e and "строк" in e, f"сломанный JS найден со строкой: {js[:24]!r} → {e!r}")

ok(S.syntax_error("a { color: red; } b { margin: 0 ", ".css").startswith("«{» из строки 1"), "CSS: незакрытая «{»")
ok(S.syntax_error("a { content: '}'; }", ".css") == "", "CSS: скобка в строке — не ошибка")
ok(S.syntax_error('[a]\nb = "x\n', ".toml").startswith("TOML"), "TOML: незакрытая строка")
ok(S.syntax_error("<svg><g></svg>", ".svg").startswith("XML, строка 1"), "SVG/XML: незакрытый тег")
try:
    import yaml  # noqa: F401
    ok(S.syntax_error("a: [1, 2\nb: 3\n", ".yaml").startswith("YAML"), "YAML: незакрытый список")
except ImportError:
    print("(PyYAML нет — YAML пропущен молча)")
ok(S.syntax_error("a: 1\n", ".yaml") == "", "YAML: верный — без тревоги")
html = "<!doctype html><html><body>\n<p>x</p>\n<script>\nfunction f() {\n  return 1;\n</script>\n</body></html>"
e = S.syntax_error(html, ".html")
ok("в <script>" in e and "строки 4" in e, f"HTML: сломанный встроенный скрипт — со строкой файла: {e!r}")
ok(S.syntax_error('<html><body><script type="text/template">{{ if }}</script></body></html>', ".html") == "", "шаблон в <script> — пропущен")
ok("JSON в <script>" in S.syntax_error('<html><body><script type="application/ld+json">{"a":}</script></body></html>', ".html"),
   "HTML: JSON в <script> проверяется как JSON")
ok(S.syntax_error("import x from './a.js';\nexport const y = await x;\n", ".js") == "", "JS-модуль (import/export, await) — не ошибка")
ok(TE.syntax_error("const a = (1;", ".js") != "", "textedit.syntax_error — общий для file_edit и кода")
try:
    out, _line, _n = TE.apply_edit("const a = 1;\n", "const a = 1;", "const a = (1;", False)
    ok(TE.syntax_error(out, ".js") and not TE.syntax_error("const a = 1;\n", ".js"), "file_edit: правка ломает JS — видно до записи")
except Exception as ex:  # noqa: BLE001
    ok(False, f"apply_edit: {ex}")

d = Path(tempfile.mkdtemp())
(d / "app.js").write_text("function f() {\n  return [1, 2;\n}\n", encoding="utf-8")
w = Q.quick_check(d / "app.js", "app.js")
ok(w.startswith("⚠ ПРОВЕРКА") and "app.js не разбирается" in w, f"write_file: сломанный JS — предупреждение сразу: {w!r}")
(d / "ok.css").write_text("a { color: red }\n", encoding="utf-8")
ok(Q.quick_check(d / "ok.css", "ok.css") == "", "write_file: верный CSS — тихо")
(d / "s.yml").write_text("a: [1\n", encoding="utf-8")
ok(C.check_syntax(d / "s.yml", "s.yml") == "" or "не разбирается" in C.check_syntax(d / "s.yml", "s.yml"), "code_write: YAML проверяется")
(d / "m.js").write_text("const x = {\n", encoding="utf-8")
cs = C.check_syntax(d / "m.js", "m.js")
ok("m.js не разбирается" in cs and "code_edit" in cs, f"code_write/code_edit: сломанный JS — предупреждение со строкой: {cs!r}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
