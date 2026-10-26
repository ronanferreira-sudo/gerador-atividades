import re

def limpar_numeracao(texto):
    if not texto:
        return ""
    
    # Se contiver separador de tópicos " • "
    if " • " in texto:
        partes = texto.split(" • ")
        partes_limpas = [limpar_item(p) for p in partes]
        return " • ".join([p for p in partes_limpas if p])
    
    # Se contiver quebras de linha
    if "\n" in texto:
        linhas = texto.split("\n")
        linhas_limpas = [limpar_item(l) for l in linhas]
        return "\n".join(linhas_limpas)
    
    return limpar_item(texto)

def limpar_item(item):
    if not item:
        return ""
    item = item.strip()
    # Remove padrões como:
    # "1 ", "1. ", "1.1 ", "1.1.1 ", "1.1.1. ", "1 - ", "1.1 - ", "a) ", "1) "
    # Regex: no início da string, um ou mais grupos de dígitos separados por ponto,
    # opcionalmente seguidos de ponto, parênteses ou traço.
    item_limpo = re.sub(r"^(\d+(\.\d+)*\.?|[a-zA-Z]\)|\d+\))\s*[-–—]?\s*", "", item).strip()
    return item_limpo

# Testes com o exemplo do usuário:
exemplo = "1 Componentes  de Microcomputadores • 1.1 Componentes  Internos • 1.1.1  CPU • 1.1.2  Armazenamento • 1.1.3  Memória"
res = limpar_numeracao(exemplo)
print("Original:", exemplo)
print("Limpo:   ", res)

exemplo_cap = "1.1. Identificar os componentes de hardware do microcomputador."
print("Cap original:", exemplo_cap)
print("Cap limpa:   ", limpar_numeracao(exemplo_cap))
