import os
import requests
import hashlib
import threading
import re
from dotenv import load_dotenv

# Carrega variáveis de ambiente do .env
load_dotenv()

# Cache global thread-safe com Lock
# Chaveado por hash do conteúdo — sem risco de cruzar dados entre usuários
_cache_lock = threading.Lock()
_cache_atividades = {}


def obter_config_ollama():
    """
    Retorna a configuração atual do Ollama de forma dinâmica,
    priorizando valores definidos no .env.
    """
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
    modelo = os.environ.get("OLLAMA_MODEL", "llama3.2")
    try:
        timeout = int(os.environ.get("OLLAMA_TIMEOUT", "180"))
    except ValueError:
        timeout = 180
    return url, modelo, timeout


def verificar_ollama_online(timeout=2.0):
    """
    Verifica rapidamente se o Ollama está online para evitar esperas longas desnecessárias.
    """
    url, _, _ = obter_config_ollama()
    try:
        resp = requests.get(f"{url}/api/tags", timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False


def extrair_topicos_relevantes(texto_base):
    """
    Extrai tópicos técnicos reais do texto base, ignorando completamente metadados
    administrativos (identificação, curso, carga horária, estratégias, recursos).
    Garante que perguntas geradas (pela IA ou fallback) tenham sentido pedagógico.
    """
    if not texto_base:
        return ["fundamentos técnicos e procedimentos operacionais"]

    topicos = []

    # 1. Se for um plano estruturado com seção "Conteúdo Programático"
    match_cp = re.search(
        r'Conte[uú]do\s+Program[aá]tico:?(.*?)(?=(?:\d+\.\s*)?Estrat[eé]gia|\Z)',
        texto_base,
        re.DOTALL | re.IGNORECASE
    )
    if match_cp:
        for linha in match_cp.group(1).splitlines():
            limpa = re.sub(r'^[\s\-\*•▪▫●○■□►▸\d\.\)]+', '', linha).strip()
            # Remove sufixos como números soltos "2" no fim da linha
            limpa = re.sub(r'\s+\d+$', '', limpa).strip()
            if len(limpa) >= 3:
                topicos.append(limpa)

    # 2. Se não encontrou em Conteúdo Programático, tenta extrair de Objetivos / Capacidades
    if not topicos:
        match_obj = re.search(
            r'Objetivos da Aula:?(.*?)(?=(?:\d+\.\s*)?Conte[uú]do|\Z)',
            texto_base,
            re.DOTALL | re.IGNORECASE
        )
        if match_obj:
            for linha in match_obj.group(1).splitlines():
                limpa = re.sub(
                    r'^(?:Desenvolver a capacidade|Meta de aprendizagem|Objetivo)[\s\:\-]+',
                    '',
                    linha,
                    flags=re.IGNORECASE
                )
                limpa = re.sub(r'^[\s\-\*•▪▫●○■□►▸\d\.\)]+', '', limpa).strip()
                limpa = re.sub(r'\s+\d+$', '', limpa).strip()
                if len(limpa) >= 6:
                    topicos.append(limpa)

    # 3. Filtragem de linhas eliminando cabeçalhos administrativos
    if not topicos:
        linhas = [l.strip() for l in texto_base.splitlines() if l.strip()]
        for l in linhas:
            if re.match(
                r'^(?:\d+[\.\)]\s*)?(?:Identifica|Curso|Unidade Curricular|Carga Hor|Aula\s*/\s*Encontro|N[ií]vel Cognitivo|Taxonomia|Estrat[eé]gia Did|Recursos Did|Abertura|Desenvolvimento|Fechamento|Notebook|Data:|Professor:)',
                l,
                re.IGNORECASE
            ):
                continue
            limpa = re.sub(r'^[\s\-\*•▪▫●○■□►▸\d\.\)]+', '', l).strip()
            limpa = re.sub(r'\s+\d+$', '', limpa).strip()
            if len(limpa) >= 10:
                topicos.append(limpa)

    # 4. Fallback final: quebra por pontuação ignorando termos administrativos
    if not topicos:
        frases = [f.strip() for f in re.split(r'[\.\;\n]+', texto_base) if len(f.strip()) >= 15]
        topicos = [
            re.sub(r'^\d+\s*', '', f).strip()
            for f in frases
            if not re.search(r'Identifica[cç][aã]o|Curso|Carga Hor[aá]ria|Aula|Encontro', f, re.IGNORECASE)
        ]

    return topicos if topicos else ["fundamentos técnicos e procedimentos operacionais"]


def extrair_conteudo_pedagogico(texto):
    """
    Higieniza o conteúdo para o prompt da IA: se for um plano de aula completo,
    extrai apenas os objetivos, o nível cognitivo e o conteúdo programático,
    eliminando metadados de cabeçalho e recursos que poderiam poluir a geração.
    """
    if not texto:
        return ""

    # Se for um plano de aula estruturado
    if "Conteudo Programatico" in texto or "Conteúdo Programático" in texto:
        partes = []

        m_bloom = re.search(
            r'N[ií]vel Cognitivo(?:\s*\(Taxonomia de Bloom\))?\s*:\s*([^\n\r]+)',
            texto,
            re.IGNORECASE
        )
        if m_bloom:
            partes.append(f"NÍVEL COGNITIVO ESPERADO (BLOOM): {m_bloom.group(1).strip()}")

        m_obj = re.search(
            r'Objetivos da Aula:?(.*?)(?=(?:\d+\.\s*)?Conte[uú]do|\Z)',
            texto,
            re.DOTALL | re.IGNORECASE
        )
        if m_obj:
            obj_texto = m_obj.group(1).strip()
            if obj_texto:
                partes.append(f"OBJETIVOS E CAPACIDADES:\n{obj_texto}")

        m_cp = re.search(
            r'Conte[uú]do\s+Program[aá]tico:?(.*?)(?=(?:\d+\.\s*)?Estrat[eé]gia|\Z)',
            texto,
            re.DOTALL | re.IGNORECASE
        )
        if m_cp:
            cp_texto = m_cp.group(1).strip()
            if cp_texto:
                partes.append(f"CONTEÚDO PROGRAMÁTICO (TÓPICOS TÉCNICOS):\n{cp_texto}")

        if partes:
            return "\n\n".join(partes)

    # Texto comum / PDF / inserção manual: filtra metadados administrativos
    linhas = [l.strip() for l in texto.replace("\r", " ").split("\n") if l.strip()]
    linhas_filtradas = [
        l for l in linhas
        if not re.match(
            r'^(?:\d+[\.\)]\s*)?(?:Identifica|Recursos Did|Estrat[eé]gia Did|Carga Hor|Data:|Professor:)',
            l,
            re.IGNORECASE
        )
    ]
    texto_limpo = " ".join(" ".join(linhas_filtradas).split())
    return texto_limpo[:2500]


def preprocessar_texto(texto):
    if not texto:
        return ""
    texto = texto.replace("\n", " ")
    texto = " ".join(texto.split())
    return texto[:2500]


def gerar_hash(texto_pdf, dificuldade, tipo, quantidade):
    base = f"{preprocessar_texto(texto_pdf)}-{dificuldade}-{tipo}-{quantidade}"
    return hashlib.md5(base.encode()).hexdigest()


def gerar_atividade_fallback(texto_base, dificuldade, tipo, quantidade):
    """
    Gera uma atividade formatada e profissional imediatamente caso o serviço de IA
    esteja temporariamente indisponível, usando tópicos pedagógicos reais.
    """
    topicos = extrair_topicos_relevantes(texto_base)

    questoes = []
    for i in range(1, quantidade + 1):
        topico = topicos[(i - 1) % len(topicos)]
        topico_fmt = topico.strip().rstrip(".:;")
        if len(topico_fmt) > 60:
            topico_exibicao = topico_fmt[:57] + "..."
        else:
            topico_exibicao = topico_fmt

        if tipo == "objetiva":
            questoes.append(
                f"Questão {i}: Com base no estudo sobre {topico_exibicao}, assinale a alternativa correta:\n"
                f"A) Trata-se de um conceito fundamental aplicado nos procedimentos operacionais da área técnica.\n"
                f"B) Refere-se a uma abordagem obsoleta desprovida de aplicação prática nas diretrizes vigentes.\n"
                f"C) Não possui relação com os critérios de conformidade e qualidade recomendados.\n"
                f"D) Representa uma técnica secundária cuja utilização é desaconselhada nos padrões atuais.\n"
                f"Resposta correta: A"
            )
        elif tipo == "discursiva":
            questoes.append(
                f"Questão {i}: Explique a importância e a aplicação prática de {topico_exibicao} no contexto profissional, destacando seus principais benefícios e requisitos técnicos."
            )
        else:
            if i % 2 == 1:
                questoes.append(
                    f"Questão {i}: Com relação a {topico_exibicao}, identifique a alternativa correta:\n"
                    f"A) Apresenta conformidade com as diretrizes e procedimentos padrão da disciplina.\n"
                    f"B) Invalida os critérios de qualidade e boas práticas estabelecidos no setor.\n"
                    f"C) Restringe-se exclusivamente a aspectos teóricos sem respaldo de aplicação.\n"
                    f"D) Nenhuma das anteriores.\n"
                    f"Resposta correta: A"
                )
            else:
                questoes.append(
                    f"Questão {i}: Descreva sucintamente como os princípios de {topico_exibicao} devem ser aplicados na resolução de problemas do setor."
                )

    return "\n\n".join(questoes)


def gerar_atividade(texto_pdf, dificuldade, tipo="objetiva", quantidade=5):
    quantidade = int(quantidade)
    quantidade = max(1, min(quantidade, 30))

    url_ollama, modelo_ollama, timeout_ollama = obter_config_ollama()
    print(f"[ATIVIDADE] Tipo={tipo} | Dificuldade={dificuldade} | Qtd={quantidade} | Modelo={modelo_ollama}")

    key = gerar_hash(texto_pdf, dificuldade, tipo, quantidade)

    # 1. Consulta ao Cache Thread-safe
    with _cache_lock:
        if key in _cache_atividades:
            print("[CACHE] Hit atividade")
            return _cache_atividades[key]

    # 2. Verificação Rápida do Ollama
    if not verificar_ollama_online():
        print("[AVISO] Ollama offline. Gerando atividade estruturada de apoio...")
        fallback = gerar_atividade_fallback(texto_pdf, dificuldade, tipo, quantidade)
        with _cache_lock:
            _cache_atividades[key] = fallback
        return fallback

    print(f"[IA] Solicitando ao Ollama ({modelo_ollama}) em {url_ollama} (timeout={timeout_ollama}s)...")

    # 3. Instruções direcionadas e objetivas
    if tipo == "objetiva":
        instrucao_tipo = (
            f"Crie EXATAMENTE {quantidade} questões OBJETIVAS de múltipla escolha de nível {dificuldade}. "
            "Cada questão DEVE ter 4 alternativas (A, B, C, D) e indicar claramente 'Resposta correta: X'."
        )
        formato = "Questão 1: [Enunciado técnico contextualizado]\nA) ...\nB) ...\nC) ...\nD) ...\nResposta correta: A"
        tokens_por_questao = 150
    elif tipo == "discursiva":
        instrucao_tipo = (
            f"Crie EXATAMENTE {quantidade} questões DISCURSIVAS analíticas de nível {dificuldade} para resposta dissertativa técnica."
        )
        formato = "Questão 1: [Enunciado reflexivo/prático]\n\nQuestão 2: [Enunciado]"
        tokens_por_questao = 100
    else:
        metade = quantidade // 2
        resto = quantidade - metade
        instrucao_tipo = (
            f"Crie EXATAMENTE {quantidade} questões de nível {dificuldade}: {metade} OBJETIVAS (com A, B, C, D e Resposta correta) "
            f"e {resto} DISCURSIVAS."
        )
        formato = "Questão 1: [Objetiva]\nA) ...\nB) ...\nC) ...\nD) ...\nResposta correta: A\n\nQuestão 2: [Discursiva]"
        tokens_por_questao = 130

    # Dimensionamento otimizado de tokens para acelerar a geração
    num_predict = min(3500, max(600, quantidade * tokens_por_questao))

    conteudo_pedagogico = extrair_conteudo_pedagogico(texto_pdf)

    prompt = f"""Você é um professor especialista do SENAI.
Crie a lista de questões avaliativas abaixo baseando-se estritamente nestes conteúdos técnicos e objetivos pedagógicos:
---
{conteudo_pedagogico}
---

{instrucao_tipo}

REGRAS OBRIGATÓRIAS:
1. Comece DIRETAMENTE com "Questão 1:" sem introdução, cumprimentos ou saudações.
2. Numere de 1 até {quantidade}: "Questão 1:", "Questão 2:", etc.
3. Não use formatação markdown pesada ou asteriscos desnecessários (evite **).
4. As questões devem focar EXCLUSIVAMENTE nos conceitos técnicos da disciplina. NUNCA faça perguntas sobre cabeçalhos administrativos, identificação de curso, carga horária ou recursos didáticos.
5. Siga rigorosamente o formato:
{formato}

Gere as {quantidade} questões agora:"""

    tentativas = 0
    max_tentativas = 2
    while tentativas < max_tentativas:
        try:
            resposta = requests.post(
                f"{url_ollama}/api/generate",
                json={
                    "model": modelo_ollama,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.2,
                        "num_predict": num_predict,
                        "top_p": 0.9
                    }
                },
                timeout=timeout_ollama
            )

            if resposta.status_code == 200:
                dados = resposta.json()
                atividade = dados.get("response", "").strip()

                if len(atividade) >= 30:
                    with _cache_lock:
                        _cache_atividades[key] = atividade
                    print(f"[OK] Atividade gerada ({len(atividade)} chars)")
                    return atividade

            tentativas += 1
            print(f"[AVISO] Tentativa {tentativas}/{max_tentativas} falhou (status {resposta.status_code})")

        except Exception as erro:
            tentativas += 1
            print(f"[AVISO] Comunicacao IA (tentativa {tentativas}/{max_tentativas}): {erro}")
            if tentativas >= max_tentativas:
                break
            import time
            time.sleep(1)

    print("[AVISO] Retornando atividade estruturada de apoio...")
    fallback = gerar_atividade_fallback(texto_pdf, dificuldade, tipo, quantidade)
    with _cache_lock:
        _cache_atividades[key] = fallback
    return fallback
