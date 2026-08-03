from flask import Flask, jsonify, request, render_template, redirect, url_for
import dados
import json

biblioteca = dados.carregar_do_arquivo()
app = Flask(__name__)

class Livro:
    def __init__(self, isbn, titulo, autor, status):
        self.isbn = isbn
        self.titulo = titulo
        self.autor = autor
        self.status = status

def encontrar_livro(isbn):
    biblioteca = dados.carregar_do_arquivo()
    for livro in biblioteca:
        if livro['isbn'] == isbn:
            print(livro)
            return livro
    return None

# Adicionado 'GET' à segunda rota
@app.route('/api/biblioteca', methods=['GET', 'POST'])
@app.route('/api/biblioteca/<isbn>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def manipular_livro(isbn=None):
    if request.method == 'GET':
        if isbn is None:  # Boa prática usar 'is None' em vez de '== None'
            return jsonify(biblioteca)
        else:
            for livro in biblioteca:
                if livro['isbn'] == isbn:
                    return jsonify(livro)
        return jsonify("Livro não encontrado"), 404
        
    elif request.method == 'POST':
        novo_livro = request.get_json()
        biblioteca.append(novo_livro)
        dados.salvar_no_arquivo(biblioteca)
        return jsonify("Livro criado com sucesso"), 201
        
    elif request.method == 'DELETE':
        for livro in biblioteca:
            if livro['isbn'] == isbn:
                biblioteca.remove(livro)
                dados.salvar_no_arquivo(biblioteca)
                return jsonify("Livro deletado com sucesso"), 200
        return jsonify("Livro não encontrado"), 404
                
    elif request.method == 'PUT':
        novo_livro = request.get_json()
        for livro in biblioteca:
            if livro['isbn'] == isbn:
                for key, value in novo_livro.items():
                    livro[key] = value
                dados.salvar_no_arquivo(biblioteca)
                return jsonify("Livro Alterado com Sucesso"), 200
        return jsonify("Livro não encontrado"), 404

@app.route('/')
def home():
    biblioteca = dados.carregar_do_arquivo()
    return render_template('list.html',biblioteca=biblioteca)


@app.route('/biblioteca/criar', methods=['GET', 'POST'])
def interface_criar():
    biblioteca = dados.carregar_do_arquivo()
    if request.method == 'POST':
        novo_livro = {
            "isbn": request.form.get('isbn'),
            "titulo": request.form.get('titulo'),
            "autor": request.form.get('autor'),
            "genero": request.form.get('genero'),
            "ano_publicacao": request.form.get('ano_publicacao'),
            "editora": request.form.get('editora'),
            "paginas": request.form.get('paginas'),
            "status": request.form.get('status'),
            "localizacao": request.form.get('localizacao')
        }
        biblioteca.append(novo_livro)
        dados.salvar_no_arquivo(biblioteca)
        return redirect(url_for('home'))
    else:
        return render_template('form_new.html')

@app.route('/biblioteca/atualizar', methods=['GET', 'POST'])
def atualiza_livro():
    biblioteca = dados.carregar_do_arquivo()
    livro = encontrar_livro(request.args.get('isbn'))
    if request.method == 'POST':
        atualizado = {
            'isbn': request.args.get('isbn'),
            'titulo': request.form.get('titulo'),
            'autor': request.form.get('autor'),
            "genero": request.form.get('genero'),
            "ano_publicacao": request.form.get('ano_publicacao'),
            "editora": request.form.get('editora'),
            "paginas": request.form.get('paginas'),
            "status": request.form.get('status'),
            "localizacao": request.form.get('localizacao')
        }
        if livro:
            biblioteca.remove(livro)
            biblioteca.append(atualizado)
            dados.salvar_no_arquivo(biblioteca)
        return render_template('list.html',biblioteca=biblioteca)
    else:
        if livro:
            return render_template('form_edit.html', livro=livro)


if __name__ == '__main__':
    app.run(debug=True)