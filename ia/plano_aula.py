import os
import requests
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Cache global thread-safe com Lock
# Chaveado por hash de conteúdo — sem risco de cruzar dados entre professores
_cache_lock = threading.Lock()
_cache_planos = {}

# URL do Ollama configurável via .env
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")


def gerar_hash_plano(texto_base, carga_horaria, aulas_por_dia, dia):
    base = f"{texto_base[:3000]}-{carga_horaria}-{aulas_por_dia}-{dia}"
    return hashlib.md5(base.encode()).hexdigest()


def preprocessar_texto(texto):
    texto = texto.replace("\n", " ")
    texto = " ".join(texto.split())
    return texto[:3000]


def gerar_plano_aula(texto_base, carga_horaria, aulas_por_dia, dia):

    key = gerar_hash_plano(texto_base, carga_horaria, aulas_por_dia, dia)

    # Cache global thread-safe
    with _cache_lock:
        if key in _cache_planos:
            print(f"CACHE PLANO DIA {dia} HIT")
            return (dia, _cache_planos[key])

    print(f"Chamando Ollama - DIA {dia}...")

    prompt = f"""
Crie o plano de aula do DIA {dia}.

Conteúdo base (Matriz de Referência):
{preprocessar_texto(texto_base)}

Com base nos itens da Matriz de Referência acima, distribua os conteúdos ao longo dos dias do curso.
Para o DIA {dia}, selecione os itens mais adequados e crie o plano de aula.

Gere APENAS o plano de aula em texto puro:

1. Identificação:
2. Objetivos:
3. Conteúdo Programático:
4. Estratégia Didática:
5. Recursos Didáticos:
6. Avaliação:

Comece diretamente com "1. Identificação:".
"""

    tentativas = 0
    max_tentativas = 3
    while tentativas < max_tentativas:
        try:
            resposta = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": 900,
                        "temperature": 0.1
                    }
                },
                timeout=120
            )

            if resposta.status_code != 200:
                tentativas += 1
                print(f"Erro Ollama DIA {dia} (tentativa {tentativas}/{max_tentativas}): {resposta.status_code}")
                continue

            data = resposta.json()
            plano = data.get("response", "")

            if len(plano) < 50:
                tentativas += 1
                print(f"Resposta muito curta DIA {dia} (tentativa {tentativas}/{max_tentativas}): {len(plano)} chars")
                continue

            with _cache_lock:
                _cache_planos[key] = plano
            print(f"DIA {dia} OK ({len(plano)} chars)")

            return (dia, plano)

        except Exception as e:
            tentativas += 1
            print(f"Erro na IA DIA {dia} (tentativa {tentativas}/{max_tentativas}):", e)
            if tentativas >= max_tentativas:
                return (dia, "Erro ao conectar com a IA")
            import time
            time.sleep(5)
    
    return (dia, "Erro ao conectar com a IA")


def gerar_todos_planos(texto_pdf, carga_horaria, aulas_por_dia, total_dias, max_workers=1):

    print(f"📅 Total de dias a gerar: {total_dias}")
    print(f"⚡ Workers paralelos: {max_workers}")
    print("-" * 40)

    resultados = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                gerar_plano_aula, texto_pdf, carga_horaria, aulas_por_dia, dia
            ): dia for dia in range(1, total_dias + 1)
        }
        concluidos = 0
        for future in as_completed(futures):
            dia, plano = future.result()
            resultados[dia] = plano
            concluidos += 1
            print(f"📊 Progresso: {concluidos}/{total_dias} dias concluídos")

    print("-" * 40)
    print(f"✅ Geração de planos finalizada! {total_dias} dias gerados.")
    print("=" * 60)

    return [resultados[dia] for dia in sorted(resultados.keys())]


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

    with _cache_lock:
        if key in _cache_planos:
            print(f"CACHE PLANO DOCENTE DIA {dia} HIT")
            return (dia, _cache_planos[key])

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
    max_tentativas = 1
    while tentativas < max_tentativas:
        try:
            resposta = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": 500,
                        "temperature": 0.2
                    }
                },
                timeout=35
            )

            if resposta.status_code == 200:
                data = resposta.json()
                plano = data.get("response", "").strip()
                if len(plano) >= 80:
                    with _cache_lock:
                        _cache_planos[key] = plano
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
    with _cache_lock:
        _cache_planos[key] = plano_fallback
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
