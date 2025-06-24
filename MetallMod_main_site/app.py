"""
Основной файл приложения FastAPI для сайта "МеталлМод".
Обрабатывает все маршруты, управляет базой данных и рендерингом шаблонов.
"""

from fastapi import FastAPI, Request, Form, UploadFile, File, Query, Depends, Body
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import json
from pathlib import Path
from utils.email_utils import send_calc_form_email, send_km_form_email
import aiofiles
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from models.popup_email import Base, PopupEmail
from email_validator import validate_email, EmailNotValidError
from models.portfolio import Base as PortfolioBase, Portfolio
from models.review import Base as ReviewBase, Review
from utils.auth_utils import authenticate_admin, set_admin_session, is_admin_authenticated, logout_admin
from models.km_request import Base as KmRequestBase, KmRequest
import csv
from io import StringIO

from dotenv import load_dotenv
load_dotenv()

# --- Инициализация ---

app = FastAPI(
    title="MetallMod Main Site",
    description="API для управления контентом и обработкой форм сайта МеталлМод.",
    version="1.0.0"
)

# Подключение статики
app.mount('/static', StaticFiles(directory='static'), name='static')

# Подключение шаблонов
templates = Jinja2Templates(directory='templates')

# Добавляем кастомный фильтр в Jinja2 для работы с JSON-строками в шаблонах
templates.env.filters['from_json'] = lambda s: json.loads(s) if s else []

# --- Инициализация отдельных баз данных ---
DB_PORTFOLIO = 'sqlite:///portfolio.db'
DB_REVIEWS = 'sqlite:///reviews.db'
DB_KM_REQUESTS = 'sqlite:///km_requests.db'
DB_POPUP_EMAILS = 'sqlite:///popup_emails.db'

engine_portfolio = create_engine(DB_PORTFOLIO, connect_args={
                                 "check_same_thread": False})
engine_reviews = create_engine(DB_REVIEWS, connect_args={
                               "check_same_thread": False})
engine_km_requests = create_engine(DB_KM_REQUESTS, connect_args={
                                   "check_same_thread": False})
engine_popup_emails = create_engine(DB_POPUP_EMAILS, connect_args={
                                    "check_same_thread": False})

PortfolioBase.metadata.create_all(engine_portfolio)
ReviewBase.metadata.create_all(engine_reviews)
KmRequestBase.metadata.create_all(engine_km_requests)
Base.metadata.create_all(engine_popup_emails)

SessionPortfolio = scoped_session(sessionmaker(bind=engine_portfolio))
SessionReviews = scoped_session(sessionmaker(bind=engine_reviews))
SessionKmRequests = scoped_session(sessionmaker(bind=engine_km_requests))
SessionPopupEmails = scoped_session(sessionmaker(bind=engine_popup_emails))

# --- Утилиты и зависимости ---


def get_locale(request: Request) -> str:
    """Определяет язык пользователя из query-параметра 'lang'."""
    lang = request.query_params.get('lang', 'ru')
    if lang not in ['ru', 'en']:
        lang = 'ru'
    return lang


def load_translations(lang: str) -> dict:
    """Загружает файл перевода для указанного языка."""
    path = Path('translations') / f'{lang}.json'
    if not path.exists():
        path = Path('translations/ru.json')  # Язык по умолчанию
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _(key: str, translations: dict) -> str:
    """Возвращает перевод для ключа или сам ключ, если перевод не найден."""
    return translations.get(key, key)

# --- Основные маршруты ---


@app.get('/', response_class=HTMLResponse)
def index(request: Request):
    """
    Главная страница сайта.
    Отображает портфолио и отзывы.
    """
    lang = get_locale(request)
    translations = load_translations(lang)

    def translate(key):
        return _(key, translations)

    db_portfolio = SessionPortfolio()
    db_reviews = SessionReviews()
    try:
        portfolio_items = db_portfolio.query(
            Portfolio).order_by(Portfolio.id.desc()).all()
        reviews = db_reviews.query(Review).order_by(Review.id.desc()).all()
    finally:
        db_portfolio.close()
        db_reviews.close()

    return templates.TemplateResponse('index.html', {
        'request': request,
        'lang': lang,
        '_': translate,
        'title': 'МеталлМод',
        'portfolio_items': portfolio_items,
        'reviews': reviews
    })


