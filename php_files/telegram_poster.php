<?php
// telegram_poster.php

$TELEGRAM_BOT_TOKEN = $_GET['token'] ?? '';
$CHAT_ID = $_GET['chat_id'] ?? '';
$INIT_CHAT_ID = $_GET['init_chat_id'] ?? '';

if (empty($TELEGRAM_BOT_TOKEN) || empty($CHAT_ID) || empty($INIT_CHAT_ID)) {
    http_response_code(400);
    die('❌ Отсутствуют параметры в URL.');
}

$INIT_CHAT_ID_JS = json_encode($INIT_CHAT_ID); // для безопасной вставки в JS

function readChannelsData($filePath, $selectedObject) {
    $channels = [];
    if (!file_exists($filePath)) return $channels;

    if (($handle = fopen($filePath, "r")) !== false) {
        $headers = fgetcsv($handle);
        $headerIndexes = [];
        foreach ($headers as $index => $header) {
            $cleanHeader = trim($header);
            $headerIndexes[$cleanHeader] = $index;
        }

        // Нормализуем $selectedObject: заменяем подчеркивания на пробелы для сравнения с CSV
        $normalizedSelectedObject = str_replace('_', ' ', $selectedObject);

        while (($row = fgetcsv($handle, 1000, ",")) !== false) {
            if (count($row) >= 5) {
                // Получаем значения из столбцов
                $chatName = trim($row[$headerIndexes['Наименование чата']] ?? '');
                $daysSinceLastPost = trim($row[$headerIndexes['Количество сообщение после последней публикации']] ?? '');
                $channelName = trim($row[$headerIndexes['Название канала']] ?? '');
                $object = trim($row[$headerIndexes['Объект']] ?? '');
                $lastPostTime = trim($row[$headerIndexes['Время последней отправки']] ?? '');
                $acceptsImages = trim($row[$headerIndexes['Картинки принимает (Да/Нет)']] ?? '');
                $minDays = trim($row[$headerIndexes['Срок в днях меньше которого не отправляем ']] ?? '7'); // Обратите внимание на пробел в конце

                // Определяем ID канала (используем Наименование чата если нет отдельного ID)
                $channelId = $chatName;

                // Проверяем условия:
                // 1. Если столбец 'Объект' пустой -> проверяем условие по дням
                // 2. Если столбец 'Объект' НЕ пустой -> проверяем вхождение $selectedObject (нормализованного) (игнорируя регистр и пробелы) и условие по дням
                $objectMatch = false;
                if (empty($object)) {
                    // Если объект пустой, проверяем только дни
                    $objectMatch = true;
                } else {
                    // Если объект НЕ пустой, проверяем вхождение нормализованного $selectedObject
                    $objectMatch = stripos($object, $normalizedSelectedObject) !== false;
                }

                // Условие по дням: если значение пустое, считаем что оно больше 8
                $daysValue = intval($daysSinceLastPost);
                if ($daysSinceLastPost === '') {
                    $daysCondition = true; // пустое значение = больше 8
                } else {
                    $daysCondition = $daysValue > 8;
                }

                if ($objectMatch && $daysCondition) {
                    $displayName = !empty($channelName) ? $channelName : $chatName;
                    $channels[] = [
                        'display_name' => $displayName,
                        'channel_id' => $channelId,
                        'channel_name' => $channelName,
                        'chat_name' => $chatName,
                        'object' => $object,
                        'days_since_last_post' => $daysSinceLastPost,
                        'last_post_time' => $lastPostTime,
                        'accepts_images' => $acceptsImages,
                        'min_days' => $minDays,
                        'raw_data' => $row
                    ];
                }
            }
        }
        fclose($handle);
    }
    return $channels;
}

// Получаем список объектов из booking_files
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

