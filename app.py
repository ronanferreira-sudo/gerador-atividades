from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    send_file,
    jsonify,
    flash
)

from werkzeug.utils import secure_filename

from PyPDF2 import PdfReader

from database.conexao import get_cursor, release_cursor

from ia.gerador import gerar_atividade
from utils.repositorio_service import (
    buscar_questoes_repositorio,
    contar_questoes_repositorio,
    formatar_questoes_para_atividade,
    compor_atividade_hibrida,
    salvar_questoes_ia_no_repositorio,
    adicionar_ao_repositorio,
    atualizar_no_repositorio,
    deletar_do_repositorio,
    obter_item_repositorio,
)
from ia.plano_aula import gerar_todos_planos, gerar_plano_aula, gerar_todos_planos_de_planejamento
from ia.planejamento_bloom import gerar_planejamento_ia, calcular_datas_aulas

from utils.docx_generator import gerar_docx_plano
from utils.pdf_generator import gerar_pdf_plano

from utils.docx_atividade_generator import gerar_docx_atividade
from utils.pdf_atividade_generator import gerar_pdf_atividade

from utils.excel_planejamento_generator import gerar_excel_planejamento
from utils.pdf_plano_reader import estruturar_dados_plano_pdf
from utils.matriz_saep_reader import ler_matriz_saep
from utils.planejamento_docente_reader import ler_excel_planejamento_docente

from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.excel_reader import extrair_dados_excel, formatar_dados_para_prompt, contar_itens
from utils.security import (
    gerar_hash_senha,
    verificar_senha,
    atualizar_senha_para_hash_se_necessario,
    redefinir_senha_usuario,
    redefinir_senha_por_email,
)
import os
import re


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "gerador_atividades_2026")
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


def pode_acessar_atividade(id, usuario_id, perfil):

    if perfil == "admin":
        return True

    conn, cursor = get_cursor()
    try:
        cursor.execute(
            """
            SELECT usuario_id
            FROM atividades
            WHERE id = %s
        """,
            (id,),
        )

        atividade = cursor.fetchone()

        if not atividade:
            return False

        return atividade[0] == usuario_id
    finally:
        release_cursor(conn, cursor)


# =========================
# LOGIN
# =========================
@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():

    if request.method == "POST":

        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")

        if not nome or not email or not senha:
            return render_template("cadastro.html", erro="Preencha todos os campos obrigatórios.")

        if len(senha) < 3:
            return render_template("cadastro.html", erro="A senha deve conter pelo menos 3 caracteres.")

        conn, cursor = get_cursor()
        try:
            # Verifica se o e-mail já está cadastrado
            cursor.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
            if cursor.fetchone():
                return render_template(
                    "cadastro.html",
                    erro=f"O e-mail '{email}' já está cadastrado. Faça login ou use outro e-mail."
                )

            senha_hash = gerar_hash_senha(senha)

            cursor.execute(
                """
                INSERT INTO usuarios (
                    nome,
                    email,
                    senha,
                    perfil
                )
                VALUES (%s,%s,%s,%s)
                """,
                (nome, email, senha_hash, "professor"),
            )

            conn.commit()
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            print(f"[CADASTRO] Erro ao cadastrar usuário: {e}")
            return render_template("cadastro.html", erro="Ocorreu um erro ao cadastrar. Tente novamente.")
        finally:
            release_cursor(conn, cursor)

        return redirect("/login")

    return render_template("cadastro.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"].strip().lower()
        senha = request.form["senha"]

        conn, cursor = get_cursor()
        try:
            cursor.execute(
                """
                SELECT id, nome, email, perfil, senha
                FROM usuarios
                WHERE email=%s
                """,
                (email,),
            )

            usuario = cursor.fetchone()
        finally:
            release_cursor(conn, cursor)

        if usuario and verificar_senha(senha, usuario[4]):
            # Migra transparentemente se a senha ainda estava em texto puro
            atualizar_senha_para_hash_se_necessario(usuario[0], senha, usuario[4])

            session["usuario_id"] = usuario[0]
            session["nome"] = usuario[1]
            session["perfil"] = usuario[3]

            return redirect("/dashboard")

        return render_template("login.html", erro="Email ou senha incorretos.")

    return render_template("login.html")


@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# ============================================================
# REDEFINIÇÃO DE SENHA (PÚBLICA / ESQUECI MINHA SENHA)
# ============================================================
@app.route("/redefinir_senha", methods=["GET", "POST"])
@app.route("/esqueci_senha", methods=["GET", "POST"])
def redefinir_senha():
    # Se já logado, redireciona para a página interna de alteração
    if "usuario_id" in session:
        return redirect("/alterar_senha")

    chave_recuperacao_configurada = os.environ.get("CHAVE_RECUPERACAO_SENHA", "").strip()

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        nova_senha = request.form.get("nova_senha", "")
        confirmar_senha = request.form.get("confirmar_senha", "")
        codigo = request.form.get("codigo_recuperacao", "").strip()

        if not email or not nova_senha or not confirmar_senha:
            return render_template(
                "redefinir_senha.html",
                erro="Preencha todos os campos obrigatórios.",
                exige_codigo=bool(chave_recuperacao_configurada),
                email=email,
            )

        if len(nova_senha) < 3:
            return render_template(
                "redefinir_senha.html",
                erro="A nova senha deve ter no mínimo 3 caracteres.",
                exige_codigo=bool(chave_recuperacao_configurada),
                email=email,
            )

        if nova_senha != confirmar_senha:
            return render_template(
                "redefinir_senha.html",
                erro="A confirmação de senha não confere com a nova senha.",
                exige_codigo=bool(chave_recuperacao_configurada),
                email=email,
            )

        # Se houver chave institucional configurada no .env, valida
        if chave_recuperacao_configurada and codigo != chave_recuperacao_configurada:
            return render_template(
                "redefinir_senha.html",
                erro="Chave de segurança institucional incorreta. Solicite ao administrador da rede.",
                exige_codigo=True,
                email=email,
            )

        # Atualiza a senha no banco
        sucesso = redefinir_senha_por_email(email, nova_senha)
        if not sucesso:
            return render_template(
                "redefinir_senha.html",
                erro="E-mail não encontrado no sistema. Verifique o endereço informado.",
                exige_codigo=bool(chave_recuperacao_configurada),
                email=email,
            )

        return redirect("/login?sucesso=senha_redefinida")

    return render_template(
        "redefinir_senha.html",
        exige_codigo=bool(chave_recuperacao_configurada),
        email=request.args.get("email", ""),
    )


# ============================================================
# ALTERAR SENHA (USUÁRIO LOGADO)
# ============================================================
@app.route("/alterar_senha", methods=["GET", "POST"])
def alterar_senha():
    if "usuario_id" not in session:
        return redirect("/login")

    usuario_id = session["usuario_id"]

    if request.method == "POST":
        senha_atual = request.form.get("senha_atual", "")
        nova_senha = request.form.get("nova_senha", "")
        confirmar_senha = request.form.get("confirmar_senha", "")

        if not senha_atual or not nova_senha or not confirmar_senha:
            return render_template("alterar_senha.html", erro="Preencha todos os campos obrigatórios.")

        if len(nova_senha) < 3:
            return render_template("alterar_senha.html", erro="A nova senha deve conter pelo menos 3 caracteres.")

        if nova_senha != confirmar_senha:
            return render_template("alterar_senha.html", erro="A nova senha e a confirmação não conferem.")

        conn, cursor = get_cursor()
        try:
            cursor.execute("SELECT senha FROM usuarios WHERE id = %s", (usuario_id,))
            res = cursor.fetchone()
            if not res or not verificar_senha(senha_atual, res[0]):
                return render_template("alterar_senha.html", erro="A senha atual informada está incorreta.")
        finally:
            release_cursor(conn, cursor)

        sucesso = redefinir_senha_usuario(usuario_id, nova_senha)
        if sucesso:
            return render_template("alterar_senha.html", sucesso="Sua senha foi alterada com sucesso!")
        else:
            return render_template("alterar_senha.html", erro="Erro ao atualizar a senha no banco de dados.")

    return render_template("alterar_senha.html")


