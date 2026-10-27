import os
import json
import re
from datetime import datetime, timedelta
import requests
from utils.texto_utils import limpar_numeracao_item, limpar_numeracao_texto

# URL do Ollama configurável via .env
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")

# Níveis da Taxonomia de Bloom e verbos correspondentes
NIVEIS_BLOOM = {
    "Lembrar": {
        "verbos": ["Reconhecer", "Identificar", "Listar", "Nomear", "Descrever", "Definir"],
        "estrategias": ["AULA EXPOSITIVA DIALOGADA", "LEITURA ORIENTADA", "APRESENTAÇÃO DE CONCEITOS"],
        "recursos": ["NOTEBOOK\nTELA DIGITAL\nSLIDES ILUSTRATIVOS\nDOCUMENTOS TÉCNICOS"],
        "criterios": "VERIFICAR SE O ALUNO RECONHECE E DEFINE CORRETAMENTE OS CONCEITOS BÁSICOS.",
        "instrumentos": "PERGUNTAS DIRECIONADAS ORALMENTE E CHECKLIST TEÓRICO."
    },
    "Entender": {
        "verbos": ["Compreender", "Interpretar", "Explicar", "Diferenciar", "Classificar", "Associar"],
        "estrategias": ["AULA EXPOSITIVA DIALOGADA\nDEMONSTRAÇÃO PRÁTICA", "ESTUDO DIRIGIDO", "DISCUSSÃO EM GRUPO"],
        "recursos": ["NOTEBOOK\nTELA DIGITAL\nCOMPUTADORES\nCOMPONENTES REAIS"],
        "criterios": "VERIFICAR O ENTENDIMENTO DO ALUNO, POR MEIO DE PERGUNTAS E ANÁLISE CONCEITUAL.",
        "instrumentos": "QUESTIONÁRIO FORMATIVO E DISCUSSÃO MEDIADA."
    },
    "Aplicar": {
        "verbos": ["Executar", "Realizar", "Utilizar", "Empregar", "Operar", "Implementar"],
        "estrategias": ["AULA EXPOSITIVA\nATIVIDADE PRÁTICA EM LABORATÓRIO", "RODÍZIO DE BANCADA", "PRÁTICA GUIADA"],
        "recursos": ["NOTEBOOK\nTELA DIGITAL\nCOMPUTADORES\nFERRAMENTAS E KITS DE HARDWARE"],
        "criterios": "VERIFICAR A EXECUÇÃO CORRETA DOS PROCEDIMENTOS PRÁTICOS E DE SEGURANÇA.",
        "instrumentos": "OBSERVAÇÃO DIRETA COM LISTA DE VERIFICAÇÃO (CHECKLIST) E ATIVIDADE PRÁTICA."
    },
    "Analisar": {
        "verbos": ["Analisar", "Comparar", "Diagnosticar", "Examinar", "Testar", "Verificar"],
        "estrategias": ["ESTUDO DE CASO\nATIVIDADE PRÁTICA DE DIAGNÓSTICO", "TESTES DE FUNCIONAMENTO", "RESOLUÇÃO DE PROBLEMAS"],
        "recursos": ["NOTEBOOK\nLABORATÓRIO DE T.I\nCOMPUTADORES\nINSTRUMENTOS DE MEDIÇÃO"],
        "criterios": "AVALIAR A CAPACIDADE DE ANÁLISE, DIAGNÓSTICO E COMPARAÇÃO DO ALUNO.",
        "instrumentos": "RELATÓRIO PRÁTICO DE DIAGNÓSTICO E ATIVIDADE DE BANCADA."
    },
    "Avaliar": {
        "verbos": ["Avaliar", "Validar", "Criticar", "Julgar", "Medir", "Revisar"],
        "estrategias": ["ATIVIDADE AVALIATIVA PRÁTICA", "AVALIAÇÃO PRÁTICA INDIVIDUAL/EM DUPLA", "SIMULAÇÃO REALÍSTICA"],
        "recursos": ["NOTEBOOK\nLABORATÓRIO T.I\nCOMPUTADORES\nSITUAÇÃO DE APRENDIZAGEM"],
        "criterios": "VERIFICAR O DOMÍNIO COMPLETO DAS COMPETÊNCIAS E AVALIAÇÃO DE RESULTADOS.",
        "instrumentos": "AVALIAÇÃO PRÁTICA FORMAL E RUBRICA DE DESEMPENHO."
    },
    "Criar": {
        "verbos": ["Criar", "Desenvolver", "Projetar", "Construir", "Planejar", "Elaborar"],
        "estrategias": ["PROJETO PRÁTICO INTEGRADOR", "DESENVOLVIMENTO DE PROTÓTIPO", "ATIVIDADE DE PROJETO"],
        "recursos": ["NOTEBOOK\nLABORATÓRIO T.I\nCOMPUTADORES\nKITS DIDÁTICOS"],
        "criterios": "AVALIAR A CAPACIDADE DE CRIAÇÃO E INTEGRAÇÃO DE SOLUÇÕES COMPLETAS.",
        "instrumentos": "APRESENTAÇÃO DO PROJETO E RUBRICA DE ENTREGA."
    }
}


