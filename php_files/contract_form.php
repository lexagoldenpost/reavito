<?php
// contract_form.php — форма договора аренды для Telegram Mini App

// Получаем параметры из URL
$TELEGRAM_BOT_TOKEN = $_GET['token'] ?? '';
$CHAT_ID = $_GET['chat_id'] ?? '';
$INIT_CHAT_ID = $_GET['init_chat_id'] ?? '';

// Проверка обязательных параметров
if (empty($TELEGRAM_BOT_TOKEN) || empty($CHAT_ID )  || empty($INIT_CHAT_ID )) {
    http_response_code(400);
    die('❌ Отсутствуют параметры в URL.');
}

// Функция получения списка объектов
function getRentalObjects() {
    $bookingFilesPath = __DIR__ . '/booking_files/*.csv';
    $files = glob($bookingFilesPath);
    $objects = [];
    if (!empty($files)) {
        foreach ($files as $file) {
            $filename = pathinfo($file, PATHINFO_FILENAME);
            $displayName = ucwords(str_replace('_', ' ', $filename));
            $objects[$filename] = $displayName;
        }
    }
    return $objects;
}

$rentalObjects = getRentalObjects();
?>
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Договор аренды</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css">
    <style>
        /* Стили остаются без изменений */
        :root {
            --tg-theme-bg-color: #ffffff;
            --tg-theme-text-color: #000000;
            --tg-theme-button-color: #2481cc;
            --tg-theme-button-text-color: #ffffff;
        }
        body {
            background: var(--tg-theme-bg-color);
            color: var(--tg-theme-text-color);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            padding: 0;
            margin: 0;
            font-size: 14px;
        }
        .container {
            max-width: 100%;
            padding: 12px;
        }
        .form-container {
            background: var(--tg-theme-bg-color);
            padding: 16px;
            margin-bottom: 16px;
        }
        .btn-tg-success {
            background: #28a745;
            color: white;
            border: none;
            padding: 14px 20px;
            border-radius: 10px;
            font-weight: 600;
            width: 100%;
            margin: 12px 0;
            transition: all 0.2s ease;
            font-size: 15px;
            cursor: pointer;
        }
        .btn-tg-success:active {
            transform: scale(0.98);
            opacity: 0.9;
        }
        .btn-tg-success:disabled {
            background: #6c757d !important;
            cursor: not-allowed !important;
            transform: none !important;
            opacity: 0.6 !important;
        }
        .form-control {
            border-radius: 8px;
            padding: 10px 12px;
            border: 1px solid #e0e0e0;
            background: var(--tg-theme-bg-color);
            color: var(--tg-theme-text-color);
            margin-bottom: 12px;
            font-size: 15px;
            width: 100%;
            box-sizing: border-box;
        }
        .form-control:focus {
            border-color: var(--tg-theme-button-color);
            outline: none;
        }
        .form-label {
            font-weight: 600;
            margin-bottom: 6px;
            color: var(--tg-theme-text-color);
            display: block;
            font-size: 13px;
        }
        .form-section {
            margin-bottom: 20px;
        }
        .section-title {
            font-size: 15px;
            font-weight: 600;
            margin-bottom: 12px;
            color: var(--tg-theme-button-color);
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .grid-2 {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .grid-3 {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 8px;
        }
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid var(--tg-theme-button-color);
            border-radius: 50%;
            width: 24px;
            height: 24px;
            animation: spin 1s linear infinite;
            margin: 0 auto 12px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .header {
            text-align: center;
            margin-bottom: 16px;
            padding: 8px 0;
        }
        .header h1 {
            font-size: 18px;
            margin: 0;
            color: var(--tg-theme-text-color);
        }
        .header p {
            color: #7f8c8d;
            margin: 4px 0 0 0;
            font-size: 13px;
        }
        .required::after {
            content: " *";
            color: #dc3545;
        }
        .summary-card {
            background: rgba(36, 129, 204, 0.1);
            border-radius: 8px;
            padding: 16px;
            margin: 12px 0;
            border-left: 3px solid var(--tg-theme-button-color);
        }
        .guest-list {
            max-height: 200px;
            overflow-y: auto;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            margin-bottom: 12px;
        }
        .guest-item {
            padding: 12px;
            border-bottom: 1px solid #f0f0f0;
            cursor: pointer;
            transition: background-color 0.2s;
        }
        .guest-item:hover {
            background-color: #f8f9fa;
        }
        .guest-item.selected {
            background-color: rgba(36, 129, 204, 0.1);
            border-left: 3px solid var(--tg-theme-button-color);
        }
        .guest-name {
            font-weight: 600;
            margin-bottom: 4px;
        }
        .guest-dates {
            font-size: 12px;
            color: #666;
        }
        .search-filter {
            margin-bottom: 12px;
        }
        .hidden-section {
            display: none;
        }
        .contract-type-badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            margin-left: 8px;
        }
        .contract-type-short {
            background: #ffc107;
            color: #000;
        }
        .contract-type-medium {
            background: #17a2b8;
            color: #fff;
        }
        .date-input-wrapper {
            position: relative;
        }
        .date-input-wrapper::after {
            content: "📅";
            position: absolute;
            right: 12px;
            top: 50%;
            transform: translateY(-50%);
            pointer-events: none;
            font-size: 16px;
        }
        .flatpickr-input {
            background: var(--tg-theme-bg-color) !important;
            color: var(--tg-theme-text-color) !important;
        }
        .flatpickr-calendar {
            background: var(--tg-theme-bg-color) !important;
            border: 1px solid #e0e0e0 !important;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15) !important;
            border-radius: 12px !important;
        }
        .flatpickr-month {
            background: var(--tg-theme-button-color) !important;
            border-radius: 12px 12px 0 0 !important;
            height: 50px !important;
        }
        .flatpickr-current-month {
            color: white !important;
            font-size: 14px !important;
        }
        .flatpickr-weekdays {
            background: rgba(36, 129, 204, 0.1) !important;
        }
        .flatpickr-weekday {
            color: var(--tg-theme-text-color) !important;
            font-weight: 600 !important;
        }
        .flatpickr-day {
            color: var(--tg-theme-text-color) !important;
            border-radius: 8px !important;
            margin: 2px !important;
        }
        .flatpickr-day:hover {
            background: rgba(36, 129, 204, 0.2) !important;
        }
        .flatpickr-day.selected {
            background: var(--tg-theme-button-color) !important;
            color: white !important;
        }
        .flatpickr-day.today {
            border: 2px solid var(--tg-theme-button-color) !important;
        }
        .flatpickr-prev-month, .flatpickr-next-month {
            color: white !important;
            fill: white !important;
        }
        .field-hint {
            font-size: 11px;
            color: #666;
            margin-top: -8px;
            margin-bottom: 8px;
            display: block;
        }
        .field-error {
            border-color: #dc3545 !important;
        }
        .error-message {
            color: #dc3545;
            font-size: 12px;
            margin-top: -8px;
            margin-bottom: 8px;
            display: block;
        }
        @media (max-width: 480px) {
            .container { padding: 8px; }
            .form-container { padding: 12px; }
            .grid-2, .grid-3 { grid-template-columns: 1fr; gap: 8px; }
            .form-control { padding: 12px; font-size: 16px; }
            .btn-tg-success { padding: 16px 20px; font-size: 16px; }
            .flatpickr-calendar {
                width: 300px !important;
                left: 50% !important;
                transform: translateX(-50%) !important;
            }
        }
        @media (min-width: 768px) {
            .container { max-width: 500px; margin: 0 auto; }
        }
        .summary-item {
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
            border-bottom: 1px solid rgba(0,0,0,0.1);
            font-size: 13px;
        }
        .summary-item:last-child {
            border-bottom: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📄 Договор аренды</h1>
            <p>Заполните данные для создания договора</p>
        </div>
        <form id="contractForm">
            <div class="form-container">
                <!-- Шаг 1: Выбор объекта -->
                <div class="form-section" id="step1">
                    <div class="section-title"><span>🏢 Выбор объекта</span></div>
                    <label class="form-label required">Объект недвижимости</label>
                    <select class="form-control" id="objectSelect" name="contract_object" required>
                        <option value="">Выберите объект...</option>
                        <?php foreach ($rentalObjects as $value => $name): ?>
                            <option value="<?= htmlspecialchars($value) ?>"><?= htmlspecialchars($name) ?></option>
                        <?php endforeach; ?>
                    </select>
                </div>

                <!-- Шаг 2: Выбор гостя -->
                <div class="form-section hidden-section" id="step2">
                    <div class="section-title"><span>👥 Выбор гостя</span></div>
                    <div class="search-filter">
                        <input type="text" class="form-control" id="guestSearch" placeholder="🔍 Поиск гостя...">
                    </div>
                    <div class="guest-list" id="guestList">
                        <div style="padding:20px;text-align:center;color:#666;">Выберите объект</div>
                    </div>
                </div>

                <!-- Шаг 3: Основная форма -->
                <div class="hidden-section" id="step3">
                    <!-- Тип договора -->
                    <div class="form-section">
                        <div class="section-title"><span>📑 Тип договора</span></div>
                        <label class="form-label required">Тип договора</label>
                        <select class="form-control" id="contractType" name="contract_type" required>
                            <option value="">Выберите тип...</option>
                            <option value="краткосрок">Краткосрочный</option>
                            <option value="среднесрок">Среднесрочный</option>
                        </select>
                        <div id="contractTypeInfo" style="font-size:12px;color:#666;margin-top:5px;"></div>
                    </div>

                    <!-- Паспортные данные -->
                    <div class="form-section">
                        <div class="section-title"><span>📕 Паспортные данные</span></div>
                        <label class="form-label required">ФИО арендатора</label>
                        <input type="text" class="form-control" name="fullname" required placeholder="Иванов Иван Иванович">
                        <div class="grid-2">
                            <div>
                                <label class="form-label required">Серия загранпаспорта</label>
                                <input type="text" class="form-control" name="passport_series" required placeholder="AB" pattern="[A-Za-z0-9]{2}" maxlength="2">
                                <span class="field-hint">Только латинские буквы и цифры (2 символа)</span>
                            </div>
                            <div>
                                <label class="form-label required">Номер</label>
                                <input type="text" class="form-control" name="passport_number" required placeholder="1234567" pattern="\d{7}" maxlength="7">
                                <span class="field-hint">Только цифры (7 символов)</span>
                            </div>
                        </div>
                        <label class="form-label required">Кем выдан</label>
                        <input type="text" class="form-control" name="passport_issued" required placeholder="Управлением по вопросам миграции">
                        <label class="form-label required">Дата выдачи</label>
                        <div class="date-input-wrapper">
                            <input type="text" class="form-control flatpickr-input" name="passport_date" required placeholder="ДД.ММ.ГГГГ" readonly>
                        </div>
                    </div>

                    <!-- Контактные данные -->
                    <div class="form-section">
                        <div class="section-title"><span>📞 Контактные данные</span></div>
                        <label class="form-label required">Телефон</label>
                        <input type="tel" class="form-control" name="phone" required placeholder="+79991234567">
                    </div>

                    <!-- Даты аренды -->
                    <div class="form-section">
                        <div class="section-title"><span>📅 Даты аренды</span></div>
                        <div class="grid-2">
                            <div>
                                <label class="form-label required">Заселение</label>
                                <div class="date-input-wrapper">
                                    <input type="text" class="form-control flatpickr-input" name="check_in" required placeholder="ДД.ММ.ГГГГ" readonly>
                                </div>
                            </div>
                            <div>
                                <label class="form-label required">Выезд</label>
                                <div class="date-input-wrapper">
                                    <input type="text" class="form-control flatpickr-input" name="check_out" required placeholder="ДД.ММ.ГГГГ" readonly>
                                </div>
                            </div>
                        </div>
                        <div style="margin-top:8px;">
                            <label class="form-label">Количество ночей</label>
                            <input type="text" class="form-control" id="nights" readonly style="background:#f8f9fa;">
                        </div>
                    </div>

                    <!-- Финансовые условия -->
                    <div class="form-section">
                        <div class="section-title"><span>💰 Финансовые условия</span></div>
                        <div class="grid-3">
                            <div><label class="form-label required">Сумма (баты)</label><input type="number" class="form-control" name="total_amount" required placeholder="10000"></div>
                            <div><label class="form-label required">Предоплата (баты)</label><input type="number" class="form-control" name="prepayment_bath" required placeholder="5000"></div>
                            <div><label class="form-label required">Предоплата (рубли)</label><input type="number" class="form-control" name="prepayment_rub" required placeholder="15000"></div>
                        </div>
                    </div>

                    <!-- Сводка -->
                    <div class="summary-card" id="summarySection" style="display:none;">
                        <div style="text-align:center;font-weight:600;margin-bottom:12px;font-size:14px;">📋 Сводка</div>
                        <div class="summary-item"><span>Объект:</span><strong id="summaryObject">-</strong></div>
                        <div class="summary-item"><span>Тип договора:</span><strong id="summaryContractType">-</strong></div>
                        <div class="summary-item"><span>ФИО:</span><strong id="summaryFullname">-</strong></div>
                        <div class="summary-item"><span>Паспорт:</span><strong id="summaryPassport">-</strong></div>
                        <div class="summary-item"><span>Период:</span><strong id="summaryPeriod">-</strong></div>
                        <div class="summary-item"><span>Ночей:</span><strong id="summaryNights">-</strong></div>
                        <div class="summary-item"><span>Сумма:</span><strong id="summaryTotalAmount">-</strong></div>
                    </div>

                    <button type="submit" class="btn-tg-success" id="submitButton">
                        <span class="button-text">📨 Отправить данные договора</span>
                        <span class="button-loading" style="display:none;">⏳ Отправка...</span>
                    </button>
                </div>
            </div>
        </form>

        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>Отправка данных...</p>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>
    <script src="https://cdn.jsdelivr.net/npm/flatpickr/dist/l10n/ru.js"></script>
    <script>
        class TelegramContractForm {
            constructor() {
                this.tg = window.Telegram.WebApp;
                this.tg.expand();
                this.tg.enableClosingConfirmation();
                this.currentBookings = [];
                this.selectedGuest = null;
                this.datepickers = {};
                this.submitTimeout = null;
                this.isSubmitting = false;
                this.init();
            }

            init() {
                this.initDatepickers();
                this.bindEvents();
                this.initInputMasks();
            }

            initDatepickers() {
                const config = {
                    locale: 'ru',
                    dateFormat: 'd.m.Y',
                    allowInput: false,
                    clickOpens: true,
                    theme: 'light',
                    minDate: 'today',
                    onChange: () => {
                        this.calculateNights();
                        this.updateContractType();
                        this.updateSummary();
                    }
                };

                this.datepickers.check_in = flatpickr('input[name="check_in"]', {
                    ...config,
                    onValueUpdate: (dates) => {
                        if (this.datepickers.check_out && dates[0]) {
                            this.datepickers.check_out.set('minDate', dates[0]);
                        }
                    }
                });

                this.datepickers.check_out = flatpickr('input[name="check_out"]', {
                    ...config,
                    onValueUpdate: (dates) => {
                        if (this.datepickers.check_in && dates[0]) {
                            const checkIn = this.datepickers.check_in.selectedDates[0];
                            if (checkIn && dates[0] <= checkIn) {
                                this.datepickers.check_out.setDate(new Date(checkIn.getTime() + 86400000));
                            }
                        }
                    }
                });

                this.datepickers.passport_date = flatpickr('input[name="passport_date"]', {
                    ...config,
                    maxDate: 'today',
                    minDate: new Date().setFullYear(new Date().getFullYear() - 50)
                });
            }

            initInputMasks() {
                // Маска для серии паспорта (только латинские буквы и цифры, 2 символа)
                const passportSeriesInput = document.querySelector('input[name="passport_series"]');
                passportSeriesInput.addEventListener('input', (e) => {
                    let value = e.target.value.toUpperCase();
                    value = value.replace(/[^A-Z0-9]/g, '');
                    value = value.substring(0, 2);
                    e.target.value = value;
                });

                // Маска для номера паспорта (только цифры, 7 символов)
                const passportNumberInput = document.querySelector('input[name="passport_number"]');
                passportNumberInput.addEventListener('input', (e) => {
                    let value = e.target.value.replace(/\D/g, '');
                    value = value.substring(0, 7);
                    e.target.value = value;
                });

                // Маска для телефона
                const phoneInput = document.querySelector('input[name="phone"]');
                phoneInput.addEventListener('input', (e) => {
                    let value = e.target.value.replace(/\D/g, '');

                    if (value.startsWith('7') || value.startsWith('8')) {
                        value = value.substring(1);
                    }

                    let formattedValue = '+7';

                    if (value.length > 0) {
                        formattedValue += ' (' + value.substring(0, 3);
                    }
                    if (value.length > 3) {
                        formattedValue += ') ' + value.substring(3, 6);
                    }
                    if (value.length > 6) {
                        formattedValue += '-' + value.substring(6, 8);
                    }
                    if (value.length > 8) {
                        formattedValue += '-' + value.substring(8, 10);
                    }

                    e.target.value = formattedValue;
                });

                // Маска для ФИО (только буквы и пробелы)
                const fullnameInput = document.querySelector('input[name="fullname"]');
                fullnameInput.addEventListener('input', (e) => {
                    let value = e.target.value;
                    value = value.replace(/[^a-zA-Zа-яА-ЯёЁ\s\-]/g, '');
                    // Убираем лишние пробелы
                    value = value.replace(/\s+/g, ' ').trim();
                    e.target.value = value;
                });

                // Маска для поля "Кем выдан"
                const passportIssuedInput = document.querySelector('input[name="passport_issued"]');
                passportIssuedInput.addEventListener('input', (e) => {
                    let value = e.target.value;
                    // Разрешаем буквы, цифры, пробелы и основные пунктуации
                    value = value.replace(/[^a-zA-Zа-яА-ЯёЁ0-9\s\-.,()]/g, '');
                    e.target.value = value;
                });

                // Маски для числовых полей (только цифры)
                const numberInputs = document.querySelectorAll('input[type="number"]');
                numberInputs.forEach(input => {
                    input.addEventListener('input', (e) => {
                        let value = e.target.value.replace(/\D/g, '');
                        if (value === '') value = '0';
                        e.target.value = value;
                    });
                });
            }

            bindEvents() {
                document.getElementById('objectSelect').addEventListener('change', (e) => {
                    if (e.target.value) {
                        this.loadBookings(e.target.value);
                        this.showStep(2);
                    } else {
                        this.hideStep(2);
                        this.hideStep(3);
                    }
                });

                document.getElementById('guestSearch').addEventListener('input', (e) => {
                    this.filterGuests(e.target.value);
                });

                document.getElementById('contractForm').addEventListener('submit', (e) => {
                    e.preventDefault();
                    this.submitForm();
                });

                document.getElementById('contractForm').addEventListener('input', () => {
                    this.updateSummary();
                });

                // Валидация при потере фокуса
                const inputs = document.querySelectorAll('input[required]');
                inputs.forEach(input => {
                    input.addEventListener('blur', () => {
                        this.validateField(input);
                    });
                });
            }

            setSubmitButtonState(disabled, loading = false) {
                const button = document.getElementById('submitButton');
                const buttonText = button.querySelector('.button-text');
                const buttonLoading = button.querySelector('.button-loading');

                button.disabled = disabled;
                this.isSubmitting = disabled;

                if (loading) {
                    buttonText.style.display = 'none';
                    buttonLoading.style.display = 'inline';
                } else {
                    buttonText.style.display = 'inline';
                    buttonLoading.style.display = 'none';
                }
            }

            validateField(field) {
                const value = field.value.trim();

                if (!value) {
                    field.classList.add('field-error');
                    this.showFieldError(field, 'Это поле обязательно для заполнения');
                    return false;
                }

                let isValid = true;
                let errorMessage = '';

                switch(field.name) {
                    case 'passport_series':
                        isValid = /^[A-Z0-9]{2}$/.test(value);
                        errorMessage = 'Серия должна содержать 2 латинских символа или цифры';
                        break;
                    case 'passport_number':
                        isValid = /^\d{7}$/.test(value);
                        errorMessage = 'Номер должен содержать 7 цифр';
                        break;
                    case 'phone':
                        isValid = /^\+7\s\(\d{3}\)\s\d{3}-\d{2}-\d{2}$/.test(value);
                        errorMessage = 'Введите корректный номер телефона';
                        break;
                    case 'fullname':
                        isValid = value.split(' ').length >= 2 && /^[a-zA-Zа-яА-ЯёЁ\s\-]+$/.test(value);
                        errorMessage = 'Введите ФИО (минимум 2 слова)';
                        break;
                    case 'check_in':
                    case 'check_out':
                    case 'passport_date':
                        isValid = this.isValidDate(value);
                        errorMessage = 'Введите корректную дату';
                        break;
                }

                if (isValid) {
                    field.classList.remove('field-error');
                    this.hideFieldError(field);
                } else {
                    field.classList.add('field-error');
                    this.showFieldError(field, errorMessage);
                }
                return isValid;
            }

            showFieldError(field, message) {
                // Удаляем существующее сообщение об ошибке
                this.hideFieldError(field);

                // Создаем новое сообщение об ошибке
                const errorElement = document.createElement('span');
                errorElement.className = 'error-message';
                errorElement.textContent = message;
                errorElement.id = field.name + '-error';

                // Вставляем после поля
                field.parentNode.insertBefore(errorElement, field.nextSibling);
            }

            hideFieldError(field) {
                const existingError = document.getElementById(field.name + '-error');
                if (existingError) {
                    existingError.remove();
                }
            }

            async loadBookings(objectName) {
                try {
                    const res = await fetch(`get_bookings.php?object=${encodeURIComponent(objectName)}`);
                    this.currentBookings = res.ok ? await res.json() : [];
                } catch {
                    this.currentBookings = [];
                }
                this.renderGuestList(this.currentBookings);
            }

            renderGuestList(bookings) {
    const el = document.getElementById('guestList');
    if (!bookings.length) {
        el.innerHTML = '<div style="padding:20px;text-align:center;color:#666;">Нет бронирований</div>';
        return;
    }
    el.innerHTML = bookings.map(b => {
        const extractedPhone = b.phone ? this.extractFirstPhone(b.phone) : null;
        return `
            <div class="guest-item" data-guest='${JSON.stringify(b).replace(/'/g, "&#39;")}'>
                <div class="guest-name">${this.escapeHtml(b.guest)}</div>
                <div class="guest-dates">${b.check_in} - ${b.check_out}</div>
                ${extractedPhone ? `<div class="guest-dates">📞 ${extractedPhone}</div>` : ''}
            </div>
        `;
    }).join('');
    el.querySelectorAll('.guest-item').forEach(item => {
        item.addEventListener('click', () => {
            this.selectGuest(JSON.parse(item.dataset.guest));
        });
    });
}
            selectGuest(guest) {
                this.selectedGuest = guest;
                document.querySelectorAll('.guest-item').forEach(i => i.classList.remove('selected'));
                const el = [...document.querySelectorAll('.guest-item')].find(i => JSON.parse(i.dataset.guest).guest === guest.guest);
                if (el) el.classList.add('selected');
                this.fillFormWithGuestData(guest);
                this.showStep(3);
            }

            fillFormWithGuestData(guest) {
    document.querySelector('[name="fullname"]').value = guest.guest || '';

    // Улучшенное извлечение телефона из строки
    if (guest.phone) {
        const phone = this.extractFirstPhone(guest.phone);
        if (phone) {
            document.querySelector('[name="phone"]').value = phone;
        } else {
            document.querySelector('[name="phone"]').value = '';
        }
    } else {
        document.querySelector('[name="phone"]').value = '';
    }

    if (guest.check_in) this.datepickers.check_in.setDate(this.parseDate(guest.check_in));
    if (guest.check_out) this.datepickers.check_out.setDate(this.parseDate(guest.check_out));
    if (guest.total_amount) document.querySelector('[name="total_amount"]').value = guest.total_amount.replace(/\s/g, '');
    if (guest.prepayment) {
        const [bath, rub] = guest.prepayment.split('/');
        if (bath) document.querySelector('[name="prepayment_bath"]').value = bath.replace(/\s/g, '');
        if (rub) document.querySelector('[name="prepayment_rub"]').value = rub.replace(/\s/g, '');
    }
    this.calculateNights();
    this.updateContractType();
    this.updateSummary();
}

// Новая функция для извлечения первого телефона из строки
extractFirstPhone(phoneString) {
    if (!phoneString) return null;

    // Убираем лишние пробелы и приводим к единому формату
    const cleanString = phoneString.toString().trim();

    // Ищем последовательности цифр длиной от 10 до 15 символов (с учетом кода страны)
    const phoneRegex = /(\+?[0-9\s\-\(\)]{10,15})/g;
    const matches = cleanString.match(phoneRegex);

    if (!matches || matches.length === 0) return null;

    // Берем первый найденный телефон
    let firstPhone = matches[0].trim();

    // Очищаем телефон от лишних символов, оставляя только цифры и плюс в начале
    let cleanPhone = firstPhone.replace(/[^\d\+]/g, '');

    // Если телефон начинается с 8, заменяем на +7
    if (cleanPhone.startsWith('8') && cleanPhone.length === 11) {
        cleanPhone = '+7' + cleanPhone.substring(1);
    }
    // Если телефон начинается с 7 и нет плюса, добавляем +
    else if (cleanPhone.startsWith('7') && cleanPhone.length === 11 && !cleanPhone.startsWith('+')) {
        cleanPhone = '+' + cleanPhone;
    }
    // Если телефон 10 цифр без кода страны, добавляем +7
    else if (cleanPhone.length === 10 && /^\d+$/.test(cleanPhone)) {
        cleanPhone = '+7' + cleanPhone;
    }

    // Форматируем телефон согласно маске поля +7 (XXX) XXX-XX-XX
    if (cleanPhone.startsWith('+7') && cleanPhone.length === 12) {
        const numbers = cleanPhone.substring(2);
        return `+7 (${numbers.substring(0,3)}) ${numbers.substring(3,6)}-${numbers.substring(6,8)}-${numbers.substring(8,10)}`;
    }

    return firstPhone; // Возвращаем исходный формат, если не удалось отформатировать
}

            filterGuests(term) {
                const filtered = this.currentBookings.filter(b =>
                    b.guest.toLowerCase().includes(term.toLowerCase())
                );
                this.renderGuestList(filtered);
            }

            calculateNights() {
                const inVal = document.querySelector('[name="check_in"]').value;
                const outVal = document.querySelector('[name="check_out"]').value;
                if (inVal && outVal) {
                    const inDate = this.parseDate(inVal);
                    const outDate = this.parseDate(outVal);
                    if (inDate && outDate && outDate > inDate) {
                        const diff = Math.ceil((outDate - inDate) / (1000 * 60 * 60 * 24));
                        const text = diff === 1 ? 'ночь' : (diff >= 2 && diff <= 4 ? 'ночи' : 'ночей');
                        document.getElementById('nights').value = `${diff} ${text}`;
                        return diff;
                    }
                }
                document.getElementById('nights').value = '0 ночей';
                return 0;
            }

            updateContractType() {
                const nights = this.calculateNights();
                const select = document.getElementById('contractType');
                const info = document.getElementById('contractTypeInfo');
                if (nights >= 30) {
                    select.value = 'среднесрок';
                    info.innerHTML = '<span class="contract-type-badge contract-type-medium">Автоматически: Среднесрочный (30+ ночей)</span>';
                } else if (nights > 0) {
                    select.value = 'краткосрок';
                    info.innerHTML = '<span class="contract-type-badge contract-type-short">Автоматически: Краткосрочный</span>';
                } else {
                    select.value = '';
                    info.innerHTML = '';
                }
            }

            updateSummary() {
                const data = Object.fromEntries(new FormData(document.getElementById('contractForm')).entries());
                const has = data.contract_object && data.fullname && data.passport_series && data.passport_number &&
                            data.check_in && data.check_out && data.contract_type;
                const summary = document.getElementById('summarySection');
                if (has) {
                    summary.style.display = 'block';
                    document.getElementById('summaryObject').textContent =
                        document.getElementById('objectSelect').options[document.getElementById('objectSelect').selectedIndex].text;
                    const typeText = data.contract_type === 'краткосрок' ? 'Краткосрочный' : 'Среднесрочный';
                    const typeClass = data.contract_type === 'краткосрок' ? 'contract-type-short' : 'contract-type-medium';
                    document.getElementById('summaryContractType').innerHTML = `${typeText} <span class="contract-type-badge ${typeClass}">${data.contract_type}</span>`;
                    document.getElementById('summaryFullname').textContent = data.fullname;
                    document.getElementById('summaryPassport').textContent = `${data.passport_series} ${data.passport_number}`;
                    document.getElementById('summaryPeriod').textContent = `${data.check_in} - ${data.check_out}`;
                    document.getElementById('summaryNights').textContent = document.getElementById('nights').value;
                    document.getElementById('summaryTotalAmount').textContent = data.total_amount ? `${data.total_amount} бат` : '-';
                } else {
                    summary.style.display = 'none';
                }
            }

            validateForm() {
                const required = document.querySelectorAll('[required]');
                let valid = true;
                let invalidFields = [];

                for (const field of required) {
                    const fieldName = field.name;
                    const value = field.value.trim();
                    let fieldValid = true;

                    if (!value) {
                        fieldValid = false;
                        invalidFields.push(this.getFieldDisplayName(fieldName));
                    } else {
                        switch(fieldName) {
                            case 'passport_series':
                                fieldValid = /^[A-Z0-9]{2}$/.test(value);
                                break;
                            case 'passport_number':
                                fieldValid = /^\d{7}$/.test(value);
                                break;
                            case 'phone':
                                fieldValid = /^\+7\s\(\d{3}\)\s\d{3}-\d{2}-\d{2}$/.test(value);
                                break;
                            case 'fullname':
                                fieldValid = value.split(' ').length >= 2 && /^[a-zA-Zа-яА-ЯёЁ\s\-]+$/.test(value);
                                break;
                            case 'check_in':
                            case 'check_out':
                            case 'passport_date':
                                fieldValid = this.isValidDate(value);
                                break;
                        }
                    }

                    if (!fieldValid) {
                        valid = false;
                        field.classList.add('field-error');
                        if (!invalidFields.includes(this.getFieldDisplayName(fieldName))) {
                            invalidFields.push(this.getFieldDisplayName(fieldName));
                        }
                    } else {
                        field.classList.remove('field-error');
                    }
                }

                return { valid, invalidFields };
            }

            getFieldDisplayName(fieldName) {
                const names = {
                    'contract_object': 'Объект недвижимости',
                    'contract_type': 'Тип договора',
                    'fullname': 'ФИО арендатора',
                    'passport_series': 'Серия загранпаспорта',
                    'passport_number': 'Номер загранпаспорта',
                    'passport_issued': 'Кем выдан паспорт',
                    'passport_date': 'Дата выдачи паспорта',
                    'phone': 'Телефон',
                    'check_in': 'Дата заселения',
                    'check_out': 'Дата выезда',
                    'total_amount': 'Сумма аренды',
                    'prepayment_bath': 'Предоплата в батах',
                    'prepayment_rub': 'Предоплата в рублях'
                };
                return names[fieldName] || fieldName;
            }

            async submitForm() {
                if (this.isSubmitting) return;

                // Валидация формы
                const validation = this.validateForm();
                if (!validation.valid) {
                    const fieldsList = validation.invalidFields.join(', ');
                    this.tg.showPopup({
                        title: '❌ Ошибка заполнения',
                        message: `Заполните все обязательные поля правильно:\n${fieldsList}`,
                        buttons: [{ type: 'ok' }]
                    });
                    return;
                }

                this.setSubmitButtonState(true, true);

                const formData = new FormData(document.getElementById('contractForm'));
                const data = Object.fromEntries(formData.entries());

                // Форматируем данные для отправки
                const message = this.formatMessage(data);

                try {
                    await this.sendToTelegram(message);
                    this.tg.showPopup({
                        title: '✅ Успешно',
                        message: 'Данные договора отправлены!',
                        buttons: [{ type: 'ok' }]
                    });
                    setTimeout(() => this.tg.close(), 1500);
                } catch (error) {
                    console.error('Ошибка отправки:', error);
                    this.tg.showPopup({
                        title: '❌ Ошибка',
                        message: 'Не удалось отправить данные. Попробуйте еще раз.',
                        buttons: [{ type: 'ok' }]
                    });
                    this.setSubmitButtonState(false, false);
                }
            }

            formatMessage(data) {
                const objectText = document.getElementById('objectSelect').options[document.getElementById('objectSelect').selectedIndex].text;
                const nights = this.calculateNights();
                const contractTypeText = data.contract_type === 'краткосрок' ? 'Краткосрочный' : 'Среднесрочный';

                return `📄 *НОВАЯ ЗАЯВКА НА ДОГОВОР АРЕНДЫ*

🏢 *Объект:* ${objectText}
📑 *Тип договора:* ${contractTypeText}

👤 *Данные арендатора:*
• *ФИО:* ${data.fullname}
• *Паспорт:* ${data.passport_series} ${data.passport_number}
• *Кем выдан:* ${data.passport_issued}
• *Дата выдачи:* ${data.passport_date}

📞 *Контактные данные:*
• *Телефон:* ${data.phone}

📅 *Период аренды:*
• *Заселение:* ${data.check_in}
• *Выезд:* ${data.check_out}
• *Количество ночей:* ${nights}

💰 *Финансовые условия:*
• *Общая сумма:* ${data.total_amount} бат
• *Предоплата:* ${data.prepayment_bath} бат / ${data.prepayment_rub} руб

${this.selectedGuest ? `_На основе бронирования: ${this.selectedGuest.guest}_` : ''}`;
            }

            async sendToTelegram(message) {
                const params = new URLSearchParams({
                    chat_id: '<?= $INIT_CHAT_ID ?>',
                    text: message,
                    parse_mode: 'Markdown'
                });

                const response = await fetch(`https://api.telegram.org/bot<?= $TELEGRAM_BOT_TOKEN ?>/sendMessage?${params}`);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
            }

            showStep(step) {
                document.getElementById(`step${step}`).classList.remove('hidden-section');
            }

            hideStep(step) {
                document.getElementById(`step${step}`).classList.add('hidden-section');
            }

            parseDate(str) {
                const [d, m, y] = str.split('.').map(Number);
                return new Date(y, m - 1, d);
            }

            isValidDate(dateStr) {
                const [d, m, y] = dateStr.split('.').map(Number);
                if (!d || !m || !y) return false;
                const date = new Date(y, m - 1, d);
                return date.getDate() === d && date.getMonth() === m - 1 && date.getFullYear() === y;
            }

            escapeHtml(unsafe) {
                return unsafe
                    .replace(/&/g, "&amp;")
                    .replace(/</g, "&lt;")
                    .replace(/>/g, "&gt;")
                    .replace(/"/g, "&quot;")
                    .replace(/'/g, "&#039;");
            }
        }

        // Инициализация при загрузке
        document.addEventListener('DOMContentLoaded', () => {
            new TelegramContractForm();
        });
    </script>
</body>
</html>