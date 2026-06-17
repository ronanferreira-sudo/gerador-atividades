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

from database.conexao import conexao, cursor

from ia.gerador import gerar_atividade
from ia.plano_aula import gerar_plano_aula

from utils.docx_generator import gerar_docx_plano
from utils.pdf_generator import gerar_pdf_plano

from utils.docx_atividade_generator import gerar_docx_atividade
from utils.pdf_atividade_generator import gerar_pdf_atividade

import os


app = Flask(__name__)
app.secret_key = "gerador_atividades_2026"


def pode_acessar_atividade(id):

    if "usuario_id" not in session:
        return False

    if session.get("perfil") == "admin":
        return True

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

    return atividade[0] == session["usuario_id"]


# =========================
# LOGIN
# =========================
@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():

    if request.method == "POST":

        nome = request.form["nome"]
        email = request.form["email"]
        senha = request.form["senha"]

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

        conexao.commit()

        return redirect("/login")

    return render_template("cadastro.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        senha = request.form["senha"]

        cursor.execute(
            """
            SELECT id, nome, email, perfil
            FROM usuarios
            WHERE email=%s AND senha=%s
            """,
            (email, senha),
        )

        usuario = cursor.fetchone()

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

        conexao.commit()

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

    return render_template(
        "atividades.html",
        atividades=dados
    )


# =========================
# DELETE
# =========================
@app.route("/deletar/<int:id>")
def deletar(id):

    if not pode_acessar_atividade(id):
        return "Acesso negado"

    cursor.execute(
        "DELETE FROM atividades WHERE id=%s",
        (id,)
    )

    conexao.commit()

    return redirect("/atividades")


# =========================
# EDITAR
# =========================
@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):

    if not pode_acessar_atividade(id):
        return "Acesso negado"

    if request.method == "POST":

        curso = request.form["curso"]
        disciplina = request.form["disciplina"]
        conteudo = request.form["conteudo"]
        dificuldade = request.form["dificuldade"]
        atividade_gerada = request.form["atividade_gerada"]

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

        conexao.commit()

        return redirect("/atividades")

    cursor.execute(
        "SELECT * FROM atividades WHERE id=%s",
        (id,)
    )

    atividade = cursor.fetchone()

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

    if not pode_acessar_atividade(id):
        return "Acesso negado"

    cursor.execute(
        """
        SELECT *
        FROM atividades
        WHERE id=%s
        """,
        (id,)
    )

    atividade = cursor.fetchone()

    if not atividade:
        return "Atividade não encontrada"

    arquivo_docx = f"atividade_{id}.docx"
    arquivo_pdf = f"atividade_{id}.pdf"

    # Gera o Word usando o modelo
    gerar_docx_atividade(
        titulo=f"{atividade[1]} - {atividade[2]}",
        conteudo=atividade[5],
        caminho_saida=arquivo_docx
    )

    # Converte Word em PDF
    gerar_pdf_atividade(
        arquivo_docx,
        arquivo_pdf
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
    if not pode_acessar_atividade(id):
        return "Acesso negado"

    cursor.execute("SELECT * FROM atividades WHERE id=%s", (id,))
    atividade = cursor.fetchone()

    arquivo = f"atividade_{id}.docx"

    gerar_docx_atividade(
    titulo=f"{atividade[1]} - {atividade[2]}",
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
    if not pode_acessar_atividade(id):
        return "Acesso negado"

    cursor.execute(
        """
        SELECT conteudo, dificuldade
        FROM atividades
        WHERE id=%s
    """,
        (id,),
    )

    atividade = cursor.fetchone()

    nova = gerar_atividade(atividade[0], atividade[1])

    cursor.execute(
        """
        UPDATE atividades
        SET atividade_gerada=%s
        WHERE id=%s
    """,
        (nova, id),
    )

    conexao.commit()

    return redirect("/atividades")


# =========================
# DASHBOARD
# =========================
@app.route("/dashboard")
def dashboard():

    cursor.execute("""
        SELECT
            curso,
            COUNT(*)
        FROM atividades
        GROUP BY curso
        ORDER BY curso
    """)

    cursos = cursor.fetchall()

    return render_template("dashboard.html", cursos=cursos)


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

        arquivo = request.files["arquivo_pdf"]
        nome_arquivo = secure_filename(arquivo.filename)

        pasta_upload = "uploads"
        if not os.path.exists(pasta_upload):
            os.makedirs(pasta_upload)

        caminho = os.path.join(pasta_upload, nome_arquivo)
        arquivo.save(caminho)

        print("PDF salvo!")

        # =========================
        # EXTRAÇÃO DE TEXTO
        # =========================
        reader = PdfReader(caminho)

        texto = ""
        for pagina in reader.pages:
            conteudo = pagina.extract_text()
            if conteudo:
                texto += conteudo + "\n"

        print("Texto extraído!")
        print("Quantidade de caracteres:", len(texto))

        # =========================
        # SALVAR CURSO
        # =========================
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
        conexao.commit()

        print("Curso salvo!")

        # =========================
        # IMPORTS (CORRETO AQUI)
        # =========================
        from utils.docx_generator import gerar_docx_plano
        from utils.pdf_generator import gerar_pdf_plano
        from utils.plano_padrao import formatar_plano

        # =========================
        # GERAR PLANOS
        # =========================
        total_dias = carga_horaria // aulas_por_dia

        print(f"Total de dias: {total_dias}")

        planos_completos = ""

        for dia in range(1, total_dias + 1):

            print(f"Gerando plano do dia {dia}...")

            plano_bruto = gerar_plano_aula(
                texto,
                carga_horaria,
                aulas_por_dia,
                dia
            )

            plano = formatar_plano(plano_bruto)

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

            conexao.commit()

            print(f"Plano do dia {dia} salvo!")

        print("Todos os planos foram gerados e salvos!")
        print(os.path.abspath("static/img/logo.jpg"))
        print(os.path.exists("static/img/logo.jpg"))

        # =========================
        # OUTPUT WORD
        # =========================
        gerar_docx_plano(
            titulo="PLANO DE AULA",
            subtitulo=f"Curso: {nome_curso}",
            conteudo=planos_completos,
            caminho_saida=f"outputs/plano_{curso_id}.docx",
            logo_path="static/img/logo.jpg"
        )   
        print("Word gerado com sucesso!")

        # =========================
        # OUTPUT PDF
        # =========================
        gerar_pdf_plano(
            titulo="PLANO DE AULA",
            subtitulo=f"Curso: {nome_curso}",
            conteudo=planos_completos,
            caminho_saida=f"outputs/plano_{curso_id}.pdf",
            logo_path="static/img/logo.jpg"
        )
        print("PDF gerado com sucesso!")

        return redirect("/listar_cursos")

    return render_template("planos.html")
# =========================
# LISTAR PLANOS
# =========================
@app.route("/listar_planos")
def listar_planos():

    if "usuario_id" not in session:
        return redirect("/login")

    if session["perfil"] == "admin":

        cursor.execute("""
            SELECT *
            FROM planos_aula
            ORDER BY id DESC
        """)

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

    return render_template("listar_planos.html", planos=planos)


# =========================
# VISUALIZAR PLANOS
# =========================


@app.route("/plano/<int:plano_id>")
def visualizar_plano(plano_id):

    cursor.execute(
        """
        SELECT *
        FROM planos_aula
        WHERE id = %s
    """,
        (plano_id,),
    )

    plano = cursor.fetchone()

    print("PLANO:", plano)  # DEBUG IMPORTANTE

    return render_template("visualizar_plano.html", plano=plano)


# =========================
# LISTAR CURSOS
# =========================
@app.route("/listar_cursos")
def listar_cursos():

    if "usuario_id" not in session:
        return redirect("/login")

    if session["perfil"] == "admin":

        cursor.execute("""
            SELECT *
            FROM cursos_plano
            ORDER BY id DESC
        """)

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

    return render_template("listar_cursos.html", cursos=cursos)


# =========================
# VISUALIZAR CURSO
# =========================
@app.route("/curso/<int:curso_id>")
def visualizar_curso(curso_id):

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

    return render_template("planos_curso.html", planos=planos, curso_id=curso_id)


# =========================
# plano pdf
# =========================
@app.route("/plano_pdf/<int:id>")
def plano_pdf(id):

    cursor.execute(
        """
        SELECT *
        FROM planos_aula
        WHERE id=%s
        """,
        (id,)
    )

    plano = cursor.fetchone()

    if not plano:
        return "Plano não encontrado"

    arquivo_docx = f"plano_{id}.docx"
    arquivo_pdf = f"plano_{id}.pdf"

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
# plano word
# =========================
@app.route("/plano_word/<int:id>")
def plano_word(id):

    cursor.execute(
        """
        SELECT *
        FROM planos_aula
        WHERE id=%s
        """,
        (id,)
    )

    plano = cursor.fetchone()

    if not plano:
        return "Plano não encontrado"

    arquivo = f"plano_{id}.docx"

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
# plano gerar atividade
# =========================
@app.route("/gerar_atividade_plano/<int:id>")
def gerar_atividade_plano(id):

    tipo = request.args.get("tipo", "objetiva")
    quantidade = request.args.get("quantidade", 5)

    # =========================
    # BUSCAR PLANO
    # =========================
    cursor.execute(
        """
        SELECT *
        FROM planos_aula
        WHERE id = %s
    """,
        (id,),
    )

    plano = cursor.fetchone()

    if not plano:
        return "Plano não encontrado"

    conteudo = plano[4]
    curso_id = plano[1]

    # =========================
    # BUSCAR NOME DO CURSO
    # =========================
    cursor.execute(
        """
        SELECT nome_curso
        FROM cursos_plano
        WHERE id = %s
    """,
        (curso_id,),
    )

    curso = cursor.fetchone()

    nome_curso = curso[0] if curso else "Curso não encontrado"

    # =========================
    # GERAR ATIVIDADE IA
    # =========================
    atividade = gerar_atividade(conteudo, "médio", tipo, quantidade)

    # =========================
    # SALVAR NO BANCO
    # =========================
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
            "médio",
            atividade,
            session["usuario_id"],
        ),
    )

    conexao.commit()

    return redirect("/atividades")

# =========================
# download plano
# =========================
@app.route("/baixar_plano/<int:plano_id>")
def baixar_plano(plano_id):

    cursor.execute("""
        SELECT *
        FROM planos_aula
        WHERE id=%s
    """, (plano_id,))

    plano = cursor.fetchone()

    if not plano:
        return "Plano não encontrado"

    arquivo = f"temp/plano_{plano_id}.docx"

    gerar_docx_plano(
        titulo="PLANO DE AULA",
        subtitulo=f"Dia {plano[2]}",
        conteudo=plano[4],
        caminho_saida=arquivo,
        logo_path="static/img/logo.jpg"
    )

    return send_file(
        arquivo,
        as_attachment=True
    )
# =========================
# START
# =========================
if __name__ == "__main__":
    app.run(debug=True)
