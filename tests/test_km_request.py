import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.km_request import Base, KmRequest


@pytest.fixture
def session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_create_km_request(session):
    km = KmRequest(name='Иван', phone='1234567890',
                   email='ivan@example.com', km_link='http://example.com')
    session.add(km)
    session.commit()
    result = session.query(KmRequest).first()
    assert result is not None
    assert result.name == 'Иван'
    assert result.phone == '1234567890'
    assert result.email == 'ivan@example.com'
    assert result.km_link == 'http://example.com'
    assert result.processed is False
