import sys
sys.path.insert(0, r'C:\projetos\gerador_atividades')

with open(r'C:\projetos\gerador_atividades\app.py', 'r', encoding='utf-8') as f:
    content = f.read()

start_marker = '# =========================\n# PLANEJAMENTO DOCENTE\n# =========================\n@app.route("/planejamento_docente", methods=["GET", "POST"])\ndef planejamento_docente():'
end_marker = '\n    return render_template("planejamento_docente.html")\n'

start_idx = content.find(start_marker)
end_idx = content.find(end_marker, start_idx) + len(end_marker)

nova_rota = '''# =========================
# PLANEJAMENTO DOCENTE
# =========================
@app.route("/planejamento_docente", methods=["GET", "POST"])
def planejamento_docente():

    if "usuario_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        nome_curso         = request.form["nome_curso"]
        unidade_curricular = request.form["unidade_curricular"]
        codigo_turma       = request.form.get("codigo_turma", "TEC.2026.1")
        modalidade         = request.form.get("modalidade", "HABILITAÇÃO TÉCNICA")
        unidade_escolar    = request.form.get("unidade_escolar", "")
        carga_horaria      = int(request.form["carga_horaria"])
        horas_por_dia      = int(request.form["horas_por_dia"])
        data_inicio_str    = request.form.get("data_inicio", "")
        data_fim_str       = request.form.get("data_fim", "")

        total_aulas = -(-carga_horaria // horas_por_dia)  # Divisão com teto

        print("=" * 60)
        print(f"📊 GERANDO PLANEJAMENTO DOCENTE")
        print(f"   Curso: {nome_curso} | UC: {unidade_curricular}")
        print(f"   CH: {carga_horaria}h | {horas_por_dia}h/dia | {total_aulas} aulas")
        print("=" * 60)

        pasta_upload = "uploads"
        os.makedirs(pasta_upload, exist_ok=True)

        # ----------------------------------------------------------
        # Lê o PDF do Plano de Curso
        # ----------------------------------------------------------
        arquivo_plano = request.files.get("arquivo_plano_pdf")
        texto_bruto = ""
        dados_plano = {
            "unidade_curricular": unidade_curricular,
            "objetivo_geral": "",
            "capacidades_tecnicas": [],
            "conhecimentos": [],
            "texto_bruto": ""
        }

        if arquivo_plano and arquivo_plano.filename:
            nome_plano = secure_filename(arquivo_plano.filename)
            caminho_plano = os.path.join(pasta_upload, nome_plano)
            arquivo_plano.save(caminho_plano)
            print(f"📄 Plano de Curso salvo: {caminho_plano}")
            try:
                dados_plano = estruturar_dados_plano_pdf(caminho_plano)
                dados_plano["unidade_curricular"] = dados_plano.get("unidade_curricular") or unidade_curricular
                texto_bruto = dados_plano.get("texto_bruto", "")
                print(f"✅ PDF lido: {len(dados_plano.get('conhecimentos', []))} conhecimentos extraídos")
            except Exception as e:
                print(f"⚠️ Erro ao ler PDF do plano: {e}")

        # ----------------------------------------------------------
        # Lê a Matriz SAEP (opcional)
        # ----------------------------------------------------------
        arquivo_matriz = request.files.get("arquivo_matriz")
        dados_matriz = []
        if arquivo_matriz and arquivo_matriz.filename:
            nome_matriz = secure_filename(arquivo_matriz.filename)
            caminho_matriz = os.path.join(pasta_upload, nome_matriz)
            arquivo_matriz.save(caminho_matriz)
            print(f"📋 Matriz SAEP salva: {caminho_matriz}")
            try:
                dados_matriz = ler_matriz_saep(caminho_matriz)
                print(f"✅ Matriz lida: {len(dados_matriz)} capacidades")
            except Exception as e:
                print(f"⚠️ Erro ao ler Matriz SAEP: {e}")

        # ----------------------------------------------------------
        # ETAPA 1: Gera o Excel do Planejamento Docente (com Bloom)
        # ----------------------------------------------------------
        datas = calcular_datas_aulas(data_inicio_str, total_aulas)

        aulas = gerar_planejamento_ia(
            dados_plano,
            dados_matriz,
            total_aulas,
            horas_por_dia,
            datas
        )

        dados_cabecalho = {
            "nome_curso":         nome_curso,
            "unidade_curricular": unidade_curricular,
            "codigo_turma":       codigo_turma,
            "modalidade":         modalidade,
            "unidade_escolar":    unidade_escolar,
            "carga_horaria":      carga_horaria,
            "horas_por_dia":      horas_por_dia,
            "data_inicio":        data_inicio_str,
            "data_fim":           data_fim_str,
            "instrutor":          session.get("nome", "")
        }

        os.makedirs("outputs", exist_ok=True)
        caminho_excel = gerar_excel_planejamento(dados_cabecalho, aulas)
        nome_arquivo_excel = os.path.basename(caminho_excel)
        print(f"✅ Excel do Planejamento Docente gerado: {caminho_excel}")

        # ----------------------------------------------------------
        # ETAPA 2: Cria entrada em cursos_plano para hospedar os
        #          planos de aula vinculados a este planejamento
        # ----------------------------------------------------------
        conn, cursor = get_cursor()
        try:
            cursor.execute(
                """
                INSERT INTO cursos_plano (
                    nome_curso,
                    carga_horaria,
                    aulas_por_dia,
                    usuario_id
                )
                VALUES (%s,%s,%s,%s)
                RETURNING id
                """,
                (
                    f"{nome_curso} — {unidade_curricular}",
                    carga_horaria,
                    horas_por_dia,
                    session["usuario_id"]
                )
            )
            curso_id = cursor.fetchone()[0]
            conn.commit()
        finally:
            release_cursor(conn, cursor)

        print(f"📚 Curso vinculado criado: ID {curso_id}")

        # ----------------------------------------------------------
        # ETAPA 3: Salva o Planejamento Docente no banco, vinculado
        #          ao curso criado
        # ----------------------------------------------------------
        conn, cursor = get_cursor()
        try:
            cursor.execute(
                """
                INSERT INTO planejamentos_docente (
                    nome_curso,
                    unidade_curricular,
                    turma,
                    unidade_escolar,
                    carga_horaria,
                    horas_por_dia,
                    data_inicio,
                    data_fim,
                    total_aulas,
                    arquivo_excel,
                    usuario_id,
                    curso_id
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
                """,
                (
                    nome_curso,
                    unidade_curricular,
                    codigo_turma,
                    unidade_escolar,
                    carga_horaria,
                    horas_por_dia,
                    data_inicio_str or None,
                    data_fim_str or None,
                    total_aulas,
                    nome_arquivo_excel,
                    session["usuario_id"],
                    curso_id
                )
            )
            planejamento_id = cursor.fetchone()[0]
            conn.commit()
        finally:
            release_cursor(conn, cursor)

        print(f"✅ Planejamento Docente salvo: ID {planejamento_id}")

        # ----------------------------------------------------------
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
        )

        conn, cursor = get_cursor()
        try:
            for dia, plano_texto in enumerate(planos_gerados, start=1):
                cursor.execute(
                    """
                    INSERT INTO planos_aula (
                        curso_id,
                        dia,
                        tema,
                        plano_gerado,
                        usuario_id,
                        planejamento_id
                    )
                    VALUES (%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        curso_id,
                        dia,
                        f"Plano Dia {dia} — {unidade_curricular}",
                        plano_texto,
                        session["usuario_id"],
                        planejamento_id
                    )
                )
            conn.commit()
        finally:
            release_cursor(conn, cursor)

        print(f"✅ {total_aulas} Planos de Aula gerados e salvos!")
        print("=" * 60)

        # Redireciona para a página do curso com todos os planos gerados
        return redirect(f"/curso/{curso_id}")

    return render_template("planejamento_docente.html")
'''

new_content = content[:start_idx] + nova_rota + content[end_idx:]

with open(r'C:\projetos\gerador_atividades\app.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f"Função reescrita! ({end_idx - start_idx} chars substituídos por {len(nova_rota)} chars)")
