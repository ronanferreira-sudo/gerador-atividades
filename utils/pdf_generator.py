from docx2pdf import convert
import os


def gerar_pdf_plano(docx_path, pdf_path):

    pasta = os.path.dirname(pdf_path)

    if pasta:
        os.makedirs(pasta, exist_ok=True)

    convert(docx_path, pdf_path)

    print("PDF GERADO COM SUCESSO")