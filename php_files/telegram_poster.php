<?php
// telegram_poster.php
// Файл, который нужно исключить (укажите здесь имя файла без расширения)
$EXCLUDED_FILE = 'booking_other'; // ЗАМЕНИТЕ на имя файла, которое нужно исключить
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

        $normalizedSelectedObject = str_replace('_', ' ', $selectedObject);

        while (($row = fgetcsv($handle, 1000, ",")) !== false) {
            if (count($row) >= 5) {
                $chatName = trim($row[$headerIndexes['Наименование чата']] ?? '');
                $daysSinceLastPost = trim($row[$headerIndexes['Количество сообщение после последней публикации']] ?? '');
                $channelName = trim($row[$headerIndexes['Название канала']] ?? '');
                $object = trim($row[$headerIndexes['Объект']] ?? '');
                $lastPostTime = trim($row[$headerIndexes['Время последней отправки']] ?? '');
                $acceptsImages = trim($row[$headerIndexes['Картинки принимает (Да/Нет)']] ?? '');
                $minDays = trim($row[$headerIndexes['Срок в днях меньше которого не отправляем']] ?? '7');

                $channelId = $chatName;

                $objectMatch = false;
                if (empty($object)) {
                    $objectMatch = true;
                } else {
                    $objectMatch = stripos($object, $normalizedSelectedObject) !== false;
                }

                $daysCondition = false;
                if ($daysSinceLastPost === '') {
                    $daysCondition = true;
                } else {
                    $daysValue = intval($daysSinceLastPost);
                    $daysCondition = $daysValue > 8;
                }

                $timeCondition = false;
                $minDaysInt = intval($minDays);

                if (empty($lastPostTime)) {
                    $timeCondition = true;
                } else {
                    $lastPostDateTime = null;
                    $formats = [
                        'Y-m-d H:i:s',
                        'd.m.Y',
                        'd.m.Y H:i:s',
                        'Y-m-d',
                    ];

                    foreach ($formats as $format) {
                        $lastPostDateTime = DateTime::createFromFormat($format, $lastPostTime);
                        if ($lastPostDateTime !== false) {
                            break;
                        }
                    }

                    if ($lastPostDateTime) {
                        $currentDateTime = new DateTime();

                        if ($lastPostDateTime > $currentDateTime) {
                            $timeCondition = false;
                        } else {
                            $interval = $currentDateTime->diff($lastPostDateTime);
                            $daysSinceLast = $interval->days;
                            $timeCondition = $daysSinceLast > $minDaysInt;
                        }
                    } else {
                        $timeCondition = true;
                    }
                }

                if ($objectMatch && $daysCondition && $timeCondition) {
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

$bookingFilesPath = __DIR__ . '/booking_files/*.csv';
$files = glob($bookingFilesPath);
$objects = [];

if (!empty($files)) {
    foreach ($files as $file) {
        $filename = pathinfo($file, PATHINFO_FILENAME);
        // Исключаем указанный файл
        if ($filename === $EXCLUDED_FILE) {
            continue;
        }
        $displayName = ucwords(str_replace('_', ' ', $filename));
        $objects[$filename] = $displayName;
    }
}

function getFreeDates($object) {
    $filePath = __DIR__ . "/booking_files/{$object}.csv";
    if (!file_exists($filePath)) {
        return ["error" => "Файл бронирования не найден", "has_free_dates" => false];
    }

    $bookedPeriods = [];
    $currentDate = new DateTime();
    $threeMonthsFromNow = (new DateTime())->modify('+3 months');

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
                    $bookedPeriods[] = [
                        'start' => clone $checkInDate,
                        'end' => clone $checkOutDate
                    ];
                }
            }
        }
        fclose($handle);
    }

    usort($bookedPeriods, function($a, $b) {
        return $a['start'] <=> $b['start'];
    });

    $freePeriods = [];
    $current = clone $currentDate;

    foreach ($bookedPeriods as $booking) {
        if ($booking['start'] > $current) {
            $freeEnd = min($booking['start'], $threeMonthsFromNow);
            if ($current < $freeEnd) {
                $freePeriods[] = [
                    'start' => clone $current,
                    'end' => $freeEnd
                ];
            }
        }

        if ($booking['end'] > $current) {
            $current = clone $booking['end'];
        }

        if ($current >= $threeMonthsFromNow) {
            break;
        }
    }

    if ($current < $threeMonthsFromNow) {
        $freePeriods[] = [
            'start' => clone $current,
            'end' => clone $threeMonthsFromNow
        ];
    }

    $filteredPeriods = [];
    $minNights = 3;

    foreach ($freePeriods as $period) {
        $interval = $period['start']->diff($period['end']);
        $totalNights = $interval->days;

        if ($totalNights >= $minNights) {
            $filteredPeriods[] = $period;
        }
    }

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

