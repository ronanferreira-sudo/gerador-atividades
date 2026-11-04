from utils.texto_utils import limpar_numeracao_texto, limpar_numeracao_item
import os
import re
import openpyxl

def ler_excel_planejamento_docente(caminho_excel):
    """
    Lê o arquivo Excel de Planejamento Docente preenchido pelo sistema.
    Detecta automaticamente se é o modelo Técnico ou Qualificação/Aperfeiçoamento.
    Retorna:
    - dados_cabecalho: {
        "nome_curso": ...,
        "unidade_curricular": ...,
        "carga_horaria": ...,
        "horas_por_dia": ...
      }
    - aulas: [
        {
            "dia": 1,
            "capacidade": "...",
            "conhecimento": "...",
            "saep": "...",
            "estrategia": "...",
            "ambiente": "...",
            "recursos": "...",
            "criterios": "...",
            "instrumentos": "...",
            "situacao_aprendizagem": "...",
            "nivel_bloom": "..."
        },
        ...
      ]
    """
    wb = openpyxl.load_workbook(caminho_excel, data_only=True)
    ws = wb.active

    # Detecta se o arquivo segue o modelo Técnico ou Qualificação
    cabecalho_d11 = str(ws.cell(row=11, column=4).value or "").upper()
    cabecalho_m6  = str(ws.cell(row=6, column=13).value or "").upper()
    eh_tecnico = any(k in cabecalho_d11 for k in ["SAEP", "MATRIZ"]) or any(k in cabecalho_m6 for k in ["TÉCNIC", "TECNIC", "HABILITA"])

    nome_curso = str(ws["C6"].value or "").strip()
    unidade_curricular = str(ws["C8"].value or "").strip()

    if eh_tecnico:
        ch_raw = ws["M7"].value or ws["L7"].value or 0
    else:
        ch_raw = ws["L7"].value or ws["M7"].value or 0

    try:
        carga_horaria = int(float(ch_raw))
    except (ValueError, TypeError):
        carga_horaria = 0

    aulas = []
    linha = 13
    dia = 1

    while linha <= ws.max_row:
        val_a = ws.cell(row=linha, column=1).value
        if not val_a or not str(val_a).strip():
            linha += 1
            continue

        texto_bloco = str(val_a).strip()

        # Extrai Capacidade e Conhecimento
        capacidade = ""
        conhecimento = ""

        # Formato padrão: CAPACIDADE:\n...\nCONHECIMENTOS:\n...
        if re.search(r"CONHECIMENTOS?", texto_bloco, flags=re.IGNORECASE):
            partes = re.split(r"\s*CONHECIMENTOS?:?\s*|\bCONHECIMENTOS?\b", texto_bloco, flags=re.IGNORECASE)
            cap_part = partes[0]
            con_part = partes[1] if len(partes) > 1 else ""

            # Remove prefixo "CAPACIDADE:" e limpa símbolos e numerações
            capacidade = re.sub(r"^\s*CAPACIDADE:\s*", "", cap_part.strip(), flags=re.IGNORECASE).strip()
            capacidade = limpar_numeracao_texto(capacidade)
            conhecimento = limpar_numeracao_texto(con_part.strip(), separador="\n")
        else:
            capacidade = limpar_numeracao_texto(texto_bloco)
            conhecimento = ""

        if eh_tecnico:
            saep = str(ws.cell(row=linha, column=4).value or "").strip()
            estrategia = str(ws.cell(row=linha, column=5).value or "").strip()
            ambiente = str(ws.cell(row=linha, column=6).value or "").strip()
            recursos = str(ws.cell(row=linha, column=9).value or "").strip()
            ch_str = str(ws.cell(row=linha, column=11).value or "").strip()
            criterios = str(ws.cell(row=linha, column=14).value or "").strip()
            instrumentos = str(ws.cell(row=linha, column=17).value or "").strip()
            situacao = str(ws.cell(row=linha, column=18).value or "").strip()
        else:
            saep = ""
            estrategia = str(ws.cell(row=linha, column=4).value or "").strip()
            ambiente = str(ws.cell(row=linha, column=5).value or "").strip()
            recursos = str(ws.cell(row=linha, column=8).value or "").strip()
            ch_str = str(ws.cell(row=linha, column=10).value or "").strip()
            criterios = str(ws.cell(row=linha, column=13).value or "").strip()
            instrumentos = str(ws.cell(row=linha, column=16).value or "").strip()
            situacao = str(ws.cell(row=linha, column=17).value or "").strip()

        # Tenta extrair horas do dia (ex: "4 HS" -> 4)
        m_hd = re.search(r"(\d+)", ch_str)
        horas_aula = int(m_hd.group(1)) if m_hd else 4

        # Infere o nível de Bloom a partir de estratégia, capacidade ou sequência
        nivel_bloom = "Entender"
        cap_lower = capacidade.lower()
        if any(v in cap_lower for v in ["reconhecer", "identificar", "listar", "nomear", "descrever", "definir"]):
            nivel_bloom = "Lembrar"
        elif any(v in cap_lower for v in ["compreender", "interpretar", "explicar", "diferenciar", "classificar"]):
            nivel_bloom = "Entender"
        elif any(v in cap_lower for v in ["executar", "realizar", "utilizar", "empregar", "operar", "implementar"]):
            nivel_bloom = "Aplicar"
        elif any(v in cap_lower for v in ["analisar", "comparar", "diagnosticar", "examinar", "testar"]):
            nivel_bloom = "Analisar"
        elif any(v in cap_lower for v in ["avaliar", "validar", "criticar", "julgar", "medir"]):
            nivel_bloom = "Avaliar"
        elif any(v in cap_lower for v in ["criar", "desenvolver", "projetar", "construir", "elaborar"]):
            nivel_bloom = "Criar"

        aulas.append({
            "dia": dia,
            "capacidade": capacidade,
            "conhecimento": conhecimento,
            "saep": saep,
            "estrategia": estrategia,
            "ambiente": ambiente,
            "recursos": recursos,
            "carga_horaria_str": ch_str,
            "horas_aula": horas_aula,
            "criterios": criterios,
            "instrumentos": instrumentos,
            "situacao_aprendizagem": situacao,
            "nivel_bloom": nivel_bloom
        })

        dia += 1
        linha += 1

    wb.close()

    horas_por_dia = aulas[0]["horas_aula"] if aulas else 4
    if carga_horaria == 0 and aulas:
        carga_horaria = sum(a["horas_aula"] for a in aulas)

    dados_cabecalho = {
        "nome_curso": nome_curso,
        "unidade_curricular": unidade_curricular,
        "carga_horaria": carga_horaria,
        "horas_por_dia": horas_por_dia,
        "total_aulas": len(aulas),
        "eh_tecnico": eh_tecnico
    }

    return dados_cabecalho, aulas
