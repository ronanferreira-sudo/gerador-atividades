from docx2pdf import convert
import os


def gerar_pdf_atividade(
    arquivo_docx,
    arquivo_pdf
):

    try:
        print(f"Convertendo DOCX para PDF: {arquivo_docx} -> {arquivo_pdf}")
        print(f"Arquivo DOCX existe: {os.path.exists(arquivo_docx)}")

        convert(
            arquivo_docx,
            arquivo_pdf
        )

        print(f"PDF gerado com sucesso: {os.path.exists(arquivo_pdf)}")
        return True

    except Exception as e:
        print(f"ERRO ao gerar PDF: {e}")
        return False
