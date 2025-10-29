<?php
// send_to_telegram.php — универсальный обработчик отправки данных в Telegram

// Заголовки
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST');
header('Access-Control-Allow-Headers: Content-Type');

// Параметры из URL
$BOT_TOKEN = $_GET['token'] ?? '';
$CHAT_ID   = $_GET['chat_id'] ?? '';
$AS_FILE   = ($_GET['as_file'] ?? '1') === '1'; // по умолчанию — как файл

// Валидация
if (empty($BOT_TOKEN) || empty($CHAT_ID)) {
    http_response_code(400);
    echo json_encode(['error' => 'Параметры token и chat_id обязательны']);
    exit;
}

// Получаем JSON-тело
$input = file_get_contents('php://input');
$data = json_decode($input, true);

if (!is_array($data)) {
    http_response_code(400);
    echo json_encode(['error' => 'Тело запроса должно быть валидным JSON']);
    exit;
}

// Генерация имени файла (если нужно)
$filename = 'form_data.json';
if (isset($data['filename']) && preg_match('/^[a-zA-Zа-яА-Я0-9_\-\.\s]+\.json$/u', $data['filename'])) {
    $filename = $data['filename'];
}

// Капшн (опционально)
// $caption = $data['caption'] ?? (
//     isset($data['message']) ? $data['message'] : '📄 Новые данные из веб-формы'
// );

// Текст для отправки как сообщение (если не файл)
$messageText = $data['message'] ?? json_encode($data, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);

// Отправка
if ($AS_FILE) {
    // === Отправка как JSON-файл ===
    $tmpFile = tempnam(sys_get_temp_dir(), 'tg_form_') . '.json';
    // Удаляем служебные поля перед сохранением
$saveData = $data;
unset($saveData['filename']);
unset($saveData['caption']);

if (!file_put_contents($tmpFile, json_encode($saveData, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT))) {
        http_response_code(500);
        echo json_encode(['error' => 'Не удалось создать временный файл']);
        exit;
    }

    $curlFile = curl_file_create($tmpFile, 'application/json', $filename);
    if (!$curlFile) {
        unlink($tmpFile);
        http_response_code(500);
        echo json_encode(['error' => 'Ошибка создания файла для cURL']);
        exit;
    }

    $payload = [
        'chat_id' => $CHAT_ID,
        'document' => $curlFile,
        'caption' => mb_substr($caption, 0, 1024), // лимит caption — 1024 символа
        'disable_notification' => true,
        'parse_mode' => 'Markdown'
    ];

    $url = "https://api.telegram.org/bot{$BOT_TOKEN}/sendDocument";

} else {
    // === Отправка как текстовое сообщение ===
    $payload = [
        'chat_id' => $CHAT_ID,
        'text' => mb_substr($messageText, 0, 4096), // лимит текста — 4096 символов
        'disable_notification' => true,
        'parse_mode' => 'Markdown'
    ];

    $url = "https://api.telegram.org/bot{$BOT_TOKEN}/sendMessage";
}

// Выполняем запрос
$ch = curl_init($url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, $payload);
curl_setopt($ch, CURLOPT_TIMEOUT, 15);
curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, true);

$response = curl_exec($ch);
$httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

// Удаляем временный файл (если был)
if (isset($tmpFile) && file_exists($tmpFile)) {
    unlink($tmpFile);
}

// Ответ клиенту
if ($httpCode === 200) {
    error_log("[✅ Telegram] Данные успешно отправлены в чат {$CHAT_ID}");
    echo json_encode([
        'ok' => true,
        'message' => 'Данные успешно отправлены в Telegram'
    ]);
} else {
    error_log("[❌ Telegram] Ошибка (HTTP {$httpCode}): " . substr($response, 0, 500));
    echo json_encode([
        'error' => "Ошибка Telegram API: HTTP {$httpCode}"
    ]);
}