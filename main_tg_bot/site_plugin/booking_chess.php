<?php
// chessboard.php — строго по требованию: половинки + гость один раз + цены в свободных

function readBookedDatesWithGuests($filePath) {
    $booked = [];
    if (!file_exists($filePath)) return $booked;
    if (($handle = fopen($filePath, "r")) !== false) {
        fgetcsv($handle);
        while (($row = fgetcsv($handle, 1000, ",")) !== false) {
            if (count($row) < 6) continue;
            $guestName = trim($row[0]);
            $checkInStr = trim($row[2]);
            $checkOutStr = trim($row[3]);
            $totalAmount = intval(trim($row[5]));
            $checkIn = DateTime::createFromFormat('d.m.Y', $checkInStr);
            $checkOut = DateTime::createFromFormat('d.m.Y', $checkOutStr);
            if (!$checkIn || !$checkOut) continue;
            $booked[] = [
                'start' => $checkIn->format('Y-m-d'),
                'end'   => $checkOut->format('Y-m-d'),
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
    $monthMap = ["январь"=>1,"февраль"=>2,"март"=>3,"апрель"=>4,"май"=>5,"июнь"=>6,"июль"=>7,"август"=>8,"сентябрь"=>9,"октябрь"=>10,"ноябрь"=>11,"декабрь"=>12];
    if (($handle = fopen($filePath, "r")) !== false) {
        fgetcsv($handle);
        while (($row = fgetcsv($handle, 1000, ",")) !== false) {
            if (count($row) >= 4) {
                $monthName = trim(mb_strtolower($row[0], 'UTF-8'));
                $startDay = intval(trim($row[1]));
                $endDay = intval(trim($row[2]));
                $price = intval(trim($row[3]));
                if (isset($monthMap[$monthName]) && $startDay > 0 && $endDay >= $startDay && $price > 0) {
                    $priceData[] = ["month"=>$monthMap[$monthName],"startDay"=>$startDay,"endDay"=>$endDay,"price"=>$price];
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
        $objects[$filename] = ['name' => $displayName, 'booked' => $bookedRanges, 'prices' => $priceData];
    }
}

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

$allDates = [];
$current = clone $startDate;
while ($current <= $endDate) {
    $allDates[] = $current->format('Y-m-d');
    $current->modify('+1 day');
}
$todayStr = (new DateTime())->format('Y-m-d');
$russianWeekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
?>
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Шахматка бронирования</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css  " rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; }
        .container { max-width: 1800px; }
        .card { box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: none; border-radius: 15px; background: white; }
        .chessboard-header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1rem; border-radius: 12px; margin-bottom: 1.5rem; text-align: center; }
        .chessboard-table { width: 100%; border-collapse: collapse; font-size: 0.72rem; }
        .chessboard-table th, .chessboard-table td { text-align: center; padding: 2px; border: 1px solid #ddd; vertical-align: middle; }
        .chessboard-table th.room-name { background: #f1f3f5; position: sticky; left: 0; z-index: 20; width: 200px; box-shadow: 2px 0 5px rgba(0,0,0,0.1); }
        .chessboard-table td.room-name { background: white; position: sticky; left: 0; z-index: 15; width: 200px; box-shadow: 2px 0 5px rgba(0,0,0,0.1); font-weight: 600; }
        .chessboard-table th.date-header { background: #f8f9fa; font-size: 0.7rem; }
        .chessboard-table th.date-header.today { background: #ffeaa7; font-weight: bold; }
        .chessboard-table th.date-header.weekend { background: #fdcb6e; }
        .cell-free { background-color: #d5f4e6; }
        .cell-booked { background-color: #fadbd8; color: #2c3e50; font-weight: 600; }
        .price-tag { display: block; font-size: 0.7rem; color: #27ae60; margin-top: 1px; }
        .legend { display: flex; flex-wrap: wrap; gap: 15px; justify-content: center; margin-top: 1rem; }
        .legend-item { display: flex; align-items: center; gap: 5px; font-size: 0.85rem; }
        .legend-color { width: 14px; height: 14px; border: 1px solid #999; }
        .table-responsive { overflow: auto; max-height: 80vh; }
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
                    <!-- Верхний заголовок: даты с colspan=2 -->
                    <tr>
                        <th class="room-name">Объекты</th>
                        <?php foreach ($allDates as $dateStr): ?>
                            <th class="date-header" colspan="2">
                                <?php
                                $dt = new DateTime($dateStr);
                                $classes = [];
                                if ($dateStr === $todayStr) echo '<span class="today">';
                                if ((int)$dt->format('N') >= 6) echo '<span class="weekend">';
                                echo $dt->format('j') . '<br>' . $russianWeekdays[(int)$dt->format('N') - 1];
                                if ((int)$dt->format('N') >= 6) echo '</span>';
                                if ($dateStr === $todayStr) echo '</span>';
                                ?>
                            </th>
                        <?php endforeach; ?>
                    </tr>
                    <!-- Нижний заголовок: Утро / Вечер -->
                    <tr>
                        <th class="room-name"></th>
                        <?php foreach ($allDates as $dateStr): ?>
                            <th class="date-header">Утро</th>
                            <th class="date-header">Вечер</th>
                        <?php endforeach; ?>
                    </tr>
                </thead>
                <tbody>
                    <?php foreach ($objects as $filename => $obj): ?>
                        <tr>
                            <td class="room-name"><?= htmlspecialchars($obj['name']) ?></td>
                            <?php
                            // Создаём карту для каждой половинки
                            $halfMap = [];
                            foreach ($allDates as $date) {
                                $halfMap[$date . '_morning'] = ['type' => 'free', 'price' => null, 'guest' => '', 'amount' => 0, 'is_start' => false];
                                $halfMap[$date . '_evening'] = ['type' => 'free', 'price' => null, 'guest' => '', 'amount' => 0, 'is_start' => false];
                            }

                            // Заполняем бронирования
                            foreach ($obj['booked'] as $booking) {
                                // Ночи: от start до end-1
                                $current = new DateTime($booking['start']);
                                $end = new DateTime($booking['end']);
                                while ($current < $end) {
                                    $dateKey = $current->format('Y-m-d');
                                    // Вечер текущей даты = начало ночи
                                    $halfMap[$dateKey . '_evening']['type'] = 'booked';
                                    // Утро следующей даты = конец ночи
                                    $nextDate = clone $current;
                                    $nextDate->modify('+1 day');
                                    $nextKey = $nextDate->format('Y-m-d');
                                    if (isset($halfMap[$nextKey . '_morning'])) {
                                        $halfMap[$nextKey . '_morning']['type'] = 'booked';
                                    }
                                    // Гостя ставим только в первую вечернюю ячейку
                                    if ($dateKey === $booking['start']) {
                                        $halfMap[$dateKey . '_evening']['guest'] = $booking['guest'];
                                        $halfMap[$dateKey . '_evening']['amount'] = $booking['total_amount'];
                                        $halfMap[$dateKey . '_evening']['is_start'] = true;
                                    }
                                    $current->modify('+1 day');
                                }
                            }

                            // Заполняем цены для свободных вечеров
                            foreach ($allDates as $date) {
                                if ($halfMap[$date . '_evening']['type'] === 'free') {
                                    $halfMap[$date . '_evening']['price'] = getPriceForDate($date, $obj['prices']);
                                }
                                // Утро не имеет собственной цены — оно относится к предыдущей ночи, но если оно свободно, и вечер тоже, то цена уже в вечерней ячейке
                                // В нашем отображении утро без брони — просто свободно, цена не дублируется
                            }

                            // Выводим все половинки
                            foreach ($allDates as $date) {
                                // Утро
                                $morning = $halfMap[$date . '_morning'];
                                $m_class = $morning['type'] === 'booked' ? 'cell-booked' : 'cell-free';
                                echo '<td class="' . $m_class . '">';
                                // В утре гостя не показываем
                                echo '</td>';

                                // Вечер
                                $evening = $halfMap[$date . '_evening'];
                                $e_class = $evening['type'] === 'booked' ? 'cell-booked' : 'cell-free';
                                echo '<td class="' . $e_class . '">';
                                if ($evening['is_start'] && $evening['guest']) {
                                    echo htmlspecialchars($evening['guest']);
                                    if ($evening['amount'] > 0) {
                                        echo '<span class="price-tag">' . number_format($evening['amount'], 0, '', ' ') . ' ฿</span>';
                                    }
                                } elseif ($evening['type'] === 'free' && $evening['price'] !== null) {
                                    echo '<span class="price-tag">' . number_format($evening['price'], 0, '', ' ') . ' ฿</span>';
                                }
                                echo '</td>';
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
        </div>
    </div>
</div>
</body>
</html>