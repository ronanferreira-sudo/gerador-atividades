import sys
sys.path.insert(0, r'C:\projetos\gerador_atividades')

from database.conexao import get_cursor, release_cursor

conn, cursor = get_cursor()

cursor.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_name='planejamentos_docente' ORDER BY ordinal_position"
)
cols = cursor.fetchall()
print('Colunas planejamentos_docente:', [c[0] for c in cols])

cursor.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_name='planos_aula' ORDER BY ordinal_position"
)
cols2 = cursor.fetchall()
print('Colunas planos_aula:', [c[0] for c in cols2])

release_cursor(conn, cursor)
