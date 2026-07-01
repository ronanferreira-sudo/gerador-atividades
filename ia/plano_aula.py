import requests
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Cache thread-safe — isolado por thread
cache_planos = threading.local()


def gerar_hash_plano(texto_base, carga_horaria, aulas_por_dia, dia):
    base = f"{texto_base[:3000]}-{carga_horaria}-{aulas_por_dia}-{dia}"
    return hashlib.md5(base.encode()).hexdigest()


def preprocessar_texto(texto):
    texto = texto.replace("\n", " ")
    texto = " ".join(texto.split())
    return texto[:3000]


def gerar_plano_aula(texto_base, carga_horaria, aulas_por_dia, dia):

    key = gerar_hash_plano(texto_base, carga_horaria, aulas_por_dia, dia)

    # Cache thread-safe
    if not hasattr(cache_planos, 'dados'):
        cache_planos.dados = {}

    if key in cache_planos.dados:
        print(f"CACHE PLANO DIA {dia} HIT")
        return (dia, cache_planos.dados[key])

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
                        "num_predict": 2000,
                        "temperature": 0.1
                    }
                },
                timeout=300
            )

            if resposta.status_code != 200:
                tentativas += 1
                print(f"Erro Ollama DIA {dia} (tentativa {tentativas}/{max_tentativas}): {resposta.status_code}")
                continue

            data = resposta.json()
            plano = data.get("response", "")

            if len(plano) < 50:
                tentativas += 1
                print(f"Resposta muito curta DIA {dia} (tentativa {tentativas}/{max_tentativas}): {len(plano)} chars")
                continue

            cache_planos.dados[key] = plano
            print(f"DIA {dia} OK ({len(plano)} chars)")

            return (dia, plano)

        except Exception as e:
            tentativas += 1
            print(f"Erro na IA DIA {dia} (tentativa {tentativas}/{max_tentativas}):", e)
            if tentativas >= max_tentativas:
                return (dia, "Erro ao conectar com a IA")
            import time
            time.sleep(5)
    
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
