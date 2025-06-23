"""
Модель SQLAlchemy для хранения email-адресов, полученных через всплывающую форму.
"""
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class PopupEmail(Base):
    """
    Представляет email-адрес, сохраненный из всплывающей формы на сайте.
    """
    __tablename__ = 'popup_emails'

    id = Column(Integer, primary_key=True, comment="Уникальный идентификатор")
    email = Column(String, unique=True, nullable=False,
                   comment="Email-адрес подписчика")
    created_at = Column(DateTime, default=datetime.utcnow,
                        comment="Дата и время создания записи")
