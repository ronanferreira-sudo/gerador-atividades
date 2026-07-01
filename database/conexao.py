import psycopg2
from psycopg2 import pool

# Pool de conexões para suportar múltiplos usuários simultâneos
conexao_pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=2,
    maxconn=10,
    host="127.0.0.1",
    port="5432",
    dbname="gerador_atividades",
    user="postgres",
    password="123"
)


def get_cursor():
    """Retorna uma conexão e cursor do pool (use com 'with')"""
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