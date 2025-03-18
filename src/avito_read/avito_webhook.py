import logging

from flask import Flask, request, jsonify
import hmac
import hashlib
import logging
logging.basicConfig(level=logging.DEBUG, filename="py_log.log",filemode="w")

app = Flask(__name__)

# Секретный ключ из кабинета Avito
AVITO_SECRET = 'ваш_секретный_ключ'

@app.route('/avito_webhook', methods=['POST'])
def handle_webhook():
    # Получаем подпись из заголовка
    #signature = request.headers.get('X-Avito-Signature')
    #if not signature:
     #   return jsonify({'error': 'Signature missing'}), 403

    # Получаем сырые данные для проверки подписи
    #raw_data = request.get_data()

    # Генерируем HMAC подпись
    #generated_signature = hmac.new(
     #   AVITO_SECRET.encode('utf-8'),
      #  raw_data,
       # hashlib.sha256
    #).hexdigest()

    # Сравниваем подписи
    #if not hmac.compare_digest(signature, generated_signature):
     #   return jsonify({'error': 'Invalid signature'}), 403

    # Если подпись верна, обрабатываем данные
    data = request.json
    print("Received webhook data:", data)

    # Пример обработки сообщения
    if 'message' in data:
        message = data['message']
        print(f"New message from user {data['user_id']}: {message['text']}")

    # Отвечаем Avito, что запрос успешно обработан
    return jsonify({'status': 'success'}), 200

if __name__ == '__main__':
  #app.run(host='0.0.0.0', port=5000, ssl_context='adhoc')  # Для теста используем самоподписанный сертификат
  app.run(host='localhost', port=5000)  # Для теста используем самоподписанный сертификат
  logging.debug(f"Старт")