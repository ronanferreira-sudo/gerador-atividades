import requests

def gerar_atividade(
    conteudo,
    dificuldade,
    tipo,
    quantidade
):

    prompt = f"""
Você é um professor experiente.

Crie uma atividade educacional.

Tema:
{conteudo}

Dificuldade:
{dificuldade}

Tipo:
{tipo}

Quantidade de questões:
{quantidade}

Regras:

- Se for objetiva, gere apenas questões objetivas.
- Se for discursiva, gere apenas questões discursivas.
- Se for mista, gere metade objetivas e metade discursivas.
- Nas objetivas use 4 alternativas.
- Informe o gabarito quando houver questões objetivas.

Organize a atividade pronta para impressão.
"""

    resposta = requests.post(
        "http://localhost:11434/api/generate",
        json={
           "model": "llama3.1:8b",
            "prompt": prompt,
            "stream": False
        },
        timeout=300
    )

    return resposta.json()["response"]