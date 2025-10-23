import time
from datetime import datetime

import psutil


def terminate_process(process_name):
    """Завершает процесс по имени"""
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] == process_name:
            proc.terminate()
            return True
    return False


def schedule_termination(process_name, target_time):
    """Планирует завершение процесса на указанное время"""
    while True:
        current_time = datetime.now().strftime("%H:%M")
        if current_time == target_time:
            print(f"Попытка завершить процесс {process_name}...")
            if terminate_process(process_name):
                print(f"Процесс {process_name} успешно завершен.")
            else:
                print(f"Процесс {process_name} не найден.")
            break
        time.sleep(30)  # Проверяем время каждые 30 секунд


if __name__ == "__main__":
    # Настройки
    PROGRAM_TO_TERMINATE = "MouseJiggler.exe"  # Имя процесса для завершения
    TERMINATION_TIME = "18:30"  # Время завершения (формат HH:MM)

    print(f"Программа запущена. Процесс {PROGRAM_TO_TERMINATE} будет завершен в {TERMINATION_TIME}")
    print("Для выхода нажмите Ctrl+C")

    try:
        schedule_termination(PROGRAM_TO_TERMINATE, TERMINATION_TIME)
    except KeyboardInterrupt:
        print("Работа программы остановлена пользователем.")