import os
import json
import re
from datetime import datetime, timedelta, date
import requests
from dotenv import load_dotenv
from utils.texto_utils import limpar_numeracao_item, limpar_numeracao_texto, eh_linha_lixo
from utils.matriz_saep_reader import filtrar_matriz_por_uc
from ia.ia_client import chamar_ia

load_dotenv()

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
        "estrategias": ["AULA EXPOSITIVA DIALOGADA\nDEMONSTRAÇÃO CONCEITUAL", "ESTUDO DIRIGIDO", "DISCUSSÃO MEDIADA"],
        "recursos": ["NOTEBOOK\nTELA DIGITAL\nCOMPUTADORES\nEXEMPLOS DIDÁTICOS"],
        "criterios": "VERIFICAR O ENTENDIMENTO E INTERPRETAÇÃO DOS CONCEITOS PELO ALUNO.",
        "instrumentos": "QUESTIONÁRIO FORMATIVO E EXERCÍCIOS DE INTERPRETAÇÃO."
    },
    "Aplicar": {
        "verbos": ["Executar", "Realizar", "Utilizar", "Empregar", "Operar", "Implementar", "Codificar", "Aplicar"],
        "estrategias": ["AULA EXPOSITIVA COM ATIVIDADE PRÁTICA EM LABORATÓRIO", "PRÁTICA GUIADA", "RESOLUÇÃO DE PROBLEMAS PRÁTICOS"],
        "recursos": ["NOTEBOOK\nTELA DIGITAL\nCOMPUTADORES\nAMBIENTE DE DESENVOLVIMENTO / LABORATÓRIO"],
        "criterios": "VERIFICAR A CORRETA EXECUÇÃO DOS PROCEDIMENTOS PRÁTICOS E APLICAÇÃO DOS CONCEITOS.",
        "instrumentos": "OBSERVAÇÃO DIRETA COM LISTA DE CHECAGEM (CHECKLIST) E ATIVIDADES PRÁTICAS."
    },
    "Analisar": {
        "verbos": ["Analisar", "Comparar", "Diagnosticar", "Examinar", "Testar", "Verificar", "Depurar"],
        "estrategias": ["ESTUDO DE CASO\nDEPURAÇÃO E DIAGNÓSTICO", "TESTES DE FUNCIONAMENTO", "ANÁLISE DE QUALIDADE E BOAS PRÁTICAS"],
        "recursos": ["NOTEBOOK\nLABORATÓRIO T.I\nCOMPUTADORES\nFERRAMENTAS DE DIAGNÓSTICO E TESTES"],
        "criterios": "AVALIAR A CAPACIDADE DE ANÁLISE CRÍTICA, DIAGNÓSTICO DE FALHAS E CONFORMIDADE COM PADRÕES.",
        "instrumentos": "RELATÓRIO PRÁTICO DE DIAGNÓSTICO E CHECKLIST DE BOAS PRÁTICAS."
    },
    "Criar": {
        "verbos": ["Criar", "Desenvolver", "Projetar", "Construir", "Planejar", "Elaborar", "Integrar"],
        "estrategias": ["PROJETO PRÁTICO INTEGRADOR", "DESENVOLVIMENTO DE PROTÓTIPO / SOLUÇÃO", "SITUAÇÃO DE APRENDIZAGEM DESAFIADORA"],
        "recursos": ["NOTEBOOK\nLABORATÓRIO T.I\nCOMPUTADORES\nFERRAMENTAS PROFISSIONAIS"],
        "criterios": "AVALIAR A CAPACIDADE DE CRIAÇÃO, INTEGRAÇÃO E MELHORIA DE SOLUÇÕES COMPLETAS.",
        "instrumentos": "APRESENTAÇÃO DO PROJETO E RUBRICA DE ENTREGA DE PRODUTO."
    },
    "Avaliar": {
        "verbos": ["Avaliar", "Validar", "Criticar", "Julgar", "Medir", "Revisar"],
        "estrategias": ["ATIVIDADE AVALIATIVA PRÁTICA", "AVALIAÇÃO PRÁTICA INDIVIDUAL OU EM DUPLA", "SIMULAÇÃO REALÍSTICA"],
        "recursos": ["NOTEBOOK\nLABORATÓRIO T.I\nCOMPUTADORES\nSITUAÇÃO DE APRENDIZAGEM AVALIATIVA"],
        "criterios": "VERIFICAR O DOMÍNIO COMPLETO DAS CAPACIDADES TÉCNICAS E CRITÉRIOS DE DESEMPENHO DA UC.",
        "instrumentos": "AVALIAÇÃO PRÁTICA FORMAL E RUBRICA DE DESEMPENHO TÉCNICO."
    }
}


