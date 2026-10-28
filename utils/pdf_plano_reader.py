import re
import unicodedata
from utils.texto_utils import limpar_numeracao_item, limpar_numeracao_texto, eh_linha_lixo

# Tenta importar pdfplumber com fallback para PyPDF2
try:
    import pdfplumber
    TEM_PDFPLUMBER = True
except ImportError:
    TEM_PDFPLUMBER = False

try:
    from PyPDF2 import PdfReader
    TEM_PYPDF2 = True
except ImportError:
    TEM_PYPDF2 = False


def normalizar_texto(texto):
    """Remove acentos, caracteres especiais e converte para minúsculas."""
    if not texto:
        return ""
    texto_norm = unicodedata.normalize("NFKD", str(texto)).encode("ASCII", "ignore").decode("ASCII")
    texto_norm = re.sub(r"[^a-zA-Z0-9\s]", " ", texto_norm)
    return re.sub(r"\s+", " ", texto_norm).strip().lower()


def extrair_texto_pdf(caminho_pdf):
    """
    Extrai todo o texto do PDF preservando palavras completas e formatação.
    Prioriza pdfplumber por sua precisão com layout e quebras de palavras.
    """
    texto_completo = []

    if TEM_PDFPLUMBER:
        try:
            with pdfplumber.open(caminho_pdf) as pdf:
                for pagina in pdf.pages:
                    txt = pagina.extract_text()
                    if txt:
                        texto_completo.append(txt)
            if texto_completo:
                return "\n".join(texto_completo)
        except Exception as e:
            print(f" Erro ao extrair texto com pdfplumber: {e}. Tentando PyPDF2...")

    if TEM_PYPDF2:
        try:
            reader = PdfReader(caminho_pdf)
            for pagina in reader.pages:
                txt = pagina.extract_text()
                if txt:
                    texto_completo.append(txt)
            if texto_completo:
                return "\n".join(texto_completo)
        except Exception as e:
            print(f" Erro ao extrair texto com PyPDF2: {e}")

    return "\n".join(texto_completo)


def limpar_texto_pdf(texto):
    """
    Remove cabeçalhos repetidos de página, rodapés institucionais e
    une palavras que foram divididas por hifenização na virada de linha.
    """
    if not texto:
        return ""

    # Normaliza marcadores de bullet comuns para facilitar o reconhecimento
    texto_norm = re.sub(r"[\uf0b7\uf0a7\u2022\u25aa\u25ab\u25cf\u25cb\u25a0\u25a1\u2023\u2043]", "• ", texto)

    # 1. Padrões comuns de rodapés e cabeçalhos em PDFs de planos de curso do SENAI
    padroes_lixo = [
        r"(?m)^\s*Plano\s+de\s+Curso\b[^\n]*$",
        r"(?m)^\s*Plano\s+de\s+Ensino\b[^\n]*$",
        r"Plano\s+de\s+Curso\s+Simplificado[^\n]*",
        r"P[aá]gina\s+\d+\s+de\s+\d+",
        r"FP\.EP\.[^\n]*",
        r"FIETO[^\n]*",
        r"SERVI[ÇC]O\s+NACIONAL\s+DE\s+APRENDIZAGEM[^\n]*",
        r"Departamento\s+Regional[^\n]*",
        r"Revis[aã]o\s+\d+[^\n]*"
    ]
    texto_limpo = texto_norm
    for p in padroes_lixo:
        texto_limpo = re.sub(p, "", texto_limpo, flags=re.IGNORECASE)

    # 2. Une palavras hifenizadas no final da linha (ex: "desenvolvi-\n mento" -> "desenvolvimento")
    texto_limpo = re.sub(r"(\b[a-zA-ZÀ-ÿ]+)-\s*\n\s*([a-zA-ZÀ-ÿ]+\b)", r"\1\2", texto_limpo)

    return texto_limpo


