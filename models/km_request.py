"""
Модель SQLAlchemy для хранения заявок из формы КМ.
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class KmRequest(Base):
    """
    Представляет заявку, отправленную через модальное окно КМ.
    """
    __tablename__ = 'km_requests'

    id = Column(Integer, primary_key=True, comment="Уникальный идентификатор")
    name = Column(String, nullable=False, comment="Имя клиента")
    phone = Column(String, nullable=False, comment="Телефон клиента")
    email = Column(String, nullable=False, comment="Почта клиента")
    km_link = Column(String, comment="Ссылка на КМ")
    created_at = Column(DateTime, default=datetime.utcnow,
                        comment="Дата и время создания заявки")
    processed = Column(Boolean, default=False,
                       nullable=False, comment="Обработано")