def calcular_datas_aulas(data_inicio_str, total_aulas, dias_semana=None, feriados=None, periodicidade="semanal"):
    """
    Gera as datas para cada aula conforme os dias da semana selecionados (0=Seg, ..., 6=Dom),
    desconsiderando feriados e recessos municipais/regionais,
    e respeitando a periodicidade ('semanal' ou 'quinzenal' / a cada 15 dias).
    """
    if not data_inicio_str:
        hoje = datetime.now()
        data_inicio = hoje + timedelta(days=1)
    else:
        if "/" in str(data_inicio_str):
            partes = str(data_inicio_str).strip().split("/")
            data_inicio = datetime(int(partes[2]), int(partes[1]), int(partes[0]))
        else:
            data_inicio = datetime.strptime(str(data_inicio_str).strip()[:10], "%Y-%m-%d")

    # Padrão: Segunda a Sexta (0, 1, 2, 3, 4) se não especificado
    if dias_semana is None or len(dias_semana) == 0:
        dias_semana = [0, 1, 2, 3, 4]
    else:
        dias_semana = [int(d) for d in dias_semana if str(d).isdigit()]

    # Conjunto de feriados no formato date
    feriados_set = set()
    if feriados:
        for f in feriados:
            if not f:
                continue
            if isinstance(f, (datetime, date)):
                feriados_set.add(f.date() if isinstance(f, datetime) else f)
            elif isinstance(f, str):
                s = f.strip()[:10]
                try:
                    if "/" in s:
                        p = s.split("/")
                        feriados_set.add(date(int(p[2]), int(p[1]), int(p[0])))
                    elif "-" in s:
                        p = s.split("-")
                        feriados_set.add(date(int(p[0]), int(p[1]), int(p[2])))
                except Exception:
                    pass

    datas = []
    atual = data_inicio.date() if isinstance(data_inicio, datetime) else data_inicio

    eh_quinzenal = (str(periodicidade).lower() in ["quinzenal", "15_dias", "15", "quinzena"])
    segunda_base = atual - timedelta(days=atual.weekday())

    # Itera dia a dia até atingir a quantidade total de aulas necessárias
    iteracoes = 0
    max_iter = total_aulas * 40 + 365  # Proteção contra loop infinito
    while len(datas) < total_aulas and iteracoes < max_iter:
        iteracoes += 1
        if atual.weekday() in dias_semana:
            if eh_quinzenal:
                semanas_decorridas = (atual - segunda_base).days // 7
                if semanas_decorridas % 2 != 0:
                    atual += timedelta(days=1)
                    continue

            if atual not in feriados_set:
                datas.append(datetime.combine(atual, datetime.min.time()))

        atual += timedelta(days=1)

    return datas


def dividir_em_blocos(lista, n):
    """Divide uma lista em n blocos aproximadamente iguais."""
    if not lista:
        return [[] for _ in range(n)]
    if n <= 1:
        return [lista]
    k, m = divmod(len(lista), n)
    return [lista[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n)]


