import requests
import hashlib
import threading

# Cache thread-safe — cada usuário tem seu próprio cache isolado
cache_atividades = threading.local()


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
    # CACHE THREAD-SAFE
    # =========================
    if not hasattr(cache_atividades, 'dados'):
        cache_atividades.dados = {}

    if key in cache_atividades.dados:
        print("CACHE HIT")
        return cache_atividades.dados[key]

    print("Chamando Ollama...")

    prompt = f"""
Crie {quantidade} questoes {tipo} nivel {dificuldade} com base no conteudo:

{preprocessar_texto(texto_pdf)}

Regras:
- Apenas as questoes, sem introducoes ou respostas
- Objetivas: multipla escolha A) B) C) D) sem gabarito
- Discursivas: abertas
- Mistas: misture as duas
- Nao invente assuntos fora do conteudo
- Nao pergunte sobre carga horaria, professor, objetivos, metodologia, avaliacao ou recursos
- Comece direto na questao 1
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
                        "temperature": 0.1,
                        "num_predict": 2000
                    }
                },
                timeout=300
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

            cache_atividades.dados[key] = atividade
            return atividade

        except Exception as erro:
            tentativas += 1
            print(f"Erro (tentativa {tentativas}/{max_tentativas}):", erro)
            if tentativas >= max_tentativas:
                return "Erro ao conectar com a IA"
            import time
            time.sleep(5)

    return "Erro ao conectar com a IA"
