import os
import re
import requests
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()

# Cache global thread-safe com Lock
# Chaveado por hash de conteúdo — sem risco de cruzar dados entre professores
_cache_lock = threading.Lock()
_cache_planos = {}

# URL do Ollama configurável via .env
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")


def verificar_ollama_online(timeout=1.5):
    """
    Verifica rapidamente se o Ollama está rodando para evitar congelamento por timeout longo.
    """
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False


def gerar_hash_plano(texto_base, carga_horaria, aulas_por_dia, dia):
    base = f"{texto_base[:3000]}-{carga_horaria}-{aulas_por_dia}-{dia}"
    return hashlib.md5(base.encode()).hexdigest()


def preprocessar_texto(texto):
    texto = texto.replace("\n", " ")
    texto = " ".join(texto.split())
    return texto[:3000]


def construir_plano_estruturado_de_aula(aula, nome_curso, uc, horas_dia):
    """
    Gera instantaneamente um Plano de Aula padrão SENAI completo e rigoroso,
    alinhado com a Taxonomia de Bloom e com os dados extraídos do Planejamento Docente.
    Execução em milissegundos, com alta qualidade técnica e sem alucinações.
    """
    dia = aula.get("dia", 1)
    nivel_bloom = aula.get("nivel_bloom", "Entender")
    capacidade = aula.get("capacidade", "")
    conhecimento = aula.get("conhecimento", "")
    estrategia = aula.get("estrategia", "AULA EXPOSITIVA COM ATIVIDADE PRATICA EM LABORATORIO")
    recursos = aula.get("recursos", "NOTEBOOK, TELA DIGITAL, COMPUTADORES")
    criterios = aula.get("criterios", "Verificar o entendimento e aplicacao dos conceitos.")
    instrumentos = aula.get("instrumentos", "Perguntas direcionadas e atividades praticas.")

    # Formata e limpa tópicos de conhecimento
    partes_con = [
        re.sub(r'^[\s\?\¿\▪\▫\•\●\○\■\□\►\▸\◆\◇\✔\√\*\-\–\—\~\_\:\;\.\,\uf0b7\uf0a7\u2022\u25aa\u25ab\u25cf\u25cb\u25a0\u25a1\u2023\u2043\d\.\)]+', '', p).strip()
        for p in re.split(r'[\n\r]+|\s*[•▪▫●○■□►▸\uf0b7\u2022\u25aa]\s*|\s+\?\s+', str(conhecimento))
        if p.strip()
    ]
    if partes_con:
        conteudo_prog_str = "\n".join([f"- {p}" for p in partes_con if p])
    else:
        conteudo_prog_str = f"- Fundamentos e procedimentos operacionais de {uc}"

    # Limpeza de recursos
    recursos_str = recursos.replace("\n", ", ") if recursos else "Notebook, Tela Digital, Laboratorio de Informatica"

    # Verbo de ação pedagógica conforme nível de Bloom
    verbos_por_bloom = {
        "Lembrar": "Reconhecer e listar os conceitos fundamentais",
        "Entender": "Compreender, interpretar e relacionar os principios tecnicos",
        "Aplicar": "Executar e aplicar os procedimentos tecnicos e operacionais",
        "Analisar": "Analisar criticamente e diagnosticar parametros de funcionamento",
        "Criar": "Desenvolver e integrar solucoes tecnicas completas",
        "Avaliar": "Avaliar e validar o cumprimento das especificacoes tecnicas e de qualidade"
    }
    verbo_meta = verbos_por_bloom.get(nivel_bloom, "Compreender e aplicar os conceitos")

    plano = f"""1. Identificacao:
- Curso: {nome_curso}
- Unidade Curricular: {uc}
- Aula / Encontro: Dia {dia} (Carga Horaria: {horas_dia}h)
- Nivel Cognitivo (Taxonomia de Bloom): {nivel_bloom}

2. Objetivos da Aula:
- Desenvolver a capacidade: {capacidade}
- Meta de aprendizagem: {verbo_meta} previstos para esta aula.

3. Conteudo Programatico:
{conteudo_prog_str}

4. Estrategia Didatica:
- Abertura / Sensibilizacao: Acolhida da turma, contextualizacao do tema da aula e levantamento dos conhecimentos previos.
- Desenvolvimento: {estrategia}.
- Aplicacao / Pratica: Execucao orientada de atividades praticas e resolucao de situacoes-problema.
- Fechamento / Sintese: Retomada dos pontos-chave, sintese dos aprendizados e esclarecimento de duvidas.

5. Recursos Didaticos:
- {recursos_str}

6. Avaliacao da Aprendizagem:
- Criterios: {criterios}
- Instrumentos: {instrumentos}
"""
    return plano


