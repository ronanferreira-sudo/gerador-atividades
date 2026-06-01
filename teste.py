import psycopg2

print("INICIO")

try:

    conexao = psycopg2.connect(
        host="127.0.0.1",
        port="5432",
        dbname="postgres",
        user="postgres",
        password="123"
    )

    print("Conectado!")

except Exception as erro:

    print("TIPO ERRO:")
    print(type(erro))

    print("ERRO:")
    print(erro)

print("FIM")