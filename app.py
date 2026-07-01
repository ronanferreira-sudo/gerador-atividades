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
from ia.plano_aula import gerar_todos_planos, gerar_plano_aula

from utils.docx_generator import gerar_docx_plano
from utils.pdf_generator import gerar_pdf_plano

from utils.docx_atividade_generator import gerar_docx_atividade
from utils.pdf_atividade_generator import gerar_pdf_atividade

from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.excel_reader import extrair_dados_excel, formatar_dados_para_prompt, contar_itens
import os


app = Flask(__name__)
app.secret_key = "gerador_atividades_2026"


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

        return "Login inválido"

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
        return "Atividade não encontrada"

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
        return "Atividade não encontrada"

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

    # Se o PDF falhar (exemplo: Word não instalado), envia o DOCX como fallback
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
        return "Atividade não encontrada"

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
        return "Atividade não encontrada"

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

        else:

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
                (session["usuario_id"],),
            )

        cursos = cursor.fetchall()
    finally:
        release_cursor(conn, cursor)

    return render_template(
        "dashboard.html",
        cursos=cursos
    )


# =========================
# PLANOS DE AULA
# =========================
@app.route("/planos", methods=["GET", "POST"])
def planos():

    if "usuario_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        nome_curso = request.form["nome_curso"]
        carga_horaria = int(request.form["carga_horaria"])
        aulas_por_dia = int(request.form["aulas_por_dia"])

        print("=" * 60)
        print(f"📚 INICIANDO GERAÇÃO DE PLANOS")
        print(f"   Curso: {nome_curso}")
        print(f"   Carga Horária: {carga_horaria}h")
        print(f"   Aulas por dia: {aulas_por_dia}h")
        print("=" * 60)

        arquivo = request.files["arquivo_pdf"]
        nome_arquivo = secure_filename(arquivo.filename)

        pasta_upload = "uploads"
        os.makedirs(pasta_upload, exist_ok=True)

        caminho = os.path.join(pasta_upload, nome_arquivo)
        arquivo.save(caminho)

        # Detecta se é Excel (.xlsx) ou PDF
        is_excel = nome_arquivo.lower().endswith(('.xlsx', '.xls'))

        if is_excel:
            print("📊 Arquivo Excel detectado! Extraindo dados da Matriz de Referência...")
            dados_excel = extrair_dados_excel(caminho)
            texto = formatar_dados_para_prompt(dados_excel)
            print(f"📊 Dados extraídos: {len(dados_excel)} itens encontrados")
        else:
            print("📄 Arquivo PDF detectado! Extraindo texto...")
            reader = PdfReader(caminho)
            texto = ""
            for pagina in reader.pages:
                conteudo = pagina.extract_text()
                if conteudo:
                    texto += conteudo + "\n"

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
                    nome_curso,
                    carga_horaria,
                    aulas_por_dia,
                    session["usuario_id"]
                )
            )

            curso_id = cursor.fetchone()[0]

            conn.commit()
        finally:
            release_cursor(conn, cursor)

        total_dias = carga_horaria // aulas_por_dia

        # 🔥 GERA TODOS OS PLANOS EM PARALELO
        planos = gerar_todos_planos(
            texto,
            carga_horaria,
            aulas_por_dia,
            total_dias,
            max_workers=2
        )

        planos_completos = ""

        conn, cursor = get_cursor()
        try:
            for dia, plano in enumerate(planos, start=1):

                planos_completos += f"\n\nDIA {dia}\n\n{plano}"

                cursor.execute(
                    """
                    INSERT INTO planos_aula (
                        curso_id,
                        dia,
                        tema,
                        plano_gerado,
                        usuario_id
                    )
                    VALUES (%s,%s,%s,%s,%s)
                    """,
                    (
                        curso_id,
                        dia,
                        f"Plano Dia {dia}",
                        plano,
                        session["usuario_id"]
                    )
                )

            conn.commit()
        finally:
            release_cursor(conn, cursor)

        os.makedirs("outputs", exist_ok=True)

        arquivo_docx = f"outputs/plano_{curso_id}.docx"
        arquivo_pdf = f"outputs/plano_{curso_id}.pdf"

        gerar_docx_plano(
            titulo="PLANO DE AULA",
            subtitulo=f"Curso: {nome_curso}",
            conteudo=planos_completos,
            caminho_saida=arquivo_docx
        )

        resultado_pdf = gerar_pdf_plano(
            arquivo_docx,
            arquivo_pdf
        )

        if not resultado_pdf:
            print("⚠️ PDF não foi gerado (apenas DOCX foi salvo)")

        return redirect("/listar_cursos")

    return render_template("planos.html")


# =========================
# LISTAR PLANOS
# =========================
@app.route("/listar_planos")
def listar_planos():

    if "usuario_id" not in session:
        return redirect("/login")

    conn, cursor = get_cursor()
    try:
        if session["perfil"] == "admin":

            cursor.execute(
                """
                SELECT *
                FROM planos_aula
                ORDER BY id DESC
                """
            )

        else:

            cursor.execute(
                """
                SELECT *
                FROM planos_aula
                WHERE usuario_id = %s
                ORDER BY id DESC
                """,
                (session["usuario_id"],),
            )

        planos = cursor.fetchall()
    finally:
        release_cursor(conn, cursor)

    return render_template(
        "listar_planos.html",
        planos=planos
    )


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
        return "Plano não encontrado"

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
        return "Plano não encontrado"

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
    dificuldade = request.args.get("dificuldade", "médio")

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
        return "Plano não encontrado"

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
        nome_curso = "Curso não encontrado"

    # =========================
    # GERAR ATIVIDADE COM IA
    # =========================
    print(f"🤖 Gerando atividade a partir do Plano #{id}")
    print(f"   Curso: {nome_curso} | Tipo: {tipo} | Dificuldade: {dificuldade} | Qtd: {quantidade}")

    atividade = gerar_atividade(
        conteudo,
        dificuldade,
        tipo,
        quantidade
    )

    print(f"✅ Atividade gerada com sucesso ({len(atividade)} caracteres)")
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
        return "Plano não encontrado"

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
# START
# =========================
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        threaded=True
    )