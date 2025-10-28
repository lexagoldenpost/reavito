<?php
// get_bookings.php
header('Content-Type: application/json');

function getFutureBookings($objectName) {
    $filePath = __DIR__ . '/booking_files/' . $objectName . '.csv';
    $bookings = [];

    if (!file_exists($filePath)) {
        return $bookings;
    }

    if (($handle = fopen($filePath, "r")) !== false) {
        $headers = fgetcsv($handle);

        while (($row = fgetcsv($handle, 1000, ",")) !== false) {
            if (count($row) >= 4) {
                $guest = trim($row[0]);
                $checkInStr = trim($row[2]);
                $checkOutStr = trim($row[3]);

                // Парсим даты
                $checkIn = DateTime::createFromFormat('d.m.Y', $checkInStr);
                $currentDate = new DateTime();

                // Берем только будущие бронирования
                if ($checkIn && $checkIn >= $currentDate) {
                    $phone = isset($row[13]) ? trim($row[13]) : '';
                    $totalAmount = isset($row[5]) ? trim($row[5]) : '';
                    $prepayment = isset($row[6]) ? trim($row[6]) : '';

                    $bookings[] = [
                        'guest' => $guest,
                        'check_in' => $checkInStr,
                        'check_out' => $checkOutStr,
                        'phone' => $phone,
                        'total_amount' => $totalAmount,
                        'prepayment' => $prepayment
                    ];
                }
            }
        }
        fclose($handle);
    }

    // Сортируем по дате заезда
    usort($bookings, function($a, $b) {
        return strtotime(str_replace('.', '-', $a['check_in'])) - strtotime(str_replace('.', '-', $b['check_in']));
    });

    return $bookings;
}

$objectName = $_GET['object'] ?? '';
if ($objectName) {
    $bookings = getFutureBookings($objectName);
    echo json_encode($bookings, JSON_UNESCAPED_UNICODE);
} else {
    echo json_encode([]);
}
?>