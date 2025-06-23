"""
Утилиты для аутентификации администратора.
Включает проверку пароля, защиту от брутфорса и управление сессиями через cookies.
"""
from passlib.context import CryptContext
from fastapi import Request
import os
import time

# --- Настройки аутентификации ---
# Пример: логин admin, пароль admin (замените хеш на свой через bcrypt)
# Для генерации нового хеша:
# from passlib.context import CryptContext; print(CryptContext(schemes=["bcrypt"]).hash('ВАШ_ПАРОЛЬ'))
ADMIN_LOGIN = os.getenv('ADMIN_LOGIN', 'admin')
ADMIN_PASSWORD_HASH = os.getenv(
    # хеш для пароля 'admin'
    'ADMIN_PASSWORD_HASH', '$2b$12$tIRqINWexvSTylVDOd/xTu5x5le9/o.GODN0/4Gax8rkr8Plip1Ga')

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Настройки защиты от брутфорса ---
FAILED_ATTEMPTS = {}  # Словарь для хранения неудачных попыток входа по IP
BLOCK_TIME = 300      # Время блокировки в секундах (5 минут)
MAX_ATTEMPTS = 5      # Максимальное количество попыток до блокировки


def get_client_ip(request: Request) -> str:
    """Возвращает IP-адрес клиента из запроса."""
    return request.client.host if request and request.client else 'unknown'


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет, соответствует ли обычный пароль хешированному."""
    return pwd_context.verify(plain_password, hashed_password)


def authenticate_admin(login: str, password: str, request: Request = None) -> (bool, str or None):
    """
    Проверяет учетные данные администратора с учетом защиты от брутфорса.

    Args:
        login (str): Логин администратора.
        password (str): Пароль администратора.
        request (Request): Запрос FastAPI для получения IP-адреса.

    Returns:
        tuple: (True, None) в случае успеха, (False, "сообщение об ошибке") в случае неудачи.
    """
    ip = get_client_ip(request)
    now = time.time()

    # 1. Проверка, не заблокирован ли IP
    if ip in FAILED_ATTEMPTS:
        fail_info = FAILED_ATTEMPTS[ip]
        if fail_info.get('blocked_until', 0) > now:
            remaining_time = int((fail_info["blocked_until"] - now) // 60 + 1)
            return False, f'Слишком много попыток. Попробуйте через {remaining_time} мин.'

    # 2. Проверка учетных данных
    if login == ADMIN_LOGIN and verify_password(password, ADMIN_PASSWORD_HASH):
        if ip in FAILED_ATTEMPTS:
            del FAILED_ATTEMPTS[ip]  # Сбрасываем счетчик при успешном входе
        return True, None

    # 3. Обработка неудачной попытки
    fail_info = FAILED_ATTEMPTS.setdefault(
        ip, {'count': 0, 'blocked_until': 0})
    fail_info['count'] += 1

    if fail_info['count'] >= MAX_ATTEMPTS:
        fail_info['blocked_until'] = now + BLOCK_TIME
        fail_info['count'] = 0  # Сбрасываем счетчик после блокировки
        return False, 'Слишком много попыток. IP заблокирован на 5 минут.'

    return False, 'Неверный логин или пароль'


# --- Управление сессией через Cookies ---
SESSION_COOKIE = 'admin_session'
SESSION_VALUE = os.getenv('ADMIN_SESSION_VALUE',
                          'supersecret_change_in_production')


def set_admin_session(response):
    """Устанавливает cookie сессии для администратора."""
    response.set_cookie(SESSION_COOKIE, SESSION_VALUE,
                        httponly=True, samesite='lax')


def is_admin_authenticated(request: Request) -> bool:
    """Проверяет, установлен ли у пользователя валидный cookie сессии."""
    return request.cookies.get(SESSION_COOKIE) == SESSION_VALUE


def logout_admin(response):
    """Удаляет cookie сессии, завершая сеанс администратора."""
    response.delete_cookie(SESSION_COOKIE)
