import pythoncom
from docx2pdf import convert
import os


def gerar_pdf_atividade(
    arquivo_docx,
    arquivo_pdf
):

    try:
        print(f"Convertendo DOCX para PDF: {arquivo_docx} -> {arquivo_pdf}")
        print(f"Arquivo DOCX existe: {os.path.exists(arquivo_docx)}")

        pasta = os.path.dirname(arquivo_pdf)
        if pasta:
            os.makedirs(pasta, exist_ok=True)

        # Inicializa COM para evitar erro CoInitialize no Windows
        pythoncom.CoInitialize()

        convert(
            arquivo_docx,
            arquivo_pdf
        )

        print(f"PDF gerado com sucesso: {os.path.exists(arquivo_pdf)}")
        return True

    except Exception as e:
        print(f"ERRO ao gerar PDF: {e}")
        return False

    finally:
        try:
            pythoncom.CoUninitialize()
        except:
            pass
