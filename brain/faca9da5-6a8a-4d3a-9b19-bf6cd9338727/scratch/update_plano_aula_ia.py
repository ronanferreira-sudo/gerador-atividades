import sys
sys.path.insert(0, r'C:\projetos\gerador_atividades')

with open(r'C:\projetos\gerador_atividades\ia\plano_aula.py', 'r', encoding='utf-8') as f:
    code = f.read()

nova_funcao = '''

def gerar_plano_aula_de_planejamento(aula, nome_curso, uc, horas_dia):
    """
    Gera um plano de aula detalhado baseado diretamente na aula do Planejamento Docente,
    garantindo alinhamento com a Taxonomia de Bloom, capacidades e conhecimentos.
    """
    dia = aula.get("dia", 1)
    nivel_bloom = aula.get("nivel_bloom", "Entender")
    capacidade = aula.get("capacidade", "")
    conhecimento = aula.get("conhecimento", "")
    estrategia = aula.get("estrategia", "AULA EXPOSITIVA DIALOGADA E ATIVIDADES PRÁTICAS")
    recursos = aula.get("recursos", "NOTEBOOK, TELA DIGITAL, COMPUTADORES")
    criterios = aula.get("criterios", "Verificar o entendimento e aplicação dos conceitos.")
    instrumentos = aula.get("instrumentos", "Perguntas direcionadas e atividades práticas.")

    key = hashlib.md5(f"plan-bloom-{nome_curso}-{uc}-{dia}-{capacidade[:50]}-{horas_dia}".encode()).hexdigest()

    if not hasattr(cache_planos, 'dados'):
        cache_planos.dados = {}

    if key in cache_planos.dados:
        print(f"CACHE PLANO DOCENTE DIA {dia} HIT")
        return (dia, cache_planos.dados[key])

    prompt = f"""
Voce e um especialista pedagogico do SENAI.
Crie um Plano de Aula detalhado e pratico para a seguinte aula, derivada do Planejamento Docente:

Curso: {nome_curso}
Unidade Curricular: {uc}
Dia/Encontro: {dia}
Carga Horaria: {horas_dia} horas
Nivel Cognitivo (Taxonomia de Bloom): {nivel_bloom}

DIRETRIZES DO PLANEJAMENTO DOCENTE:
- Capacidade a desenvolver: {capacidade}
- Conhecimentos da aula: {conhecimento}
- Estrategia de Ensino: {estrategia}
- Recursos Didaticos: {recursos}
- Criterios de Avaliacao: {criterios}
- Instrumentos de Avaliacao: {instrumentos}

Gere APENAS o plano de aula estruturado em texto puro:
1. Identificacao:
   - Curso: {nome_curso}
   - Unidade Curricular: {uc}
   - Aula / Encontro: {dia} ({horas_dia} horas)
   - Nivel Bloom: {nivel_bloom}

2. Objetivos da Aula:
   (Formule objetivos claros com verbos compativeis com o nivel {nivel_bloom})

3. Conteudo Programatico:
   (Detalhamento dos topicos de conhecimento desta aula)

4. Estrategia Didatica (Passo a Passo da Aula):
   - Abertura / Introducao:
   - Desenvolvimento / Pratica:
   - Fechamento / Sintese:

5. Recursos Didaticos Utilizados:

6. Avaliacao da Aprendizagem:
   - Criterios:
   - Instrumentos:

Comece diretamente com "1. Identificacao:".
"""

    tentativas = 0
    max_tentativas = 3
    while tentativas < max_tentativas:
        try:
            resposta = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3.1:8b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": 2000,
                        "temperature": 0.2
                    }
                },
                timeout=300
            )

            if resposta.status_code == 200:
                data = resposta.json()
                plano = data.get("response", "").strip()
                if len(plano) >= 80:
                    cache_planos.dados[key] = plano
                    print(f"✅ Plano de Aula do DIA {dia} gerado com sucesso via Ollama!")
                    return (dia, plano)

            tentativas += 1
        except Exception as e:
            tentativas += 1
            print(f"Erro IA dia {dia}: {e}")
            import time
            time.sleep(3)

    # Fallback estruturado baseado no próprio Planejamento Docente
    plano_fallback = f"""1. Identificacao:
- Curso: {nome_curso}
- Unidade Curricular: {uc}
- Aula: Encontro {dia} ({horas_dia}h)
- Nivel Cognitivo (Taxonomia de Bloom): {nivel_bloom}

2. Objetivos da Aula:
- Desenvolver a capacidade: {capacidade}
- Compreender e aplicar os conceitos fundamentais previstos para este encontro.

3. Conteudo Programatico:
- {conhecimento.replace(' • ', chr(10) + '- ')}

4. Estrategia Didatica:
- Abertura: Contextualizacao dos objetivos e ativacao de conhecimentos previos.
- Desenvolvimento: {estrategia}.
- Pratica: Exercicios de fixacao e procedimentos orientados.
- Fechamento: Sintese dos pontos-chave e esclarecimento de duvidas.

5. Recursos Didaticos:
- {recursos.replace(chr(10), ', ')}

6. Avaliacao da Aprendizagem:
- Criterios: {criterios}
- Instrumentos: {instrumentos}
"""
    cache_planos.dados[key] = plano_fallback
    return (dia, plano_fallback)


def gerar_todos_planos_de_planejamento(aulas, nome_curso, uc, horas_dia, max_workers=2):
    """
    Gera todos os planos de aula em paralelo a partir da lista de aulas do Planejamento Docente.
    """
    print(f"📅 Gerando {len(aulas)} Planos de Aula a partir do Planejamento Docente...")
    resultados = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                gerar_plano_aula_de_planejamento, aula, nome_curso, uc, horas_dia
            ): aula.get("dia", idx + 1) for idx, aula in enumerate(aulas)
        }
        concluidos = 0
        total = len(aulas)
        for future in as_completed(futures):
            dia, plano = future.result()
            resultados[dia] = plano
            concluidos += 1
            print(f"📊 Progresso Planos: {concluidos}/{total} gerados.")

    return [resultados[dia] for dia in sorted(resultados.keys())]
'''

if 'def gerar_plano_aula_de_planejamento' not in code:
    code = code + nova_funcao
    with open(r'C:\projetos\gerador_atividades\ia\plano_aula.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print("Funções adicionadas em ia/plano_aula.py com sucesso!")
else:
    print("Já existia em ia/plano_aula.py.")