def calcular_datas_aulas(data_inicio_str, total_aulas):
    """
    Gera as datas para cada aula em dias úteis (Segunda a Sexta),
    a partir da data inicial.
    """
    if not data_inicio_str:
        hoje = datetime.now()
        data_inicio = hoje + timedelta(days=1)
    else:
        if "/" in data_inicio_str:
            partes = data_inicio_str.strip().split("/")
            data_inicio = datetime(int(partes[2]), int(partes[1]), int(partes[0]))
        else:
            data_inicio = datetime.strptime(data_inicio_str.strip()[:10], "%Y-%m-%d")

    datas = []
    atual = data_inicio

    while len(datas) < total_aulas:
        if atual.weekday() < 5:
            datas.append(atual)
        atual += timedelta(days=1)

    return datas


def dividir_em_blocos(lista, n):
    """Divide uma lista em n blocos aproximadamente iguais."""
    if not lista:
        return [[] for _ in range(n)]
    k, m = divmod(len(lista), n)
    return [lista[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n)]


def limitar_texto_palavras_completas(texto, limite=100):
    """Trunca um texto respeitando os limites de palavras completas."""
    if not texto or len(texto) <= limite:
        return texto
    cortado = texto[:limite]
    if " " in cortado:
        cortado = cortado.rsplit(" ", 1)[0]
    return cortado.strip()


