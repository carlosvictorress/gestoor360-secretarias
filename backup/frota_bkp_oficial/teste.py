from flask import Flask

app = Flask(__name__)

@app.route("/")
def pagina_inicial():
    return "<h1>Página Inicial de Teste FUNCIONA!</h1>"

@app.route("/admin/licenca")
def pagina_licenca():
    return "<h1>A ROTA /admin/licenca FUNCIONA!</h1>"