"""
Модель SQLAlchemy для хранения проектов портфолио.
"""
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Portfolio(Base):
    """
    Представляет один проект в портфолио.
    """
    __tablename__ = 'portfolio'

    id = Column(Integer, primary_key=True, comment="Уникальный идентификатор")
    title = Column(String, nullable=False, comment="Название проекта")
    description = Column(Text, comment="Подробное описание проекта")
    # Поле category оставлено для возможного будущего использования
    category = Column(
        String, comment="Категория проекта (например, 'Мосты', 'Здания')")
    image_path = Column(
        String, comment="Путь к основному изображению (для превью)")
    image_paths = Column(
        Text, comment="JSON-строка со списком путей ко всем изображениям проекта")
    created_at = Column(DateTime, default=datetime.utcnow,
                        comment="Дата и время создания записи")