def gerar_planejamento_algoritmico(dados_plano, dados_matriz, total_aulas, horas_por_dia, datas):
    """
    Gera o planejamento docente completo garantindo a Taxonomia de Bloom
    e a divisão exata dos conteúdos e horas por dia, SEM numerações de tópicos
    e com palavras 100% completas.
    """
    conhecimentos_brutos = dados_plano.get("conhecimentos", [])
    conhecimentos = [limpar_numeracao_item(c) for c in conhecimentos_brutos if limpar_numeracao_item(c)]

    capacidades_plano = [limpar_numeracao_texto(c) for c in dados_plano.get("capacidades_tecnicas", []) if limpar_numeracao_texto(c)]

    if not conhecimentos:
        conhecimentos = [
            f"Fundamentos de {dados_plano.get('unidade_curricular', 'Conteúdo')}",
            "Conceitos e características técnicas",
            "Componentes e arquitetura",
            "Operação e procedimentos práticos",
            "Testes e diagnóstico",
            "Atividades práticas integradoras"
        ]

    blocos_conhecimentos = dividir_em_blocos(conhecimentos, total_aulas)

    aulas = []
    for dia in range(1, total_aulas + 1):
        proporcao = dia / total_aulas

        if proporcao <= 0.25:
            nivel = "Lembrar" if dia == 1 else "Entender"
        elif proporcao <= 0.65:
            nivel = "Entender" if dia == 2 else "Aplicar"
        elif proporcao < 0.90:
            nivel = "Aplicar" if dia < total_aulas - 1 else "Analisar"
        else:
            nivel = "Avaliar"

        cfg_bloom = NIVEIS_BLOOM[nivel]

        # Seleciona tópicos de conhecimento para o dia SEM números
        topicos_dia = [limpar_numeracao_item(t) for t in blocos_conhecimentos[dia - 1] if limpar_numeracao_item(t)]
        texto_conhecimento = " • ".join(topicos_dia) if topicos_dia else "Fundamentos e práticas profissionais"

        if capacidades_plano:
            idx_cap = min(dia - 1, len(capacidades_plano) - 1)
            cap_base = capacidades_plano[idx_cap]
        else:
            verbo = cfg_bloom["verbos"][dia % len(cfg_bloom["verbos"])]
            topico_ref = topicos_dia[0] if topicos_dia else texto_conhecimento
            topico_limpo = limitar_texto_palavras_completas(topico_ref, 80)
            cap_base = f"{verbo} os conceitos e procedimentos relativos a {topico_limpo}."

        cap_base = limpar_numeracao_texto(cap_base)

        if dia == total_aulas:
            estrategia = "ATIVIDADE AVALIATIVA PRATICA"
            criterios = "VERIFICAR O ENTENDIMENTO DO ALUNO, POR MEIO DE UMA ATIVIDADE PRATICA AVALIATIVA."
            instrumentos = "SERAO FEITAS PERGUNTAS E ATIVIDADE PRATICA NO COMPUTADOR / BANCADA."
        else:
            estrategia = cfg_bloom["estrategias"][dia % len(cfg_bloom["estrategias"])]
            criterios = cfg_bloom["criterios"]
            instrumentos = cfg_bloom["instrumentos"]

        data_aula = datas[dia - 1] if dia - 1 < len(datas) else datetime.now()

        aula = {
            "dia": dia,
            "nivel_bloom": nivel,
            "capacidade": cap_base,
            "conhecimento": texto_conhecimento,
            "estrategia": estrategia,
            "ambiente": "LABORATORIO T.I",
            "recursos": "NOTEBOOK\nTELA DIGITAL\nCOMPUTADORES\nCOMPONENTES",
            "carga_horaria_str": f"{horas_por_dia} HS",
            "criterios": criterios,
            "instrumentos": instrumentos,
            "situacao_aprendizagem": f"Situação de Aprendizagem da UC - Encontro {dia}",
            "data_inicio": data_aula,
            "data_fim": data_aula
        }
        aulas.append(aula)

    return aulas