# ============================================================
# GESTÃO DE USUÁRIOS (PAINEL ADMINISTRATIVO)
# ============================================================
@app.route("/usuarios")
def listar_usuarios():
    if "usuario_id" not in session:
        return redirect("/login")

    if session.get("perfil") != "admin":
        return redirect("/dashboard")

    conn, cursor = get_cursor()
    try:
        cursor.execute("""
            SELECT u.id, u.nome, u.email, u.perfil,
                   COALESCE((SELECT COUNT(*) FROM atividades a WHERE a.usuario_id = u.id), 0) AS total_atividades,
                   COALESCE((SELECT COUNT(*) FROM planejamentos_docente p WHERE p.usuario_id = u.id), 0) AS total_planejamentos
            FROM usuarios u
            ORDER BY u.id ASC
        """)
        usuarios = cursor.fetchall()
    finally:
        release_cursor(conn, cursor)

    return render_template("usuarios.html", usuarios=usuarios)


@app.route("/admin/redefinir_senha/<int:id>", methods=["POST"])
def admin_redefinir_senha(id):
    if "usuario_id" not in session or session.get("perfil") != "admin":
        return redirect("/login")

    nova_senha = request.form.get("nova_senha", "").strip()
    if not nova_senha or len(nova_senha) < 3:
        return redirect("/usuarios?erro=senha_curta")

    redefinir_senha_usuario(id, nova_senha)
    return redirect("/usuarios?sucesso=senha_redefinida")


@app.route("/admin/alterar_perfil/<int:id>", methods=["POST"])
def admin_alterar_perfil(id):
    if "usuario_id" not in session or session.get("perfil") != "admin":
        return redirect("/login")

    if id == session["usuario_id"]:
        return redirect("/usuarios?erro=proprio_usuario")

    novo_perfil = request.form.get("perfil", "professor").strip().lower()
    if novo_perfil not in ("admin", "professor"):
        novo_perfil = "professor"

    conn, cursor = get_cursor()
    try:
        cursor.execute("UPDATE usuarios SET perfil = %s WHERE id = %s", (novo_perfil, id))
        conn.commit()
    finally:
        release_cursor(conn, cursor)

    return redirect("/usuarios?sucesso=perfil_atualizado")


@app.route("/admin/deletar_usuario/<int:id>", methods=["POST", "GET"])
def admin_deletar_usuario(id):
    if "usuario_id" not in session or session.get("perfil") != "admin":
        return redirect("/login")

    if id == session["usuario_id"]:
        return redirect("/usuarios?erro=proprio_usuario")

    conn, cursor = get_cursor()
    try:
        cursor.execute("DELETE FROM usuarios WHERE id = %s", (id,))
        conn.commit()
    finally:
        release_cursor(conn, cursor)

    return redirect("/usuarios?sucesso=usuario_excluido")


# =========================
# LANDING PAGE (PÁGINA INICIAL DO SGPP)
# =========================
@app.route("/", methods=["GET"])
@app.route("/inicio", methods=["GET"])
def landing():
    # Sempre exibe a Landing Page ao abrir o site (mesmo logado, com botão 'Ir para o Painel')
    return render_template("landing.html")


# =========================
# NOVA ATIVIDADE (GERAR ATIVIDADE - REPOSITÓRIO / IA)
# =========================
@app.route("/nova_atividade", methods=["GET", "POST"])
@app.route("/", methods=["POST"])
def index():

    if "usuario_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        curso = request.form.get("curso", "").strip()
        disciplina = request.form.get("disciplina", "").strip()
        conteudo = request.form.get("conteudo", "").strip()
        dificuldade = request.form.get("dificuldade", "médio").strip()
        tipo = request.form.get("tipo", "mista").strip()
        quantidade_str = request.form.get("quantidade", "5").strip()
        fonte = request.form.get("fonte", "ia").strip()
        completar_com_ia = request.form.get("completar_com_ia", "").strip()

        try:
            quantidade = max(1, min(int(quantidade_str), 50))
        except ValueError:
            quantidade = 5

        # Se a fonte for Repositório do Professor
        if fonte == "repositorio":
            questoes_disp = buscar_questoes_repositorio(
                curso=curso,
                disciplina=disciplina,
                conteudo=conteudo,
                dificuldade=dificuldade,
                tipo=tipo,
                usuario_id=session["usuario_id"],
                limite=quantidade
            )
            qtd_disp = len(questoes_disp)

            # Se não tem o suficiente no repositório e ainda não autorizou completar com IA
            if qtd_disp < quantidade and completar_com_ia != "sim":
                # Se o usuário escolheu "Não, voltar para solicitação"
                if completar_com_ia == "nao":
                    return render_template(
                        "index.html",
                        dados_form={
                            "curso": curso,
                            "disciplina": disciplina,
                            "conteudo": conteudo,
                            "dificuldade": dificuldade,
                            "tipo": tipo,
                            "quantidade": quantidade,
                            "fonte": fonte
                        }
                    )

                # Fallback sem JavaScript ativo: renderiza o aviso com as opções Sim e Não
                return render_template(
                    "index.html",
                    confirmar_complemento=True,
                    disponiveis=qtd_disp,
                    solicitadas=quantidade,
                    faltantes=quantidade - qtd_disp,
                    dados_form={
                        "curso": curso,
                        "disciplina": disciplina,
                        "conteudo": conteudo,
                        "dificuldade": dificuldade,
                        "tipo": tipo,
                        "quantidade": quantidade,
                        "fonte": fonte
                    }
                )

            # Se atingiu a quantidade pelo repositório
            if qtd_disp >= quantidade:
                questoes_selecionadas = questoes_disp[:quantidade]
                atividade_gerada = formatar_questoes_para_atividade(questoes_selecionadas)
                origem_salva = "repositorio"
            else:
                # Completar com IA / banco externo (Usuário disse SIM!)
                faltantes = quantidade - qtd_disp
                texto_ia = gerar_atividade(
                    conteudo,
                    dificuldade,
                    tipo,
                    faltantes
                )
                # Salva as novas questões geradas pela IA no repositório
                salvar_questoes_ia_no_repositorio(
                    texto_atividade=texto_ia,
                    curso=curso,
                    disciplina=disciplina,
                    conteudo=conteudo,
                    dificuldade=dificuldade,
                    tipo=tipo,
                    usuario_id=session["usuario_id"]
                )
                atividade_gerada = compor_atividade_hibrida(questoes_disp, texto_ia, quantidade)
                origem_salva = "misto" if qtd_disp > 0 else "ia"

        else:
            # Geração direta com IA / Banco Externo
            atividade_gerada = gerar_atividade(
                conteudo,
                dificuldade,
                tipo,
                quantidade
            )
            salvar_questoes_ia_no_repositorio(
                texto_atividade=atividade_gerada,
                curso=curso,
                disciplina=disciplina,
                conteudo=conteudo,
                dificuldade=dificuldade,
                tipo=tipo,
                usuario_id=session["usuario_id"]
            )
            origem_salva = "ia"

        conn, cursor = get_cursor()
        try:
            cursor.execute(
                """
                INSERT INTO atividades (
                    curso,
                    disciplina,
                    conteudo,
                    dificuldade,
                    atividade_gerada,
                    usuario_id,
                    origem
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    curso,
                    disciplina,
                    conteudo,
                    dificuldade,
                    atividade_gerada,
                    session["usuario_id"],
                    origem_salva
                ),
            )

            conn.commit()
        finally:
            release_cursor(conn, cursor)

        return redirect("/atividades")

    return render_template("index.html")


# =========================
# API VERIFICAÇÃO REPOSITÓRIO
# =========================
@app.route("/api/repositorio/verificar", methods=["POST"])
def api_verificar_repositorio():
    if "usuario_id" not in session:
        return jsonify({"erro": "Não autorizado"}), 401

    dados = request.get_json() or {}
    curso = dados.get("curso", "").strip()
    disciplina = dados.get("disciplina", "").strip()
    conteudo = dados.get("conteudo", "").strip()
    dificuldade = dados.get("dificuldade", "").strip()
    tipo = dados.get("tipo", "").strip()
    fonte = dados.get("fonte", "repositorio").strip()

    try:
        quantidade = max(1, min(int(dados.get("quantidade", 5)), 50))
    except (ValueError, TypeError):
        quantidade = 5

    if fonte != "repositorio":
        return jsonify({
            "suficiente": True,
            "disponiveis": 0,
            "solicitadas": quantidade,
            "faltantes": 0
        })

    questoes = buscar_questoes_repositorio(
        curso=curso,
        disciplina=disciplina,
        conteudo=conteudo,
        dificuldade=dificuldade,
        tipo=tipo,
        usuario_id=session["usuario_id"],
        limite=quantidade
    )
    disponiveis = len(questoes)

    return jsonify({
        "suficiente": disponiveis >= quantidade,
        "disponiveis": disponiveis,
        "solicitadas": quantidade,
        "faltantes": max(0, quantidade - disponiveis)
    })


# =========================
# REPOSITÓRIO DE ATIVIDADES
# =========================
@app.route("/repositorio")
def listar_repositorio():
    if "usuario_id" not in session:
        return redirect("/login")

    busca = (request.args.get("busca") or "").strip()
    origem = (request.args.get("origem") or "").strip()
    tipo = (request.args.get("tipo") or "").strip()
    dificuldade = (request.args.get("dificuldade") or "").strip()

    try:
        pagina = max(1, int(request.args.get("pagina", 1)))
    except ValueError:
        pagina = 1

    por_pagina = 15
    offset = (pagina - 1) * por_pagina

    conn, cursor = get_cursor()
    try:
        condicoes = []
        params = []

        if busca:
            condicoes.append("(enunciado ILIKE %s OR curso ILIKE %s OR disciplina ILIKE %s OR conteudo ILIKE %s)")
            termo = f"%{busca}%"
            params.extend([termo, termo, termo, termo])

        if origem:
            condicoes.append("origem = %s")
            params.append(origem)

        if tipo:
            condicoes.append("tipo = %s")
            params.append(tipo)

        if dificuldade:
            condicoes.append("dificuldade ILIKE %s")
            params.append(f"%{dificuldade}%")

        where_sql = ("WHERE " + " AND ".join(condicoes)) if condicoes else ""

        # Estatísticas do repositório
        cursor.execute("SELECT COUNT(*) FROM repositorio_atividades")
        total_itens = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM repositorio_atividades WHERE origem = 'professor'")
        total_professor = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM repositorio_atividades WHERE origem = 'ia'")
        total_ia = cursor.fetchone()[0]

        # Total filtrado para paginação
        cursor.execute(f"SELECT COUNT(*) FROM repositorio_atividades {where_sql}", tuple(params))
        total_filtrado = cursor.fetchone()[0]

        total_paginas = (total_filtrado + por_pagina - 1) // por_pagina

        query = f"""
            SELECT id, curso, disciplina, conteudo, dificuldade, tipo,
                   enunciado, alternativas, resposta_correta, origem, usuario_id, data_criacao
            FROM repositorio_atividades
            {where_sql}
            ORDER BY id DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, tuple(params + [por_pagina, offset]))
        rows = cursor.fetchall()

        questoes = []
        for r in rows:
            questoes.append({
                "id": r[0],
                "curso": r[1],
                "disciplina": r[2],
                "conteudo": r[3],
                "dificuldade": r[4],
                "tipo": r[5],
                "enunciado": r[6],
                "alternativas": r[7],
                "resposta_correta": r[8],
                "origem": r[9],
                "usuario_id": r[10],
                "data_criacao": r[11]
            })

    finally:
        release_cursor(conn, cursor)

    return render_template(
        "repositorio.html",
        questoes=questoes,
        total_itens=total_itens,
        total_professor=total_professor,
        total_ia=total_ia,
        total_paginas=total_paginas,
        pagina=pagina,
        busca=busca,
        origem=origem,
        tipo=tipo,
        dificuldade=dificuldade
    )


