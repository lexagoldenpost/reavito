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
$checkoutDates = [];
$checkinDates = [];
$priceData = [];

if (!empty($files)) {
    foreach ($files as $file) {
        $filename = pathinfo($file, PATHINFO_FILENAME);
        $bookings = readBookedDates($file);
        $bookedData[$filename] = $bookings;

        $checkouts = [];
        $checkins = [];
        foreach ($bookings as $b) {
            $checkouts[] = $b['end'];
            $checkins[] = $b['start'];
        }
        $checkoutDates[$filename] = array_unique($checkouts);
        $checkinDates[$filename] = array_unique($checkins);

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

        .calendar-info {
            background: linear-gradient(135deg, #f8f9fa, #e9ecef);
            border-radius: 10px;
        }

        .example-booking {
            font-size: 12px;
            border: 1px dashed #28a745 !important;
        }

        .calendar-day.selected {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            position: relative;
        }

        .calendar-day.checkout-day {
            background: linear-gradient(135deg, #e8f5e9, #c8e6c9);
            color: #2e7d32;
            border: 1px dashed #28a745;
        }

        .legend {
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-top: 15px;
            flex-wrap: wrap;
        }

        .legend-item {
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 12px;
        }

        .legend-color {
            width: 15px;
            height: 15px;
            border-radius: 3px;
        }

        .legend-color.night {
            background: linear-gradient(135deg, #667eea, #764ba2);
        }

        .legend-color.checkout {
            background: linear-gradient(135deg, #e8f5e9, #c8e6c9);
            border: 1px dashed #28a745;
        }

        .flatpickr-day.booked {
            background-color: #ffb347 !important;
            color: white !important;
            border-color: #ffb347 !important;
        }
        .flatpickr-day.booked:hover {
            background-color: #ff9a1f !important;
        }

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

        /* Обновленные стили для компактной таблицы цен */
        .compact-price-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }

        .month-price-card {
            background: linear-gradient(135deg, #f8f9fa, #e9ecef);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #e0e0e0;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }

        .month-price-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
            border-color: #667eea;
        }

        .month-price-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(135deg, #667eea, #764ba2);
        }

        .month-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid rgba(102, 126, 234, 0.1);
        }

        .month-name {
            font-weight: 700;
            font-size: 18px;
            color: #2c3e50;
            margin: 0;
        }

        .month-periods {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .period-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 12px;
            background: white;
            border-radius: 8px;
            border-left: 4px solid #28a745;
            transition: all 0.2s ease;
        }

        .period-item:hover {
            background: #f8f9fa;
            transform: translateX(5px);
        }

        .period-range {
            font-size: 14px;
            color: #6c757d;
            font-weight: 500;
        }

        .period-price {
            font-weight: 700;
            font-size: 16px;
            color: #28a745;
            background: rgba(40, 167, 69, 0.1);
            padding: 4px 10px;
            border-radius: 6px;
        }

        .no-price-data {
            text-align: center;
            color: #6c757d;
            font-style: italic;
            padding: 40px 20px;
            background: #f8f9fa;
            border-radius: 12px;
            border: 2px dashed #dee2e6;
        }

        .no-price-data i {
            font-size: 48px;
            margin-bottom: 15px;
            display: block;
            color: #adb5bd;
        }

        .price-card-highlight {
            background: linear-gradient(135deg, #fff3cd, #ffeaa7);
            border-color: #ffc107;
        }

        .price-card-highlight::before {
            background: linear-gradient(135deg, #ffc107, #e0a800);
        }

        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            cursor: pointer;
        }

        .section-header h5 {
            margin: 0;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .toggle-section-btn {
            background: none;
            border: none;
            font-size: 20px;
            color: #667eea;
            cursor: pointer;
            transition: transform 0.3s ease;
        }

        .toggle-section-btn.collapsed {
            transform: rotate(-90deg);
        }

        .collapsible-section {
            transition: all 0.3s ease;
            overflow: hidden;
        }

        .collapsible-section.collapsed {
            max-height: 0;
            opacity: 0;
            margin: 0;
            padding: 0;
        }

        /* Анимации */
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .month-price-card {
            animation: fadeInUp 0.5s ease-out;
        }

        .month-price-card:nth-child(odd) {
            animation-delay: 0.1s;
        }

        .month-price-card:nth-child(even) {
            animation-delay: 0.2s;
        }

        /* Адаптивность для мобильных */
        @media (max-width: 768px) {
            .compact-price-grid {
                grid-template-columns: 1fr;
                gap: 12px;
            }
            
            .month-price-card {
                padding: 15px;
            }
            
            .month-header {
                flex-direction: column;
                align-items: flex-start;
                gap: 8px;
            }
            
            .month-name {
                font-size: 16px;
            }
            
            .period-item {
                padding: 6px 10px;
            }
            
            .period-range {
                font-size: 13px;
            }
            
            .period-price {
                font-size: 14px;
                padding: 3px 8px;
            }

            .calculator-form-container {
                grid-template-columns: 1fr 1fr;
            }
            .calculate-btn-container {
                grid-column: span 2;
            }
            .date-fields-container {
                grid-column: span 2;
                grid-template-columns: 1fr 1fr 1fr;
            }
        }

        @media (max-width: 480px) {
            .compact-price-grid {
                gap: 10px;
            }
            
            .month-price-card {
                padding: 12px;
            }
            
            .period-item {
                flex-direction: column;
                align-items: flex-start;
                gap: 5px;
            }
            
            .period-price {
                align-self: flex-end;
            }

            .calculator-form-container {
                grid-template-columns: 1fr;
            }
            .calculate-btn-container {
                grid-column: span 1;
            }
            .date-fields-container {
                grid-column: span 1;
                grid-template-columns: 1fr;
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
                        <div class="section-header" onclick="toggleSection('priceListSection')">
                            <h5>💰 Стоимость по месяцам</h5>
                            <button type="button" class="toggle-section-btn collapsed" id="togglePriceListBtn">▼</button>
                        </div>
                        
                        <div id="priceListSection" class="collapsible-section collapsed">
                            <div id="priceListContainer"></div>
                        </div>

                        <div class="section-header" onclick="toggleSection('calendarSection')">
                            <h5>📅 Календарь стоимости</h5>
                            <button type="button" class="toggle-section-btn collapsed" id="toggleCalendarBtn">▼</button>
                        </div>
                        
                        <div id="calendarSection" class="collapsible-section collapsed">
                            <div class="calendar-info mb-4 p-3 bg-light rounded" style="border-left: 4px solid #2980b9;">
                                <div class="row align-items-center">
                                    <div class="col-md-8">
                                        <small class="text-muted">
                                            <strong>💡 Расчет стоимости осуществляется по ночам:</strong><br>
                                            • Дата заезда = ночь, за которую платите<br>
                                            • Дата выезда = утренний выезд (не оплачивается)
                                        </small>
                                    </div>
                                    <div class="col-md-4">
                                        <div class="example-booking p-2 bg-white rounded border">
                                            <small class="text-muted d-block">Пример:</small>
                                            <small class="text-success fw-bold">15 → 16 ноября = 1 ночь (15 ноября)</small>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div id="calendarContainer"></div>
                        </div>
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
        const allCheckoutDates = <?= json_encode($checkoutDates, JSON_UNESCAPED_UNICODE) ?>;
        const allCheckinDates = <?= json_encode($checkinDates, JSON_UNESCAPED_UNICODE) ?>;
        const allPriceData = <?= json_encode($priceData, JSON_UNESCAPED_UNICODE) ?>;

        let bookedRanges = [];
        let pricePeriods = [];
        let currentCheckoutDates = new Set();
        let currentCheckinDates = new Set();
        let fpCheckin = null;
        let fpCheckout = null;
        let currentBreakdown = [];
        let selectedStartDate = null;
        let selectedEndDate = null;
        let currentObjectName = '';
        let isFormCollapsed = false;
        let originalTotalCost = 0;

        // Состояния свернутости секций - по умолчанию свернуты
        let isPriceListCollapsed = true;
        let isCalendarCollapsed = true;

        function toggleSection(sectionId) {
            const section = document.getElementById(sectionId);
            const toggleBtn = document.getElementById('toggle' + sectionId.charAt(0).toUpperCase() + sectionId.slice(1) + 'Btn');
            
            if (sectionId === 'priceListSection') {
                isPriceListCollapsed = !isPriceListCollapsed;
                section.classList.toggle('collapsed', isPriceListCollapsed);
                toggleBtn.classList.toggle('collapsed', isPriceListCollapsed);
            } else if (sectionId === 'calendarSection') {
                isCalendarCollapsed = !isCalendarCollapsed;
                section.classList.toggle('collapsed', isCalendarCollapsed);
                toggleBtn.classList.toggle('collapsed', isCalendarCollapsed);
            }
        }

        function toggleBookingForm() {
            const formCard = document.getElementById('bookingFormCard');
            const toggleBtn = document.getElementById('toggleFormBtn');
            isFormCollapsed = !isFormCollapsed;
            
            if (isFormCollapsed) {
                formCard.classList.add('collapsed');
                toggleBtn.innerHTML = '▼';
                toggleBtn.classList.remove('btn-outline-secondary');
                toggleBtn.classList.add('btn-secondary');
            } else {
                formCard.classList.remove('collapsed');
                toggleBtn.innerHTML = '▲';
                toggleBtn.classList.remove('btn-secondary');
                toggleBtn.classList.add('btn-outline-secondary');
            }
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

        function isDateAvailableForCheckin(dateStr) {
            const isBooked = getBookedDatesArray().includes(dateStr);
            const isCheckoutDate = currentCheckoutDates.has(dateStr);
            const isCheckinDate = currentCheckinDates.has(dateStr);
            
            return !isBooked || (isCheckoutDate && !isCheckinDate);
        }

        function isDateAvailableForCheckout(dateStr) {
            const isBooked = getBookedDatesArray().includes(dateStr);
            const isCheckoutDate = currentCheckoutDates.has(dateStr);
            const isCheckinDate = currentCheckinDates.has(dateStr);
            
            if (!isBooked) return true;
            if (isCheckinDate && !isCheckoutDate) return true;
            
            const date = parseDate(dateStr);
            const hasBookingAfter = Array.from(currentCheckinDates).some(checkin => {
                const checkinDate = parseDate(checkin);
                return checkinDate > date;
            });
            
            return hasBookingAfter && !isCheckoutDate;
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

                    dayElem.classList.remove('booked', 'available-checkin');

                    if (!isDateAvailableForCheckin(dateStr)) {
                        dayElem.classList.add('booked');
                        dayElem.title = 'Занято';
                    } else if (currentCheckoutDates.has(dateStr) && !currentCheckinDates.has(dateStr)) {
                        dayElem.classList.add('available-checkin');
                        dayElem.title = 'Свободна для заезда (стыковка)';
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

                    dayElem.classList.remove('booked', 'available-checkout');

                    if (!isDateAvailableForCheckout(dateStr)) {
                        dayElem.classList.add('booked');
                        dayElem.title = 'Занято';
                    } else if (currentCheckinDates.has(dateStr) && !currentCheckoutDates.has(dateStr)) {
                        dayElem.classList.add('available-checkout');
                        dayElem.title = 'Свободна для выезда (стыковка)';
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

        function generatePriceList() {
            const container = document.getElementById('priceListContainer');
            container.innerHTML = '';

            if (!pricePeriods || pricePeriods.length === 0) {
                container.innerHTML = `
                    <div class="no-price-data">
                        <i>💰</i>
                        <div>Нет данных о ценах</div>
                        <small class="text-muted">Загрузите файл с ценами для отображения</small>
                    </div>
                `;
                return;
            }

            const monthlyPrices = {};
            const monthNames = {
                1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
                5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
                9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
            };

            // Группируем периоды по месяцам
            pricePeriods.forEach(period => {
                const monthKey = period.startMonth;
                if (!monthlyPrices[monthKey]) {
                    monthlyPrices[monthKey] = [];
                }
                monthlyPrices[monthKey].push(period);
            });

            // Создаем сетку карточек
            const grid = document.createElement('div');
            grid.className = 'compact-price-grid';

            // Сортируем месяцы по порядку
            const sortedMonths = Object.keys(monthlyPrices).sort((a, b) => a - b);

            sortedMonths.forEach(monthNum => {
                const monthData = monthlyPrices[monthNum];
                monthData.sort((a, b) => a.startDay - b.startDay);

                const monthCard = document.createElement('div');
                monthCard.className = 'month-price-card';
                
                // Добавляем подсветку для текущего месяца
                const currentMonth = new Date().getMonth() + 1;
                if (parseInt(monthNum) === currentMonth) {
                    monthCard.classList.add('price-card-highlight');
                }

                // Заголовок месяца
                const monthHeader = document.createElement('div');
                monthHeader.className = 'month-header';
                monthHeader.innerHTML = `
                    <div class="month-name">${monthNames[monthNum]}</div>
                `;

                // Контейнер для периодов
                const periodsContainer = document.createElement('div');
                periodsContainer.className = 'month-periods';

                // Добавляем каждый период
                monthData.forEach(period => {
                    const periodItem = document.createElement('div');
                    periodItem.className = 'period-item';
                    periodItem.innerHTML = `
                        <div class="period-range">${period.startDay} - ${period.endDay} число</div>
                        <div class="period-price">${period.price.toLocaleString('ru-RU')} ฿</div>
                    `;
                    periodsContainer.appendChild(periodItem);
                });

                monthCard.appendChild(monthHeader);
                monthCard.appendChild(periodsContainer);
                grid.appendChild(monthCard);
            });

            container.appendChild(grid);
        }

        function generatePriceCalendar() {
            generatePriceList();
            
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

            const legendElement = document.createElement('div');
            legendElement.className = 'legend';
            legendElement.innerHTML = `
                <div class="legend-item">
                    <div class="legend-color night"></div>
                    <span>Ночь проживания (оплачиваемая)</span>
                </div>
            `;
            container.appendChild(legendElement);

            document.getElementById('priceCalendar').style.display = 'block';
        }

        function checkDateConflict(startDate, endDate) {
            const startStr = startDate.toISOString().split('T')[0];
            const endStr = endDate.toISOString().split('T')[0];

            let current = new Date(startDate);
            while (current < endDate) {
                const currentStr = current.toISOString().split('T')[0];
                if (getBookedDatesArray().includes(currentStr) &&
                    !isDateAvailableForBooking(currentStr, current, startDate, endDate)) {
                    return currentStr;
                }
                current.setDate(current.getDate() + 1);
            }
            return null;
        }

        function isDateAvailableForBooking(dateStr, currentDate, startDate, endDate) {
            if (currentDate.getTime() === startDate.getTime() &&
                currentCheckoutDates.has(dateStr) &&
                !currentCheckinDates.has(dateStr)) {
                return true;
            }

            if (currentDate.getTime() === endDate.getTime() - 86400000 &&
                currentCheckinDates.has(dateStr) &&
                !currentCheckoutDates.has(dateStr)) {
                return true;
            }

            return false;
        }

        document.getElementById('objectSelect').addEventListener('change', function () {
            const obj = this.value;
            bookedRanges = allBookedData[obj] || [];
            pricePeriods = allPriceData[obj] || [];
            currentObjectName = this.options[this.selectedIndex].text;

            if (pricePeriods.length > 0) {
                generatePriceList();
            }

            currentCheckoutDates = new Set();
            currentCheckinDates = new Set();

            if (allCheckoutDates[obj]) {
                allCheckoutDates[obj].forEach(d => {
                    const dt = parseDate(d);
                    currentCheckoutDates.add(dt.toISOString().split('T')[0]);
                });
            }
            if (allCheckinDates[obj]) {
                allCheckinDates[obj].forEach(d => {
                    const dt = parseDate(d);
                    currentCheckinDates.add(dt.toISOString().split('T')[0]);
                });
            }

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

            function parseLocalDate(str) {
                const [y, m, d] = str.split('-').map(Number);
                return new Date(y, m - 1, d);
            }

            selectedStartDate = parseLocalDate(checkin);
            selectedEndDate = parseLocalDate(checkout);
            const nights = Math.ceil((selectedEndDate - selectedStartDate) / (1000 * 60 * 60 * 24));
            if (nights <= 0) {
                alert('Дата выезда должна быть позже даты заезда');
                return;
            }

            const conflictDate = checkDateConflict(selectedStartDate, selectedEndDate);
            if (conflictDate) {
                alert('Выбранные даты пересекаются с существующей бронировкой на дату: ' + formatDate(new Date(conflictDate)));
                return;
            }

            originalTotalCost = calculateTotalCost(selectedStartDate, selectedEndDate);
            document.getElementById('resultObjectName').textContent = currentObjectName;
            document.getElementById('resultPeriodInfo').innerHTML = `${formatDate(selectedStartDate)} - ${formatDate(selectedEndDate)} <span class="expand-form-btn">✏️</span>`;
            document.getElementById('resultNightsInfo').textContent = nights + ' ' + getNightsText(nights);

            applyAutoDiscount(nights);
            generatePriceCalendar();

            document.getElementById('resultSection').style.display = 'block';
            setTimeout(() => {
                document.getElementById('resultSection').scrollIntoView({ behavior: 'smooth' });
            }, 100);
        });

        // Инициализация по умолчанию свернутых секций
        document.addEventListener('DOMContentLoaded', function() {
            initCalendars();
            updateNights();
            
            // Устанавливаем секции как свернутые по умолчанию
            document.getElementById('priceListSection').classList.add('collapsed');
            document.getElementById('calendarSection').classList.add('collapsed');
            document.getElementById('togglePriceListBtn').classList.add('collapsed');
            document.getElementById('toggleCalendarBtn').classList.add('collapsed');
        });
    </script>
</body>
</html>