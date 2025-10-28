# local_receiver.py
from flask import Flask, request, jsonify
import csv
import os
from datetime import datetime

app = Flask(__name__)

# Папка для сохранения данных (в корне проекта, как вы предпочитаете)
DATA_DIR = 'received_data'
os.makedirs(DATA_DIR, exist_ok=True)

@app.route('/receive', methods=['POST'])
def receive_data():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data"}), 400

        # Пример обработки: сохраняем в CSV
        filename = f"{DATA_DIR}/form_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Записываем заголовки (ключи первого уровня)
            keys = data.keys()
            writer.writerow(keys)
            writer.writerow([data[k] for k in keys])

        print(f"✅ Данные получены и сохранены в: {filename}")
        return jsonify({"status": "ok", "file": filename})

    except Exception as e:
        print("❌ Ошибка:", e)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 Локальный приёмник запущен на http://localhost:8080")
    print("Убедитесь, что он работает перед отправкой данных с веб-формы.")
    app.run(host='127.0.0.1', port=8080, debug=False)