def gerar_planejamento_ia(dados_plano, dados_matriz, total_aulas, horas_por_dia, datas):
    """
    Chama o Ollama para enriquecer os planos de aula com a Taxonomia de Bloom.
    Em caso de falha ou lentidão, faz fallback transparente para o gerador algorítmico.
    """
    uc = dados_plano.get("unidade_curricular", "")
    objetivo = dados_plano.get("objetivo_geral", "")

    conhecimentos_limpos = [limpar_numeracao_item(c) for c in dados_plano.get("conhecimentos", []) if limpar_numeracao_item(c)]
    conhecimentos_str = "\n".join(conhecimentos_limpos[:40])

    capacidades_limpas = [limpar_numeracao_texto(c) for c in dados_plano.get("capacidades_tecnicas", []) if limpar_numeracao_texto(c)]
    capacidades_str = "\n".join(capacidades_limpas)

    matriz_resumo = []
    for item in dados_matriz[:10]:
        cap_itin = limpar_numeracao_texto(item.get('capacidade_itinerario', ''))
        matriz_resumo.append(f"- {cap_itin} (Bloom: {item.get('detalhamento_bloom', '')})")
    matriz_str = "\n".join(matriz_resumo) if matriz_resumo else "Conforme Matriz de Referência"

    prompt = f"""
Voce e um especialista em Planejamento Docente do SENAI com foco na Taxonomia de Bloom.
Elabore o planejamento de {total_aulas} aulas para a Unidade Curricular: "{uc}".
Carga horaria por aula: {horas_por_dia} horas.

OBJETIVO DA UC:
{objetivo}

CAPACIDADES DA MATRIZ / PLANO:
{capacidades_str}
{matriz_str}

CONHECIMENTOS A DISTRIBUIR:
{conhecimentos_str}

REQUISITOS PEDAGOGICOS OBRIGATORIOS:
1. Distribua os conhecimentos progressivamente ao longo das {total_aulas} aulas.
2. Aplique a Taxonomia de Bloom (Lembrar -> Entender -> Aplicar -> Analisar -> Avaliar).
3. REGRA CRITICA: NUNCA coloque numeros de topicos ou secoes (como "1", "1.1", "1.1.1", "2.1") nas capacidades ou conhecimentos. Escreva apenas os nomes e termos limpos separados por " • ".
4. Cada aula deve ter:
   - capacidade: Texto da capacidade iniciando com verbo de Bloom (SEM NUMEROS no inicio)
   - conhecimento: Topicos de conhecimento daquela aula separados por " • " (SEM NUMEROS de topicos)
   - estrategia: Estrategia de ensino (ex: AULA EXPOSITIVA DIALOGADA, ATIVIDADE PRATICA EM LABORATORIO, ATIVIDADE AVALIATIVA PRATICA)
   - criterios: Criterio de avaliacao claro
   - instrumentos: Instrumento de avaliacao (ex: PERGUNTAS ORAIS, CHECKLIST PRATICO, AVALIACAO PRATICA)
5. REGRA DE INTEGRIDADE: Escreva sempre palavras completas e frases inteiras em portugues, nunca corte palavras pela metade e nunca termine sentencas com preposicoes ou termos incompletos.

Responda ESTRITAMENTE em formato JSON valido, sem nenhum texto antes ou depois:
{{
  "aulas": [
    {{
      "dia": 1,
      "nivel_bloom": "Lembrar",
      "capacidade": "Reconhecer componentes fundamentais...",
      "conhecimento": "Componentes de Microcomputadores • Componentes Internos • CPU • Memoria",
      "estrategia": "AULA EXPOSITIVA DIALOGADA",
      "criterios": "Verificar se o aluno reconhece os componentes.",
      "instrumentos": "Perguntas direcionadas e checklist."
    }}
  ]
}}
"""

    try:
        print(f"🤖 Solicitando ao Ollama planejamento docente ({total_aulas} aulas com Taxonomia de Bloom)...")
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 4096
                }
            },
            timeout=45
        )

        if resp.status_code == 200:
            texto_resp = resp.json().get("response", "").strip()
            match_json = re.search(r"\{[\s\S]*\}", texto_resp)
            if match_json:
                dados_json = json.loads(match_json.group(0))
                lista_aulas_ia = dados_json.get("aulas", [])
                if len(lista_aulas_ia) == total_aulas:
                    aulas_finais = []
                    for idx, a in enumerate(lista_aulas_ia):
                        dia = idx + 1
                        data_aula = datas[idx] if idx < len(datas) else datetime.now()
                        cap_ia = limpar_numeracao_texto(a.get("capacidade", ""))
                        con_ia = limpar_numeracao_texto(a.get("conhecimento", ""))
                        aulas_finais.append({
                            "dia": dia,
                            "nivel_bloom": a.get("nivel_bloom", "Entender"),
                            "capacidade": cap_ia,
                            "conhecimento": con_ia,
                            "estrategia": a.get("estrategia", "AULA EXPOSITIVA\nATIVIDADE PRATICA"),
                            "ambiente": "LABORATORIO T.I",
                            "recursos": "NOTEBOOK\nTELA DIGITAL\nCOMPUTADORES",
                            "carga_horaria_str": f"{horas_por_dia} HS",
                            "criterios": a.get("criterios", "VERIFICAR O ENTENDIMENTO DO ALUNO."),
                            "instrumentos": a.get("instrumentos", "PERGUNTAS DURANTE A AULA E ATIVIDADES PRATICAS."),
                            "situacao_aprendizagem": f"Situação de Aprendizagem - Encontro {dia}",
                            "data_inicio": data_aula,
                            "data_fim": data_aula
                        })
                    print("✅ Planejamento gerado com sucesso via Ollama!")
                    return aulas_finais

    except Exception as e:
        print(f"⚠️ Aviso na geração via IA: {e}. Utilizando gerador algorítmico robusto...")

    # Fallback algorítmico
    return gerar_planejamento_algoritmico(dados_plano, dados_matriz, total_aulas, horas_por_dia, datas)