def classificar_bloom_topico(texto):
    """
    Classifica um tópico de conhecimento em uma escala de complexidade cognitiva de Bloom (1 a 6).
    1: Lembrar (Conceitos, Fundamentos, Introdução, Definições, O que é)
    2: Entender (Características, Modelos, Tipos de dados, Variáveis, Constantes, Fluxogramas)
    3: Aplicar (Operadores, Expressões, Comandos, Condicionais, Repetições, Codificação, Compiladores)
    4: Analisar (Indentação, Nomenclatura, Comentários, Legibilidade, Diagnóstico, Depuração, Testes)
    5: Criar (Projetos, Soluções integradas, Inovação, Melhoria contínua, Automação)
    6: Avaliar (Avaliação prática, Validação, Critérios de desempenho)
    """
    t = texto.lower()
    if any(k in t for k in ["avaliação", "validar", "revisão final", "simulado"]):
        return 6
    if any(k in t for k in ["inovação", "melhoria contínua", "visão inovadora", "projeto integrador", "desenvolvimento de soluções"]):
        return 5
    if any(k in t for k in ["indentação", "legibilidade", "padrões de nomenclatura", "nomenclatura", "comentários", "depuração", "debug", "diagnóstico", "teste de mesa", "análise de código"]):
        return 4
    if any(k in t for k in ["operador", "operadores", "aritmético", "relacional", "lógico", "expressões", "expressao", "repetição", "repeticao", "condicional", "condicionais", "laço", "codificação", "codificacao", "compilador", "compiladores", "implementação", "implementacao", "instalação", "configuração"]):
        return 3
    if any(k in t for k in ["tipo de dado", "tipos de dados", "constante", "constantes", "variável", "variavel", "variáveis", "variaveis", "fluxograma", "representações gráficas", "representacao grafica", "arquitetura", "componentes", "características", "ferramentas para codificação"]):
        return 2
    if any(k in t for k in ["fundamento", "fundamentos", "conceito", "conceitos", "definição", "definicao", "introdução", "introducao", "abstração", "abstracao", "etapas para construção", "o que é", "histórico"]):
        return 1
    return 3


def ordenar_conhecimentos_por_bloom(conhecimentos_brutos, matriz_itens=None):
    """
    Filtra ruídos institucionais ('Plano de Curso', cabeçalhos) e
    ordena pedagogicamente os tópicos pela Taxonomia de Bloom.
    """
    conhecimentos_limpos = []
    for c in conhecimentos_brutos:
        c_limpo = limpar_numeracao_item(c)
        if c_limpo and not eh_linha_lixo(c_limpo) and c_limpo not in conhecimentos_limpos:
            conhecimentos_limpos.append(c_limpo)

    if not conhecimentos_limpos:
        return []

    # Ordenação pedagógica por nível de Bloom
    ordenados = sorted(conhecimentos_limpos, key=classificar_bloom_topico)
    return ordenados


def determinar_nivel_bloom_dia(dia, total_aulas):
    """Determina o nível cognitivo da Taxonomia de Bloom para a aula do dia."""
    proporcao = dia / total_aulas
    if dia == 1:
        return "Lembrar"
    elif proporcao <= 0.25:
        return "Entender"
    elif proporcao <= 0.70:
        return "Aplicar"
    elif proporcao < 0.90:
        return "Analisar"
    elif dia < total_aulas:
        return "Criar"
    else:
        return "Avaliar"


