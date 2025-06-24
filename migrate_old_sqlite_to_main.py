import sqlite3
from datetime import datetime
from MetallMod_main_site.app import Session, Portfolio, Review, KmRequest, PopupEmail

# Путь к старым базам
old_dbs = {
    'portfolio': 'portfolio.db',
    'reviews': 'reviews.db',
    'km_requests': 'km_requests.db',
    'popup_emails': 'popup_emails.db',
}

# --- Перенос Portfolio ---


def migrate_portfolio():
    conn = sqlite3.connect(old_dbs['portfolio'])
    cur = conn.cursor()
    cur.execute(
        'SELECT id, title, description, image_path, image_paths FROM portfolio')
    rows = cur.fetchall()
    session = Session()
    for row in rows:
        item = Portfolio(
            id=row[0],
            title=row[1],
            description=row[2],
            image_path=row[3],
            image_paths=row[4]
        )
        session.merge(item)
    session.commit()
    session.close()
    conn.close()
    print(f'Перенесено {len(rows)} записей Portfolio')

# --- Перенос Review ---


def migrate_reviews():
    conn = sqlite3.connect(old_dbs['reviews'])
    cur = conn.cursor()
    cur.execute('SELECT id, client_name, text, logo_path FROM reviews')
    rows = cur.fetchall()
    session = Session()
    for row in rows:
        item = Review(
            id=row[0],
            client_name=row[1],
            text=row[2],
            logo_path=row[3]
        )
        session.merge(item)
    session.commit()
    session.close()
    conn.close()
    print(f'Перенесено {len(rows)} записей Review')

# --- Перенос KmRequest ---


def migrate_km_requests():
    conn = sqlite3.connect(old_dbs['km_requests'])
    cur = conn.cursor()
    cur.execute(
        'SELECT id, name, phone, email, km_link, created_at, processed FROM km_requests')
    rows = cur.fetchall()
    session = Session()
    for row in rows:
        # Преобразуем строку в datetime, если не None
        created_at = None
        if row[5]:
            try:
                created_at = datetime.fromisoformat(row[5])
            except Exception:
                try:
                    created_at = datetime.strptime(
                        row[5], "%Y-%m-%d %H:%M:%S.%f")
                except Exception:
                    created_at = datetime.strptime(row[5], "%Y-%m-%d %H:%M:%S")
        item = KmRequest(
            id=row[0],
            name=row[1],
            phone=row[2],
            email=row[3],
            km_link=row[4],
            created_at=created_at,
            processed=bool(row[6])
        )
        session.merge(item)
    session.commit()
    session.close()
    conn.close()
    print(f'Перенесено {len(rows)} записей KmRequest')

# --- Перенос PopupEmail ---


def migrate_popup_emails():
    conn = sqlite3.connect(old_dbs['popup_emails'])
    cur = conn.cursor()
    cur.execute('SELECT id, email, created_at FROM popup_email')
    rows = cur.fetchall()
    session = Session()
    for row in rows:
        # Преобразуем строку в datetime, если не None
        created_at = None
        if row[2]:
            try:
                created_at = datetime.fromisoformat(row[2])
            except Exception:
                try:
                    created_at = datetime.strptime(
                        row[2], "%Y-%m-%d %H:%M:%S.%f")
                except Exception:
                    created_at = datetime.strptime(row[2], "%Y-%m-%d %H:%M:%S")
        item = PopupEmail(
            id=row[0],
            email=row[1],
            created_at=created_at
        )
        session.merge(item)
    session.commit()
    session.close()
    conn.close()
    print(f'Перенесено {len(rows)} записей PopupEmail')


if __name__ == '__main__':
    migrate_portfolio()
    migrate_reviews()
    migrate_km_requests()
    # migrate_popup_emails()  # больше не нужна
    print('Перенос завершён!')
