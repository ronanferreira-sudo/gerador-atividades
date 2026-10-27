import os
import openpyxl

def ler_matriz_saep(caminho_arquivo):
    """
    Lê a Matriz SAEP (aceita .xlsx ou .xls).
    Retorna uma lista de dicionários com as capacidades e seus níveis de Bloom:
    [
        {
            "capacidade_saep": ...,
            "detalhamento_bloom": ..., # Lembrar, Entender, Aplicar, Analisar, Avaliar, Criar
            "conhecimentos": ...,
            "modulo": ...,
            "unidade_curricular": ...,
            "capacidade_itinerario": ...
        }, ...
    ]
    """
    caminho_xlsx = caminho_arquivo

    # Se for .xls binário do Excel 97-2003, converte para .xlsx usando win32com se disponível
    if caminho_arquivo.lower().endswith(".xls"):
        caminho_convertido = caminho_arquivo + "x"
        if not os.path.exists(caminho_convertido):
            try:
                import win32com.client
                import pythoncom
                pythoncom.CoInitialize()
                excel = win32com.client.Dispatch("Excel.Application")
                excel.Visible = False
                excel.DisplayAlerts = False
                wb_temp = excel.Workbooks.Open(os.path.abspath(caminho_arquivo))
                # 51 = xlOpenXMLWorkbook (.xlsx)
                wb_temp.SaveAs(os.path.abspath(caminho_convertido), FileFormat=51)
                wb_temp.Close(False)
                excel.Quit()
                caminho_xlsx = caminho_convertido
            except Exception as e:
                print(f"Aviso: Não foi possível converter .xls para .xlsx via Excel: {e}")
                # Se falhar a conversão via COM, tenta ler diretamente via COM
                return _ler_matriz_via_com(caminho_arquivo)
        else:
            caminho_xlsx = caminho_convertido

    return _ler_matriz_openpyxl(caminho_xlsx)


def _ler_matriz_openpyxl(caminho_xlsx):
    wb = openpyxl.load_workbook(caminho_xlsx, data_only=True)
    itens = []

    # Procura a aba 'Detalhamento' ou a primeira aba
    nome_aba = "Detalhamento" if "Detalhamento" in wb.sheetnames else wb.sheetnames[0]
    ws = wb[nome_aba]

    # Procura as colunas de cabeçalho
    col_cap_saep = 1
    col_bloom = 2
    col_conhec = 3
    col_modulo = 4
    col_uc = 5
    col_cap_itin = 6

    # Varre as linhas
    bloom_atual = "Entender"
    cap_saep_atual = ""
    uc_atual = ""
    modulo_atual = ""

    for r in range(2, ws.max_row + 1):
        v_cap_saep = ws.cell(r, col_cap_saep).value
        v_bloom = ws.cell(r, col_bloom).value
        v_conhec = ws.cell(r, col_conhec).value
        v_modulo = ws.cell(r, col_modulo).value
        v_uc = ws.cell(r, col_uc).value
        v_cap_itin = ws.cell(r, col_cap_itin).value

        # Linhas mescladas mantêm o contexto anterior
        if v_cap_saep and str(v_cap_saep).strip():
            cap_saep_atual = str(v_cap_saep).strip()
        if v_bloom and str(v_bloom).strip():
            bloom_atual = str(v_bloom).strip()
        if v_modulo and str(v_modulo).strip():
            modulo_atual = str(v_modulo).strip()
        if v_uc and str(v_uc).strip():
            uc_atual = str(v_uc).strip()

        # Se houver capacidade do itinerário ou capacidade SAEP
        texto_cap = str(v_cap_itin).strip() if v_cap_itin else (str(v_cap_saep).strip() if v_cap_saep else "")
        if texto_cap and not texto_cap.upper().startswith("CAPACIDADES"):
            itens.append({
                "capacidade_saep": cap_saep_atual,
                "detalhamento_bloom": bloom_atual,
                "conhecimentos": str(v_conhec).strip() if v_conhec else "",
                "modulo": modulo_atual,
                "unidade_curricular": uc_atual,
                "capacidade_itinerario": texto_cap
            })

    wb.close()
    return itens


def _ler_matriz_via_com(caminho_arquivo):
    itens = []
    try:
        import win32com.client
        import pythoncom
        pythoncom.CoInitialize()
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        wb = excel.Workbooks.Open(os.path.abspath(caminho_arquivo))
        try:
            ws = wb.Sheets("Detalhamento")
        except:
            ws = wb.Sheets(1)

        total_linhas = ws.UsedRange.Rows.Count
        bloom_atual = "Entender"
        cap_saep_atual = ""
        uc_atual = ""
        modulo_atual = ""

        for r in range(2, total_linhas + 1):
            v_cap_saep = ws.Cells(r, 1).Value
            v_bloom = ws.Cells(r, 2).Value
            v_conhec = ws.Cells(r, 3).Value
            v_modulo = ws.Cells(r, 4).Value
            v_uc = ws.Cells(r, 5).Value
            v_cap_itin = ws.Cells(r, 6).Value

            if v_cap_saep and str(v_cap_saep).strip():
                cap_saep_atual = str(v_cap_saep).strip()
            if v_bloom and str(v_bloom).strip():
                bloom_atual = str(v_bloom).strip()
            if v_modulo and str(v_modulo).strip():
                modulo_atual = str(v_modulo).strip()
            if v_uc and str(v_uc).strip():
                uc_atual = str(v_uc).strip()

            texto_cap = str(v_cap_itin).strip() if v_cap_itin else (str(v_cap_saep).strip() if v_cap_saep else "")
            if texto_cap and not texto_cap.upper().startswith("CAPACIDADES"):
                itens.append({
                    "capacidade_saep": cap_saep_atual,
                    "detalhamento_bloom": bloom_atual,
                    "conhecimentos": str(v_conhec).strip() if v_conhec else "",
                    "modulo": modulo_atual,
                    "unidade_curricular": uc_atual,
                    "capacidade_itinerario": texto_cap
                })

        wb.Close(False)
        excel.Quit()
    except Exception as e:
        print(f"Erro ao ler matriz via COM: {e}")
    return itens
