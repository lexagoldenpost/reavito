<?php
$TELEGRAM_BOT_TOKEN = $_GET['token'] ?? '';
$CHAT_ID = $_GET['chat_id'] ?? '';
$INIT_CHAT_ID = $_GET['init_chat_id'] ?? '';

if (empty($TELEGRAM_BOT_TOKEN) || empty($CHAT_ID) || empty($INIT_CHAT_ID)) {
    http_response_code(400);
    die('❌ Отсутствуют параметры в URL.');
}

$INIT_CHAT_ID_JS = json_encode($INIT_CHAT_ID);

function getRentalObjects() {
    $bookingFilesPath = __DIR__ . '/booking_files/*.csv';
    $files = glob($bookingFilesPath);
    $objects = [];
    foreach ($files as $file) {
        $filename = pathinfo($file, PATHINFO_FILENAME);
        $displayName = ucwords(str_replace('_', ' ', $filename));
        $objects[$filename] = $displayName;
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
    <title>✏️ Редактировать бронирование</title>
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
        .btn-tg-success, .btn-tg-danger {
            color: white;
            border: none;
            padding: 14px 20px;
            border-radius: 10px;
            font-weight: 600;
            width: 100%;
            margin: 8px 0;
            transition: all 0.2s ease;
            font-size: 15px;
            cursor: pointer;
        }
        .btn-tg-success { background: #28a745; }
        .btn-tg-danger { background: #dc3545; }
        .btn-tg-success:active, .btn-tg-danger:active {
            transform: scale(0.98);
            opacity: 0.9;
        }
        .btn-tg-success:disabled, .btn-tg-danger:disabled {
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
        .payment-buttons, .source-buttons {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 8px;
        }
        .payment-btn, .source-btn {
            background: #f0f8ff;
            border: 1px solid #2481cc;
            color: #2481cc;
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .payment-btn.active, .source-btn.active {
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

        /* Список бронирований */
        .booking-list {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            max-height: 200px;
            overflow-y: auto;
            background: var(--tg-theme-bg-color);
        }
        .booking-item {
            padding: 10px 12px;
            cursor: pointer;
            border-bottom: 1px solid #f0f0f0;
            color: var(--tg-theme-text-color);
        }
        .booking-item:last-child {
            border-bottom: none;
        }
        .booking-item:hover {
            background-color: #f5f9ff;
        }
        .booking-placeholder {
            padding: 10px 12px;
            color: #888;
            font-style: italic;
        }
        .booking-item.active {
            background-color: #e6f2ff;
            font-weight: 600;
        }

        @media (max-width: 480px) {
            .container { padding: 8px; }
            .form-container { padding: 12px; }
            .grid-2 { grid-template-columns: 1fr; gap: 8px; }
            .form-control { padding: 12px; font-size: 16px; }
            .btn-tg-success, .btn-tg-danger { padding: 16px 20px; font-size: 16px; }
        }
        @media (min-width: 768px) {
            .container { max-width: 500px; margin: 0 auto; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✏️ Редактировать бронирование</h1>
            <p>Выберите объект и бронь</p>
        </div>

        <div class="form-container">
            <div class="form-section">
                <label class="form-label required">Объект недвижимости</label>
                <select class="form-control" id="objectSelect" required>
                    <option value="">Выберите объект...</option>
                    <?php foreach ($rentalObjects as $value => $name): ?>
                        <option value="<?= htmlspecialchars($value) ?>"><?= htmlspecialchars($name) ?></option>
                    <?php endforeach; ?>
                </select>
            </div>

            <div class="form-section">
                <label class="form-label required">Актуальные бронирования</label>
                <div id="bookingList" class="booking-list">
                    <div class="booking-placeholder">Сначала выберите объект</div>
                </div>
            </div>
        </div>

        <form id="bookingForm" style="display:none;">
            <input type="hidden" id="currentSyncId" name="sync_id">

            <div class="form-container">
                <div class="form-section">
                    <label class="form-label required">Имя гостя</label>
                    <input type="text" class="form-control" name="guest" required placeholder="Иванов Иван">
                </div>

                <div class="form-section">
                    <label class="form-label required">Дата бронирования</label>
                    <input type="text" class="form-control flatpickr-input" name="booking_date" value="<?= htmlspecialchars($today) ?>" placeholder="ДД.ММ.ГГГГ" readonly>
                </div>

                <div class="form-section">
                    <div class="grid-2">
                        <div>
                            <label class="form-label required">Заезд</label>
                            <input type="text" class="form-control flatpickr-input" name="check_in" required placeholder="ДД.ММ.ГГГГ" readonly>
                        </div>
                        <div>
                            <label class="form-label required">Выезд</label>
                            <input type="text" class="form-control flatpickr-input" name="check_out" required placeholder="ДД.ММ.ГГГГ" readonly>
                        </div>
                    </div>
                    <div style="margin-top:8px;">
                        <label class="form-label">Количество ночей</label>
                        <input type="text" class="form-control" id="nights" readonly style="background:#f8f9fa;">
                    </div>
                </div>

                <div class="form-section">
                    <label class="form-label required">Сумма (баты)</label>
                    <input type="number" class="form-control" name="total_sum" required placeholder="10000">
                </div>

                <div class="form-section">
                    <div class="section-title">Аванс</div>
                    <div class="grid-2">
                        <div>
                            <label class="form-label required">Баты</label>
                            <input type="text" class="form-control" id="advance_bath" required placeholder="5000">
                        </div>
                        <div>
                            <label class="form-label required">Рубли</label>
                            <input type="text" class="form-control" id="advance_rub" required placeholder="15000">
                        </div>
                    </div>
                </div>

                <div class="form-section">
                    <div class="section-title">Доплата</div>
                    <div class="grid-2">
                        <div>
                            <label class="form-label">Баты</label>
                            <input type="text" class="form-control" id="additional_bath" placeholder="0">
                        </div>
                        <div>
                            <label class="form-label">Рубли</label>
                            <input type="text" class="form-control" id="additional_rub" placeholder="0">
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

                <div class="form-section">
                    <label class="form-label">Способ оплаты</label>
                    <input type="text" class="form-control" id="payment_method" name="payment_method" placeholder="Т-Банк, Альфа и т.д.">
                    <div class="payment-buttons">
                        <?php foreach (['Т-Банк', 'Альфа', 'Райф', 'ГПБ'] as $bank): ?>
                            <div class="payment-btn" data-value="<?= htmlspecialchars($bank) ?>"><?= htmlspecialchars($bank) ?></div>
                        <?php endforeach; ?>
                    </div>
                </div>

                <div class="form-section">
                    <label class="form-label required">Телефон</label>
                    <input type="text" class="form-control" name="phone" required placeholder="Иван +7999...">
                </div>

                <div class="form-section">
                    <label class="form-label">Доп. телефон</label>
                    <input type="text" class="form-control" name="extra_phone" placeholder="Анна +7988...">
                </div>

                <div class="form-section">
                    <label class="form-label">Источник</label>
                    <input type="text" class="form-control" id="source" name="source" placeholder="Авито, Телеграм...">
                    <div class="source-buttons">
                        <?php foreach (['Авито (вотс ап)', 'Телеграм'] as $src): ?>
                            <div class="source-btn" data-value="<?= htmlspecialchars($src) ?>"><?= htmlspecialchars($src) ?></div>
                        <?php endforeach; ?>
                    </div>
                </div>

                <div class="form-section">
                    <label class="form-label">Комментарий</label>
                    <textarea class="form-control" name="comment" rows="2" style="resize:vertical;" placeholder="Комментарий..."></textarea>
                </div>

                <div class="form-section">
                    <label class="form-label">Рейсы</label>
                    <input type="text" class="form-control" name="flights" placeholder="SU123, 10.11.2025">
                </div>

                <button type="submit" class="btn-tg-success" id="saveButton">
                    <span class="button-text">💾 Сохранить изменения</span>
                    <span class="button-loading" style="display:none;">⏳ Сохранение...</span>
                </button>

                <button type="button" class="btn-tg-danger" id="deleteButton">
                    <span class="button-text">🗑️ Удалить бронь</span>
                    <span class="button-loading" style="display:none;">⏳ Удаление...</span>
                </button>
            </div>
        </form>

        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>Загрузка...</p>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>
    <script src="https://cdn.jsdelivr.net/npm/flatpickr/dist/l10n/ru.js"></script>
    <script>
        class TelegramEditBookingForm {
            constructor() {
                this.tg = window.Telegram.WebApp;
                this.tg.expand();
                this.tg.enableClosingConfirmation();
                this.currentBooking = null;
                this.fpBookingDate = null;
                this.fpCheckIn = null;
                this.fpCheckOut = null;
                this.init();
            }

            init() {
                this.bindObjectSelect();
                this.initDatepickers();
                this.bindFormEvents();
                this.initPaymentButtons();
                this.initSourceButtons();
            }

            bindObjectSelect() {
                const objectSelect = document.getElementById('objectSelect');
                const bookingList = document.getElementById('bookingList');

                objectSelect.addEventListener('change', async () => {
                    const object = objectSelect.value;
                    if (!object) {
                        bookingList.innerHTML = '<div class="booking-placeholder">Сначала выберите объект</div>';
                        return;
                    }

                    try {
                        document.getElementById('loading').style.display = 'block';
                        const response = await fetch(`get_bookings.php?object=${encodeURIComponent(object)}`);
                        const bookings = await response.json();

                        if (bookings.length === 0) {
                            bookingList.innerHTML = '<div class="booking-placeholder">Нет активных броней</div>';
                        } else {
                            bookingList.innerHTML = '';
                            bookings.forEach(b => {
                                const div = document.createElement('div');
                                div.className = 'booking-item';
                                div.dataset.guid = b.sync_id;
                                div.textContent = `${b.guest} (${b.check_in} – ${b.check_out})`;
                                div.addEventListener('click', () => {
                                    document.querySelectorAll('.booking-item').forEach(el => el.classList.remove('active'));
                                    div.classList.add('active');
                                    this.loadBooking(object, b.sync_id);
                                });
                                bookingList.appendChild(div);
                            });
                        }
                    } catch (e) {
                        console.error(e);
                        this.tg.showPopup({ title: 'Ошибка', message: 'Не удалось загрузить брони', buttons: [{type:'ok'}] });
                    } finally {
                        document.getElementById('loading').style.display = 'none';
                    }
                });
            }

            async loadBooking(object, sync_id) {
                try {
                    document.getElementById('loading').style.display = 'block';
                    const response = await fetch(`get_booking.php?object=${encodeURIComponent(object)}&sync_id=${encodeURIComponent(sync_id)}`);
                    const data = await response.json();

                    if (!data.sync_id) throw new Error('Бронь не найдена');

                    this.currentBooking = data;

                    document.getElementById('currentSyncId').value = data.sync_id;
                    document.querySelector('[name="guest"]').value = data.guest || '';
                    this.fpBookingDate.setDate(data.booking_date || '');
                    this.fpCheckIn.setDate(data.check_in || '');
                    this.fpCheckOut.setDate(data.check_out || '');
                    document.querySelector('[name="total_sum"]').value = data.total_sum || '';
                    document.querySelector('[name="extra_charges"]').value = data.extra_charges || '';
                    document.querySelector('[name="expenses"]').value = data.expenses || '';
                    document.querySelector('[name="payment_method"]').value = data.payment_method || '';
                    document.querySelector('[name="phone"]').value = data.phone || '';
                    document.querySelector('[name="extra_phone"]').value = data.extra_phone || '';
                    document.querySelector('[name="source"]').value = data.source || '';
                    document.querySelector('[name="comment"]').value = data.comment || '';
                    document.querySelector('[name="flights"]').value = data.flights || '';

                    // Разбор аванса и доплаты
                    const parseAmount = (str) => {
                        if (!str) return ['0', '0'];
                        const clean = str.replace(/\s+/g, '');
                        if (clean.includes('/')) {
                            return clean.split('/');
                        } else if (clean.includes('+')) {
                            const num = clean.split('+')[0];
                            return [num, '0'];
                        }
                        return [clean, '0'];
                    };

                    const adv = parseAmount(data.advance);
                    document.getElementById('advance_bath').value = adv[0] || '0';
                    document.getElementById('advance_rub').value = adv[1] || '0';

                    const add = parseAmount(data.additional_payment);
                    document.getElementById('additional_bath').value = add[0] || '0';
                    document.getElementById('additional_rub').value = add[1] || '0';

                    document.getElementById('bookingForm').style.display = 'block';
                    this.calculateNights();

                } catch (e) {
                    console.error(e);
                    this.tg.showPopup({ title: 'Ошибка', message: e.message || 'Не удалось загрузить данные', buttons: [{type:'ok'}] });
                } finally {
                    document.getElementById('loading').style.display = 'none';
                }
            }

            initDatepickers() {
                const commonConfig = {
                    locale: 'ru',
                    dateFormat: 'd.m.Y',
                    allowInput: false
                };

                this.fpBookingDate = flatpickr('input[name="booking_date"]', { ...commonConfig });
                this.fpCheckIn = flatpickr('input[name="check_in"]', {
                    ...commonConfig,
                    minDate: 'today',
                    onChange: () => this.calculateNights()
                });
                this.fpCheckOut = flatpickr('input[name="check_out"]', {
                    ...commonConfig,
                    minDate: 'today',
                    onChange: () => this.calculateNights()
                });
            }

            calculateNights() {
                const checkIn = this.fpCheckIn.selectedDates[0];
                const checkOut = this.fpCheckOut.selectedDates[0];
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
                    });
                });
            }

            initSourceButtons() {
                document.querySelectorAll('.source-btn').forEach(btn => {
                    btn.addEventListener('click', () => {
                        const input = document.getElementById('source');
                        input.value = btn.dataset.value;
                        document.querySelectorAll('.source-btn').forEach(b => b.classList.remove('active'));
                        btn.classList.add('active');
                    });
                });
            }

            bindFormEvents() {
                document.getElementById('bookingForm').addEventListener('submit', (e) => {
                    e.preventDefault();
                    this.saveBooking();
                });

                document.getElementById('deleteButton').addEventListener('click', () => {
                    this.deleteBooking();
                });
            }

            validateForm() {
                // Сброс стилей
                document.querySelectorAll('.form-control').forEach(el => {
                    el.classList.remove('field-error', 'field-valid');
                });

                const requiredFields = [
                    { selector: '[name="guest"]', label: 'Имя гостя' },
                    { selector: '[name="booking_date"]', label: 'Дата бронирования' },
                    { selector: '[name="check_in"]', label: 'Заезд' },
                    { selector: '[name="check_out"]', label: 'Выезд' },
                    { selector: '[name="total_sum"]', label: 'Сумма (баты)' },
                    { selector: '#advance_bath', label: 'Аванс (баты)' },
                    { selector: '#advance_rub', label: 'Аванс (рубли)' },
                    { selector: '[name="phone"]', label: 'Телефон' }
                ];

                let isValid = true;
                for (const field of requiredFields) {
                    const el = document.querySelector(field.selector);
                    if (!el || el.value.trim() === '') {
                        el?.classList.add('field-error');
                        isValid = false;
                    } else {
                        el?.classList.add('field-valid');
                    }
                }

                const checkIn = this.fpCheckIn.selectedDates[0];
                const checkOut = this.fpCheckOut.selectedDates[0];
                if (checkIn && checkOut && checkOut <= checkIn) {
                    document.querySelector('[name="check_in"]').classList.add('field-error');
                    document.querySelector('[name="check_out"]').classList.add('field-error');
                    this.tg.showPopup({ title: 'Ошибка', message: 'Дата выезда должна быть позже даты заезда', buttons: [{type:'ok'}] });
                    return false;
                }

                if (!isValid) {
                    this.tg.showPopup({ title: 'Ошибка', message: 'Заполните все обязательные поля', buttons: [{type:'ok'}] });
                    return false;
                }

                return true;
            }

            async saveBooking() {
                if (!this.validateForm()) return;

                this.setButtonsState(true, true);

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

                    const filename = `Изменение_Бронь_${document.getElementById('objectSelect').value}_${shortName}_${formatDateShort(checkIn)}_${formatDateShort(checkOut)}.json`;

                    const payload = {
                        form_type: 'edit_booking',
                        init_chat_id: <?= $INIT_CHAT_ID_JS ?>,
                        _sync_id: document.getElementById('currentSyncId').value,
                        object: document.getElementById('objectSelect').value,
                        guest: formData.get('guest'),
                        booking_date: formData.get('booking_date'),
                        check_in: formData.get('check_in'),
                        check_out: formData.get('check_out'),
                        nights: document.getElementById('nights').value,
                        total_sum: formData.get('total_sum'),
                        advance: document.getElementById('advance_bath').value + '/' + document.getElementById('advance_rub').value,
                        additional_payment: (document.getElementById('additional_bath').value || '0') + '/' + (document.getElementById('additional_rub').value || '0'),
                        extra_charges: formData.get('extra_charges') || '',
                        expenses: formData.get('expenses') || '',
                        payment_method: formData.get('payment_method') || '',
                        phone: formData.get('phone'),
                        extra_phone: formData.get('extra_phone') || '',
                        source: formData.get('source') || '',
                        comment: formData.get('comment') || '',
                        flights: formData.get('flights') || '',
                        timestamp: new Date().toLocaleString('ru-RU'),
                        filename: filename
                    };

                    const response = await fetch(`send_to_telegram.php?token=<?= $TELEGRAM_BOT_TOKEN ?>&chat_id=<?= $CHAT_ID ?>&as_file=1`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });

                    const result = await response.json();
                    if (result.ok) {
                        this.tg.showPopup({ title: '✅ Успех', message: 'Бронь отправлена на обновление!', buttons: [{type:'ok'}] });
                        setTimeout(() => this.tg.close(), 2000);
                    } else {
                        throw new Error(result.error || 'Ошибка сохранения');
                    }

                } catch (error) {
                    console.error(error);
                    this.tg.showPopup({ title: '❌ Ошибка', message: error.message, buttons: [{type:'ok'}] });
                } finally {
                    this.setButtonsState(false, false);
                }
            }

            async deleteBooking() {
    if (!confirm('Вы уверены, что хотите удалить эту бронь?')) return;

    this.setButtonsState(true, false, true);

    try {
        const guest = this.currentBooking.guest || 'Гость';
        const shortName = guest.split(' ')[0] || 'Гость';
        const checkIn = this.currentBooking.check_in;
        const checkOut = this.currentBooking.check_out;

        const formatDateShort = (d) => {
            const [dd, mm, yyyy] = d.split('.');
            return `${yyyy.slice(-2)}${mm}${dd}`;
        };

        const filename = `Удаление_Бронь_${document.getElementById('objectSelect').value}_${shortName}_${formatDateShort(checkIn)}_${formatDateShort(checkOut)}.json`;

        const payload = {
            form_type: 'delete_booking',
            _sync_id: this.currentBooking.sync_id,
            guest: this.currentBooking.guest,
            object: document.getElementById('objectSelect').value,
            init_chat_id: <?= $INIT_CHAT_ID_JS ?>,
            filename: filename
        };

        const response = await fetch(`send_to_telegram.php?token=<?= $TELEGRAM_BOT_TOKEN ?>&chat_id=<?= $CHAT_ID ?>&as_file=1`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const result = await response.json();
        if (result.ok) {
            this.tg.showPopup({ title: '🗑️ Удалено', message: 'Бронь отправлена на удаление!', buttons: [{type:'ok'}] });
            setTimeout(() => this.tg.close(), 1500);
        } else {
            throw new Error(result.error || 'Ошибка удаления');
        }

    } catch (error) {
        console.error(error);
        this.tg.showPopup({ title: '❌ Ошибка', message: error.message, buttons: [{type:'ok'}] });
    } finally {
        this.setButtonsState(false, false, false);
    }
}

            setButtonsState(disabled, saving = false, deleting = false) {
                const saveBtn = document.getElementById('saveButton');
                const delBtn = document.getElementById('deleteButton');

                saveBtn.disabled = disabled;
                delBtn.disabled = disabled;

                saveBtn.querySelector('.button-text').style.display = saving ? 'none' : 'inline';
                saveBtn.querySelector('.button-loading').style.display = saving ? 'inline' : 'none';

                delBtn.querySelector('.button-text').style.display = deleting ? 'none' : 'inline';
                delBtn.querySelector('.button-loading').style.display = deleting ? 'inline' : 'none';
            }
        }

        document.addEventListener('DOMContentLoaded', () => new TelegramEditBookingForm());
    </script>
</body>
</html>