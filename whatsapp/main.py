import pywhatkit
import datetime

# Настройки
phone_number = "+79169127547"  # Замените на номер получателя в международном формате
message = "Привет! Это тестовое сообщение из Python через WhatsApp"
wait_time = 15  # Время ожидания перед отправкой (секунды)
close_tab = True  # Закрыть вкладку браузера после отправки

try:
  # Получаем текущее время
  now = datetime.datetime.now()

  # Отправляем сообщение
  pywhatkit.sendwhatmsg(
      phone_no=phone_number,
      message=message,
      time_hour=now.hour,
      time_min=now.minute + 1,  # Отправить через 1 минуту
      wait_time=wait_time,
      tab_close=close_tab
  )

  print("Сообщение успешно отправлено!")
except Exception as e:
  print(f"Произошла ошибка: {e}")