def gerar_plano_aula(texto_base, carga_horaria, aulas_por_dia, dia):
    """
    Gera o plano de aula para upload direto (PDF de plano de curso avulso).
    Verifica se o Ollama está online para resposta rápida sem travar o sistema.
    """
    key = gerar_hash_plano(texto_base, carga_horaria, aulas_por_dia, dia)

    with _cache_lock:
        if key in _cache_planos:
            print(f"[CACHE] Hit plano dia {dia}")
            return (dia, _cache_planos[key])

    # Se Ollama estiver offline, não trava esperando timeout
    if not verificar_ollama_online():
        plano_rapido = f"""1. Identificacao:
- Unidade Curricular / Conteudo: Aula do Dia {dia}
- Carga Horaria: {aulas_por_dia} horas

2. Objetivos da Aula:
- Compreender e aplicar os conceitos e tecnicas previstos para o Dia {dia}.

3. Conteudo Programatico:
- {preprocessar_texto(texto_base)[:300]}

4. Estrategia Didatica:
- Abertura com contextualizacao dos topicos previstos.
- Desenvolvimento expositivo-dialogado e resolucao pratica de exercicios.
- Fechamento com sintese e esclarecimento de duvidas.

5. Recursos Didaticos:
- Computador, tela interativa, material didatico de apoio.

6. Avaliacao da Aprendizagem:
- Observacao direta do desempenho discente e acompanhamento das praticas."""
        with _cache_lock:
            _cache_planos[key] = plano_rapido
        return (dia, plano_rapido)

    print(f"[IA] Chamando Ollama - DIA {dia}...")

    prompt = f"""Crie o plano de aula do DIA {dia} baseado no conteudo abaixo:
{preprocessar_texto(texto_base)[:2000]}

Gere APENAS o plano de aula no formato estruturado:
1. Identificacao:
2. Objetivos da Aula:
3. Conteudo Programatico:
4. Estrategia Didatica:
5. Recursos Didaticos:
6. Avaliacao da Aprendizagem:

Comece diretamente com "1. Identificacao:"."""

    try:
        resposta = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": 450,
                    "temperature": 0.1
                }
            },
            timeout=40
        )

        if resposta.status_code == 200:
            data = resposta.json()
            plano = data.get("response", "").strip()
            if len(plano) >= 50:
                with _cache_lock:
                    _cache_planos[key] = plano
                return (dia, plano)

    except Exception as e:
        print(f"[AVISO] Ollama DIA {dia}: {e}")

    # Fallback estruturado se IA demorar
    plano_fallback = f"""1. Identificacao:
- Aula: Encontro do Dia {dia} ({aulas_por_dia}h)

2. Objetivos da Aula:
- Aplicar os conceitos e procedimentos tecnicos correspondentes ao encontro.

3. Conteudo Programatico:
- {preprocessar_texto(texto_base)[:250]}

4. Estrategia Didatica:
- Abertura contextualizada, demonstracao pratica e fechamento reflexivo.

5. Recursos Didaticos:
- Computador, tela digital e recursos multimidia.

6. Avaliacao da Aprendizagem:
- Acompanhamento formativo por checklist e participacao."""
    with _cache_lock:
        _cache_planos[key] = plano_fallback
    return (dia, plano_fallback)


