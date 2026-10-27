import pythoncom
from docx2pdf import convert
import os


def gerar_pdf_plano(docx_path, pdf_path):

    try:
        print(f"Convertendo DOCX para PDF: {docx_path} -> {pdf_path}")
        print(f"Arquivo DOCX existe: {os.path.exists(docx_path)}")

        pasta = os.path.dirname(pdf_path)

        if pasta:
            os.makedirs(pasta, exist_ok=True)

        # Inicializa COM para evitar erro CoInitialize no Windows
        pythoncom.CoInitialize()

        convert(docx_path, pdf_path)

        print(f"PDF gerado com sucesso: {os.path.exists(pdf_path)}")
        return True

    except Exception as e:
        print(f"ERRO ao gerar PDF: {e}")
        return False

    finally:
        try:
            pythoncom.CoUninitialize()
        except:
            pass