$selectedObject = $_POST['object'] ?? '';
$action = $_POST['action'] ?? '';
$selectedChannels = $_POST['channels'] ?? [];
$messageText = $_POST['message_text'] ?? '';

$channelsData = [];
if ($selectedObject) {
    $dataFile = __DIR__ . '/task_files/channels.csv';
    if (file_exists($dataFile)) {
        $channelsData = readChannelsData($dataFile, $selectedObject);
    }
}

$freeDatesInfo = ['has_free_dates' => false, 'dates' => ''];
if ($selectedObject) {
    $freeDatesInfo = getFreeDates($selectedObject);
}

if ($selectedObject && !$messageText && $freeDatesInfo['has_free_dates']) {
    $objectData = [
        'halo_title' => [
            'line1' => 'Аренда квартиры в новом комплексе Halo Title в 400м от пляжа Най Янг',
            'line2' => '10 минут езды от аэропорта!',
            'line3' => '🏡 1BR 36м2, 3й этаж, вид на бассейн'
        ],
        'citygate_p311' => [
            'line1' => 'Аренда квартиры в комплексе Citygate в 700м от пляжа Камала',
            'line2' => '30 минут езды от аэропорта!',
            'line3' => '🏡 1BR 38м2, 3й этаж, вид на горы'
        ]
    ];

    if (isset($objectData[$selectedObject])) {
        $line1 = $objectData[$selectedObject]['line1'];
        $line2 = $objectData[$selectedObject]['line2'];
        $line3 = $objectData[$selectedObject]['line3'];

        $messageText = (
            "{$line1}\n" .
            "{$line2}\n" .
            "{$line3}\n\n" .
            "🗝️Собственник!\n\n" .
            "СВОБОДНЫЕ ДЛЯ БРОНИРОВАНИЯ ДАТЫ (ближайшие 3 месяца):\n\n" .
            "{$freeDatesInfo['dates']}\n\n" .
            "⚠️Пишите свои даты в ЛС."
        );
    } else {
        // fallback: использовать имя объекта в сообщении
        $messageText = "Объект: {$objects[$selectedObject]}\n\nСвободные даты:\n{$freeDatesInfo['dates']}";
    }
}

