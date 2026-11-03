<?php
/**
 * Dewiar — заплатка шлюза vLLM (gate/index.php): вызовы действий (tool_calls) в потоке.
 *
 * Что чинит. Шлюз в потоковом ответе /v1/chat/completions пересылал только текст (delta.content) и рассуждения,
 * а куски с delta.tool_calls выбрасывал. Модель «вызывала» действие (finish_reason tool_calls), а до сайта доходил
 * только текст: «Помахала Мише 👋» — а действия нет; или пустой ответ, и сайт переспрашивал модель целиком (вдвое
 * дольше). В кабинете это видно в «Мощностях»: «Похоже, вызовы действий теряет шлюз сервера моделей».
 *
 * Как поставить (на сервере моделей):
 *   php gate_toolcalls_patch.php /путь/к/src/vllm/gate/index.php
 * Рядом сохранится копия index.php.bak-ГГГГММДД-ЧЧММСС. Повторный запуск ничего не меняет. Перезапуск не нужен.
 */
declare(strict_types=1);
$f = $argv[1] ?? '';
if ($f === '' || !is_file($f)) {
    fwrite(STDERR, "Укажите путь к gate/index.php: php gate_toolcalls_patch.php /…/vllm/gate/index.php\n");
    exit(2);
}
$s = file_get_contents($f);
if (strpos($s, 'DEWIAR-TOOLCALLS') !== false) {
    echo "Уже исправлено — ничего не меняю.\n";
    exit(0);
}
$steps = [
    // 1) берём delta.tool_calls рядом с текстом
    ["                if (!empty(\$choice['finish_reason'])) { \$finish = \$choice['finish_reason']; }\n                if (\$delta === '' && \$reason === null) { return; }",
     "                if (!empty(\$choice['finish_reason'])) { \$finish = \$choice['finish_reason']; }\n"
     . "                \$tcs = \$choice['delta']['tool_calls'] ?? null;   // DEWIAR-TOOLCALLS: вызовы действий в потоке — не выбрасывать\n"
     . "                if (\$delta === '' && \$reason === null && empty(\$tcs)) { return; }"],
    // 2) пересылаем их клиенту в том же куске (OpenAI-формат)
    ["                    if (\$delta !== '')  { \$d['content'] = (string)\$delta; }\n",
     "                    if (\$delta !== '')  { \$d['content'] = (string)\$delta; }\n"
     . "                    if (!empty(\$tcs)) { \$d['tool_calls'] = \$tcs; }   // DEWIAR-TOOLCALLS\n"],
];
foreach ($steps as $i => [$a, $b]) {
    if (substr_count($s, $a) !== 1) {
        fwrite(STDERR, 'Не нашла место ' . ($i + 1) . " в $f — версия шлюза другая. Пришлите файл разработчику Dewiar.\n");
        exit(1);
    }
    $s = str_replace($a, $b, $s);
}
$bak = $f . '.bak-' . date('Ymd-His');
if (!copy($f, $bak)) {
    fwrite(STDERR, "Не удалось сохранить копию $bak — ничего не меняю.\n");
    exit(1);
}
$tmp = $f . '.new';
file_put_contents($tmp, $s);
exec('php -l ' . escapeshellarg($tmp) . ' 2>&1', $out, $rc);
if ($rc !== 0) {
    @unlink($tmp);
    fwrite(STDERR, "Проверка PHP не прошла — ничего не меняю:\n" . implode("\n", $out) . "\n");
    exit(1);
}
rename($tmp, $f);
echo "Готово: вызовы действий теперь проходят через шлюз в потоке. Копия — $bak\n";
