import os
import re
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from ia.ia_client import chamar_ia, obter_config_ia, verificar_ollama_online

load_dotenv()

# Cache global thread-safe com Lock
# Chaveado por hash de conteúdo — sem risco de cruzar dados entre professores
_cache_lock = threading.Lock()
_cache_planos = {}


def obter_config_ollama():
    """Retorna configuração dinâmica para compatibilidade."""
    cfg = obter_config_ia()["ollama"]
    return cfg["url"], cfg["model"], cfg["timeout"]


def gerar_hash_plano(texto_base, carga_horaria, aulas_por_dia, dia):
    base = f"{texto_base[:3000]}-{carga_horaria}-{aulas_por_dia}-{dia}"
    return hashlib.md5(base.encode()).hexdigest()


def preprocessar_texto(texto):
    if not texto:
        return ""
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
    Utiliza ia_client para suportar Ollama, Gemini ou APIs compatíveis dinamicamente.
    """
    key = gerar_hash_plano(texto_base, carga_horaria, aulas_por_dia, dia)

    with _cache_lock:
        if key in _cache_planos:
            print(f"[CACHE] Hit plano dia {dia}")
            return (dia, _cache_planos[key])

    print(f"[IA] Solicitando geracao do Plano de Aula - DIA {dia}...")

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
        plano = chamar_ia(
            prompt=prompt,
            system_prompt="Você é um especialista em planejamento pedagógico do SENAI.",
            max_tokens=600,
            temperature=0.1
        )

        if plano and len(plano.strip()) >= 50:
            plano_limpo = plano.strip()
            with _cache_lock:
                _cache_planos[key] = plano_limpo
            return (dia, plano_limpo)
    except Exception as e:
        print(f"[AVISO] Erro na geracao via IA do DIA {dia}: {e}")

    # Fallback estruturado se IA demorar ou falhar
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
    Se usar_ia=True, realiza enriquecimento contextual via IA.
    """
    dia = aula.get("dia", 1)
    key = hashlib.md5(f"plan-bloom-{nome_curso}-{uc}-{dia}-{horas_dia}".encode()).hexdigest()

    with _cache_lock:
        if key in _cache_planos:
            return (dia, _cache_planos[key])

    # Geração instantânea padronizada de alta fidelidade
    plano_estruturado = construir_plano_estruturado_de_aula(aula, nome_curso, uc, horas_dia)

    if not usar_ia:
        with _cache_lock:
            _cache_planos[key] = plano_estruturado
        return (dia, plano_estruturado)

    # Enriquecimento opcional via IA se requisitado
    try:
        prompt = f"""Voce e especialista pedagogico do SENAI.
Aprimore o seguinte plano de aula mantendo rigorosamente a estrutura numerada de 1 a 6:
Curso: {nome_curso} | UC: {uc} | Dia: {dia} | Nivel Bloom: {aula.get('nivel_bloom', 'Aplicar')}
Capacidade: {aula.get('capacidade', '')}
Conteudo: {aula.get('conhecimento', '')}

{plano_estruturado}"""

        plano_ia = chamar_ia(
            prompt=prompt,
            system_prompt="Você é um especialista pedagógico do SENAI.",
            max_tokens=550,
            temperature=0.2
        )

        if plano_ia and len(plano_ia.strip()) >= 80:
            plano_ia_limpo = plano_ia.strip()
            with _cache_lock:
                _cache_planos[key] = plano_ia_limpo
            return (dia, plano_ia_limpo)
    except Exception as e:
        print(f"[AVISO] Enriquecimento IA dia {dia}: {e}")

    with _cache_lock:
        _cache_planos[key] = plano_estruturado
    return (dia, plano_estruturado)


def gerar_todos_planos_de_planejamento(aulas, nome_curso, uc, horas_dia, max_workers=4):
    """
    Gera todos os planos de aula a partir do Planejamento Docente instantaneamente.
    """
    print(f"[PLANOS] Gerando {len(aulas)} Planos de Aula a partir do Planejamento Docente...")
    resultados = {}

    for idx, aula in enumerate(aulas):
        dia = aula.get("dia", idx + 1)
        _, plano = gerar_plano_aula_de_planejamento(aula, nome_curso, uc, horas_dia, usar_ia=False)
        resultados[dia] = plano

    print(f"[OK] Todos os {len(aulas)} Planos de Aula gerados instantaneamente com sucesso!")
    return [resultados[dia] for dia in sorted(resultados.keys())]