// Функция для получения свободных дат из CSV файла бронирования
function getFreeDates($object) {
    $filePath = __DIR__ . "/booking_files/{$object}.csv";
    if (!file_exists($filePath)) {
        return ["error" => "Файл бронирования не найден", "has_free_dates" => false];
    }

    $bookedPeriods = [];
    $currentDate = new DateTime();
    $threeMonthsFromNow = (new DateTime())->modify('+3 months');

    // Читаем все бронирования
    if (($handle = fopen($filePath, "r")) !== false) {
        $headers = fgetcsv($handle);
        $checkInIndex = array_search('Заезд', $headers);
        $checkOutIndex = array_search('Выезд', $headers);

        if ($checkInIndex === false || $checkOutIndex === false) {
            fclose($handle);
            return ["error" => "Не найдены столбцы 'Заезд' и 'Выезд'", "has_free_dates" => false];
        }

        while (($row = fgetcsv($handle, 1000, ",")) !== false) {
            $checkIn = trim($row[$checkInIndex] ?? '');
            $checkOut = trim($row[$checkOutIndex] ?? '');

            if ($checkIn && $checkOut) {
                $checkInDate = DateTime::createFromFormat('d.m.Y', $checkIn);
                $checkOutDate = DateTime::createFromFormat('d.m.Y', $checkOut);

                if ($checkInDate && $checkOutDate && $checkOutDate > $checkInDate) {
                    // Добавляем период бронирования
                    $bookedPeriods[] = [
                        'start' => clone $checkInDate,
                        'end' => clone $checkOutDate
                    ];
                }
            }
        }
        fclose($handle);
    }

    // Сортируем бронирования по дате заезда
    usort($bookedPeriods, function($a, $b) {
        return $a['start'] <=> $b['start'];
    });

    // Находим свободные периоды
    $freePeriods = [];
    $current = clone $currentDate;

    foreach ($bookedPeriods as $booking) {
        if ($booking['start'] > $current) {
            // Найден свободный период между current и началом бронирования
            $freeEnd = min($booking['start'], $threeMonthsFromNow);
            if ($current < $freeEnd) {
                $freePeriods[] = [
                    'start' => clone $current,
                    'end' => $freeEnd
                ];
            }
        }

        // Перемещаем current после окончания текущего бронирования
        if ($booking['end'] > $current) {
            $current = clone $booking['end'];
        }

        if ($current >= $threeMonthsFromNow) {
            break;
        }
    }

    // Добавляем оставшийся период до 3 месяцев, если есть
    if ($current < $threeMonthsFromNow) {
        $freePeriods[] = [
            'start' => clone $current,
            'end' => clone $threeMonthsFromNow
        ];
    }

    // Фильтруем периоды: минимальная продолжительность 3 ночи (4 дня)
    $filteredPeriods = [];
    $minNights = 3;

    foreach ($freePeriods as $period) {
        $interval = $period['start']->diff($period['end']);
        $totalNights = $interval->days;

        // Если период достаточно длинный для минимального бронирования
        if ($totalNights >= $minNights) {
            $filteredPeriods[] = $period;
        }
    }

    // Форматируем результат
    $formattedDates = [];
    foreach ($filteredPeriods as $period) {
        $startStr = $period['start']->format('d.m.Y');
        $endStr = $period['end']->format('d.m.Y');

        if ($startStr === $endStr) {
            $formattedDates[] = $startStr;
        } else {
            $formattedDates[] = $startStr . ' - ' . $endStr;
        }
    }

    $hasFreeDates = !empty($formattedDates);

    return [
        "dates" => implode("\n", $formattedDates),
        "has_free_dates" => $hasFreeDates,
        "free_periods" => $filteredPeriods
    ];
}

// Обработка POST запросов
$selectedObject = $_POST['object'] ?? '';
$action = $_POST['action'] ?? '';
$selectedChannels = $_POST['channels'] ?? [];
$messageText = $_POST['message_text'] ?? '';

// Чтение данных о каналах
$channelsData = [];

// Если выбран объект - читаем данные
if ($selectedObject) {
    $dataFile = __DIR__ . '/task_files/channels.csv';
    if (file_exists($dataFile)) {
        $channelsData = readChannelsData($dataFile, $selectedObject);
    }
}

// Получаем информацию о свободных датах
$freeDatesInfo = ['has_free_dates' => false, 'dates' => ''];
if ($selectedObject) {
    $freeDatesInfo = getFreeDates($selectedObject);
}

