<?php
header('Content-Type: application/json; charset=utf-8');

$object = $_GET['object'] ?? '';
$sync_id = $_GET['sync_id'] ?? '';

if (!$object || !$sync_id) {
    http_response_code(400);
    echo json_encode(['error' => 'object и sync_id обязательны']);
    exit;
}

$filePath = __DIR__ . "/booking_files/{$object}.csv";
if (!file_exists($filePath)) {
    echo json_encode(['error' => 'Файл не найден']);
    exit;
}

$handle = fopen($filePath, 'r');
$headers = fgetcsv($handle, 1000, ',');

if (!$headers) {
    fclose($handle);
    echo json_encode(['error' => 'Неверный формат CSV']);
    exit;
}

$idx_sync_id = array_search('_sync_id', $headers);
if ($idx_sync_id === false) {
    fclose($handle);
    echo json_encode(['error' => 'Колонка _sync_id не найдена']);
    exit;
}

while (($row = fgetcsv($handle, 1000, ',')) !== false) {
    if (isset($row[$idx_sync_id]) && trim($row[$idx_sync_id]) === $sync_id) {
        $map = [
            'Гость' => 'guest',
            'Дата бронирования' => 'booking_date',
            'Заезд' => 'check_in',
            'Выезд' => 'check_out',
            'Количество ночей' => 'nights',
            'СуммаБатты' => 'total_sum',
            'Аванс Батты/Рубли' => 'advance',
            'Доплата Батты/Рубли' => 'additional_payment',
            'Источник' => 'source',
            'Дополнительные доплаты' => 'extra_charges',
            'Расходы' => 'expenses',
            'Оплата' => 'payment_method',
            'Комментарий' => 'comment',
            'телефон' => 'phone',
            'дополнительный телефон' => 'extra_phone',
            'Рейсы' => 'flights',
            '_sync_id' => 'sync_id'
        ];

        $booking = [];
        foreach ($headers as $i => $key) {
            $engKey = $map[$key] ?? $key;
            $value = isset($row[$i]) ? trim($row[$i]) : '';
// Удаляем все пробелы для числовых полей
if (in_array($engKey, ['total_sum', 'advance', 'additional_payment', 'commission'])) {
    $value = preg_replace('/\s+/', '', $value);
}
$booking[$engKey] = $value;
        }

        echo json_encode($booking, JSON_UNESCAPED_UNICODE);
        fclose($handle);
        exit;
    }
}

fclose($handle);
echo json_encode(['error' => 'Бронь не найдена']);