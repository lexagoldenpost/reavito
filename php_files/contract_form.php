<?php
// contract_form.php — форма договора аренды для Telegram Mini App
// Получаем параметры из URL
$TELEGRAM_BOT_TOKEN = $_GET['token'] ?? '';
$CHAT_ID = $_GET['chat_id'] ?? '';
$INIT_CHAT_ID = $_GET['init_chat_id'] ?? '';
$INIT_CHAT_ID_JS = json_encode($INIT_CHAT_ID); // для безопасной вставки в JS
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

// Функция проверки, что дата в будущем или сегодня
function isFutureOrToday($dateString) {
    if (empty($dateString)) {
        return false;
    }
    // Предполагаем формат даты DD.MM.YYYY из flatpickr
    $date = DateTime::createFromFormat('d.m.Y', $dateString);
    if (!$date) {
        // Пробуем YYYY-MM-DD, если не подошёл DD.MM.YYYY
        $date = DateTime::createFromFormat('Y-m-d', $dateString);
    }
    if (!$date) {
        return false;
    }

    $today = new DateTime();
    $today->setTime(0, 0, 0); // Установим время на 00:00:00 для корректного сравнения

    return $date >= $today;
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
    .field-valid {
    border-color: #28a745 !important;
    background-color: rgba(40, 167, 69, 0.05) !important;
}
.field-error {
    border-color: #dc3545 !important;
    background-color: rgba(220, 53, 69, 0.05) !important;
}
.error-message {
    color: #dc3545;
    font-size: 12px;
    margin-top: -8px;
    margin-bottom: 8px;
    display: block;
}
/* Добавляем иконки для статусов полей */
.form-control:not(.flatpickr-input) {
    background-image: none;
    padding-right: 40px;
    background-position: right 12px center;
    background-repeat: no-repeat;
    background-size: 16px;
}
.form-control.field-valid:not(.flatpickr-input) {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%2328a745'%3E%3Cpath d='M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z'/%3E%3C/svg%3E");
}
.form-control.field-error:not(.flatpickr-input) {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23dc3545'%3E%3Cpath d='M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z'/%3E%3C/svg%3E");
}
/* Стили для чекбоксов */
.form-checkbox {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 0;
    cursor: pointer;
}
.form-checkbox input[type="checkbox"] {
    width: 20px;
    height: 20px;
    accent-color: var(--tg-theme-button-color);
    cursor: pointer;
}
.form-checkbox span {
    font-size: 14px;
    color: var(--tg-theme-text-color);
    font-weight: 500;
}
.services-section {
    background: rgba(36, 129, 204, 0.05);
    border-radius: 8px;
    padding: 16px;
    margin: 12px 0;
    border: 1px solid rgba(36, 129, 204, 0.2);
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
                        <select class="form-control" id="contractType" name="contract_type">
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
                        <span class="field-hint">Только буквы, пробелы и дефисы (минимум 2 слова)</span>
                        <div class="grid-2">
                            <div>
                                <label class="form-label required">Серия загранпаспорта</label>
                                <input type="text" class="form-control" name="passport_series" required placeholder="AB" pattern="[A-Za-z0-9]{2}" maxlength="2">
                                <span class="field-hint">Только латинские буквы и цифры (2 символа)</span>
                            </div>
                            <div>
                                <label class="form-label required">Номер</label>
                                <!-- ИСПРАВЛЕНО: изменен тип поля на tel с inputmode numeric -->
                                <input type="tel" class="form-control" name="passport_number" required placeholder="1234567" pattern="\d{7}" maxlength="7" inputmode="numeric">
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
                                <label class="form-label required">Заезд</label>
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
                            <div><label class="form-label">Доп. оплата (баты)</label><input type="number" class="form-control" name="extraPaymentBath" placeholder="1500"></div>
                        </div>
                    </div>
                    <!-- Услуги -->
                    <div class="form-section services-section">
                        <div class="section-title"><span>🧹 Услуги</span></div>
                        <div style="display: flex; flex-direction: column; gap: 12px;">
                            <label class="form-checkbox">
                                <input type="checkbox" name="interim_cleaning" checked>
                                <span>Уборка, прачка</span>
                            </label>
                            <label class="form-checkbox">
                                <input type="checkbox" name="electric" checked>
                                <span>Свет, вода</span>
                            </label>
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
                this.filteredBookings = []; // Новое свойство для отфильтрованных броней
                this.selectedGuest = null;
                this.datepickers = {};
                this.submitTimeout = null;
                this.isSubmitting = false;
                this.autoFilledFields = new Set();
                this.init();
            }
            init() {
                this.initDatepickers();
                this.bindEvents();
                this.initInputMasks();
                this.highlightRequiredFields();
            }
            highlightRequiredFields() {
                const requiredFields = document.querySelectorAll('[required]');
                requiredFields.forEach(field => {
                    if (!this.autoFilledFields.has(field.name)) {
                        this.updateFieldHighlight(field);
                    }
                });
            }
            updateFieldHighlight(field, isAutoFilled = false) {
                const value = field.value?.trim();
                const fieldName = field.name || field.id;
                const isValid = this.validateFieldValue(field, value);
                if (isAutoFilled || this.autoFilledFields.has(fieldName)) {
                    if (isValid) {
                        field.classList.remove('field-error', 'field-valid');
                        this.hideFieldError(field);
                    } else {
                        field.classList.add('field-error');
                        this.showFieldError(field, this.getValidationErrorMessage(field));
                    }
                    return;
                }
                if (!value) {
                    field.classList.add('field-error');
                    field.classList.remove('field-valid');
                } else if (!isValid) {
                    field.classList.add('field-error');
                    field.classList.remove('field-valid');
                    this.showFieldError(field, this.getValidationErrorMessage(field));
                } else {
                    field.classList.remove('field-error');
                    field.classList.remove('field-valid');
                    this.hideFieldError(field);
                }
            }
            getValidationErrorMessage(field) {
                const value = field.value?.trim() || '';
                switch(field.name) {
                    case 'passport_series':
                        return 'Серия должна содержать 2 латинских символа или цифры';
                    case 'passport_number':
                        return 'Номер должен содержать 7 цифр';
                    case 'phone':
                        return 'Введите корректный номер телефона';
                    case 'fullname':
                        return 'Введите ФИО (минимум 2 слова)';
                    case 'total_amount':
                    case 'prepayment_bath':
                    case 'extraPaymentBath':
                        return 'Введите корректное положительное число';
                    case 'check_in':
                    case 'check_out':
                    case 'passport_date':
                        return 'Введите корректную дату';
                    default:
                        return 'Некорректное значение';
                }
            }
            clearAutoFilledFields() {
                this.autoFilledFields.clear();
            }
            validateFieldValue(field, value) {
                if (!value) return false;
                switch(field.name) {
                    case 'passport_series':
                        return /^[A-Z0-9]{2}$/.test(value);
                    case 'passport_number':
                        return /^\d{7}$/.test(value);
                    case 'phone':
                        return /^\+7\s\(\d{3}\)\s\d{3}-\d{2}-\d{2}$/.test(value);
                    case 'fullname':
                        return value.split(' ').length >= 2 && /^[a-zA-Zа-яА-ЯёЁ\s\-]+$/.test(value);
                    case 'check_in':
                    case 'check_out':
                    case 'passport_date':
                        return this.isValidDate(value);
                    case 'total_amount':
                    case 'prepayment_bath':
                    case 'extraPaymentBath':
                        const num = Number(value);
                        return !isNaN(num) && num > 0 && Number.isInteger(num);
                    default:
                        return true;
                }
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
                const passportSeriesInput = document.querySelector('input[name="passport_series"]');
                passportSeriesInput.addEventListener('input', (e) => {
                    let value = e.target.value.toUpperCase();
                    value = value.replace(/[^A-Z0-9]/g, '');
                    value = value.substring(0, 2);
                    e.target.value = value;
                });
                const passportNumberInput = document.querySelector('input[name="passport_number"]');
                passportNumberInput.addEventListener('input', (e) => {
                    let value = e.target.value.replace(/\D/g, '');
                    value = value.substring(0, 7);
                    e.target.value = value;
                });
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
                const fullnameInput = document.querySelector('input[name="fullname"]');
                fullnameInput.addEventListener('input', (e) => {
                    let value = e.target.value;
                    value = value.replace(/[^a-zA-Zа-яА-ЯёЁ\s\-]/g, '');
                    value = value.replace(/\s+/g, ' ').trim();
                    e.target.value = value;
                });
                const passportIssuedInput = document.querySelector('input[name="passport_issued"]');
                passportIssuedInput.addEventListener('input', (e) => {
                    let value = e.target.value;
                    value = value.replace(/[^a-zA-Zа-яА-ЯёЁ0-9\s\-.,()]/g, '');
                    e.target.value = value;
                });
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
                        this.selectedGuest = null;
                        this.clearAutoFilledFields();
                    } else {
                        this.hideStep(2);
                        this.hideStep(3);
                    }
                    this.updateFieldHighlight(e.target);
                });
                document.getElementById('guestSearch').addEventListener('input', (e) => {
                    this.filterGuests(e.target.value);
                });
                document.getElementById('contractForm').addEventListener('submit', (e) => {
                    e.preventDefault();
                    this.submitForm();
                });
                document.getElementById('contractForm').addEventListener('input', (e) => {
                    this.updateSummary();
                    if (e.target.hasAttribute('required')) {
                        this.autoFilledFields.delete(e.target.name);
                        this.updateFieldHighlight(e.target, false);
                    }
                });
                const inputs = document.querySelectorAll('input[required], select[required]');
                inputs.forEach(input => {
                    input.addEventListener('blur', (e) => {
                        if (!this.autoFilledFields.has(e.target.name)) {
                            this.validateField(e.target);
                            this.updateFieldHighlight(e.target);
                        }
                    });
                    input.addEventListener('focus', (e) => {
                        this.hideFieldError(e.target);
                    });
                });
                document.querySelectorAll('select[required]').forEach(select => {
                    select.addEventListener('change', (e) => {
                        this.updateFieldHighlight(e.target);
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
                this.hideFieldError(field);
                const errorElement = document.createElement('span');
                errorElement.className = 'error-message';
                errorElement.textContent = message;
                errorElement.id = field.name + '-error';
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
                    const allBookings = res.ok ? await res.json() : [];
                    // Фильтруем бронирования: оставляем только те, у которых check_in >= сегодня
                    const today = new Date();
                    today.setHours(0, 0, 0, 0); // Установим время на 00:00:00 для корректного сравнения

                    this.currentBookings = allBookings.filter(booking => {
                        const checkInStr = booking.check_in;
                        if (!checkInStr) return false; // Пропускаем брони без даты заезда

                        // Предполагаем формат DD.MM.YYYY
                        const [day, month, year] = checkInStr.split('.').map(Number);
                        if (isNaN(day) || isNaN(month) || isNaN(year)) return false;

                        const checkInDate = new Date(year, month - 1, day); // month - 1, т.к. в Date месяцы с 0

                        return checkInDate >= today;
                    });

                    this.filteredBookings = [...this.currentBookings]; // Инициализируем filteredBookings
                } catch {
                    this.currentBookings = [];
                    this.filteredBookings = [];
                }
                this.renderGuestList(this.filteredBookings);
            }
            renderGuestList(bookings) {
                const el = document.getElementById('guestList');
                if (!bookings.length) {
                    el.innerHTML = '<div style="padding:20px;text-align:center;color:#666;">Нет активных бронирований</div>';
                    this.hideStep(3);
                    return;
                }
                el.innerHTML = bookings.map((booking, i) => {
                    const isSelected = this.selectedGuest && this.selectedGuest.id === booking.id;
                    const guestName = booking.guest || 'Не указан';
                    const checkIn = booking.check_in || 'Не указана';
                    const checkOut = booking.check_out || 'Не указана';
                    const totalAmount = booking.total_amount || 'Не указана';
                    return `
                        <div class="guest-item ${isSelected ? 'selected' : ''}" data-index="${i}">
                            <div class="guest-name">${this.escapeHtml(guestName)}</div>
                            <div class="guest-dates">📅 ${this.escapeHtml(checkIn)} - ${this.escapeHtml(checkOut)}</div>
                            <div class="guest-details" style="font-size:11px;color:#888;margin-top:2px;">
                                💰 ${this.escapeHtml(totalAmount)} бат
                            </div>
                        </div>
                    `;
                }).join('');
                el.querySelectorAll('.guest-item').forEach(item => {
                    item.addEventListener('click', () => this.selectGuest(bookings[parseInt(item.dataset.index)]));
                });
            }
            selectGuest(guest) {
                this.selectedGuest = guest;
                document.querySelectorAll('.guest-item').forEach(item => {
                    item.classList.toggle('selected', item.dataset.index === guest.id);
                });
                this.clearAutoFilledFields();
                this.fillFormFromGuest(guest);
                this.showStep(3);
                this.updateSummary();
            }
            fillFormFromGuest(guest) {
                if (guest.guest) {
                    const fullnameInput = document.querySelector('input[name="fullname"]');
                    fullnameInput.value = guest.guest;
                    this.autoFilledFields.add('fullname');
                    this.updateFieldHighlight(fullnameInput, true);
                }
                if (guest.phone) {
                    const phoneInput = document.querySelector('input[name="phone"]');
                    const extractedPhone = this.extractFirstPhone(guest.phone);
                    if (extractedPhone) {
                        phoneInput.value = extractedPhone;
                        this.autoFilledFields.add('phone');
                        this.updateFieldHighlight(phoneInput, true);
                    }
                }
                if (guest.check_in) {
                    this.datepickers.check_in.setDate(guest.check_in, true);
                    this.autoFilledFields.add('check_in');
                }
                if (guest.check_out) {
                    this.datepickers.check_out.setDate(guest.check_out, true);
                    this.autoFilledFields.add('check_out');
                }
                const totalAmountInput = document.querySelector('input[name="total_amount"]');
                if (guest.total_amount) {
                    const amount = guest.total_amount.replace(/\s/g, '');
                    totalAmountInput.value = amount;
                    this.autoFilledFields.add('total_amount');
                    this.updateFieldHighlight(totalAmountInput, true);
                } else {
                    totalAmountInput.value = '';
                    this.autoFilledFields.delete('total_amount');
                }
                const prepaymentBathInput = document.querySelector('input[name="prepayment_bath"]');
                let prepaymentBath = '';
                if (guest.prepayment) {
                    const parts = guest.prepayment.split('/');
                    prepaymentBath = parts[0].trim().replace(/\s/g, '');
                }
                if (prepaymentBath && /^\d+$/.test(prepaymentBath)) {
                    prepaymentBathInput.value = prepaymentBath;
                    this.autoFilledFields.add('prepayment_bath');
                    this.updateFieldHighlight(prepaymentBathInput, true);
                } else {
                    prepaymentBathInput.value = '';
                    this.autoFilledFields.delete('prepayment_bath');
                }
                // === Доп. оплата (баты) из "Дополнительные доплаты" ===
                const extraPaymentBathInput = document.querySelector('input[name="extraPaymentBath"]');
                let extraValue = '';
                if (guest.extra_charges) {
                    const matches = guest.extra_charges.match(/\+\s*(\d+)|(\d+)/g);
                    if (matches) {
                        const nums = matches.map(m => {
                            const n = m.replace(/\D/g, '');
                            return n ? parseInt(n, 10) : 0;
                        }).filter(n => n > 0);
                        if (nums.length) {
                            const candidate = nums.find(n => n > 31) || nums[nums.length - 1];
                            extraValue = String(candidate);
                        }
                    }
                }
                const nights = this.calculateNights();
                const isShortTerm = nights > 0 && nights < 27;
                const extraPaymentBathField = extraPaymentBathInput.closest('.grid-3').children[2];
                if (isShortTerm) {
                    extraPaymentBathField.style.display = 'block';
                    if (extraValue && /^\d+$/.test(extraValue)) {
                        extraPaymentBathInput.value = extraValue;
                        this.autoFilledFields.add('extraPaymentBath');
                        this.updateFieldHighlight(extraPaymentBathInput, true);
                    } else {
                        extraPaymentBathInput.value = '';
                        this.autoFilledFields.delete('extraPaymentBath');
                    }
                } else {
                    extraPaymentBathField.style.display = 'none';
                    extraPaymentBathInput.value = '0';
                    this.autoFilledFields.add('extraPaymentBath');
                    this.updateFieldHighlight(extraPaymentBathInput, true);
                }
                this.calculateNights();
                this.updateContractType();
            }
            extractFirstPhone(phoneText) {
                if (!phoneText) return '';
                const phoneMatch = phoneText.match(/[\+]?[7|8][\s(]?[0-9]{3}[\s)]?[\s-]?[0-9]{3}[\s-]?[0-9]{2}[\s-]?[0-9]{2}/);
                if (phoneMatch) {
                    let phone = phoneMatch[0];
                    phone = phone.replace(/\D/g, '');
                    if (phone.startsWith('7') || phone.startsWith('8')) {
                        phone = '7' + phone.substring(1);
                    }
                    if (phone.length === 11) {
                        return this.formatPhone(phone);
                    }
                }
                return '';
            }
            formatPhone(phone) {
                return `+7 (${phone.substring(1, 4)}) ${phone.substring(4, 7)}-${phone.substring(7, 9)}-${phone.substring(9, 11)}`;
            }
            filterGuests(query) {
                // Фильтруем отфильтрованные бронирования (те, что уже не в прошлом)
                const filtered = this.filteredBookings.filter(booking =>
                    booking.guest?.toLowerCase().includes(query.toLowerCase()) ||
                    booking.phone?.toLowerCase().includes(query.toLowerCase())
                );
                this.renderGuestList(filtered);
            }
            calculateNights() {
                const checkIn = this.datepickers.check_in.selectedDates[0];
                const checkOut = this.datepickers.check_out.selectedDates[0];
                let nights = '';
                if (checkIn && checkOut) {
                    const diff = Math.ceil((checkOut - checkIn) / (1000 * 60 * 60 * 24));
                    nights = diff > 0 ? diff : 0;
                }
                const nightsInput = document.getElementById('nights');
                if (nightsInput) nightsInput.value = nights;
                return parseInt(nights) || 0;
            }
            updateContractType() {
                const nights = this.calculateNights();
                const select = document.getElementById('contractType');
                const info = document.getElementById('contractTypeInfo');
                if (nights >= 27) {
                    select.value = 'среднесрок';
                    info.innerHTML = '<span class="contract-type-badge contract-type-medium">Автоматически: Среднесрочный (27+ ночей)</span>';
                } else if (nights > 0) {
                    select.value = 'краткосрок';
                    info.innerHTML = '<span class="contract-type-badge contract-type-short">Автоматически: Краткосрочный</span>';
                } else {
                    select.value = '';
                    info.innerHTML = '';
                }
            }
            updateSummary() {
                const formData = new FormData(document.getElementById('contractForm'));
                const objectSelect = document.getElementById('objectSelect');
                const objectText = objectSelect.options[objectSelect.selectedIndex]?.text || '-';
                document.getElementById('summaryObject').textContent = objectText;
                document.getElementById('summaryContractType').textContent = formData.get('contract_type') || '-';
                document.getElementById('summaryFullname').textContent = formData.get('fullname') || '-';
                document.getElementById('summaryPassport').textContent = `${formData.get('passport_series') || ''} ${formData.get('passport_number') || ''}`.trim() || '-';
                document.getElementById('summaryPeriod').textContent = `${formData.get('check_in') || ''} - ${formData.get('check_out') || ''}`;
                document.getElementById('summaryNights').textContent = document.getElementById('nights').value || '-';
                document.getElementById('summaryTotalAmount').textContent = formData.get('total_amount') ? `${formData.get('total_amount')} бат` : '-';
                const hasData = Array.from(formData.entries()).some(([key, value]) => value && !['contract_object', 'token', 'chat_id', 'init_chat_id'].includes(key));
                document.getElementById('summarySection').style.display = hasData ? 'block' : 'none';
            }
            isValidDate(dateString) {
                if (!dateString) return false;
                const parts = dateString.split('.');
                if (parts.length !== 3) return false;
                const day = parseInt(parts[0], 10);
                const month = parseInt(parts[1], 10);
                const year = parseInt(parts[2], 10);
                const date = new Date(year, month - 1, day);
                return date.getDate() === day && date.getMonth() === month - 1 && date.getFullYear() === year;
            }
            showStep(stepNumber) {
                document.getElementById(`step${stepNumber}`).classList.remove('hidden-section');
            }
            hideStep(stepNumber) {
                document.getElementById(`step${stepNumber}`).classList.add('hidden-section');
            }
            escapeHtml(text) {
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }
            async submitForm() {
                if (this.isSubmitting) return;
                const requiredFields = document.querySelectorAll('[required]');
                let isValid = true;
                let firstErrorField = null;
                requiredFields.forEach(field => {
                    if (!this.autoFilledFields.has(field.name) && !this.validateField(field)) {
                        isValid = false;
                        if (!firstErrorField) {
                            firstErrorField = field;
                        }
                    }
                });
                if (!isValid && firstErrorField) {
                    firstErrorField.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    firstErrorField.focus();
                    this.tg.showPopup({
                        title: 'Ошибка',
                        message: 'Пожалуйста, заполните все обязательные поля корректно',
                        buttons: [{ type: 'ok' }]
                    });
                    return;
                }
                this.setSubmitButtonState(true, true);
                document.getElementById('loading').style.display = 'block';
                try {
                    const formData = new FormData(document.getElementById('contractForm'));
                    const fullnameRaw = formData.get('fullname') || 'Арендатор';
                    const parts = fullnameRaw.trim().split(/\s+/);
                    let shortName = 'Арендатор';
                    if (parts.length >= 3) {
                        shortName = `${parts[0]}_${parts[1][0]}_${parts[2][0]}`;
                    } else if (parts.length === 2) {
                        shortName = `${parts[0]}_${parts[1][0]}`;
                    } else {
                        shortName = parts[0] || 'Арендатор';
                    }
                    shortName = shortName.replace(/[^a-zA-Zа-яА-ЯёЁ0-9_]/g, '');
                    const formatDateShort = (d) => {
                        const [dd, mm, yyyy] = d.split('.');
                        return `${yyyy.slice(-2)}${mm}${dd}`;
                    };
                    const checkInShort = formatDateShort(formData.get('check_in'));
                    const checkOutShort = formatDateShort(formData.get('check_out'));
                    const filename = `Договор_${formData.get('contract_object')}_${formData.get('contract_type')}_${shortName}_${checkInShort}_${checkOutShort}.json`;
                    const contractData = {
                        form_type: 'contract',
                        init_chat_id: <?= $INIT_CHAT_ID_JS ?>,
                        contract_object: formData.get('contract_object'),
                        contract_type: formData.get('contract_type'),
                        fullname: formData.get('fullname'),
                        passport_series: formData.get('passport_series'),
                        passport_number: formData.get('passport_number'),
                        passport_issued: formData.get('passport_issued'),
                        passport_date: formData.get('passport_date'),
                        phone: formData.get('phone'),
                        check_in: formData.get('check_in'),
                        check_out: formData.get('check_out'),
                        total_amount: formData.get('total_amount'),
                        prepayment_bath: formData.get('prepayment_bath'),
                        extraPaymentBath: formData.get('extraPaymentBath'),
                        interim_cleaning: formData.get('interim_cleaning') ? '1' : '0',
                        electric: formData.get('electric') ? '1' : '0',
                        selected_guest_id: this.selectedGuest?.id || '',
                        selected_guest_name: this.selectedGuest?.guest || '',
                        timestamp: new Date().toLocaleString('ru-RU'),
                        filename: filename
                    };
                    const response = await fetch(`send_to_telegram.php?token=<?= $TELEGRAM_BOT_TOKEN ?>&chat_id=<?= $CHAT_ID ?>&as_file=1`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(contractData)
                    });
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    const result = await response.json();
                    if (result.ok) {
                        this.tg.showPopup({
                            title: '✅ Успех',
                            message: 'Данные договора успешно отправлены!',
                            buttons: [{ type: 'ok' }]
                        });
                        setTimeout(() => {
                            this.tg.close();
                        }, 2000);
                    } else {
                        throw new Error(result.error || 'Неизвестная ошибка отправки');
                    }
                } catch (error) {
                    console.error('Submit error:', error);
                    let errorMessage = 'Не удалось отправить данные. Попробуйте еще раз.';
                    if (error.name === 'AbortError') {
                        errorMessage = 'Превышено время ожидания ответа от сервера. Проверьте подключение к интернету.';
                    } else if (error.message) {
                        errorMessage = error.message;
                    }
                    this.tg.showPopup({
                        title: '❌ Ошибка',
                        message: errorMessage,
                        buttons: [{ type: 'ok' }]
                    });
                } finally {
                    this.setSubmitButtonState(false, false);
                    document.getElementById('loading').style.display = 'none';
                    clearTimeout(this.submitTimeout);
                }
            }
        }
        document.addEventListener('DOMContentLoaded', () => {
            new TelegramContractForm();
        });
    </script>
</body>
</html>