import requests
import hashlib

# Cache limpo a cada reinício — garante que parâmetros alterados gerem novas respostas
cache_atividades = {}


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
    # CACHE
    # =========================
    if key in cache_atividades:
        print("CACHE HIT")
        return cache_atividades[key]

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

    try:

        resposta = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.1:8b",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 1500
                }
            },
            timeout=60
        )

        if resposta.status_code != 200:
            print("Erro Ollama:", resposta.text)
            return "Erro ao gerar atividade"

        dados = resposta.json()

        atividade = dados.get("response", "").strip()

        cache_atividades[key] = atividade

        return atividade

    except Exception as erro:
        print("Erro:", erro)
        return "Erro ao conectar com a IA"