def isolar_bloco_uc(texto, uc_alvo=None):
    """
    Localiza todas as seções de detalhamento de UC no PDF e recorta
    estritamente o trecho correspondente à UC determinada pelo professor.
    """
    padrao_inicio_uc = re.compile(
        r"(?:(?:\bUNIDADE\s+CURRICULAR\b|\bDetalhamento\s+da\s+Unidade\s+Curricular\b|\bM[oó]dulo\b[^\n]*)\s*[:\-]?\s*\n?\s*)?"
        r"(?:Unidade\s+Curricular|Detalhamento\s+da\s+Unidade\s+Curricular|UC)\s*[:\-]\s*([^\n\r]+)",
        re.IGNORECASE
    )

    matches = list(padrao_inicio_uc.finditer(texto))

    if not matches:
        # Se não achou com o padrão específico, tenta padrão alternativo de cabeçalho
        padrao_alt = re.compile(r"\n\s*(?:UC\s*\d+\s*[-–:]\s*|UNIDADE\s+CURRICULAR\s*[-–:]\s*)([^\n\r]+)", re.IGNORECASE)
        matches = list(padrao_alt.finditer(texto))

    if not matches:
        print(" Nenhuma demarcação explícita de múltiplas UCs encontrada. Processando o documento completo.")
        return texto

    ucs_encontradas = []
    for idx, m in enumerate(matches):
        nome_bruto = m.group(1).strip()
        nome_limpo = re.split(r"\s+Carga\s+Hor", nome_bruto, flags=re.IGNORECASE)[0].strip()
        if re.match(r"^Capacidades\b", nome_limpo, re.IGNORECASE):
            continue
        pos_inicio = m.start()
        ucs_encontradas.append({
            "indice": idx,
            "nome": nome_limpo,
            "pos_inicio": pos_inicio
        })

    if not ucs_encontradas:
        print(" Nenhuma UC individual delimitada. Utilizando o texto completo.")
        return texto

    print(f" Encontradas {len(ucs_encontradas)} seções de Unidade Curricular no PDF:")
    for u in ucs_encontradas:
        print(f"    UC #{u['indice'] + 1}: {u['nome']}")

    # Se o professor não especificou ou o documento só tem 1 UC
    if not uc_alvo or not str(uc_alvo).strip():
        print(f" Nenhuma UC alvo fornecida. Utilizando a primeira UC: '{ucs_encontradas[0]['nome']}'")
        uc_escolhida = ucs_encontradas[0]
    else:
        alvo_norm = normalizar_texto(uc_alvo)
        print(f" Buscando UC determinada pelo professor: '{uc_alvo}' (normalizado: '{alvo_norm}')")

        uc_escolhida = None

        # 1. Correspondência exata normalizada ou inclusão direta
        for u in ucs_encontradas:
            u_norm = normalizar_texto(u["nome"])
            if alvo_norm == u_norm or alvo_norm in u_norm or u_norm in alvo_norm:
                uc_escolhida = u
                break

        # 2. Correspondência por palavras-chave significativas (> 3 caracteres)
        if not uc_escolhida:
            palavras_alvo = [w for w in alvo_norm.split() if len(w) > 3 and w not in ["para", "com", "tecnico", "curso"]]
            if palavras_alvo:
                melhor_match = None
                maior_pontuacao = 0
                for u in ucs_encontradas:
                    u_norm = normalizar_texto(u["nome"])
                    pontos = sum(1 for w in palavras_alvo if w in u_norm)
                    if pontos > maior_pontuacao:
                        maior_pontuacao = pontos
                        melhor_match = u
                if melhor_match and maior_pontuacao > 0:
                    uc_escolhida = melhor_match

        # 3. Fallback: primeira UC encontrada
        if not uc_escolhida:
            print(f" UC '{uc_alvo}' não encontrada explicitamente no PDF. Utilizando UC padrão: '{ucs_encontradas[0]['nome']}'")
            uc_escolhida = ucs_encontradas[0]

    print(f" UC delimitada para extração: '{uc_escolhida['nome']}'")

    pos_ini = uc_escolhida["pos_inicio"]
    idx_atual = uc_escolhida["indice"]

    # Fim do bloco da UC:
    if idx_atual + 1 < len(ucs_encontradas):
        # Termina exatamente onde começa a próxima UC
        pos_fim_cand = ucs_encontradas[idx_atual + 1]["pos_inicio"]
        # Retrocede se antes da próxima UC houver 'MÓDULO...', 'Carga Horária...', etc.
        trecho_pre = texto[:pos_fim_cand]
        match_pre = list(re.finditer(r"\n\s*(?:M[oó]dulo[^\n]*|Carga\s+Hor[aá]ria[^\n]*)\s*", trecho_pre[-350:], re.IGNORECASE))
        if match_pre:
            pos_fim = (pos_fim_cand - 350) + match_pre[0].start()
        else:
            pos_fim = pos_fim_cand
    else:
        # Se for a última UC, termina onde começam as seções gerais do curso ou no fim do arquivo
        padrao_final = re.compile(
            r"\n\s*(?:(?:\d+[\.\)]\s*)?(?:METODOLOGIA\s+DE\s+ENSINO|CRIT[EÉ]RIOS\s+DE\s+AVALIA[ÇC][AÃ]O|PERFIL\s+DO\s+DOCENTE|INSTALA[ÇC][ÕO]ES|RECURSOS\s+DID[AÁ]TICOS|BIBLIOGRAFIA|REFER[EÊ]NCIAS|AVALIA[ÇC][AÃ]O\s+DA\s+APRENDIZAGEM))",
            re.IGNORECASE
        )
        match_final = padrao_final.search(texto, pos_ini)
        if match_final:
            pos_fim = match_final.start()
        else:
            pos_fim = len(texto)

    bloco_uc = texto[pos_ini:pos_fim].strip()
    return bloco_uc


