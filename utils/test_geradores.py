"""Teste dos dois geradores de Excel (técnico e qualificação)."""
import sys
sys.path.insert(0, '.')

from datetime import datetime
from utils.excel_planejamento_generator import gerar_excel_planejamento

AULAS_TESTE = [
    {
        "dia": 1,
        "nivel_bloom": "Lembrar",
        "capacidade": "Reconhecer os conceitos fundamentais de redes de computadores",
        "conhecimento": "Topologia de redes\nProtocolos TCP/IP\nModelo OSI",
        "estrategia": "AULA EXPOSITIVA DIALOGADA",
        "ambiente": "LABORATORIO T.I",
        "recursos": "NOTEBOOK\nTELA DIGITAL\nCOMPUTADORES",
        "carga_horaria_str": "4 HS",
        "criterios": "VERIFICAR SE O ALUNO RECONHECE OS CONCEITOS BÁSICOS DE REDES.",
        "instrumentos": "PERGUNTAS ORAIS E CHECKLIST TEÓRICO.",
        "situacao_aprendizagem": "https://recursosdidaticos.senai.br",
        "data_inicio": datetime(2026, 11, 10),
        "data_fim": datetime(2026, 11, 10),
    },
    {
        "dia": 2,
        "nivel_bloom": "Entender",
        "capacidade": "Compreender o funcionamento dos protocolos de comunicação",
        "conhecimento": "Protocolo IP\nMáscara de sub-rede\nGateway padrão",
        "estrategia": "ESTUDO DIRIGIDO\nDISCUSSÃO MEDIADA",
        "ambiente": "LABORATORIO T.I",
        "recursos": "NOTEBOOK\nTELA DIGITAL\nCOMPUTADORES",
        "carga_horaria_str": "4 HS",
        "criterios": "AVALIAR O ENTENDIMENTO DOS PROTOCOLOS DE COMUNICAÇÃO.",
        "instrumentos": "QUESTIONÁRIO FORMATIVO.",
        "situacao_aprendizagem": "https://recursosdidaticos.senai.br",
        "data_inicio": datetime(2026, 11, 11),
        "data_fim": datetime(2026, 11, 11),
    },
]

cabecalho_tecnico = {
    "nome_curso": "TÉCNICO EM INFORMÁTICA",
    "unidade_curricular": "Redes de Computadores",
    "codigo_turma": "TEC.2026.1.100",
    "modalidade": "HABILITAÇÃO TÉCNICA",
    "unidade_escolar": "Taquaralto - Centro de Formação Profissional",
    "carga_horaria": 80,
    "data_inicio": "10/11/2026",
    "data_fim": "20/12/2026",
    "instrutor": "RONAN JOSÉ FERREIRA",
}

cabecalho_qualif = {
    "nome_curso": "INFORMÁTICA BÁSICA",
    "unidade_curricular": "Ferramentas Digitais",
    "codigo_turma": "QUAL.2026.1.200",
    "modalidade": "QUALIFICAÇÃO PROFISSIONAL",
    "unidade_escolar": "Taquaralto - Centro de Formação Profissional",
    "carga_horaria": 40,
    "data_inicio": "10/11/2026",
    "data_fim": "10/12/2026",
    "instrutor": "RONAN JOSÉ FERREIRA",
}

print("Testando gerador TÉCNICO (.xlsx)...")
try:
    saida_t = gerar_excel_planejamento(cabecalho_tecnico, AULAS_TESTE, caminho_saida="outputs/TESTE_tecnico.xlsx")
    print(f"  [OK] Arquivo gerado: {saida_t}")
except Exception as e:
    print(f"  [ERRO] Erro: {e}")
    import traceback; traceback.print_exc()

print()
print("Testando gerador QUALIFICAÇÃO (.xlsx)...")
try:
    saida_q = gerar_excel_planejamento(cabecalho_qualif, AULAS_TESTE, caminho_saida="outputs/TESTE_qualificacao.xlsx")
    print(f"  [OK] Arquivo gerado: {saida_q}")
except Exception as e:
    print(f"  [ERRO] Erro: {e}")
    import traceback; traceback.print_exc()
