"""
Модель SQLAlchemy для хранения отзывов клиентов.
"""
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Review(Base):
    """
    Представляет один отзыв клиента.
    """
    __tablename__ = 'reviews'

    id = Column(Integer, primary_key=True, comment="Уникальный идентификатор")
    client_name = Column(String, nullable=False,
                         comment="Имя клиента или название компании")
    text = Column(Text, nullable=False, comment="Текст отзыва")
    logo_path = Column(
        String, comment="Путь к файлу логотипа клиента (опционально)")
    created_at = Column(DateTime, default=datetime.utcnow,
                        comment="Дата и время создания записи")