@app.route("/repositorio/nova", methods=["GET", "POST"])
def repositorio_nova():
    if "usuario_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        curso = request.form.get("curso", "").strip()
        disciplina = request.form.get("disciplina", "").strip()
        conteudo = request.form.get("conteudo", "").strip()
        dificuldade = request.form.get("dificuldade", "médio").strip()
        tipo = request.form.get("tipo", "objetiva").strip()
        enunciado = request.form.get("enunciado", "").strip()
        alternativas = request.form.get("alternativas", "").strip()
        resposta_correta = request.form.get("resposta_correta", "").strip()

        if not curso or not disciplina or not conteudo or not enunciado:
            return render_template(
                "repositorio_form.html",
                item=request.form,
                erro="Preencha todos os campos obrigatórios."
            )

        adicionar_ao_repositorio(
            curso=curso,
            disciplina=disciplina,
            conteudo=conteudo,
            dificuldade=dificuldade,
            tipo=tipo,
            enunciado=enunciado,
            alternativas=alternativas,
            resposta_correta=resposta_correta,
            origem="professor",
            usuario_id=session["usuario_id"]
        )

        return redirect("/repositorio")

    return render_template("repositorio_form.html", item=None)


@app.route("/repositorio/editar/<int:id>", methods=["GET", "POST"])
def repositorio_editar(id):
    if "usuario_id" not in session:
        return redirect("/login")

    item = obter_item_repositorio(id)
    if not item:
        return redirect("/repositorio")

    if request.method == "POST":
        curso = request.form.get("curso", "").strip()
        disciplina = request.form.get("disciplina", "").strip()
        conteudo = request.form.get("conteudo", "").strip()
        dificuldade = request.form.get("dificuldade", "médio").strip()
        tipo = request.form.get("tipo", "objetiva").strip()
        enunciado = request.form.get("enunciado", "").strip()
        alternativas = request.form.get("alternativas", "").strip()
        resposta_correta = request.form.get("resposta_correta", "").strip()

        atualizar_no_repositorio(
            item_id=id,
            curso=curso,
            disciplina=disciplina,
            conteudo=conteudo,
            dificuldade=dificuldade,
            tipo=tipo,
            enunciado=enunciado,
            alternativas=alternativas,
            resposta_correta=resposta_correta
        )

        return redirect("/repositorio")

    return render_template("repositorio_form.html", item=item)


@app.route("/repositorio/deletar/<int:id>", methods=["GET", "POST"])
def repositorio_deletar(id):
    if "usuario_id" not in session:
        return redirect("/login")

    deletar_do_repositorio(
        item_id=id,
        usuario_id=session["usuario_id"],
        perfil=session.get("perfil", "professor")
    )

    return redirect("/repositorio")


