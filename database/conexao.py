import os
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env (na raiz do projeto)
load_dotenv()

# Pool de conexões para suportar múltiplos usuários simultâneos
# Configuração via .env — sem credenciais fixas no código
conexao_pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=2,
    maxconn=20,  # Aumentado para suportar mais professores simultâneos
    host=os.getenv("DB_HOST", "127.0.0.1"),
    port=os.getenv("DB_PORT", "5432"),
    dbname=os.getenv("DB_NAME", "gerador_atividades"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "123")
)


def get_cursor():
    """Retorna uma conexão e cursor do pool thread-safe"""
    conn = conexao_pool.getconn()
    conn.autocommit = True
    cursor = conn.cursor()
    return conn, cursor


def release_cursor(conn, cursor):
    """Devolve a conexão ao pool"""
    if cursor:
        cursor.close()
    if conn:
        conexao_pool.putconn(conn)
