import os
from dotenv import load_dotenv

load_dotenv()

# --- Базы данных ---
DB_PORTFOLIO = os.getenv('DB_PORTFOLIO', 'sqlite:///portfolio.db')
DB_REVIEWS = os.getenv('DB_REVIEWS', 'sqlite:///reviews.db')
DB_KM_REQUESTS = os.getenv('DB_KM_REQUESTS', 'sqlite:///km_requests.db')
DB_POPUP_EMAILS = os.getenv('DB_POPUP_EMAILS', 'sqlite:///popup_emails.db')
DB_URL = os.getenv('DB_URL', 'sqlite:///main.db')

# --- Email ---
MAIL_HOST = os.getenv('MAIL_HOST', 'smtp.mail.ru')
MAIL_PORT = int(os.getenv('MAIL_PORT', 465))
MAIL_USER = os.getenv('MAIL_USER', 'test_sender@metallmod.ru')
MAIL_PASS = os.getenv('MAIL_PASS')
MAIL_TO = os.getenv('MAIL_TO', 'test_receiver@metallmod.ru')

# --- Админка ---
ADMIN_LOGIN = os.getenv('ADMIN_LOGIN', 'admin')
ADMIN_PASSWORD_HASH = os.getenv(
    'ADMIN_PASSWORD_HASH', '$2b$12$tIRqINWexvSTylVDOd/xTu5x5le9/o.GODN0/4Gax8rkr8Plip1Ga')
ADMIN_SESSION_VALUE = os.getenv(
    'ADMIN_SESSION_VALUE', 'supersecret_change_in_production')

# --- Прочее ---
SESSION_COOKIE = 'admin_session'
