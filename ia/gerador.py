import os
import requests
import hashlib
import threading

# Cache global thread-safe com Lock
# Chaveado por hash do conteúdo — sem risco de cruzar dados entre usuários
_cache_lock = threading.Lock()
_cache_atividades = {}

# URL do Ollama configurável via .env
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")


def preprocessar_texto(texto):
    texto = texto.replace("\n", " ")
    texto = " ".join(texto.split())
    return texto[:1500]


def gerar_hash(texto_pdf, dificuldade, tipo, quantidade):
    base = f"{preprocessar_texto(texto_pdf)}-{dificuldade}-{tipo}-{quantidade}"
    return hashlib.md5(base.encode()).hexdigest()


def gerar_atividade(texto_pdf, dificuldade, tipo="objetiva", quantidade=5):

    quantidade = int(quantidade)

    print("Dificuldade:", dificuldade)
    print("Tipo:", tipo)
    print("Quantidade:", quantidade)

    key = gerar_hash(texto_pdf, dificuldade, tipo, quantidade)

    # =========================
    # CACHE GLOBAL THREAD-SAFE
    # =========================
    with _cache_lock:
        if key in _cache_atividades:
            print("CACHE HIT")
            return _cache_atividades[key]

    print("Chamando Ollama...")

    if tipo == "objetiva":
        instrucao_tipo = (
            f"Gere EXATAMENTE {quantidade} questoes OBJETIVAS de multipla escolha, "
            "cada uma com 4 alternativas A) B) C) D) e a Resposta correta identificada. "
            "Nao misture com discursivas."
        )
        exemplo = (
            "Questao 1: Enunciado da questao?\n"
            "A) opcao\nB) opcao\nC) opcao\nD) opcao\n"
            "Resposta correta: A\n\n"
            "Questao 2: Enunciado da questao?\n"
            "A) opcao\nB) opcao\nC) opcao\nD) opcao\n"
            "Resposta correta: B"
        )
    elif tipo == "discursiva":
        instrucao_tipo = (
            f"Gere EXATAMENTE {quantidade} questoes DISCURSIVAS (abertas para resposta dissertativa). "
            "Nao misture com objetivas."
        )
        exemplo = (
            "Questao 1: Enunciado da questao discursiva?\n\n"
            "Questao 2: Enunciado da questao discursiva?"
        )
    else:
        metade = quantidade // 2
        resto = quantidade - metade
        instrucao_tipo = (
            f"Gere EXATAMENTE {quantidade} questoes: {metade} OBJETIVAS (com A B C D e Resposta correta) "
            f"e {resto} DISCURSIVAS (abertas). Alterne entre os tipos."
        )
        exemplo = (
            "Questao 1: Enunciado objetiva?\n"
            "A) opcao\nB) opcao\nC) opcao\nD) opcao\n"
            "Resposta correta: A\n\n"
            "Questao 2: Enunciado discursiva?"
        )

    # Tokens necessários: ~200 por questão objetiva, ~120 por discursiva — com margem de segurança
    tokens_por_questao = 220 if tipo in ("objetiva", "mista") else 150
    num_predict = max(800, quantidade * tokens_por_questao)

    prompt = f"""Voce e um professor avaliador. Crie EXATAMENTE {quantidade} questoes de nivel {dificuldade} sobre o conteudo abaixo.

CONTEUDO:
{preprocessar_texto(texto_pdf)}

{instrucao_tipo}

REGRAS OBRIGATORIAS:
- Comece DIRETAMENTE com "Questao 1:" sem nenhuma introducao ou frase antes
- Numere todas as questoes de 1 ate {quantidade}: "Questao 1:", "Questao 2:", ..., "Questao {quantidade}:"
- Nao use asteriscos, negrito ou markdown
- Nao pergunte sobre carga horaria, objetivos, metodologia ou professor
- Baseie-se APENAS no conteudo fornecido

FORMATO ESPERADO:
{exemplo}

Gere as {quantidade} questoes agora:"""

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
                        "temperature": 0.1,
                        "num_predict": num_predict
                    }
                },
                timeout=180
            )

            if resposta.status_code != 200:
                tentativas += 1
                print(f"Erro Ollama (tentativa {tentativas}/{max_tentativas}): {resposta.status_code}")
                continue

            dados = resposta.json()
            atividade = dados.get("response", "").strip()

            if len(atividade) < 20:
                tentativas += 1
                print(f"Resposta muito curta (tentativa {tentativas}/{max_tentativas}): {len(atividade)} chars")
                continue

            with _cache_lock:
                _cache_atividades[key] = atividade
            return atividade

        except Exception as erro:
            tentativas += 1
            print(f"Erro (tentativa {tentativas}/{max_tentativas}):", erro)
            if tentativas >= max_tentativas:
                return "Erro ao conectar com a IA"
            import time
            time.sleep(5)

    return "Erro ao conectar com a IA"
