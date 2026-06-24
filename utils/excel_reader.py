"""
Utilitário para ler planilhas Excel e extrair dados das colunas:
- Cruzamento de: (Subfunção, Capacidade, Conhecimento)
- Identificação - MATRIZ DE REFERÊNCIA SAEP

O arquivo Excel deve ter o formato esperado de uma matriz de referência
onde a primeira linha ou primeiras linhas contém os cabeçalhos.
"""

import openpyxl
import re


def encontrar_linha_cabecalho(ws):
    """
    Varre as primeiras linhas da planilha para encontrar os cabeçalhos.
    Retorna o número da linha onde os cabeçalhos principais estão.
    """
    for row in ws.iter_rows(min_row=1, max_row=10, max_col=ws.max_column):
        for cell in row:
            if cell.value and isinstance(cell.value, str):
                valor = cell.value.strip().upper()
                if "MATRIZ DE REFERÊNCIA" in valor or "IDENTIFICAÇÃO" in valor:
                    return cell.row
    return 1


def encontrar_colunas(ws, linha_cabecalho):
    """
    Encontra as colunas relevantes na planilha:
    - Identificação - MATRIZ DE REFERÊNCIA SAEP
    - Cruzamento de: (Subfunção, Capacidade, Conhecimento)

    Retorna um dicionário com os índices das colunas encontradas.
    """
    colunas = {
        "identificacao": None,
        "subfuncao": None,
        "capacidade": None,
        "conhecimento": None,
    }

    # Procura nas linhas de cabeçalho (até 5 linhas a partir da linha do cabeçalho principal)
    for row in ws.iter_rows(
        min_row=max(1, linha_cabecalho - 2),
        max_row=linha_cabecalho + 3,
        max_col=ws.max_column,
    ):
        for cell in row:
            if cell.value and isinstance(cell.value, str):
                valor = cell.value.strip().upper()

                # Identificação - MATRIZ DE REFERÊNCIA SAEP
                if "IDENTIFICAÇÃO" in valor or "MATRIZ DE REFERÊNCIA" in valor:
                    if colunas["identificacao"] is None:
                        colunas["identificacao"] = cell.column

                # Cruzamento de: Subfunção
                if "SUBFUNÇÃO" in valor or "SUBFUNCAO" in valor:
                    colunas["subfuncao"] = cell.column

                # Cruzamento de: Capacidade
                if "CAPACIDADE" in valor:
                    colunas["capacidade"] = cell.column

                # Cruzamento de: Conhecimento
                if "CONHECIMENTO" in valor:
                    colunas["conhecimento"] = cell.column

    return colunas


def extrair_dados_excel(caminho_arquivo):
    """
    Lê o arquivo Excel e extrai os dados das colunas:
    - Identificação - MATRIZ DE REFERÊNCIA SAEP
    - Subfunção (dentro de Cruzamento de:)
    - Capacidade (dentro de Cruzamento de:)
    - Conhecimento (dentro de Cruzamento de:)

    Retorna uma lista de dicionários com os dados extraídos,
    apenas para linhas onde a coluna Identificação possui conteúdo.
    Também retorna um texto formatado para uso na IA.
    """
    wb = openpyxl.load_workbook(caminho_arquivo, data_only=True)
    ws = wb.active

    linha_cabecalho = encontrar_linha_cabecalho(ws)
    colunas = encontrar_colunas(ws, linha_cabecalho)

    print(f"📋 Linha do cabeçalho encontrada: {linha_cabecalho}")
    print(f"📋 Colunas encontradas: {colunas}")

    # Se nenhuma coluna foi encontrada, tenta uma abordagem mais flexível
    if not any(colunas.values()):
        print("⚠️  Nenhuma coluna específica encontrada. Usando abordagem genérica...")
        return _extrair_generico(ws, linha_cabecalho)

    dados = []
    linha_inicio = linha_cabecalho + 2  # Pular linha do cabeçalho e possivelmente uma linha em branco

    for row in ws.iter_rows(
        min_row=linha_inicio,
        max_row=ws.max_row,
        min_col=1,
        max_col=ws.max_column,
    ):
        # Pega o valor da coluna Identificação
        if colunas["identificacao"]:
            cell_id = row[colunas["identificacao"] - 1]
            valor_id = cell_id.value
        else:
            valor_id = None

        # Só considera linhas que tenham conteúdo na coluna Identificação
        if valor_id is not None and str(valor_id).strip():
            registro = {
                "identificacao": str(valor_id).strip(),
            }

            if colunas["subfuncao"]:
                cell_sub = row[colunas["subfuncao"] - 1]
                registro["subfuncao"] = str(cell_sub.value).strip() if cell_sub.value else ""

            if colunas["capacidade"]:
                cell_cap = row[colunas["capacidade"] - 1]
                registro["capacidade"] = str(cell_cap.value).strip() if cell_cap.value else ""

            if colunas["conhecimento"]:
                cell_conh = row[colunas["conhecimento"] - 1]
                registro["conhecimento"] = str(cell_conh.value).strip() if cell_conh.value else ""

            dados.append(registro)

    wb.close()
    return dados


def _extrair_generico(ws, linha_cabecalho):
    """
    Abordagem genérica: extrai todas as linhas com dados a partir do cabeçalho.
    Pega as primeiras colunas úteis.
    """
    dados = []
    linha_inicio = linha_cabecalho + 2

    for row in ws.iter_rows(
        min_row=linha_inicio,
        max_row=ws.max_row,
        min_col=1,
        max_col=min(ws.max_column, 4),  # Pega as primeiras 4 colunas
    ):
        valores = [cell.value for cell in row if cell.value is not None and str(cell.value).strip()]

        if valores:
            registro = {
                "identificacao": str(valores[0]).strip() if len(valores) > 0 else "",
                "subfuncao": str(valores[1]).strip() if len(valores) > 1 else "",
                "capacidade": str(valores[2]).strip() if len(valores) > 2 else "",
                "conhecimento": str(valores[3]).strip() if len(valores) > 3 else "",
            }
            if registro["identificacao"]:
                dados.append(registro)

    return dados


def formatar_dados_para_prompt(dados):
    """
    Formata os dados extraídos do Excel em um texto estruturado
    para ser usado como contexto no prompt da IA.
    Extrai apenas os Conhecimentos (ignora Identificação, Subfunção e Capacidade).
    """
    if not dados:
        return "Nenhum dado encontrado no arquivo Excel."

    conhecimentos = []
    for registro in dados:
        if registro.get("conhecimento") and registro["conhecimento"].strip():
            conhecimentos.append(registro["conhecimento"].strip())

    if not conhecimentos:
        return "Nenhum conhecimento encontrado no arquivo Excel."

    linhas = []
    linhas.append("CONHECIMENTOS DO CURSO")
    linhas.append("=" * 60)

    for i, conhecimento in enumerate(conhecimentos, start=1):
        linhas.append(f"{i}. {conhecimento}")

    return "\n".join(linhas)


def contar_itens(dados):
    """Retorna a quantidade de Conhecimentos extraídos."""
    conhecimentos = [r for r in dados if r.get("conhecimento") and r["conhecimento"].strip()]
    return len(conhecimentos)


if __name__ == "__main__":
    # Teste rápido
    import sys
    if len(sys.argv) > 1:
        caminho = sys.argv[1]
        dados = extrair_dados_excel(caminho)
        print(f"\n📊 Total de itens extraídos: {len(dados)}")
        print("\n" + formatar_dados_para_prompt(dados))