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
        instrucao_tipo = "TODAS as questoes devem ser OBJETIVAS de multipla escolha com 4 alternativas A) B) C) D). Nao misture com discursivas."
    elif tipo == "discursiva":
        instrucao_tipo = "TODAS as questoes devem ser DISCURSIVAS (abertas para resposta dissertativa). Nao misture com objetivas."
    else:
        instrucao_tipo = "MISTURE questoes objetivas (multipla escolha) e discursivas (abertas)."

    prompt = f"""
INSTRUCAO: Crie {quantidade} questoes nivel {dificuldade} com base NO CONTEUDO ABAIXO.

{preprocessar_texto(texto_pdf)}

{instrucao_tipo}

REGRAS ABSOLUTAS:
- VA DIRETO PARA "Questao 1:" - SEM introducao, sem "Aqui estao", sem frases iniciais
- SEMPRE comeca exatamente com "Questao 1:"
- Nao invente assuntos fora do conteudo
- Nao pergunte sobre carga horaria, professor, objetivos, metodologia, avaliacao ou recursos
- NAO use asteriscos, negrito ou qualquer formatacao
- NAO coloque o tipo da questao (Objetiva/Discursiva) no enunciado
"""

    tentativas = 0
    max_tentativas = 3
    while tentativas < max_tentativas:
        try:
            resposta = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": "llama3.1:8b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 900
                    }
                },
                timeout=120
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
