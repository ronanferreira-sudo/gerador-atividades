import requests
import hashlib

cache_atividades = {}


def preprocessar_texto(texto):
    texto = texto.replace("\n", " ")
    texto = " ".join(texto.split())
    return texto[:3000]


def gerar_hash(texto_pdf, dificuldade, tipo, quantidade):
    base = f"{preprocessar_texto(texto_pdf)}-{dificuldade}-{tipo}-{quantidade}"
    return hashlib.md5(base.encode()).hexdigest()


def gerar_atividade(texto_pdf, dificuldade, tipo="objetiva", quantidade=5):

    print("Chamando Ollama...")

    key = gerar_hash(texto_pdf, dificuldade, tipo, quantidade)

    # =========================
    # CACHE HIT
    # =========================
    if key in cache_atividades:
        print("CACHE HIT - resposta instantânea")
        return cache_atividades[key]

    # =========================
    # PROMPT
    # =========================
    prompt = f"""
Você é um professor especialista na elaboração de avaliações educacionais.

Analise cuidadosamente o conteúdo abaixo:

{preprocessar_texto(texto_pdf)}

INSTRUÇÕES GERAIS:

- Gere EXATAMENTE {quantidade} questões
- Dificuldade: {dificuldade}
- Tipo da atividade: {tipo}

REGRA MAIS IMPORTANTE:

VOCÊ DEVE GERAR EXATAMENTE {quantidade} QUESTÕES NUMERADAS DE 1 ATÉ {quantidade}.
Não pode gerar menos.
Não pode gerar mais.

Se não cumprir essa regra, a resposta será inválida.

REGRAS DE CONTEÚDO:

- Crie perguntas SOMENTE baseadas no conteúdo fornecido
- Não inclua perguntas sobre:
  nome do curso
  tema da aula
  professor
  carga horária
  metodologia
  objetivos
  avaliação
  recursos didáticos

FORMATO:

Atividade:

1.
2.
3.
...
"""

    try:

        resposta = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.1:8b",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 1200
                }
            },
            timeout=300
        )

        if resposta.status_code != 200:
            print("Erro Ollama:", resposta.text)
            return "Erro ao gerar atividade"

        dados = resposta.json()
        atividade = dados.get("response", "")

        # salva no cache
        cache_atividades[key] = atividade

        return atividade

    except Exception as erro:
        print("Erro:", erro)
        return "Erro ao conectar com a IA"