// Если выбран объект и не указан текст сообщения, генерируем его
if ($selectedObject && !$messageText && $freeDatesInfo['has_free_dates']) {
    $free_dates_message = $freeDatesInfo['dates'];

    // Здесь можно задать разные заголовки под каждый объект
    $objectData = [
        'halo' => [
            'title' => 'Halo',
            'description' => '1BR 36м2, 3й этаж, вид на бассейн'
        ],
        'dvushka' => [
            'title' => 'Двушка',
            'description' => '2BR 54м2, 5й этаж, вид на море'
        ]
    ];

    $title = $objectData[$selectedObject]['title'] ?? $objects[$selectedObject] ?? $selectedObject;
    $description = $objectData[$selectedObject]['description'] ?? 'апартаменты';

    $messageText = (
        "Аренда квартиры в новом комплексе {$title} в 400м от пляжа Най Янг\n" .
        "10 минут езды от аэропорта!\n" .
        "🏡 {$description}\n\n" .
        "🗝️Собственник!\n\n" .
        "СВОБОДНЫЕ ДЛЯ БРОНИРОВАНИЯ ДАТЫ (ближайшие 3 месяца):\n\n" .
        "{$free_dates_message}\n\n" .
        "⚠️Есть и другие варианты, спрашивайте в ЛС."
    );
}

// Отправка в Telegram - УПРОЩЕННАЯ ВЕРСИЯ
$sendResult = null;
if ($action === 'send' && !empty($selectedChannels) && !empty($messageText)) {
    // Собираем список ID чатов для отправки
    $channelIds = [];
    $channelNames = [];

    foreach ($selectedChannels as $channelIndex) {
        if (isset($channelsData[$channelIndex])) {
            $channel = $channelsData[$channelIndex];
            $channelIds[] = $channel['channel_id'];
            $channelNames[] = $channel['display_name'];
        }
    }

    // Формируем имя файла
    $timestamp = date('Ymd_His');
    $filename = "Рассылка_{$selectedObject}_{$timestamp}.json";

    // Формируем данные для отправки в Telegram
    $postData = [
        'form_type' => 'telegram_poster',
        'init_chat_id' => $INIT_CHAT_ID,
        'object' => $selectedObject,
        'message_text' => $messageText,
        'include_images' => false,
        'channel_ids' => $channelIds,
        'channel_names' => $channelNames,
        'channels_count' => count($channelIds),
        'timestamp' => date('Y-m-d H:i:s'),
        'filename' => $filename
    ];

    // Простая отправка через прямой include файла send_to_telegram.php
    $_GET['token'] = $TELEGRAM_BOT_TOKEN;
    $_GET['chat_id'] = $CHAT_ID;
    $_GET['as_file'] = '1';

    ob_start();
    $_POST = $postData; // Передаем данные как POST
    include __DIR__ . '/send_to_telegram.php';
    $response = ob_get_clean();

    $result = json_decode($response, true);

    if ($result && isset($result['ok']) && $result['ok']) {
        $sendResult = [
            'success' => true,
            'message' => 'Данные успешно отправлены в Telegram',
            'filename' => $filename,
            'channels_count' => count($channelIds)
        ];
    } else {
        $sendResult = [
            'success' => false,
            'message' => $result['error'] ?? 'Неизвестная ошибка при отправке',
            'filename' => $filename,
            'channels_count' => count($channelIds)
        ];
    }
}
?>

