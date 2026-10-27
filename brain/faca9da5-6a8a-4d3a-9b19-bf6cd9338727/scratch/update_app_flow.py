import sys
sys.path.insert(0, r'C:\projetos\gerador_atividades')

with open(r'C:\projetos\gerador_atividades\app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Atualiza imports se necessário
if "gerar_todos_planos_de_planejamento" not in content:
    content = content.replace(
        "from ia.plano_aula import gerar_todos_planos, gerar_plano_aula",
        "from ia.plano_aula import gerar_todos_planos, gerar_plano_aula, gerar_todos_planos_de_planejamento"
    )

# 2. Atualiza a chamada em planejamento_docente para usar gerar_todos_planos_de_planejamento
antigo_bloco_planos = """        # ----------------------------------------------------------
        # ETAPA 4: Gera os Planos de Aula a partir do Planejamento
        #          Docente (texto do PDF → IA → planos_aula)
        # ----------------------------------------------------------
        print(f"📅 Gerando {total_aulas} Planos de Aula a partir do Planejamento Docente...")

        texto_para_planos = texto_bruto or "\\n".join(
            dados_plano.get("conhecimentos", [])
        ) or f"{nome_curso} — {unidade_curricular}"

        planos_gerados = gerar_todos_planos(
            texto_para_planos,
            carga_horaria,
            horas_por_dia,
            total_aulas,
            max_workers=2
        )"""

novo_bloco_planos = """        # ----------------------------------------------------------
        # ETAPA 4: Gera os Planos de Aula a partir do Planejamento
        #          Docente (usando os dados ricos de cada aula + Bloom)
        # ----------------------------------------------------------
        print(f"📅 Gerando {total_aulas} Planos de Aula DIRETAMENTE a partir do Planejamento Docente...")

        planos_gerados = gerar_todos_planos_de_planejamento(
            aulas,
            nome_curso,
            unidade_curricular,
            horas_por_dia,
            max_workers=2
        )"""

if antigo_bloco_planos in content:
    content = content.replace(antigo_bloco_planos, novo_bloco_planos)
    print("Bloco de geração de planos atualizado para usar os dados do Planejamento Docente!")
else:
    print("Aviso: Trecho exato de planos_gerados não encontrado, buscando alternativo...")
    # Tenta substituição mais flexível
    idx1 = content.find("ETAPA 4: Gera os Planos de Aula a partir do Planejamento")
    if idx1 != -1:
        idx2 = content.find("conn, cursor = get_cursor()", idx1)
        if idx2 != -1:
            trecho_velho = content[idx1:idx2]
            content = content.replace(trecho_velho, novo_bloco_planos + "\n\n        ")
            print("Substituição flexível realizada com sucesso!")

# 3. Adiciona rota auxiliar para gerar planos a partir de um planejamento existente se não tiver planos
rota_gerar_planos_existente = """

# =========================
# GERAR PLANOS DE UM PLANEJAMENTO EXISTENTE
# =========================
@app.route("/gerar_planos_planejamento/<int:planejamento_id>")
def gerar_planos_planejamento(planejamento_id):

    if "usuario_id" not in session:
        return redirect("/login")

    conn, cursor = get_cursor()
    try:
        cursor.execute(
            "SELECT * FROM planejamentos_docente WHERE id = %s",
            (planejamento_id,)
        )
        plan = cursor.fetchone()
    finally:
        release_cursor(conn, cursor)

    if not plan:
        return "Planejamento não encontrado", 404

    curso_id = plan[13] if len(plan) > 13 else None

    # Se já tem curso_id e planos associados, vai direto pro curso
    if curso_id:
        return redirect(f"/curso/{curso_id}")

    # Cria curso_id
    nome_curso = plan[1]
    uc = plan[2]
    ch = plan[5]
    hd = plan[6]
    total_aulas = plan[9]

    conn, cursor = get_cursor()
    try:
        cursor.execute(
            \"\"\"
            INSERT INTO cursos_plano (nome_curso, carga_horaria, aulas_por_dia, usuario_id)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            \"\"\",
            (f"{nome_curso} — {uc}", ch, hd, session["usuario_id"])
        )
        curso_id = cursor.fetchone()[0]

        cursor.execute(
            "UPDATE planejamentos_docente SET curso_id = %s WHERE id = %s",
            (curso_id, planejamento_id)
        )
        conn.commit()
    finally:
        release_cursor(conn, cursor)

    # Gera planos básicos a partir do planejamento
    datas = calcular_datas_aulas(str(plan[7]) if plan[7] else None, total_aulas)
    dados_plano = {"unidade_curricular": uc, "conhecimentos": []}
    aulas = gerar_planejamento_ia(dados_plano, [], total_aulas, hd, datas)
    planos_gerados = gerar_todos_planos_de_planejamento(aulas, nome_curso, uc, hd, max_workers=2)

    conn, cursor = get_cursor()
    try:
        for dia, plano_texto in enumerate(planos_gerados, start=1):
            cursor.execute(
                \"\"\"
                INSERT INTO planos_aula (curso_id, dia, tema, plano_gerado, usuario_id, planejamento_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                \"\"\",
                (curso_id, dia, f"Plano Dia {dia} — {uc}", plano_texto, session["usuario_id"], planejamento_id)
            )
        conn.commit()
    finally:
        release_cursor(conn, cursor)

    return redirect(f"/curso/{curso_id}")
"""

if "def gerar_planos_planejamento" not in content:
    ancora = "# =========================\n# START"
    content = content.replace(ancora, rota_gerar_planos_existente + "\n" + ancora)
    print("Rota /gerar_planos_planejamento adicionada com sucesso!")

with open(r'C:\projetos\gerador_atividades\app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("app.py atualizado!")
