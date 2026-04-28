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
        .grid-3 {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
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
        .optional::after {
            content: " (опционально)";
            color: #6c757d;
            font-weight: normal;
            font-size: 12px;
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
        .hidden {
            display: none !important;
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
            .grid-2, .grid-3 { grid-template-columns: 1fr; gap: 8px; }
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
                <!-- Дополнительные поля для booking_other -->
                <div id="ownerSection" class="form-section hidden">
                    <div class="grid-3">
                        <div>
                            <label class="form-label required">Название кондо</label>
                            <input type="text" class="form-control" id="condo_name" name="condo_name" required>
                        </div>
                        <div>
                            <label class="form-label required">Номер апарта</label>
                            <input type="text" class="form-control" id="apartment_number" name="apartment_number" required>
                        </div>
                        <div>
                            <label class="form-label required">Хозяин</label>
                            <input type="text" class="form-control" id="owner_name" name="owner_name" required>
                        </div>
                    </div>
                </div>

                <div class="form-section">
                    <label class="form-label required">Имя гостя</label>
                    <input type="text" class="form-control" name="guest" required placeholder="Иванов Иван">
                    <span class="field-hint">Минимум 2 символа</span>
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

                <!-- Поле комиссии для booking_other -->
                <div id="commissionSection" class="form-section hidden">
                    <label class="form-label">Комиссия (баты)</label>
                    <input type="number" class="form-control" id="commission" name="commission" placeholder="0">
                    <span class="field-hint">Комиссия в батах (только для booking_other)</span>
                </div>

                <!-- Секция аванса (скрыта по умолчанию) -->
                <div class="form-section hidden" id="advanceSection">
                    <div class="section-title">Аванс</div>
                    <div class="grid-2">
                        <div>
                            <label class="form-label required">Баты</label>
                            <input type="text" class="form-control" id="advance_bath" required placeholder="5000" value="0">
                        </div>
                        <div>
                            <label class="form-label required">Рубли</label>
                            <input type="text" class="form-control" id="advance_rub" required placeholder="15000" value="0">
                        </div>
                    </div>
                </div>

                <!-- Секция доплаты (рубли скрыты) -->
                <div class="form-section">
                    <div class="section-title">Доплата</div>
                    <div class="grid-2">
                        <div>
                            <label class="form-label">Баты</label>
                            <input type="text" class="form-control" id="additional_bath" placeholder="0" value="0">
                        </div>
                        <div id="additionalRubSection" class="hidden">
                            <label class="form-label">Рубли</label>
                            <input type="text" class="form-control" id="additional_rub" placeholder="0" value="0">
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

                <!-- Для booking_other телефон не обязательный -->
                <div class="form-section">
                    <label class="form-label required" id="phoneLabel">Телефон</label>
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
                this.isBookingOther = false;
                this.init();
            }

            init() {
                this.bindObjectSelect();
                this.initDatepickers();
                this.bindFormEvents();
                this.initPaymentButtons();
                this.initSourceButtons();
                this.hideRubFields(); // Скрываем поля рублей
            }

            // Метод для скрытия полей аванса и доплаты
            hideRubFields() {
                // Скрываем всю секцию аванса
                const advanceSection = document.getElementById('advanceSection');
                if (advanceSection) {
                    advanceSection.classList.add('hidden');
                }

                // Скрываем секцию доплаты в рублях
                const additionalRubSection = document.getElementById('additionalRubSection');
                if (additionalRubSection) {
                    additionalRubSection.classList.add('hidden');
                }

                // Устанавливаем значения по умолчанию
                const advanceBath = document.getElementById('advance_bath');
                const advanceRub = document.getElementById('advance_rub');
                const additionalRub = document.getElementById('additional_rub');

                if (advanceBath) advanceBath.value = '0';
                if (advanceRub) advanceRub.value = '0';
                if (additionalRub) additionalRub.value = '0';
            }

            bindObjectSelect() {
                const objectSelect = document.getElementById('objectSelect');
                const bookingList = document.getElementById('bookingList');

                objectSelect.addEventListener('change', async () => {
                    const object = objectSelect.value;
                    this.isBookingOther = object === 'booking_other';
                    this.toggleBookingOtherFields();

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

            toggleBookingOtherFields() {
                const ownerSection = document.getElementById('ownerSection');
                const commissionSection = document.getElementById('commissionSection');
                const phoneField = document.querySelector('input[name="phone"]');
                const phoneLabel = document.getElementById('phoneLabel');

                if (this.isBookingOther) {
                    ownerSection.classList.remove('hidden');
                    commissionSection.classList.remove('hidden');

                    // Делаем телефон необязательным
                    phoneField.removeAttribute('required');
                    phoneLabel.classList.remove('required');
                    phoneLabel.classList.add('optional');
                    phoneLabel.innerHTML = 'Телефон <span style="color:#6c757d;font-weight:normal;font-size:12px;">(опционально)</span>';

                    // Делаем поля хозяина обязательными
                    document.getElementById('condo_name').setAttribute('required', 'required');
                    document.getElementById('apartment_number').setAttribute('required', 'required');
                    document.getElementById('owner_name').setAttribute('required', 'required');
                } else {
                    ownerSection.classList.add('hidden');
                    commissionSection.classList.add('hidden');

                    // Делаем телефон обязательным
                    phoneField.setAttribute('required', 'required');
                    phoneLabel.classList.add('required');
                    phoneLabel.classList.remove('optional');
                    phoneLabel.textContent = 'Телефон';

                    // Убираем обязательность полей хозяина
                    document.getElementById('condo_name').removeAttribute('required');
                    document.getElementById('apartment_number').removeAttribute('required');
                    document.getElementById('owner_name').removeAttribute('required');
                }
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

                    // Загружаем комиссию для booking_other
                    if (this.isBookingOther && data.Комиссия !== undefined) {
                        document.getElementById('commission').value = data.Комиссия || '';
                    } else if (this.isBookingOther) {
                        document.getElementById('commission').value = '';
                    }

                    // Загружаем данные хозяина для booking_other
                    if (this.isBookingOther) {
                        document.getElementById('condo_name').value = data['Название кондо'] || '';
                        document.getElementById('apartment_number').value = data['Номер апарта'] || '';
                        document.getElementById('owner_name').value = data['Хозяин'] || '';
                    }

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
                    const advanceRubField = document.getElementById('advance_rub');
                    if (advanceRubField) advanceRubField.value = adv[1] || '0';

                    const add = parseAmount(data.additional_payment);
                    document.getElementById('additional_bath').value = add[0] || '0';
                    const additionalRubField = document.getElementById('additional_rub');
                    if (additionalRubField) additionalRubField.value = add[1] || '0';

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
                    onChange: () => this.calculateNights(),
                    onValueUpdate: (dates) => {
                        if (this.fpCheckOut && dates[0]) {
                            this.fpCheckOut.set('minDate', dates[0]);
                        }
                    }
                });
                this.fpCheckOut = flatpickr('input[name="check_out"]', {
                    ...commonConfig,
                    minDate: 'today',
                    onChange: () => this.calculateNights(),
                    onValueUpdate: (dates) => {
                        if (this.fpCheckIn && dates[0]) {
                            const checkIn = this.fpCheckIn.selectedDates[0];
                            if (checkIn && dates[0] <= checkIn) {
                                this.fpCheckOut.setDate(new Date(checkIn.getTime() + 86400000));
                            }
                        }
                    }
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
                        this.updateFieldHighlight(input);
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
                        this.updateFieldHighlight(input);
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

                // Только цифры в числовых полях
                document.querySelectorAll('input[type="number"], #advance_bath, #advance_rub, #additional_bath, #additional_rub, #commission').forEach(input => {
                    input.addEventListener('input', (e) => {
                        e.target.value = e.target.value.replace(/[^\d]/g, '');
                    });
                });

                // Валидация полей
                const inputs = document.querySelectorAll('input[required], select[required]');
                inputs.forEach(input => {
                    input.addEventListener('blur', () => this.validateField(input));
                    input.addEventListener('focus', () => this.hideFieldError(input));
                    input.addEventListener('input', () => this.updateFieldHighlight(input));
                });
            }

            validateField(field) {
                const value = field.value.trim();
                const fieldName = field.name || field.id;

                this.hideFieldError(field);

                // Для booking_other телефон необязателен
                if (fieldName === 'phone' && this.isBookingOther) {
                    if (value && value.length < 2) {
                        field.classList.add('field-error');
                        return false;
                    }
                    return true;
                }

                if (!value) {
                    if (field.hasAttribute('required')) {
                        field.classList.add('field-error');
                        return false;
                    }
                    return true;
                }

                let isValid = true;

                switch(fieldName) {
                    case 'guest':
                        isValid = value.length >= 2;
                        break;
                    case 'booking_date':
                    case 'check_in':
                    case 'check_out':
                        isValid = this.isValidDate(value);
                        break;
                    case 'total_sum':
                    case 'advance_bath':
                    case 'advance_rub':
                    case 'additional_bath':
                    case 'additional_rub':
                    case 'commission':
                        isValid = /^\d*$/.test(value);
                        break;
                    case 'phone':
                        isValid = value.length >= 2;
                        break;
                }

                if (!isValid) {
                    field.classList.add('field-error');
                    return false;
                }

                field.classList.add('field-valid');
                return true;
            }

            hideFieldError(field) {
                field.classList.remove('field-error', 'field-valid');
            }

            updateFieldHighlight(field) {
                this.validateField(field);
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

            validateForm() {
                // Сброс стилей
                document.querySelectorAll('.form-control').forEach(el => {
                    el.classList.remove('field-error', 'field-valid');
                });

                // Базовые обязательные поля для всех объектов
                const requiredFields = [
                    { selector: '[name="guest"]', label: 'Имя гостя' },
                    { selector: '[name="booking_date"]', label: 'Дата бронирования' },
                    { selector: '[name="check_in"]', label: 'Заезд' },
                    { selector: '[name="check_out"]', label: 'Выезд' },
                    { selector: '[name="total_sum"]', label: 'Сумма (баты)' }
                ];

                // Для booking_other телефон не обязателен, а поля хозяина обязательны
                if (!this.isBookingOther) {
                    requiredFields.push({ selector: '[name="phone"]', label: 'Телефон' });
                } else {
                    requiredFields.push(
                        { selector: '#condo_name', label: 'Название кондо' },
                        { selector: '#apartment_number', label: 'Номер апарта' },
                        { selector: '#owner_name', label: 'Хозяин' }
                    );
                }

                let isValid = true;
                for (const field of requiredFields) {
                    const el = document.querySelector(field.selector);
                    if (!el || el.value.trim() === '') {
                        if (el) el.classList.add('field-error');
                        isValid = false;
                    } else {
                        if (el) el.classList.add('field-valid');
                    }
                }

                // Проверка на цифры для дополнительных полей (не обязательных)
                const advanceBath = document.getElementById('advance_bath');
                const advanceRub = document.getElementById('advance_rub');
                const additionalBath = document.getElementById('additional_bath');
                const additionalRub = document.getElementById('additional_rub');
                const commission = document.getElementById('commission');

                if (advanceBath && !/^\d*$/.test(advanceBath.value)) {
                    advanceBath.classList.add('field-error');
                    isValid = false;
                } else if (advanceBath && advanceBath.value !== '') {
                    advanceBath.classList.add('field-valid');
                }

                if (advanceRub && !/^\d*$/.test(advanceRub.value)) {
                    advanceRub.classList.add('field-error');
                    isValid = false;
                } else if (advanceRub && advanceRub.value !== '') {
                    advanceRub.classList.add('field-valid');
                }

                if (additionalBath && !/^\d*$/.test(additionalBath.value)) {
                    additionalBath.classList.add('field-error');
                    isValid = false;
                } else if (additionalBath && additionalBath.value !== '') {
                    additionalBath.classList.add('field-valid');
                }

                if (additionalRub && !/^\d*$/.test(additionalRub.value)) {
                    additionalRub.classList.add('field-error');
                    isValid = false;
                } else if (additionalRub && additionalRub.value !== '') {
                    additionalRub.classList.add('field-valid');
                }

                if (commission && !/^\d*$/.test(commission.value)) {
                    commission.classList.add('field-error');
                    isValid = false;
                } else if (commission && commission.value !== '') {
                    commission.classList.add('field-valid');
                }

                const checkIn = this.fpCheckIn.selectedDates[0];
                const checkOut = this.fpCheckOut.selectedDates[0];
                if (checkIn && checkOut && checkOut <= checkIn) {
                    document.querySelector('[name="check_in"]')?.classList.add('field-error');
                    document.querySelector('[name="check_out"]')?.classList.add('field-error');
                    this.tg.showPopup({ title: 'Ошибка', message: 'Дата выезда должна быть позже даты заезда', buttons: [{type:'ok'}] });
                    return false;
                }

                if (!isValid) {
                    this.tg.showPopup({ title: 'Ошибка', message: 'Проверьте правильность заполнения полей', buttons: [{type:'ok'}] });
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
                    const object = document.getElementById('objectSelect').value;

                    // Получаем значения с обработкой пустых
                    const advanceBath = document.getElementById('advance_bath').value || '0';
                    const advanceRub = document.getElementById('advance_rub').value || '0';
                    const additionalBath = document.getElementById('additional_bath').value || '0';
                    const additionalRub = document.getElementById('additional_rub').value || '0';

                    const formatDateShort = (d) => {
                        const [dd, mm, yyyy] = d.split('.');
                        return `${yyyy.slice(-2)}${mm}${dd}`;
                    };

                    const filename = `Изменение_Бронь_${object}_${shortName}_${formatDateShort(checkIn)}_${formatDateShort(checkOut)}.json`;

                    const payload = {
                        form_type: 'edit_booking',
                        init_chat_id: <?= $INIT_CHAT_ID_JS ?>,
                        _sync_id: document.getElementById('currentSyncId').value,
                        object: object,
                        guest: formData.get('guest'),
                        booking_date: formData.get('booking_date'),
                        check_in: formData.get('check_in'),
                        check_out: formData.get('check_out'),
                        nights: document.getElementById('nights').value,
                        total_sum: formData.get('total_sum'),
                        advance: advanceBath + '/' + advanceRub,
                        additional_payment: additionalBath + '/' + additionalRub,
                        extra_charges: formData.get('extra_charges') || '',
                        expenses: formData.get('expenses') || '',
                        payment_method: formData.get('payment_method') || '',
                        phone: formData.get('phone') || '',
                        extra_phone: formData.get('extra_phone') || '',
                        source: formData.get('source') || '',
                        comment: formData.get('comment') || '',
                        flights: formData.get('flights') || '',
                        timestamp: new Date().toLocaleString('ru-RU'),
                        filename: filename
                    };

                    // Добавляем дополнительные поля для booking_other
                    if (this.isBookingOther) {
                        payload.condo_name = document.getElementById('condo_name').value;
                        payload.apartment_number = document.getElementById('apartment_number').value;
                        payload.owner_name = document.getElementById('owner_name').value;
                        payload.commission = document.getElementById('commission').value || '0';
                    }

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
                    const object = document.getElementById('objectSelect').value;

                    const formatDateShort = (d) => {
                        const [dd, mm, yyyy] = d.split('.');
                        return `${yyyy.slice(-2)}${mm}${dd}`;
                    };

                    const filename = `Удаление_Бронь_${object}_${shortName}_${formatDateShort(checkIn)}_${formatDateShort(checkOut)}.json`;

                    const payload = {
                        form_type: 'delete_booking',
                        _sync_id: this.currentBooking.sync_id,
                        guest: this.currentBooking.guest,
                        object: object,
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