import re

def limpar_numeracao_item(item):
    """
    Remove números no início de itens de conhecimento ou capacidade, tais como:
    '1 ', '1. ', '1.1 ', '1.1.1 ', '1.1.1. ', '1 - ', '1.1 - ', 'a) ', '1) '
    """
    if not item:
        return ""
    item = str(item).strip()
    item_limpo = re.sub(r"^(\d+(\.\d+)*\.?|[a-zA-Z]\)|\d+\))\s*[-–—]?\s*", "", item).strip()
    # Remove múltiplos espaços internos
    item_limpo = re.sub(r"\s+", " ", item_limpo)
    return item_limpo


def limpar_numeracao_texto(texto):
    """
    Limpa numerações de itens em textos que contenham separador ' • ' ou quebras de linha.
    Exemplo:
    '1 Componentes de Microcomputadores • 1.1 Componentes Internos • 1.1.1 CPU'
    -> 'Componentes de Microcomputadores • Componentes Internos • CPU'
    """
    if not texto:
        return ""

    texto = str(texto)

    if " • " in texto:
        partes = texto.split(" • ")
        partes_limpas = [limpar_numeracao_item(p) for p in partes]
        return " • ".join([p for p in partes_limpas if p])

    if "\n" in texto:
        linhas = texto.split("\n")
        linhas_limpas = [limpar_numeracao_item(l) for l in linhas]
        return "\n".join([l for l in linhas_limpas if l])

    return limpar_numeracao_item(texto)
