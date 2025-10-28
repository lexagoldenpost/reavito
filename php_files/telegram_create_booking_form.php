<?php
/**
 * Plugin Name: Telegram Booking Form
 * Description: Форма бронирования для Telegram Mini App
 * Version: 1.7
 * Author: Your Name
 */

// Защита от прямого доступа
if (!defined('ABSPATH')) {
    exit;
}

class TelegramBookingForm {

    private $booking_dir;

    public function __construct() {
        // Определяем папку для хранения JSON файлов
        $this->booking_dir = WP_CONTENT_DIR . '/uploads/booking_data/';

        // Создаем папку если не существует
        if (!file_exists($this->booking_dir)) {
            wp_mkdir_p($this->booking_dir);
        }

        add_shortcode('telegram_booking', array($this, 'booking_form_shortcode'));
        add_action('wp_enqueue_scripts', array($this, 'enqueue_scripts'));
        add_action('wp_ajax_save_booking_to_json', array($this, 'save_booking_to_json'));
        add_action('wp_ajax_nopriv_save_booking_to_json', array($this, 'save_booking_to_json'));

        // Добавляем обработчик для Telegram Mini App
        add_action('init', array($this, 'check_telegram_init_data'));
    }

    public function check_telegram_init_data() {
        // Проверяем, открыто ли в Telegram Mini App
        if (isset($_GET['tgWebAppData'])) {
            // Можно добавить проверку подписи Telegram
            $this->is_telegram_mini_app = true;
        }
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

        // Подключаем Telegram Web App SDK
        wp_enqueue_script('telegram-web-app', 'https://telegram.org/js/telegram-web-app.js', array(), null, true);

        wp_add_inline_style('wp-block-library', $this->get_form_styles());
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
            max-width: 100%;
            margin: 0;
            background: white;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            min-height: 100vh;
        }
        .telegram-booking-header {
            background: var(--tg-theme-bg-color, #4f46e5);
            color: var(--tg-theme-text-color, white);
            padding: 20px 16px;
            text-align: center;
        }
        .telegram-booking-header h1 {
            margin: 0 0 8px 0;
            font-size: 20px;
            font-weight: 600;
        }
        .telegram-booking-header p {
            margin: 0;
            opacity: 0.9;
            font-size: 14px;
        }
        .telegram-form-container {
            padding: 20px 16px;
        }
        .telegram-form-group {
            margin-bottom: 16px;
        }
        .telegram-form-group label {
            display: block;
            margin-bottom: 6px;
            font-weight: 500;
            color: var(--tg-theme-text-color, #374151);
            font-size: 14px;
        }
        .telegram-form-control {
            width: 100%;
            padding: 12px 14px;
            border: 1px solid var(--tg-theme-hint-color, #e5e7eb);
            border-radius: 8px;
            font-size: 16px;
            background: var(--tg-theme-bg-color, white);
            color: var(--tg-theme-text-color, #374151);
            box-sizing: border-box;
        }
        .telegram-form-control:focus {
            outline: none;
            border-color: var(--tg-theme-button-color, #4f46e5);
        }
        .telegram-form-row {
            display: flex;
            gap: 12px;
        }
        .telegram-form-row .telegram-form-group {
            flex: 1;
        }
        .telegram-submit-btn {
            width: 100%;
            padding: 16px;
            background: var(--tg-theme-button-color, #4f46e5);
            color: var(--tg-theme-button-text-color, white);
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            margin-top: 8px;
        }
        .telegram-submit-btn:active {
            opacity: 0.8;
        }
        .telegram-error-message {
            color: #dc2626;
            font-size: 12px;
            margin-top: 4px;
            display: none;
        }
        .telegram-loading {
            text-align: center;
            padding: 40px 20px;
            display: none;
        }
        .telegram-spinner {
            border: 3px solid #f3f4f6;
            border-top: 3px solid var(--tg-theme-button-color, #4f46e5);
            border-radius: 50%;
            width: 32px;
            height: 32px;
            animation: spin 1s linear infinite;
            margin: 0 auto 16px;
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
            font-size: 40px;
            margin-bottom: 16px;
        }
        ';
    }

    private function get_form_scripts() {
        return '
        jQuery(document).ready(function($) {
            console.log("Telegram Mini App form initialized");

            // Инициализируем Telegram Mini App
            let tg = null;
            let isTelegram = false;

            if (typeof window.Telegram !== "undefined" && window.Telegram.WebApp) {
                tg = window.Telegram.WebApp;
                tg.ready();
                tg.expand();
                isTelegram = true;
                console.log("Telegram Mini App initialized successfully");

                // Устанавливаем тему Telegram
                applyTelegramTheme();

            } else {
                console.warn("Telegram Mini App not available - running in browser mode");
            }

            function applyTelegramTheme() {
                // Применяем CSS переменные Telegram
                document.documentElement.style.setProperty("--tg-theme-bg-color", tg.themeParams.bg_color || "#ffffff");
                document.documentElement.style.setProperty("--tg-theme-text-color", tg.themeParams.text_color || "#000000");
                document.documentElement.style.setProperty("--tg-theme-hint-color", tg.themeParams.hint_color || "#999999");
                document.documentElement.style.setProperty("--tg-theme-button-color", tg.themeParams.button_color || "#4f46e5");
                document.documentElement.style.setProperty("--tg-theme-button-text-color", tg.themeParams.button_text_color || "#ffffff");
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

            // Функция для сохранения в JSON
            function saveToJsonFile(formData) {
                return new Promise((resolve, reject) => {
                    $.ajax({
                        url: "' . admin_url('admin-ajax.php') . '",
                        type: "POST",
                        data: {
                            action: "save_booking_to_json",
                            booking_data: formData,
                            nonce: "' . wp_create_nonce('save_booking_nonce') . '"
                        },
                        success: function(response) {
                            if (response.success) {
                                resolve(response.data);
                            } else {
                                reject(response.data);
                            }
                        },
                        error: function(xhr, status, error) {
                            reject(error);
                        }
                    });
                });
            }

            // Главная функция отправки данных
            window.submitTelegramBooking = async function() {
                console.log("=== ОТПРАВКА ДАННЫХ В TELEGRAM MINI APP ===");

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
                    user_id: window.bookingParams.user_id,
                    created_at: new Date().toISOString()
                };

                console.log("Данные для отправки:", formData);

                try {
                    // Сохраняем в JSON файл
                    const saveResult = await saveToJsonFile(formData);
                    console.log("Данные успешно сохранены в JSON:", saveResult);

                    // В режиме Telegram Mini App отправляем данные обратно в бота
                    if (isTelegram && tg) {
                        console.log("Sending data back to Telegram bot...");

                        // Добавляем флаг успешного сохранения
                        const responseData = {
                            ...formData,
                            json_save_success: true,
                            json_save_message: saveResult.message,
                            json_file_path: saveResult.file_path,
                            booking_id: saveResult.booking_id
                        };

                        // Отправляем данные в бота
                        tg.sendData(JSON.stringify(responseData));

                        // Показываем успешное сообщение на 1.5 секунды
                        $("#telegram_loadingSection").hide();
                        $("#telegram_successSection").show();

                        // Закрываем Mini App через 1.5 секунды
                        setTimeout(() => {
                            tg.close();
                        }, 1500);

                    } else {
                        // Режим браузера - просто показываем успех
                        $("#telegram_loadingSection").hide();
                        $("#telegram_successSection").show();

                        // Через 3 секунды перезагружаем форму
                        setTimeout(() => {
                            $("#telegram_successSection").hide();
                            $("#telegram_formSection").show();
                            $("#telegram_booking_form")[0].reset();
                        }, 3000);
                    }

                } catch (error) {
                    console.error("Ошибка при сохранении в JSON:", error);

                    $("#telegram_loadingSection").hide();
                    $("#telegram_formSection").show();

                    const errorMessage = `
                        <div style="text-align: center; padding: 20px; color: #dc2626;">
                            <div style="font-size: 36px; margin-bottom: 10px;">❌</div>
                            <h3>Ошибка сохранения</h3>
                            <p>${error}</p>
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

            // Обработка кнопки "Назад" в Telegram
            if (isTelegram && tg) {
                tg.BackButton.show();
                tg.BackButton.onClick(function() {
                    tg.close();
                });
            }
        });
        ';
    }

    public function save_booking_to_json() {
        // Проверка nonce
        if (!wp_verify_nonce($_POST['nonce'], 'save_booking_nonce')) {
            wp_send_json_error('Security check failed');
        }

        try {
            $booking_data = $_POST['booking_data'];

            // Получаем имя JSON файла на основе object_id
            $filename = $this->get_json_filename($booking_data['object_id']);
            $filepath = $this->booking_dir . $filename;

            // Читаем существующие данные или создаем новый массив
            $existing_data = [];
            if (file_exists($filepath)) {
                $existing_content = file_get_contents($filepath);
                $existing_data = json_decode($existing_content, true) ?: [];
            }

            // Добавляем новое бронирование
            $booking_id = uniqid();
            $booking_data['id'] = $booking_id;
            $booking_data['sync_id'] = $this->generate_uuid();
            $existing_data[] = $booking_data;

            // Сохраняем обратно в файл
            $json_content = json_encode($existing_data, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);

            if (file_put_contents($filepath, $json_content) === false) {
                throw new Exception('Failed to write JSON file');
            }

            wp_send_json_success(array(
                'message' => 'Data successfully saved to JSON file',
                'file_path' => $filepath,
                'filename' => $filename,
                'booking_id' => $booking_id,
                'object_id' => $booking_data['object_id']
            ));

        } catch (Exception $e) {
            wp_send_json_error('Error saving to JSON: ' . $e->getMessage());
        }
    }

    private function get_json_filename($object_id) {
        // Преобразуем object_id в имя файла
        $filename = str_replace('_', '-', $object_id) . '.json';
        return sanitize_file_name($filename);
    }

    private function generate_uuid() {
        return sprintf('%04x%04x-%04x-%04x-%04x-%04x%04x%04x',
            mt_rand(0, 0xffff), mt_rand(0, 0xffff),
            mt_rand(0, 0xffff),
            mt_rand(0, 0x0fff) | 0x4000,
            mt_rand(0, 0x3fff) | 0x8000,
            mt_rand(0, 0xffff), mt_rand(0, 0xffff), mt_rand(0, 0xffff)
        );
    }

    private function get_form_html($atts) {
        ob_start();
        ?>
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title><?php echo esc_html($atts['title']); ?></title>
            <style>
                :root {
                    --tg-theme-bg-color: #ffffff;
                    --tg-theme-text-color: #000000;
                    --tg-theme-hint-color: #999999;
                    --tg-theme-button-color: #4f46e5;
                    --tg-theme-button-text-color: #ffffff;
                }

                body {
                    margin: 0;
                    padding: 0;
                    background: var(--tg-theme-bg-color);
                    color: var(--tg-theme-text-color);
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                }
            </style>
        </head>
        <body>
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
                                <!-- Форма остается такой же -->
                                <div class="telegram-form-group">
                                    <label for="telegram_guest_name">👤 ФИО гостя *</label>
                                    <input type="text" id="telegram_guest_name" class="telegram-form-control" placeholder="Введите полное имя гостя" required>
                                    <div id="telegram_nameError" class="telegram-error-message"></div>
                                </div>

                                <div class="telegram-form-group">
                                    <label for="telegram_phone">📞 Телефон (Таиланд)</label>
                                    <div style="display: flex; align-items: center;">
                                        <span style="padding: 0 12px; background: #f3f4f6; border: 1px solid #e5e7eb; border-right: none; border-radius: 8px 0 0 8px; height: 44px; display: flex; align-items: center; color: #6b7280; font-size: 14px;">+66</span>
                                        <input type="tel" id="telegram_phone" class="telegram-form-control" style="border-radius: 0 8px 8px 0; border-left: none; margin-left: 0;" placeholder="Введите номер телефона">
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

                                <!-- Остальные поля формы остаются без изменений -->
                                <!-- ... -->

                                <button type="submit" id="telegram_submit_btn" class="telegram-submit-btn">
                                    💾 Сохранить бронирование
                                </button>
                            </div>
                        </div>
                    </form>

                    <div class="telegram-loading" id="telegram_loadingSection">
                        <div class="telegram-spinner"></div>
                        <p>Сохраняем данные...</p>
                    </div>

                    <div class="telegram-success-message" id="telegram_successSection">
                        <div class="telegram-success-icon">✅</div>
                        <h3>Бронирование успешно сохранено!</h3>
                        <p>Приложение закроется автоматически...</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        <?php
        return ob_get_clean();
    }
}

new TelegramBookingForm();