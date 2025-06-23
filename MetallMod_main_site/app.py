"""
Основной файл приложения FastAPI для сайта "МеталлМод".
Обрабатывает все маршруты, управляет базой данных и рендерингом шаблонов.
"""

from fastapi import FastAPI, Request, Form, UploadFile, File, Query, Depends, Body
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import json
from pathlib import Path
from utils.email_utils import send_calc_form_email
import aiofiles
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.popup_email import Base, PopupEmail
from email_validator import validate_email, EmailNotValidError
from models.portfolio import Base as PortfolioBase, Portfolio
from models.review import Base as ReviewBase, Review
from utils.auth_utils import authenticate_admin, set_admin_session, is_admin_authenticated, logout_admin

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

# Инициализация SQLite
DB_URL = 'sqlite:///popup_emails.db'
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})

# Создание таблиц, если они не существуют
Base.metadata.create_all(engine)
PortfolioBase.metadata.create_all(engine)
ReviewBase.metadata.create_all(engine)

SessionLocal = sessionmaker(bind=engine)

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

    db = SessionLocal()
    try:
        portfolio_items = db.query(Portfolio).order_by(
            Portfolio.id.desc()).all()
        reviews = db.query(Review).order_by(Review.id.desc()).all()
    finally:
        db.close()

    return templates.TemplateResponse('index.html', {
        'request': request,
        'lang': lang,
        '_': translate,
        'title': 'МеталлМод',
        'portfolio_items': portfolio_items,
        'reviews': reviews
    })


@app.post('/send-calc-form')
async def send_calc_form(name: str = Form(...), phone: str = Form(...), file: UploadFile = File(...)):
    """
    Принимает данные из формы калькулятора, сохраняет файл и отправляет email.
    """
    save_dir = 'static/uploads'
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(save_dir, file.filename)

    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)

    file_url = f'/static/uploads/{file.filename}'
    await send_calc_form_email(name, phone, content, file.filename, file_url=file_url)

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

    db = SessionLocal()
    try:
        if db.query(PopupEmail).filter_by(email=email).first():
            return JSONResponse({'success': True, 'message': 'Email уже сохранён'})

        new_popup_email = PopupEmail(email=email)
        db.add(new_popup_email)
        db.commit()
    finally:
        db.close()

    return JSONResponse({'success': True, 'message': 'Email сохранён'})

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

    db = SessionLocal()
    try:
        items = db.query(Portfolio).order_by(Portfolio.id.desc()).all()
    finally:
        db.close()

    return templates.TemplateResponse('admin/portfolio_manage.html', {'request': request, 'items': items})


@app.post('/admin/portfolio/add')
async def add_portfolio(request: Request, title: str = Form(...), description: str = Form(...), images: list = File(None)):
    """Добавляет новый проект в портфолио."""
    if not is_admin_authenticated(request):
        return RedirectResponse('/admin/login', status_code=303)
    db = SessionLocal()
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
    db = SessionLocal()
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
    db = SessionLocal()
    item = db.query(Portfolio).filter_by(id=item_id).first()
    if not item:
        db.close()
        return JSONResponse({'success': False, 'message': 'Проект не найден'})
    item.image_paths = json.dumps(images)
    item.image_path = images[0] if images else None
    db.commit()
    db.close()
    return JSONResponse({'success': True})

# --- Админка: Отзывы ---


@app.get('/admin/reviews', response_class=HTMLResponse)
def admin_reviews(request: Request):
    """Страница управления отзывами (только для авторизованных админов)."""
    if not is_admin_authenticated(request):
        return RedirectResponse('/admin/login', status_code=303)
    db = SessionLocal()
    items = db.query(Review).order_by(Review.id.desc()).all()
    db.close()
    return templates.TemplateResponse('admin/reviews_manage.html', {'request': request, 'items': items})


@app.post('/admin/reviews/add')
async def add_review(request: Request, client_name: str = Form(...), text: str = Form(...), logo: UploadFile = File(None)):
    """Добавляет новый отзыв."""
    if not is_admin_authenticated(request):
        return RedirectResponse('/admin/login', status_code=303)
    db = SessionLocal()
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
    db = SessionLocal()
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

# TODO: добавить остальные маршруты, мультиязычность, обработку форм, email, портфолио, отзывы, калькулятор, попап, админку
