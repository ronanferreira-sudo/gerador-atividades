from utils.texto_utils import limpar_numeracao_texto
import os
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from datetime import datetime


def gerar_excel_planejamento(
    dados_cabecalho,
    aulas,
    caminho_modelo="templates/modelo_planejamento_docente.xlsx",
    caminho_saida=None
):
    """
    Gera o arquivo Excel do Planejamento Docente a partir do modelo base,
    preenchendo cabeçalho e todas as aulas calculadas com a Taxonomia de Bloom.
    """
    if not os.path.exists(caminho_modelo):
        raise FileNotFoundError(f"Arquivo modelo não encontrado: {caminho_modelo}")

    wb = openpyxl.load_workbook(caminho_modelo)
    ws = wb.active

    # ==========================================
    # 1. ATUALIZA O CABEÇALHO (Linhas 5 a 8)
    # ==========================================
    # C5: Unidade Escolar
    if dados_cabecalho.get("unidade_escolar"):
        ws["C5"] = str(dados_cabecalho["unidade_escolar"]).strip()

    # L5: Início e Fim
    data_ini = dados_cabecalho.get("data_inicio", "")
    data_fim = dados_cabecalho.get("data_fim", "")
    if isinstance(data_ini, (datetime,)):
        data_ini = data_ini.strftime("%d/%m/%Y")
    if isinstance(data_fim, (datetime,)):
        data_fim = data_fim.strftime("%d/%m/%Y")
    if data_ini and data_fim:
        ws["L5"] = f"{data_ini} a {data_fim}"
    elif data_ini:
        ws["L5"] = f"A partir de {data_ini}"

    # C6: Curso
    if dados_cabecalho.get("nome_curso"):
        ws["C6"] = str(dados_cabecalho["nome_curso"]).strip().upper()

    # L6: Modalidade
    modalidade = dados_cabecalho.get("modalidade", "HABILITAÇÃO TÉCNICA")
    ws["L6"] = f" {modalidade.strip().upper()} "

    # C7: Código da Turma
    turma = dados_cabecalho.get("codigo_turma", "TEC.2026.1")
    ws["C7"] = f" {turma.strip().upper()}"

    # L7: Carga Horária da U.C
    if dados_cabecalho.get("carga_horaria"):
        try:
            ws["L7"] = float(dados_cabecalho["carga_horaria"])
        except ValueError:
            ws["L7"] = str(dados_cabecalho["carga_horaria"])

    # C8: Unidade Curricular
    if dados_cabecalho.get("unidade_curricular"):
        ws["C8"] = str(dados_cabecalho["unidade_curricular"]).strip()

    # L8: Instrutor
    if dados_cabecalho.get("instrutor"):
        ws["L8"] = str(dados_cabecalho["instrutor"]).strip().upper()

    # ==========================================
    # 2. LIMPAR LINHAS ANTERIORES (Linha 13 em diante)
    # ==========================================
    # Remove mesclagens antigas das linhas de dados (>= 13)
    ranges_para_remover = [
        rng for rng in list(ws.merged_cells.ranges)
        if rng.min_row >= 13
    ]
    for rng in ranges_para_remover:
        ws.merged_cells.remove(rng)

    # Deleta as linhas anteriores a partir da linha 13
    if ws.max_row >= 13:
        ws.delete_rows(13, ws.max_row - 12)

    # Estilos padrão
    fonte_padrao = Font(name="Calibri", size=10, bold=False)
    fonte_link = Font(name="Calibri", size=9, bold=False, color="0000FF", underline="single")
    alin_centro = Alignment(horizontal="center", vertical="center", wrap_text=True)
    alin_data = Alignment(horizontal="center", vertical="center", wrap_text=False)
    
    borda_fina = Border(
        left=Side(style="thin", color="000000"),
        right=Side(style="thin", color="000000"),
        top=Side(style="thin", color="000000"),
        bottom=Side(style="thin", color="000000")
    )

    # ==========================================
    # 3. PREENCHER AS AULAS
    # ==========================================
    total_aulas = len(aulas)
    linha_inicio_dados = 13

    for idx, aula in enumerate(aulas):
        r = linha_inicio_dados + idx
        ws.row_dimensions[r].height = 110  # Altura generosa para acomodar o texto

        # Texto do bloco O que? (Capacidade / Conhecimento) - 100% sem numeração de tópicos
        cap_limpa = limpar_numeracao_texto(aula.get('capacidade', '')).strip()
        con_limpo = limpar_numeracao_texto(aula.get('conhecimento', '')).strip()
        texto_o_que = (
            f"CAPACIDADE:\n"
            f"{cap_limpa}\n"
            f"CONHECIMENTO\n"
            f"{con_limpo}"
        )
        ws.cell(row=r, column=1, value=texto_o_que)  # Col A

        # Col D: Como? Estratégia de Ensino
        ws.cell(row=r, column=4, value=str(aula.get("estrategia", "")).strip().upper())

        # Col E: Onde? Ambientes Pedagógicos
        ws.cell(row=r, column=5, value=str(aula.get("ambiente", "LABORATORIO T.I")).strip().upper())

        # Col H: Recursos Didáticos
        ws.cell(row=r, column=8, value=str(aula.get("recursos", "NOTEBOOK\nTELA DIGITAL\nCOMPUTADORES")).strip().upper())

        # Col J: Carga Horária
        ws.cell(row=r, column=10, value=str(aula.get("carga_horaria_str", "4 HS")).strip().upper())

        # Col M: Critérios de Avaliação
        ws.cell(row=r, column=13, value=str(aula.get("criterios", "")).strip().upper())

        # Col P: Instrumento de Avaliação
        ws.cell(row=r, column=16, value=str(aula.get("instrumentos", "")).strip().upper())

        # Col Q: Situação de Aprendizagem
        ws.cell(row=r, column=17, value=str(aula.get("situacao_aprendizagem", "https://recursosdidaticos.senai.br")).strip())

        # Datas (R e S)
        dt_ini = aula.get("data_inicio")
        dt_fim = aula.get("data_fim", dt_ini)

        cell_r = ws.cell(row=r, column=18)
        cell_s = ws.cell(row=r, column=19)

        if isinstance(dt_ini, datetime):
            cell_r.value = dt_ini
            cell_r.number_format = "DD/MM/YYYY"
        else:
            cell_r.value = str(dt_ini) if dt_ini else ""

        if isinstance(dt_fim, datetime):
            cell_s.value = dt_fim
            cell_s.number_format = "DD/MM/YYYY"
        else:
            cell_s.value = str(dt_fim) if dt_fim else ""

        # Aplica estilos e bordas em todas as células de A a S da linha r
        for col_idx in range(1, 20):
            c_obj = ws.cell(row=r, column=col_idx)
            c_obj.font = fonte_padrao
            c_obj.alignment = alin_centro
            c_obj.border = borda_fina

        # Ajusta mesclagens da linha r
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)   # A:C
        ws.merge_cells(start_row=r, start_column=5, end_row=r, end_column=7)   # E:G
        ws.merge_cells(start_row=r, start_column=8, end_row=r, end_column=9)   # H:I
        ws.merge_cells(start_row=r, start_column=10, end_row=r, end_column=12) # J:L
        ws.merge_cells(start_row=r, start_column=13, end_row=r, end_column=15) # M:O

    # Mescla a coluna Q (Situação de Aprendizagem) por toda a extensão se desejado
    if total_aulas > 1:
        primeira_linha = linha_inicio_dados
        ultima_linha = linha_inicio_dados + total_aulas - 1
        ws.merge_cells(start_row=primeira_linha, start_column=17, end_row=ultima_linha, end_column=17)
        ws.cell(row=primeira_linha, column=17).alignment = alin_centro

    # Define caminho de saída se não fornecido
    if not caminho_saida:
        os.makedirs("outputs", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_uc_safe = "".join(c for c in dados_cabecalho.get("unidade_curricular", "UC") if c.isalnum() or c in (" ", "_", "-")).strip()
        caminho_saida = f"outputs/Planejamento_Docente_{nome_uc_safe}_{timestamp}.xlsx"

    wb.save(caminho_saida)
    wb.close()
    return caminho_saida