@app.post('/send-calc-form')
async def send_calc_form(name: str = Form(...), phone: str = Form(...), file: UploadFile = File(None)):
    """
    Принимает данные из формы калькулятора, сохраняет файл и отправляет email.
    """
    if file:
        save_dir = 'static/uploads'
        os.makedirs(save_dir, exist_ok=True)
        file_path = os.path.join(save_dir, file.filename)
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)
        file_url = f'/static/uploads/{file.filename}'
        await send_calc_form_email(name, phone, content, file.filename, file_url=file_url)
    else:
        await send_calc_form_email(name, phone, None, None, file_url=None)
    return JSONResponse({'success': True, 'message': 'Заявка отправлена!'})


@app.post('/popup-email')
async def popup_email(email: str = Form(...)):
    """
    Сохраняет email из всплывающей формы в базу данных.
    """
    try:
        validate_email(email)
    except EmailNotValidError:
        return JSONResponse({'success': False, 'message': 'Некорректный email'})
    db = SessionPopupEmails()
    try:
        if db.query(PopupEmail).filter_by(email=email).first():
            return JSONResponse({'success': True, 'message': 'Email уже сохранён'})
        new_popup_email = PopupEmail(email=email)
        db.add(new_popup_email)
        db.commit()
    finally:
        db.close()
    return JSONResponse({'success': True, 'message': 'Email сохранён'})


@app.post('/send-km-form')
async def send_km_form(
    name: str = Form(...),
    phone: str = Form(...),
    email: str = Form(...),
    km_link: str = Form(None),
    consent: str = Form(...)
):
    """
    Принимает данные из формы КМ, сохраняет в БД и отправляет email админу.
    """
    db = SessionKmRequests()
    try:
        km_request = KmRequest(
            name=name,
            phone=phone,
            email=email,
            km_link=km_link
        )
        db.add(km_request)
        db.commit()
    finally:
        db.close()

    await send_km_form_email(name, phone, email, km_link)

    return JSONResponse({'success': True, 'message': 'Заявка отправлена!'})

# --- Админка: Портфолио ---


@app.get('/admin', response_class=HTMLResponse)
def admin_root(request: Request):
    """Перенаправляет на страницу входа или в админку в зависимости от авторизации."""
    if is_admin_authenticated(request):
        return RedirectResponse('/admin/portfolio', status_code=303)
    return RedirectResponse('/admin/login', status_code=303)


@app.get('/admin/portfolio', response_class=HTMLResponse)
def admin_portfolio(request: Request):
    """Страница управления портфолио (только для авторизованных админов)."""
    if not is_admin_authenticated(request):
        return RedirectResponse('/admin/login', status_code=303)
    db = SessionPortfolio()
    try:
        items = db.query(Portfolio).order_by(Portfolio.id.desc()).all()
        for item in items:
            try:
                item.image_paths_json = json.dumps(
                    json.loads(item.image_paths or '[]'))
            except Exception:
                item.image_paths_json = '[]'
    finally:
        db.close()
    return templates.TemplateResponse('admin/portfolio_manage.html', {'request': request, 'items': items})


@app.post('/admin/portfolio/add')
async def add_portfolio(request: Request, title: str = Form(...), description: str = Form(...), images: list = File(None)):
    """Добавляет новый проект в портфолио."""
    if not is_admin_authenticated(request):
        return RedirectResponse('/admin/login', status_code=303)
    db = SessionPortfolio()
    image_paths = []
    img_dir = 'static/uploads/portfolio_img'
    os.makedirs(img_dir, exist_ok=True)
    if images:
        if not isinstance(images, list):
            images = [images]
        for image in images:
            if getattr(image, 'filename', None):
                img_path = os.path.join(img_dir, image.filename)
                async with aiofiles.open(img_path, 'wb') as out_file:
                    content = await image.read()
                    await out_file.write(content)
                image_url = f'/static/uploads/portfolio_img/{image.filename}'
                image_paths.append(image_url)
    image_path = image_paths[0] if image_paths else None
    item = Portfolio(title=title, description=description,
                     image_path=image_path, image_paths=json.dumps(image_paths))
    db.add(item)
    db.commit()
    db.close()
    return RedirectResponse('/admin/portfolio', status_code=303)


