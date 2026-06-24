import requests
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed

cache_planos = {}


def gerar_hash_plano(texto_base, carga_horaria, aulas_por_dia, dia):
    base = f"{texto_base[:600]}-{carga_horaria}-{aulas_por_dia}-{dia}"
    return hashlib.md5(base.encode()).hexdigest()


def preprocessar_texto(texto):
    texto = texto.replace("\n", " ")
    texto = " ".join(texto.split())
    return texto[:600]


def gerar_plano_aula(texto_base, carga_horaria, aulas_por_dia, dia):

    key = gerar_hash_plano(texto_base, carga_horaria, aulas_por_dia, dia)

    if key in cache_planos:
        print(f"CACHE PLANO DIA {dia} HIT")
        return (dia, cache_planos[key])

    print(f"Chamando Ollama - DIA {dia}...")

    prompt = f"""
Crie o plano de aula do DIA {dia}.

Conteúdo base (Matriz de Referência):
{preprocessar_texto(texto_base)}

Com base nos itens da Matriz de Referência acima, distribua os conteúdos ao longo dos dias do curso.
Para o DIA {dia}, selecione os itens mais adequados e crie o plano de aula.

Gere APENAS o plano de aula em texto puro:

1. Identificação:
2. Objetivos:
3. Conteúdo Programático:
4. Estratégia Didática:
5. Recursos Didáticos:
6. Avaliação:

Comece diretamente com "1. Identificação:".
"""

    try:
        resposta = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.1:8b",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": 400,
                    "temperature": 0.1
                }
            },
            timeout=60
        )

        if resposta.status_code != 200:
            return (dia, "Erro ao gerar plano")

        data = resposta.json()
        plano = data.get("response", "")

        cache_planos[key] = plano
        print(f"DIA {dia} OK ({len(plano)} chars)")

        return (dia, plano)

    except Exception as e:
        print(f"Erro na IA DIA {dia}:", e)
        return (dia, "Erro ao conectar com a IA")


def gerar_todos_planos(texto_pdf, carga_horaria, aulas_por_dia, total_dias, max_workers=4):

    print(f"📅 Total de dias a gerar: {total_dias}")
    print(f"⚡ Workers paralelos: {max_workers}")
    print("-" * 40)

    resultados = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                gerar_plano_aula, texto_pdf, carga_horaria, aulas_por_dia, dia
            ): dia for dia in range(1, total_dias + 1)
        }
        concluidos = 0
        for future in as_completed(futures):
            dia, plano = future.result()
            resultados[dia] = plano
            concluidos += 1
            print(f"📊 Progresso: {concluidos}/{total_dias} dias concluídos")

    print("-" * 40)
    print(f"✅ Geração de planos finalizada! {total_dias} dias gerados.")
    print("=" * 60)

    return [resultados[dia] for dia in sorted(resultados.keys())]
