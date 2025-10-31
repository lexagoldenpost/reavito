<?php
// add_booking_form.php — форма создания бронирования для Telegram Mini App
$TELEGRAM_BOT_TOKEN = $_GET['token'] ?? '';
$CHAT_ID = $_GET['chat_id'] ?? '';
$INIT_CHAT_ID = $_GET['init_chat_id'] ?? '';

if (empty($TELEGRAM_BOT_TOKEN) || empty($CHAT_ID) || empty($INIT_CHAT_ID)) {
    http_response_code(400);
    die('❌ Отсутствуют параметры в URL.');
}

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
$today = date('d.m.Y');
?>
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>➕ Новое бронирование</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css">
    <style>
        /* Скопированы стили из contract_form.php */
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
        }
        .grid-2 {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .grid-3 {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
        }
        .payment-buttons {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 8px;
        }
        .payment-btn {
            background: #f0f8ff;
            border: 1px solid #2481cc;
            color: #2481cc;
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .payment-btn:hover {
            background: #e0f0ff;
        }
        .payment-btn.active {
            background: #2481cc;
            color: white;
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
        .field-hint {
            font-size: 11px;
            color: #666;
            margin-top: -8px;
            margin-bottom: 8px;
            display: block;
        }
        .field-error {
            border-color: #dc3545 !important;
            background-color: rgba(220, 53, 69, 0.05) !important;
        }
        .field-valid {
            border-color: #28a745 !important;
            background-color: rgba(40, 167, 69, 0.05) !important;
        }
        .error-message {
            color: #dc3545;
            font-size: 12px;
            margin-top: -8px;
            margin-bottom: 8px;
            display: block;
        }
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
        @media (max-width: 480px) {
            .container { padding: 8px; }
            .form-container { padding: 12px; }
            .grid-2, .grid-3 { grid-template-columns: 1fr; gap: 8px; }
            .form-control { padding: 12px; font-size: 16px; }
            .btn-tg-success { padding: 16px 20px; font-size: 16px; }
        }
        @media (min-width: 768px) {
            .container { max-width: 500px; margin: 0 auto; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>➕ Новое бронирование</h1>
            <p>Заполните данные для создания брони</p>
        </div>
        <form id="bookingForm">
            <div class="form-container">
                <!-- Объект -->
                <div class="form-section">
                    <label class="form-label required">Объект недвижимости</label>
                    <select class="form-control" id="objectSelect" name="object" required>
                        <option value="">Выберите объект...</option>
                        <?php foreach ($rentalObjects as $value => $name): ?>
                            <option value="<?= htmlspecialchars($value) ?>"><?= htmlspecialchars($name) ?></option>
                        <?php endforeach; ?>
                    </select>
                </div>

                <!-- Гость -->
                <div class="form-section">
                    <label class="form-label required">Имя гостя</label>
                    <input type="text" class="form-control" name="guest" required placeholder="Иванов Иван">
                    <span class="field-hint">Минимум 2 символа</span>
                </div>

                <!-- Дата бронирования -->
                <div class="form-section">
                    <label class="form-label">Дата бронирования</label>
                    <input type="text" class="form-control" name="booking_date" value="<?= htmlspecialchars($today) ?>" placeholder="ДД.ММ.ГГГГ">
                </div>

                <!-- Даты -->
                <div class="form-section">
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

                <!-- Финансы -->
                <div class="form-section">
                    <label class="form-label required">Сумма (баты)</label>
                    <input type="number" class="form-control" name="total_sum" required placeholder="10000">
                </div>

                <div class="form-section">
                    <div class="section-title">Аванс</div>
                    <div class="grid-2">
                        <div>
                            <label class="form-label required">Баты</label>
                            <input type="number" class="form-control" id="advance_bath" required placeholder="5000">
                        </div>
                        <div>
                            <label class="form-label required">Рубли</label>
                            <input type="number" class="form-control" id="advance_rub" required placeholder="15000">
                        </div>
                    </div>
                </div>

                <div class="form-section">
                    <div class="section-title">Доплата</div>
                    <div class="grid-2">
                        <div>
                            <label class="form-label">Баты</label>
                            <input type="number" class="form-control" id="additional_bath" placeholder="0">
                        </div>
                        <div>
                            <label class="form-label">Рубли</label>
                            <input type="number" class="form-control" id="additional_rub" placeholder="0">
                        </div>
                    </div>
                </div>

                <div class="form-section">
                    <label class="form-label">Дополнительные доплаты</label>
                    <input type="text" class="form-control" name="extra_charges" placeholder="Уборка, трансфер...">
                </div>

                <div class="form-section">
                    <label class="form-label">Расходы</label>
                    <input type="text" class="form-control" name="expenses" placeholder="Коммунальные, уборка...">
                </div>

                <!-- Оплата -->
                <div class="form-section">
                    <label class="form-label">Способ оплаты</label>
                    <input type="text" class="form-control" id="payment_method" name="payment_method" placeholder="Т-Банк, Альфа и т.д.">
                    <div class="payment-buttons">
                        <?php foreach (['Т-Банк', 'Альфа', 'Райф', 'ГПБ'] as $bank): ?>
                            <div class="payment-btn" data-value="<?= htmlspecialchars($bank) ?>"><?= htmlspecialchars($bank) ?></div>
                        <?php endforeach; ?>
                    </div>
                </div>

                <!-- Контакты -->
                <div class="form-section">
                    <label class="form-label required">Телефон</label>
                    <input type="text" class="form-control" name="phone" required placeholder="Иван +7999...">
                </div>

                <div class="form-section">
                    <label class="form-label">Доп. телефон</label>
                    <input type="text" class="form-control" name="extra_phone" placeholder="Анна +7988...">
                </div>

                <div class="form-section">
                    <label class="form-label">Комментарий</label>
                    <textarea class="form-control" name="comment" rows="2" style="resize:vertical;" placeholder="Особые пожелания..."></textarea>
                </div>

                <div class="form-section">
                    <label class="form-label">Рейсы</label>
                    <input type="text" class="form-control" name="flights" placeholder="SU123, 10.11.2025">
                </div>

                <button type="submit" class="btn-tg-success" id="submitButton">
                    <span class="button-text">📨 Создать бронирование</span>
                    <span class="button-loading" style="display:none;">⏳ Отправка...</span>
                </button>
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
        class TelegramBookingForm {
            constructor() {
                this.tg = window.Telegram.WebApp;
                this.tg.expand();
                this.tg.enableClosingConfirmation();
                this.datepickers = {};
                this.isSubmitting = false;
                this.init();
            }

            init() {
                this.initDatepickers();
                this.bindEvents();
                this.initPaymentButtons();
                this.highlightRequiredFields();
            }

            initDatepickers() {
                const config = {
                    locale: 'ru',
                    dateFormat: 'd.m.Y',
                    allowInput: false,
                    minDate: 'today',
                    onChange: () => this.calculateNights()
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
            }

            calculateNights() {
                const checkIn = this.datepickers.check_in.selectedDates[0];
                const checkOut = this.datepickers.check_out.selectedDates[0];
                let nights = '';
                if (checkIn && checkOut) {
                    const diff = Math.ceil((checkOut - checkIn) / (1000 * 60 * 60 * 24));
                    nights = diff > 0 ? diff : 0;
                }
                document.getElementById('nights').value = nights;
            }

            initPaymentButtons() {
                document.querySelectorAll('.payment-btn').forEach(btn => {
                    btn.addEventListener('click', () => {
                        const input = document.getElementById('payment_method');
                        input.value = btn.dataset.value;
                        document.querySelectorAll('.payment-btn').forEach(b => b.classList.remove('active'));
                        btn.classList.add('active');
                        this.updateFieldHighlight(input);
                    });
                });
            }

            bindEvents() {
                document.getElementById('bookingForm').addEventListener('submit', (e) => {
                    e.preventDefault();
                    this.submitForm();
                });

                const inputs = document.querySelectorAll('input[required], select[required]');
                inputs.forEach(input => {
                    input.addEventListener('blur', () => this.validateField(input));
                    input.addEventListener('focus', () => this.hideFieldError(input));
                    input.addEventListener('input', () => this.updateFieldHighlight(input));
                });

                document.querySelectorAll('select[required]').forEach(select => {
                    select.addEventListener('change', () => this.updateFieldHighlight(select));
                });

                // Числовые поля — только цифры
                document.querySelectorAll('input[type="number"]').forEach(input => {
                    input.addEventListener('input', (e) => {
                        e.target.value = e.target.value.replace(/\D/g, '');
                    });
                });
            }

            validateField(field) {
                const value = field.value.trim();
                const fieldName = field.name || field.id;

                if (!value) {
                    if (field.hasAttribute('required')) {
                        this.showError(field, 'Это поле обязательно для заполнения');
                        return false;
                    }
                    return true;
                }

                let isValid = true;
                let msg = '';

                switch(fieldName) {
                    case 'guest':
                        isValid = value.length >= 2;
                        msg = 'Минимум 2 символа';
                        break;
                    case 'check_in':
                    case 'check_out':
                        isValid = this.isValidDate(value);
                        msg = 'Некорректная дата';
                        break;
                    case 'total_sum':
                    case 'advance_bath':
                    case 'advance_rub':
                        isValid = /^\d+$/.test(value) && parseInt(value) > 0;
                        msg = 'Введите положительное число';
                        break;
                    case 'additional_bath':
                    case 'additional_rub':
                        isValid = /^\d*$/.test(value); // может быть пустым
                        msg = 'Только цифры';
                        break;
                    case 'phone':
                        isValid = value.length >= 2;
                        msg = 'Минимум 2 символа';
                        break;
                }

                if (!isValid) {
                    this.showError(field, msg);
                    return false;
                }

                this.hideFieldError(field);
                return true;
            }

            showError(field, msg) {
                field.classList.add('field-error');
                this.hideFieldError(field);
                const err = document.createElement('span');
                err.className = 'error-message';
                err.id = field.name + '-error';
                err.textContent = msg;
                field.parentNode.insertBefore(err, field.nextSibling);
            }

            hideFieldError(field) {
                const el = document.getElementById(field.name + '-error');
                if (el) el.remove();
                field.classList.remove('field-error', 'field-valid');
            }

            updateFieldHighlight(field) {
                if (this.validateField(field)) {
                    field.classList.add('field-valid');
                }
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

            setSubmitButtonState(disabled, loading = false) {
                const btn = document.getElementById('submitButton');
                const txt = btn.querySelector('.button-text');
                const load = btn.querySelector('.button-loading');
                btn.disabled = disabled;
                this.isSubmitting = disabled;
                if (loading) {
                    txt.style.display = 'none';
                    load.style.display = 'inline';
                } else {
                    txt.style.display = 'inline';
                    load.style.display = 'none';
                }
            }

            async submitForm() {
                if (this.isSubmitting) return;

                const requiredFields = ['object', 'guest', 'check_in', 'check_out', 'total_sum', 'advance_bath', 'advance_rub', 'phone'];
                let valid = true;
                for (const name of requiredFields) {
                    const field = document.querySelector(`[name="${name}"], #${name}`);
                    if (!this.validateField(field)) valid = false;
                }

                if (!valid) {
                    this.tg.showPopup({ title: 'Ошибка', message: 'Проверьте обязательные поля', buttons: [{type:'ok'}] });
                    return;
                }

                this.setSubmitButtonState(true, true);
                document.getElementById('loading').style.display = 'block';

                try {
                    const formData = new FormData(document.getElementById('bookingForm'));
                    const guest = formData.get('guest') || 'Гость';
                    const shortName = guest.split(' ')[0] || 'Гость';
                    const checkIn = formData.get('check_in');
                    const checkOut = formData.get('check_out');

                    const formatDateShort = (d) => {
                        const [dd, mm, yyyy] = d.split('.');
                        return `${yyyy.slice(-2)}${mm}${dd}`;
                    };

                    const filename = `Бронь_${formData.get('object')}_${shortName}_${formatDateShort(checkIn)}_${formatDateShort(checkOut)}.json`;

                    // Собираем аванс и доплату
                    const advanceBath = document.getElementById('advance_bath').value;
                    const advanceRub = document.getElementById('advance_rub').value;
                    const additionalBath = document.getElementById('additional_bath').value;
                    const additionalRub = document.getElementById('additional_rub').value;

                    const advance = advanceBath + '/' + advanceRub;
                    const additional_payment = (additionalBath || '0') + '/' + (additionalRub || '0');

                    const bookingData = {
                        form_type: 'booking',
                        object: formData.get('object'),
                        guest: formData.get('guest'),
                        booking_date: formData.get('booking_date') || '<?= $today ?>',
                        check_in: formData.get('check_in'),
                        check_out: formData.get('check_out'),
                        nights: document.getElementById('nights').value,
                        total_sum: formData.get('total_sum'),
                        advance: advance,
                        additional_payment: additional_payment,
                        extra_charges: formData.get('extra_charges') || '',
                        expenses: formData.get('expenses') || '',
                        payment_method: formData.get('payment_method') || '',
                        phone: formData.get('phone'),
                        extra_phone: formData.get('extra_phone') || '',
                        comment: formData.get('comment') || '',
                        flights: formData.get('flights') || '',
                        timestamp: new Date().toLocaleString('ru-RU'),
                        filename: filename
                    };

                    const response = await fetch(`send_to_telegram.php?token=<?= $TELEGRAM_BOT_TOKEN ?>&chat_id=<?= $CHAT_ID ?>&as_file=1`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(bookingData)
                    });

                    if (!response.ok) throw new Error(`HTTP ${response.status}`);
                    const result = await response.json();

                    if (result.ok) {
                        this.tg.showPopup({ title: '✅ Успех', message: 'Бронирование создано!', buttons: [{type:'ok'}] });
                        setTimeout(() => this.tg.close(), 2000);
                    } else {
                        throw new Error(result.error || 'Неизвестная ошибка');
                    }

                } catch (error) {
                    console.error('Booking error:', error);
                    this.tg.showPopup({
                        title: '❌ Ошибка',
                        message: error.message || 'Не удалось отправить данные',
                        buttons: [{type:'ok'}]
                    });
                } finally {
                    this.setSubmitButtonState(false, false);
                    document.getElementById('loading').style.display = 'none';
                }
            }

            highlightRequiredFields() {
                document.querySelectorAll('[required]').forEach(f => this.updateFieldHighlight(f));
            }
        }

        document.addEventListener('DOMContentLoaded', () => new TelegramBookingForm());
    </script>
</body>
</html>