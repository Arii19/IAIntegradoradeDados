import os
from sqlalchemy import create_engine

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

def salvar_chat(user_id, pergunta, resposta):
    with engine.connect() as conn:
        conn.execute(
            "INSERT INTO chat_history (user_id, pergunta, resposta) VALUES (:user_id, :pergunta, :resposta)",
            {"user_id": user_id, "pergunta": pergunta, "resposta": resposta}
        )
        conn.commit()

def buscar_historico(user_id, limit=20):
    with engine.connect() as conn:
        result = conn.execute(
            "SELECT pergunta, resposta, created_at FROM chat_history WHERE user_id=:user_id ORDER BY created_at DESC LIMIT :limit",
            {"user_id": user_id, "limit": limit}
        )
        rows = result.fetchall()
    return rows
