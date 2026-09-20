<?php
/**
 * Разрезает большой файл стабов (php-stubs/wordpress-stubs.php, ~5 МБ) на части
 * меньше 1 МБ, чтобы intelephense их проиндексировал.
 *
 * Зачем: у intelephense есть параметр files.maxSize со значением по умолчанию
 * 1e6 байт (DEFAULT_MAX_FILE_SIZE в lib/intelephense.js). Файлы больше он
 * пропускает молча, без ошибки — поэтому все функции ядра WordPress
 * подсвечивались как Undefined, хотя стабы лежали в воркспейсе. Плагин php-lsp
 * запускает `intelephense --stdio` без initializationOptions, то есть поднять
 * лимит из конфигурации сессии нельзя — режем файл.
 *
 * Границы ищутся токенайзером PHP (token_get_all), а не регуляркой: фигурные
 * скобки встречаются и в докблоках, и в строках.
 *
 * Использование:
 *   php scripts/split_php_stubs.php php-stubs/wordpress-stubs.php
 *   php scripts/split_php_stubs.php php-stubs/wordpress-stubs.php 900000
 *
 * Исходный файл переименовывается в *.php.bak, чтобы intelephense его больше
 * не видел, а рядом появляются wordpress-stubs.part1.php, .part2.php и т.д.
 */

$src   = $argv[1] ?? 'php-stubs/wordpress-stubs.php';
$limit = (int) ($argv[2] ?? 900000);

if (!is_file($src)) {
    fwrite(STDERR, "Не найден файл стабов: $src\n");
    exit(1);
}

$code   = file_get_contents($src);
$tokens = token_get_all($code);

// Собираем сегменты: каждый — один top-level элемент вместе с предшествующими
// комментариями и пробелами, привязанный к своему неймспейсу.
$segments   = [];   // [namespace, text]
$ns         = '';   // текущий неймспейс ('' = глобальный)
$depth      = 0;    // глубина фигурных скобок внутри тела неймспейса
$inNsHeader = false;
$nsName     = '';
$buf        = '';
$nsBraced   = false;

$flush = function () use (&$segments, &$buf, &$ns) {
    if (trim($buf) !== '') {
        $segments[] = [$ns, $buf];
    }
    $buf = '';
};

foreach ($tokens as $t) {
    if (is_array($t)) {
        [$id, $text] = $t;

        if ($id === T_OPEN_TAG || $id === T_CLOSE_TAG) {
            continue; // теги открытия/закрытия ставим сами при сборке частей
        }

        if ($id === T_NAMESPACE && $depth === 0) {
            $flush();
            $inNsHeader = true;
            $nsName     = '';
            continue;
        }

        if ($inNsHeader) {
            if ($id === T_STRING || $id === T_NAME_QUALIFIED || $id === T_NS_SEPARATOR) {
                $nsName .= $text;
            }
            continue; // пробелы и комментарии в шапке неймспейса не нужны
        }

        // Скобки внутри интерполяции строк: "{$a}" и "${a}"
        if ($id === T_CURLY_OPEN || $id === T_DOLLAR_OPEN_CURLY_BRACES) {
            $depth++;
        }

        $buf .= $text;
        continue;
    }

    // Односимвольные токены
    if ($inNsHeader) {
        if ($t === '{') {
            $ns         = $nsName;
            $nsBraced   = true;
            $inNsHeader = false;
            $depth      = 0;
            continue;
        }
        if ($t === ';') {
            $ns         = $nsName;
            $nsBraced   = false;
            $inNsHeader = false;
            $depth      = 0;
            continue;
        }
        continue;
    }

    if ($t === '{') {
        $depth++;
        $buf .= $t;
        continue;
    }

    if ($t === '}') {
        if ($nsBraced && $depth === 0) {
            // Закрылось тело неймспейса
            $flush();
            $ns       = '';
            $nsBraced = false;
            continue;
        }
        $depth--;
        $buf .= $t;
        if ($depth === 0) {
            $flush(); // конец top-level объявления
        }
        continue;
    }

    $buf .= $t;

    if ($t === ';' && $depth === 0) {
        $flush(); // top-level use/const/define
    }
}
$flush();

// Раскладываем сегменты по частям, не превышая лимит.
$parts   = [];
$current = [];
$size    = 0;

foreach ($segments as [$segNs, $text]) {
    $cost = strlen($text) + strlen($segNs) + 32; // запас на обёртку namespace
    if ($size > 0 && $size + $cost > $limit) {
        $parts[] = $current;
        $current = [];
        $size    = 0;
    }
    $current[] = [$segNs, $text];
    $size     += $cost;
}
if ($current) {
    $parts[] = $current;
}

$dir  = dirname($src);
$base = basename($src, '.php');

// Убираем старые части, чтобы после пересборки не осталось лишних файлов.
foreach (glob("$dir/$base.part*.php") as $old) {
    unlink($old);
}

$written = [];
foreach ($parts as $i => $part) {
    $out = "<?php\n\n";
    $prevNs = null;
    $open   = false;

    foreach ($part as [$segNs, $text]) {
        if ($segNs !== $prevNs) {
            if ($open) {
                $out .= "\n}\n";
            }
            $out   .= "\nnamespace " . ($segNs === '' ? '' : $segNs . ' ') . "{\n";
            $open   = true;
            $prevNs = $segNs;
        }
        $out .= $text;
    }
    if ($open) {
        $out .= "\n}\n";
    }

    $path = sprintf('%s/%s.part%d.php', $dir, $base, $i + 1);
    file_put_contents($path, $out);
    $written[$path] = strlen($out);
}

// Прячем исходник от индексатора: .bak не попадает под *.php.
$bak = $src . '.bak';
if (is_file($bak)) {
    unlink($bak);
}
rename($src, $bak);

printf("Исходник: %s (%s байт) → %s\n", $src, number_format(strlen($code), 0, '.', ' '), $bak);
printf("Сегментов: %d, частей: %d, лимит %s байт\n", count($segments), count($parts), number_format($limit, 0, '.', ' '));
foreach ($written as $path => $len) {
    printf("  %-46s %9s байт\n", $path, number_format($len, 0, '.', ' '));
}