# =========================
# LISTAR + PESQUISA COM PAGINAÇÃO
# =========================
@app.route("/atividades")
def atividades():

    if "usuario_id" not in session:
        return redirect("/login")

    busca = (request.args.get("busca") or "").strip()
    try:
        pagina = max(1, int(request.args.get("pagina", 1)))
    except ValueError:
        pagina = 1

    por_pagina = 20
    offset = (pagina - 1) * por_pagina

    conn, cursor = get_cursor()
    try:
        if session["perfil"] == "admin":
            if busca:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM atividades
                    WHERE curso ILIKE %s
                       OR disciplina ILIKE %s
                       OR conteudo ILIKE %s
                    """,
                    (f"%{busca}%", f"%{busca}%", f"%{busca}%"),
                )
                total_itens = cursor.fetchone()[0]

                cursor.execute(
                    """
                    SELECT *
                    FROM atividades
                    WHERE curso ILIKE %s
                       OR disciplina ILIKE %s
                       OR conteudo ILIKE %s
                    ORDER BY id DESC
                    LIMIT %s OFFSET %s
                    """,
                    (f"%{busca}%", f"%{busca}%", f"%{busca}%", por_pagina, offset),
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM atividades")
                total_itens = cursor.fetchone()[0]

                cursor.execute(
                    """
                    SELECT *
                    FROM atividades
                    ORDER BY id DESC
                    LIMIT %s OFFSET %s
                    """,
                    (por_pagina, offset),
                )

        else:
            usuario_id = session["usuario_id"]
            if busca:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM atividades
                    WHERE usuario_id = %s
                      AND (
                            curso ILIKE %s
                         OR disciplina ILIKE %s
                         OR conteudo ILIKE %s
                      )
                    """,
                    (usuario_id, f"%{busca}%", f"%{busca}%", f"%{busca}%"),
                )
                total_itens = cursor.fetchone()[0]

                cursor.execute(
                    """
                    SELECT *
                    FROM atividades
                    WHERE usuario_id = %s
                      AND (
                            curso ILIKE %s
                         OR disciplina ILIKE %s
                         OR conteudo ILIKE %s
                      )
                    ORDER BY id DESC
                    LIMIT %s OFFSET %s
                    """,
                    (
                        usuario_id,
                        f"%{busca}%",
                        f"%{busca}%",
                        f"%{busca}%",
                        por_pagina,
                        offset
                    ),
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM atividades WHERE usuario_id = %s", (usuario_id,))
                total_itens = cursor.fetchone()[0]

                cursor.execute(
                    """
                    SELECT *
                    FROM atividades
                    WHERE usuario_id = %s
                    ORDER BY id DESC
                    LIMIT %s OFFSET %s
                    """,
                    (usuario_id, por_pagina, offset),
                )

        dados = cursor.fetchall()
        total_paginas = max(1, -(-total_itens // por_pagina))
    finally:
        release_cursor(conn, cursor)

    return render_template(
        "atividades.html",
        atividades=dados,
        pagina=pagina,
        total_paginas=total_paginas,
        total_itens=total_itens,
        busca=busca
    )


# =========================
# DELETE
# =========================
@app.route("/deletar/<int:id>")
def deletar(id):

    if "usuario_id" not in session:
        return redirect("/login")

    if not pode_acessar_atividade(id, session["usuario_id"], session.get("perfil")):
        return "Acesso negado"

    conn, cursor = get_cursor()
    try:
        cursor.execute(
            "DELETE FROM atividades WHERE id=%s",
            (id,)
        )

        conn.commit()
    finally:
        release_cursor(conn, cursor)

    return redirect("/atividades")


# =========================
# EDITAR
# =========================
@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):

    if "usuario_id" not in session:
        return redirect("/login")

    if not pode_acessar_atividade(id, session["usuario_id"], session.get("perfil")):
        return "Acesso negado"

    if request.method == "POST":

        curso = request.form["curso"]
        disciplina = request.form["disciplina"]
        conteudo = request.form["conteudo"]
        dificuldade = request.form["dificuldade"]
        atividade_gerada = request.form["atividade_gerada"]

        conn, cursor = get_cursor()
        try:
            cursor.execute(
                """
                UPDATE atividades
                SET curso=%s,
                    disciplina=%s,
                    conteudo=%s,
                    dificuldade=%s,
                    atividade_gerada=%s
                WHERE id=%s
                """,
                (
                    curso,
                    disciplina,
                    conteudo,
                    dificuldade,
                    atividade_gerada,
                    id
                ),
            )

            conn.commit()
        finally:
            release_cursor(conn, cursor)

        return redirect("/atividades")

    conn, cursor = get_cursor()
    try:
        cursor.execute(
            "SELECT * FROM atividades WHERE id=%s",
            (id,)
        )

        atividade = cursor.fetchone()
    finally:
        release_cursor(conn, cursor)

    if not atividade:
        return "Atividade nÃ£o encontrada"

    return render_template(
        "editar.html",
        atividade=atividade
    )


# =========================
# CABEÇALHO DA ATIVIDADE
# =========================
def extrair_cabecalho_atividade(atividade):
    curso_raw = (atividade[1] or "").strip()
    disc_raw = (atividade[2] or "").strip()
    cont_raw = (atividade[3] or "").strip()
    dif_raw = (atividade[4] or "").strip()

    curso = curso_raw
    uc = disc_raw
    aula = "Encontro Regular"
    bloom = dif_raw.capitalize() if dif_raw else "Lembrar"

    if "—" in curso_raw:
        partes = [p.strip() for p in curso_raw.split("—")]
        curso = partes[0]
        if len(partes) > 1 and disc_raw in ("Plano de Aula", "", None):
            uc = partes[1]
    elif " - " in curso_raw and disc_raw in ("Plano de Aula", "", None):
        partes = [p.strip() for p in curso_raw.split(" - ")]
        curso = partes[0]
        uc = partes[1]

    m_c = re.search(r"Curso:\s*([^\n\r]+)", cont_raw, re.IGNORECASE)
    if m_c:
        curso = m_c.group(1).strip()

    m_uc = re.search(r"Unidade Curricular:\s*([^\n\r]+)", cont_raw, re.IGNORECASE)
    if m_uc:
        uc = m_uc.group(1).strip()

    m_a = re.search(r"Aula\s*/\s*Encontro:\s*([^\n\r]+)", cont_raw, re.IGNORECASE)
    if m_a:
        aula = m_a.group(1).strip()
    else:
        m_a2 = re.search(r"Aula:\s*([^\n\r]+)", cont_raw, re.IGNORECASE)
        if m_a2:
            aula = m_a2.group(1).strip()

    m_b = re.search(r"N[i\xed]vel Cognitivo(?:\s*\(Taxonomia de Bloom\))?:\s*([^\n\r]+)", cont_raw, re.IGNORECASE)
    if m_b:
        bloom = m_b.group(1).strip()

    return {
        "curso": curso,
        "unidade_curricular": uc,
        "aula_encontro": aula,
        "nivel_bloom": bloom
    }

# =========================
# PDF
# =========================
@app.route("/pdf/<int:id>")
def gerar_pdf(id):

    if "usuario_id" not in session:
        return redirect("/login")

    if not pode_acessar_atividade(id, session["usuario_id"], session.get("perfil")):
        return "Acesso negado"

    conn, cursor = get_cursor()
    try:
        cursor.execute(
            """
            SELECT *
            FROM atividades
            WHERE id=%s
            """,
            (id,)
        )

        atividade = cursor.fetchone()
    finally:
        release_cursor(conn, cursor)

    if not atividade:
        return "Atividade nÃ£o encontrada"

    arquivo_docx = f"outputs/atividade_{id}.docx"
    arquivo_pdf = f"outputs/atividade_{id}.pdf"

    dados_cab = extrair_cabecalho_atividade(atividade)

    os.makedirs("outputs", exist_ok=True)

    gerar_docx_atividade(
        titulo="ATIVIDADE",
        subtitulo=dados_cab["curso"],
        conteudo=atividade[5],
        caminho_saida=arquivo_docx,
        dados_cabecalho=dados_cab
    )

    resultado = gerar_pdf_atividade(
        arquivo_docx=arquivo_docx,
        arquivo_pdf=arquivo_pdf,
        titulo="ATIVIDADE",
        subtitulo=dados_cab["curso"],
        dados_cabecalho=dados_cab,
        conteudo=atividade[5]
    )

    if not resultado or not os.path.exists(arquivo_pdf):
        from utils.pdf_atividade_generator import gerar_pdf_atividade_reportlab
        gerar_pdf_atividade_reportlab(
            arquivo_pdf=arquivo_pdf,
            titulo="ATIVIDADE",
            subtitulo=dados_cab["curso"],
            dados_cabecalho=dados_cab,
            conteudo=atividade[5],
            arquivo_docx=arquivo_docx
        )

    if os.path.exists(arquivo_pdf):
        return send_file(
            arquivo_pdf,
            as_attachment=True,
            download_name=f"atividade_{id}.pdf",
            mimetype="application/pdf"
        )

    return "Erro ao gerar arquivo PDF da atividade. Por favor, tente novamente.", 500


# =========================
# WORD
# =========================
@app.route("/word/<int:id>")
def gerar_word(id):

    if "usuario_id" not in session:
        return redirect("/login")

    if not pode_acessar_atividade(id, session["usuario_id"], session.get("perfil")):
        return "Acesso negado"

    conn, cursor = get_cursor()
    try:
        cursor.execute(
            """
            SELECT *
            FROM atividades
            WHERE id=%s
            """,
            (id,)
        )

        atividade = cursor.fetchone()
    finally:
        release_cursor(conn, cursor)

    if not atividade:
        return "Atividade não encontrada"

    arquivo = f"outputs/atividade_{id}.docx"

    dados_cab = extrair_cabecalho_atividade(atividade)

    gerar_docx_atividade(
        titulo="ATIVIDADE",
        subtitulo=dados_cab["curso"],
        conteudo=atividade[5],
        caminho_saida=arquivo,
        dados_cabecalho=dados_cab
    )

    return send_file(
        arquivo,
        as_attachment=True,
        download_name=f"atividade_{id}.docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


# =========================
# REGENERAR IA
# =========================
@app.route("/regenerar/<int:id>")
def regenerar(id):

    if "usuario_id" not in session:
        return redirect("/login")

    if not pode_acessar_atividade(id, session["usuario_id"], session.get("perfil")):
        return "Acesso negado"

    conn, cursor = get_cursor()
    try:
        cursor.execute(
            """
            SELECT conteudo, dificuldade
            FROM atividades
            WHERE id=%s
            """,
            (id,)
        )

        atividade = cursor.fetchone()
    finally:
        release_cursor(conn, cursor)

    if not atividade:
        return "Atividade nÃ£o encontrada"

    nova = gerar_atividade(
        atividade[0],
        atividade[1],
        "objetiva",
        5
    )

    conn, cursor = get_cursor()
    try:
        cursor.execute(
            """
            UPDATE atividades
            SET atividade_gerada=%s
            WHERE id=%s
            """,
            (nova, id)
        )

        conn.commit()
    finally:
        release_cursor(conn, cursor)

    return redirect("/atividades")


# =========================
# DASHBOARD
# =========================
@app.route("/dashboard")
def dashboard():

    if "usuario_id" not in session:
        return redirect("/login")

    conn, cursor = get_cursor()
    try:
        if session["perfil"] == "admin":

            cursor.execute(
                """
                SELECT
                    curso,
                    COUNT(*)
                FROM atividades
                GROUP BY curso
                ORDER BY curso
                """
            )
            cursos = cursor.fetchall()

            cursor.execute("SELECT COUNT(*) FROM atividades")
            total_atividades = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM planejamentos_docente")
            total_planejamentos = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM planos_aula")
            total_planos = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM cursos_plano")
            total_cursos_plano = cursor.fetchone()[0]

        else:
            usuario_id = session["usuario_id"]

            cursor.execute(
                """
                SELECT
                    curso,
                    COUNT(*)
                FROM atividades
                WHERE usuario_id = %s
                GROUP BY curso
                ORDER BY curso
                """,
                (usuario_id,),
            )
            cursos = cursor.fetchall()

            cursor.execute("SELECT COUNT(*) FROM atividades WHERE usuario_id = %s", (usuario_id,))
            total_atividades = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM planejamentos_docente WHERE usuario_id = %s", (usuario_id,))
            total_planejamentos = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM planos_aula WHERE usuario_id = %s", (usuario_id,))
            total_planos = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM cursos_plano WHERE usuario_id = %s", (usuario_id,))
            total_cursos_plano = cursor.fetchone()[0]

    finally:
        release_cursor(conn, cursor)

    return render_template(
        "dashboard.html",
        cursos=cursos,
        total_atividades=total_atividades,
        total_planejamentos=total_planejamentos,
        total_planos=total_planos,
        total_cursos_plano=total_cursos_plano
    )

# =========================
# PLANOS DE AULA
# =========================
@app.route("/planos", methods=["GET", "POST"])
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
        print(f"[INFO] PROCESSANDO ARQUIVO PARA GERAR PLANOS DE AULA")
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
                    print(f"[INFO] Arquivo reconhecido como Planejamento Docente ({len(aulas_excel)} aulas identificadas)!")
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
                print("[INFO] Extraindo dados de Matriz de Referência...")
                dados_excel = extrair_dados_excel(caminho)
                texto = formatar_dados_para_prompt(dados_excel)
            else:
                print("[INFO] Extraindo texto do PDF...")
                reader = PdfReader(caminho)
                texto = ""
                for pagina in reader.pages:
                    conteudo = pagina.extract_text()
                    if conteudo:
                        texto += conteudo + "\n"

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
                planos_completos += f"\n\nDIA {dia}\n\n{plano}"
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

        print(f"[OK] {len(planos)} Planos de aula gerados para o Curso #{curso_id}!")
        print("=" * 60)

        # Redireciona para o curso onde cada plano tem o botão individual para gerar atividade
        return redirect(f"/curso/{curso_id}")

    return render_template("planos.html")


# =========================
# LISTAR PLANOS
# =========================
@app.route("/listar_planos")
def listar_planos():
    return redirect("/listar_cursos")


# =========================
# VISUALIZAR PLANO
# =========================
@app.route("/plano/<int:plano_id>")
def visualizar_plano(plano_id):

    conn, cursor = get_cursor()
    try:
        cursor.execute(
            """
            SELECT pa.*, cp.nome_curso, cp.carga_horaria
            FROM planos_aula pa
            LEFT JOIN cursos_plano cp ON cp.id = pa.curso_id
            WHERE pa.id = %s
            """,
            (plano_id,),
        )

        plano = cursor.fetchone()
    finally:
        release_cursor(conn, cursor)

    if not plano:
        return "Plano nÃ£o encontrado"

    return render_template(
        "visualizar_plano.html",
        plano=plano
    )


# =========================
# LISTAR CURSOS
# =========================
@app.route("/listar_cursos")
def listar_cursos():

    if "usuario_id" not in session:
        return redirect("/login")

    conn, cursor = get_cursor()
    try:
        if session["perfil"] == "admin":

            cursor.execute(
                """
                SELECT *
                FROM cursos_plano
                ORDER BY id DESC
                """
            )

        else:

            cursor.execute(
                """
                SELECT *
                FROM cursos_plano
                WHERE usuario_id = %s
                ORDER BY id DESC
                """,
                (session["usuario_id"],),
            )

        cursos = cursor.fetchall()
    finally:
        release_cursor(conn, cursor)

    return render_template(
        "listar_cursos.html",
        cursos=cursos
    )


# =========================
# DELETAR CURSO
# =========================
@app.route("/deletar_curso/<int:curso_id>")
def deletar_curso(curso_id):

    if "usuario_id" not in session:
        return redirect("/login")

    conn, cursor = get_cursor()
    try:
        # Verifica se o curso pertence ao usuario (ou se Ã© admin)
        if session["perfil"] == "admin":
            cursor.execute(
                "SELECT id FROM cursos_plano WHERE id = %s",
                (curso_id,)
            )
        else:
            cursor.execute(
                "SELECT id FROM cursos_plano WHERE id = %s AND usuario_id = %s",
                (curso_id, session["usuario_id"])
            )

        curso = cursor.fetchone()
        if not curso:
            return "Curso nÃ£o encontrado", 404

        # Deleta os planos de aula associados primeiro
        cursor.execute(
            "DELETE FROM planos_aula WHERE curso_id = %s",
            (curso_id,)
        )

        # Deleta o curso
        cursor.execute(
            "DELETE FROM cursos_plano WHERE id = %s",
            (curso_id,)
        )

        conn.commit()
        print(f"ðŸ—‘ï¸ Curso #{curso_id} e seus planos deletados")
    finally:
        release_cursor(conn, cursor)

    return redirect("/listar_cursos")


# =========================
# VISUALIZAR CURSO
# =========================
@app.route("/curso/<int:curso_id>")
def visualizar_curso(curso_id):

    if "usuario_id" not in session:
        return redirect("/login")

    conn, cursor = get_cursor()
    try:
        cursor.execute(
            """
            SELECT *
            FROM cursos_plano
            WHERE id = %s
            """,
            (curso_id,),
        )

        curso = cursor.fetchone()

        cursor.execute(
            """
            SELECT *
            FROM planos_aula
            WHERE curso_id = %s
            ORDER BY dia
            """,
            (curso_id,),
        )

        planos = cursor.fetchall()
    finally:
        release_cursor(conn, cursor)

    return render_template(
        "planos_curso.html",
        planos=planos,
        curso_id=curso_id,
        curso=curso
    )


# =========================
# PLANO PDF
# =========================
@app.route("/plano_pdf/<int:id>")
def plano_pdf(id):

    if "usuario_id" not in session:
        return redirect("/login")

    conn, cursor = get_cursor()
    try:
        cursor.execute(
            """
            SELECT *
            FROM planos_aula
            WHERE id=%s
            """,
            (id,)
        )

        plano = cursor.fetchone()
    finally:
        release_cursor(conn, cursor)

    if not plano:
        return "Plano nÃ£o encontrado"

    arquivo_docx = f"outputs/plano_{id}.docx"
    arquivo_pdf = f"outputs/plano_{id}.pdf"

    gerar_docx_plano(
        titulo="PLANO DE AULA",
        subtitulo=plano[3],
        conteudo=plano[4],
        caminho_saida=arquivo_docx
    )

    resultado = gerar_pdf_plano(
        arquivo_docx,
        arquivo_pdf,
        titulo="PLANO DE AULA",
        subtitulo=plano[3],
        conteudo=plano[4]
    )

    if not resultado or not os.path.exists(arquivo_pdf):
        from utils.pdf_generator import gerar_pdf_plano_reportlab
        gerar_pdf_plano_reportlab(
            docx_path=arquivo_docx,
            pdf_path=arquivo_pdf,
            titulo="PLANO DE AULA",
            subtitulo=plano[3],
            conteudo=plano[4]
        )

    if os.path.exists(arquivo_pdf):
        return send_file(
            arquivo_pdf,
            as_attachment=True,
            download_name=f"plano_{id}.pdf",
            mimetype="application/pdf"
        )

    return "Erro ao gerar arquivo PDF do plano. Por favor, tente novamente.", 500


# =========================
# PLANO WORD
# =========================
@app.route("/plano_word/<int:id>")
def plano_word(id):

    if "usuario_id" not in session:
        return redirect("/login")

    conn, cursor = get_cursor()
    try:
        cursor.execute(
            """
            SELECT *
            FROM planos_aula
            WHERE id=%s
            """,
            (id,)
        )

        plano = cursor.fetchone()
    finally:
        release_cursor(conn, cursor)

    if not plano:
        return "Plano não encontrado"

    arquivo = f"outputs/plano_{id}.docx"

    gerar_docx_plano(
        titulo="PLANO DE AULA",
        subtitulo=plano[3],
        conteudo=plano[4],
        caminho_saida=arquivo
    )

    return send_file(
        arquivo,
        as_attachment=True,
        download_name=f"plano_{id}.docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


# =========================
# CURSO COMPLETO PDF & WORD
# =========================
@app.route("/curso_pdf/<int:curso_id>")
def curso_pdf(curso_id):

    if "usuario_id" not in session:
        return redirect("/login")

    conn, cursor = get_cursor()
    try:
        cursor.execute("SELECT * FROM cursos_plano WHERE id = %s", (curso_id,))
        curso = cursor.fetchone()

        cursor.execute("SELECT * FROM planos_aula WHERE curso_id = %s ORDER BY dia", (curso_id,))
        planos = cursor.fetchall()
    finally:
        release_cursor(conn, cursor)

    if not curso:
        return "Curso não encontrado", 404

    arquivo_docx = f"outputs/plano_{curso_id}.docx"
    arquivo_pdf = f"outputs/plano_{curso_id}.pdf"

    nome_curso = curso[1]
    planos_completos = []
    for p in planos:
        planos_completos.append(f"DIA {p[2]}\n{p[4]}")
    conteudo_total = "\n\n".join(planos_completos)

    if not os.path.exists(arquivo_docx):
        gerar_docx_plano(
            titulo="PLANO DE AULA",
            subtitulo=f"Curso: {nome_curso}",
            conteudo=conteudo_total,
            caminho_saida=arquivo_docx
        )

    gerar_pdf_plano(
        docx_path=arquivo_docx,
        pdf_path=arquivo_pdf,
        titulo="PLANO DE AULA",
        subtitulo=f"Curso: {nome_curso}",
        conteudo=conteudo_total
    )

    if not os.path.exists(arquivo_pdf):
        from utils.pdf_generator import gerar_pdf_plano_reportlab
        gerar_pdf_plano_reportlab(
            docx_path=arquivo_docx,
            pdf_path=arquivo_pdf,
            titulo="PLANO DE AULA",
            subtitulo=f"Curso: {nome_curso}",
            conteudo=conteudo_total
        )

    if os.path.exists(arquivo_pdf):
        return send_file(
            arquivo_pdf,
            as_attachment=True,
            download_name=f"curso_{curso_id}_completo.pdf",
            mimetype="application/pdf"
        )

    return "Erro ao gerar arquivo PDF do curso completo.", 500


@app.route("/curso_word/<int:curso_id>")
def curso_word(curso_id):

    if "usuario_id" not in session:
        return redirect("/login")

    conn, cursor = get_cursor()
    try:
        cursor.execute("SELECT * FROM cursos_plano WHERE id = %s", (curso_id,))
        curso = cursor.fetchone()

        cursor.execute("SELECT * FROM planos_aula WHERE curso_id = %s ORDER BY dia", (curso_id,))
        planos = cursor.fetchall()
    finally:
        release_cursor(conn, cursor)

    if not curso:
        return "Curso não encontrado", 404

    arquivo_docx = f"outputs/plano_{curso_id}.docx"

    if not os.path.exists(arquivo_docx):
        nome_curso = curso[1]
        planos_completos = []
        for p in planos:
            planos_completos.append(f"DIA {p[2]}\n{p[4]}")
        conteudo_total = "\n\n".join(planos_completos)

        gerar_docx_plano(
            titulo="PLANO DE AULA",
            subtitulo=f"Curso: {nome_curso}",
            conteudo=conteudo_total,
            caminho_saida=arquivo_docx
        )

    return send_file(
        arquivo_docx,
        as_attachment=True,
        download_name=f"curso_{curso_id}_completo.docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


# =========================
# GERAR ATIVIDADE DO PLANO
# =========================
@app.route("/gerar_atividade_plano/<int:id>", methods=["GET"])
def gerar_atividade_plano(id):

    if "usuario_id" not in session:
        return redirect("/login")

    tipo = request.args.get("tipo", "objetiva")
    quantidade_str = request.args.get("quantidade", "5")
    dificuldade = request.args.get("dificuldade", "mÃ©dio")

    # Validar quantidade
    try:
        quantidade = int(quantidade_str)
        if quantidade < 1:
            quantidade = 5
        if quantidade > 50:
            quantidade = 50
    except ValueError:
        quantidade = 5

    # =========================
    # BUSCAR PLANO
    # =========================
    conn, cursor = get_cursor()
    try:
        cursor.execute(
            """
            SELECT *
            FROM planos_aula
            WHERE id = %s
            """,
            (id,),
        )

        plano = cursor.fetchone()
    finally:
        release_cursor(conn, cursor)

    if not plano:
        return "Plano nÃ£o encontrado"

    conteudo = plano[4]
    curso_id = plano[1]

    # =========================
    # BUSCAR NOME DO CURSO
    # =========================
    conn, cursor = get_cursor()
    try:
        cursor.execute(
            """
            SELECT nome_curso
            FROM cursos_plano
            WHERE id = %s
            """,
            (curso_id,),
        )

        curso = cursor.fetchone()
    finally:
        release_cursor(conn, cursor)

    if curso:
        nome_curso = curso[0]
    else:
        nome_curso = "Curso nÃ£o encontrado"

    # =========================
    # GERAR ATIVIDADE COM IA
    # =========================
    print(f"ðŸ¤– Gerando atividade a partir do Plano #{id}")
    print(f"   Curso: {nome_curso} | Tipo: {tipo} | Dificuldade: {dificuldade} | Qtd: {quantidade}")

    atividade = gerar_atividade(
        conteudo,
        dificuldade,
        tipo,
        quantidade
    )

    print(f"âœ… Atividade gerada com sucesso ({len(atividade)} caracteres)")
    print("=" * 60)

    # =========================
    # SALVAR NO BANCO
    # =========================
    conn, cursor = get_cursor()
    try:
        # Extrai metadados estruturados para o cabeçalho da atividade
        curso_ident = nome_curso
        uc_ident = "Plano de Aula"
        aula_ident = f"Dia {plano[2]}"
        bloom_ident = dificuldade.capitalize()

        m_c = re.search(r"Curso:\s*([^\n\r]+)", conteudo, re.IGNORECASE)
        if m_c:
            curso_ident = m_c.group(1).strip()
        elif "—" in nome_curso:
            curso_ident = nome_curso.split("—")[0].strip()

        m_uc = re.search(r"Unidade Curricular:\s*([^\n\r]+)", conteudo, re.IGNORECASE)
        if m_uc:
            uc_ident = m_uc.group(1).strip()
        elif "—" in nome_curso:
            uc_ident = nome_curso.split("—")[1].strip()

        m_a = re.search(r"Aula\s*/\s*Encontro:\s*([^\n\r]+)", conteudo, re.IGNORECASE)
        if m_a:
            aula_ident = m_a.group(1).strip()

        m_b = re.search(r"N[i\xed]vel Cognitivo(?:\s*\(Taxonomia de Bloom\))?:\s*([^\n\r]+)", conteudo, re.IGNORECASE)
        if m_b:
            bloom_ident = m_b.group(1).strip()

        cabecalho_ident = (
            f"- Curso: {curso_ident}\n"
            f"- Unidade Curricular: {uc_ident}\n"
            f"- Aula / Encontro: {aula_ident}\n"
            f"- Nível Cognitivo (Taxonomia de Bloom): {bloom_ident}"
        )

        cursor.execute(
            """
            INSERT INTO atividades (
                curso,
                disciplina,
                conteudo,
                dificuldade,
                atividade_gerada,
                usuario_id,
                origem
            )
            VALUES (%s,%s,%s,%s,%s,%s,'ia')
            """,
            (
                curso_ident,
                uc_ident,
                cabecalho_ident,
                bloom_ident,
                atividade,
                session["usuario_id"]
            ),
        )

        conn.commit()

        # Cataloga também no repositório de atividades
        try:
            salvar_questoes_ia_no_repositorio(
                texto_atividade=atividade,
                curso=curso_ident,
                disciplina=uc_ident,
                conteudo=cabecalho_ident,
                dificuldade=bloom_ident,
                tipo=tipo,
                usuario_id=session["usuario_id"]
            )
        except Exception as e_repo:
            print(f"[REPOSITORIO] Aviso ao catalogar atividade do plano: {e_repo}")
    finally:
        release_cursor(conn, cursor)

    return redirect("/atividades")


# =========================
# DELETAR PLANO INDIVIDUAL
# =========================
@app.route("/deletar_plano/<int:plano_id>")
def deletar_plano(plano_id):

    if "usuario_id" not in session:
        return redirect("/login")

    conn, cursor = get_cursor()
    try:
        # Busca o plano para saber o curso_id (para redirecionar)
        cursor.execute(
            "SELECT curso_id, usuario_id FROM planos_aula WHERE id = %s",
            (plano_id,)
        )
        plano = cursor.fetchone()

        if not plano:
            return "Plano nÃ£o encontrado", 404

        curso_id = plano[0]
        dono_id = plano[1]

        # Verifica permissÃ£o: admin ou dono
        if session["perfil"] != "admin" and dono_id != session["usuario_id"]:
            return "Acesso negado", 403

        # Deleta o plano
        cursor.execute(
            "DELETE FROM planos_aula WHERE id = %s",
            (plano_id,)
        )
        conn.commit()
        print(f"ðŸ—‘ï¸ Plano #{plano_id} deletado")
    finally:
        release_cursor(conn, cursor)

    return redirect(f"/curso/{curso_id}")


# =========================
# DOWNLOAD PLANO
# =========================
@app.route("/baixar_plano/<int:plano_id>")
def baixar_plano(plano_id):

    if "usuario_id" not in session:
        return redirect("/login")

    conn, cursor = get_cursor()
    try:
        cursor.execute(
            """
            SELECT *
            FROM planos_aula
            WHERE id=%s
            """,
            (plano_id,)
        )

        plano = cursor.fetchone()
    finally:
        release_cursor(conn, cursor)

    if not plano:
        return "Plano nÃ£o encontrado"

    arquivo = f"temp/plano_{plano_id}.docx"

    os.makedirs("temp", exist_ok=True)

    gerar_docx_plano(
        titulo="PLANO DE AULA",
        subtitulo=f"Dia {plano[2]}",
        conteudo=plano[4],
        caminho_saida=arquivo
    )

    return send_file(
        arquivo,
        as_attachment=True
    )




# =========================
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
        print(f"[INFO] GERANDO PLANEJAMENTO DOCENTE")
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
            print(f"[INFO] Plano de Curso salvo: {caminho_plano}")
            try:
                dados_plano = estruturar_dados_plano_pdf(caminho_plano, unidade_curricular_alvo=unidade_curricular)
                dados_plano["unidade_curricular"] = dados_plano.get("unidade_curricular") or unidade_curricular
                print(f"[OK] PDF lido: {len(dados_plano.get('conhecimentos', []))} conhecimentos extraídos")
            except Exception as e:
                print(f"[AVISO] Erro ao ler PDF do plano: {e}")

        # ----------------------------------------------------------
        # 2. Lê a Matriz SAEP (opcional)
        # ----------------------------------------------------------
        arquivo_matriz = request.files.get("arquivo_matriz")
        dados_matriz = []
        if arquivo_matriz and arquivo_matriz.filename:
            nome_matriz = secure_filename(arquivo_matriz.filename)
            caminho_matriz = os.path.join(pasta_upload, nome_matriz)
            arquivo_matriz.save(caminho_matriz)
            print(f"[INFO] Matriz SAEP salva: {caminho_matriz}")
            try:
                dados_matriz = ler_matriz_saep(caminho_matriz)
                print(f"[OK] Matriz lida: {len(dados_matriz)} capacidades")
            except Exception as e:
                print(f"[AVISO] Erro ao ler Matriz SAEP: {e}")

        # Dias da semana de aula selecionados pelo professor (0=Seg, ..., 6=Dom)
        dias_semana_raw = request.form.getlist("dias_semana")
        if dias_semana_raw:
            dias_semana = [int(x) for x in dias_semana_raw if str(x).isdigit()]
        else:
            dias_semana = [0, 1, 2, 3, 4]

        # Feriados e recessos municipais / regionais informados
        feriados_json = request.form.get("feriados_json", "[]")
        feriados = []
        try:
            import json
            itens_feriados = json.loads(feriados_json) if feriados_json else []
            for item in itens_feriados:
                if isinstance(item, dict) and "data" in item:
                    feriados.append(item["data"])
                elif isinstance(item, str) and item.strip():
                    feriados.append(item.strip())
        except Exception as e:
            print(f"[AVISO] Erro ao decodificar feriados_json: {e}")

        feriados_form = request.form.getlist("feriados")
        if feriados_form:
            feriados.extend([f.strip() for f in feriados_form if f.strip()])

        # Frequência / Periodicidade (semanal ou quinzenal / 15 em 15 dias)
        periodicidade = request.form.get("periodicidade", "semanal")

        # ----------------------------------------------------------
        # 3. Gera o Planejamento Docente (Taxonomia de Bloom)
        # ----------------------------------------------------------
        datas = calcular_datas_aulas(
            data_inicio_str,
            total_aulas,
            dias_semana=dias_semana,
            feriados=feriados,
            periodicidade=periodicidade
        )

        data_fim_calculada = datas[-1].strftime("%Y-%m-%d") if datas else data_inicio_str
        if not data_fim_str:
            data_fim_str = data_fim_calculada

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
        print(f"[OK] Excel do Planejamento Docente gerado com sucesso: {caminho_excel}")

        # ----------------------------------------------------------
        # 4. Salva o Planejamento Docente e gera automaticamente os Planos de Aula
        # ----------------------------------------------------------
        conn, cursor = get_cursor()
        try:
            # 4.1 Cria o registro do curso em cursos_plano
            cursor.execute(
                """
                INSERT INTO cursos_plano (nome_curso, carga_horaria, aulas_por_dia, usuario_id)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (f"{nome_curso} — {unidade_curricular}", carga_horaria, horas_por_dia, session["usuario_id"])
            )
            curso_id = cursor.fetchone()[0]

            # 4.2 Salva o Planejamento Docente com curso_id vinculado
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
                    curso_id,
                    usuario_id,
                    modalidade
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
                    curso_id,
                    session["usuario_id"],
                    modalidade
                )
            )
            planejamento_id = cursor.fetchone()[0]
            conn.commit()
            print(f"[OK] Planejamento Docente #{planejamento_id} (Curso #{curso_id}) salvo com sucesso!")
        finally:
            release_cursor(conn, cursor)

        print(f"[OK] Planejamento Docente pronto!")
        print(f"[INFO] Disponibilizando arquivo Excel para download imediato...")
        print("=" * 60)

        # Redireciona para a lista de planejamentos com download automático
        return redirect(f"/listar_planejamentos?sucesso=1&download={planejamento_id}")

    return render_template("planejamento_docente.html")


# =========================
# LISTAR PLANEJAMENTOS DOCENTES
# =========================
@app.route("/listar_planejamentos")
def listar_planejamentos():

    if "usuario_id" not in session:
        return redirect("/login")

    conn, cursor = get_cursor()
    try:
        sql_select = """
            SELECT 
                p.id,
                p.nome_curso,
                p.unidade_curricular,
                p.turma,
                p.unidade_escolar,
                p.carga_horaria,
                p.horas_por_dia,
                p.data_inicio,
                p.data_fim,
                p.total_aulas,
                p.arquivo_excel,
                p.usuario_id,
                p.data_criacao,
                p.curso_id,
                p.modalidade,
                COALESCE(
                    (SELECT COUNT(*) FROM planos_aula pa WHERE pa.planejamento_id = p.id),
                    (SELECT COUNT(*) FROM planos_aula pa WHERE p.curso_id IS NOT NULL AND pa.curso_id = p.curso_id),
                    0
                ) AS qtd_planos
            FROM planejamentos_docente p
        """

        if session["perfil"] == "admin":
            cursor.execute(sql_select + " ORDER BY p.id DESC")
        else:
            cursor.execute(sql_select + " WHERE p.usuario_id = %s ORDER BY p.id DESC", (session["usuario_id"],))

        planejamentos = cursor.fetchall()
    finally:
        release_cursor(conn, cursor)

    return render_template(
        "listar_planejamentos.html",
        planejamentos=planejamentos
    )


# =========================
# BAIXAR PLANEJAMENTO DOCENTE (EXCEL)
# =========================
@app.route("/baixar_planejamento/<int:planejamento_id>")
def baixar_planejamento(planejamento_id):

    if "usuario_id" not in session:
        return redirect("/login")

    conn, cursor = get_cursor()
    try:
        if session["perfil"] == "admin":
            cursor.execute(
                "SELECT id, arquivo_excel FROM planejamentos_docente WHERE id = %s",
                (planejamento_id,)
            )
        else:
            cursor.execute(
                "SELECT id, arquivo_excel FROM planejamentos_docente WHERE id = %s AND usuario_id = %s",
                (planejamento_id, session["usuario_id"])
            )
        planejamento = cursor.fetchone()
    finally:
        release_cursor(conn, cursor)

    if not planejamento:
        return "Planejamento não encontrado", 404

    nome_arquivo = planejamento[1]  # coluna arquivo_excel
    caminho = os.path.join("outputs", nome_arquivo)

    if not os.path.exists(caminho):
        return "Arquivo Excel não encontrado no servidor. Por favor, gere novamente.", 404

    return send_file(
        caminho,
        as_attachment=True,
        download_name=nome_arquivo
    )


# =========================
# DELETAR PLANEJAMENTO DOCENTE
# =========================
@app.route("/deletar_planejamento/<int:planejamento_id>")
def deletar_planejamento(planejamento_id):

    if "usuario_id" not in session:
        return redirect("/login")

    conn, cursor = get_cursor()
    try:
        if session["perfil"] == "admin":
            cursor.execute(
                "SELECT id, arquivo_excel FROM planejamentos_docente WHERE id = %s",
                (planejamento_id,)
            )
        else:
            cursor.execute(
                "SELECT id, arquivo_excel FROM planejamentos_docente WHERE id = %s AND usuario_id = %s",
                (planejamento_id, session["usuario_id"])
            )
        planejamento = cursor.fetchone()

        if not planejamento:
            return "Planejamento não encontrado", 404

        # Remove o arquivo Excel do disco, se existir
        nome_arquivo = planejamento[1]
        if nome_arquivo:
            caminho = os.path.join("outputs", nome_arquivo)
            if os.path.exists(caminho):
                os.remove(caminho)
                print(f"[INFO] Arquivo Excel removido: {caminho}")

        cursor.execute(
            "DELETE FROM planejamentos_docente WHERE id = %s",
            (planejamento_id,)
        )
        conn.commit()
        print(f"[INFO] Planejamento Docente #{planejamento_id} deletado")
    finally:
        release_cursor(conn, cursor)

    return redirect("/listar_planejamentos")



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
            """
            SELECT id, nome_curso, unidade_curricular, turma, unidade_escolar,
                   carga_horaria, horas_por_dia, data_inicio, data_fim, total_aulas,
                   arquivo_excel, usuario_id, data_criacao, curso_id, modalidade
            FROM planejamentos_docente
            WHERE id = %s
            """,
            (planejamento_id,)
        )
        plan = cursor.fetchone()
    finally:
        release_cursor(conn, cursor)

    if not plan:
        return "Planejamento não encontrado", 404

    # Verifica permissão: dono ou admin
    if session.get("perfil") != "admin" and plan[11] != session["usuario_id"]:
        return "Acesso não autorizado", 403

    p_id = plan[0]
    nome_curso = plan[1]
    uc = plan[2]
    turma = plan[3]
    unidade_escolar = plan[4]
    ch = plan[5]
    hd = plan[6]
    data_inicio = plan[7]
    data_fim = plan[8]
    total_aulas = plan[9]
    nome_arquivo_excel = plan[10]
    dono_id = plan[11]
    curso_id = plan[13]

    # 1. Se já tem planos gerados e curso_id vinculado, vai direto para o curso
    conn, cursor = get_cursor()
    try:
        qtd = 0
        if curso_id:
            cursor.execute("SELECT COUNT(*) FROM planos_aula WHERE curso_id = %s", (curso_id,))
            qtd = cursor.fetchone()[0]
        if qtd == 0:
            cursor.execute("SELECT COUNT(*) FROM planos_aula WHERE planejamento_id = %s", (p_id,))
            qtd = cursor.fetchone()[0]

        if qtd > 0:
            if not curso_id:
                cursor.execute("SELECT curso_id FROM planos_aula WHERE planejamento_id = %s LIMIT 1", (p_id,))
                c_row = cursor.fetchone()
                if c_row and c_row[0]:
                    curso_id = c_row[0]
                    cursor.execute("UPDATE planejamentos_docente SET curso_id = %s WHERE id = %s", (curso_id, p_id))
                    conn.commit()
            if curso_id:
                return redirect(f"/curso/{curso_id}")
    finally:
        release_cursor(conn, cursor)

    # 2. Lê as aulas estruturadas da planilha Excel do planejamento
    caminho_excel = os.path.join("outputs", nome_arquivo_excel) if nome_arquivo_excel else ""
    aulas_excel = []
    if caminho_excel and os.path.exists(caminho_excel):
        try:
            _, aulas_excel = ler_excel_planejamento_docente(caminho_excel)
        except Exception as e:
            print(f"[AVISO] Erro ao ler Excel do planejamento #{p_id}: {e}")

    # 3. Cria ou vincula o curso na tabela cursos_plano
    conn, cursor = get_cursor()
    try:
        if not curso_id:
            cursor.execute(
                """
                INSERT INTO cursos_plano (nome_curso, carga_horaria, aulas_por_dia, usuario_id)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (f"{nome_curso} — {uc}", ch, hd, dono_id)
            )
            curso_id = cursor.fetchone()[0]

            cursor.execute(
                "UPDATE planejamentos_docente SET curso_id = %s WHERE id = %s",
                (curso_id, p_id)
            )
            conn.commit()
    finally:
        release_cursor(conn, cursor)

    # 4. Fallback caso não tenha conseguido ler do Excel
    if not aulas_excel:
        datas = calcular_datas_aulas(str(data_inicio) if data_inicio else None, total_aulas)
        dados_plano = {"unidade_curricular": uc, "conhecimentos": []}
        aulas_excel = gerar_planejamento_ia(dados_plano, [], total_aulas, hd, datas)

    # 5. Gera os planos de aula detalhados
    planos_gerados = gerar_todos_planos_de_planejamento(
        aulas_excel,
        nome_curso,
        uc,
        hd,
        max_workers=2
    )

    # 6. Salva no banco de dados vinculando curso_id e planejamento_id
    planos_completos = ""
    conn, cursor = get_cursor()
    try:
        cursor.execute("DELETE FROM planos_aula WHERE curso_id = %s OR planejamento_id = %s", (curso_id, p_id))
        for dia, plano_texto in enumerate(planos_gerados, start=1):
            planos_completos += f"\n\nDIA {dia}\n\n{plano_texto}"
            cursor.execute(
                """
                INSERT INTO planos_aula (curso_id, dia, tema, plano_gerado, usuario_id, planejamento_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (curso_id, dia, f"Plano Dia {dia} — {uc}", plano_texto, dono_id, p_id)
            )
        conn.commit()
        print(f"[OK] {len(planos_gerados)} Planos de Aula gerados e salvos para o Planejamento #{p_id} (Curso #{curso_id})!")
    finally:
        release_cursor(conn, cursor)

    # 7. Gera DOCX e PDF consolidados do curso
    try:
        os.makedirs("outputs", exist_ok=True)
        arquivo_docx = f"outputs/plano_{curso_id}.docx"
        arquivo_pdf = f"outputs/plano_{curso_id}.pdf"
        gerar_docx_plano(
            titulo="PLANO DE AULA",
            subtitulo=f"Curso: {nome_curso} — {uc}",
            conteudo=planos_completos,
            caminho_saida=arquivo_docx
        )
        gerar_pdf_plano(arquivo_docx, arquivo_pdf)
    except Exception as e:
        print(f"[AVISO] Erro ao consolidar DOCX/PDF: {e}")

    return redirect(f"/curso/{curso_id}")


# =========================
# START
# =========================
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        threaded=True
    )