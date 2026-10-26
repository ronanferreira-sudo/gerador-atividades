import sys
sys.path.insert(0, r'C:\projetos\gerador_atividades')

from utils.texto_utils import limpar_numeracao_texto, limpar_numeracao_item

# Teste 1: O exemplo exato que o usuário citou
exemplo_usuario = "1 Componentes  de Microcomputadores • 1.1 Componentes  Internos • 1.1.1  CPU • 1.1.2  Armazenamento • 1.1.3  Memória"
resultado = limpar_numeracao_texto(exemplo_usuario)

print("=== TESTE CONHECIMENTOS ===")
print("Antes: ", exemplo_usuario)
print("Depois:", resultado)

# Teste 2: Capacidade numerada
cap_exemplo = "1.1.2 Diagnosticar defeitos em fontes de alimentação ATX"
res_cap = limpar_numeracao_texto(cap_exemplo)
print("\n=== TESTE CAPACIDADE ===")
print("Antes: ", cap_exemplo)
print("Depois:", res_cap)

assert "1.1.1" not in resultado, "Erro: número ainda presente!"
assert "1 " not in resultado, "Erro: número ainda presente!"
assert "1.1.2" not in res_cap, "Erro: número ainda presente!"
print("\n✅ Todos os testes passaram com sucesso!")