def adaptar_verbo_para_bloom(capacidade_texto, nivel_bloom):
    """
    Garante que a capacidade inicie com um verbo perfeitamente alinhado
    ao nível da Taxonomia de Bloom especificado, substituindo verbos de outros níveis
    de forma natural e fluida.
    """
    cap_limpa = limpar_numeracao_texto(capacidade_texto).strip()
    if not cap_limpa:
        return ""

    cfg = NIVEIS_BLOOM.get(nivel_bloom, NIVEIS_BLOOM["Aplicar"])
    verbos_alvo = cfg["verbos"]

    # Se a capacidade já começa com um verbo válido do nível atual, preserva
    primeira_palavra = cap_limpa.split()[0].capitalize()
    if primeira_palavra in verbos_alvo:
        return cap_limpa

    # Substituição limpa de verbos transitivos
    if nivel_bloom == "Lembrar":
        if re.match(r"^(?:Reconhecer|Identificar|Listar|Nomear|Descrever|Definir)\b", cap_limpa, re.I):
            return cap_limpa
        cap_sub = re.sub(r"^[A-ZÁÉÍÓÚ][a-zà-ÿ]+(?:ar|er|ir|or)\b\s*", "", cap_limpa).strip()
        return f"Reconhecer e identificar {cap_sub[0].lower() + cap_sub[1:]}" if cap_sub else cap_limpa

    if nivel_bloom == "Entender":
        if re.match(r"^(?:Compreender|Interpretar|Explicar|Diferenciar|Classificar|Associar)\b", cap_limpa, re.I):
            return cap_limpa
        cap_sub = re.sub(r"^[A-ZÁÉÍÓÚ][a-zà-ÿ]+(?:ar|er|ir|or)\b\s*", "", cap_limpa).strip()
        return f"Compreender e interpretar {cap_sub[0].lower() + cap_sub[1:]}" if cap_sub else cap_limpa

    if nivel_bloom == "Analisar":
        if re.match(r"^(?:Analisar|Identificar|Diagnosticar|Examinar|Testar|Verificar|Depurar)\b", cap_limpa, re.I):
            return cap_limpa
        cap_sub = re.sub(r"^[A-ZÁÉÍÓÚ][a-zà-ÿ]+(?:ar|er|ir|or)\b\s*", "", cap_limpa).strip()
        return f"Analisar e examinar {cap_sub[0].lower() + cap_sub[1:]}" if cap_sub else cap_limpa

    if nivel_bloom == "Criar":
        if re.match(r"^(?:Criar|Desenvolver|Projetar|Elaborar|Construir|Integrar)\b", cap_limpa, re.I):
            return cap_limpa
        cap_sub = re.sub(r"^[A-ZÁÉÍÓÚ][a-zà-ÿ]+(?:ar|er|ir|or)\b\s*", "", cap_limpa).strip()
        return f"Desenvolver soluções aplicando {cap_sub[0].lower() + cap_sub[1:]}" if cap_sub else cap_limpa

    if nivel_bloom == "Avaliar":
        if re.match(r"^(?:Avaliar|Validar|Medir|Revisar)\b", cap_limpa, re.I):
            return cap_limpa
        cap_sub = re.sub(r"^[A-ZÁÉÍÓÚ][a-zà-ÿ]+(?:ar|er|ir|or)\b\s*", "", cap_limpa).strip()
        return f"Avaliar a conformidade e eficácia de {cap_sub[0].lower() + cap_sub[1:]}" if cap_sub else cap_limpa

    return cap_limpa


def formular_capacidade_dia(dia, total_aulas, nivel_bloom, topicos_dia, capacidades_plano, matriz_itens, socioemocionais, uc_nome):
    """
    Gera uma Capacidade completa, contextualizada e rigorosamente coerente
    com a Taxonomia de Bloom, cruzando o Plano de Curso e a Matriz SAEP.
    Garante que jamais haverá frases pela metade, termos cortados ou repetições vazias.
    """
    cfg_bloom = NIVEIS_BLOOM[nivel_bloom]

    # Última aula: Avaliação formal prática somativa
    if dia == total_aulas:
        return f"Avaliar a integridade, conformidade e execução prática dos conhecimentos e procedimentos desenvolvidos na Unidade Curricular de {uc_nome}."

    # Penúltima aula: Projeto integrador / Criação / Inovação
    if dia == total_aulas - 1 and total_aulas > 3:
        if socioemocionais:
            socio_ref = socioemocionais[0]
            if len(socio_ref) > 15:
                return f"Desenvolver soluções técnicas integrando os conhecimentos de {uc_nome}, valorizando a melhoria contínua nos processos de trabalho."
        return f"Desenvolver e integrar soluções técnicas completas de {uc_nome}, propondo melhorias e inovações nos processos de trabalho."

    # Capacidades consolidadas do Plano de Curso + Matriz SAEP (Itinerário e SAEP)
    todas_caps = []
    for c in capacidades_plano:
        c_l = limpar_numeracao_texto(c)
        if c_l and len(c_l) > 15 and not eh_linha_lixo(c_l) and c_l not in todas_caps:
            todas_caps.append(c_l)

    for m in (matriz_itens or []):
        cap_itin = m.get("capacidade_itinerario", "")
        cap_l = limpar_numeracao_texto(cap_itin)
        if cap_l and len(cap_l) > 15 and not eh_linha_lixo(cap_l) and cap_l not in todas_caps:
            todas_caps.append(cap_l)

    topicos_str = " ".join(topicos_dia).lower()
    palavras_topicos = set(w for w in re.findall(r"\b[a-záéíóúãõç]{4,}\b", topicos_str) if w not in ["para", "com", "como", "sobre", "entre"])

    melhor_cap = None
    maior_score = 0

    for cap in todas_caps:
        palavras_cap = set(re.findall(r"\b[a-záéíóúãõç]{4,}\b", cap.lower()))
        score = len(palavras_topicos.intersection(palavras_cap))
        if score > maior_score:
            maior_score = score
            melhor_cap = cap

    # Se encontrou capacidade aderente pelo cruzamento de termos com o conteúdo do dia
    if melhor_cap and maior_score > 0:
        return adaptar_verbo_para_bloom(melhor_cap, nivel_bloom)

    # Mapeamento proporcional se não houver cruzamento direto de palavras
    if todas_caps:
        idx = min(int((dia - 1) / total_aulas * len(todas_caps)), len(todas_caps) - 1)
        cap_cand = todas_caps[idx]
        return adaptar_verbo_para_bloom(cap_cand, nivel_bloom)

    # Fallback contextualizado se não houver capacidades cadastradas
    verbo = cfg_bloom["verbos"][dia % len(cfg_bloom["verbos"])]
    topico_ref = topicos_dia[0] if topicos_dia else f"procedimentos de {uc_nome}"
    return f"{verbo} os conceitos, técnicas e procedimentos relativos a {topico_ref.lower()} na resolução de problemas práticos."