@app.post('/admin/portfolio/delete/{item_id}')
def delete_portfolio(request: Request, item_id: int):
    """Удаляет проект из портфолио."""
    if not is_admin_authenticated(request):
        return RedirectResponse('/admin/login', status_code=303)
    db = SessionPortfolio()
    item = db.query(Portfolio).filter_by(id=item_id).first()
    if item:
        db.delete(item)
        db.commit()
    db.close()
    return RedirectResponse('/admin/portfolio', status_code=303)


@app.post('/admin/portfolio/update_images/{item_id}')
def update_portfolio_images(request: Request, item_id: int, data: dict = Body(...)):
    """Обновляет порядок изображений для проекта в портфолио."""
    if not is_admin_authenticated(request):
        return JSONResponse({'success': False, 'message': 'Not authenticated'})
    images = data.get('images', [])
    db = SessionPortfolio()
    item = db.query(Portfolio).filter_by(id=item_id).first()
    if not item:
        db.close()
        return JSONResponse({'success': False, 'message': 'Проект не найден'})
    item.image_paths = json.dumps(images)
    item.image_path = images[0] if images else None
    db.commit()
    db.close()
    return JSONResponse({'success': True})


@app.post('/admin/portfolio/edit/{item_id}')
async def edit_portfolio(
    request: Request,
    item_id: int,
    title: str = Form(...),
    description: str = Form(...),
    images: list = File(None),
    deleted_images: str = Form(None),
    current_images_order: str = Form(None)
):
    if not is_admin_authenticated(request):
        return RedirectResponse('/admin/login', status_code=303)
    db = SessionPortfolio()
    item = db.query(Portfolio).filter_by(id=item_id).first()
    if not item:
        db.close()
        return RedirectResponse('/admin/portfolio', status_code=303)
    # Обновляем текстовые поля
    item.title = title
    item.description = description

    # Удаляем отмеченные фото
    if deleted_images:
        deleted = json.loads(deleted_images)
        current = json.loads(item.image_paths or '[]')
        current = [img for img in current if img not in deleted]
        item.image_paths = json.dumps(current)
        item.image_path = current[0] if current else None

    # Добавляем новые фото
    img_dir = 'static/uploads/portfolio_img'
    os.makedirs(img_dir, exist_ok=True)
    new_images = []
    if images:
        if not isinstance(images, list):
            images = [images]
        for image in images:
            if getattr(image, 'filename', None):
                img_path = os.path.join(img_dir, image.filename)
                async with aiofiles.open(img_path, 'wb') as out_file:
                    content = await image.read()
                    await out_file.write(content)
                image_url = f'/static/uploads/portfolio_img/{image.filename}'
                new_images.append(image_url)
    # Объединяем старые и новые фото
    all_images = json.loads(item.image_paths or '[]') + new_images
    # Если передан порядок, используем его
    if current_images_order:
        try:
            order = json.loads(current_images_order)
            # Добавляем новые фото, если их нет в порядке
            for img in new_images:
                if img not in order:
                    order.append(img)
            all_images = order
        except Exception:
            pass
    item.image_paths = json.dumps(all_images)
    item.image_path = all_images[0] if all_images else None

    db.commit()
    db.close()
    return RedirectResponse('/admin/portfolio', status_code=303)

# --- Админка: Отзывы ---


@app.get('/admin/reviews', response_class=HTMLResponse)
def admin_reviews(request: Request):
    """Страница управления отзывами (только для авторизованных админов)."""
    if not is_admin_authenticated(request):
        return RedirectResponse('/admin/login', status_code=303)
    db = SessionReviews()
    items = db.query(Review).order_by(Review.id.desc()).all()
    db.close()
    return templates.TemplateResponse('admin/reviews_manage.html', {'request': request, 'items': items})


