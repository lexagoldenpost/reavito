<?php
// chessboard.php — профессиональная шахматка с colspan

function readBookedDatesWithGuests($filePath) {
    $booked = [];
    if (!file_exists($filePath)) {
        error_log("Файл не найден: " . $filePath);
        return $booked;
    }

    if (($handle = fopen($filePath, "r")) !== false) {
        fgetcsv($handle); // заголовок
        $lineNum = 1;
        while (($row = fgetcsv($handle, 1000, ",")) !== false) {
            $lineNum++;
            if (count($row) < 6) continue;

            $guestName = trim($row[0]);
            $checkInStr = trim($row[2]);
            $checkOutStr = trim($row[3]);
            $totalAmount = intval(trim($row[5]));

            $checkIn = DateTime::createFromFormat('d.m.Y', $checkInStr);
            $checkOut = DateTime::createFromFormat('d.m.Y', $checkOutStr);

            if (!$checkIn || !$checkOut) continue;

            // Вычисляем количество ночей (разница в днях)
            $interval = $checkIn->diff($checkOut);
            $nights = (int)$interval->days;

            // Защита от 0 ночей
            if ($nights <= 0) $nights = 1;

            $booked[] = [
                'start' => $checkIn->format('Y-m-d'),
                'end'   => $checkOut->format('Y-m-d'),
                'nights' => $nights,
                'guest' => $guestName,
                'total_amount' => $totalAmount
            ];
        }
        fclose($handle);
    }
    return $booked;
}

function readPriceData($filePath) {
    $priceData = [];
    if (!file_exists($filePath)) return $priceData;

    $monthMap = [
        "январь" => 1, "февраль" => 2, "март" => 3, "апрель" => 4,
        "май" => 5, "июнь" => 6, "июль" => 7, "август" => 8,
        "сентябрь" => 9, "октябрь" => 10, "ноябрь" => 11, "декабрь" => 12
    ];

    if (($handle = fopen($filePath, "r")) !== false) {
        fgetcsv($handle); // заголовок
        while (($row = fgetcsv($handle, 1000, ",")) !== false) {
            if (count($row) >= 4) {
                $monthName = trim(mb_strtolower($row[0], 'UTF-8'));
                $startDay = intval(trim($row[1]));
                $endDay = intval(trim($row[2]));
                $price = intval(trim($row[3]));

                if (isset($monthMap[$monthName]) && $startDay > 0 && $endDay >= $startDay && $price > 0) {
                    $priceData[] = [
                        "month" => $monthMap[$monthName],
                        "startDay" => $startDay,
                        "endDay" => $endDay,
                        "price" => $price
                    ];
                }
            }
        }
        fclose($handle);
    }
    return $priceData;
}

function getPriceForDate($dateStr, $pricePeriods) {
    $dt = new DateTime($dateStr);
    $month = (int)$dt->format('n');
    $day = (int)$dt->format('j');
    foreach ($pricePeriods as $p) {
        if ($p['month'] === $month && $day >= $p['startDay'] && $day <= $p['endDay']) {
            return $p['price'];
        }
    }
    return null;
}

// === Подготовка данных ===
$bookingFilesPath = __DIR__ . '/booking_files/*.csv';
$files = glob($bookingFilesPath);

$objects = [];
if (!empty($files)) {
    foreach ($files as $file) {
        $filename = pathinfo($file, PATHINFO_FILENAME);
        $displayName = ucwords(str_replace('_', ' ', $filename));
        $bookedRanges = readBookedDatesWithGuests($file);
        $priceFile = __DIR__ . "/task_files/{$filename}_price.csv";
        $priceData = readPriceData($priceFile);
        $objects[$filename] = [
            'name' => $displayName,
            'booked' => $bookedRanges,
            'prices' => $priceData
        ];
    }
}

// Параметры шахматки
$monthsToShow = isset($_GET['months']) ? (int)$_GET['months'] : 13;
$monthsToShow = max(1, min(24, $monthsToShow));

$startDateParam = $_GET['start'] ?? null;
if ($startDateParam && preg_match('/^\d{4}-\d{2}-\d{2}$/', $startDateParam)) {
    $startDate = new DateTime($startDateParam);
} else {
    $startDate = new DateTime('first day of this month');
}

$endDate = clone $startDate;
$endDate->modify("+{$monthsToShow} months -1 day");

// Генерация всех дат
$allDates = [];
$current = clone $startDate;
while ($current <= $endDate) {
    $allDates[] = $current->format('Y-m-d');
    $current->modify('+1 day');
}

$todayStr = (new DateTime())->format('Y-m-d');
$russianMonths = [1 => 'Янв', 2 => 'Фев', 3 => 'Мар', 4 => 'Апр', 5 => 'Май', 6 => 'Июн',
                  7 => 'Июл', 8 => 'Авг', 9 => 'Сен', 10 => 'Окт', 11 => 'Ноя', 12 => 'Дек'];
$russianWeekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
?>
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Шахматка бронирования</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; }
        .container { max-width: 1800px; }
        .card { box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: none; border-radius: 15px; background: white; }
        .chessboard-header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1rem; border-radius: 12px; margin-bottom: 1.5rem; text-align: center; }
        .chessboard-table { width: 100%; border-collapse: collapse; font-size: 0.75rem; }
        .chessboard-table th, .chessboard-table td { text-align: center; padding: 4px; border: 1px solid #e0e0e0; vertical-align: middle; }
        .chessboard-table th.room-name { background: #f1f3f5; position: sticky; left: 0; z-index: 10; width: 200px; }
        .chessboard-table th.date-header { background: #f8f9fa; font-size: 0.7rem; }
        .chessboard-table th.date-header.today { background: #ffeaa7; font-weight: bold; }
        .chessboard-table th.date-header.weekend { background: #fdcb6e; }
        .cell-available { background-color: #d5f4e6; }
        .cell-booked { background-color: #fadbd8; color: #2c3e50; font-weight: 600; }
        .cell-checkin { background-color: #d6eaf8; }
        .cell-checkout { background-color: #fcf3cf; }
        .cell-same-day { background: linear-gradient(135deg, #d6eaf8 50%, #fcf3cf 50%); }
        .today-border { border: 2px solid #e17055 !important; }
        .price-tag { display: block; font-size: 0.7rem; color: #27ae60; margin-top: 2px; }
        .legend { display: flex; flex-wrap: wrap; gap: 15px; justify-content: center; margin-top: 1rem; }
        .legend-item { display: flex; align-items: center; gap: 5px; font-size: 0.85rem; }
        .legend-color { width: 14px; height: 14px; border: 1px solid #999; }
    </style>
</head>
<body>
<div class="container py-4">
    <div class="card p-4">
        <div class="chessboard-header">
            <h2 class="mb-0">Шахматка бронирования</h2>
        </div>

        <div class="text-center mb-3">
            <div class="d-inline-block px-3 py-2 bg-light rounded">
                <?= htmlspecialchars($startDate->format('d.m.Y')) ?> – <?= htmlspecialchars($endDate->format('d.m.Y')) ?>
            </div>
        </div>

        <div class="table-responsive">
            <table class="chessboard-table">
                <thead>
                    <tr>
                        <th class="room-name">Объекты</th>
                        <?php foreach ($allDates as $dateStr): ?>
                            <?php
                            $dt = new DateTime($dateStr);
                            $classes = ['date-header'];
                            if ($dateStr === $todayStr) $classes[] = 'today';
                            if ((int)$dt->format('N') >= 6) $classes[] = 'weekend';
                            ?>
                            <th class="<?= implode(' ', $classes) ?>">
                                <?= $dt->format('j') ?><br>
                                <?= $russianWeekdays[(int)$dt->format('N') - 1] ?>
                            </th>
                        <?php endforeach; ?>
                    </tr>
                </thead>
                <tbody>
                    <?php foreach ($objects as $filename => $obj): ?>
                        <tr data-room="<?= htmlspecialchars($obj['name']) ?>">
                            <td class="room-name"><?= htmlspecialchars($obj['name']) ?></td>
                            <?php
                            $dateIndex = 0;
                            $totalDates = count($allDates);
                            while ($dateIndex < $totalDates) {
                                $currentDate = $allDates[$dateIndex];
                                $rendered = false;

                                // Ищем бронь, начинающуюся сегодня
                                foreach ($obj['booked'] as $booking) {
                                    if ($booking['start'] === $currentDate) {
                                        // Найдена бронь — рисуем colspan
                                        $colspan = min($booking['nights'], $totalDates - $dateIndex);
                                        $classes = ['cell-booked'];
                                        if ($booking['nights'] == 1) {
                                            $classes[] = 'cell-same-day';
                                        } else {
                                            $classes[] = 'cell-checkin';
                                        }
                                        if ($currentDate === $todayStr) $classes[] = 'today-border';

                                        echo '<td colspan="' . $colspan . '" class="' . implode(' ', $classes) . '">';
                                        echo htmlspecialchars($booking['guest']);
                                        if ($booking['total_amount'] > 0) {
                                            echo '<span class="price-tag">' . number_format($booking['total_amount'], 0, '', ' ') . ' ฿</span>';
                                        }
                                        echo '</td>';

                                        $dateIndex += $colspan;
                                        $rendered = true;
                                        break;
                                    }
                                }

                                if (!$rendered) {
                                    // Свободный день
                                    $classes = ['cell-available'];
                                    if ($currentDate === $todayStr) $classes[] = 'today-border';
                                    $price = getPriceForDate($currentDate, $obj['prices']);
                                    echo '<td class="' . implode(' ', $classes) . '">';
                                    if ($price !== null) {
                                        echo '<span class="price-tag">' . number_format($price, 0, '', ' ') . ' ฿</span>';
                                    }
                                    echo '</td>';
                                    $dateIndex++;
                                }
                            }
                            ?>
                        </tr>
                    <?php endforeach; ?>
                </tbody>
            </table>
        </div>

        <div class="legend">
            <div class="legend-item"><div class="legend-color" style="background:#d5f4e6"></div> Свободно</div>
            <div class="legend-item"><div class="legend-color" style="background:#fadbd8"></div> Занято</div>
            <div class="legend-item"><div class="legend-color" style="background:#d6eaf8"></div> Заезд</div>
            <div class="legend-item"><div class="legend-color" style="background:#fcf3cf"></div> Выезд</div>
            <div class="legend-item"><div class="legend-color" style="background:linear-gradient(135deg, #d6eaf8 50%, #fcf3cf 50%)"></div> Заезд/Выезд</div>
        </div>
    </div>
</div>
</body>
</html>