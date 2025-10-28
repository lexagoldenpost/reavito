<?php
// chessboard.php — утро/вечер остаются, но надписи скрыты; гость и цена — через colspan

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
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; }
        .container { max-width: 1800px; }
        .card { box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: none; border-radius: 15px; background: white; }
        .chessboard-header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1rem; border-radius: 12px; margin-bottom: 1.5rem; text-align: center; }
        .chessboard-table { width: 100%; border-collapse: collapse; font-size: 0.72rem; }
        .chessboard-table th, .chessboard-table td { text-align: center; padding: 4px; border: 1px solid #ddd; vertical-align: middle; }
        .chessboard-table th.room-name { background: #f1f3f5; position: sticky; left: 0; z-index: 20; width: 200px; box-shadow: 2px 0 5px rgba(0,0,0,0.1); }
        .chessboard-table td.room-name { background: white; position: sticky; left: 0; z-index: 15; width: 200px; box-shadow: 2px 0 5px rgba(0,0,0,0.1); font-weight: 600; }
        .chessboard-table th.date-header { background: #f8f9fa; font-size: 0.7rem; }
        .chessboard-table th.date-header.today { background: #ffeaa7; font-weight: bold; }
        .chessboard-table th.date-header.weekend { background: #fdcb6e; }
        .cell-free { background-color: #d5f4e6; }
        .cell-booked { background-color: #fadbd8; color: #2c3e50; font-weight: 600; }
        .price-tag { display: block; font-size: 0.7rem; color: #27ae60; margin-top: 2px; }
        .legend { display: flex; flex-wrap: wrap; gap: 15px; justify-content: center; margin-top: 1rem; }
        .legend-item { display: flex; align-items: center; gap: 5px; font-size: 0.85rem; }
        .legend-color { width: 14px; height: 14px; border: 1px solid #999; }
        .table-responsive { overflow: auto; max-height: 80vh; }
        /* Скрыть надписи "Утро/Вечер", но оставить ячейки */
        .time-label { visibility: hidden; height: 0; overflow: hidden; font-size: 0; line-height: 0; }
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
                                $content = $dt->format('j') . '<br>' . $russianWeekdays[(int)$dt->format('N') - 1];
                                if ($dateStr === $todayStr) {
                                    echo '<span class="today">' . $content . '</span>';
                                } elseif ((int)$dt->format('N') >= 6) {
                                    echo '<span class="weekend">' . $content . '</span>';
                                } else {
                                    echo $content;
                                }
                                ?>
                            </th>
                        <?php endforeach; ?>
                    </tr>
                    <!-- Нижний заголовок: "Утро"/"Вечер" — скрыты -->
                    <tr>
                        <th class="room-name"></th>
                        <?php foreach ($allDates as $dateStr): ?>
                            <th class="date-header time-label">Утро</th>
                            <th class="date-header time-label">Вечер</th>
                        <?php endforeach; ?>
                    </tr>
                </thead>
                <tbody>
                    <?php foreach ($objects as $filename => $obj): ?>
                        <tr>
                            <td class="room-name"><?= htmlspecialchars($obj['name']) ?></td>
                            <?php
                            // Создаём карту занятых позиций (индексы)
                            $occupied = [];
                            $guestInfo = [];

                            // Преобразуем даты в индексы
                            $dateToIndex = array_flip($allDates); // дата => индекс

                            // Подготавливаем информацию о бронировании по индексам
                            foreach ($obj['booked'] as $booking) {
                                $startIdx = $dateToIndex[$booking['start']] ?? null;
                                $endIdx = $dateToIndex[$booking['end']] ?? null;
                                if ($startIdx === null || $endIdx === null) continue;

                                // Бронь занимает: от start (вечер) до end (утро не включается)
                                // В терминах ячеек: каждая дата = [утро, вечер] → индексы: 2*i, 2*i+1
                                // Ночи: от start (вечер = 2*startIdx+1) до end (утро = 2*endIdx)
                                // То есть ячейки: [2*startIdx+1, 2*startIdx+2, ..., 2*endIdx - 1]
                                $cellStart = 2 * $startIdx + 1;
                                $cellEnd = 2 * $endIdx; // не включительно
                                for ($c = $cellStart; $c < $cellEnd; $c++) {
                                    $occupied[$c] = true;
                                }
                                // Сохраняем данные для отображения в первой ячейке брони
                                $guestInfo[$cellStart] = [
                                    'guest' => $booking['guest'],
                                    'amount' => $booking['total_amount'],
                                    'length' => $cellEnd - $cellStart
                                ];
                            }

                            $totalCells = count($allDates) * 2;
                            $i = 0;
                            while ($i < $totalCells) {
                                if (isset($guestInfo[$i])) {
                                    // Начало бронирования — рисуем одну ячейку на весь период
                                    $info = $guestInfo[$i];
                                    $colspan = $info['length'];
                                    echo '<td class="cell-booked" colspan="' . $colspan . '">';
                                    echo htmlspecialchars($info['guest']);
                                    if ($info['amount'] > 0) {
                                        echo '<span class="price-tag">' . number_format($info['amount'], 0, '', ' ') . ' ฿</span>';
                                    }
                                    echo '</td>';
                                    $i += $colspan;
                                } elseif (!isset($occupied[$i])) {
                                    // Свободная ячейка — проверяем, можно ли объединить с соседней
                                    // Правило: если обе ячейки (утро+вечер одной даты) свободны — объединяем
                                    $isMorning = ($i % 2 === 0);
                                    $sameDatePairFree = false;
                                    if ($isMorning && ($i + 1) < $totalCells && !isset($occupied[$i + 1])) {
                                        // Утро и вечер одной даты свободны
                                        $sameDatePairFree = true;
                                        $price = getPriceForDate($allDates[$i / 2], $obj['prices']);
                                        echo '<td class="cell-free" colspan="2">';
                                        if ($price !== null) {
                                            echo '<span class="price-tag">' . number_format($price, 0, '', ' ') . ' ฿</span>';
                                        }
                                        echo '</td>';
                                        $i += 2;
                                    } else {
                                        // Одиночная свободная ячейка (редко, но возможно при частичной брони)
                                        $dateIndex = intdiv($i, 2);
                                        $price = getPriceForDate($allDates[$dateIndex], $obj['prices']);
                                        echo '<td class="cell-free">';
                                        if ($price !== null) {
                                            echo '<span class="price-tag">' . number_format($price, 0, '', ' ') . ' ฿</span>';
                                        }
                                        echo '</td>';
                                        $i++;
                                    }
                                } else {
                                    // Занято, но не начало — пропускаем (уже отрисовано через colspan)
                                    $i++;
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
        </div>
    </div>
</div>
</body>
</html>