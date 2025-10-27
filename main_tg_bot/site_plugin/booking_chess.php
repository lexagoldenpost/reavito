<?php
// chessboard.php — шахматка бронирования с гостями и ценами + отладка

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
            if (count($row) < 6) {
                error_log("Строка {$lineNum}: недостаточно столбцов (" . count($row) . ") в файле " . basename($filePath));
                continue;
            }

            $guestName = trim($row[0]);
            $checkInStr = trim($row[2]);
            $checkOutStr = trim($row[3]);
            $totalAmount = intval(trim($row[5]));

            // Отладка: выводим сырые значения
            error_log("Строка {$lineNum}: Гость='{$guestName}', Заезд='{$checkInStr}', Выезд='{$checkOutStr}', Сумма={$totalAmount}");

            $checkIn = DateTime::createFromFormat('d.m.Y', $checkInStr);
            $checkOut = DateTime::createFromFormat('d.m.Y', $checkOutStr);

            if (!$checkIn || !$checkOut) {
                error_log("Строка {$lineNum}: Ошибка парсинга даты. Заезд: '{$checkInStr}' -> " . ($checkIn ? 'OK' : 'FAIL') . ", Выезд: '{$checkOutStr}' -> " . ($checkOut ? 'OK' : 'FAIL'));
                continue;
            }

            $booked[] = [
                'start' => $checkIn->format('Y-m-d'),
                'end'   => $checkOut->format('Y-m-d'),
                'guest' => $guestName,
                'total_amount' => $totalAmount
            ];

            error_log("Строка {$lineNum}: Успешно добавлена бронь: {$guestName} с {$checkInStr} по {$checkOutStr}, сумма {$totalAmount}");
        }
        fclose($handle);
    } else {
        error_log("Не удалось открыть файл: " . $filePath);
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
                $monthName = trim(mb_strtolower($row[0], 'UTF-8')); // ← убираем пробелы!
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
$endDate->modify("+{$monthsToShow} months");

// Русские месяцы и дни
$russianMonths = [
    1 => 'Янв', 2 => 'Фев', 3 => 'Мар', 4 => 'Апр', 5 => 'Май', 6 => 'Июн',
    7 => 'Июл', 8 => 'Авг', 9 => 'Сен', 10 => 'Окт', 11 => 'Ноя', 12 => 'Дек'
];
$russianWeekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

$today = new DateTime();
$todayStr = $today->format('Y-m-d');

// Генерация всех дат
$allDates = [];
$current = clone $startDate;
while ($current < $endDate) {
    $allDates[] = $current->format('Y-m-d');
    $current->modify('+1 day');
}
?>
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Шахматка бронирования</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background-color: #f8f9fa;
        }
        .container {
            max-width: 1600px;
        }
        .card {
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border: none;
            border-radius: 15px;
            background: white;
        }
        .chessboard-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1rem;
            border-radius: 12px;
            margin-bottom: 1.5rem;
            text-align: center;
        }
        .chessboard-controls {
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
            align-items: center;
            margin-bottom: 1.5rem;
        }
        .chessboard-controls input,
        .chessboard-controls button {
            padding: 0.5rem 1rem;
            border-radius: 8px;
            font-size: 1rem;
        }
        .chessboard-controls input {
            flex: 1;
            min-width: 200px;
            border: 1px solid #ced4da;
        }
        .chessboard-navigation {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }
        .chessboard-nav-btn {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 0.5rem 1.2rem;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: opacity 0.2s;
        }
        .chessboard-nav-btn:hover {
            opacity: 0.9;
        }
        .chessboard-current-range {
            font-weight: 600;
            color: #2c3e50;
            font-size: 1.1rem;
        }

        /* Шахматка */
        .chessboard-wrapper {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            background: white;
            margin-bottom: 1.5rem;
        }
        .chessboard-table {
            display: grid;
            grid-template-columns: 240px repeat(<?= count($allDates) ?>, 50px);
            min-width: min-content;
        }
        .chessboard-header-cell,
        .room-name-cell {
            position: sticky;
            left: 0;
            z-index: 10;
            background: #f1f3f5;
            font-weight: 600;
            padding: 0.6rem 0.4rem;
            text-align: center;
            border-right: 1px solid #e0e0e0;
            border-bottom: 1px solid #e0e0e0;
            font-size: 0.85rem;
        }
        .chessboard-header-cell {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
        }
        .date-header-cell {
            padding: 0.4rem;
            text-align: center;
            font-size: 0.75rem;
            border-right: 1px solid #f0f0f0;
            border-bottom: 1px solid #f0f0f0;
            background: #f8f9fa;
        }
        .date-header-cell.today {
            background: #ffeaa7;
            font-weight: bold;
        }
        .date-header-cell.weekend {
            background: #fdcb6e;
            color: #2d3436;
        }
        .room-row {
            display: contents;
        }
        .room-cell {
            height: 65px;
            border-right: 1px solid #f0f0f0;
            border-bottom: 1px solid #f0f0f0;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            font-size: 0.7rem;
            position: relative;
            padding: 2px;
            box-sizing: border-box;
        }
        .room-cell.available {
            background: #d5f4e6;
        }
        .room-cell.booked {
            background: #fadbd8;
        }
        .room-cell.checkin {
            background: #d6eaf8;
        }
        .room-cell.checkout {
            background: #fcf3cf;
        }
        .room-cell.same-day {
            background: linear-gradient(135deg, #d6eaf8 50%, #fcf3cf 50%);
        }
        .room-cell.today {
            border: 2px solid #e17055;
        }
        .room-cell .guest-name {
            font-weight: 600;
            font-size: 0.75rem;
            text-align: center;
            line-height: 1.2;
            max-height: 36px;
            overflow: hidden;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            color: #2c3e50;
        }
        .room-cell .price-tag {
            font-size: 0.75rem;
            font-weight: bold;
            color: #27ae60;
            margin-top: 2px;
        }
        .room-cell.checkin::before,
        .room-cell.checkout::after {
            content: '';
            position: absolute;
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }
        .room-cell.checkin::before {
            top: 2px;
            left: 2px;
            background: #3498db;
        }
        .room-cell.checkout::after {
            bottom: 2px;
            right: 2px;
            background: #f1c40f;
        }

        /* Легенда */
        .chessboard-legend {
            display: flex;
            justify-content: center;
            gap: 20px;
            flex-wrap: wrap;
            margin-top: 1rem;
            padding: 1rem;
            background: #f8f9fa;
            border-radius: 12px;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .legend-color {
            width: 16px;
            height: 16px;
            border-radius: 3px;
            border: 1px solid #999;
        }
        .legend-color.available { background: #d5f4e6; }
        .legend-color.booked { background: #fadbd8; }
        .legend-color.checkin { background: #d6eaf8; }
        .legend-color.checkout { background: #fcf3cf; }
        .legend-color.same-day {
            background: linear-gradient(135deg, #d6eaf8 50%, #fcf3cf 50%);
        }

        @media (max-width: 768px) {
            .chessboard-table {
                grid-template-columns: 180px repeat(<?= count($allDates) ?>, 46px);
            }
            .room-cell { height: 60px; font-size: 0.65rem; }
        }
        @media (max-width: 576px) {
            .chessboard-table {
                grid-template-columns: 140px repeat(<?= count($allDates) ?>, 42px);
            }
            .room-cell { height: 55px; font-size: 0.6rem; }
            .room-cell .guest-name { font-size: 0.65rem; }
        }
    </style>
</head>
<body>
    <div class="container py-4">
        <div class="card p-4">
            <div class="chessboard-header">
                <h2 class="mb-0">Шахматка бронирования</h2>
            </div>

            <div class="chessboard-controls">
                <input type="text" id="roomFilter" placeholder="Поиск объекта...">
                <button class="btn btn-outline-secondary" onclick="clearFilter()">Сбросить</button>
            </div>

            <div class="chessboard-navigation">
                <button class="chessboard-nav-btn" onclick="navigate(-1)">← Месяц назад</button>
                <div class="chessboard-current-range" id="currentRange">
                    <?= $russianMonths[$startDate->format('n')] . ' ' . $startDate->format('Y') ?> –
                    <?= $russianMonths[$endDate->format('n')] . ' ' . $endDate->format('Y') ?>
                </div>
                <button class="chessboard-nav-btn" onclick="navigate(1)">Месяц вперед →</button>
            </div>

            <div class="chessboard-wrapper">
                <div class="chessboard-table" id="chessboardTable">
                    <!-- Заголовок -->
                    <div class="chessboard-header-cell">Объекты / Даты</div>
                    <?php foreach ($allDates as $dateStr): ?>
                        <?php
                        $dt = new DateTime($dateStr);
                        $isToday = ($dateStr === $todayStr);
                        $isWeekend = ($dt->format('N') >= 6);
                        $classes = ['date-header-cell'];
                        if ($isToday) $classes[] = 'today';
                        if ($isWeekend) $classes[] = 'weekend';
                        ?>
                        <div class="<?= implode(' ', $classes) ?>">
                            <div><?= $dt->format('j') ?></div>
                            <div><?= $russianWeekdays[(int)$dt->format('N') - 1] ?></div>
                        </div>
                    <?php endforeach; ?>

                    <!-- Строки объектов -->
                    <?php foreach ($objects as $filename => $obj): ?>
                        <div class="room-row" data-room-name="<?= htmlspecialchars($obj['name']) ?>">
                            <div class="room-name-cell"><?= htmlspecialchars($obj['name']) ?></div>
                            <?php foreach ($allDates as $dateStr): ?>
                                <?php
                                $status = 'available';
                                $guestName = '';
                                $totalAmount = 0;
                                $price = null;
                                $isToday = ($dateStr === $todayStr);
                                $cellClasses = ['room-cell'];
                                $isBooked = false;

                                foreach ($obj['booked'] as $range) {
                                    $start = $range['start'];
                                    $end = $range['end'];
                                    $guest = $range['guest'];
                                    $amount = $range['total_amount'];

                                    if ($dateStr === $start && $dateStr === $end) {
                                        $status = 'same-day';
                                        $guestName = $guest;
                                        $totalAmount = $amount;
                                        $isBooked = true;
                                        break;
                                    } elseif ($dateStr === $start) {
                                        $status = 'checkin';
                                        $guestName = $guest;
                                        $totalAmount = $amount;
                                        $isBooked = true;
                                        break;
                                    } elseif ($dateStr === $end) {
                                        $status = 'checkout';
                                        $guestName = $guest;
                                        $totalAmount = $amount;
                                        $isBooked = true;
                                        break;
                                    } elseif ($dateStr > $start && $dateStr < $end) {
                                        $status = 'booked';
                                        $guestName = $guest;
                                        $totalAmount = $amount;
                                        $isBooked = true;
                                        break;
                                    }
                                }

                                if (!$isBooked) {
                                    $price = getPriceForDate($dateStr, $obj['prices']);
                                }

                                $cellClasses[] = $status;
                                if ($isToday) $cellClasses[] = 'today';
                                ?>
                                <div class="<?= implode(' ', $cellClasses) ?>">
                                    <?php if ($isBooked): ?>
                                        <div class="guest-name"><?= htmlspecialchars($guestName) ?></div>
                                        <?php if ($totalAmount > 0): ?>
                                            <div class="price-tag"><?= number_format($totalAmount, 0, '', ' ') ?> ฿</div>
                                        <?php endif; ?>
                                    <?php elseif ($price !== null): ?>
                                        <div class="price-tag"><?= number_format($price, 0, '', ' ') ?> ฿</div>
                                    <?php endif; ?>
                                </div>
                            <?php endforeach; ?>
                        </div>
                    <?php endforeach; ?>
                </div>
            </div>

            <div class="chessboard-legend">
                <div class="legend-item">
                    <div class="legend-color available"></div>
                    <span>Свободно</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color booked"></div>
                    <span>Занято</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color checkin"></div>
                    <span>Заезд</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color checkout"></div>
                    <span>Выезд</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color same-day"></div>
                    <span>Заезд/Выезд</span>
                </div>
            </div>
        </div>
    </div>

    <script>
        console.log("=== Отладка шахматки ===");
        console.log("Объекты:", <?= json_encode($objects, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT) ?>);
        console.log("Все даты:", <?= json_encode($allDates, JSON_UNESCAPED_UNICODE) ?>);
        console.log("Текущая дата:", "<?= $todayStr ?>");

        function clearFilter() {
            document.getElementById('roomFilter').value = '';
            document.querySelectorAll('.room-row').forEach(row => row.style.display = '');
        }

        document.getElementById('roomFilter').addEventListener('input', function() {
            const term = this.value.toLowerCase();
            document.querySelectorAll('.room-row').forEach(row => {
                const name = row.dataset.roomName.toLowerCase();
                row.style.display = name.includes(term) ? '' : 'none';
            });
        });

        function navigate(direction) {
            const url = new URL(window.location);
            const currentStart = url.searchParams.get('start') || '<?= $startDate->format('Y-m-d') ?>';
            const date = new Date(currentStart);
            date.setMonth(date.getMonth() + direction);
            url.searchParams.set('start', date.toISOString().split('T')[0]);
            window.location.href = url.toString();
        }
    </script>
</body>
</html>