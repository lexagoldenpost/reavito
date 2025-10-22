# ssl_generator.py
import os
import subprocess
import sys
from pathlib import Path


def generate_ssl_certificates_force():
    """Генерация SSL сертификатов с несколькими способами"""
    try:
        cert_file = "lapkabookink.com+3.pem"
        key_file = "lapkabookink.com+3-key.pem"

        # Если сертификаты уже существуют
        if os.path.exists(cert_file) and os.path.exists(key_file):
            print("✅ SSL сертификаты уже существуют")
            return True

        print("🔐 Попытка генерации SSL сертификатов...")

        # Способ 1: Проверяем mkcert в PATH
        mkcert_paths = [
            "mkcert",
            "mkcert.exe",
            r"C:\Program Files\mkcert\mkcert.exe",
            r"C:\Windows\System32\mkcert.exe"
        ]

        mkcert_found = None
        for mkcert_cmd in mkcert_paths:
            try:
                result = subprocess.run([mkcert_cmd, "--version"],
                                        capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    mkcert_found = mkcert_cmd
                    print(f"✅ Найден mkcert: {mkcert_cmd}")
                    break
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

        if mkcert_found:
            # Генерируем сертификаты через mkcert
            cmd = [mkcert_found, 'lapkabookink.com', 'localhost', '127.0.0.1', '::1']
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())

            if result.returncode == 0:
                print("✅ SSL сертификаты успешно сгенерированы через mkcert")
                return True
            else:
                print(f"❌ Ошибка mkcert: {result.stderr}")

        # Способ 2: Используем openssl если mkcert не найден
        print("🔄 mkcert не найден, пробуем через OpenSSL...")
        return generate_self_signed_cert()

    except Exception as e:
        print(f"❌ Ошибка при генерации SSL сертификатов: {e}")
        # Последняя попытка - самоподписанный сертификат
        return generate_self_signed_cert()


def generate_self_signed_cert():
    """Генерация самоподписанного SSL сертификата через OpenSSL"""
    try:
        cert_file = "lapkabookink.com+3.pem"
        key_file = "lapkabookink.com+3-key.pem"

        # Проверяем OpenSSL
        try:
            subprocess.run(["openssl", "version"], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            print("❌ OpenSSL не установлен. Установите OpenSSL или mkcert")
            return False

        # Генерируем приватный ключ
        key_cmd = [
            "openssl", "genrsa", "-out", key_file, "2048"
        ]
        subprocess.run(key_cmd, check=True, cwd=os.getcwd())

        # Создаем конфиг для сертификата
        config_content = f"""
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_req
prompt = no

[req_distinguished_name]
C = RU
ST = Moscow
L = Moscow
O = LapkaBooking
OU = IT Department
CN = lapkabookink.com

[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = lapkabookink.com
DNS.2 = localhost
DNS.3 = www.lapkabookink.com
IP.1 = 127.0.0.1
IP.2 = ::1
"""

        config_file = "ssl_config.cnf"
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(config_content)

        # Генерируем самоподписанный сертификат
        cert_cmd = [
            "openssl", "req", "-new", "-x509", "-key", key_file,
            "-out", cert_file, "-days", "365", "-config", config_file
        ]
        subprocess.run(cert_cmd, check=True, cwd=os.getcwd())

        # Удаляем временный конфиг
        if os.path.exists(config_file):
            os.remove(config_file)

        print("✅ Самоподписанные SSL сертификаты созданы через OpenSSL")
        print("⚠️  Браузер может показывать предупреждение о безопасности")
        return True

    except Exception as e:
        print(f"❌ Ошибка создания самоподписанного сертификата: {e}")
        return False


def check_ssl_files():
    """Проверка существования SSL файлов"""
    cert_file = "lapkabookink.com+3.pem"
    key_file = "lapkabookink.com+3-key.pem"

    if os.path.exists(cert_file) and os.path.exists(key_file):
        print(f"✅ SSL файлы найдены: {cert_file}, {key_file}")
        return True
    else:
        print(f"❌ SSL файлы не найдены: {cert_file}, {key_file}")
        return False


if __name__ == "__main__":
    generate_ssl_certificates_force()