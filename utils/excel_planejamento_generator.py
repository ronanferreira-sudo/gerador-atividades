import os
import re
import math
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from datetime import datetime
from utils.texto_utils import limpar_numeracao_texto, limpar_numeracao_item

# Diretório base do projeto e pasta templates interna do sistema
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_TEMPLATES = os.path.join(BASE_DIR, "templates")

MODELO_TECNICO      = os.path.join(PASTA_TEMPLATES, "modelo_tecnico.xlsx")
MODELO_QUALIFICACAO = os.path.join(PASTA_TEMPLATES, "modelo_qualificacao.xlsx")
MODELO_LEGADO       = os.path.join(PASTA_TEMPLATES, "modelo_planejamento_docente.xlsx")


def obter_caminho_modelo(tipo: str) -> str:
    """
    Retorna o caminho do modelo oficial (.xlsx) salvo internamente no sistema (templates/).
    Totalmente autocontido e independente do computador ou ambiente em que o sistema roda:
      - 'tecnico'      → templates/modelo_tecnico.xlsx
      - 'qualificacao' → templates/modelo_qualificacao.xlsx
    """
    tipo_norm = "tecnico" if tipo == "tecnico" else "qualificacao"

    if tipo_norm == "tecnico":
        caminho = MODELO_TECNICO
        if not os.path.exists(caminho):
            caminho = os.path.join("templates", "modelo_tecnico.xlsx")
    else:
        caminho = MODELO_QUALIFICACAO
        if not os.path.exists(caminho):
            caminho = os.path.join("templates", "modelo_qualificacao.xlsx")

    if not os.path.exists(caminho):
        if os.path.exists(MODELO_LEGADO):
            print(f"[AVISO] Usando modelo legado de fallback: {MODELO_LEGADO}")
            return MODELO_LEGADO
        raise FileNotFoundError(
            f"Arquivo modelo '{caminho}' não encontrado no sistema. "
            f"Verifique se o arquivo existe na pasta templates/ do projeto."
        )

    return caminho


def detectar_tipo_curso(modalidade: str = "", nome_curso: str = "") -> str:
    """
    Detecta o tipo de curso com base na modalidade ou nome do curso.
    Retorna 'tecnico' ou 'qualificacao'.
      - Técnico / Habilitação Técnica → 'tecnico'
      - Qualificação / Aperfeiçoamento → 'qualificacao'
    """
    m = (modalidade or "").strip().upper()
    n = (nome_curso or "").strip().upper()

    # Prioridade para a modalidade explicitada no formulário
    if any(p in m for p in ["APERFEIÇOAMENTO", "APERFEICOAMENTO", "QUALIFICAÇÃO", "QUALIFICACAO"]):
        return "qualificacao"
    if any(p in m for p in ["TÉCNICO", "TECNICO", "HABILITAÇÃO", "HABILITACAO"]):
        return "tecnico"

    # Se a modalidade não for conclusiva, inspeciona o nome do curso
    if any(p in n for p in ["APERFEIÇOAMENTO", "APERFEICOAMENTO", "QUALIFICAÇÃO", "QUALIFICACAO"]):
        return "qualificacao"
    if any(p in n for p in ["TÉCNICO", "TECNICO", "HABILITAÇÃO", "HABILITACAO"]):
        return "tecnico"

    return "qualificacao"


def calcular_altura_linha(texto_o_que, texto_estrategia="", texto_recursos="", texto_criterios="", texto_instrumentos=""):
    """
    Calcula a altura ideal da linha do Excel baseando-se no número de linhas reais
    e quebras automáticas de texto (wrap text) para garantir que nenhuma informação
    fique cortada ou oculta.
    """
    def estimar_linhas_bloco(texto, largura_chars):
        if not texto:
            return 0
        total = 0
        for linha in str(texto).split("\n"):
            linha_s = linha.strip()
            if not linha_s:
                total += 1
            else:
                total += max(1, math.ceil(len(linha_s) / max(largura_chars, 10)))
        return total

    # Larguras estimadas em caracteres úteis por coluna mesclada:
    # A:C (~50 caracteres)
    # D (~32 caracteres)
    # H:I (~16 caracteres)
    # M:O (~22 caracteres)
    # P (~18 caracteres)
    linhas_a = estimar_linhas_bloco(texto_o_que, 50)
    linhas_d = estimar_linhas_bloco(texto_estrategia, 32)
    linhas_h = estimar_linhas_bloco(texto_recursos, 16)
    linhas_m = estimar_linhas_bloco(texto_criterios, 22)
    linhas_p = estimar_linhas_bloco(texto_instrumentos, 18)

    max_linhas = max(linhas_a, linhas_d, linhas_h, linhas_m, linhas_p, 6)

    # Cada linha consome aproximadamente 16 pontos em Calibri 10, com margem interna
    altura_estimada = max_linhas * 16 + 25

    # Altura base mínima de 115 pt; aumenta dinamicamente conforme a quantidade de conteúdo
    return max(115, altura_estimada)