$sendResult = null;
if ($action === 'send' && !empty($selectedChannels) && !empty($messageText)) {
    // ✅ ФОРМИРУЕМ ПОЛНЫЙ СПИСОК КАНАЛОВ С МЕТАДАННЫМИ
    $channelList = [];

    foreach ($selectedChannels as $channelIndex) {
        if (isset($channelsData[$channelIndex])) {
            $channel = $channelsData[$channelIndex];
            $channelList[] = [
                'channel_id' => $channel['channel_id'],
                'display_name' => $channel['display_name'],
                'accepts_images' => strtolower(trim($channel['accepts_images'])) === 'да',
                'object' => $channel['object'],
                'last_post_time' => $channel['last_post_time'],
                'min_days' => $channel['min_days']
            ];
        }
    }

    $timestamp = date('Ymd_His');
    $filename = "Рассылка_{$selectedObject}_{$timestamp}.json";

    $postData = [
        'form_type' => 'telegram_poster',
        'init_chat_id' => $INIT_CHAT_ID,
        'object' => $selectedObject,
        'message_text' => $messageText,
        'include_images' => false, // может быть обновлено в send_to_telegram.php
        'channels' => $channelList, // ✅ полный список вместо channel_ids
        'channels_count' => count($channelList),
        'timestamp' => date('Y-m-d H:i:s'),
        'filename' => $filename
    ];

    $_GET['token'] = $TELEGRAM_BOT_TOKEN;
    $_GET['chat_id'] = $CHAT_ID;
    $_GET['as_file'] = '1';

    ob_start();
    $_POST = $postData;
    include __DIR__ . '/send_to_telegram.php';
    $response = ob_get_clean();

    $result = json_decode($response, true);

    if ($result && isset($result['ok']) && $result['ok']) {
        $sendResult = [
            'success' => true,
            'message' => 'Данные успешно отправлены в Telegram',
            'filename' => $filename,
            'channels_count' => count($channelList)
        ];
    } else {
        $sendResult = [
            'success' => false,
            'message' => $result['error'] ?? 'Неизвестная ошибка при отправке',
            'filename' => $filename,
            'channels_count' => count($channelList)
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
        /* ... (стили без изменений) ... */
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

                        <div class="row mb-4">
                            <div class="col-md-6">
                                <label for="objectSelect" class="form-label">Объект недвижимости</label>
                                <select class="form-select" id="objectSelect" name="object" required onchange="this.form.submit()">
    <option value="">Выберите объект...</option>
    <?php if (empty($objects)): ?>
        <option value="">Объекты не найдены</option>
    <?php else: ?>
        <?php foreach ($objects as $value => $name): ?>
            <?php if ($value !== 'booking_other'): ?>
                <option value="<?= htmlspecialchars($value) ?>" <?= $selectedObject === $value ? 'selected' : '' ?>>
                    <?= htmlspecialchars($name) ?>
                </option>
            <?php endif; ?>
        <?php endforeach; ?>
    <?php endif; ?>
</select>
                            </div>
                        </div>

                        <?php if ($selectedObject && !empty($channelsData)): ?>
                            <div class="row mb-4">
                                <div class="col-12">
                                    <h5>Доступные каналы для рассылки</h5>
                                    <p class="text-muted">
                                        Показываются каналы где объект пустой ИЛИ объект = "<?= htmlspecialchars($objects[$selectedObject] ?? $selectedObject) ?>"
                                        и прошло более 8 дней с последней публикации
                                    </p>

                                    <div class="mb-3">
                                        <button type="button" class="btn btn-outline-primary btn-sm" onclick="selectAllChannels()">Выбрать все</button>
                                        <button type="button" class="btn btn-outline-secondary btn-sm" onclick="deselectAllChannels()">Снять все</button>
                                        <span class="ms-3 text-muted">Выбрано: <span id="selectedCount"><?= count($channelsData) ?></span> каналов</span>
                                    </div>

                                    <div id="channelsList">
                                        <?php foreach ($channelsData as $index => $channel): ?>
                                            <div class="channel-item">
                                                <div class="form-check">
                                                    <input class="form-check-input channel-checkbox" type="checkbox" name="channels[]" value="<?= $index ?>" id="channel<?= $index ?>" checked>
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
                                                                        Картинки: <?= htmlspecialchars($channel['accepts_images']) ?>
                                                                        <?php if (!empty($channel['last_post_time'])): ?>
                                                                            | Последняя отправка: <?= htmlspecialchars($channel['last_post_time']) ?>
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

                            <div class="row mb-4">
                                <div class="col-12">
                                    <label for="messageText" class="form-label">Текст сообщения</label>
                                    <textarea class="form-control" id="messageText" name="message_text" rows="6" placeholder="Введите текст для рассылки..." required><?= htmlspecialchars($messageText) ?></textarea>
                                    <div class="form-text">
                                        <small>Свободные даты автоматически добавляются в сообщение. Минимальное бронирование: 3 ночи.</small>
                                    </div>
                                </div>
                            </div>

                            <?php if (!$freeDatesInfo['has_free_dates'] && $selectedObject): ?>
                                <div class="no-free-dates">
                                    <strong>🚫 Нет свободных дат для бронирования от 3 ночей</strong><br>
                                    Для объекта "<?= htmlspecialchars($objects[$selectedObject] ?? $selectedObject) ?>" нет свободных дат для бронирования на ближайшие 3 месяца (минимально 3 ночи).
                                </div>
                            <?php endif; ?>

                            <div class="row">
                                <div class="col-12">
                                    <button type="button" class="btn btn-primary btn-lg w-100" id="sendButton" <?= !$freeDatesInfo['has_free_dates'] ? 'disabled' : '' ?>>
                                        📢 Отправить в выбранные каналы (<?= count($channelsData) ?>)
                                    </button>
                                </div>
                            </div>

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
                const selectedCheckboxes = document.querySelectorAll('input[name="channels[]"]:checked');
                if (selectedCheckboxes.length === 0) {
                    this.tg.showPopup({ title: 'Ошибка', message: 'Пожалуйста, выберите хотя бы один канал', buttons: [{ type: 'ok' }] });
                    return;
                }

                const channelsData = <?= json_encode($channelsData) ?>;
                const selectedIndices = Array.from(selectedCheckboxes).map(cb => cb.value);
                const channelList = selectedIndices.map(idx => {
                    const ch = channelsData[idx];
                    return {
                        channel_id: ch.channel_id,
                        display_name: ch.display_name,
                        accepts_images: (ch.accepts_images || '').toLowerCase() === 'да',
                        object: ch.object,
                        last_post_time: ch.last_post_time,
                        min_days: ch.min_days
                    };
                });

                const messageText = document.getElementById('messageText').value.trim();
                const selectedObject = document.getElementById('objectSelect').value;
                const timestamp = new Date().toLocaleString('ru-RU');
                const filename = `Рассылка_${selectedObject}_${new Date().toISOString().replace(/[:.]/g, '-')}.json`;

                const posterData = {
                    form_type: 'telegram_poster',
                    init_chat_id: <?= $INIT_CHAT_ID_JS ?>,
                    object: selectedObject,
                    message_text: messageText,
                    include_images: false,
                    channels: channelList, // ✅ передаём полный список
                    channels_count: channelList.length,
                    timestamp: timestamp,
                    filename: filename
                };

                this.setSubmitButtonState(true, true);
                document.getElementById('loading').style.display = 'block';

                try {
                    const response = await fetch(`send_to_telegram.php?token=<?= $TELEGRAM_BOT_TOKEN ?>&chat_id=<?= $CHAT_ID ?>&as_file=1`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(posterData)
                    });

                    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                    const result = await response.json();

                    if (result.ok) {
                        this.tg.showPopup({ title: '✅ Успех', message: `Отправлено в ${channelList.length} каналов!`, buttons: [{ type: 'ok' }] });
                        setTimeout(() => this.tg.close(), 2000);
                    } else {
                        throw new Error(result.error || 'Ошибка отправки');
                    }
                } catch (error) {
                    console.error('Submit error:', error);
                    this.tg.showPopup({
                        title: '❌ Ошибка',
                        message: error.message || 'Не удалось отправить. Проверьте соединение.',
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

            document.querySelectorAll('.channel-checkbox').forEach(checkbox => {
                checkbox.addEventListener('change', updateSelectedCount);
            });
            updateSelectedCount();
        });

        function selectAllChannels() {
            document.querySelectorAll('.channel-checkbox').forEach(cb => cb.checked = true);
            updateSelectedCount();
        }

        function deselectAllChannels() {
            document.querySelectorAll('.channel-checkbox').forEach(cb => cb.checked = false);
            updateSelectedCount();
        }

        function updateSelectedCount() {
            const count = document.querySelectorAll('.channel-checkbox:checked').length;
            document.getElementById('selectedCount').textContent = count;
        }
    </script>
</body>
</html>