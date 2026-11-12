"""
Módulo de Gerenciamento do Repositório de Atividades Pedagógicas.
Permite o cadastro manual pelo professor, armazenamento de questões geradas por IA,
busca contextual e combinação de atividades (Repositório + IA / Banco Externo).
"""

import re
import logging
from database.conexao import get_cursor, release_cursor

logger = logging.getLogger("gerador_atividades")


def parsear_texto_em_questoes(texto):
    """
    Analisa um texto de atividade avaliativa completo e o divide em questões individuais,
    extraindo enunciado, alternativas (se houver), resposta correta/gabarito e tipo.
    """
    if not texto:
        return []

    # Divide por blocos que comecem com "Questão X:" ou "Questao X:"
    blocos = re.split(r'(?i)\n*(?=Quest[aã]o\s+\d+\s*:)', texto.strip())
    questoes = []

    for bloco in blocos:
        bloco = bloco.strip()
        if not bloco or not re.match(r'(?i)^Quest[aã]o\s+\d+\s*:', bloco):
            continue

        # Remove o prefixo 'Questão X:'
        m = re.match(r'(?i)^Quest[aã]o\s+\d+\s*:\s*(.*)', bloco, re.DOTALL)
        corpo = m.group(1).strip() if m else bloco

        # Extrai resposta correta / gabarito se presente
        m_resp = re.search(r'(?i)(?:Resposta correta|Gabarito|Resposta)\s*:\s*([^\n\r]+)', corpo)
        resposta = m_resp.group(1).strip() if m_resp else ''

        # Extrai alternativas no formato A) ... B) ... etc.
        m_alt = re.search(r'(?i)(\n[A-E]\)[\s\S]+?)(?=(?:Resposta correta|Gabarito|Resposta)\s*:|\Z)', corpo)
        alternativas = m_alt.group(1).strip() if m_alt else ''

        # O enunciado é a parte que vem antes das alternativas ou do gabarito
        if alternativas:
            idx_alt = corpo.find(alternativas)
            enunciado = corpo[:idx_alt].strip() if idx_alt != -1 else corpo
        elif resposta:
            enunciado = re.sub(r'(?i)(?:Resposta correta|Gabarito|Resposta)\s*:\s*[^\n\r]+', '', corpo).strip()
        else:
            enunciado = corpo

        # Limpa pontuação e quebras redundantes
        enunciado = re.sub(r'^\s*[:\-\.]\s*', '', enunciado).strip()

        tipo = 'objetiva' if alternativas else 'discursiva'

        questoes.append({
            'enunciado': enunciado,
            'alternativas': alternativas,
            'resposta_correta': resposta,
            'tipo': tipo,
            'texto_completo': bloco
        })

    return questoes


def formatar_questoes_para_atividade(questoes):
    """
    Recebe uma lista de dicionários de questões e formata em texto limpo sequencial,
    numerando de 1 a N, no formato padrão do sistema para exportação e edição.
    """
    blocos = []
    for idx, q in enumerate(questoes, 1):
        enunciado = (q.get("enunciado") or "").strip()
        alternativas = (q.get("alternativas") or "").strip()
        resposta = (q.get("resposta_correta") or "").strip()

        texto_q = f"Questão {idx}: {enunciado}"
        if alternativas:
            texto_q += f"\n\n{alternativas}"
        if resposta:
            if not resposta.lower().startswith("resposta"):
                texto_q += f"\nResposta correta: {resposta}"
            else:
                texto_q += f"\n{resposta}"

        blocos.append(texto_q)

    return "\n\n".join(blocos)