def gerar_excel_planejamento(
    dados_cabecalho,
    aulas,
    caminho_modelo=None,
    caminho_saida=None
):
    """
    Gera o arquivo Excel do Planejamento Docente a partir do modelo correto.
    Diferencia automaticamente o tipo de curso:
      - Curso Técnico / Habilitação Técnica → usa modelo técnico (modelo tecnico.xlsx)
      - Qualificação Profissional / Aperfeiçoamento → usa modelo qualificação (modelo qualificacao.xlsx)
    Utiliza os modelos oficiais salvos internamente na pasta templates/ do sistema.
    """
    modalidade = dados_cabecalho.get("modalidade", "")
    nome_curso = dados_cabecalho.get("nome_curso", "")

    # --- Seleciona o modelo automaticamente se não fornecido explicitamente ---
    if caminho_modelo is None:
        tipo = detectar_tipo_curso(modalidade, nome_curso)
        caminho_modelo = obter_caminho_modelo(tipo)
        print(f"[INFO] Modalidade: '{modalidade}' | Curso: '{nome_curso}' => Tipo: '{tipo}'")
        print(f"[INFO] Modelo selecionado: {caminho_modelo}")
    else:
        # Detecta tipo pelo nome do arquivo fornecido
        tipo = "tecnico" if "tecnico" in caminho_modelo.lower() else "qualificacao"

    if not os.path.exists(caminho_modelo):
        print(f"[AVISO] Modelo '{caminho_modelo}' nao encontrado. Usando fallback.")
        caminho_modelo = obter_caminho_modelo(tipo)

    # Roteia para o gerador correspondente
    if tipo == "tecnico":
        return _gerar_excel_tecnico(dados_cabecalho, aulas, caminho_modelo, caminho_saida)
    else:
        return _gerar_excel_qualificacao(dados_cabecalho, aulas, caminho_modelo, caminho_saida)

