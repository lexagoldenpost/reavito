<?php
/**
 * Plugin Name: Telegram Booking Form
 * Description: Форма бронирования для Telegram бота
 * Version: 1.0
 * Author: Your Name
 */

// Защита от прямого доступа
if (!defined('ABSPATH')) {
    exit;
}

class TelegramBookingForm {

    public function __construct() {
        add_shortcode('telegram_booking', array($this, 'booking_form_shortcode'));
        add_action('wp_enqueue_scripts', array($this, 'enqueue_scripts'));
    }

    public function enqueue_scripts() {
        if (is_singular()) {
            global $post;
            if (has_shortcode($post->post_content, 'telegram_booking')) {
                $this->enqueue_form_assets();
            }
        }
    }

    private function enqueue_form_assets() {
        // Подключаем jQuery
        wp_enqueue_script('jquery');

        // Inline styles
        wp_add_inline_style('wp-block-library', $this->get_form_styles());

        // Inline scripts
        wp_add_inline_script('jquery', $this->get_form_scripts());
    }

    public function booking_form_shortcode($atts) {
        $atts = shortcode_atts(array(
            'object' => 'citygate_p311',
            'user_id' => '0',
            'title' => 'Форма бронирования'
        ), $atts);

        return $this->get_form_html($atts);
    }

    private function get_form_styles() {
        return '
        .telegram-booking-container {
            max-width: 500px;
            margin: 20px auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            overflow: hidden;
            font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
        }

        .telegram-booking-header {
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            color: white;
            padding: 30px 20px;
            text-align: center;
        }

        .telegram-booking-header h1 {
            font-size: 24px;
            margin-bottom: 8px;
            font-weight: 600;
        }

        .telegram-booking-header p {
            opacity: 0.9;
            font-size: 14px;
        }

        .telegram-form-container {
            padding: 30px;
        }

        .telegram-form-group {
            margin-bottom: 20px;
        }

        .telegram-form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            color: #374151;
            font-size: 14px;
        }

        .telegram-form-control {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e5e7eb;
            border-radius: 12px;
            font-size: 16px;
            transition: all 0.3s ease;
            background: #f9fafb;
        }

        .telegram-form-control:focus {
            outline: none;
            border-color: #4f46e5;
            background: white;
            box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
        }

