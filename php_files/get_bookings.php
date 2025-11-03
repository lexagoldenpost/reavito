<?php
header('Content-Type: application/json; charset=utf-8');

$objectName = $_GET['object'] ?? '';
if (!$objectName) {
    echo json_encode([]);
    exit;
}

$filePath = __DIR__ . '/booking_files/' . $objectName . '.csv';
if (!file_exists($filePath)) {
    echo json_encode([]);
    exit;
}

$handle = fopen($filePath, 'r');
$headers = fgetcsv($handle, 1000, ',');

if (!$headers) {
    fclose($handle);
    echo json_encode([]);
    exit;
}

// Индексы колонок
$idx_guest      = array_search('Гость', $headers);
$idx_check_in   = array_search('Заезд', $headers);
$idx_check_out  = array_search('Выезд', $headers);
$idx_phone      = array_search('телефон', $headers);
$idx_total      = array_search('СуммаБатты', $headers);
$idx_advance    = array_search('Аванс Батты/Рубли', $headers);
$idx_sync_id    = array_search('_sync_id', $headers);

if ($idx_sync_id === false || $idx_check_out === false) {
    fclose($handle);
    echo json_encode([]);
    exit;
}

$today = new DateTime();
$bookings = [];

while (($row = fgetcsv($handle, 1000, ',')) !== false) {
    $checkOutStr = isset($row[$idx_check_out]) ? trim($row[$idx_check_out]) : '';
    if (!$checkOutStr) continue;

    $checkOut = DateTime::createFromFormat('d.m.Y', $checkOutStr);
    if (!$checkOut) continue;

    // Фильтр: выезд строго больше сегодняшнего дня
    if ($checkOut > $today) {
        $checkInStr = isset($row[$idx_check_in]) ? trim($row[$idx_check_in]) : '';

        $bookings[] = [
            'sync_id'           => isset($row[$idx_sync_id]) ? trim($row[$idx_sync_id]) : '',
            'guest'          => isset($row[$idx_guest]) ? trim($row[$idx_guest]) : '',
            'check_in'       => $checkInStr,
            'check_out'      => $checkOutStr,
            'phone'          => isset($row[$idx_phone]) ? trim($row[$idx_phone]) : '',
            'total_amount'   => isset($row[$idx_total]) ? trim($row[$idx_total]) : '',
            'prepayment'     => isset($row[$idx_advance]) ? trim($row[$idx_advance]) : ''
        ];
    }
}

// Сортировка по дате заезда («Заезд»)
usort($bookings, function($a, $b) {
    $dateA = DateTime::createFromFormat('d.m.Y', $a['check_in']);
    $dateB = DateTime::createFromFormat('d.m.Y', $b['check_in']);

    if (!$dateA && !$dateB) return 0;
    if (!$dateA) return 1;
    if (!$dateB) return -1;

    return $dateA <=> $dateB;
});

fclose($handle);
echo json_encode($bookings, JSON_UNESCAPED_UNICODE);