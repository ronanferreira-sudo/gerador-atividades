from docxtpl import DocxTemplate
import os


def gerar_docx_atividade(
    titulo,
    conteudo,
    caminho_saida
):

    doc = DocxTemplate(
        "templates/modelo_atividade.docx"
    )

    contexto = {
        "titulo": titulo,
        "conteudo": conteudo
    }

    doc.render(contexto)

    pasta = os.path.dirname(caminho_saida)

    if pasta:
        os.makedirs(pasta, exist_ok=True)

    doc.save(caminho_saida)