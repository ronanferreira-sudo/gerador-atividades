from docx2pdf import convert


def gerar_pdf_atividade(
    arquivo_docx,
    arquivo_pdf
):

    convert(
        arquivo_docx,
        arquivo_pdf
    )

    print("PDF DA ATIVIDADE GERADO COM SUCESSO")