from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    send_file
)

from werkzeug.utils import secure_filename

from PyPDF2 import PdfReader

from database.conexao import get_cursor, release_cursor

from ia.gerador import gerar_atividade
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
import os


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "gerador_atividades_2026")


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

        nome = request.form["nome"]
        email = request.form["email"]
        senha = request.form["senha"]

        conn, cursor = get_cursor()
        try:
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
                (nome, email, senha, "professor"),
            )

            conn.commit()
        finally:
            release_cursor(conn, cursor)

        return redirect("/login")

    return render_template("cadastro.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        senha = request.form["senha"]

        conn, cursor = get_cursor()
        try:
            cursor.execute(
                """
                SELECT id, nome, email, perfil
                FROM usuarios
                WHERE email=%s AND senha=%s
                """,
                (email, senha),
            )

            usuario = cursor.fetchone()
        finally:
            release_cursor(conn, cursor)

        if usuario:
            session["usuario_id"] = usuario[0]
            session["nome"] = usuario[1]
            session["perfil"] = usuario[3]

            return redirect("/dashboard")

        return "Login invÃ¡lido"

    return render_template("login.html")


@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# =========================
# INDEX (GERAR IA)
# =========================
@app.route("/", methods=["GET", "POST"])
def index():

    if "usuario_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        curso = request.form["curso"]
        disciplina = request.form["disciplina"]
        conteudo = request.form["conteudo"]
        dificuldade = request.form["dificuldade"]
        tipo = request.form["tipo"]
        quantidade = request.form["quantidade"]

        atividade_gerada = gerar_atividade(
            conteudo,
            dificuldade,
            tipo,
            quantidade
        )

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
                    usuario_id
                )
                VALUES (%s,%s,%s,%s,%s,%s)
                """,
                (
                    curso,
                    disciplina,
                    conteudo,
                    dificuldade,
                    atividade_gerada,
                    session["usuario_id"]
                ),
            )

            conn.commit()
        finally:
            release_cursor(conn, cursor)

        return redirect("/atividades")

    return render_template("index.html")


# =========================
# LISTAR + PESQUISA
# =========================
@app.route("/atividades")
def atividades():

    if "usuario_id" not in session:
        return redirect("/login")

    busca = request.args.get("busca")

    conn, cursor = get_cursor()
    try:
        if session["perfil"] == "admin":

            if busca:

                cursor.execute(
                    """
                    SELECT *
                    FROM atividades
                    WHERE curso ILIKE %s
                       OR disciplina ILIKE %s
                       OR conteudo ILIKE %s
                    ORDER BY id DESC
                    """,
                    (f"%{busca}%", f"%{busca}%", f"%{busca}%"),
                )

            else:

                cursor.execute(
                    """
                    SELECT *
                    FROM atividades
                    ORDER BY id DESC
                    """
                )

        else:

            if busca:

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
                    """,
                    (
                        session["usuario_id"],
                        f"%{busca}%",
                        f"%{busca}%",
                        f"%{busca}%"
                    ),
                )

            else:

                cursor.execute(
                    """
                    SELECT *
                    FROM atividades
                    WHERE usuario_id = %s
                    ORDER BY id DESC
                    """,
                    (session["usuario_id"],),
                )

        dados = cursor.fetchall()
    finally:
        release_cursor(conn, cursor)

    return render_template(
        "atividades.html",
        atividades=dados
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

    gerar_docx_atividade(
        titulo=f"{atividade[1]} - {atividade[2]}",
        subtitulo=atividade[1],
        conteudo=atividade[5],
        caminho_saida=arquivo_docx
    )

    resultado = gerar_pdf_atividade(
        arquivo_docx,
        arquivo_pdf
    )

    # Se o PDF falhar (exemplo: Word nÃ£o instalado), envia o DOCX como fallback
    if not resultado:
        return send_file(
            arquivo_docx,
            as_attachment=True,
            download_name=f"atividade_{id}.docx"
        )

    return send_file(
        arquivo_pdf,
        as_attachment=True
    )


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
        return "Atividade nÃ£o encontrada"

    arquivo = f"outputs/atividade_{id}.docx"

    gerar_docx_atividade(
        titulo=f"{atividade[1]} - {atividade[2]}",
        subtitulo=atividade[1],
        conteudo=atividade[5],
        caminho_saida=arquivo
    )

    return send_file(
        arquivo,
        as_attachment=True
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

        print(f"✅ {len(planos)} Planos de aula gerados para o Curso #{curso_id}!")
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

    gerar_pdf_plano(
        arquivo_docx,
        arquivo_pdf
    )

    return send_file(
        arquivo_pdf,
        as_attachment=True
    )


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
        return "Plano nÃ£o encontrado"

    arquivo = f"outputs/plano_{id}.docx"

    gerar_docx_plano(
        titulo="PLANO DE AULA",
        subtitulo=plano[3],
        conteudo=plano[4],
        caminho_saida=arquivo
    )

    return send_file(
        arquivo,
        as_attachment=True
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
        cursor.execute(
            """
            INSERT INTO atividades (
                curso,
                disciplina,
                conteudo,
                dificuldade,
                atividade_gerada,
                usuario_id
            )
            VALUES (%s,%s,%s,%s,%s,%s)
            """,
            (
                nome_curso,
                "Plano de Aula",
                conteudo[:200],
                dificuldade,
                atividade,
                session["usuario_id"]
            ),
        )

        conn.commit()
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


# =========================
# LISTAR PLANEJAMENTOS DOCENTES
# =========================
@app.route("/listar_planejamentos")
def listar_planejamentos():

    if "usuario_id" not in session:
        return redirect("/login")

    conn, cursor = get_cursor()
    try:
        if session["perfil"] == "admin":
            cursor.execute(
                """
                SELECT *
                FROM planejamentos_docente
                ORDER BY id DESC
                """
            )
        else:
            cursor.execute(
                """
                SELECT *
                FROM planejamentos_docente
                WHERE usuario_id = %s
                ORDER BY id DESC
                """,
                (session["usuario_id"],)
            )

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
                "SELECT * FROM planejamentos_docente WHERE id = %s",
                (planejamento_id,)
            )
        else:
            cursor.execute(
                "SELECT * FROM planejamentos_docente WHERE id = %s AND usuario_id = %s",
                (planejamento_id, session["usuario_id"])
            )
        planejamento = cursor.fetchone()
    finally:
        release_cursor(conn, cursor)

    if not planejamento:
        return "Planejamento não encontrado", 404

    nome_arquivo = planejamento[10]  # coluna arquivo_excel
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
                print(f"🗑️ Arquivo Excel removido: {caminho}")

        cursor.execute(
            "DELETE FROM planejamentos_docente WHERE id = %s",
            (planejamento_id,)
        )
        conn.commit()
        print(f"🗑️ Planejamento Docente #{planejamento_id} deletado")
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