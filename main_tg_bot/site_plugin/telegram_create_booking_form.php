<?php
/**
 * Plugin Name: Telegram Booking Form
 * Description: Форма бронирования для Telegram бота
 * Version: 1.3
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
        // Убираем AJAX обработку, так как данные будут отправляться через Telegram WebApp
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
        wp_enqueue_script('jquery');
        wp_add_inline_style('wp-block-library', $this->get_form_styles());
        wp_add_inline_script('jquery', $this->get_form_scripts());
    }

    public function booking_form_shortcode($atts) {
        $atts = shortcode_atts(array(
            'object' => 'citygate_p311',
            'user_id' => '0',
            'title' => 'Форма бронирования',
            'bot_token' => '',
            'chat_id' => ''
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
            background: linear-gradient(135deg, #4f46e5, #7c3aed);
            color: white;
            padding: 30px 20px;
            text-align: center;
        }
        .telegram-booking-header h1 {
            margin: 0 0 10px 0;
            font-size: 24px;
            font-weight: 600;
        }
        .telegram-booking-header p {
            margin: 0;
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
            border-radius: 10px;
            font-size: 16px;
            transition: all 0.3s;
            box-sizing: border-box;
        }
        .telegram-form-control:focus {
            outline: none;
            border-color: #4f46e5;
            box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
        }
        .telegram-form-row {
            display: flex;
            gap: 15px;
        }
        .telegram-form-row .telegram-form-group {
            flex: 1;
        }
        .telegram-submit-btn {
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, #4f46e5, #7c3aed);
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            margin-top: 10px;
        }
        .telegram-submit-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(79, 70, 229, 0.3);
        }
        .telegram-submit-btn:active {
            transform: translateY(0);
        }
        .telegram-error-message {
            color: #dc2626;
            font-size: 12px;
            margin-top: 5px;
            display: none;
        }
        .telegram-loading {
            text-align: center;
            padding: 40px 20px;
            display: none;
        }
        .telegram-spinner {
            border: 4px solid #f3f4f6;
            border-top: 4px solid #4f46e5;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .telegram-success-message {
            text-align: center;
            padding: 40px 20px;
            display: none;
            color: #059669;
        }
        .telegram-success-icon {
            font-size: 48px;
            margin-bottom: 20px;
        }
        ';
    }

    private function get_form_scripts() {
        return '
        jQuery(document).ready(function($) {
            console.log("Telegram booking form initialized");

            // Инициализируем WebApp
            let telegramWebApp = null;
            if (typeof Telegram !== "undefined" && Telegram.WebApp) {
                telegramWebApp = Telegram.WebApp;
                telegramWebApp.ready();
                telegramWebApp.expand();
                telegramWebApp.setHeaderColor("#4f46e5");
                telegramWebApp.setBackgroundColor("#f8fafc");
                console.log("WebApp initialized successfully");
            } else {
                console.warn("Telegram WebApp not available - running in browser mode");
            }

            // Устанавливаем минимальную дату (сегодня)
            const today = new Date().toISOString().split("T")[0];
            $("#telegram_check_in").attr("min", today);
            $("#telegram_check_out").attr("min", today);

            // Автоматический расчет количества ночей
            $("#telegram_check_in, #telegram_check_out").on("change", calculateNights);

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

            // Главная функция отправки данных через Telegram WebApp
            window.submitTelegramBooking = function() {
                console.log("=== ОТПРАВКА ДАННЫХ ЧЕРЕЗ TELEGRAM WEBAPP ===");

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

                // Отправляем данные через Telegram WebApp
                if (telegramWebApp) {
                    console.log("Sending data via Telegram WebApp...");
                    telegramWebApp.sendData(JSON.stringify(formData));

                    // Показываем успешное сообщение
                    setTimeout(() => {
                        $("#telegram_loadingSection").hide();
                        $("#telegram_successSection").show();

                        // Закрываем WebApp через 2 секунды
                        setTimeout(() => {
                            telegramWebApp.close();
                        }, 2000);
                    }, 1000);

                } else {
                    // Режим браузера - показываем ошибку
                    console.error("Telegram WebApp not available");
                    $("#telegram_loadingSection").hide();
                    $("#telegram_formSection").show();

                    const errorMessage = `
                        <div style="text-align: center; padding: 20px; color: #dc2626;">
                            <div style="font-size: 36px; margin-bottom: 10px;">❌</div>
                            <h3>Ошибка Telegram WebApp</h3>
                            <p>Форма должна быть открыта через Telegram бота</p>
                            <p style="font-size: 12px; margin-top: 10px; opacity: 0.7;">
                                Данные для отправки: ${JSON.stringify(formData)}
                            </p>
                        </div>
                    `;
                    $("#telegram_formMessage").html(errorMessage).show();
                }

                return false;
            };

            // Обработчики событий
            $("#telegram_submit_btn").on("click", function(e) {
                e.preventDefault();
                window.submitTelegramBooking();
            });

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
                            <div class="telegram-form-group">
                                <label for="telegram_guest_name">👤 ФИО гостя *</label>
                                <input type="text" id="telegram_guest_name" class="telegram-form-control" placeholder="Введите полное имя гостя" required>
                                <div id="telegram_nameError" class="telegram-error-message"></div>
                            </div>

                            <div class="telegram-form-group">
                                <label for="telegram_phone">📞 Телефон (Таиланд)</label>
                                <div style="display: flex; align-items: center;">
                                    <span style="padding: 0 12px; background: #f3f4f6; border: 2px solid #e5e7eb; border-right: none; border-radius: 10px 0 0 10px; height: 48px; display: flex; align-items: center; color: #6b7280;">+66</span>
                                    <input type="tel" id="telegram_phone" class="telegram-form-control" style="border-radius: 0 10px 10px 0; border-left: none; margin-left: 0;" placeholder="Введите номер телефона">
                                </div>
                            </div>

                            <div class="telegram-form-group">
                                <label for="telegram_additional_phone">📞 Дополнительный телефон</label>
                                <input type="tel" id="telegram_additional_phone" class="telegram-form-control" placeholder="Дополнительный номер для связи">
                            </div>

                            <div class="telegram-form-row">
                                <div class="telegram-form-group">
                                    <label for="telegram_check_in">📅 Заезд *</label>
                                    <input type="date" id="telegram_check_in" class="telegram-form-control" required>
                                    <div id="telegram_checkInError" class="telegram-error-message"></div>
                                </div>

                                <div class="telegram-form-group">
                                    <label for="telegram_check_out">📅 Выезд *</label>
                                    <input type="date" id="telegram_check_out" class="telegram-form-control" required>
                                    <div id="telegram_checkOutError" class="telegram-error-message"></div>
                                </div>
                            </div>

                            <div class="telegram-form-group">
                                <label for="telegram_nights_count">🌙 Количество ночей</label>
                                <input type="number" id="telegram_nights_count" class="telegram-form-control" readonly>
                            </div>

                            <div class="telegram-form-group">
                                <label for="telegram_total_baht">💰 Сумма (батты)</label>
                                <input type="text" id="telegram_total_baht" class="telegram-form-control" placeholder="Общая сумма бронирования">
                            </div>

                            <div class="telegram-form-row">
                                <div class="telegram-form-group">
                                    <label for="telegram_advance_baht">💳 Аванс (батты)</label>
                                    <input type="text" id="telegram_advance_baht" class="telegram-form-control" placeholder="0">
                                </div>
                                <div class="telegram-form-group">
                                    <label for="telegram_advance_rub">💳 Аванс (рубли)</label>
                                    <input type="text" id="telegram_advance_rub" class="telegram-form-control" placeholder="0">
                                </div>
                            </div>

                            <div class="telegram-form-row">
                                <div class="telegram-form-group">
                                    <label for="telegram_additional_baht">💳 Доплата (батты)</label>
                                    <input type="text" id="telegram_additional_baht" class="telegram-form-control" placeholder="0">
                                </div>
                                <div class="telegram-form-group">
                                    <label for="telegram_additional_rub">💳 Доплата (рубли)</label>
                                    <input type="text" id="telegram_additional_rub" class="telegram-form-control" placeholder="0">
                                </div>
                            </div>

                            <div class="telegram-form-group">
                                <label for="telegram_source">📊 Источник бронирования</label>
                                <select id="telegram_source" class="telegram-form-control">
                                    <option value="">Выберите источник</option>
                                    <option value="Telegram">Telegram</option>
                                    <option value="Instagram">Instagram</option>
                                    <option value="Facebook">Facebook</option>
                                    <option value="Рекомендация">Рекомендация</option>
                                    <option value="Поиск в интернете">Поиск в интернете</option>
                                    <option value="Другое">Другое</option>
                                </select>
                            </div>

                            <div class="telegram-form-group">
                                <label for="telegram_flights">✈️ Рейсы</label>
                                <input type="text" id="telegram_flights" class="telegram-form-control" placeholder="Номера рейсов и время прилета/вылета">
                            </div>

                            <div class="telegram-form-group">
                                <label for="telegram_payment_method">💸 Способ оплаты</label>
                                <select id="telegram_payment_method" class="telegram-form-control">
                                    <option value="">Выберите способ оплаты</option>
                                    <option value="Kasikorn Bank">Kasikorn Bank</option>
                                    <option value="Bangkok Bank">Bangkok Bank</option>
                                    <option value="SCB">SCB</option>
                                    <option value="Тинькофф">Тинькофф</option>
                                    <option value="Сбербанк">Сбербанк</option>
                                    <option value="Альфа-Банк">Альфа-Банк</option>
                                    <option value="Наличные">Наличные</option>
                                    <option value="Другое">Другое</option>
                                </select>
                            </div>

                            <div class="telegram-form-group">
                                <label for="telegram_comment">📝 Комментарий</label>
                                <textarea id="telegram_comment" class="telegram-form-control" rows="3" placeholder="Дополнительная информация, пожелания гостя и т.д."></textarea>
                            </div>

                            <button type="submit" id="telegram_submit_btn" class="telegram-submit-btn">
                                📨 Отправить бронирование
                            </button>
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