@app.post('/admin/reviews/add')
async def add_review(request: Request, client_name: str = Form(...), text: str = Form(...), logo: UploadFile = File(None)):
    """Добавляет новый отзыв."""
    if not is_admin_authenticated(request):
        return RedirectResponse('/admin/login', status_code=303)
    db = SessionReviews()
    logo_path = None
    if logo and getattr(logo, 'filename', None):
        logo_dir = 'static/uploads/review_logo'
        os.makedirs(logo_dir, exist_ok=True)
        logo_path_full = os.path.join(logo_dir, logo.filename)
        async with aiofiles.open(logo_path_full, 'wb') as out_file:
            content = await logo.read()
            await out_file.write(content)
        logo_path = f'/static/uploads/review_logo/{logo.filename}'
    item = Review(client_name=client_name, text=text, logo_path=logo_path)
    db.add(item)
    db.commit()
    db.close()
    return RedirectResponse('/admin/reviews', status_code=303)


@app.post('/admin/reviews/delete/{item_id}')
def delete_review(request: Request, item_id: int):
    """Удаляет отзыв."""
    if not is_admin_authenticated(request):
        return RedirectResponse('/admin/login', status_code=303)
    db = SessionReviews()
    item = db.query(Review).filter_by(id=item_id).first()
    if item:
        db.delete(item)
        db.commit()
    db.close()
    return RedirectResponse('/admin/reviews', status_code=303)

# --- Админка: Авторизация ---


@app.get('/admin/login', response_class=HTMLResponse)
def admin_login_get(request: Request):
    """Страница входа в админку."""
    if is_admin_authenticated(request):
        return RedirectResponse('/admin/portfolio', status_code=303)
    return templates.TemplateResponse('admin/login.html', {'request': request, 'error': None})


@app.post('/admin/login', response_class=HTMLResponse)
def admin_login_post(request: Request, login: str = Form(...), password: str = Form(...)):
    """Обрабатывает попытку входа в админку."""
    is_ok, error = authenticate_admin(login, password, request)
    if is_ok:
        response = RedirectResponse('/admin/portfolio', status_code=303)
        set_admin_session(response)
        return response

    return templates.TemplateResponse('admin/login.html', {'request': request, 'error': error})


@app.get('/admin/logout')
def admin_logout(request: Request):
    """Выход из админки."""
    response = RedirectResponse('/admin/login', status_code=303)
    logout_admin(response)
    return response

# --- Статические страницы ---


@app.get('/consent', response_class=HTMLResponse)
def consent_page(request: Request):
    """Страница "Согласие на обработку персональных данных"."""
    return templates.TemplateResponse('consent.html', {'request': request})


@app.get('/policy', response_class=HTMLResponse)
def policy_page(request: Request):
    """Страница "Политика в отношении обработки персональных данных"."""
    return templates.TemplateResponse('policy.html', {'request': request})

# --- Админка: Заявки КМ ---


@app.get('/admin/km_requests', response_class=HTMLResponse)
def admin_km_requests(request: Request, name: str = '', phone: str = '', email: str = '', km_link: str = '', date: str = '', processed: str = '', page: int = 1, per_page: int = 25):
    """Страница управления заявками КМ с фильтрацией и пагинацией (только для авторизованных админов)."""
    if not is_admin_authenticated(request):
        return RedirectResponse('/admin/login', status_code=303)
    db = SessionKmRequests()
    query = db.query(KmRequest)
    filters = {
        'name': name,
        'phone': phone,
        'email': email,
        'km_link': km_link,
        'date': date,
        'processed': processed
    }
    if name:
        query = query.filter(KmRequest.name.ilike(f'%{name}%'))
    if phone:
        query = query.filter(KmRequest.phone.ilike(f'%{phone}%'))
    if email:
        query = query.filter(KmRequest.email.ilike(f'%{email}%'))
    if km_link:
        query = query.filter(KmRequest.km_link.ilike(f'%{km_link}%'))
    if date:
        from datetime import datetime, timedelta
        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            next_day = date_obj + timedelta(days=1)
            query = query.filter(KmRequest.created_at >=
                                 date_obj, KmRequest.created_at < next_day)
        except Exception:
            pass
    if processed == '1':
        query = query.filter(KmRequest.processed == True)
    elif processed == '0':
        query = query.filter(KmRequest.processed == False)
    total = query.count()
    per_page = max(10, min(per_page, 100))
    pages = (total + per_page - 1) // per_page
    page = max(1, min(page, pages if pages else 1))
    items = query.order_by(KmRequest.id.desc()).offset(
        (page-1)*per_page).limit(per_page).all()
    db.close()
    return templates.TemplateResponse('admin/km_requests_manage.html', {
        'request': request,
        'items': items,
        'filters': filters,
        'page': page,
        'per_page': per_page,
        'pages': pages,
        'total': total
    })