def adicionar_ao_repositorio(curso, disciplina, conteudo, dificuldade, tipo,
                             enunciado, alternativas="", resposta_correta="",
                             origem="professor", usuario_id=None):
    """
    Insere uma nova questão/atividade no repositório.
    """
    conn, cursor = get_cursor()
    try:
        cursor.execute(
            """
            INSERT INTO repositorio_atividades (
                curso, disciplina, conteudo, dificuldade, tipo,
                enunciado, alternativas, resposta_correta, origem, usuario_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                curso.strip(),
                disciplina.strip(),
                conteudo.strip(),
                dificuldade.strip().lower(),
                tipo.strip().lower(),
                enunciado.strip(),
                (alternativas or "").strip(),
                (resposta_correta or "").strip(),
                origem,
                usuario_id
            )
        )
        novo_id = cursor.fetchone()[0]
        conn.commit()
        return novo_id
    finally:
        release_cursor(conn, cursor)


def atualizar_no_repositorio(item_id, curso, disciplina, conteudo, dificuldade, tipo,
                             enunciado, alternativas="", resposta_correta=""):
    """
    Atualiza uma questão/atividade existente no repositório.
    """
    conn, cursor = get_cursor()
    try:
        cursor.execute(
            """
            UPDATE repositorio_atividades
            SET curso = %s,
                disciplina = %s,
                conteudo = %s,
                dificuldade = %s,
                tipo = %s,
                enunciado = %s,
                alternativas = %s,
                resposta_correta = %s
            WHERE id = %s
            """,
            (
                curso.strip(),
                disciplina.strip(),
                conteudo.strip(),
                dificuldade.strip().lower(),
                tipo.strip().lower(),
                enunciado.strip(),
                (alternativas or "").strip(),
                (resposta_correta or "").strip(),
                item_id
            )
        )
        conn.commit()
        return True
    finally:
        release_cursor(conn, cursor)


def deletar_do_repositorio(item_id, usuario_id=None, perfil="professor"):
    """
    Remove uma questão do repositório. Professores só deletam as suas próprias; admin deleta qualquer.
    """
    conn, cursor = get_cursor()
    try:
        if perfil == "admin":
            cursor.execute("DELETE FROM repositorio_atividades WHERE id = %s", (item_id,))
        else:
            cursor.execute(
                "DELETE FROM repositorio_atividades WHERE id = %s AND usuario_id = %s",
                (item_id, usuario_id)
            )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        release_cursor(conn, cursor)


def obter_item_repositorio(item_id):
    """
    Retorna os detalhes de um item específico do repositório.
    """
    conn, cursor = get_cursor()
    try:
        cursor.execute(
            """
            SELECT r.id, r.curso, r.disciplina, r.conteudo, r.dificuldade,
                   r.tipo, r.enunciado, r.alternativas, r.resposta_correta,
                   r.origem, r.usuario_id, r.data_criacao, u.nome as autor_nome
            FROM repositorio_atividades r
            LEFT JOIN usuarios u ON u.id = r.usuario_id
            WHERE r.id = %s
            """,
            (item_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "curso": row[1],
            "disciplina": row[2],
            "conteudo": row[3],
            "dificuldade": row[4],
            "tipo": row[5],
            "enunciado": row[6],
            "alternativas": row[7],
            "resposta_correta": row[8],
            "origem": row[9],
            "usuario_id": row[10],
            "data_criacao": row[11],
            "autor_nome": row[12] or "Sistema IA"
        }
    finally:
        release_cursor(conn, cursor)


def salvar_questoes_ia_no_repositorio(texto_atividade, curso, disciplina, conteudo,
                                      dificuldade, tipo, usuario_id=None):
    """
    Divide o texto gerado pela IA em questões e cadastra cada uma no repositório com origem='ia'.
    """
    questoes = parsear_texto_em_questoes(texto_atividade)
    if not questoes:
        return 0

    inseridas = 0
    conn, cursor = get_cursor()
    try:
        for q in questoes:
            cursor.execute(
                """
                INSERT INTO repositorio_atividades (
                    curso, disciplina, conteudo, dificuldade, tipo,
                    enunciado, alternativas, resposta_correta, origem, usuario_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'ia', %s)
                """,
                (
                    curso.strip(),
                    disciplina.strip(),
                    conteudo.strip(),
                    dificuldade.strip().lower(),
                    q["tipo"],
                    q["enunciado"],
                    q["alternativas"],
                    q["resposta_correta"],
                    usuario_id
                )
            )
            inseridas += 1
        conn.commit()
    except Exception as e:
        print(f"[REPOSITORIO] Erro ao salvar questões da IA no repositório: {e}")
    finally:
        release_cursor(conn, cursor)

    return inseridas


def buscar_questoes_repositorio(curso=None, disciplina=None, conteudo=None,
                                dificuldade=None, tipo=None, usuario_id=None,
                                limite=20, apenas_professor=False):
    """
    Busca questões no repositório usando critérios contextuais.
    Prioriza questões do próprio professor, seguidas de questões do repositório em geral.
    """
    condicoes = []
    params = []

    if apenas_professor:
        condicoes.append("origem = 'professor'")

    # Filtro de tipo: se for mista, aceita qualquer; se especificado, filtra
    if tipo and tipo != "mista":
        condicoes.append("tipo = %s")
        params.append(tipo.strip().lower())

    # Monta cláusula de busca textual inteligente
    text_clauses = []
    if disciplina and disciplina.strip():
        text_clauses.append("disciplina ILIKE %s")
        params.append(f"%{disciplina.strip()}%")

    if curso and curso.strip():
        text_clauses.append("curso ILIKE %s")
        params.append(f"%{curso.strip()}%")

    if conteudo and conteudo.strip():
        palavras = [p for p in re.split(r'[\s,;.-]+', conteudo.strip()) if len(p) >= 4]
        for p in palavras[:3]:
            text_clauses.append("(conteudo ILIKE %s OR enunciado ILIKE %s)")
            params.extend([f"%{p}%", f"%{p}%"])

    if text_clauses:
        condicoes.append("(" + " OR ".join(text_clauses) + ")")

    where_sql = ("WHERE " + " AND ".join(condicoes)) if condicoes else ""

    # Ordenação com pontuação:
    order_clauses = []
    order_params = []
    if usuario_id:
        order_clauses.append("CASE WHEN usuario_id = %s THEN 0 ELSE 1 END")
        order_params.append(int(usuario_id))
    order_clauses.append("CASE WHEN origem = 'professor' THEN 0 ELSE 1 END")
    if dificuldade:
        order_clauses.append("CASE WHEN dificuldade ILIKE %s THEN 0 ELSE 1 END")
        order_params.append(f"%{dificuldade}%")
    order_clauses.append("id DESC")

    order_sql = "ORDER BY " + ", ".join(order_clauses)

    query = f"""
        SELECT id, curso, disciplina, conteudo, dificuldade, tipo,
               enunciado, alternativas, resposta_correta, origem, usuario_id, data_criacao
        FROM repositorio_atividades
        {where_sql}
        {order_sql}
        LIMIT %s
    """
    all_params = params + order_params + [limite]

    conn, cursor = get_cursor()
    try:
        cursor.execute(query, tuple(all_params))
        rows = cursor.fetchall()

        # Se a busca refinada não encontrou o suficiente e temos termos de curso/disciplina,
        # busca questões adicionais da mesma disciplina ou curso
        if len(rows) < limite and (disciplina or curso):
            ids_existentes = [r[0] for r in rows]
            fallback_params = []
            fallback_conds = []
            if ids_existentes:
                fallback_conds.append(f"id NOT IN ({','.join(str(i) for i in ids_existentes)})")
            if apenas_professor:
                fallback_conds.append("origem = 'professor'")
            if tipo and tipo != "mista":
                fallback_conds.append("tipo = %s")
                fallback_params.append(tipo.strip().lower())

            fallback_or = []
            if disciplina and disciplina.strip():
                fallback_or.append("disciplina ILIKE %s")
                fallback_params.append(f"%{disciplina.strip()}%")
            if curso and curso.strip():
                fallback_or.append("curso ILIKE %s")
                fallback_params.append(f"%{curso.strip()}%")

            if fallback_or:
                fallback_conds.append("(" + " OR ".join(fallback_or) + ")")
                fb_where = "WHERE " + " AND ".join(fallback_conds)
                fb_query = f"""
                    SELECT id, curso, disciplina, conteudo, dificuldade, tipo,
                           enunciado, alternativas, resposta_correta, origem, usuario_id, data_criacao
                    FROM repositorio_atividades
                    {fb_where}
                    ORDER BY id DESC
                    LIMIT %s
                """
                fallback_params.append(limite - len(rows))
                cursor.execute(fb_query, tuple(fallback_params))
                rows.extend(cursor.fetchall())

        resultados = []
        for r in rows:
            resultados.append({
                "id": r[0],
                "curso": r[1],
                "disciplina": r[2],
                "conteudo": r[3],
                "dificuldade": r[4],
                "tipo": r[5],
                "enunciado": r[6],
                "alternativas": r[7],
                "resposta_correta": r[8],
                "origem": r[9],
                "usuario_id": r[10],
                "data_criacao": r[11]
            })
        return resultados
    finally:
        release_cursor(conn, cursor)


def contar_questoes_repositorio(curso=None, disciplina=None, conteudo=None,
                                dificuldade=None, tipo=None, usuario_id=None,
                                apenas_professor=False):
    """
    Retorna a quantidade exata de questões disponíveis no repositório para os critérios dados.
    """
    itens = buscar_questoes_repositorio(
        curso=curso,
        disciplina=disciplina,
        conteudo=conteudo,
        dificuldade=dificuldade,
        tipo=tipo,
        usuario_id=usuario_id,
        limite=100,
        apenas_professor=apenas_professor
    )
    return len(itens)


def compor_atividade_hibrida(questoes_repositorio, texto_ia, quantidade_total):
    """
    Combina uma lista de questões vindas do repositório com o texto gerado pela IA,
    renumerando todas sequencialmente de Questão 1 até Questão N.
    """
    todas = list(questoes_repositorio)

    if texto_ia:
        novas_ia = parsear_texto_em_questoes(texto_ia)
        if novas_ia:
            for n in novas_ia:
                if len(todas) < quantidade_total:
                    todas.append(n)
        else:
            return formatar_questoes_para_atividade(todas) + "\n\n" + texto_ia

    return formatar_questoes_para_atividade(todas[:quantidade_total])


def migrar_atividades_existentes_para_repositorio():
    """
    Garante que as atividades já geradas anteriormente no sistema sejam catalogadas
    no repositório como origem='ia', para que o banco já nasça populado.
    """
    conn, cursor = get_cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM repositorio_atividades")
        count = cursor.fetchone()[0]
        if count > 0:
            return

        cursor.execute("SELECT id, curso, disciplina, conteudo, dificuldade, atividade_gerada, usuario_id FROM atividades")
        atividades = cursor.fetchall()
        migradas = 0

        for ativ in atividades:
            cid, curso, disciplina, conteudo, dificuldade, texto, uid = ativ
            if not texto:
                continue
            qs = parsear_texto_em_questoes(texto)
            for q in qs:
                cursor.execute(
                    """
                    INSERT INTO repositorio_atividades (
                        curso, disciplina, conteudo, dificuldade, tipo,
                        enunciado, alternativas, resposta_correta, origem, usuario_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'ia', %s)
                    """,
                    (
                        curso,
                        disciplina,
                        conteudo,
                        dificuldade,
                        q["tipo"],
                        q["enunciado"],
                        q["alternativas"],
                        q["resposta_correta"],
                        uid
                    )
                )
                migradas += 1

        conn.commit()
        print(f"[REPOSITORIO] Migração concluída: {migradas} questões catalogadas no repositório.")
    except Exception as e:
        print(f"[REPOSITORIO] Aviso na migração inicial: {e}")
    finally:
        release_cursor(conn, cursor)


try:
    migrar_atividades_existentes_para_repositorio()
except Exception:
    pass