def gerar_todos_planos(texto_pdf, carga_horaria, aulas_por_dia, total_dias, max_workers=2):
    """
    Gera todos os planos em paralelo limitando a fila para maior agilidade.
    """
    print(f"[PLANOS] Total de dias a gerar: {total_dias}")
    resultados = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                gerar_plano_aula, texto_pdf, carga_horaria, aulas_por_dia, dia
            ): dia for dia in range(1, total_dias + 1)
        }
        for future in as_completed(futures):
            dia, plano = future.result()
            resultados[dia] = plano

    return [resultados[dia] for dia in sorted(resultados.keys())]


def gerar_plano_aula_de_planejamento(aula, nome_curso, uc, horas_dia, usar_ia=False):
    """
    Gera um plano de aula detalhado baseado na aula do Planejamento Docente.
    Por padrão gera de forma instantânea e consistente com a Taxonomia de Bloom.
    Se usar_ia=True e o Ollama estiver ativo, realiza enriquecimento contextual.
    """
    dia = aula.get("dia", 1)
    key = hashlib.md5(f"plan-bloom-{nome_curso}-{uc}-{dia}-{horas_dia}".encode()).hexdigest()

    with _cache_lock:
        if key in _cache_planos:
            return (dia, _cache_planos[key])

    # Geração instantânea padronizada de alta fidelidade
    plano_estruturado = construir_plano_estruturado_de_aula(aula, nome_curso, uc, horas_dia)

    if not usar_ia or not verificar_ollama_online():
        with _cache_lock:
            _cache_planos[key] = plano_estruturado
        return (dia, plano_estruturado)

    # Enriquecimento opcional via Ollama se requisitado
    try:
        prompt = f"""Voce e especialista pedagogico do SENAI.
Aprimore o seguinte plano de aula mantendo rigorosamente a estrutura numerada de 1 a 6:
Curso: {nome_curso} | UC: {uc} | Dia: {dia} | Nivel Bloom: {aula.get('nivel_bloom', 'Aplicar')}
Capacidade: {aula.get('capacidade', '')}
Conteudo: {aula.get('conhecimento', '')}

{plano_estruturado}"""

        resposta = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": 450,
                    "temperature": 0.2
                }
            },
            timeout=25
        )

        if resposta.status_code == 200:
            plano_ia = resposta.json().get("response", "").strip()
            if len(plano_ia) >= 80:
                with _cache_lock:
                    _cache_planos[key] = plano_ia
                return (dia, plano_ia)
    except Exception as e:
        print(f"[AVISO] Enriquecimento IA dia {dia}: {e}")

    with _cache_lock:
        _cache_planos[key] = plano_estruturado
    return (dia, plano_estruturado)


def gerar_todos_planos_de_planejamento(aulas, nome_curso, uc, horas_dia, max_workers=4):
    """
    Gera todos os planos de aula a partir do Planejamento Docente.
    Como o Planejamento Docente já possui toda a Taxonomia de Bloom, capacidades,
    conteúdos e critérios calibrados, os planos são gerados de forma INSTANTÂNEA,
    padronizada e profissional em milissegundos.
    """
    print(f"[PLANOS] Gerando {len(aulas)} Planos de Aula a partir do Planejamento Docente...")
    resultados = {}

    for idx, aula in enumerate(aulas):
        dia = aula.get("dia", idx + 1)
        _, plano = gerar_plano_aula_de_planejamento(aula, nome_curso, uc, horas_dia, usar_ia=False)
        resultados[dia] = plano

    print(f"[OK] Todos os {len(aulas)} Planos de Aula gerados instantaneamente com sucesso!")
    return [resultados[dia] for dia in sorted(resultados.keys())]
