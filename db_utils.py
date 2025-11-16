import psycopg2
import os
from contextlib import contextmanager

@contextmanager
def get_connection():
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    try:
        yield conn
    finally:
        conn.close()

def salvar_chat(user_id, pergunta, resposta):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_history (user_id, pergunta, resposta) VALUES (%s, %s, %s)",
                (user_id, pergunta, resposta)
            )
            conn.commit()

def buscar_historico(user_id, limit=20):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pergunta, resposta, created_at FROM chat_history WHERE user_id=%s ORDER BY created_at DESC LIMIT %s",
                (user_id, limit)
            )
            rows = cur.fetchall()
    return rows
