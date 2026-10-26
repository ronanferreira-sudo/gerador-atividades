with open(r'C:\projetos\gerador_atividades\utils\excel_planejamento_generator.py', 'r', encoding='utf-8') as f:
    code = f.read()

if "from utils.texto_utils import limpar_numeracao_texto" not in code:
    code = "from utils.texto_utils import limpar_numeracao_texto\n" + code

velho_bloco = """        # Texto do bloco O que? (Capacidade / Conhecimento)
        texto_o_que = (
            f"CAPACIDADE:\\n"
            f"{aula.get('capacidade', '').strip()}\\n"
            f"CONHECIMENTO\\n"
            f"{aula.get('conhecimento', '').strip()}"
        )"""

novo_bloco = """        # Texto do bloco O que? (Capacidade / Conhecimento) - 100% sem numeração de tópicos
        cap_limpa = limpar_numeracao_texto(aula.get('capacidade', '')).strip()
        con_limpo = limpar_numeracao_texto(aula.get('conhecimento', '')).strip()
        texto_o_que = (
            f"CAPACIDADE:\\n"
            f"{cap_limpa}\\n"
            f"CONHECIMENTO\\n"
            f"{con_limpo}"
        )"""

code_norm = code.replace('\r\n', '\n')
velho_norm = velho_bloco.replace('\r\n', '\n')
novo_norm = novo_bloco.replace('\r\n', '\n')

if velho_norm in code_norm:
    code_norm = code_norm.replace(velho_norm, novo_norm)
    with open(r'C:\projetos\gerador_atividades\utils\excel_planejamento_generator.py', 'w', encoding='utf-8') as f:
        f.write(code_norm)
    print("excel_planejamento_generator.py atualizado com sucesso!")
else:
    print("Trecho não encontrado em excel_planejamento_generator.py")
