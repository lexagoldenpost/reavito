# main_tg_bot/ftp_client.py
import ftplib
import os
from pathlib import Path
from typing import List, Dict
from ftplib import FTP_TLS

from common.logging_config import setup_logger

logger = setup_logger("ftp_client")


class FTPClient:
    def __init__(self):
        self.ftp = None

    def connect(self, host: str, username: str, password: str, port: int = 21, use_ftps: bool = False) -> bool:
        """
        Подключение к FTP/FTPS серверу

        Args:
            host: FTP хост
            username: Имя пользователя
            password: Пароль
            port: Порт (по умолчанию 21)
            use_ftps: Использовать FTPS (безопасный FTP)

        Returns:
            bool: True если подключение успешно
        """
        try:
            if use_ftps:
                self.ftp = FTP_TLS()
                self.ftp.connect(host, port)
                self.ftp.login(username, password)
                self.ftp.prot_p()  # Включаем защищенный канал данных
                logger.info(f"Успешное подключение к FTPS серверу {host}:{port}")
            else:
                self.ftp = ftplib.FTP()
                self.ftp.connect(host, port)
                self.ftp.login(username, password)
                logger.info(f"Успешное подключение к FTP серверу {host}:{port}")

            return True

        except Exception as e:
            logger.error(f"Ошибка подключения к FTP серверу {host}:{port}: {e}")
            return False

    def disconnect(self):
        """Закрытие соединения с FTP сервером"""
        if self.ftp:
            try:
                self.ftp.quit()
                logger.info("Соединение с FTP сервером закрыто")
            except Exception as e:
                logger.error(f"Ошибка при закрытии соединения: {e}")
            finally:
                self.ftp = None

    def _create_remote_directory(self, remote_path: str):
        """
        Рекурсивно создает директории на FTP сервере
        """
        if not remote_path or remote_path == "/":
            return

        try:
            # Пробуем перейти в директорию
            self.ftp.cwd(remote_path)
        except ftplib.error_perm:
            # Если не удалось, создаем директорию рекурсивно
            parent_path = os.path.dirname(remote_path.rstrip('/'))
            if parent_path and parent_path != '/':
                self._create_remote_directory(parent_path)

            self.ftp.mkd(remote_path)
            logger.info(f"Создана директория на FTP: {remote_path}")

    def upload_file(self, local_file_path: Path, remote_filename: str = None, remote_path: str = "/") -> bool:
        """
        Загружает один файл на FTP сервер

        Args:
            local_file_path: Локальный путь к файлу
            remote_filename: Имя файла на сервере (если None, используется оригинальное имя)
            remote_path: Удаленная директория

        Returns:
            bool: True если файл успешно загружен
        """
        if not self.ftp:
            logger.error("FTP соединение не установлено")
            return False

        if not local_file_path.exists():
            logger.error(f"Локальный файл не существует: {local_file_path}")
            return False

        try:
            # Создаем удаленную директорию если нужно
            if remote_path and remote_path != "/":
                self._create_remote_directory(remote_path)
                self.ftp.cwd(remote_path)

            # Определяем имя файла на сервере
            if remote_filename is None:
                remote_filename = local_file_path.name

            # Загружаем файл
            with open(local_file_path, 'rb') as f:
                self.ftp.storbinary(f"STOR {remote_filename}", f)

            logger.info(f"Файл {local_file_path.name} успешно загружен на FTP сервер")
            return True

        except Exception as e:
            logger.error(f"Ошибка при загрузке файла {local_file_path} на FTP: {e}")
            return False

    def upload_files(self, file_paths: List[Path], remote_path: str = "/") -> Dict[Path, bool]:
        """
        Загружает несколько файлов на FTP сервер

        Args:
            file_paths: Список путей к файлам
            remote_path: Удаленная директория

        Returns:
            Dict[Path, bool]: Словарь с результатами загрузки для каждого файла
        """
        results = {}

        for file_path in file_paths:
            success = self.upload_file(file_path, remote_path=remote_path)
            results[file_path] = success

        return results

    def list_files(self, remote_path: str = "/") -> List[str]:
        """
        Получает список файлов в удаленной директории
        """
        if not self.ftp:
            logger.error("FTP соединение не установлено")
            return []

        try:
            if remote_path and remote_path != "/":
                self.ftp.cwd(remote_path)

            files = self.ftp.nlst()
            logger.info(f"Найдено {len(files)} файлов в директории {remote_path}")
            return files

        except Exception as e:
            logger.error(f"Ошибка при получении списка файлов: {e}")
            return []

    def delete_file(self, remote_filename: str, remote_path: str = "/") -> bool:
        """
        Удаляет файл на FTP сервере
        """
        if not self.ftp:
            logger.error("FTP соединение не установлено")
            return False

        try:
            if remote_path and remote_path != "/":
                self.ftp.cwd(remote_path)

            self.ftp.delete(remote_filename)
            logger.info(f"Файл {remote_filename} удален с FTP сервера")
            return True

        except Exception as e:
            logger.error(f"Ошибка при удалении файла {remote_filename}: {e}")
            return False
