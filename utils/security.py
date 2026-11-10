import bcrypt
from database.conexao import get_cursor, release_cursor


def gerar_hash_senha(senha: str) -> str:
    """Gera um hash bcrypt seguro para a senha."""
    if not senha:
        return ""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(senha.encode("utf-8"), salt).decode("utf-8")


def verificar_senha(senha_candidata: str, senha_armazenada: str) -> bool:
    """
    Verifica a senha informada contra a armazenada.
    Suporta tanto hashes bcrypt ($2a$, $2b$) quanto migração suave
    de senhas legadas que ainda estavam em texto puro.
    """
    if not senha_candidata or not senha_armazenada:
        return False

    # Se for um hash bcrypt
    if senha_armazenada.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            return bcrypt.checkpw(
                senha_candidata.encode("utf-8"),
                senha_armazenada.encode("utf-8")
            )
        except Exception:
            return False

    # Fallback para senhas legadas em texto puro
    return senha_candidata == senha_armazenada


def atualizar_senha_para_hash_se_necessario(usuario_id: int, senha_plana: str, senha_armazenada: str):
    """
    Migra transparentemente uma senha em texto puro para hash bcrypt
    após um login bem-sucedido.
    """
    if not senha_armazenada.startswith(("$2a$", "$2b$", "$2y$")):
        novo_hash = gerar_hash_senha(senha_plana)
        conn, cursor = get_cursor()
        try:
            cursor.execute(
                "UPDATE usuarios SET senha = %s WHERE id = %s",
                (novo_hash, usuario_id)
            )
            conn.commit()
        except Exception as e:
            print(f"[SEGURANCA] Aviso ao migrar senha de usuario #{usuario_id}: {e}")
        finally:
            release_cursor(conn, cursor)


def redefinir_senha_usuario(usuario_id: int, nova_senha: str) -> bool:
    """Atualiza a senha de um usuário no banco com hash seguro bcrypt."""
    if not nova_senha:
        return False
    novo_hash = gerar_hash_senha(nova_senha)
    conn, cursor = get_cursor()
    try:
        cursor.execute("UPDATE usuarios SET senha = %s WHERE id = %s", (novo_hash, usuario_id))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"[SEGURANCA] Erro ao redefinir senha do usuário #{usuario_id}: {e}")
        return False
    finally:
        release_cursor(conn, cursor)


def redefinir_senha_por_email(email: str, nova_senha: str) -> bool:
    """Atualiza a senha de um usuário através do e-mail cadastrado."""
    if not email or not nova_senha:
        return False
    novo_hash = gerar_hash_senha(nova_senha)
    conn, cursor = get_cursor()
    try:
        cursor.execute("UPDATE usuarios SET senha = %s WHERE LOWER(email) = LOWER(%s)", (novo_hash, email.strip()))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"[SEGURANCA] Erro ao redefinir senha por email ({email}): {e}")
        return False
    finally:
        release_cursor(conn, cursor)