@app.post('/admin/km_requests/delete/{item_id}')
def delete_km_request(request: Request, item_id: int):
    """Удаляет заявку КМ по id (только для авторизованных админов)."""
    if not is_admin_authenticated(request):
        return RedirectResponse('/admin/login', status_code=303)
    db = SessionKmRequests()
    item = db.query(KmRequest).filter_by(id=item_id).first()
    if item:
        db.delete(item)
        db.commit()
    db.close()
    return RedirectResponse('/admin/km_requests', status_code=303)


@app.post('/admin/km_requests/toggle_processed/{item_id}')
def toggle_km_request_processed(request: Request, item_id: int, processed: str = Form(None)):
    """Переключает статус 'Обработано' у заявки КМ (только для авторизованных админов)."""
    if not is_admin_authenticated(request):
        return RedirectResponse('/admin/login', status_code=303)
    db = SessionKmRequests()
    item = db.query(KmRequest).filter_by(id=item_id).first()
    if item:
        item.processed = bool(processed)
        db.commit()
    db.close()
    return RedirectResponse('/admin/km_requests', status_code=303)


@app.get('/admin/km_requests/export_csv')
def export_km_requests_csv(request: Request, name: str = '', phone: str = '', email: str = '', km_link: str = '', date: str = '', processed: str = ''):
    """Экспортирует заявки КМ в CSV с учётом фильтров (только для авторизованных админов)."""
    if not is_admin_authenticated(request):
        return RedirectResponse('/admin/login', status_code=303)
    db = SessionKmRequests()
    query = db.query(KmRequest)
    if name:
        query = query.filter(KmRequest.name.ilike(f'%{name}%'))
    if phone:
        query = query.filter(KmRequest.phone.ilike(f'%{phone}%'))
    if email:
        query = query.filter(KmRequest.email.ilike(f'%{email}%'))
    if km_link:
        query = query.filter(KmRequest.km_link.ilike(f'%{km_link}%'))
    if date:
        from datetime import datetime, timedelta
        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            next_day = date_obj + timedelta(days=1)
            query = query.filter(KmRequest.created_at >=
                                 date_obj, KmRequest.created_at < next_day)
        except Exception:
            pass
    if processed == '1':
        query = query.filter(KmRequest.processed == True)
    elif processed == '0':
        query = query.filter(KmRequest.processed == False)
    items = query.order_by(KmRequest.id.desc()).all()
    db.close()

    def generate():
        output = StringIO()
        output.write('\ufeff')  # BOM для UTF-8
        writer = csv.writer(output)
        writer.writerow(['ID', 'Имя', 'Телефон', 'Email',
                        'Ссылка на КМ', 'Дата', 'Обработано'])
        for req in items:
            writer.writerow([
                req.id,
                req.name,
                req.phone,
                req.email,
                req.km_link,
                req.created_at.strftime(
                    '%d.%m.%Y %H:%M') if req.created_at else '',
                'Да' if req.processed else 'Нет'
            ])
        output.seek(0)
        yield output.read()
    return StreamingResponse(generate(), media_type='text/csv', headers={"Content-Disposition": "attachment; filename=km_requests.csv"})

# TODO: добавить остальные маршруты, мультиязычность, обработку форм, email, портфолио, отзывы, калькулятор, попап, админку
