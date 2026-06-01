import psycopg2

conexao = psycopg2.connect(
    host="127.0.0.1",
    port="5432",
    dbname="gerador_atividades",
    user="postgres",
    password="123"
)

cursor = conexao.cursor()