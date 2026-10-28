import re

SIMBOLOS_INICIAIS_REGEX = r'^[\s\?\¿\▪\▫\•\●\○\■\□\►\▸\◆\◇\✔\√\*\-\–\—\~\_\:\;\.\,\uf0b7\uf0a7\u2022\u25aa\u25ab\u25cf\u25cb\u25a0\u25a1\u2023\u2043]+'
NUMERACAO_REGEX = r'^(\d+(\.\d+)*\.?|[a-zA-Z]\)|\d+\))\s*[-–—]?\s*'

PADROES_LIXO_ITEM = [
    r"^plano\s+de\s+curso",
    r"^plano\s+de\s+ensino",
    r"^p[aá]gina\s+\d+",
    r"^servi[çc]o\s+nacional",
    r"^departamento\s+regional",
    r"^federa[çc][aã]o",
    r"^fieto",
    r"^fp\.ep",
    r"^m[oó]dulo\b",
    r"^espec[ií]fico\b",
    r"^b[aá]sico\b",
    r"^introdut[oó]rio\b",
    r"^unidade\s+curricular",
    r"^detalhamento\s+da\s+unidade",
    r"^capacidades\s+(?:t[eé]cnicas|socioemocionais|b[aá]sicas)",
    r"^conhecimentos",
    r"^conte[uú]dos\s+formativos",
    r"^objetivo\s+geral",
    r"^carga\s+hor[aá]ria",
    r"^horas\b",
    r"^\d+\s*h(?:oras)?\b",
    r"^fun[çc][oõ]es",
    r"^f\.\d+",
]


def eh_linha_lixo(linha):
    """Verifica se uma linha é cabeçalho, rodapé ou ruído institucional."""
    if not linha:
        return True
    s = str(linha).strip()
    if not s or len(s) < 2:
        return True
    # Remove símbolos iniciais para testar o texto real
    s_limpo = re.sub(SIMBOLOS_INICIAIS_REGEX, '', s).strip()
    s_limpo = re.sub(NUMERACAO_REGEX, '', s_limpo).strip()
    if not s_limpo or len(s_limpo) < 2:
        return True
    s_lower = s_limpo.lower()
    for p in PADROES_LIXO_ITEM:
        if re.search(p, s_lower, re.IGNORECASE):
            return True
    return False


def limpar_numeracao_item(item):
    """
    Remove números e quaisquer símbolos ou '?' no início de itens de conhecimento ou capacidade, tais como:
    '▪ ', '? ', '• ', '1 ', '1. ', '1.1 ', '? 1.1 ', '▪ 1.2 ', '- 1. ', 'a) ', '1) ', '• '
    Garante que a palavra comece limpa sem símbolos estranhos ou ponto de interrogação.
    Descarta itens que sejam ruídos institucionais como 'Plano de Curso'.
    """
    if not item or eh_linha_lixo(item):
        return ""
    s = str(item).strip()
    while True:
        s_antigo = s
        s = re.sub(SIMBOLOS_INICIAIS_REGEX, '', s).strip()
        s = re.sub(NUMERACAO_REGEX, '', s).strip()
        if s == s_antigo:
            break
    # Remove múltiplos espaços internos
    s = re.sub(r"\s+", " ", s).strip()
    if eh_linha_lixo(s):
        return ""
    return s


def limpar_numeracao_texto(texto, separador="\n"):
    """
    Limpa símbolos ('?', '•', '▪', etc.) e numerações de itens em textos que
    contenham separador ' • ', quebras de linha ou múltiplos tópicos.
    Descarta automaticamente linhas de cabeçalho como 'Plano de Curso'.
    Retorna os tópicos limpos, por padrão um por linha.
    """
    if not texto:
        return ""

    texto = str(texto).strip()

    # Identifica se há quebras ou separadores comuns
    partes = re.split(r'[\n\r]+|\s*[•▪▫●○■□►▸\uf0b7\u2022\u25aa]\s*|\s+\?\s+', texto)
    if len(partes) > 1:
        partes_limpas = [limpar_numeracao_item(p) for p in partes]
        partes_validas = [p for p in partes_limpas if p and not eh_linha_lixo(p)]
        return separador.join(partes_validas)

    return limpar_numeracao_item(texto)

