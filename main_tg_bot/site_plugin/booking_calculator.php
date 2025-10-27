<?php
function readBookedDates($filePath) {
    $booked = [];
    if (!file_exists($filePath)) return $booked;
    if (($handle = fopen($filePath, "r")) !== false) {
        fgetcsv($handle); // пропускаем заголовок
        while (($row = fgetcsv($handle, 1000, ",")) !== false) {
            if (count($row) >= 4) {
                $checkInStr = trim($row[2]); // Заезд
                $checkOutStr = trim($row[3]); // Выезд
                $checkIn = DateTime::createFromFormat('d.m.Y', $checkInStr);
                $checkOut = DateTime::createFromFormat('d.m.Y', $checkOutStr);
                if ($checkIn && $checkOut) {
                    // Выезд — день отъезда, не входит в проживание
                    // Заняты ночи: [заезд, выезд)
                    $booked[] = [
                        'start' => $checkIn->format('d.m.Y'),
                        'end'   => $checkOut->format('d.m.Y')
                    ];
                }
            }
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
        fgetcsv($handle);
        while (($row = fgetcsv($handle, 1000, ",")) !== false) {
            if (count($row) >= 4) {
                $monthName = mb_strtolower(trim($row[0]), 'UTF-8');
                $startDay = intval(trim($row[1]));
                $endDay = intval(trim($row[2]));
                $price = intval(trim($row[3]));
                if (isset($monthMap[$monthName]) && $startDay > 0 && $endDay >= $startDay && $price > 0) {
                    $priceData[] = [
                        "startMonth" => $monthMap[$monthName],
                        "endMonth" => $monthMap[$monthName],
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

$bookingFilesPath = __DIR__ . '/booking_files/*.csv';
$files = glob($bookingFilesPath);

$bookedData = [];
$priceData = [];

if (!empty($files)) {
    foreach ($files as $file) {
        $filename = pathinfo($file, PATHINFO_FILENAME);
        $bookedData[$filename] = readBookedDates($file);
        $priceFile = __DIR__ . "/task_files/{$filename}_price.csv";
        $priceData[$filename] = readPriceData($priceFile);
    }
}
?>

<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Расчет стоимости бронирования</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css" rel="stylesheet">
    <style>
        .container { max-width: 800px; }
        .card {
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border: none;
            border-radius: 10px;
        }
        .flatpickr-day.booked {
            background-color: #dc3545 !important;
            color: white !important;
            border-color: #dc3545 !important;
        }
        .flatpickr-day.booked:hover {
            background-color: #bb2d3b !important;
        }
        .result-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .form-label { font-weight: 500; }
        .legend {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 10px;
            font-size: 14px;
        }
        .legend-color {
            width: 16px;
            height: 16px;
            border-radius: 2px;
        }
        .legend-occupied { background-color: #dc3545; }
    </style>
</head>
<body class="bg-light">
    <div class="container py-5">
        <div class="row justify-content-center">
            <div class="col-12">
                <div class="card p-4 mb-4">
                    <h2 class="text-center mb-4">Калькулятор стоимости бронирования</h2>

                    <form id="bookingForm">
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label for="objectSelect" class="form-label">Объект недвижимости</label>
                                <select class="form-select" id="objectSelect" required>
                                    <option value="">Выберите объект...</option>
                                    <?php if (empty($files)): ?>
                                        <option value="">Файлы не найдены</option>
                                    <?php else: ?>
                                        <?php foreach ($files as $file): ?>
                                            <?php
                                            $filename = pathinfo($file, PATHINFO_FILENAME);
                                            $displayName = ucwords(str_replace('_', ' ', $filename));
                                            ?>
                                            <option value="<?= htmlspecialchars($filename) ?>"><?= htmlspecialchars($displayName) ?></option>
                                        <?php endforeach; ?>
                                    <?php endif; ?>
                                </select>
                            </div>

                            <div class="col-md-6 mb-3">
                                <label for="dateRange" class="form-label">Период бронирования</label>
                                <div class="legend">
                                    <div class="legend-color legend-occupied"></div>
                                    <span>🔴 — занято (ночь забронирована)</span>
                                </div>
                                <input type="text" class="form-control" id="dateRange" placeholder="Выберите даты..." readonly required>
                            </div>
                        </div>

                        <div class="text-center mt-4">
                            <button type="submit" class="btn btn-primary btn-lg px-5">Рассчитать стоимость</button>
                        </div>
                    </form>
                </div>

                <div id="resultSection" class="card result-card p-4" style="display: none;">
                    <h3 class="text-center mb-3">Результат расчета</h3>
                    <div class="text-center">
                        <h4 id="totalAmount" class="display-4 fw-bold mb-3">0 ₽</h4>
                        <p id="periodInfo" class="mb-2"></p>
                        <p id="nightsInfo" class="mb-0"></p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>
    <script src="https://cdn.jsdelivr.net/npm/flatpickr/dist/l10n/ru.js"></script>

    <script>
        const allBookedData = <?= json_encode($bookedData, JSON_UNESCAPED_UNICODE) ?>;
        const allPriceData = <?= json_encode($priceData, JSON_UNESCAPED_UNICODE) ?>;

        let bookedRanges = [];
        let pricePeriods = [];
        let datePicker;

        function parseDate(str) {
            const [d, m, y] = str.split('.').map(Number);
            return new Date(y, m - 1, d);
        }

        function formatDate(date) {
            return date.toLocaleDateString('ru-RU', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric'
            });
        }

        function parseDateFromString(dateStr) {
            const months = {
                'января': 0, 'февраля': 1, 'марта': 2, 'апреля': 3,
                'мая': 4, 'июня': 5, 'июля': 6, 'августа': 7,
                'сентября': 8, 'октября': 9, 'ноября': 10, 'декабря': 11
            };
            const parts = dateStr.split(' ');
            if (parts.length === 3) {
                const day = parseInt(parts[0]);
                const month = months[parts[1]];
                const year = parseInt(parts[2]);
                return new Date(year, month, day);
            }
            return null;
        }

        function isDateBooked(dateToCheck) {
            for (const range of bookedRanges) {
                const start = parseDate(range.start);
                const end = parseDate(range.end);
                // Занята ночь, если: start <= date < end
                if (dateToCheck >= start && dateToCheck < end) {
                    return true;
                }
            }
            return false;
        }

        function updateCalendarStyles() {
            setTimeout(() => {
                const days = document.querySelectorAll('.flatpickr-day');
                days.forEach(day => {
                    const dateStr = day.getAttribute('aria-label');
                    if (!dateStr) return;
                    const date = parseDateFromString(dateStr);
                    const booked = date && isDateBooked(date);
                    day.classList.toggle('booked', booked);
                });
            }, 50);
        }

        function updateDatePickerDisable() {
            const disableList = [];
            for (const range of bookedRanges) {
                let current = parseDate(range.start);
                const end = parseDate(range.end);
                while (current < end) { // < end, а не <=
                    disableList.push(new Date(current));
                    current.setDate(current.getDate() + 1);
                }
            }
            datePicker.set('disable', disableList);
        }

        function calculateTotalCost(startDate, endDate) {
            let total = 0;
            let current = new Date(startDate);
            while (current < endDate) {
                const month = current.getMonth() + 1;
                const day = current.getDate();
                let price = 0;
                for (const p of pricePeriods) {
                    if (p.startMonth === month && day >= p.startDay && day <= p.endDay) {
                        price = p.price;
                        break;
                    }
                }
                total += price;
                current.setDate(current.getDate() + 1);
            }
            return total;
        }

        document.getElementById('objectSelect').addEventListener('change', function () {
            const obj = this.value;
            bookedRanges = allBookedData[obj] || [];
            pricePeriods = allPriceData[obj] || [];
            updateDatePickerDisable();
            updateCalendarStyles();
        });

        document.getElementById('bookingForm').addEventListener('submit', function (e) {
            e.preventDefault();
            const dates = datePicker.selectedDates;
            if (dates.length !== 2) {
                alert('Выберите период бронирования');
                return;
            }
            const startDate = dates[0];
            const endDate = dates[1];
            const nights = Math.ceil((endDate - startDate) / (1000 * 60 * 60 * 24));
            const totalCost = calculateTotalCost(startDate, endDate);

            document.getElementById('totalAmount').textContent = totalCost.toLocaleString('ru-RU') + ' бат';
            document.getElementById('periodInfo').textContent =
                `Период: ${formatDate(startDate)} – ${formatDate(endDate)}`;
            document.getElementById('nightsInfo').textContent = `Количество ночей: ${nights}`;
            document.getElementById('resultSection').style.display = 'block';
        });

        document.addEventListener('DOMContentLoaded', () => {
            datePicker = flatpickr("#dateRange", {
                mode: "range",
                locale: "ru",
                minDate: "today",
                dateFormat: "d.m.Y",
                disable: [],
                onChange: updateCalendarStyles,
                onMonthChange: updateCalendarStyles,
                onYearChange: updateCalendarStyles
            });
        });
    </script>
</body>
</html>