from sqlalchemy import create_engine, Column, Integer, String, Text, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from datetime import datetime

DATABASE_URL = os.getenv("External_Database_URL")  # Ex: 'postgresql://user:password@host:port/dbname'
engine = create_engine(DATABASE_URL)
Base = declarative_base()

class ChatHistory(Base):
    __tablename__ = "chat_history"
    __table_args__ = {"schema": "chatapp"}  # Schema customizado

    id = Column(Integer, primary_key=True)
    user_id = Column(String(64))
    pergunta = Column(Text)
    resposta = Column(Text)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

Session = sessionmaker(bind=engine)

def criar_tabelas():
    Base.metadata.create_all(engine)

def salvar_chat(user_id, pergunta, resposta):
    session = Session()
    novo = ChatHistory(user_id=user_id, pergunta=pergunta, resposta=resposta)
    session.add(novo)
    session.commit()
    session.close()

def buscar_historico(user_id, limit=20):
    session = Session()
    historico = session.query(ChatHistory).filter_by(user_id=user_id).order_by(ChatHistory.created_at.desc()).limit(limit).all()
    session.close()
    return historico
