import os
import smtplib
import ssl
import time
from datetime import datetime
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import mss
import pyautogui


def take_screenshot():
    """Создает скриншот и возвращает путь к файлу"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"screenshot_{timestamp}.png"
    with mss.mss() as sct:
        sct.shot(output=filename)
    return filename

def send_email(sender_email, sender_password, receiver_email, subject, body, attachment_path):
    """Отправляет email с вложением и удаляет файл после отправки"""
    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        with open(attachment_path, 'rb') as attachment:
            img = MIMEImage(attachment.read())
            img.add_header('Content-Disposition', 'attachment', filename=os.path.basename(attachment_path))
            msg.attach(img)

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.yandex.ru", 465, context=context) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_email, msg.as_string())

        os.remove(attachment_path)
        print(f"Файл {attachment_path} успешно отправлен и удален.")
        return True

    except Exception as e:
        print(f"Ошибка при отправке/удалении: {e}")
        return False

def should_stop_script(stop_time):
    """Проверяет, наступило ли время остановки скрипта"""
    current_time = datetime.now().time()
    return current_time >= stop_time

def main():
    # Настройки
    interval_minutes = 15  # Интервал между скриншотами в минутах
    sender_email = "lexagoldenpost@yandex.ru"
    sender_password = "whwooytowcrkgumj"
    receiver_email = "lexagoldenpost@yandex.ru"
    stop_time = datetime.strptime("18:30", "%H:%M").time()  # Время остановки (18:30)

    if not os.path.exists("screenshots"):
        os.makedirs("screenshots")

    while True:
        try:
            # Проверяем, не наступило ли время остановки
            if should_stop_script(stop_time):
                print(f"Время остановки ({stop_time}) наступило. Завершение работы.")
                break

            print(f"\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Создание скриншота...")
            screenshot_path = take_screenshot()

            new_path = os.path.join("screenshots", os.path.basename(screenshot_path))
            os.rename(screenshot_path, new_path)
            screenshot_path = new_path

            print("Отправка письма...")
            success = send_email(
                sender_email,
                sender_password,
                receiver_email,
                f"Скриншот от {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "Автоматически отправленный скриншот.",
                screenshot_path
            )

            if not success:
                print("Файл не был удален из-за ошибки отправки.")

            print(f"Ожидание {interval_minutes} минут до следующего скриншота...")
            time.sleep(interval_minutes * 60)

        except KeyboardInterrupt:
            print("\nПрограмма остановлена пользователем.")
            break
        except Exception as e:
            print(f"Ошибка: {e}\nПовтор через 5 минут...")
            time.sleep(5 * 60)

if __name__ == "__main__":
    print("Скриншоттер с автоудалением запущен. Для остановки нажмите Ctrl+C")
    main()