def _gerar_excel_qualificacao(dados_cabecalho, aulas, caminho_modelo, caminho_saida):
    """
    Preenche o modelo de Qualificação/Aperfeiçoamento (.xlsx).
    Layout (colunas):
      A:C  = O que? (Capacidade / Conhecimento)
      D    = Como? (Estratégia de Ensino)
      E:G  = Onde? (Ambientes Pedagógicos)
      H:I  = Recursos Didáticos
      J:L  = Carga Horária
      M:O  = Critérios de Avaliação
      P    = Instrumento de Avaliação
      Q    = Situação de Aprendizagem
      R    = Data Início
      S    = Data Fim
    """
    wb = openpyxl.load_workbook(caminho_modelo)
    ws = wb.active

    # ==========================================
    # 1. ATUALIZA O CABEÇALHO (Linhas 5 a 8)
    # ==========================================
    if dados_cabecalho.get("unidade_escolar"):
        ws["C5"] = str(dados_cabecalho["unidade_escolar"]).strip()

    data_ini = dados_cabecalho.get("data_inicio", "")
    data_fim = dados_cabecalho.get("data_fim", "")
    if isinstance(data_ini, datetime):
        data_ini = data_ini.strftime("%d/%m/%Y")
    if isinstance(data_fim, datetime):
        data_fim = data_fim.strftime("%d/%m/%Y")
    if data_ini and data_fim:
        ws["L5"] = f"{data_ini} a {data_fim}"
    elif data_ini:
        ws["L5"] = f"A partir de {data_ini}"

    if dados_cabecalho.get("nome_curso"):
        ws["C6"] = str(dados_cabecalho["nome_curso"]).strip().upper()

    modalidade = dados_cabecalho.get("modalidade", "QUALIFICAÇÃO PROFISSIONAL")
    ws["L6"] = f" {modalidade.strip().upper()} "

    turma = dados_cabecalho.get("codigo_turma", "QUAL.2026.1")
    ws["C7"] = f" {turma.strip().upper()}"

    if dados_cabecalho.get("carga_horaria"):
        try:
            ws["L7"] = float(dados_cabecalho["carga_horaria"])
        except (ValueError, TypeError):
            ws["L7"] = str(dados_cabecalho["carga_horaria"])

    if dados_cabecalho.get("unidade_curricular"):
        ws["C8"] = str(dados_cabecalho["unidade_curricular"]).strip()

    if dados_cabecalho.get("instrutor"):
        ws["L8"] = str(dados_cabecalho["instrutor"]).strip().upper()

    # ==========================================
    # 2. LIMPAR LINHAS DE DADOS (a partir da linha 13)
    # ==========================================
    ranges_para_remover = [
        rng for rng in list(ws.merged_cells.ranges)
        if rng.min_row >= 13
    ]
    for rng in ranges_para_remover:
        ws.merged_cells.remove(rng)

    if ws.max_row >= 13:
        ws.delete_rows(13, ws.max_row - 12)

    # Estilos
    fonte_padrao = Font(name="Calibri", size=10, bold=False)
    alin_esquerda_topo = Alignment(horizontal="left", vertical="top", wrap_text=True)
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

        cap_limpa = limpar_numeracao_texto(aula.get("capacidade", "")).strip()
        con_limpo = limpar_numeracao_texto(aula.get("conhecimento", ""), separador="\n").strip()
        titulo_cap = " " * 19 + "CAPACIDADE:"
        titulo_con = " " * 17 + "CONHECIMENTOS:"
        texto_o_que = f"{titulo_cap}\n{cap_limpa}\n\n{titulo_con}\n{con_limpo}"

        ws.cell(row=r, column=1, value=texto_o_que)   # A: O que?

        estrategia_txt = str(aula.get("estrategia", "")).strip().upper()
        ws.cell(row=r, column=4, value=estrategia_txt)  # D: Como?

        ws.cell(row=r, column=5, value=str(aula.get("ambiente", "LABORATORIO T.I")).strip().upper())  # E: Onde?

        recursos_txt = str(aula.get("recursos", "NOTEBOOK\nTELA DIGITAL\nCOMPUTADORES")).strip().upper()
        ws.cell(row=r, column=8, value=recursos_txt)  # H: Recursos

        ws.cell(row=r, column=10, value=str(aula.get("carga_horaria_str", "4 HS")).strip().upper())  # J: CH

        criterios_txt = str(aula.get("criterios", "")).strip().upper()
        ws.cell(row=r, column=13, value=criterios_txt)  # M: Critérios

        instrumentos_txt = str(aula.get("instrumentos", "")).strip().upper()
        ws.cell(row=r, column=16, value=instrumentos_txt)  # P: Instrumentos

        ws.cell(row=r, column=17, value=str(aula.get("situacao_aprendizagem", "https://recursosdidaticos.senai.br")).strip())  # Q: SA

        # R e S: Datas
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

        ws.row_dimensions[r].height = calcular_altura_linha(texto_o_que, estrategia_txt, recursos_txt, criterios_txt, instrumentos_txt)

        for col_idx in range(1, 20):
            c_obj = ws.cell(row=r, column=col_idx)
            c_obj.font = fonte_padrao
            c_obj.border = borda_fina
            if col_idx in (1, 2, 3, 13, 14, 15):
                c_obj.alignment = alin_esquerda_topo
            elif col_idx in (18, 19):
                c_obj.alignment = alin_data
            else:
                c_obj.alignment = alin_centro

        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)    # A:C
        ws.merge_cells(start_row=r, start_column=5, end_row=r, end_column=7)    # E:G
        ws.merge_cells(start_row=r, start_column=8, end_row=r, end_column=9)    # H:I
        ws.merge_cells(start_row=r, start_column=10, end_row=r, end_column=12)  # J:L
        ws.merge_cells(start_row=r, start_column=13, end_row=r, end_column=15)  # M:O

    # Mescla coluna Q (Situação de Aprendizagem) por toda a extensão
    if total_aulas > 1:
        ws.merge_cells(start_row=linha_inicio_dados, start_column=17, end_row=linha_inicio_dados + total_aulas - 1, end_column=17)
        ws.cell(row=linha_inicio_dados, column=17).alignment = alin_centro

    if not caminho_saida:
        os.makedirs("outputs", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_uc_safe = "".join(c for c in dados_cabecalho.get("unidade_curricular", "UC") if c.isalnum() or c in (" ", "_", "-")).strip()
        caminho_saida = f"outputs/Planejamento_Docente_Qualificacao_{nome_uc_safe}_{timestamp}.xlsx"

    wb.save(caminho_saida)
    wb.close()
    return caminho_saida


def _gerar_excel_tecnico(dados_cabecalho, aulas, caminho_modelo, caminho_saida):
    """
    Preenche o modelo de Curso Técnico (.xlsx) oficial do SENAI usando openpyxl.
    Layout (colunas):
      A:C (1:3)   = O que? (Capacidade / Conhecimento)
      D   (4)     = Identificação - MATRIZ DE REFERÊNCIA SAEP
      E   (5)     = Como? (Estratégia de Ensino)
      F:H (6:8)   = Onde? (Ambientes Pedagógicos)
      I:J (9:10)  = Recursos Didáticos
      K:M (11:13) = Carga Horária
      N:P (14:16) = Critérios de Avaliação
      Q   (17)    = Instrumento de Avaliação da Aprendizagem
      R   (18)    = Situação de Aprendizagem
      S   (19)    = Quando - Início
      T   (20)    = Quando - Fim
    """
    wb = openpyxl.load_workbook(caminho_modelo)
    ws = wb.active

    # ==========================================
    # 1. ATUALIZA O CABEÇALHO (Linhas 5 a 8)
    # ==========================================
    if dados_cabecalho.get("unidade_escolar"):
        ws["C5"] = str(dados_cabecalho["unidade_escolar"]).strip()

    data_ini = dados_cabecalho.get("data_inicio", "")
    data_fim = dados_cabecalho.get("data_fim", "")
    if isinstance(data_ini, datetime):
        data_ini = data_ini.strftime("%d/%m/%Y")
    if isinstance(data_fim, datetime):
        data_fim = data_fim.strftime("%d/%m/%Y")
    if data_ini and data_fim:
        ws["M5"] = f"{data_ini} à {data_fim}"
    elif data_ini:
        ws["M5"] = f"A partir de {data_ini}"

    if dados_cabecalho.get("nome_curso"):
        ws["C6"] = str(dados_cabecalho["nome_curso"]).strip().upper()

    modalidade = dados_cabecalho.get("modalidade", "HABILITAÇÃO TÉCNICA")
    ws["M6"] = f" {modalidade.strip().upper()} "

    turma = dados_cabecalho.get("codigo_turma", "TEC.2026.1")
    ws["C7"] = f" {turma.strip().upper()}"

    if dados_cabecalho.get("carga_horaria"):
        try:
            ws["M7"] = float(dados_cabecalho["carga_horaria"])
        except (ValueError, TypeError):
            ws["M7"] = str(dados_cabecalho["carga_horaria"])

    if dados_cabecalho.get("unidade_curricular"):
        ws["C8"] = str(dados_cabecalho["unidade_curricular"]).strip()

    if dados_cabecalho.get("instrutor"):
        ws["M8"] = str(dados_cabecalho["instrutor"]).strip().upper()

    # ==========================================
    # 2. LIMPAR LINHAS DE DADOS DE EXEMPLO (a partir da linha 13)
    # ==========================================
    ranges_para_remover = [
        rng for rng in list(ws.merged_cells.ranges)
        if rng.min_row >= 13
    ]
    for rng in ranges_para_remover:
        ws.merged_cells.remove(rng)

    if ws.max_row >= 13:
        ws.delete_rows(13, ws.max_row - 12)

    # Estilos
    fonte_padrao = Font(name="Calibri", size=10, bold=False)
    fonte_sa = Font(name="Calibri", size=11, bold=False)
    alin_esquerda_centro = Alignment(horizontal="left", vertical="center", wrap_text=True)
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

        cap_limpa = limpar_numeracao_texto(aula.get("capacidade", "")).strip()
        con_limpo = limpar_numeracao_texto(aula.get("conhecimento", ""), separador="\n").strip()
        titulo_cap = " " * 15 + "CAPACIDADE:"
        titulo_con = " " * 13 + "CONHECIMENTOS:"
        texto_o_que = f"{titulo_cap}\n{cap_limpa}\n\n{titulo_con}\n{con_limpo}"

        # A: O que?
        ws.cell(row=r, column=1, value=texto_o_que)

        # D: Matriz de Referência SAEP
        saep_txt = str(aula.get("saep") or "").strip()
        if not saep_txt:
            saep_txt = "Não tem cruzamento"
        ws.cell(row=r, column=4, value=saep_txt)

        # E: Como? Estratégia
        estrategia_txt = str(aula.get("estrategia", "")).strip().upper()
        ws.cell(row=r, column=5, value=estrategia_txt)

        # F: Onde? Ambientes
        ws.cell(row=r, column=6, value=str(aula.get("ambiente", "LABORATORIO T.I")).strip().upper())

        # I: Recursos Didáticos
        recursos_txt = str(aula.get("recursos", "NOTEBOOK\nTELA DIGITAL\nCOMPUTADORES")).strip().upper()
        ws.cell(row=r, column=9, value=recursos_txt)

        # K: Carga Horária
        ws.cell(row=r, column=11, value=str(aula.get("carga_horaria_str", "4 HS")).strip().upper())

        # N: Critérios de Avaliação
        criterios_txt = str(aula.get("criterios", "")).strip().upper()
        ws.cell(row=r, column=14, value=criterios_txt)

        # Q: Instrumento de Avaliação
        instrumentos_txt = str(aula.get("instrumentos", "")).strip().upper()
        ws.cell(row=r, column=17, value=instrumentos_txt)

        # R: Situação de Aprendizagem
        ws.cell(row=r, column=18, value=str(aula.get("situacao_aprendizagem", "https://recursosdidaticos.senai.br")).strip())

        # S e T: Datas
        dt_ini = aula.get("data_inicio")
        dt_fim = aula.get("data_fim", dt_ini)
        cell_s = ws.cell(row=r, column=19)
        cell_t = ws.cell(row=r, column=20)
        if isinstance(dt_ini, datetime):
            cell_s.value = dt_ini
            cell_s.number_format = "DD/MM/YYYY"
        else:
            cell_s.value = str(dt_ini) if dt_ini else ""
        if isinstance(dt_fim, datetime):
            cell_t.value = dt_fim
            cell_t.number_format = "DD/MM/YYYY"
        else:
            cell_t.value = str(dt_fim) if dt_fim else ""

        # Altura da linha
        ws.row_dimensions[r].height = calcular_altura_linha(texto_o_que, estrategia_txt, recursos_txt, criterios_txt, instrumentos_txt)

        # Aplica estilos e bordas
        for col_idx in range(1, 21):
            c_obj = ws.cell(row=r, column=col_idx)
            c_obj.font = fonte_sa if col_idx == 18 else fonte_padrao
            c_obj.border = borda_fina
            if col_idx in (1, 2, 3, 4, 14, 15, 16):
                c_obj.alignment = alin_esquerda_centro
            elif col_idx in (19, 20):
                c_obj.alignment = alin_data
            else:
                c_obj.alignment = alin_centro

        # Mesclagens por linha
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)    # A:C
        ws.merge_cells(start_row=r, start_column=6, end_row=r, end_column=8)    # F:H
        ws.merge_cells(start_row=r, start_column=9, end_row=r, end_column=10)   # I:J
        ws.merge_cells(start_row=r, start_column=11, end_row=r, end_column=13)  # K:M
        ws.merge_cells(start_row=r, start_column=14, end_row=r, end_column=16)  # N:P

    # Mescla coluna R (Situação de Aprendizagem) verticalmente caso haja mais de 1 aula
    if total_aulas > 1:
        ws.merge_cells(start_row=linha_inicio_dados, start_column=18, end_row=linha_inicio_dados + total_aulas - 1, end_column=18)
        ws.cell(row=linha_inicio_dados, column=18).alignment = alin_centro

    if not caminho_saida:
        os.makedirs("outputs", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_uc_safe = "".join(c for c in dados_cabecalho.get("unidade_curricular", "UC") if c.isalnum() or c in (" ", "_", "-")).strip()
        caminho_saida = f"outputs/Planejamento_Docente_Tecnico_{nome_uc_safe}_{timestamp}.xlsx"

    wb.save(caminho_saida)
    wb.close()
    return caminho_saida