<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Рассылка в Telegram каналы</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        .container { max-width: 1200px; }
        .card { box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: none; border-radius: 15px; }
        .channel-item { border: 1px solid #dee2e6; border-radius: 8px; padding: 15px; margin-bottom: 10px; }
        .channel-item:hover { background-color: #f8f9fa; }
        .result-alert { margin-top: 20px; }
        .channel-info { font-size: 0.9em; color: #6c757d; }
        .loading { display: none; text-align: center; padding: 20px; }
        .spinner { border: 3px solid #f3f3f3; border-top: 3px solid #0d6efd; border-radius: 50%; width: 24px; height: 24px; animation: spin 1s linear infinite; margin: 0 auto 12px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .object-badge { background-color: #e9ecef; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; }
        .collapse-header { cursor: pointer; }
        .collapse-header::after { content: ' ▼'; transition: transform 0.2s; }
        .collapse-header.collapsed::after { transform: rotate(-90deg); }
        .no-free-dates {
            background-color: #f8d7da;
            color: #721c24;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
            border: 1px solid #f5c6cb;
        }
        .debug-info {
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 15px;
            margin: 15px 0;
            font-size: 0.9em;
        }
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
        }
        .error-message {
            color: #dc3545;
            font-size: 12px;
            margin-top: -8px;
            margin-bottom: 8px;
            display: block;
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
<body class="bg-light">
    <div class="container py-5">
        <div class="row justify-content-center">
            <div class="col-12">
                <div class="card p-4 mb-4">
                    <div class="d-flex justify-content-between align-items-center mb-4">
                        <h2 class="text-center mb-0">Рассылка в Telegram каналы</h2>
                        <button type="button" class="btn btn-outline-secondary btn-sm" onclick="location.reload()">
                            🔄 Новая рассылка
                        </button>
                    </div>

                    <?php if ($sendResult): ?>
                        <div class="alert <?= $sendResult['success'] ? 'alert-success' : 'alert-danger' ?> result-alert">
                            <h5><?= $sendResult['success'] ? '✅ Успешно' : '❌ Ошибка' ?></h5>
                            <p><?= htmlspecialchars($sendResult['message']) ?></p>
                            <?php if ($sendResult['success']): ?>
                                <p><strong>Файл:</strong> <?= htmlspecialchars($sendResult['filename']) ?></p>
                                <p><strong>Количество каналов:</strong> <?= $sendResult['channels_count'] ?></p>
                            <?php endif; ?>
                        </div>
                    <?php endif; ?>

                    <!-- Отладочная информация -->
                    <?php if ($selectedObject): ?>
                    <div class="debug-info">
                        <strong>Отладочная информация:</strong><br>
                        Объект: <?= htmlspecialchars($selectedObject) ?><br>
                        Свободные даты: <?= $freeDatesInfo['has_free_dates'] ? 'ДА' : 'НЕТ' ?><br>
                        Количество каналов: <?= count($channelsData) ?><br>
                        <pre style="margin: 10px 0 0 0; font-size: 0.8em;"><?= htmlspecialchars($freeDatesInfo['dates']) ?></pre>
                    </div>
                    <?php endif; ?>

                    <form method="POST" id="telegramForm">
                        <input type="hidden" name="action" id="formAction" value="">
                        <input type="hidden" name="token" value="<?= htmlspecialchars($TELEGRAM_BOT_TOKEN) ?>">
                        <input type="hidden" name="chat_id" value="<?= htmlspecialchars($CHAT_ID) ?>">
                        <input type="hidden" name="init_chat_id" value="<?= htmlspecialchars($INIT_CHAT_ID) ?>">

                        <!-- Выбор объекта -->
                        <div class="row mb-4">
                            <div class="col-md-6">
                                <label for="objectSelect" class="form-label">Объект недвижимости</label>
                                <select class="form-select" id="objectSelect" name="object" required
                                    onchange="this.form.submit()">
                                    <option value="">Выберите объект...</option>
                                    <?php if (empty($objects)): ?>
                                        <option value="">Объекты не найдены</option>
                                    <?php else: ?>
                                        <?php foreach ($objects as $value => $name): ?>
                                            <option value="<?= htmlspecialchars($value) ?>"
                                                <?= $selectedObject === $value ? 'selected' : '' ?>>
                                                <?= htmlspecialchars($name) ?>
                                            </option>
                                        <?php endforeach; ?>
                                    <?php endif; ?>
                                </select>
                            </div>
                        </div>

                        <?php if ($selectedObject && !empty($channelsData)): ?>
                            <!-- Список каналов -->
                            <div class="row mb-4">
                                <div class="col-12">
                                    <h5>Доступные каналы для рассылки</h5>
                                    <p class="text-muted">
                                        Показываются каналы где объект пустой ИЛИ объект = "<?= htmlspecialchars($objects[$selectedObject] ?? $selectedObject) ?>"
                                        и прошло более 8 дней с последней публикации
                                    </p>

                                    <div class="mb-3">
                                        <button type="button" class="btn btn-outline-primary btn-sm"
                                            onclick="selectAllChannels()">Выбрать все</button>
                                        <button type="button" class="btn btn-outline-secondary btn-sm"
                                            onclick="deselectAllChannels()">Снять все</button>
                                        <span class="ms-3 text-muted">Выбрано: <span id="selectedCount"><?= count($channelsData) ?></span> каналов</span>
                                    </div>

                                    <div id="channelsList">
                                        <?php foreach ($channelsData as $index => $channel): ?>
                                            <div class="channel-item">
                                                <div class="form-check">
                                                    <input class="form-check-input channel-checkbox"
                                                        type="checkbox"
                                                        name="channels[]"
                                                        value="<?= $index ?>"
                                                        id="channel<?= $index ?>"
                                                        checked>
                                                    <label class="form-check-label w-100" for="channel<?= $index ?>">
                                                        <div class="d-flex justify-content-between align-items-center">
                                                            <div>
                                                                <strong><?= htmlspecialchars($channel['display_name']) ?></strong>
                                                                <?php if (!empty($channel['object'])): ?>
                                                                    <span class="object-badge ms-2"><?= htmlspecialchars($channel['object']) ?></span>
                                                                <?php else: ?>
                                                                    <span class="object-badge ms-2">для всех объектов</span>
                                                                <?php endif; ?>
                                                                <div class="channel-info mt-2">
                                                                    <div class="collapse-header collapsed" data-bs-toggle="collapse" href="#info_<?= $index ?>" role="button" aria-expanded="false">
                                                                        Подробности
                                                                    </div>
                                                                    <div class="collapse" id="info_<?= $index ?>">
                                                                        ID: <?= htmlspecialchars($channel['channel_id']) ?> |
                                                                        Дней с последней публикации: <?= !empty($channel['days_since_last_post']) ? $channel['days_since_last_post'] : 'не указано' ?> |
                                                                        Картинки: <?= $channel['accepts_images'] ?>
                                                                        <?php if (!empty($channel['last_post_time'])): ?>
                                                                            | Последняя отправка: <?= $channel['last_post_time'] ?>
                                                                        <?php endif; ?>
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </label>
                                                </div>
                                            </div>
                                        <?php endforeach; ?>
                                    </div>
                                </div>
                            </div>

                            <!-- Текст сообщения -->
                            <div class="row mb-4">
                                <div class="col-12">
                                    <label for="messageText" class="form-label">Текст сообщения</label>
                                    <textarea class="form-control" id="messageText" name="message_text"
                                        rows="6" placeholder="Введите текст для рассылки..."
                                        required><?= htmlspecialchars($messageText) ?></textarea>
                                    <div class="form-text">
                                        <small>Свободные даты автоматически добавляются в сообщение. Минимальное бронирование: 3 ночи.</small>
                                    </div>
                                </div>
                            </div>

                            <!-- Сообщение о недоступных датах -->
                            <?php if (!$freeDatesInfo['has_free_dates'] && $selectedObject): ?>
                                <div class="no-free-dates">
                                    <strong>🚫 Нет свободных дат для бронирования от 3 ночей</strong><br>
                                    Для объекта "<?= htmlspecialchars($objects[$selectedObject] ?? $selectedObject) ?>" нет свободных дат для бронирования на ближайшие 3 месяца (минимально 3 ночи).
                                </div>
                            <?php endif; ?>

                            <!-- Кнопка отправки -->
                            <div class="row">
                                <div class="col-12">
                                    <button type="button" class="btn btn-primary btn-lg w-100"
                                        id="sendButton"
                                        <?= !$freeDatesInfo['has_free_dates'] ? 'disabled' : '' ?>>
                                        📢 Отправить в выбранные каналы (<?= count($channelsData) ?>)
                                    </button>
                                </div>
                            </div>

                            <!-- Индикатор загрузки -->
                            <div class="loading" id="loading">
                                <div class="spinner"></div>
                                <p>Отправка данных в Telegram...</p>
                            </div>

                        <?php elseif ($selectedObject && empty($channelsData)): ?>
                            <div class="alert alert-info">
                                Для выбранного объекта "<?= htmlspecialchars($objects[$selectedObject] ?? $selectedObject) ?>" нет доступных каналов для рассылки.
                                Возможно, все каналы имеют недавние публикации (менее 8 дней).
                            </div>
                        <?php endif; ?>
                    </form>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        class TelegramPosterForm {
            constructor() {
                this.tg = window.Telegram.WebApp;
                this.tg.expand();
                this.tg.enableClosingConfirmation();
                this.isSubmitting = false;
                this.init();
            }
            init() {
                this.bindEvents();
            }
            bindEvents() {
                document.getElementById('sendButton').addEventListener('click', (e) => {
                    e.preventDefault();
                    this.submitForm();
                });
            }
            setSubmitButtonState(disabled, loading = false) {
                const button = document.getElementById('sendButton');
                const originalText = '📢 Отправить в выбранные каналы (' + <?= count($channelsData) ?> + ')';
                if (disabled) {
                    button.disabled = true;
                    button.textContent = loading ? '⏳ Отправка...' : 'Отправка...';
                    button.classList.add('btn-secondary');
                    button.classList.remove('btn-primary');
                } else {
                    button.disabled = false;
                    button.textContent = originalText;
                    button.classList.add('btn-primary');
                    button.classList.remove('btn-secondary');
                }
                this.isSubmitting = disabled;
            }
            async submitForm() {
                if (this.isSubmitting) return;
                const form = document.getElementById('telegramForm');
                const formData = new FormData(form);
                const selectedChannels = document.querySelectorAll('input[name="channels[]"]:checked');
                if (selectedChannels.length === 0) {
                    this.tg.showPopup({
                        title: 'Ошибка',
                        message: 'Пожалуйста, выберите хотя бы один канал для отправки',
                        buttons: [{ type: 'ok' }]
                    });
                    return;
                }
                this.setSubmitButtonState(true, true);
                document.getElementById('loading').style.display = 'block';
                try {
                    const selectedChannels = Array.from(document.querySelectorAll('input[name="channels[]"]:checked')).map(cb => cb.value);
                    const messageText = document.getElementById('messageText').value;
                    const selectedObject = document.getElementById('objectSelect').value;
                    const timestamp = new Date().toLocaleString('ru-RU');
                    const filename = `Рассылка_${selectedObject}_${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
                    const posterData = {
                        form_type: 'telegram_poster',
                        init_chat_id: <?= $INIT_CHAT_ID_JS ?>,
                        object: selectedObject,
                        message_text: messageText,
                        include_images: false,
                        channel_ids: selectedChannels.map(index => {
                            const channel = <?= json_encode($channelsData) ?>;
                            return channel[index]?.channel_id || '';
                        }),
                        channel_names: selectedChannels.map(index => {
                            const channel = <?= json_encode($channelsData) ?>;
                            return channel[index]?.display_name || '';
                        }),
                        channels_count: selectedChannels.length,
                        timestamp: timestamp,
                        filename: filename
                    };
                    const response = await fetch(`send_to_telegram.php?token=<?= $TELEGRAM_BOT_TOKEN ?>&chat_id=<?= $CHAT_ID ?>&as_file=1`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(posterData)
                    });
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    const result = await response.json();
                    if (result.ok) {
                        this.tg.showPopup({
                            title: '✅ Успех',
                            message: `Данные успешно отправлены в ${selectedChannels.length} каналов!`,
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
                }
            }
        }
        document.addEventListener('DOMContentLoaded', () => {
            new TelegramPosterForm();
        });

        function selectAllChannels() {
            document.querySelectorAll('.channel-checkbox').forEach(checkbox => {
                checkbox.checked = true;
            });
            updateSelectedCount();
        }

        function deselectAllChannels() {
            document.querySelectorAll('.channel-checkbox').forEach(checkbox => {
                checkbox.checked = false;
            });
            updateSelectedCount();
        }

        function updateSelectedCount() {
            const selected = document.querySelectorAll('.channel-checkbox:checked').length;
            document.getElementById('selectedCount').textContent = selected;
        }

        // Обновляем счетчик при изменении выбора
        document.addEventListener('DOMContentLoaded', function() {
            document.querySelectorAll('.channel-checkbox').forEach(checkbox => {
                checkbox.addEventListener('change', updateSelectedCount);
            });
            updateSelectedCount();
        });
    </script>
</body>
</html>