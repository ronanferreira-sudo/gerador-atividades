"""
Script de testes automatizados para o Repositório de Atividades e Fluxo de Geração.
"""

import unittest
from app import app
from database.conexao import get_cursor, release_cursor
import utils.repositorio_service as rep_svc


class TestRepositorioAtividades(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()

        # Obter um usuário de teste existente no banco
        conn, cur = get_cursor()
        try:
            cur.execute("SELECT id, nome, perfil FROM usuarios LIMIT 1")
            user = cur.fetchone()
            if not user:
                # Criar usuário temporário para teste
                cur.execute(
                    "INSERT INTO usuarios (nome, email, senha, perfil) VALUES ('Professor Teste', 'prof_teste@senai.br', '123', 'professor') RETURNING id, nome, perfil"
                )
                user = cur.fetchone()
                conn.commit()
            self.user_id = user[0]
            self.user_nome = user[1]
            self.user_perfil = user[2]
        finally:
            release_cursor(conn, cur)

    def tearDown(self):
        self.app_context.pop()

    def test_01_adicionar_obter_atualizar_excluir_repositorio(self):
        """Testa o ciclo de vida CRUD de uma questão autoral no repositório."""
        novo_id = rep_svc.adicionar_ao_repositorio(
            curso="Técnico em Eletroeletrônica",
            disciplina="Circuitos Elétricos",
            conteudo="Lei de Ohm e Resistência Elétrica",
            dificuldade="médio",
            tipo="objetiva",
            enunciado="Qual a unidade de medida da resistência elétrica no SI?",
            alternativas="A) Volt\nB) Ampère\nC) Ohm\nD) Watt",
            resposta_correta="C) Ohm",
            origem="professor",
            usuario_id=self.user_id
        )
        self.assertIsNotNone(novo_id)

        # Obter
        item = rep_svc.obter_item_repositorio(novo_id)
        self.assertEqual(item["origem"], "professor")
        self.assertEqual(item["disciplina"], "Circuitos Elétricos")
        self.assertEqual(item["tipo"], "objetiva")

        # Atualizar
        rep_svc.atualizar_no_repositorio(
            item_id=novo_id,
            curso="Técnico em Eletroeletrônica",
            disciplina="Circuitos Elétricos Avançados",
            conteudo="Lei de Ohm",
            dificuldade="fácil",
            tipo="objetiva",
            enunciado="Qual a unidade no SI da resistência?",
            alternativas="A) Volt\nB) Ampère\nC) Ohm\nD) Joule",
            resposta_correta="C"
        )
        item_mod = rep_svc.obter_item_repositorio(novo_id)
        self.assertEqual(item_mod["disciplina"], "Circuitos Elétricos Avançados")
        self.assertEqual(item_mod["dificuldade"], "fácil")

        # Deletar
        sucesso_del = rep_svc.deletar_do_repositorio(novo_id, self.user_id, self.user_perfil)
        self.assertTrue(sucesso_del)

        item_pos = rep_svc.obter_item_repositorio(novo_id)
        self.assertIsNone(item_pos)

    def test_02_parsear_e_formatar_questoes(self):
        """Testa o desmembramento de atividade em questões e a formatação sequencial."""
        texto_exemplo = """Questão 1: O que é Python?
A) Uma serpente
B) Uma linguagem de programação
C) Um sistema operacional
D) Um protocolo de rede
Resposta correta: B

Questão 2: Explique a função do comando print().
"""
        questoes = rep_svc.parsear_texto_em_questoes(texto_exemplo)
        self.assertEqual(len(questoes), 2)
        self.assertEqual(questoes[0]["tipo"], "objetiva")
        self.assertEqual(questoes[0]["resposta_correta"], "B")
        self.assertEqual(questoes[1]["tipo"], "discursiva")

        # Formatação de volta
        formatado = rep_svc.formatar_questoes_para_atividade(questoes)
        self.assertIn("Questão 1: O que é Python?", formatado)
        self.assertIn("Questão 2: Explique a função do comando print().", formatado)
        self.assertIn("Resposta correta: B", formatado)

    def test_03_composicao_hibrida(self):
        """Testa a combinação de questões do repositório com novas questões geradas pela IA."""
        questoes_repo = [
            {
                "enunciado": "Questão do repositório 1",
                "alternativas": "A) 1\nB) 2\nC) 3\nD) 4",
                "resposta_correta": "A",
                "tipo": "objetiva"
            }
        ]
        texto_ia = """Questão 1: Questão gerada pela IA
A) X\nB) Y\nC) Z\nD) W
Resposta correta: C
"""
        hibrido = rep_svc.compor_atividade_hibrida(questoes_repo, texto_ia, quantidade_total=2)
        self.assertIn("Questão 1: Questão do repositório 1", hibrido)
        self.assertIn("Questão 2: Questão gerada pela IA", hibrido)

    def test_04_api_verificar_repositorio(self):
        """Testa a API JSON de pré-verificação de quantidade do repositório."""
        with self.client.session_transaction() as sess:
            sess["usuario_id"] = self.user_id
            sess["nome"] = self.user_nome
            sess["perfil"] = self.user_perfil

        # Testa verificação com quantidade alta inexistente
        resp = self.client.post("/api/repositorio/verificar", json={
            "curso": "Curso Inexistente ZzZkXw88",
            "disciplina": "Disciplina Inexistente ZzZkXw88",
            "conteudo": "ZzZkXw88",
            "dificuldade": "difícil",
            "tipo": "objetiva",
            "quantidade": 10,
            "fonte": "repositorio"
        })
        self.assertEqual(resp.status_code, 200)
        dados = resp.get_json()
        self.assertFalse(dados["suficiente"])
        self.assertEqual(dados["disponiveis"], 0)
        self.assertEqual(dados["faltantes"], 10)

    def test_05_fluxo_confirmacao_quantidade_insuficiente(self):
        """Testa o fluxo quando o repositório não tem o suficiente: Sim completa com IA, Não volta."""
        with self.client.session_transaction() as sess:
            sess["usuario_id"] = self.user_id
            sess["nome"] = self.user_nome
            sess["perfil"] = self.user_perfil

        # 1. Requisição inicial com fonte='repositorio' sem confirmação prévia
        # Deve renderizar com aviso de confirmação
        resp = self.client.post("/", data={
            "curso": "Curso Fantasia ZzZkXw88",
            "disciplina": "Disciplina Fantasia ZzZkXw88",
            "conteudo": "ZzZkXw88",
            "dificuldade": "médio",
            "tipo": "objetiva",
            "quantidade": "4",
            "fonte": "repositorio",
            "completar_com_ia": ""
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Quantidade Insuficiente no Repositório", resp.get_data(as_text=True))
        self.assertIn("Sim, completar com banco externo", resp.get_data(as_text=True))
        self.assertIn("Não, voltar para solicitação", resp.get_data(as_text=True))

        # 2. Usuário escolhe 'nao' (volta para solicitação mantendo dados)
        resp_nao = self.client.post("/", data={
            "curso": "Curso Fantasia ZzZkXw88",
            "disciplina": "Disciplina Fantasia ZzZkXw88",
            "conteudo": "ZzZkXw88",
            "dificuldade": "médio",
            "tipo": "objetiva",
            "quantidade": "4",
            "fonte": "repositorio",
            "completar_com_ia": "nao"
        })
        self.assertEqual(resp_nao.status_code, 200)
        # Deve renderizar a tela de solicitação com os campos preservados
        self.assertIn("Curso Fantasia ZzZkXw88", resp_nao.get_data(as_text=True))
        self.assertIn("Disciplina Fantasia ZzZkXw88", resp_nao.get_data(as_text=True))

        # 3. Usuário escolhe 'sim' (completa com IA e salva)
        resp_sim = self.client.post("/", data={
            "curso": "Curso Fantasia",
            "disciplina": "Disciplina Fantasia",
            "conteudo": "Conceitos básicos de teste de software",
            "dificuldade": "fácil",
            "tipo": "objetiva",
            "quantidade": "2",
            "fonte": "repositorio",
            "completar_com_ia": "sim"
        })
        # Deve redirecionar para /atividades após gerar com sucesso
        self.assertEqual(resp_sim.status_code, 302)
        self.assertIn("/atividades", resp_sim.headers["Location"])


if __name__ == "__main__":
    unittest.main()