def estruturar_dados_plano_pdf(caminho_pdf, unidade_curricular_alvo=None):
    """
    Analisa o PDF do Plano de Curso e extrai estritamente as informações
    da Unidade Curricular solicitada pelo professor:
    - Unidade Curricular
    - Carga Horária
    - Objetivo Geral
    - Capacidades Técnicas
    - Capacidades Socioemocionais
    - Conhecimentos
    Garante palavras inteiras e completas, sem cortes por quebra de linha.
    """
    texto_bruto = extrair_texto_pdf(caminho_pdf)
    texto_limpo = limpar_texto_pdf(texto_bruto)

    # Isola somente a porção de texto da UC determinada
    texto_uc = isolar_bloco_uc(texto_limpo, unidade_curricular_alvo)

    dados = {
        "unidade_curricular": unidade_curricular_alvo or "",
        "carga_horaria": None,
        "objetivo_geral": "",
        "capacidades_tecnicas": [],
        "capacidades_socioemocionais": [],
        "conhecimentos": [],
        "texto_bruto": texto_uc
    }

    # 1. Nome da Unidade Curricular
    match_uc = re.search(r"(?:Unidade\s+Curricular|Detalhamento\s+da\s+Unidade\s+Curricular|UC)\s*[:\-]\s*([^\n\r]+)", texto_uc, re.IGNORECASE)
    if match_uc:
        nome_uc_extraido = re.split(r"\s+Carga\s+Hor", match_uc.group(1), flags=re.IGNORECASE)[0].strip()
        if nome_uc_extraido:
            dados["unidade_curricular"] = " ".join(nome_uc_extraido.split()).strip()

    # 2. Carga Horária da UC específica
    match_ch = re.search(r"Carga\s+Hor[aá]ria:\s*(\d+)", texto_uc, re.IGNORECASE)
    if match_ch:
        dados["carga_horaria"] = int(match_ch.group(1))

    # 3. Objetivo Geral da UC
    match_obj = re.search(
        r"Objetivo\s+Geral:\s*([\s\S]+?)(?=\n\s*(?:Capacidades\s+T[eé]cnicas|Capacidades\s+B[aá]sicas|Capacidades\s+Socioemocionais|CONHECIMENTOS|$))",
        texto_uc,
        re.IGNORECASE
    )
    if match_obj:
        obj_texto = match_obj.group(1)
        # Normaliza espaços mantendo todas as palavras completas
        dados["objetivo_geral"] = " ".join(obj_texto.split()).strip()

    # 4. Capacidades Técnicas (unindo frases multilinhas sem cortes de palavras)
    match_cap_tec = re.search(
        r"\n\s*Capacidades\s+T[eé]cnicas\s*\n([\s\S]+?)(?=\n\s*(?:Capacidades\s+Socioemocionais|Capacidades\s+B[aá]sicas|CONHECIMENTOS|$))",
        texto_uc,
        re.IGNORECASE
    )
    if match_cap_tec:
        bloco = match_cap_tec.group(1)
        linhas = [l.strip() for l in bloco.split("\n") if l.strip()]
        itens = []
        item_atual = ""

        for linha in linhas:
            if eh_linha_lixo(linha):
                continue
            has_bullet = bool(re.match(r"^[•\-\u2022\uf0b7\*\►\▸\▪\▫]\s*", linha))
            linha_sem_bullet = re.sub(r"^[•\-\u2022\uf0b7\*\►\▸\▪\▫\s]+", "", linha).strip()
            is_verb = bool(re.match(r"^[A-ZÁÉÍÓÚ][a-zà-ÿ]+(?:ar|er|ir|or)\b", linha_sem_bullet))

            if has_bullet or (is_verb and not item_atual):
                if item_atual:
                    cap_limpa = limpar_numeracao_item(item_atual)
                    if cap_limpa and not eh_linha_lixo(cap_limpa) and cap_limpa not in itens:
                        itens.append(cap_limpa)
                item_atual = linha_sem_bullet
            elif is_verb and len(item_atual) > 25 and (item_atual.endswith(".") or linha_sem_bullet.split()[0] in ["Utilizar", "Aplicar", "Estruturar", "Codificar", "Interpretar", "Identificar", "Reconhecer"]):
                if item_atual:
                    cap_limpa = limpar_numeracao_item(item_atual)
                    if cap_limpa and not eh_linha_lixo(cap_limpa) and cap_limpa not in itens:
                        itens.append(cap_limpa)
                item_atual = linha_sem_bullet
            else:
                if item_atual:
                    if item_atual.endswith("-"):
                        item_atual = item_atual[:-1] + linha_sem_bullet
                    else:
                        item_atual = f"{item_atual} {linha_sem_bullet}".strip()
                else:
                    item_atual = linha_sem_bullet

        if item_atual:
            cap_limpa = limpar_numeracao_item(item_atual)
            if cap_limpa and not eh_linha_lixo(cap_limpa) and cap_limpa not in itens:
                itens.append(cap_limpa)

        dados["capacidades_tecnicas"] = [i for i in itens if len(i) > 10 and not eh_linha_lixo(i)]

    # 5. Capacidades Socioemocionais
    match_cap_socio = re.search(
        r"\n\s*Capacidades\s+Socioemocionais\s*\n([\s\S]+?)(?=\n\s*(?:CONHECIMENTOS|$))",
        texto_uc,
        re.IGNORECASE
    )
    if match_cap_socio:
        bloco = match_cap_socio.group(1)
        linhas = [l.strip() for l in bloco.split("\n") if l.strip()]
        itens_socio = []
        item_atual = ""
        for linha in linhas:
            if eh_linha_lixo(linha):
                continue
            has_bullet = bool(re.match(r"^[•\-\u2022\uf0b7\*\►\▸\▪\▫]\s*", linha))
            linha_sem_bullet = re.sub(r"^[•\-\u2022\uf0b7\*\►\▸\▪\▫\s]+", "", linha).strip()
            is_verb = bool(re.match(r"^[A-ZÁÉÍÓÚ][a-zà-ÿ]+(?:ar|er|ir|or)\b", linha_sem_bullet))

            if has_bullet or (is_verb and not item_atual):
                if item_atual:
                    cap_limpa = limpar_numeracao_item(item_atual)
                    if cap_limpa and not eh_linha_lixo(cap_limpa) and cap_limpa not in itens_socio:
                        itens_socio.append(cap_limpa)
                item_atual = linha_sem_bullet
            elif is_verb and len(item_atual) > 25 and (item_atual.endswith(".") or linha_sem_bullet.split()[0] in ["Valorizar", "Demonstrar", "Atuar", "Colaborar", "Trabalhar"]):
                if item_atual:
                    cap_limpa = limpar_numeracao_item(item_atual)
                    if cap_limpa and not eh_linha_lixo(cap_limpa) and cap_limpa not in itens_socio:
                        itens_socio.append(cap_limpa)
                item_atual = linha_sem_bullet
            else:
                if item_atual:
                    if item_atual.endswith("-"):
                        item_atual = item_atual[:-1] + linha_sem_bullet
                    else:
                        item_atual = f"{item_atual} {linha_sem_bullet}".strip()
                else:
                    item_atual = linha_sem_bullet

        if item_atual:
            cap_limpa = limpar_numeracao_item(item_atual)
            if cap_limpa and not eh_linha_lixo(cap_limpa) and cap_limpa not in itens_socio:
                itens_socio.append(cap_limpa)

        dados["capacidades_socioemocionais"] = [i for i in itens_socio if len(i) > 10 and not eh_linha_lixo(i)]

    # 6. Conhecimentos (limpando ruídos institucionais como 'Plano de Curso' e unindo tópicos)
    match_conhec = re.search(r"\n\s*CONHECIMENTOS\s*\n([\s\S]+)$", texto_uc, re.IGNORECASE)
    if match_conhec:
        bloco = match_conhec.group(1)
        linhas = [l.strip() for l in bloco.split("\n") if l.strip()]
        conhecimentos = []
        item_atual = ""

        for linha in linhas:
            if re.match(r"^(?:UNIDADE\s+CURRICULAR|M[OÓ]DULO|CARGA\s+HOR[AÁ]RIA|METODOLOGIA|CRIT[EÉ]RIOS|PERFIL|INSTALA[ÇC]|OBJETIVO\s+GERAL|FUN[ÇC][OÕ]ES)", linha, re.IGNORECASE):
                break
            if eh_linha_lixo(linha):
                continue

            # Verifica se a linha atual é continuação da anterior
            continua = False
            if item_atual:
                palavras = item_atual.split()
                ult_palavra = palavras[-1].lower() if palavras else ""
                if item_atual.endswith("-") or ult_palavra in ["de", "da", "do", "dos", "das", "para", "com", "em", "e", "ou", "a", "o", "por", "sobre", "na", "no"]:
                    continua = True
                elif re.match(r"^[a-zà-ÿ]", linha):
                    continua = True

            if continua:
                if item_atual.endswith("-"):
                    item_atual = item_atual[:-1] + linha
                else:
                    item_atual = f"{item_atual} {linha}".strip()
            else:
                if item_atual:
                    item_limpo = limpar_numeracao_item(item_atual)
                    if len(item_limpo) > 2 and not eh_linha_lixo(item_limpo) and not item_limpo.startswith("http") and item_limpo not in conhecimentos:
                        conhecimentos.append(item_limpo)
                item_atual = linha

        if item_atual:
            item_limpo = limpar_numeracao_item(item_atual)
            if len(item_limpo) > 2 and not eh_linha_lixo(item_limpo) and not item_limpo.startswith("http") and item_limpo not in conhecimentos:
                conhecimentos.append(item_limpo)

        dados["conhecimentos"] = conhecimentos

    return dados
