import sqlite3

def dml_ddl(query, args):
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    try:
        cursor.execute(query, args)
    except:
        conn.rollback()
    conn.commit()
    conn.close()

def dql(query, args):
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute(query, args)
    #DQL - SELECT - retorna dado do banco
    resultado = cursor.fetchall()
    conn.close()
    #fetchall - lista com todos os resultados encontrados
    #fetchone - tupla com o primeiro resultado encontrado


query_dml = """CREATE TABLE IF NOT EXISTS qualquer (
    id INTEGER,
    nome TEXT,
    nota REAL,
    observacao BLOB
);"""
# INTEGER - Inteiro
# TEXT - string
# REAL - float/decimal
# BLOB - Texto longo
args_dml = []

dml_ddl(query_dml, args_dml)
query_ddl = """INSERT INTO qualquer VALUES (?, ?, ?, ?);"""
args_ddl01 = [1, "Davi", 7.5, "Aluno de python"]
args_ddl02 = [2, "Moraes", 8, "Sobrenome do aluno de python"]
dml_ddl(query_ddl, args_ddl01)
query_dql = "SELECT * FROM qualquer WHERE id = ?;"
dql(query_dql, [1])