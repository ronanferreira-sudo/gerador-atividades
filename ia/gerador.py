import requests
import hashlib

# Cache limpo a cada reinício — garante que parâmetros alterados gerem novas respostas
cache_atividades = {}


def preprocessar_texto(texto):
    texto = texto.replace("\n", " ")
    texto = " ".join(texto.split())
    return texto[:3000]


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
Você é um professor especialista em elaboração de avaliações.

CONTEÚDO PARA AS QUESTÕES:

{preprocessar_texto(texto_pdf)}

INSTRUÇÕES:

1. Gere EXATAMENTE {quantidade} questões.

2. Todas as questões devem ser elaboradas SOMENTE com base no conteúdo fornecido.

3. Não invente assuntos que não estejam presentes no conteúdo.

4. Não faça perguntas sobre:
- carga horária;
- professor;
- objetivos;
- metodologia;
- avaliação;
- recursos didáticos.

5. Nível de dificuldade:
{dificuldade}

6. Tipo da atividade:
{tipo}

REGRAS:

SE O TIPO FOR "objetiva":
- faça questões de múltipla escolha;
- alternativas A), B), C) e D);
- NÃO coloque gabarito, NÃO coloque respostas.

SE O TIPO FOR "discursiva":
- faça perguntas abertas;
- não coloque alternativas.

SE O TIPO FOR "mista":
- misture questões objetivas e discursivas.

IMPORTANTE:

- Numere as questões de 1 até {quantidade}.
- Gere exatamente {quantidade} questões.
- Gere APENAS as questões, sem introduções, sem explicações, sem gabarito, sem respostas.
- Comece diretamente na questão 1.
"""

    try:

        resposta = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.1:8b",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 2000
                }
            },
            timeout=300
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