        .telegram-form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }

        .telegram-btn {
            width: 100%;
            padding: 16px;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .telegram-btn-primary {
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            color: white;
        }

        .telegram-btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(79, 70, 229, 0.3);
        }

        .telegram-loading {
            display: none;
            text-align: center;
            padding: 40px 20px;
        }

        .telegram-spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #4f46e5;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: telegram-spin 1s linear infinite;
            margin: 0 auto 15px;
        }

        @keyframes telegram-spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .telegram-success-message {
            display: none;
            text-align: center;
            padding: 40px 20px;
            color: #059669;
        }

        .telegram-success-icon {
            font-size: 48px;
            margin-bottom: 20px;
        }

        .telegram-error-message {
            color: #dc2626;
            font-size: 14px;
            margin-top: 5px;
            display: none;
        }

        .telegram-section-title {
            font-size: 18px;
            font-weight: 600;
            color: #374151;
            margin: 25px 0 15px 0;
            padding-bottom: 10px;
            border-bottom: 2px solid #f3f4f6;
        }

        .telegram-phone-input {
            display: flex;
            align-items: center;
        }

        .telegram-phone-prefix {
            background: #e5e7eb;
            padding: 12px 15px;
            border: 2px solid #e5e7eb;
            border-right: none;
            border-radius: 12px 0 0 12px;
            font-weight: 500;
        }

        .telegram-phone-input input {
            border-radius: 0 12px 12px 0;
            flex: 1;
        }

        .telegram-form-message {
            margin-top: 15px;
            padding: 10px;
            border-radius: 8px;
            text-align: center;
            display: none;
        }

        .telegram-form-message.success {
            background: #d1fae5;
            color: #065f46;
            border: 1px solid #a7f3d0;
        }

        .telegram-form-message.error {
            background: #fee2e2;
            color: #991b1b;
            border: 1px solid #fecaca;
        }

        .telegram-currency-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }

        .telegram-currency-group {
            display: flex;
            flex-direction: column;
        }

        .telegram-currency-label {
            font-size: 12px;
            color: #6b7280;
            margin-bottom: 4px;
        }

        .telegram-error-container {
            display: none;
            text-align: center;
            padding: 40px 20px;
            color: #dc2626;
        }

        @media (max-width: 480px) {
            .telegram-form-row {
                grid-template-columns: 1fr;
            }

            .telegram-booking-container {
                margin: 10px;
            }

            .telegram-form-container {
                padding: 20px;
            }

            .telegram-currency-row {
                grid-template-columns: 1fr;
            }
        }
        ';
    }

    private function get_form_scripts() {
        return '
        jQuery(document).ready(function($) {
            console.log("Telegram booking form initialized");

            // Инициализируем WebApp
            console.log("Initializing Telegram WebApp...");
            Telegram.WebApp.ready();
            Telegram.WebApp.expand();
            Telegram.WebApp.setHeaderColor("#4f46e5");
            Telegram.WebApp.setBackgroundColor("#f8fafc");

            console.log("WebApp initialized successfully");

            // Устанавливаем минимальную дату (сегодня)
            const today = new Date().toISOString().split("T")[0];
            $("#telegram_check_in").attr("min", today);
            $("#telegram_check_out").attr("min", today);

            // Автоматический расчет количества ночей
            $("#telegram_check_in, #telegram_check_out").on("change", function() {
                calculateNights();
            });

            // Маски для числовых полей
            $("#telegram_total_baht, #telegram_advance_baht, #telegram_advance_rub, #telegram_additional_baht, #telegram_additional_rub").on("input", function() {
                this.value = this.value.replace(/[^0-9]/g, "");
            });

            function calculateNights() {
                const checkIn = $("#telegram_check_in").val();
                const checkOut = $("#telegram_check_out").val();

                if (checkIn && checkOut) {
                    const start = new Date(checkIn);
                    const end = new Date(checkOut);
                    const timeDiff = end.getTime() - start.getTime();
                    const nights = Math.ceil(timeDiff / (1000 * 3600 * 24));

                    if (nights > 0) {
                        $("#telegram_nights_count").val(nights);
                        hideError("telegram_checkOutError");
                    } else {
                        $("#telegram_nights_count").val("");
                        showError("telegram_checkOutError", "Дата выезда должна быть позже даты заезда");
                    }
                }
            }

            function validateForm() {
                let isValid = true;
                const name = $("#telegram_guest_name").val().trim();
                const checkIn = $("#telegram_check_in").val();
                const checkOut = $("#telegram_check_out").val();

                // Сброс ошибок
                hideAllErrors();

                if (!name) {
                    showError("telegram_nameError", "Пожалуйста, введите ФИО гостя");
                    isValid = false;
                }

                if (!checkIn) {
                    showError("telegram_checkInError", "Выберите дату заезда");
                    isValid = false;
                }

                if (!checkOut) {
                    showError("telegram_checkOutError", "Выберите дату выезда");
                    isValid = false;
                }

                // Проверка что дата выезда позже даты заезда
                if (checkIn && checkOut) {
                    const start = new Date(checkIn);
                    const end = new Date(checkOut);
                    if (end <= start) {
                        showError("telegram_checkOutError", "Дата выезда должна быть позже даты заезда");
                        isValid = false;
                    }
                }

                return isValid;
            }

            function showError(elementId, message) {
                $("#" + elementId).text(message).show();
            }

            function hideError(elementId) {
                $("#" + elementId).hide();
            }

            function hideAllErrors() {
                $(".telegram-error-message").hide();
            }

            function formatPaymentValue(bahtValue, rubValue) {
                bahtValue = bahtValue || "0";
                rubValue = rubValue || "0";
                return bahtValue + "/" + rubValue;
            }

            // Главная функция отправки данных
            window.submitTelegramBooking = function() {
                console.log("=== ОТПРАВКА ДАННЫХ В TELEGRAM БОТА ===");

                if (!validateForm()) {
                    return false;
                }

                // Показываем загрузку
                $("#telegram_formSection").hide();
                $("#telegram_loadingSection").show();

                // Форматируем данные платежей
                const advancePayment = formatPaymentValue(
                    $("#telegram_advance_baht").val(),
                    $("#telegram_advance_rub").val()
                );

                const additionalPayment = formatPaymentValue(
                    $("#telegram_additional_baht").val(),
                    $("#telegram_additional_rub").val()
                );

                // Собираем данные формы
                const formData = {
                    guest_name: $("#telegram_guest_name").val().trim(),
                    phone: $("#telegram_phone").val().trim() ? "+66" + $("#telegram_phone").val().trim() : "",
                    additional_phone: $("#telegram_additional_phone").val().trim(),
                    check_in: $("#telegram_check_in").val(),
                    check_out: $("#telegram_check_out").val(),
                    nights_count: $("#telegram_nights_count").val(),
                    total_baht: $("#telegram_total_baht").val(),
                    advance_payment: advancePayment,
                    additional_payment: additionalPayment,
                    source: $("#telegram_source").val(),
                    flights: $("#telegram_flights").val(),
                    payment_method: $("#telegram_payment_method").val(),
                    comment: $("#telegram_comment").val().trim(),
                    booking_date: new Date().toISOString().split("T")[0],
                    object_id: window.bookingParams.object,
                    user_id: window.bookingParams.user_id
                };

                console.log("Данные для отправки:", formData);

                // ОТПРАВКА ДАННЫХ В TELEGRAM BOT
                try {
                    console.log("Отправка данных через Telegram.WebApp.sendData()...");

                    // Отправляем данные в бота
                    Telegram.WebApp.sendData(JSON.stringify(formData));

                    console.log("✅ Данные успешно отправлены");

                    // Показываем успешное сообщение
                    $("#telegram_loadingSection").hide();
                    $("#telegram_successSection").show();

                    // Закрываем WebApp через 1.5 секунды
                    setTimeout(() => {
                        Telegram.WebApp.close();
                    }, 1500);

                } catch (error) {
                    console.error("❌ Ошибка отправки данных:", error);

                    // Показываем ошибку
                    $("#telegram_loadingSection").hide();
                    $("#telegram_formSection").show();

                    // Показываем сообщение об ошибке
                    const errorMessage = `
                        <div style="text-align: center; padding: 20px; color: #dc2626;">
                            <div style="font-size: 36px; margin-bottom: 10px;">❌</div>
                            <h3>Ошибка отправки</h3>
                            <p>Не удалось отправить данные в бота</p>
                            <button onclick="window.submitTelegramBooking()" style="margin-top: 15px; padding: 10px 20px; background: #dc2626; color: white; border: none; border-radius: 8px; cursor: pointer;">
                                Попробовать снова
                            </button>
                        </div>
                    `;
                    $("#telegram_formMessage").html(errorMessage).show();
                }

                return false;
            };

            // Обработчик для кнопки
            $("#telegram_submit_btn").on("click", function(e) {
                e.preventDefault();
                window.submitTelegramBooking();
            });

            // Обработчик для формы
            $("#telegram_booking_form").on("submit", function(e) {
                e.preventDefault();
                window.submitTelegramBooking();
            });
        });
        ';
    }

    private function get_form_html($atts) {
        ob_start();
        ?>
        <div id="telegram-booking-form">
            <script>
                window.bookingParams = {
                    object: '<?php echo esc_js($atts['object']); ?>',
                    user_id: '<?php echo esc_js($atts['user_id']); ?>'
                };
            </script>

            <div class="telegram-booking-container">
                <div class="telegram-booking-header">
                    <h1>🏢 <?php echo esc_html($atts['title']); ?></h1>
                    <p>Заполните форму для создания брони</p>
                </div>

                <form id="telegram_booking_form">
                    <div id="telegram_formSection">
                        <div class="telegram-form-container">
                            <div class="telegram-section-title">👤 Информация о госте</div>

                            <div class="telegram-form-group">
                                <label for="telegram_guest_name">ФИО гостя *</label>
                                <input type="text" id="telegram_guest_name" class="telegram-form-control" placeholder="Введите полное имя" required>
                                <div class="telegram-error-message" id="telegram_nameError">Пожалуйста, введите ФИО гостя</div>
                            </div>

                            <div class="telegram-form-row">
                                <div class="telegram-form-group">
                                    <label for="telegram_phone">Телефон</label>
                                    <div class="telegram-phone-input">
                                        <div class="telegram-phone-prefix">+66</div>
                                        <input type="tel" id="telegram_phone" class="telegram-form-control" placeholder="812345678">
                                    </div>
                                    <div class="telegram-error-message" id="telegram_phoneError">Введите корректный номер телефона</div>
                                </div>

                                <div class="telegram-form-group">
                                    <label for="telegram_additional_phone">Доп. телефон</label>
                                    <input type="tel" id="telegram_additional_phone" class="telegram-form-control" placeholder="Дополнительный номер">
                                </div>
                            </div>

                            <div class="telegram-section-title">📅 Даты проживания *</div>

                            <div class="telegram-form-row">
                                <div class="telegram-form-group">
                                    <label for="telegram_check_in">Заезд *</label>
                                    <input type="date" id="telegram_check_in" class="telegram-form-control" required>
                                    <div class="telegram-error-message" id="telegram_checkInError">Выберите дату заезда</div>
                                </div>

                                <div class="telegram-form-group">
                                    <label for="telegram_check_out">Выезд *</label>
                                    <input type="date" id="telegram_check_out" class="telegram-form-control" required>
                                    <div class="telegram-error-message" id="telegram_checkOutError">Выберите дату выезда</div>
                                </div>
                            </div>

                            <div class="telegram-form-group">
                                <label for="telegram_nights_count">Количество ночей</label>
                                <input type="number" id="telegram_nights_count" class="telegram-form-control" placeholder="Автоматический расчет" readonly>
                            </div>

                            <div class="telegram-section-title">💰 Финансовая информация</div>

                            <div class="telegram-form-group">
                                <label for="telegram_total_baht">Сумма (батты)</label>
                                <input type="text" id="telegram_total_baht" class="telegram-form-control" placeholder="Введите сумму в баттах">
                                <div class="telegram-error-message" id="telegram_amountError">Введите корректную сумму</div>
                            </div>

                            <div class="telegram-form-group">
                                <label>Аванс</label>
                                <div class="telegram-currency-row">
                                    <div class="telegram-currency-group">
                                        <div class="telegram-currency-label">Батты</div>
                                        <input type="text" id="telegram_advance_baht" class="telegram-form-control" placeholder="0">
                                    </div>
                                    <div class="telegram-currency-group">
                                        <div class="telegram-currency-label">Рубли</div>
                                        <input type="text" id="telegram_advance_rub" class="telegram-form-control" placeholder="0">
                                    </div>
                                </div>
                            </div>

                            <div class="telegram-form-group">
                                <label>Доплата</label>
                                <div class="telegram-currency-row">
                                    <div class="telegram-currency-group">
                                        <div class="telegram-currency-label">Батты</div>
                                        <input type="text" id="telegram_additional_baht" class="telegram-form-control" placeholder="0">
                                    </div>
                                    <div class="telegram-currency-group">
                                        <div class="telegram-currency-label">Рубли</div>
                                        <input type="text" id="telegram_additional_rub" class="telegram-form-control" placeholder="0">
                                    </div>
                                </div>
                            </div>

                            <div class="telegram-section-title">📋 Дополнительная информация</div>

                            <div class="telegram-form-group">
                                <label for="telegram_source">Источник бронирования</label>
                                <select id="telegram_source" class="telegram-form-control">
                                    <option value="">Выберите источник</option>
                                    <option value="Airbnb">Airbnb</option>
                                    <option value="Booking.com">Booking.com</option>
                                    <option value="Telegram">Telegram</option>
                                    <option value="Авито">Авито</option>
                                    <option value="Авито Вотс ап">Авито Вотс ап</option>
                                    <option value="телеграмм">телеграмм</option>
                                    <option value="Сайт">Сайт</option>
                                    <option value="Рекомендация">Рекомендация</option>
                                    <option value="Другое">Другое</option>
                                </select>
                            </div>

                            <div class="telegram-form-group">
                                <label for="telegram_flights">Рейсы</label>
                                <input type="text" id="telegram_flights" class="telegram-form-control" placeholder="Номера рейсов">
                            </div>

                            <div class="telegram-form-group">
                                <label for="telegram_payment_method">Способ оплаты</label>
                                <select id="telegram_payment_method" class="telegram-form-control">
                                    <option value="">Выберите способ оплаты</option>
                                    <option value="Карта">Карта</option>
                                    <option value="Наличные">Наличные</option>
                                    <option value="Перевод">Перевод</option>
                                    <option value="Т-Банк">Т-Банк</option>
                                    <option value="ГПБ">ГПБ</option>
                                    <option value="Райф">Райф</option>
                                    <option value="Cryptocurrency">Криптовалюта</option>
                                </select>
                            </div>

                            <div class="telegram-form-group">
                                <label for="telegram_comment">Комментарий</label>
                                <textarea id="telegram_comment" class="telegram-form-control" rows="3" placeholder="Дополнительная информация..."></textarea>
                            </div>

                            <button type="button" id="telegram_submit_btn" class="telegram-btn telegram-btn-primary">
                                ✅ Сохранить бронирование
                            </button>

                            <div class="telegram-form-message" id="telegram_formMessage"></div>
                        </div>
                    </div>
                </form>

                <div class="telegram-loading" id="telegram_loadingSection">
                    <div class="telegram-spinner"></div>
                    <p>Отправляем данные в Telegram бота...</p>
                </div>

                <div class="telegram-success-message" id="telegram_successSection">
                    <div class="telegram-success-icon">✅</div>
                    <h3>Бронирование успешно отправлено!</h3>
                    <p>Форма закроется автоматически...</p>
                </div>
            </div>
        </div>
        <?php
        return ob_get_clean();
    }
}

new TelegramBookingForm();
?>