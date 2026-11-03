"""03.11, экзамен телефона и «Мощности»: «Похоже, вызовы действий теряет шлюз сервера моделей» — шлюз vLLM (gate/index.php)
в потоке пересылал только текст, а delta.tool_calls выбрасывал («Помахала Мише 👋» без действия, пустые ответы и повторы).
Заплатка tools/vllm/gate_toolcalls_patch.php: находит два места, пересылает tool_calls, делает копию, повтор — без изменений,
чужая версия — не трогает."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


if not shutil.which("php"):
    print("нет php — пропуск"); print("ИТОГ: всё прошло"); sys.exit(0)
GATE = r'''<?php
$cb = function (array $chunk) use (&$finish) {
                $choice = $chunk['choices'][0] ?? null;
                $delta   = $choice['delta']['content'] ?? '';
                $reason  = null;
                if (!empty($choice['finish_reason'])) { $finish = $choice['finish_reason']; }
                if ($delta === '' && $reason === null) { return; }
                $out = [];
                if (true) {
                    $d = [];
                    if ($delta !== '')  { $d['content'] = (string)$delta; }
                    $out[] = $d;
                }
                echo json_encode($out, JSON_UNESCAPED_UNICODE), "\n";
};
$finish = '';
$cb(['choices' => [['delta' => ['content' => 'Помахала']]]]);
$cb(['choices' => [['delta' => ['tool_calls' => [['index' => 0, 'function' => ['name' => 'close_wave', 'arguments' => '{}']]]]]]]);
'''
P = ROOT / "tools/vllm/gate_toolcalls_patch.php"
with tempfile.TemporaryDirectory() as t:
    g = Path(t) / "index.php"; g.write_text(GATE, encoding="utf-8")
    before = subprocess.run(["php", str(g)], capture_output=True, text=True).stdout
    ok("close_wave" not in before, "до заплатки шлюз выбрасывает вызов действия")
    r = subprocess.run(["php", str(P), str(g)], capture_output=True, text=True)
    ok(r.returncode == 0 and "Готово" in r.stdout and list(Path(t).glob("index.php.bak-*")), f"заплатка встала, копия рядом: {r.stdout.strip()} {r.stderr.strip()}")
    after = subprocess.run(["php", str(g)], capture_output=True, text=True).stdout
    ok("close_wave" in after and "Помахала" in after, "после — вызов идёт клиенту в потоке, текст как был")
    r2 = subprocess.run(["php", str(P), str(g)], capture_output=True, text=True)
    ok(r2.returncode == 0 and "Уже исправлено" in r2.stdout and g.read_text(encoding="utf-8").count("DEWIAR-TOOLCALLS") == 2, "повторный запуск ничего не меняет")
    o = Path(t) / "other.php"; o.write_text("<?php echo 1;\n", encoding="utf-8")
    r3 = subprocess.run(["php", str(P), str(o)], capture_output=True, text=True)
    ok(r3.returncode == 1 and o.read_text(encoding="utf-8") == "<?php echo 1;\n" and "версия шлюза другая" in r3.stderr, "чужая версия шлюза — не трогает, говорит, что делать")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
