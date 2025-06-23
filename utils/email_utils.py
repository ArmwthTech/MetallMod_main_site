"""
Утилиты для отправки email-сообщений с использованием aiosmtplib.
"""
import aiosmtplib
from email.message import EmailMessage
import os

# --- Настройки SMTP ---
MAIL_HOST = os.getenv('MAIL_HOST', 'smtp.mail.ru')
MAIL_PORT = int(os.getenv('MAIL_PORT', 465))
MAIL_USER = os.getenv('MAIL_USER', 'test_sender@metallmod.ru')
MAIL_PASS = os.getenv('MAIL_PASS')
# TODO: заменить на production email
MAIL_TO = os.getenv('MAIL_TO', 'test_receiver@metallmod.ru')


async def send_calc_form_email(name: str, phone: str, file_data: bytes, file_name: str, file_url: str = None):
    """
    Формирует и отправляет email с данными из формы калькулятора.

    Args:
        name (str): Имя отправителя.
        phone (str): Телефон отправителя.
        file_data (bytes): Содержимое файла в виде байтов для вложения.
        file_name (str): Имя файла для вложения.
        file_url (str, optional): Ссылка на загруженный файл. Defaults to None.

    Raises:
        ValueError: Если не заданы переменные окружения MAIL_USER или MAIL_TO.
    """
    if not MAIL_USER or not MAIL_PASS:
        # В реальном проекте здесь лучше использовать logging вместо print
        print("Ошибка: MAIL_USER или MAIL_PASS не установлены. Письмо не будет отправлено.")
        # Можно либо выбросить исключение, либо просто выйти, чтобы не ломать приложение
        # raise ValueError("MAIL_USER and MAIL_PASS environment variables must be set.")
        return

    msg = EmailMessage()
    msg['From'] = MAIL_USER
    msg['To'] = MAIL_TO
    msg['Subject'] = 'Новая заявка с сайта МеталлМод'

    # --- Формирование тела письма ---
    body = f"""
    Новая заявка с сайта МеталлМод:

    Имя: {name}
    Телефон: {phone}
    """
    if file_url:
        body += f"\nСсылка на загруженный файл: {file_url}"

    msg.set_content(body)

    # --- Добавление вложения ---
    if file_data and file_name:
        msg.add_attachment(file_data, maintype='application',
                           subtype='octet-stream', filename=file_name)

    # --- Отправка письма ---
    try:
        await aiosmtplib.send(
            msg,
            hostname=MAIL_HOST,
            port=MAIL_PORT,
            username=MAIL_USER,
            password=MAIL_PASS,
            use_tls=True
        )
    except Exception as e:
        # Логгирование ошибки отправки
        print(f"Ошибка отправки email: {e}")
        # В реальном приложении здесь можно добавить логику повторной отправки
        # или уведомление администратора.
