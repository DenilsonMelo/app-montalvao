from datetime import date, timedelta
from sqlalchemy.orm import Session
from db import engine, SessionLocal, Base
from models import User, Bucket, Giant, Bill

print("Criando tabelas...")
Base.metadata.create_all(bind=engine)
db: Session = SessionLocal()

# Limpa e popula
db.query(Bill).delete()
db.query(Giant).delete()
db.query(Bucket).delete()
db.query(User).delete()
db.commit()

u = User(name="Gustavo")
db.add(u); db.commit(); db.refresh(u)

buckets = [
    Bucket(user_id=u.id, name="Dízimo", description="", percent=10, type="dizimo", balance=0),
    Bucket(user_id=u.id, name="Operacional", description="Empresas", percent=50, type="operacional", balance=0),
    Bucket(user_id=u.id, name="Empréstimos", description="", percent=20, type="emprestimo", balance=0),
    Bucket(user_id=u.id, name="Cartões", description="", percent=15, type="cartao", balance=0),
    Bucket(user_id=u.id, name="Ataque/Colchão", description="", percent=5, type="ataque", balance=0),
]
db.add_all(buckets); db.commit()

g1 = Giant(user_id=u.id, name="Cartão C6", total_to_pay=3500, parcels=6, months_left=6, priority=1, status="active")
g2 = Giant(user_id=u.id, name="Empréstimo Banco", total_to_pay=12000, parcels=12, months_left=12, priority=2, status="active")
db.add_all([g1, g2]); db.commit()

today = date.today()
b1 = Bill(user_id=u.id, title="Cartão C6 - Fatura", amount=850.0, due_date=today + timedelta(days=5), is_critical=True)
b2 = Bill(user_id=u.id, title="Consórcio", amount=420.0, due_date=today - timedelta(days=2), is_critical=True)
b3 = Bill(user_id=u.id, title="Internet", amount=120.0, due_date=today + timedelta(days=1), is_critical=False)
db.add_all([b1, b2, b3]); db.commit()

print("OK. Usuário criado:", u.name)
db.close()
