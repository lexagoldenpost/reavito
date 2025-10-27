<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Расчет стоимости бронирования</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css" rel="stylesheet">
    <style>
        .container {
            max-width: 800px;
        }
        .card {
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border: none;
            border-radius: 10px;
        }
        .flatpickr-day.booked {
            background-color: #dc3545;
            color: white;
            border-color: #dc3545;
        }
        .flatpickr-day.booked:hover {
            background-color: #bb2d3b;
            border-color: #b02a37;
        }
        .result-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .form-label {
            font-weight: 500;
        }
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
                                    <?php
                                    $bookingFiles = glob('/home/booking_files/*.csv');
                                    foreach ($bookingFiles as $file) {
                                        $filename = pathinfo($file, PATHINFO_FILENAME);
                                        $displayName = ucfirst(preg_replace('/([a-z])([A-Z])/', '$1 $2', $filename));
                                        echo "<option value=\"$filename\">$displayName</option>";
                                    }
                                    ?>
                                </select>
                            </div>

                            <div class="col-md-6 mb-3">
                                <label for="dateRange" class="form-label">Период бронирования</label>
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
        let bookedDates = [];
        let priceData = {};

        // Инициализация календаря
        const datePicker = flatpickr("#dateRange", {
            mode: "range",
            locale: "ru",
            minDate: "today",
            dateFormat: "d.m.Y",
            disable: [],
            onChange: function(selectedDates) {
                updateCalendarStyles();
            },
            onMonthChange: function() {
                updateCalendarStyles();
            },
            onYearChange: function() {
                updateCalendarStyles();
            }
        });

        // Обработчик изменения объекта
        document.getElementById('objectSelect').addEventListener('change', function() {
            const objectName = this.value;
            if (objectName) {
                loadBookedDates(objectName);
                loadPriceData(objectName);
            } else {
                bookedDates = [];
                priceData = {};
                datePicker.set('disable', []);
                updateCalendarStyles();
            }
        });

        // Загрузка занятых дат
        function loadBookedDates(objectName) {
            fetch('get_booked_dates.php?object=' + encodeURIComponent(objectName))
                .then(response => response.json())
                .then(data => {
                    bookedDates = data;
                    updateDatePickerDisable();
                    updateCalendarStyles();
                })
                .catch(error => {
                    console.error('Error loading booked dates:', error);
                    bookedDates = [];
                });
        }

        // Загрузка данных о ценах
        function loadPriceData(objectName) {
            fetch('get_price_data.php?object=' + encodeURIComponent(objectName))
                .then(response => response.json())
                .then(data => {
                    priceData = data;
                })
                .catch(error => {
                    console.error('Error loading price data:', error);
                    priceData = {};
                });
        }

        // Обновление заблокированных дат в календаре
        function updateDatePickerDisable() {
            const disableDates = [];
            bookedDates.forEach(period => {
                let current = new Date(period.start);
                const end = new Date(period.end);

                while (current <= end) {
                    disableDates.push(new Date(current));
                    current.setDate(current.getDate() + 1);
                }
            });

            datePicker.set('disable', disableDates);
        }

        // Обновление стилей календаря для отображения занятых дат
        function updateCalendarStyles() {
            setTimeout(() => {
                document.querySelectorAll('.flatpickr-day').forEach(day => {
                    const dateStr = day.getAttribute('aria-label');
                    if (dateStr) {
                        const date = parseDateFromString(dateStr);
                        const isBooked = bookedDates.some(period =>
                            date >= new Date(period.start) && date <= new Date(period.end)
                        );

                        if (isBooked) {
                            day.classList.add('booked');
                        } else {
                            day.classList.remove('booked');
                        }
                    }
                });
            }, 10);
        }

        // Парсинг даты из строки
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

        // Обработчик формы
        document.getElementById('bookingForm').addEventListener('submit', function(e) {
            e.preventDefault();

            const selectedDates = datePicker.selectedDates;
            if (selectedDates.length !== 2) {
                alert('Пожалуйста, выберите период бронирования');
                return;
            }

            const startDate = selectedDates[0];
            const endDate = selectedDates[1];

            // Расчет стоимости
            const totalCost = calculateTotalCost(startDate, endDate);
            const nights = Math.ceil((endDate - startDate) / (1000 * 60 * 60 * 24));

            // Отображение результата
            document.getElementById('totalAmount').textContent = totalCost.toLocaleString('ru-RU') + ' бат';
            document.getElementById('periodInfo').textContent =
                `Период: ${formatDate(startDate)} - ${formatDate(endDate)}`;
            document.getElementById('nightsInfo').textContent =
                `Количество ночей: ${nights}`;

            document.getElementById('resultSection').style.display = 'block';
        });

        // Расчет общей стоимости
        function calculateTotalCost(startDate, endDate) {
            let total = 0;
            let current = new Date(startDate);

            while (current < endDate) {
                const month = current.getMonth() + 1;
                const day = current.getDate();

                // Поиск подходящего ценового периода
                let dailyPrice = 0;
                for (const period of Object.values(priceData)) {
                    if (month >= period.startMonth && month <= period.endMonth) {
                        if ((month === period.startMonth && day >= period.startDay) ||
                            (month === period.endMonth && day <= period.endDay) ||
                            (month > period.startMonth && month < period.endMonth)) {
                            dailyPrice = period.price;
                            break;
                        }
                    }
                }

                total += dailyPrice;
                current.setDate(current.getDate() + 1);
            }

            return total;
        }

        // Форматирование даты
        function formatDate(date) {
            return date.toLocaleDateString('ru-RU', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric'
            });
        }
    </script>
