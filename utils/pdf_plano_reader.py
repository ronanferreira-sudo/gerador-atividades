import re
from PyPDF2 import PdfReader
from utils.texto_utils import limpar_numeracao_item


def extrair_texto_pdf(caminho_pdf):
    """Extrai todo o texto de um arquivo PDF."""
    reader = PdfReader(caminho_pdf)
    texto_completo = []
    for pagina in reader.pages:
        texto = pagina.extract_text()
        if texto:
            texto_completo.append(texto)
    return "\n".join(texto_completo)


def estruturar_dados_plano_pdf(caminho_pdf):
    """
    Analisa o PDF do Plano de Curso e extrai:
    - Unidade Curricular
    - Carga Horária
    - Objetivo Geral
    - Capacidades Técnicas
    - Capacidades Socioemocionais
    - Conhecimentos
    """
    texto = extrair_texto_pdf(caminho_pdf)

    dados = {
        "unidade_curricular": "",
        "carga_horaria": None,
        "objetivo_geral": "",
        "capacidades_tecnicas": [],
        "capacidades_socioemocionais": [],
        "conhecimentos": [],
        "texto_bruto": texto
    }

    # 1. Unidade Curricular
    match_uc = re.search(r"Unidade\s+Curricular:\s*([\s\S]+?)(?=Carga\s+Hor|Objetivo\s+Geral|$)", texto, re.IGNORECASE)
    if match_uc:
        dados["unidade_curricular"] = " ".join(match_uc.group(1).split()).strip()

    # 2. Carga Horária
    match_ch = re.search(r"Carga\s+Hor[aá]ria:\s*(\d+)", texto, re.IGNORECASE)
    if match_ch:
        dados["carga_horaria"] = int(match_ch.group(1))

    # 3. Objetivo Geral
    match_obj = re.search(r"Objetivo\s+Geral:\s*([\s\S]+?)(?=\n\s*Capacidades\s+T[eé]cnicas|\n\s*Capacidades\s+Socioemocionais|\n\s*Conhecimentos|$)", texto, re.IGNORECASE)
    if match_obj:
        dados["objetivo_geral"] = " ".join(match_obj.group(1).split()).strip()

    # 4. Capacidades Técnicas
    match_cap_tec = re.search(r"Capacidades\s+T[eé]cnicas([\s\S]+?)(?=Capacidades\s+Socioemocionais|Capacidades\s+B[aá]sicas|Conhecimentos|$)", texto, re.IGNORECASE)
    if match_cap_tec:
        bloco = match_cap_tec.group(1)
        linhas = [l.strip() for l in bloco.split("\n") if l.strip()]
        itens = []
        item_atual = ""
        for linha in linhas:
            if re.match(r"^[A-ZÁÉÍÓÚ][a-záéíóú]", linha) and item_atual and (item_atual.endswith(".") or len(item_atual) > 60):
                itens.append(limpar_numeracao_item(item_atual))
                item_atual = linha
            else:
                item_atual = f"{item_atual} {linha}".strip()
        if item_atual:
            itens.append(limpar_numeracao_item(item_atual))
        dados["capacidades_tecnicas"] = [i for i in itens if len(i) > 5]

    # 5. Capacidades Socioemocionais
    match_cap_socio = re.search(r"Capacidades\s+Socioemocionais([\s\S]+?)(?=Conhecimentos|$)", texto, re.IGNORECASE)
    if match_cap_socio:
        bloco = match_cap_socio.group(1)
        linhas = [limpar_numeracao_item(l.strip()) for l in bloco.split("\n") if l.strip()]
        dados["capacidades_socioemocionais"] = [" ".join(linhas)] if linhas else []

    # 6. Conhecimentos (sem números de tópicos como 1, 1.1, 1.1.1)
    match_conhec = re.search(r"Conhecimentos([\s\S]+)$", texto, re.IGNORECASE)
    if match_conhec:
        bloco = match_conhec.group(1)
        linhas = [l.strip() for l in bloco.split("\n") if l.strip()]
        conhecimentos = []
        for l in linhas:
            # Ignora cabeçalhos repetidos de página
            if "Plano de Curso" in l or "Página" in l or "Revisão" in l or "FP.EP." in l or "UNIDADE CURRICULAR" in l:
                continue
            item_limpo = limpar_numeracao_item(l)
            if len(item_limpo) > 2 and not item_limpo.startswith("http"):
                conhecimentos.append(item_limpo)
        dados["conhecimentos"] = conhecimentos

    return dados
