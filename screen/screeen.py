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


def is_working_hours(start_time, end_time):
    """Проверяет, находится ли текущее время в рабочем интервале"""
    current_time = datetime.now().time()
    return start_time <= current_time <= end_time


def main():
    # Настройки
    interval_minutes = 15  # Интервал между скриншотами в минутах
    sender_email = "lexagoldenpost@yandex.ru"
    sender_password = "whwooytowcrkgumj"
    receiver_email = "lexagoldenpost@yandex.ru"

    # Время работы скрипта
    work_start = datetime.strptime("09:00", "%H:%M").time()  # Начало работы (9:00)
    work_end = datetime.strptime("18:20", "%H:%M").time()  # Конец работы (18:20)

    if not os.path.exists("screenshots"):
        os.makedirs("screenshots")

    print(f"Скрипт будет работать с {work_start} до {work_end}")
    print("В нерабочее время скрипт будет ожидать начала рабочего дня")

    while True:
        try:
            # Проверяем, рабочее ли сейчас время
            if not is_working_hours(work_start, work_end):
                current_time = datetime.now().strftime('%H:%M')
                print(f"\n{current_time} - Не рабочее время. Ожидание до {work_start}...")

                # Рассчитываем время до начала следующего рабочего дня
                now = datetime.now()
                next_start = datetime.combine(now.date(), work_start)

                # Если текущее время после окончания работы, переносим на следующий день
                if now.time() > work_end:
                    next_start = datetime.combine(now.date(), work_start) + timedelta(days=1)

                # Спим до начала рабочего времени
                sleep_seconds = (next_start - now).total_seconds()
                if sleep_seconds > 0:
                    time.sleep(min(sleep_seconds, 3600))  # Проверяем каждый час
                continue

            # Если рабочее время - выполняем основную работу
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

            # Проверяем время во время ожидания
            for _ in range(interval_minutes * 60 // 60):  # Проверяем каждую минуту
                if not is_working_hours(work_start, work_end):
                    break
                time.sleep(60)

        except KeyboardInterrupt:
            print("\nПрограмма остановлена пользователем.")
            break
        except Exception as e:
            print(f"Ошибка: {e}\nПовтор через 5 минут...")
            time.sleep(5 * 60)


if __name__ == "__main__":
    print("Скриншоттер с автоудалением запущен. Для остановки нажмите Ctrl+C")
    main()