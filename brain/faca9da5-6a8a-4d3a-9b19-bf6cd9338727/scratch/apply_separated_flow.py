import sys
sys.path.insert(0, r'C:\projetos\gerador_atividades')

with open(r'C:\projetos\gerador_atividades\app.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Import do leitor de planejamento docente
if "ler_excel_planejamento_docente" not in code:
    code = code.replace(
        "from utils.matriz_saep_reader import ler_matriz_saep",
        "from utils.matriz_saep_reader import ler_matriz_saep\nfrom utils.planejamento_docente_reader import ler_excel_planejamento_docente"
    )

# 2. Ajusta planejamento_docente para APENAS gerar o planejamento e entregar o download do Excel
# Encontra a rota planejamento_docente
start_pd = code.find('@app.route("/planejamento_docente", methods=["GET", "POST"])')
end_pd = code.find('# =========================\n# LISTAR PLANEJAMENTOS DOCENTES', start_pd)

nova_funcao_pd = '''@app.route("/planejamento_docente", methods=["GET", "POST"])
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
        # 1. Lê o PDF do Plano de Curso
        # ----------------------------------------------------------
        arquivo_plano = request.files.get("arquivo_plano_pdf")
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
                print(f"✅ PDF lido: {len(dados_plano.get('conhecimentos', []))} conhecimentos extraídos")
            except Exception as e:
                print(f"⚠️ Erro ao ler PDF do plano: {e}")

        # ----------------------------------------------------------
        # 2. Lê a Matriz SAEP (opcional)
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
        # 3. Gera o Planejamento Docente (Taxonomia de Bloom)
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
        print(f"✅ Excel do Planejamento Docente gerado com sucesso: {caminho_excel}")

        # ----------------------------------------------------------
        # 4. Salva o Planejamento Docente no banco de dados
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
                    usuario_id
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
                    session["usuario_id"]
                )
            )
            planejamento_id = cursor.fetchone()[0]
            conn.commit()
        finally:
            release_cursor(conn, cursor)

        print(f"✅ Planejamento Docente salvo no banco: ID #{planejamento_id}")
        print(f"📥 Disponibilizando arquivo Excel para download imediato...")
        print("=" * 60)

        # Entrega o arquivo Excel diretamente para download do usuário
        return send_file(
            caminho_excel,
            as_attachment=True,
            download_name=nome_arquivo_excel
        )

    return render_template("planejamento_docente.html")


'''

code = code[:start_pd] + nova_funcao_pd + code[end_pd:]
print("planejamento_docente atualizado para apenas gerar e entregar o Excel!")

# 3. Agora atualiza a rota /planos para aceitar o Excel do Planejamento Docente ou PDF/Excel
start_planos = code.find('@app.route("/planos", methods=["GET", "POST"])')
end_planos = code.find('# =========================\n# LISTAR PLANOS', start_planos)

nova_funcao_planos = '''@app.route("/planos", methods=["GET", "POST"])
def planos():

    if "usuario_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        nome_curso = request.form.get("nome_curso", "").strip()
        carga_horaria_form = request.form.get("carga_horaria")
        aulas_por_dia_form = request.form.get("aulas_por_dia")

        carga_horaria = int(carga_horaria_form) if carga_horaria_form else 0
        aulas_por_dia = int(aulas_por_dia_form) if aulas_por_dia_form else 4

        arquivo = request.files["arquivo_pdf"]
        nome_arquivo = secure_filename(arquivo.filename)

        pasta_upload = "uploads"
        os.makedirs(pasta_upload, exist_ok=True)

        caminho = os.path.join(pasta_upload, nome_arquivo)
        arquivo.save(caminho)

        is_excel = nome_arquivo.lower().endswith((".xlsx", ".xls"))

        print("=" * 60)
        print(f"📚 PROCESSANDO ARQUIVO PARA GERAR PLANOS DE AULA")
        print(f"   Arquivo: {nome_arquivo} (Excel: {is_excel})")
        print("=" * 60)

        planos = []
        curso_id = None
        total_dias = 0

        # Verifica se é um arquivo Excel de Planejamento Docente
        if is_excel:
            try:
                dados_cabecalho, aulas_excel = ler_excel_planejamento_docente(caminho)
                if aulas_excel and len(aulas_excel) > 0:
                    print(f"📊 Arquivo reconhecido como Planejamento Docente ({len(aulas_excel)} aulas identificadas)!")
                    if not nome_curso and dados_cabecalho.get("nome_curso"):
                        nome_curso = dados_cabecalho["nome_curso"]
                    if dados_cabecalho.get("unidade_curricular"):
                        if nome_curso:
                            nome_curso = f"{nome_curso} — {dados_cabecalho['unidade_curricular']}"
                        else:
                            nome_curso = dados_cabecalho["unidade_curricular"]

                    if carga_horaria <= 0:
                        carga_horaria = dados_cabecalho.get("carga_horaria", 40)
                    if aulas_por_dia <= 0:
                        aulas_por_dia = dados_cabecalho.get("horas_por_dia", 4)

                    total_dias = len(aulas_excel)

                    # Cria o curso
                    conn, cursor = get_cursor()
                    try:
                        cursor.execute(
                            """
                            INSERT INTO cursos_plano (nome_curso, carga_horaria, aulas_por_dia, usuario_id)
                            VALUES (%s, %s, %s, %s)
                            RETURNING id
                            """,
                            (nome_curso or "Curso Planejado", carga_horaria, aulas_por_dia, session["usuario_id"])
                        )
                        curso_id = cursor.fetchone()[0]
                        conn.commit()
                    finally:
                        release_cursor(conn, cursor)

                    # Gera planos de aula a partir das aulas estruturadas no Excel do planejamento
                    planos = gerar_todos_planos_de_planejamento(
                        aulas_excel,
                        nome_curso,
                        dados_cabecalho.get("unidade_curricular", ""),
                        aulas_por_dia,
                        max_workers=2
                    )

            except Exception as e:
                print(f"Aviso ao ler como Planejamento Docente: {e}. Tentando fluxo padrão...")

        # Fluxo alternativo: Matriz SAEP ou PDF de Plano de Curso
        if not planos:
            if is_excel:
                print("📊 Extraindo dados de Matriz de Referência...")
                dados_excel = extrair_dados_excel(caminho)
                texto = formatar_dados_para_prompt(dados_excel)
            else:
                print("📄 Extraindo texto do PDF...")
                reader = PdfReader(caminho)
                texto = ""
                for pagina in reader.pages:
                    conteudo = pagina.extract_text()
                    if conteudo:
                        texto += conteudo + "\\n"

            if carga_horaria <= 0:
                carga_horaria = 40
            if aulas_por_dia <= 0:
                aulas_por_dia = 4

            total_dias = max(1, carga_horaria // aulas_por_dia)

            conn, cursor = get_cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO cursos_plano (nome_curso, carga_horaria, aulas_por_dia, usuario_id)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (nome_curso or "Curso Sem Nome", carga_horaria, aulas_por_dia, session["usuario_id"])
                )
                curso_id = cursor.fetchone()[0]
                conn.commit()
            finally:
                release_cursor(conn, cursor)

            planos = gerar_todos_planos(texto, carga_horaria, aulas_por_dia, total_dias, max_workers=2)

        # Salva os planos no banco
        planos_completos = ""
        conn, cursor = get_cursor()
        try:
            for dia, plano in enumerate(planos, start=1):
                planos_completos += f"\\n\\nDIA {dia}\\n\\n{plano}"
                cursor.execute(
                    """
                    INSERT INTO planos_aula (curso_id, dia, tema, plano_gerado, usuario_id)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (curso_id, dia, f"Plano Dia {dia}", plano, session["usuario_id"])
                )
            conn.commit()
        finally:
            release_cursor(conn, cursor)

        # Gera o DOCX consolidado do curso
        os.makedirs("outputs", exist_ok=True)
        arquivo_docx = f"outputs/plano_{curso_id}.docx"
        arquivo_pdf = f"outputs/plano_{curso_id}.pdf"

        gerar_docx_plano(
            titulo="PLANO DE AULA",
            subtitulo=f"Curso: {nome_curso}",
            conteudo=planos_completos,
            caminho_saida=arquivo_docx
        )
        gerar_pdf_plano(arquivo_docx, arquivo_pdf)

        print(f"✅ {len(planos)} Planos de aula gerados para o Curso #{curso_id}!")
        print("=" * 60)

        # Redireciona para o curso onde cada plano tem o botão individual para gerar atividade
        return redirect(f"/curso/{curso_id}")

    return render_template("planos.html")


'''

code = code[:start_planos] + nova_funcao_planos + code[end_planos:]
print("Rota /planos atualizada para suportar Excel do Planejamento Docente e criar os planos!")

# 4. Ajusta rota gerar_planos_planejamento para ler o Excel do planejamento gravado
start_gpp = code.find('@app.route("/gerar_planos_planejamento/<int:planejamento_id>")')
if start_gpp != -1:
    end_gpp = code.find('# =========================\n# START', start_gpp)
    nova_funcao_gpp = '''@app.route("/gerar_planos_planejamento/<int:planejamento_id>")
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

    # Se já tem planos gerados e curso_id vinculado, vai direto para o curso
    if curso_id:
        conn, cursor = get_cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM planos_aula WHERE curso_id = %s", (curso_id,))
            qtd = cursor.fetchone()[0]
            if qtd > 0:
                return redirect(f"/curso/{curso_id}")
        finally:
            release_cursor(conn, cursor)

    nome_curso = plan[1]
    uc = plan[2]
    ch = plan[5]
    hd = plan[6]
    nome_arquivo_excel = plan[10]

    caminho_excel = os.path.join("outputs", nome_arquivo_excel) if nome_arquivo_excel else ""

    aulas_excel = []
    if caminho_excel and os.path.exists(caminho_excel):
        try:
            _, aulas_excel = ler_excel_planejamento_docente(caminho_excel)
        except Exception as e:
            print(f"Erro ao ler Excel do planejamento: {e}")

    # Cria o curso
    conn, cursor = get_cursor()
    try:
        cursor.execute(
            """
            INSERT INTO cursos_plano (nome_curso, carga_horaria, aulas_por_dia, usuario_id)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
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

    if not aulas_excel:
        datas = calcular_datas_aulas(str(plan[7]) if plan[7] else None, plan[9])
        dados_plano = {"unidade_curricular": uc, "conhecimentos": []}
        aulas_excel = gerar_planejamento_ia(dados_plano, [], plan[9], hd, datas)

    planos_gerados = gerar_todos_planos_de_planejamento(aulas_excel, nome_curso, uc, hd, max_workers=2)

    conn, cursor = get_cursor()
    try:
        for dia, plano_texto in enumerate(planos_gerados, start=1):
            cursor.execute(
                """
                INSERT INTO planos_aula (curso_id, dia, tema, plano_gerado, usuario_id, planejamento_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (curso_id, dia, f"Plano Dia {dia} — {uc}", plano_texto, session["usuario_id"], planejamento_id)
            )
        conn.commit()
    finally:
        release_cursor(conn, cursor)

    return redirect(f"/curso/{curso_id}")


'''
    code = code[:start_gpp] + nova_funcao_gpp + code[end_gpp:]
    print("Rota gerar_planos_planejamento atualizada!")

with open(r'C:\projetos\gerador_atividades\app.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Todas as atualizações no app.py concluídas com sucesso!")
