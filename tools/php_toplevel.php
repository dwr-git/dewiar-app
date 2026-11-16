<?php
// Что лежит на верхнем уровне PHP-файла (для раскладки cloud.php по частям — tools/split_php.py): функции и константы
// с их строками, всё остальное (исполняемые строки) — отдельно. Вывод — JSON: [{kind, name, from, to}, …].
//   php tools/php_toplevel.php server/dwrapp/cloud.php
$src = file_get_contents($argv[1]);
$t = token_get_all($src);
$out = [];
$depth = 0;
$line = 1;
$n = count($t);
$cur = null;            // открытое объявление верхнего уровня
$stmt = null;           // исполняемая строка верхнего уровня
$run = 1;               // строка текущего токена (у одиночных символов своей строки нет)
for ($i = 0; $i < $n; $i++) {
    $tok = $t[$i];
    $line = $run;
    $run += substr_count(is_array($tok) ? $tok[1] : $tok, "\n");
    if (is_array($tok)) {
        [$id, $text] = $tok;
        if ($depth === 0 && $cur === null && $stmt === null) {
            if ($id === T_FUNCTION) {
                $j = $i + 1;
                while ($j < $n && is_array($t[$j]) && $t[$j][0] === T_WHITESPACE) {
                    $j++;
                }
                $cur = ['kind' => 'function', 'name' => is_array($t[$j]) ? $t[$j][1] : '', 'from' => $line, 'opened' => false];
                continue;
            }
            if ($id === T_CONST) {
                $j = $i + 1;
                while ($j < $n && is_array($t[$j]) && $t[$j][0] === T_WHITESPACE) {
                    $j++;
                }
                $cur = ['kind' => 'const', 'name' => is_array($t[$j]) ? $t[$j][1] : '', 'from' => $line, 'opened' => false];
                continue;
            }
            if (!in_array($id, [T_WHITESPACE, T_COMMENT, T_DOC_COMMENT, T_OPEN_TAG, T_CLOSE_TAG, T_INLINE_HTML], true)) {
                $stmt = ['kind' => 'stmt', 'name' => trim(substr($text, 0, 30)), 'from' => $line];
            }
        }
        if ($id === T_CURLY_OPEN || $id === T_DOLLAR_OPEN_CURLY_BRACES) {
            $depth++;
        }
        continue;
    }
    // одиночный символ
    if ($depth === 0 && $cur === null && $stmt === null && $tok !== ';') {
        $stmt = ['kind' => 'stmt', 'name' => $tok, 'from' => $line];
    }
    if ($tok === '{') {
        $depth++;
        if ($cur !== null && $depth === 1) {
            $cur['opened'] = true;
        }
    } elseif ($tok === '}') {
        $depth--;
        if ($depth === 0 && $cur !== null && $cur['kind'] === 'function' && $cur['opened']) {
            $cur['to'] = $line;
            unset($cur['opened']);
            $out[] = $cur;
            $cur = null;
        } elseif ($depth === 0 && $stmt !== null) {
            $stmt['to'] = $line;
            $out[] = $stmt;
            $stmt = null;
        }
    } elseif ($tok === ';' && $depth === 0) {
        if ($cur !== null && $cur['kind'] === 'const') {
            $cur['to'] = $line;
            unset($cur['opened']);
            $out[] = $cur;
            $cur = null;
        } elseif ($stmt !== null) {
            $stmt['to'] = $line;
            $out[] = $stmt;
            $stmt = null;
        }
    }
}
echo json_encode($out, JSON_UNESCAPED_UNICODE), "\n";
