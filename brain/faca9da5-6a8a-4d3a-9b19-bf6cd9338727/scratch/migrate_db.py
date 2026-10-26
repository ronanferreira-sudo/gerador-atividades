import sys
sys.path.insert(0, r'C:\projetos\gerador_atividades')

from database.conexao import get_cursor, release_cursor

conn, cursor = get_cursor()

# Adiciona planejamento_id em planos_aula (FK opcional para planejamentos_docente)
cursor.execute("""
    ALTER TABLE planos_aula
    ADD COLUMN IF NOT EXISTS planejamento_id INTEGER REFERENCES planejamentos_docente(id) ON DELETE SET NULL
""")

# Adiciona curso_id em planejamentos_docente (FK para cursos_plano)
cursor.execute("""
    ALTER TABLE planejamentos_docente
    ADD COLUMN IF NOT EXISTS curso_id INTEGER REFERENCES cursos_plano(id) ON DELETE SET NULL
""")

conn.commit()
release_cursor(conn, cursor)
print("Colunas adicionadas com sucesso!")
