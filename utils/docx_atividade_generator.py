from docxtpl import DocxTemplate
import os


def gerar_docx_atividade(
    titulo,
    conteudo,
    caminho_saida,
    subtitulo="",
    dados_cabecalho=None
):
    doc = DocxTemplate("templates/modelo_atividade.docx")

    if not dados_cabecalho:
        dados_cabecalho = {}

    curso_val = dados_cabecalho.get("curso") or subtitulo or ""
    uc_val = dados_cabecalho.get("unidade_curricular") or ""
    aula_val = dados_cabecalho.get("aula_encontro") or "Encontro Regular"
    bloom_val = dados_cabecalho.get("nivel_bloom") or "Lembrar"

    contexto = {
        "titulo": titulo or "ATIVIDADE AVALIATIVA",
        "subtitulo": subtitulo,
        "curso": curso_val,
        "unidade_curricular": uc_val,
        "aula_encontro": aula_val,
        "nivel_bloom": bloom_val,
        "conteudo": conteudo
    }

    doc.render(contexto)

    pasta = os.path.dirname(caminho_saida)
    if pasta:
        os.makedirs(pasta, exist_ok=True)

    doc.save(caminho_saida)