def gerar_planejamento_algoritmico(dados_plano, dados_matriz, total_aulas, horas_por_dia, datas):
    """
    Gera o planejamento docente completo cruzando o Plano de Curso e a Matriz SAEP
    através da Taxonomia de Bloom, com divisão exata e progressiva dos conhecimentos
    e capacidades ao longo dos dias.
    """
    uc_nome = dados_plano.get("unidade_curricular", "Unidade Curricular")

    # 1. Filtra a Matriz SAEP especificamente para esta UC
    matriz_uc = filtrar_matriz_por_uc(dados_matriz, uc_nome)

    # 2. Extrai e limpa capacidades do Plano
    capacidades_plano = [
        limpar_numeracao_texto(c) for c in dados_plano.get("capacidades_tecnicas", [])
        if limpar_numeracao_texto(c) and not eh_linha_lixo(c)
    ]
    socioemocionais = [
        limpar_numeracao_texto(c) for c in dados_plano.get("capacidades_socioemocionais", [])
        if limpar_numeracao_texto(c) and not eh_linha_lixo(c)
    ]

    # 3. Limpa e ordena pedagogicamente os conhecimentos com Bloom
    conhecimentos_ordenados = ordenar_conhecimentos_por_bloom(
        dados_plano.get("conhecimentos", []),
        matriz_itens=matriz_uc
    )

    if not conhecimentos_ordenados:
        conhecimentos_ordenados = [
            f"Fundamentos e conceitos de {uc_nome}",
            "Definições e princípios essenciais",
            "Estruturas e ferramentas de trabalho",
            "Procedimentos e técnicas de aplicação",
            "Operações e implementação prática",
            "Boas práticas e controle de qualidade",
            "Diagnóstico e resolução de problemas",
            "Melhoria contínua e projetos integradores"
        ]

    # Divide os conhecimentos ordenados pelos dias de aula
    blocos_conhecimentos = dividir_em_blocos(conhecimentos_ordenados, total_aulas)

    aulas = []
    for dia in range(1, total_aulas + 1):
        nivel = determinar_nivel_bloom_dia(dia, total_aulas)
        cfg_bloom = NIVEIS_BLOOM[nivel]

        topicos_dia = [t for t in blocos_conhecimentos[dia - 1] if t and not eh_linha_lixo(t)]
        if not topicos_dia:
            topicos_dia = [f"Práticas e aprofundamento em {uc_nome}"]

        texto_conhecimento = "\n".join(topicos_dia)

        capacidade_dia = formular_capacidade_dia(
            dia=dia,
            total_aulas=total_aulas,
            nivel_bloom=nivel,
            topicos_dia=topicos_dia,
            capacidades_plano=capacidades_plano,
            matriz_itens=matriz_uc,
            socioemocionais=socioemocionais,
            uc_nome=uc_nome
        )

        data_aula = datas[dia - 1] if dia - 1 < len(datas) else datetime.now()

        estrategia = cfg_bloom["estrategias"][dia % len(cfg_bloom["estrategias"])]
        criterios = cfg_bloom["criterios"]
        instrumentos = cfg_bloom["instrumentos"]

        # Matriz SAEP para cursos técnicos
        saep_dia = "Não tem cruzamento"
        if matriz_uc:
            idx_m = min(int((dia - 1) / total_aulas * len(matriz_uc)), len(matriz_uc) - 1)
            item_m = matriz_uc[idx_m]
            cap_s = str(item_m.get("capacidade_saep") or "").strip()
            con_r = str(item_m.get("conhecimentos_relacionados") or "").strip()
            if cap_s and con_r:
                saep_dia = f"{cap_s}\n{con_r}"
            elif cap_s:
                saep_dia = cap_s
            elif con_r:
                saep_dia = con_r

        aula = {
            "dia": dia,
            "nivel_bloom": nivel,
            "capacidade": capacidade_dia,
            "conhecimento": texto_conhecimento,
            "saep": saep_dia,
            "estrategia": estrategia,
            "ambiente": "LABORATORIO T.I",
            "recursos": "NOTEBOOK\nTELA DIGITAL\nCOMPUTADORES\nFERRAMENTAS DIDÁTICAS",
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
    Chama o Ollama para enriquecer os planos de aula com o cruzamento da Taxonomia de Bloom.
    Em caso de lentidão, indisponibilidade ou inconsistência de aulas, utiliza o motor
    algorítmico robusto baseado na mesma matriz pedagógica.
    """
    uc = dados_plano.get("unidade_curricular", "")
    objetivo = dados_plano.get("objetivo_geral", "")

    # Filtra matriz especificamente para a UC alvo
    matriz_uc = filtrar_matriz_por_uc(dados_matriz, uc)

    # Conhecimentos ordenados pedagogicamente e limpos
    conhecimentos_ordenados = ordenar_conhecimentos_por_bloom(
        dados_plano.get("conhecimentos", []),
        matriz_itens=matriz_uc
    )
    conhecimentos_str = "\n".join(conhecimentos_ordenados[:40])

    capacidades_plano = [
        limpar_numeracao_texto(c) for c in dados_plano.get("capacidades_tecnicas", [])
        if limpar_numeracao_texto(c) and not eh_linha_lixo(c)
    ]
    capacidades_str = "\n".join(capacidades_plano)

    matriz_resumo = []
    for item in matriz_uc:
        cap_itin = limpar_numeracao_texto(item.get('capacidade_itinerario', ''))
        bloom_ref = item.get('detalhamento_bloom', '')
        con_rel = item.get('conhecimentos_relacionados', '')
        matriz_resumo.append(f"- {cap_itin} (Bloom: {bloom_ref} | Foco: {con_rel})")
    matriz_str = "\n".join(matriz_resumo) if matriz_resumo else "Conforme Matriz de Referência"

    prompt = f"""
Voce e um especialista em Planejamento Docente do SENAI com foco na Taxonomia de Bloom.
Elabore o planejamento de EXATAMENTE {total_aulas} aulas para a Unidade Curricular: "{uc}".
Carga horaria por aula: {horas_por_dia} horas.

OBJETIVO DA UC:
{objetivo}

CAPACIDADES DA MATRIZ SAEP / ITINERÁRIO:
{matriz_str}

CAPACIDADES DO PLANO DE CURSO:
{capacidades_str}

CONHECIMENTOS PEDAGOGICAMENTE ORDENADOS:
{conhecimentos_str}

REQUISITOS PEDAGOGICOS OBRIGATORIOS:
1. Distribua os conhecimentos progressivamente ao longo das {total_aulas} aulas.
2. Aplique a Taxonomia de Bloom na progressao cognitiva:
   - Aulas iniciais: Lembrar e Entender (fundamentos, conceitos, definicoes, tipos de dados, modelos)
   - Aulas intermediarias: Aplicar (operadores, estruturas condicionais e de repeticao, codificacao, compiladores)
   - Aulas avancadas: Analisar (padroes de nomenclatura, indentacao, legibilidade, depuracao de codigo)
   - Aulas finais: Criar e Avaliar (projetos integradores, melhoria de processos, avaliacao pratica)
3. REGRA CRITICA: NUNCA coloque termos como "Plano de Curso" nos conhecimentos.
4. REGRA CRITICA: NUNCA coloque numeros de topicos ou secoes (como "1", "1.1", "2.1") e NUNCA coloque simbolos (?, •, -, *) no inicio das palavras. Escreva apenas os nomes limpos, separados por quebra de linha \\n.
5. Cada aula DEVE conter:
   - dia: numero da aula de 1 a {total_aulas}
   - nivel_bloom: Nivel correspondente (Lembrar, Entender, Aplicar, Analisar, Criar, Avaliar)
   - capacidade: Frase completa iniciando com verbo de Bloom adequado
   - conhecimento: Topicos de conhecimento daquela aula separados por \\n
   - estrategia: Estrategia de ensino coerente
   - criterios: Criterio de avaliacao claro
   - instrumentos: Instrumento de avaliacao correspondente
6. Escreva sempre palavras completas e frases inteiras em portugues, sem cortes.

Responda ESTRITAMENTE em formato JSON valido, sem nenhum texto antes ou depois:
{{
  "aulas": [
    {{
      "dia": 1,
      "nivel_bloom": "Lembrar",
      "capacidade": "Reconhecer conceitos fundamentais...",
      "conhecimento": "Topico 1\\nTopico 2",
      "estrategia": "AULA EXPOSITIVA DIALOGADA",
      "criterios": "Verificar se o aluno reconhece os conceitos.",
      "instrumentos": "Perguntas orais e checklist."
    }}
  ]
}}
"""

    try:
        print(f"[IA] Solicitando planejamento docente com Taxonomia de Bloom ({total_aulas} aulas)...")
        texto_resp = chamar_ia(
            prompt=prompt,
            system_prompt="Você é um especialista em planejamento pedagógico do SENAI e responde exclusivamente em JSON válido.",
            max_tokens=4096,
            temperature=0.2
        )

        if texto_resp:
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
                        con_ia = limpar_numeracao_texto(a.get("conhecimento", ""), separador="\n")
                        nivel_ia = a.get("nivel_bloom", determinar_nivel_bloom_dia(dia, total_aulas))

                        # Validação de integridade do texto
                        if not cap_ia or eh_linha_lixo(cap_ia):
                            cap_ia = formular_capacidade_dia(dia, total_aulas, nivel_ia, con_ia.split("\n"), capacidades_plano, matriz_uc, [], uc)

                        saep_dia = "Não tem cruzamento"
                        if matriz_uc:
                            idx_m = min(int(idx / total_aulas * len(matriz_uc)), len(matriz_uc) - 1)
                            item_m = matriz_uc[idx_m]
                            cap_s = str(item_m.get("capacidade_saep") or "").strip()
                            con_r = str(item_m.get("conhecimentos_relacionados") or "").strip()
                            if cap_s and con_r:
                                saep_dia = f"{cap_s}\n{con_r}"
                            elif cap_s:
                                saep_dia = cap_s
                            elif con_r:
                                saep_dia = con_r

                        aulas_finais.append({
                            "dia": dia,
                            "nivel_bloom": nivel_ia,
                            "capacidade": cap_ia,
                            "conhecimento": con_ia,
                            "saep": saep_dia,
                            "estrategia": a.get("estrategia", "AULA EXPOSITIVA COM ATIVIDADE PRATICA EM LABORATORIO"),
                            "ambiente": "LABORATORIO T.I",
                            "recursos": "NOTEBOOK\nTELA DIGITAL\nCOMPUTADORES\nFERRAMENTAS DIDÁTICAS",
                            "carga_horaria_str": f"{horas_por_dia} HS",
                            "criterios": a.get("criterios", "VERIFICAR O ENTENDIMENTO E DESEMPENHO PRÁTICO DO ALUNO."),
                            "instrumentos": a.get("instrumentos", "OBSERVAÇÃO DIRETA E ATIVIDADE PRÁTICA."),
                            "situacao_aprendizagem": f"Situação de Aprendizagem - Encontro {dia}",
                            "data_inicio": data_aula,
                            "data_fim": data_aula
                        })
                    print("[OK] Planejamento gerado com sucesso via IA!")
                    return aulas_finais

    except Exception as e:
        print(f"[AVISO] Aviso na geração via IA: {e}. Utilizando gerador algorítmico robusto...")

    # Fallback transparente para o gerador algorítmico de alta fidelidade
    return gerar_planejamento_algoritmico(dados_plano, dados_matriz, total_aulas, horas_por_dia, datas)