</body>
</html>

<?php
// Сохранение вспомогательных PHP файлов
file_put_contents('get_booked_dates.php', '<?php
header("Content-Type: application/json");

if (!isset($_GET["object"])) {
    echo json_encode([]);
    exit;
}

$objectName = $_GET["object"];
$bookingFile = "/home/booking_files/" . $objectName . ".csv";

if (!file_exists($bookingFile)) {
    echo json_encode([]);
    exit;
}

$bookedDates = [];
$handle = fopen($bookingFile, "r");
if ($handle !== FALSE) {
    $headers = fgetcsv($handle, 1000, ",");

    while (($data = fgetcsv($handle, 1000, ",")) !== FALSE) {
        if (count($data) >= 4) {
            $checkIn = DateTime::createFromFormat("d.m.Y", trim($data[2]));
            $checkOut = DateTime::createFromFormat("d.m.Y", trim($data[3]));

            if ($checkIn && $checkOut) {
                $bookedDates[] = [
                    "start" => $checkIn->format("Y-m-d"),
                    "end" => $checkOut->format("Y-m-d")
                ];
            }
        }
    }
    fclose($handle);
}

echo json_encode($bookedDates);
?>');

file_put_contents('get_price_data.php', '<?php
header("Content-Type: application/json");

if (!isset($_GET["object"])) {
    echo json_encode([]);
    exit;
}

$objectName = $_GET["object"];
$priceFile = "/home/task_files/" . $objectName . "_price.csv";  // ОБНОВЛЕННЫЙ ПУТЬ

if (!file_exists($priceFile)) {
    echo json_encode([]);
    exit;
}

$priceData = [];
$handle = fopen($priceFile, "r");
if ($handle !== FALSE) {
    $headers = fgetcsv($handle, 1000, ",");

    while (($data = fgetcsv($handle, 1000, ",")) !== FALSE) {
        if (count($data) >= 5) {
            $monthNames = [
                "январь" => 1, "февраль" => 2, "март" => 3, "апрель" => 4,
                "май" => 5, "июнь" => 6, "июль" => 7, "август" => 8,
                "сентябрь" => 9, "октябрь" => 10, "ноябрь" => 11, "декабрь" => 12
            ];

            $monthName = strtolower(trim($data[0]));
            $startDay = intval(trim($data[1]));
            $endDay = intval(trim($data[2]));
            $price = intval(trim($data[3]));

            if (isset($monthNames[$monthName])) {
                $priceData[] = [
                    "startMonth" => $monthNames[$monthName],
                    "endMonth" => $monthNames[$monthName],
                    "startDay" => $startDay,
                    "endDay" => $endDay,
                    "price" => $price
                ];
            }
        }
    }
    fclose($handle);
}

echo json_encode($priceData);
?>');
?>