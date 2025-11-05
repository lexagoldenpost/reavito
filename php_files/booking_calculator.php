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
        .container { max-width: 1200px; }
        .card {
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border: none;
            border-radius: 15px;
            transition: all 0.3s ease;
        }
        .card.collapsed {
            max-height: 80px;
            overflow: hidden;
        }

        /* Занятые даты */
        .flatpickr-day.booked {
            background-color: #ffb347 !important;
            color: white !important;
            border-color: #ffb347 !important;
        }
        .flatpickr-day.booked:hover {
            background-color: #ff9a1f !important;
        }

        /* Доступные для стыковки: день выезда или заезда существующей брони */
        .flatpickr-day.available-checkout,
        .flatpickr-day.available-checkin {
            background-color: #e8f5e9 !important;
            color: #2e7d32 !important;
            border: 1px solid #a5d6a7 !important;
        }
        .flatpickr-day.available-checkout:hover,
        .flatpickr-day.available-checkin:hover {
            background-color: #c8e6c9 !important;
        }

        /* Исправляем стили дат следующего/предыдущего месяца */
        .flatpickr-day.flatpickr-disabled,
        .flatpickr-day.prevMonthDay,
        .flatpickr-day.nextMonthDay {
            color: #2c3e50 !important;
            opacity: 1 !important;
        }

        .flatpickr-day.flatpickr-disabled.booked,
        .flatpickr-day.prevMonthDay.booked,
        .flatpickr-day.nextMonthDay.booked {
            background-color: #ffb347 !important;
            color: white !important;
            border-color: #ffb347 !important;
        }

        .result-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }

        .calculator-form-container {
            display: grid;
            grid-template-columns: 2fr 3fr 1fr;
            gap: 15px;
            align-items: end;
            width: 100%;
        }

        .form-field {
            display: flex;
            flex-direction: column;
            width: 100%;
        }

        .form-field label {
            font-size: 14px;
            margin-bottom: 8px;
            color: #333;
            font-weight: 600;
        }

        .form-field input,
        .form-field select {
            padding: 14px;
            border: 1px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
            width: 100%;
            transition: border-color 0.3s;
            height: 48px;
            box-sizing: border-box;
        }

        .form-field input:focus,
        .form-field select:focus {
            border-color: #2980b9;
            outline: none;
            box-shadow: 0 0 0 2px rgba(41, 128, 185, 0.1);
        }

        .form-field-nights {
            display: flex;
            flex-direction: column;
            width: 100%;
        }

        .form-field-nights label {
            font-size: 14px;
            margin-bottom: 8px;
            color: #333;
            font-weight: 600;
        }

        .form-field-nights input {
            padding: 14px;
            border: 1px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
            width: 100%;
            background: #f8f9fa;
            color: #2980b9;
            font-weight: 600;
            cursor: not-allowed;
            height: 48px;
            box-sizing: border-box;
        }

        .date-fields-container {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 15px;
            align-items: end;
        }

        .calculate-btn-container {
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
            height: 100%;
        }

        .calculate-btn {
            background: linear-gradient(135deg, #2980b9, #1a5276);
            color: white;
            border: none;
            padding: 14px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 15px;
            font-weight: 600;
            transition: all 0.3s;
            height: 48px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 2px 8px rgba(41, 128, 185, 0.3);
            width: 100%;
        }

        .calculate-btn:hover {
            background: linear-gradient(135deg, #1a5276, #154360);
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(41, 128, 185, 0.4);
        }

        .calculate-btn:disabled {
            background: #95a5a6;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }

        .total-with-discount {
            background: rgba(255, 255, 255, 0.15);
            border-radius: 12px;
            padding: 20px;
            margin-top: 15px;
            border: 2px solid rgba(255, 255, 255, 0.2);
        }

        .discount-controls {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 15px;
            flex-wrap: wrap;
        }

        .discount-badge {
            background: linear-gradient(135deg, #28a745, #20c997);
            color: white;
            padding: 8px 16px;
            border-radius: 25px;
            font-weight: 600;
            font-size: 14px;
        }

        .final-price {
            text-align: center;
        }

        .original-price {
            font-size: 16px;
            opacity: 0.8;
            text-decoration: line-through;
            margin-bottom: 5px;
        }

        .final-amount {
            font-size: 2.2rem;
            font-weight: 700;
            margin: 10px 0;
        }

        .price-calendar-section {
            background: white;
            border-radius: 12px;
            padding: 25px;
            margin-top: 25px;
            color: #333;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
        }

        .calendar-month {
            margin-bottom: 30px;
        }

        .calendar-month-title {
            text-align: center;
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 15px;
            font-size: 18px;
            padding-bottom: 10px;
            border-bottom: 2px solid #f8f9fa;
        }

        .calendar-grid {
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 5px;
        }

        .calendar-day {
            padding: 8px 3px;
            text-align: center;
            border-radius: 6px;
            background: #f8f9fa;
            position: relative;
            min-height: 60px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            font-size: 13px;
        }

        .calendar-day.selected {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
        }

        .calendar-day.booked {
            background: #ffb347 !important;
            color: white !important;
        }

        .calendar-day-price {
            font-size: 10px;
            font-weight: 600;
            color: #28a745;
            margin-top: 3px;
        }

        .calendar-day.selected .calendar-day-price {
            color: #fff;
        }

        .calendar-day.booked .calendar-day-price {
            color: #fff !important;
            text-decoration: line-through;
        }

        .calendar-day-header {
            text-align: center;
            font-weight: 600;
            color: #6c757d;
            font-size: 11px;
            padding: 6px 3px;
            background: #e9ecef;
            border-radius: 4px;
        }

        .booking-summary-compact {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
            margin-bottom: 20px;
            background: rgba(255, 255, 255, 0.1);
            padding: 15px;
            border-radius: 10px;
        }

        .summary-item {
            text-align: center;
        }

        .summary-item h6 {
            font-size: 12px;
            opacity: 0.8;
            margin-bottom: 5px;
            font-weight: 500;
        }

        .summary-item p {
            font-size: 14px;
            font-weight: 600;
            margin: 0;
        }

        .expand-form-btn {
            background: rgba(255, 255, 255, 0.2);
            border: none;
            color: white;
            padding: 5px 12px;
            border-radius: 15px;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-left: 10px;
        }

        .expand-form-btn:hover {
            background: rgba(255, 255, 255, 0.3);
        }

        .input-group-discount {
            max-width: 120px;
        }

        .input-group-discount .form-control {
            text-align: center;
            font-weight: 600;
        }

        .auto-discount-badge {
            background: linear-gradient(135deg, #ff6b6b, #ee5a24);
            color: white;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            margin-left: 8px;
        }

        .price-comparison {
            text-align: center;
            margin: 15px 0;
        }

        @media (max-width: 1024px) {
            .calculator-form-container {
                grid-template-columns: 1fr 1fr;
                gap: 15px;
            }
            .calculate-btn-container {
                grid-column: span 2;
            }
            .date-fields-container {
                grid-column: span 2;
                grid-template-columns: 1fr 1fr 1fr;
            }
        }

        @media (max-width: 768px) {
            .calculator-form-container {
                grid-template-columns: 1fr;
                gap: 15px;
            }
            .calculate-btn-container {
                grid-column: span 1;
            }
            .date-fields-container {
                grid-column: span 1;
                grid-template-columns: 1fr;
            }
        }

        @media (max-width: 480px) {
            .container {
                padding: 10px;
            }
            .card {
                padding: 15px !important;
            }
            .calculator-form-container {
                gap: 10px;
            }
        }
    </style>
</head>
<body class="bg-light">
    <div class="container py-5">
        <div class="row justify-content-center">
            <div class="col-12">
                <div id="bookingFormCard" class="card p-4 mb-4">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h2 class="text-center mb-0" style="flex: 1;">Калькулятор стоимости бронирования</h2>
                        <button type="button" class="btn btn-sm btn-outline-secondary" onclick="toggleBookingForm()" id="toggleFormBtn">
                            ▲
                        </button>
                    </div>

                    <form id="bookingForm">
                        <div class="calculator-form-container">
                            <div class="form-field">
                                <label for="objectSelect">Объект недвижимости</label>
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

                            <div class="date-fields-container">
                                <div class="form-field">
                                    <label for="checkin">Дата заезда</label>
                                    <input type="text" id="checkin" placeholder="Выберите дату" readonly />
                                </div>
                                <div class="form-field">
                                    <label for="checkout">Дата выезда</label>
                                    <input type="text" id="checkout" placeholder="Выберите дату" readonly />
                                </div>
                                <div class="form-field-nights">
                                    <label for="nights">Ночей</label>
                                    <input type="text" id="nights" placeholder="0" readonly />
                                </div>
                            </div>

                            <div class="calculate-btn-container">
                                <button type="submit" class="calculate-btn">
                                    Рассчитать стоимость
                                </button>
                            </div>
                        </div>
                    </form>
                </div>

                <div id="resultSection" class="card result-card p-4" style="display: none;">
                    <h3 class="text-center mb-3">Результат расчета</h3>

                    <div class="booking-summary-compact">
                        <div class="summary-item">
                            <h6>Объект</h6>
                            <p id="resultObjectName">-</p>
                        </div>
                        <div class="summary-item" style="cursor: pointer;" onclick="toggleBookingForm()">
                            <h6>Период бронирования</h6>
                            <p id="resultPeriodInfo">
                                -
                                <span class="expand-form-btn">✏️</span>
                            </p>
                        </div>
                        <div class="summary-item">
                            <h6>Количество ночей</h6>
                            <p id="resultNightsInfo">0</p>
                        </div>
                    </div>

                    <div class="price-comparison">
                        <div class="original-price" id="originalPrice">0 ฿ без скидки</div>
                        <div class="final-amount" id="finalAmount">0 ฿</div>
                    </div>

                    <div class="total-with-discount">
                        <div class="discount-controls">
                            <label class="form-label mb-0">Скидка:</label>
                            <div class="input-group input-group-discount">
                                <input type="number" class="form-control" id="discountInput"
                                       min="0" max="100" value="0" step="1">
                                <span class="input-group-text">%</span>
                            </div>
                            <div class="discount-badge">
                                Скидка: <span id="discountValue">0</span>%
                                <span id="autoDiscountBadge" class="auto-discount-badge" style="display: none;">Авто</span>
                            </div>
                        </div>
                    </div>

                    <div id="priceCalendar" class="price-calendar-section" style="display: none;">
                        <h5 class="text-center mb-4">📅 Стоимость по дням</h5>
                        <div id="calendarContainer"></div>
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
        let fpCheckin = null;
        let fpCheckout = null;
        let currentBreakdown = [];
        let selectedStartDate = null;
        let selectedEndDate = null;
        let currentObjectName = '';
        let isFormCollapsed = false;
        let originalTotalCost = 0;

        function toggleBookingForm() {
            const formCard = document.getElementById('bookingFormCard');
            const toggleBtn = document.getElementById('toggleFormBtn');

            if (isFormCollapsed) {
                formCard.classList.remove('collapsed');
                toggleBtn.innerHTML = '▲';
                toggleBtn.classList.remove('btn-secondary');
                toggleBtn.classList.add('btn-outline-secondary');
            } else {
                formCard.classList.add('collapsed');
                toggleBtn.innerHTML = '▼';
                toggleBtn.classList.remove('btn-outline-secondary');
                toggleBtn.classList.add('btn-secondary');
            }
            isFormCollapsed = !isFormCollapsed;
        }

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

        function getBookedDatesArray() {
            const bookedDates = [];
            for (const range of bookedRanges) {
                let current = parseDate(range.start);
                const end = parseDate(range.end);
                while (current < end) {
                    bookedDates.push(current.toISOString().split('T')[0]);
                    current.setDate(current.getDate() + 1);
                }
            }
            return bookedDates;
        }

        function getCheckoutDates() {
            const dates = new Set();
            for (const range of bookedRanges) {
                const d = parseDate(range.end);
                dates.add(d.toISOString().split('T')[0]);
            }
            return dates;
        }

        function getCheckinDates() {
            const dates = new Set();
            for (const range of bookedRanges) {
                const d = parseDate(range.start);
                dates.add(d.toISOString().split('T')[0]);
            }
            return dates;
        }

        function isDateBooked(dateToCheck) {
            const dateStr = dateToCheck.toISOString().split('T')[0];
            return getBookedDatesArray().includes(dateStr);
        }

        function getPriceForDate(date) {
            const month = date.getMonth() + 1;
            const day = date.getDate();
            for (const p of pricePeriods) {
                if (p.startMonth === month && day >= p.startDay && day <= p.endDay) {
                    return p.price;
                }
            }
            return 0;
        }

        function updateNights() {
            const checkin = document.getElementById('checkin').value;
            const checkout = document.getElementById('checkout').value;
            if (checkin && checkout) {
                const start = new Date(checkin);
                const end = new Date(checkout);
                const diffTime = end - start;
                const nights = Math.floor(diffTime / (1000 * 60 * 60 * 24));
                document.getElementById('nights').value = nights > 0 ? nights + ' ' + getNightsText(nights) : '0 ночей';
            } else {
                document.getElementById('nights').value = '0 ночей';
            }
        }

        function getNightsText(nights) {
            if (nights === 1) return 'ночь';
            if (nights >= 2 && nights <= 4) return 'ночи';
            return 'ночей';
        }

        function initCalendars() {
            if (fpCheckin) fpCheckin.destroy();
            if (fpCheckout) fpCheckout.destroy();

            fpCheckin = flatpickr("#checkin", {
                dateFormat: "Y-m-d",
                minDate: "today",
                disableMobile: true,
                locale: "ru",
                onChange: function(selectedDates) {
                    updateNights();
                    if (selectedDates.length > 0) {
                        const nextDay = new Date(selectedDates[0]);
                        nextDay.setDate(nextDay.getDate() + 1);
                        fpCheckout.set("minDate", nextDay);
                        if (fpCheckout.selectedDates[0] && fpCheckout.selectedDates[0] <= selectedDates[0]) {
                            fpCheckout.clear();
                            updateNights();
                        }
                    }
                },
                onDayCreate: function(dObj, dStr, fp, dayElem) {
                    const date = new Date(dayElem.dateObj);
                    const dateStr = date.toISOString().split('T')[0];
                    const booked = getBookedDatesArray();
                    const checkouts = getCheckoutDates();
                    const checkins = getCheckinDates();

                    dayElem.classList.remove('booked', 'available-checkout', 'available-checkin');

                    if (booked.includes(dateStr)) {
                        dayElem.classList.add('booked');
                        dayElem.title = 'Занято';
                    } else if (checkouts.has(dateStr)) {
                        dayElem.classList.add('available-checkout');
                        dayElem.title = 'Можно заехать (после выезда)';
                    } else if (checkins.has(dateStr)) {
                        dayElem.classList.add('available-checkin');
                        dayElem.title = 'Можно выехать (до заезда)';
                    }
                }
            });

            fpCheckout = flatpickr("#checkout", {
                dateFormat: "Y-m-d",
                minDate: "today",
                disableMobile: true,
                locale: "ru",
                onChange: function(selectedDates) {
                    updateNights();
                    if (selectedDates.length > 0) {
                        const prevDay = new Date(selectedDates[0]);
                        prevDay.setDate(prevDay.getDate() - 1);
                        fpCheckin.set("maxDate", prevDay);
                    }
                },
                onDayCreate: function(dObj, dStr, fp, dayElem) {
                    const date = new Date(dayElem.dateObj);
                    const dateStr = date.toISOString().split('T')[0];
                    const booked = getBookedDatesArray();
                    const checkouts = getCheckoutDates();
                    const checkins = getCheckinDates();

                    dayElem.classList.remove('booked', 'available-checkout', 'available-checkin');

                    if (booked.includes(dateStr)) {
                        dayElem.classList.add('booked');
                        dayElem.title = 'Занято';
                    } else if (checkouts.has(dateStr)) {
                        dayElem.classList.add('available-checkout');
                        dayElem.title = 'Можно заехать (после выезда)';
                    } else if (checkins.has(dateStr)) {
                        dayElem.classList.add('available-checkin');
                        dayElem.title = 'Можно выехать (до заезда)';
                    }
                }
            });

            document.getElementById('checkin').disabled = true;
            document.getElementById('checkout').disabled = true;
        }

        function calculateTotalCost(startDate, endDate) {
            let total = 0;
            let current = new Date(startDate);
            currentBreakdown = [];
            while (current < endDate) {
                const price = getPriceForDate(current);
                total += price;
                currentBreakdown.push({
                    date: new Date(current),
                    price: price,
                    booked: isDateBooked(current)
                });
                current.setDate(current.getDate() + 1);
            }
            return total;
        }

        function updateDiscount() {
            const discount = parseInt(document.getElementById('discountInput').value) || 0;
            document.getElementById('discountValue').textContent = discount;
            if (discount > 0 && discount <= 100) {
                const discountAmount = originalTotalCost * discount / 100;
                const finalAmount = originalTotalCost - discountAmount;
                document.getElementById('originalPrice').textContent = originalTotalCost.toLocaleString('ru-RU') + ' ฿ без скидки';
                document.getElementById('finalAmount').textContent = finalAmount.toLocaleString('ru-RU') + ' ฿';
            } else {
                document.getElementById('originalPrice').textContent = '';
                document.getElementById('finalAmount').textContent = originalTotalCost.toLocaleString('ru-RU') + ' ฿';
            }
        }

        function applyAutoDiscount(nights) {
            const autoDiscountBadge = document.getElementById('autoDiscountBadge');
            if (nights >= 27) {
                document.getElementById('discountInput').value = 10;
                autoDiscountBadge.style.display = 'inline';
            } else {
                document.getElementById('discountInput').value = 0;
                autoDiscountBadge.style.display = 'none';
            }
            updateDiscount();
        }

        function generatePriceCalendar() {
            const container = document.getElementById('calendarContainer');
            container.innerHTML = '';
            if (!selectedStartDate || !selectedEndDate) return;

            const startMonth = new Date(selectedStartDate.getFullYear(), selectedStartDate.getMonth(), 1);
            const endMonth = new Date(selectedEndDate.getFullYear(), selectedEndDate.getMonth(), 1);
            let currentMonth = new Date(startMonth);

            while (currentMonth <= endMonth) {
                const year = currentMonth.getFullYear();
                const month = currentMonth.getMonth();
                const monthName = currentMonth.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' });

                const monthElement = document.createElement('div');
                monthElement.className = 'calendar-month';
                const titleElement = document.createElement('div');
                titleElement.className = 'calendar-month-title';
                titleElement.textContent = monthName.charAt(0).toUpperCase() + monthName.slice(1);
                monthElement.appendChild(titleElement);

                const gridElement = document.createElement('div');
                gridElement.className = 'calendar-grid';
                const weekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
                weekdays.forEach(day => {
                    const dayHeader = document.createElement('div');
                    dayHeader.className = 'calendar-day-header';
                    dayHeader.textContent = day;
                    gridElement.appendChild(dayHeader);
                });

                const firstDayOfMonth = new Date(year, month, 1);
                const firstWeekday = firstDayOfMonth.getDay();
                const offset = firstWeekday === 0 ? 6 : firstWeekday - 1;
                for (let j = 0; j < offset; j++) {
                    const emptyDay = document.createElement('div');
                    emptyDay.className = 'calendar-day';
                    gridElement.appendChild(emptyDay);
                }

                const daysInMonth = new Date(year, month + 1, 0).getDate();
                for (let day = 1; day <= daysInMonth; day++) {
                    const currentDate = new Date(year, month, day);
                    const isSelected = currentDate >= selectedStartDate && currentDate < selectedEndDate;
                    const isBooked = isDateBooked(currentDate);
                    const price = getPriceForDate(currentDate);

                    const dayElement = document.createElement('div');
                    dayElement.className = 'calendar-day';
                    if (isSelected) dayElement.classList.add('selected');
                    if (isBooked) dayElement.classList.add('booked');

                    if (price > 0) {
                        dayElement.innerHTML = `<div>${day}</div><div class="calendar-day-price">${price} ฿</div>`;
                    } else {
                        dayElement.innerHTML = `<div>${day}</div><div class="calendar-day-price"></div>`;
                    }
                    gridElement.appendChild(dayElement);
                }

                const totalCells = offset + daysInMonth;
                const remainingCells = 7 - (totalCells % 7);
                if (remainingCells < 7) {
                    for (let j = 0; j < remainingCells; j++) {
                        const emptyDay = document.createElement('div');
                        emptyDay.className = 'calendar-day';
                        gridElement.appendChild(emptyDay);
                    }
                }

                monthElement.appendChild(gridElement);
                container.appendChild(monthElement);
                currentMonth.setMonth(currentMonth.getMonth() + 1);
            }

            document.getElementById('priceCalendar').style.display = 'block';
        }

        function checkDateConflict(startDate, endDate) {
            const bookedDates = getBookedDatesArray();
            let currentDate = new Date(startDate);
            while (currentDate < endDate) {
                const currentDateStr = currentDate.toISOString().split('T')[0];
                if (bookedDates.includes(currentDateStr)) return currentDateStr;
                currentDate.setDate(currentDate.getDate() + 1);
            }
            return null;
        }

        document.getElementById('objectSelect').addEventListener('change', function () {
            const obj = this.value;
            bookedRanges = allBookedData[obj] || [];
            pricePeriods = allPriceData[obj] || [];
            currentObjectName = this.options[this.selectedIndex].text;

            document.getElementById('checkin').disabled = false;
            document.getElementById('checkout').disabled = false;

            if (fpCheckin) fpCheckin.redraw();
            if (fpCheckout) fpCheckout.redraw();
            updateNights();
        });

        document.getElementById('discountInput').addEventListener('input', updateDiscount);

        document.getElementById('bookingForm').addEventListener('submit', function (e) {
            e.preventDefault();
            const checkin = document.getElementById('checkin').value;
            const checkout = document.getElementById('checkout').value;
            if (!checkin || !checkout) {
                alert('Выберите даты заезда и выезда');
                return;
            }

            selectedStartDate = new Date(checkin);
            selectedEndDate = new Date(checkout);
            const nights = Math.ceil((selectedEndDate - selectedStartDate) / (1000 * 60 * 60 * 24));
            if (nights <= 0) {
                alert('Дата выезда должна быть позже даты заезда');
                return;
            }

            const conflictDate = checkDateConflict(selectedStartDate, selectedEndDate);
            if (conflictDate) {
                alert('Выбранный период содержит забронированные даты (' + formatDate(new Date(conflictDate)) + '). Пожалуйста, выберите другой период.');
                return;
            }

            originalTotalCost = calculateTotalCost(selectedStartDate, selectedEndDate);
            document.getElementById('resultObjectName').textContent = currentObjectName;
            document.getElementById('resultPeriodInfo').innerHTML =
                `${formatDate(selectedStartDate)} – ${formatDate(selectedEndDate)}
                 <span class="expand-form-btn">✏️</span>`;
            document.getElementById('resultNightsInfo').textContent = nights;

            applyAutoDiscount(nights);
            updateDiscount();
            generatePriceCalendar();
            document.getElementById('resultSection').style.display = 'block';
            if (!isFormCollapsed) toggleBookingForm();
            document.getElementById('resultSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
        });

        document.addEventListener('DOMContentLoaded', () => {
            initCalendars();
            updateNights();
        });
    </script>
</body>
</html>