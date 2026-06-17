from docxtpl import DocxTemplate
import os
import re


def extrair_linha(texto, campo):
    match = re.search(
        rf"{campo}\s*:\s*(.+)",
        texto,
        re.IGNORECASE
    )
    return match.group(1).strip() if match else ""


def extrair_bloco(texto, inicio, fim=None):

    try:

        if fim:
            padrao = rf"{inicio}(.*?){fim}"
        else:
            padrao = rf"{inicio}(.*)"

        match = re.search(
            padrao,
            texto,
            re.DOTALL | re.IGNORECASE
        )

        if match:
            return match.group(1).strip()

    except Exception as e:
        print("ERRO EXTRAÇÃO:", e)

    return ""


def gerar_docx_plano(
    titulo,
    subtitulo,
    conteudo,
    caminho_saida,
    logo_path=None
):

    print("USANDO MODELO:", os.path.abspath("templates/modelo.docx"))
    print("EXISTE:", os.path.exists("templates/modelo.docx"))

    doc = DocxTemplate("templates/modelo.docx")

    # =====================
    # CAMPOS DO PLANO
    # =====================

    unidade_curricular = extrair_linha(
        conteudo,
        "Unidade Curricular"
    )

    carga_horaria = extrair_linha(
        conteudo,
        "Carga Horária"
    )

    objetivo_geral = extrair_bloco(
        conteudo,
        "Objetivo Geral:",
        "Objetivos"
    )

    conteudo_programatico = extrair_bloco(
        conteudo,
        "Conteúdo Programático",
        "Estratégia Didática"
    )

    estrategia_didatica = extrair_bloco(
        conteudo,
        "Estratégia Didática",
        "Recursos Didáticos"
    )

    recursos_didaticos = extrair_bloco(
        conteudo,
        "Recursos Didáticos",
        "Avaliação"
    )

    avaliacao = extrair_bloco(
        conteudo,
        "Avaliação"
    )

    print("=== DADOS EXTRAIDOS ===")
    print("UNIDADE:", unidade_curricular)
    print("CARGA:", carga_horaria)
    print("OBJETIVO:", objetivo_geral)

    contexto = {
        "titulo": titulo,
        "subtitulo": unidade_curricular,
        "carga_horaria": carga_horaria,
        "objetivo_geral": objetivo_geral,
        "conteudo_programatico": conteudo_programatico,
        "estrategia_didatica": estrategia_didatica,
        "recursos_didaticos": recursos_didaticos,
        "avaliacao": avaliacao,
    }

    pasta = os.path.dirname(caminho_saida)

    if pasta:
        os.makedirs(pasta, exist_ok=True)

    doc.render(contexto)
    doc.save(caminho_saida)

    print("WORD GERADO COM SUCESSO")