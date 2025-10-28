<?php
// contract_form.php — форма договора аренды для Telegram Mini App

// Получаем параметры из URL
$TELEGRAM_BOT_TOKEN = $_GET['token'] ?? '';
$CHAT_ID = $_GET['chat_id'] ?? '';

// Проверка обязательных параметров
if (empty($TELEGRAM_BOT_TOKEN) || empty($CHAT_ID)) {
    http_response_code(400);
    die('❌ Отсутствуют параметры token или chat_id в URL.');
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
        }
        .btn-tg-success:active {
            transform: scale(0.98);
            opacity: 0.9;
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
                            </div>
                            <div>
                                <label class="form-label required">Номер</label>
                                <input type="text" class="form-control" name="passport_number" required placeholder="1234567" pattern="\d{7}" maxlength="7">
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

                    <button type="submit" class="btn-tg-success">📨 Отправить данные договора</button>
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
                this.init();
            }

            init() {
                this.initDatepickers();
                this.bindEvents();
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
                el.innerHTML = bookings.map(b => `
                    <div class="guest-item" data-guest='${JSON.stringify(b).replace(/'/g, "&#39;")}'>
                        <div class="guest-name">${this.escapeHtml(b.guest)}</div>
                        <div class="guest-dates">${b.check_in} - ${b.check_out}</div>
                    </div>
                `).join('');
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
                document.querySelector('[name="phone"]').value = guest.phone || '';
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
                for (const field of required) {
                    if (!field.value.trim()) {
                        valid = false;
                        field.style.borderColor = '#dc3545';
                    } else {
                        field.style.borderColor = '';
                    }
                    if (field.name === 'passport_series' && !/^[A-Za-z0-9]{2}$/.test(field.value)) valid = false;
                    if (field.name === 'passport_number' && !/^\d{7}$/.test(field.value)) valid = false;
                    if (['check_in', 'check_out', 'passport_date'].includes(field.name) && !this.isValidDate(field.value)) valid = false;
                }
                return valid;
            }

            isValidDate(str) {
                const m = str.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
                if (!m) return false;
                const d = new Date(m[3], m[2] - 1, m[1]);
                return d.getFullYear() == m[3] && d.getMonth() == m[2] - 1 && d.getDate() == m[1];
            }

            parseDate(str) {
                const m = str.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
                return m ? new Date(m[3], m[2] - 1, m[1]) : null;
            }

            escapeHtml(text) {
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }

            generateFilename() {
                const data = Object.fromEntries(new FormData(document.getElementById('contractForm')).entries());
                if (!data.contract_object || !data.fullname || !data.check_in || !data.contract_type) return 'договор.json';
                const obj = data.contract_object.replace(/[^a-zA-Zа-яА-Я0-9]/g, '');
                const name = data.fullname.split(' ')[0] || 'арендатор';
                const today = new Date().toLocaleDateString('ru-RU').replace(/\./g, '-');
                const checkin = data.check_in.replace(/\./g, '-');
                return `Договор_${obj}_${data.contract_type}_${name}_${checkin}_${today}.json`;
            }

            showStep(n) { document.getElementById(`step${n}`).classList.remove('hidden-section'); }
            hideStep(n) { document.getElementById(`step${n}`).classList.add('hidden-section'); }

            async submitForm() {
                if (!this.validateForm()) {
                    this.showError('Заполните все обязательные поля правильно');
                    return;
                }

                const formData = new FormData(document.getElementById('contractForm'));
                const data = Object.fromEntries(formData.entries());
                data.timestamp = new Date().toISOString();
                data.days = this.calculateNights();
                data.filename = this.generateFilename();
                data.object_name = document.getElementById('objectSelect').options[document.getElementById('objectSelect').selectedIndex].text;

                document.getElementById('loading').style.display = 'block';
                document.querySelector('button[type="submit"]').disabled = true;

                try {
                    const response = await fetch(`send_to_telegram.php?token=<?= urlencode($TELEGRAM_BOT_TOKEN) ?>&chat_id=<?= urlencode($CHAT_ID) ?>&as_file=1`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        filename: data.filename,
        caption: this.formatTelegramMessage(data),
    data: data
                        })
                    });

                    const result = await response.json();

                    if (response.ok && result.ok) {
                        if (this.tg) {
                            this.tg.showPopup({ title: 'Успешно', message: result.message, buttons: [{ type: 'ok' }] }, () => {
                                setTimeout(() => this.tg.close(), 1000);
                            });
                        } else {
                            alert(result.message);
                            window.close();
                        }
                    } else {
                        throw new Error(result.error || 'Ошибка сервера');
                    }
                } catch (err) {
                    console.error(err);
                    this.showError('Ошибка: ' + (err.message || 'неизвестная ошибка'));
                } finally {
                    document.getElementById('loading').style.display = 'none';
                    document.querySelector('button[type="submit"]').disabled = false;
                }
            }

            formatTelegramMessage(data) {
                const type = data.contract_type === 'краткосрок' ? 'Краткосрочный' : 'Среднесрочный';
                return `📄 *НОВЫЙ ДОГОВОР АРЕНДЫ*
🏢 *Объект:* ${data.object_name}
📑 *Тип договора:* ${type}
👤 *Арендатор:* ${data.fullname}
📕 *Загранпаспорт:* ${data.passport_series} ${data.passport_number}
🏛️ *Выдан:* ${data.passport_issued}
📅 *Дата выдачи:* ${data.passport_date}
📞 *Телефон:* ${data.phone}
📅 *Период аренды:*
   Заселение: ${data.check_in}
   Выезд: ${data.check_out}
   Ночей: ${data.days}
💰 *Финансовые условия:*
   Общая сумма: ${data.total_amount} бат
   Предоплата: ${data.prepayment_bath} бат / ${data.prepayment_rub} руб
⏰ *Создан:* ${new Date().toLocaleString('ru-RU')}`;
            }

            showError(msg) {
                if (this.tg) {
                    this.tg.showPopup({ title: 'Ошибка', message: msg, buttons: [{ type: 'ok' }] });
                } else {
                    alert(msg);
                }
            }
        }

        document.addEventListener('DOMContentLoaded', () => new TelegramContractForm());
    </script>
</body>
</html>