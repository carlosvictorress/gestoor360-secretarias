# ===================================================================
# PARTE 1: Importações de Bibliotecas
# ===================================================================
import os
import io
import csv
import uuid
import locale
import qrcode
import base64
import re
import math
from functools import wraps
from datetime import datetime, timedelta

from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    session, make_response, send_from_directory, Response, abort, jsonify
)
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from sqlalchemy import func, or_, and_
from werkzeug.utils import secure_filename
from num2words import num2words

# Importações para o gerador de PDF (ReportLab)
from reportlab.lib.pagesizes import letter, landscape, A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image,
    BaseDocTemplate, Frame, PageTemplate, KeepTogether, ListFlowable, HRFlowable
)
from reportlab.pdfgen import canvas as canvas_lib
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.units import cm, inch

# Configura o locale para o português do Brasil
try:
    locale.setlocale(locale.LC_TIME, "pt_BR.UTF-8")
except locale.Error:
    print("Locale pt_BR.UTF-8 não encontrado, usando o padrão do sistema.")

# ===================================================================
# PARTE 2: Configuração da Aplicação e Inicialização das Extensões
# ===================================================================

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))

# --- Configurações da Aplicação ---
database_url = os.environ.get("DATABASE_URL")
if database_url:
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url or "sqlite:///" + os.path.join(basedir, "servidores.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "uma-chave-secreta-muito-dificil-de-adivinhar"
app.config["UPLOAD_FOLDER"] = "uploads"
RAIO_PERMITIDO_METROS = 100

# --- Inicialização das Extensões ---
db = SQLAlchemy(app)
migrate = Migrate(app, db)
bcrypt = Bcrypt(app)


# ===================================================================
# PARTE 3: Importação dos Modelos
# ===================================================================
from .models import *


# ===================================================================
# PARTE 4: Comandos CLI, Funções Globais e Decoradores
# ===================================================================

def check_license(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Defina aqui as rotas que podem ser acessadas mesmo com a licença expirada
        allowed_routes = [
            "login", "logout", "renovar_licenca", "admin_licenca", 
            "static", "uploaded_file"
        ]
        
        if request.endpoint in allowed_routes:
            return f(*args, **kwargs)

        # Busca a licença no banco de dados
        licenca = License.query.first()

        # Se a licença não existe ou está expirada
        if not licenca or licenca.expiration_date < datetime.utcnow():
            # Permite que o admin acesse para poder renovar
            if session.get("role") == "admin":
                return f(*args, **kwargs)
            
            # Para outros usuários, exibe a mensagem e redireciona
            flash(
                "Sua licença de uso do sistema expirou. Por favor, renove sua assinatura para continuar.",
                "warning",
            )
            return redirect(url_for("renovar_licenca"))
            
        # Se a licença estiver válida, permite o acesso
        return f(*args, **kwargs)

    return decorated_function

@app.cli.command("init-db")
def init_db_command():
    db.create_all()
    os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "documentos"), exist_ok=True)
    print("Banco de dados e pastas de uploads inicializados.")


@app.cli.command("create-admin")
def create_admin_command():
    with app.app_context():
        username = input("Digite o nome de usuário para o admin: ")
        password = input("Digite a senha para o admin: ")
        user = User.query.filter_by(username=username).first()
        if user:
            print(f"Usuário '{username}' já existe.")
            return
        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
        new_user = User(username=username, password_hash=hashed_password, role="admin")
        db.session.add(new_user)
        db.session.commit()
        print(f"Usuário administrador '{username}' criado com sucesso!")


@app.context_processor
def inject_year():
    return {"current_year": datetime.utcnow().year}


def registrar_log(action):
    try:
        if "logged_in" in session:
            username = session.get("username", "Anônimo")
            ip_address = request.remote_addr
            log_entry = Log(username=username, action=action, ip_address=ip_address)
            db.session.add(log_entry)
            db.session.commit()
    except Exception as e:
        print(f"Erro ao registrar log: {e}")
        db.session.rollback()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "logged_in" not in session:
            flash("Por favor, faça login para acessar esta página.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Você não tem permissão para acessar esta página.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated_function

def fleet_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("role") not in ["admin", "fleet"]:
            flash("Você não tem permissão para acessar este módulo.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated_function
    
def cabecalho_e_rodape(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.drawString(
        2 * cm, 1.5 * cm, f"Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    )
    canvas.drawRightString(doc.width + doc.leftMargin, 1.5 * cm, f"Página {doc.page}")

    if doc.page == 1:
        image_path = os.path.join(basedir, "static", "timbre.jpg")
        if os.path.exists(image_path):
            canvas.drawImage(
                image_path,
                2 * cm,
                A4[1] - 2.5 * cm, # A4[1] é a altura da página
                width=17 * cm,
                height=2.2 * cm,
                preserveAspectRatio=True,
                mask="auto",
            )

    canvas.restoreState()    


# ===================================================================
# PARTE 5: Definição das Rotas da Aplicação
# ===================================================================


@app.route("/usuarios")
@login_required
@admin_required
def lista_usuarios():
    usuarios = User.query.order_by(User.username).all()
    # Busca a nova lista de secretarias
    secretarias = Secretaria.query.order_by(Secretaria.nome).all()
    # Envia as duas listas para o template
    return render_template("usuarios.html", usuarios=usuarios, secretarias=secretarias)
    
@app.route("/secretarias/add", methods=["POST"])
@login_required
@admin_required
def add_secretaria():
    nome_secretaria = request.form.get("nome")
    if not nome_secretaria:
        flash("O nome da secretaria é obrigatório.", "warning")
        return redirect(url_for("lista_usuarios"))
    
    # Verifica se a secretaria já existe
    existente = Secretaria.query.filter_by(nome=nome_secretaria).first()
    if existente:
        flash("Essa secretaria já está cadastrada.", "danger")
        return redirect(url_for("lista_usuarios"))

    nova_secretaria = Secretaria(nome=nome_secretaria)
    db.session.add(nova_secretaria)
    db.session.commit()
    registrar_log(f'Cadastrou a secretaria: "{nome_secretaria}".')
    flash("Secretaria cadastrada com sucesso!", "success")
    return redirect(url_for("lista_usuarios"))


@app.route("/secretarias/delete/<int:id>")
@login_required
@admin_required
def delete_secretaria(id):
    secretaria_para_excluir = Secretaria.query.get_or_404(id)
    try:
        nome_sec = secretaria_para_excluir.nome
        db.session.delete(secretaria_para_excluir)
        db.session.commit()
        registrar_log(f'Excluiu a secretaria: "{nome_sec}".')
        flash(f'Secretaria "{nome_sec}" excluída com sucesso.', "success")
    except Exception as e:
        db.session.rollback()
        # Este erro pode acontecer se um usuário estiver vinculado a esta secretaria no futuro
        flash(f"Não foi possível excluir a secretaria. Verifique se não há vínculos. Erro: {e}", "danger")

    return redirect(url_for("lista_usuarios"))    


@app.route("/usuarios/add", methods=["POST"])
@login_required
@admin_required
def add_usuario():
    username = request.form.get("username")
    password = request.form.get("password")
    role = request.form.get("role", "operador")
    if not username or not password:
        flash("Nome de usuário e senha são obrigatórios.", "warning")
        return redirect(url_for("lista_usuarios"))
    user_exists = User.query.filter_by(username=username).first()
    if user_exists:
        flash("Este nome de usuário já existe.", "danger")
        return redirect(url_for("lista_usuarios"))
    hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
    new_user = User(username=username, password_hash=hashed_password, role=role)
    db.session.add(new_user)
    db.session.commit()
    registrar_log(f'Criou o usuário: "{username}" com o papel "{role}".')
    flash(f'Usuário "{username}" criado com sucesso!', "success")
    return redirect(url_for("lista_usuarios"))


@app.route("/usuarios/editar/<int:id>", methods=["GET", "POST"])
@login_required
@admin_required
def editar_usuario(id):
    user = User.query.get_or_404(id)
    if request.method == "POST":
        if (user.role == "admin" and User.query.filter_by(role="admin").count() == 1 and request.form.get("role") == "operador"):
            flash("Não é possível remover o status de administrador do último admin do sistema.", "danger")
            return redirect(url_for("editar_usuario", id=id))
        new_username = request.form.get("username")
        user_exists = User.query.filter(User.username == new_username, User.id != id).first()
        if user_exists:
            flash("Este nome de usuário já está em uso.", "danger")
            return render_template("editar_usuario.html", user=user)
        user.username = new_username
        user.role = request.form.get("role")
        new_password = request.form.get("password")
        if new_password:
            user.password_hash = bcrypt.generate_password_hash(new_password).decode("utf-8")
        db.session.commit()
        registrar_log(f'Editou o usuário: "{user.username}".')
        flash("Usuário atualizado com sucesso!", "success")
        return redirect(url_for("lista_usuarios"))
    return render_template("editar_usuario.html", user=user)
    
@app.route("/logs")
@login_required
@admin_required
def ver_logs():
    page = request.args.get("page", 1, type=int)
    logs_pagination = Log.query.order_by(Log.timestamp.desc()).paginate(
        page=page, per_page=25, error_out=False
    )
    return render_template("logs.html", logs=logs_pagination)    
    
    
@app.route("/admin/licenca", methods=["GET", "POST"])
@login_required
@admin_required
def admin_licenca():
    licenca = License.query.first_or_404()
    if request.method == "POST":
        nova_chave = str(uuid.uuid4())
        licenca.renewal_key = nova_chave
        db.session.commit()
        registrar_log("Gerou uma nova chave de renovação.")
        flash("Nova chave de renovação gerada com sucesso!", "success")
        return redirect(url_for("admin_licenca"))
    return render_template("admin_licenca.html", licenca=licenca)


@app.route("/renovar", methods=["GET", "POST"])
@login_required
def renovar_licenca():
    licenca = License.query.first_or_404()
    if request.method == "POST":
        chave_inserida = request.form.get("renewal_key")
        if licenca.renewal_key and licenca.renewal_key == chave_inserida:
            licenca.expiration_date = datetime.utcnow() + timedelta(days=31)
            licenca.renewal_key = None
            db.session.commit()
            registrar_log("Renovou a licença do sistema com sucesso.")
            flash("Licença renovada com sucesso! Obrigado.", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Chave de renovação inválida ou já utilizada.", "danger")
    
    if licenca.expiration_date >= datetime.utcnow() and session.get("role") != "admin":
        return redirect(url_for("dashboard"))
        
    return render_template("renovar_licenca.html")    
    
    
@app.route("/relatorio/servidores/pdf")
@login_required
def gerar_relatorio_pdf():
    servidores = Servidor.query.order_by(Servidor.nome).all()
    
    buffer = io.BytesIO()
    doc = BaseDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=3 * cm,
        bottomMargin=2.5 * cm,
    )

    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    template = PageTemplate(id="main_template", frames=[frame], onPage=cabecalho_e_rodape)
    doc.addPageTemplates([template])
    
    styles = getSampleStyleSheet()
    p_style = ParagraphStyle(name="CustomNormal", parent=styles["Normal"], alignment=TA_CENTER, fontSize=8)
    header_style = ParagraphStyle(name="CustomHeader", parent=styles["Normal"], alignment=TA_CENTER, fontSize=9, fontName="Helvetica-Bold")
    
    story = [
        Paragraph("Relatório Geral de Servidores", styles["h1"]),
        Spacer(1, 1 * cm),
    ]

    if not servidores:
        story.append(Paragraph("Nenhum servidor cadastrado.", styles["Normal"]))
    else:
        table_data = [
            [Paragraph(h, header_style) for h in ["Nome", "CPF", "Função", "Lotação", "Vínculo", "Telefone"]]
        ]
        for s in servidores:
            row = [
                Paragraph(s.nome or "", p_style),
                Paragraph(s.cpf or "", p_style),
                Paragraph(s.funcao or "", p_style),
                Paragraph(s.lotacao or "", p_style),
                Paragraph(s.tipo_vinculo or "", p_style),
                Paragraph(s.telefone or "", p_style),
            ]
            table_data.append(row)

        table = Table(table_data, colWidths=[7 * cm, 3.5 * cm, 4 * cm, 4 * cm, 3.5 * cm, 3 * cm])
        style = TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#004d40")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
        table.setStyle(style)
        story.append(table)

    doc.build(story)
    buffer.seek(0)
    
    response = make_response(buffer.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'inline; filename=relatorio_servidores_{datetime.now().strftime("%Y-%m-%d")}.pdf'
    
    registrar_log("Gerou o PDF do Relatório Geral de Servidores.")
    return response


@app.route("/combustivel/relatorio/mensal/selecionar")
@login_required
def pagina_relatorio_mensal():
    return render_template("relatorio_mensal.html")

@app.route("/relatorio/combustivel/tce-pi")
@login_required
def relatorio_combustivel_tce_pi():
    """
    Gera um relatório de abastecimento no formato CSV exigido pelo TCE-PI.
    """
    try:
        abastecimentos = Abastecimento.query.join(
            Motorista, Abastecimento.motorista_id == Motorista.id
        ).join(Veiculo).order_by(Abastecimento.data.asc()).all()

        output = io.StringIO()
        writer = csv.writer(output, delimiter=";")

        header = [
            "unidade_gestora", "exercicio", "mes_referencia", "numero_notafiscal",
            "data_notafiscal", "cpf_condutor", "nome_condutor", "placa_veiculo",
            "quilometragem", "tipo_combustivel", "quantidade_combustivel",
            "valor_unitario", "valor_total", "cnpj_fornecedor",
        ]
        writer.writerow(header)

        for r in abastecimentos:
            row = [
                "", r.data.year, r.data.month, "", r.data.strftime("%Y-%m-%d"),
                r.motorista.cpf, r.motorista.nome, r.veiculo.placa,
                f"{r.quilometragem:.1f}".replace(".", ","), r.tipo_combustivel,
                f"{r.litros:.2f}".replace(".", ","), f"{r.valor_litro:.2f}".replace(".", ","),
                f"{r.valor_total:.2f}".replace(".", ","), "",
            ]
            writer.writerow(row)

        csv_content = output.getvalue()
        response = Response(
            csv_content.encode("utf-8-sig"),
            mimetype="text/csv",
            headers={
                "Content-Disposition": "attachment;filename=Relatorio_Abastecimento_TCE-PI.csv"
            },
        )
        registrar_log("Gerou o relatório de abastecimento para o TCE-PI.")
        return response

    except Exception as e:
        flash(f"Ocorreu um erro ao gerar o relatório: {e}", "danger")
        return redirect(url_for("lancar_abastecimento"))


@app.route("/relatorio/veiculos/selecionar")
@login_required
def selecionar_relatorio_veiculos():
    return render_template("selecionar_relatorio_veiculos.html")   


@app.route("/relatorio/veiculos/gerar", methods=["POST"])
@login_required
@fleet_required
def gerar_relatorio_veiculos_mensal():
    try:
        ano = int(request.form.get("ano"))
        mes = int(request.form.get("mes"))
        orgao_filtro = request.form.get("orgao")

        data_inicio = datetime(ano, mes, 1)
        if mes == 12:
            data_fim = datetime(ano + 1, 1, 1)
        else:
            data_fim = datetime(ano, mes + 1, 1)

        query_veiculos = Veiculo.query

        if orgao_filtro and orgao_filtro != "todos":
            query_veiculos = query_veiculos.filter(Veiculo.orgao == orgao_filtro)

        veiculos = query_veiculos.order_by(Veiculo.modelo).all()
        dados_relatorio = []

        for veiculo in veiculos:
            abastecimentos_do_mes = (
                Abastecimento.query.filter(
                    Abastecimento.veiculo_placa == veiculo.placa,
                    Abastecimento.data >= data_inicio,
                    Abastecimento.data < data_fim,
                )
                .order_by(Abastecimento.quilometragem.asc())
                .all()
            )

            if abastecimentos_do_mes:
                km_anterior_por_veiculo = {}
                ultimo_abastecimento_anterior = (
                    Abastecimento.query.filter(
                        Abastecimento.veiculo_placa == veiculo.placa,
                        Abastecimento.data < data_inicio,
                    )
                    .order_by(Abastecimento.quilometragem.desc())
                    .first()
                )

                if ultimo_abastecimento_anterior:
                    km_anterior_por_veiculo[veiculo.placa] = (
                        ultimo_abastecimento_anterior.quilometragem
                    )

                for r in abastecimentos_do_mes:
                    placa = r.veiculo.placa
                    km_inicial = km_anterior_por_veiculo.get(placa, 0)
                    km_final = r.quilometragem
                    dados_relatorio.append(
                        {
                            "modelo": veiculo.modelo,
                            "placa": placa,
                            "renavam": veiculo.renavam or "",
                            "ano_fab": veiculo.ano_fabricacao or "",
                            "ano_mod": veiculo.ano_modelo or "",
                            "tipo_veiculo": r.veiculo.tipo or "AUTOMOVEL",
                            "orgao_localizacao": veiculo.orgao or "",
                            "qtde_abastecimento": f"{r.litros:.2f}".replace(".", ","),
                            "combustivel": r.tipo_combustivel,
                            "km_inicial_mes": (
                                f"{km_inicial:.1f}".replace(".", ",")
                                if km_inicial
                                else ""
                            ),
                            "km_final_mes": f"{km_final:.1f}".replace(".", ","),
                        }
                    )
                    km_anterior_por_veiculo[placa] = km_final

        if not dados_relatorio:
            flash(
                f"Nenhum abastecimento encontrado para os filtros selecionados.",
                "warning",
            )
            return redirect(url_for("selecionar_relatorio_veiculos"))

        output = io.StringIO()
        # A coluna 'capacidade' não existe no dicionário, foi removida do header
        header = [
            "modelo",
            "placa",
            "renavam",
            "ano_fab",
            "ano_mod",
            "tipo_veiculo",
            "capacidade",
            "orgao_localizacao",
            "qtde_abastecimento",
            "combustivel",
            "km_inicial_mes",
            "km_final_mes",
        ]
        writer = csv.DictWriter(output, fieldnames=header, delimiter=";")
        writer.writeheader()

        # O DictWriter espera um dicionário com todas as chaves do cabeçalho
        # Precisamos garantir que todas as chaves existam em cada linha
        rows_completas = []
        for row in dados_relatorio:
            # Adiciona a chave 'capacidade' vazia se ela não existir
            if "capacidade" not in row:
                row["capacidade"] = ""
            rows_completas.append(row)

        writer.writerows(rows_completas)

        response = Response(
            output.getvalue().encode("utf-8-sig"),
            mimetype="text/csv",
            headers={
                "Content-Disposition": f"attachment;filename=relatorio_detalhado_{mes}-{ano}.csv"
            },
        )
        return response

    except Exception as e:
        db.session.rollback()
        flash(f"Ocorreu um erro ao gerar o relatório: {e}", "danger")
        return redirect(url_for("selecionar_relatorio_veiculos"))    


@app.route("/usuarios/delete/<int:id>")
@login_required
@admin_required
def delete_usuario(id):
    if User.query.count() <= 1:
        flash("Não é possível excluir o último usuário do sistema.", "danger")
        return redirect(url_for("lista_usuarios"))
    user_to_delete = User.query.get_or_404(id)
    if user_to_delete.username == session.get("username"):
        flash("Você não pode excluir seu próprio usuário.", "danger")
        return redirect(url_for("lista_usuarios"))
    username_deleted = user_to_delete.username
    db.session.delete(user_to_delete)
    db.session.commit()
    registrar_log(f'Excluiu o usuário: "{username_deleted}".')
    flash(f'Usuário "{username_deleted}" excluído.', "success")
    return redirect(url_for("lista_usuarios"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # ... (a lógica do POST continua a mesma)
        username = request.form.get("usuario")
        password = request.form.get("senha")
        secretaria = request.form.get("secretaria")

        if not secretaria:
            flash("Seleção de secretaria inválida. Por favor, reinicie o processo.", "danger")
            return redirect(url_for("login"))

        user = User.query.filter_by(username=username).first()
        
        if user and bcrypt.check_password_hash(user.password_hash, password):
            session["logged_in"] = True
            session["username"] = user.username
            session["role"] = user.role
            session["secretaria"] = secretaria
            
            registrar_log(f"Fez login no sistema pela secretaria '{secretaria}'.")
            flash("Login realizado com sucesso!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Usuário ou senha inválidos.", "danger")
            return redirect(url_for("login"))
    
    # --- ALTERAÇÃO PRINCIPAL AQUI ---
    # Agora busca os dados da nova tabela 'Secretaria'
    secretarias_cadastradas = Secretaria.query.order_by(Secretaria.nome).all()
    # Pega apenas o nome de cada secretaria para a lista
    secretarias = [s.nome for s in secretarias_cadastradas]
    
    return render_template("login.html", secretarias=secretarias)


@app.route("/")
@login_required
def dashboard():
    total_servidores = db.session.query(func.count(Servidor.num_contrato)).scalar()
    
    # Lógica para os gráficos (estava faltando)
    servidores_por_funcao = (
        db.session.query(Servidor.funcao, func.count(Servidor.funcao))
        .group_by(Servidor.funcao)
        .order_by(func.count(Servidor.funcao).desc())
        .all()
    )
    servidores_por_lotacao = (
        db.session.query(Servidor.lotacao, func.count(Servidor.lotacao))
        .group_by(Servidor.lotacao)
        .order_by(func.count(Servidor.lotacao).desc())
        .all()
    )
    
    # Cria as listas de dados para enviar ao template
    funcao_labels = [item[0] or "Não Especificado" for item in servidores_por_funcao]
    funcao_data = [item[1] for item in servidores_por_funcao]
    lotacao_labels = [item[0] or "Não Especificado" for item in servidores_por_lotacao]
    lotacao_data = [item[1] for item in servidores_por_lotacao]

    # Envia todas as variáveis necessárias para o template
    return render_template(
        "dashboard.html",
        total_servidores=total_servidores,
        funcao_labels=funcao_labels,
        funcao_data=funcao_data,
        lotacao_labels=lotacao_labels,
        lotacao_data=lotacao_data
    )


@app.route("/logout")
@login_required
def logout():
    registrar_log("Fez logout do sistema.")
    session.clear()
    flash("Você saiu do sistema.", "info")
    return redirect(url_for("login"))


# ==========================================================
# ROTAS DO MÓDULO GAM
# ==========================================================
@app.route("/gam")
@login_required
def listar_gams():
    gams = GAM.query.order_by(GAM.data_emissao.desc()).all()
    return render_template("listar_gams.html", gams=gams)


@app.route("/gam/novo", methods=["GET", "POST"])
@login_required
def criar_gam():
    if request.method == "POST":
        servidor_contrato = request.form.get("servidor_num_contrato")
        servidor = Servidor.query.get(servidor_contrato)
        if not servidor:
            flash("Erro: Servidor selecionado é inválido.", "danger")
            return redirect(url_for("criar_gam"))
        data_laudo_str = request.form.get("data_laudo")
        nova_guia = GAM(
            servidor_num_contrato=servidor_contrato,
            texto_inicial_observacoes=request.form.get("texto_inicial_observacoes"),
            data_laudo=datetime.strptime(data_laudo_str, "%Y-%m-%d").date() if data_laudo_str else None,
            medico_laudo=request.form.get("medico_laudo"),
            dias_afastamento_laudo=request.form.get("dias_afastamento_laudo", type=int),
            justificativa_laudo=request.form.get("justificativa_laudo"),
            cid10=request.form.get("cid10"),
            status="Emitida"
        )
        db.session.add(nova_guia)
        db.session.commit()
        flash("Guia de Atendimento Médico (GAM) gerada com sucesso!", "success")
        return redirect(url_for("listar_gams"))
    servidores_efetivos = Servidor.query.filter(Servidor.tipo_vinculo.ilike("%efetivo%")).order_by(Servidor.nome).all()
    return render_template("gam_form.html", servidores=servidores_efetivos, gam=None)


@app.route("/gam/editar/<int:gam_id>", methods=["GET", "POST"])
@login_required
def editar_gam(gam_id):
    guia = GAM.query.get_or_404(gam_id)
    if request.method == "POST":
        try:
            guia.texto_inicial_observacoes = request.form.get("texto_inicial_observacoes")
            data_laudo_str = request.form.get("data_laudo")
            guia.data_laudo = datetime.strptime(data_laudo_str, "%Y-%m-%d").date() if data_laudo_str else None
            guia.medico_laudo = request.form.get("medico_laudo")
            guia.dias_afastamento_laudo = request.form.get("dias_afastamento_laudo", type=int)
            guia.justificativa_laudo = request.form.get("justificativa_laudo")
            guia.cid10 = request.form.get("cid10")
            db.session.commit()
            flash("Guia atualizada com sucesso!", "success")
            return redirect(url_for("listar_gams"))
        except Exception as e:
            db.session.rollback()
            flash(f"Ocorreu um erro ao atualizar a guia: {e}", "danger")
    servidores_efetivos = Servidor.query.filter(Servidor.tipo_vinculo.ilike("%efetivo%")).order_by(Servidor.nome).all()
    return render_template("gam_form.html", gam=guia, servidores=servidores_efetivos)


@app.route("/gam/excluir/<int:gam_id>")
@login_required
@admin_required
def excluir_gam(gam_id):
    guia = GAM.query.get_or_404(gam_id)
    try:
        db.session.delete(guia)
        db.session.commit()
        flash("Guia excluída com sucesso.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir a guia: {e}", "danger")
    return redirect(url_for("listar_gams"))


@app.route("/gam/imprimir/<int:gam_id>")
@login_required
def imprimir_gam(gam_id):
    guia = GAM.query.get_or_404(gam_id)
    pdf_buffer = gerar_pdf_gam(guia)
    response = make_response(pdf_buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    nome_arquivo = f'GAM_{guia.servidor.nome.replace(" ", "_")}_{guia.id}.pdf'
    response.headers['Content-Disposition'] = f'inline; filename={nome_arquivo}'
    return response


def gerar_pdf_gam(guia):
    buffer = io.BytesIO()
    doc = BaseDocTemplate(buffer, pagesize=A4, leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=4.5*cm, bottomMargin=1.5*cm)
    def cabecalho_completo(canvas, doc):
        canvas.saveState()
        try:
            timbre_path = os.path.join(basedir, "static", "timbre.jpg")
            if os.path.exists(timbre_path):
                logo = Image(timbre_path, width=17*cm, height=2.2*cm, hAlign='CENTER')
                logo.drawOn(canvas, 2*cm, A4[1] - 3*cm)
        except Exception as e:
            print(f"Erro ao carregar o timbre: {e}")
        posicao_y_texto = A4[1] - 3.7*cm
        canvas.setFont('Helvetica-Bold', 12)
        canvas.drawCentredString(10.5*cm, posicao_y_texto, "GUIA PARA ATENDIMENTO MÉDICO - GAM")
        canvas.setFont('Helvetica-Bold', 11)
        canvas.drawCentredString(10.5*cm, posicao_y_texto - 0.5*cm, "PREFEITURA MUNICIPAL DE VALENÇA DO PIAUÍ")
        canvas.restoreState()
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
    template = PageTemplate(id='main_template', frames=[frame], onPage=cabecalho_completo)
    doc.addPageTemplates([template])
    story = []
    styles = getSampleStyleSheet()
    style_corpo = ParagraphStyle(name='Corpo', fontName='Helvetica', fontSize=10.5, alignment=TA_JUSTIFY, leading=13)
    style_negrito = ParagraphStyle(name='Negrito', parent=style_corpo, fontName='Helvetica-Bold')
    style_assinatura = ParagraphStyle(name='Assinatura', fontName='Helvetica', fontSize=9, alignment=TA_CENTER)
    dados_servidor_texto = f"<b>1-NOME DO SERVIDOR:</b> {guia.servidor.nome.upper()} &nbsp;&nbsp; <b>MATRÍCULA N.</b> {guia.servidor.num_contrato} &nbsp;&nbsp; <b>LOTAÇÃO:</b> {guia.servidor.lotacao}"
    if guia.data_laudo:
        locale.setlocale(locale.LC_TIME, "pt_BR.UTF-8")
        data_laudo_formatada = guia.data_laudo.strftime('%d de %B de %Y')
    else:
        data_laudo_formatada = "[data não informada]"
    texto_observacoes = (f"{guia.texto_inicial_observacoes or ''} Na declaração médica, datada do dia {data_laudo_formatada}, o(a) médico(a) {guia.medico_laudo or '[médico]'} recomenda {guia.dias_afastamento_laudo or '[dias]'} dias de afastamento das suas atividades laborais, pois declara que {guia.justificativa_laudo or '[justificativa]'}")
    cid_texto = f"<b>CID 10: {guia.cid10 or 'Não informado'}</b>"
    encaminhamento_texto = f"Desse modo, encaminho o(a) servidor(a) {guia.servidor.nome} para perícia médica do município."
    observacoes_data = [[Paragraph("OBSERVAÇÕES DA CHEFIA (ESPECIFICAR A DESCRIÇÃO DO CARGO/FUNÇÃO)", style_negrito)], [Paragraph(texto_observacoes, style_corpo)], [Paragraph(cid_texto, style_corpo)], [Paragraph(encaminhamento_texto, style_corpo)]]
    tabela_observacoes = Table(observacoes_data, colWidths=[18*cm])
    tabela_observacoes.setStyle(TableStyle([('BOTTOMPADDING', (0, 0), (0, 0), 8), ('TOPPADDING', (0, 1), (0, -1), 8)]))
    data_hora_texto = f"DATA: {guia.data_emissao.strftime('%d/%m/%Y')}, HORA: {guia.data_emissao.strftime('%H:%M')}"
    assinatura_chefia_data = [[Paragraph(data_hora_texto, style_corpo)], [Spacer(1, 1*cm)], [HRFlowable(width="70%", thickness=0.5, color=colors.black, hAlign='CENTER')], [Paragraph("ASSINATURA E CARIMBO DA CHEFIA", style_assinatura)]]
    tabela_assinatura_chefia = Table(assinatura_chefia_data, colWidths=[18*cm])
    medico_data_hora = "<b>2-DATA DO ATENDIMENTO:</b> ______/______/__________ &nbsp;&nbsp;&nbsp; <b>HORA DO ATENDIMENTO:</b>_____:_____ h."
    assinatura_medico_data = [[Paragraph(medico_data_hora, style_corpo)], [Spacer(1, 0.5*cm)], [Paragraph("<b>RECOMENDAÇÕES DO MÉDICO</b>", style_corpo)], [Spacer(1, 2.5*cm)], [Paragraph("DATA: ______/______/__________", style_corpo)], [Spacer(1, 1*cm)], [HRFlowable(width="70%", thickness=0.5, color=colors.black, hAlign='CENTER')], [Paragraph("ASSINATURA E CARIMBO DO MÉDICO", style_assinatura)]]
    tabela_medico = Table(assinatura_medico_data, colWidths=[18*cm])
    tabela_principal_data = [[Paragraph(dados_servidor_texto, style_corpo)], [tabela_observacoes], [tabela_assinatura_chefia], [HRFlowable(width="100%", thickness=1, color=colors.black, dash=(2,2))], [tabela_medico]]
    tabela_principal = Table(tabela_principal_data, rowHeights=[1.2*cm, 7.5*cm, 3*cm, 0.3*cm, 6.5*cm])
    tabela_principal.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 4)]))
    story.append(tabela_principal)
    doc.build(story)
    buffer.seek(0)
    return buffer


@app.route("/api/servidor-details/<string:num_contrato>")
@login_required
def get_servidor_details(num_contrato):
    servidor = Servidor.query.filter_by(num_contrato=num_contrato).first()
    if servidor:
        return jsonify({
            "nome": servidor.nome,
            "matricula": servidor.num_contrato,
            "lotacao": servidor.lotacao,
            "funcao": servidor.funcao,
            "data_admissao": servidor.data_inicio.strftime('%d/%m/%Y') if servidor.data_inicio else ''
        })
    return jsonify({"error": "Servidor não encontrado"}), 404
    
@app.route("/servidores")
@login_required
def lista_servidores():
    termo_busca = request.args.get("termo")
    funcao_filtro = request.args.get("funcao")
    lotacao_filtro = request.args.get("lotacao")
    query = Servidor.query

    if termo_busca:
        search_pattern = f"%{termo_busca}%"
        query = query.filter(
            or_(
                Servidor.nome.ilike(search_pattern),
                Servidor.cpf.ilike(search_pattern),
                Servidor.num_contrato.ilike(search_pattern),
            )
        )

    if funcao_filtro:
        query = query.filter(Servidor.funcao == funcao_filtro)

    if lotacao_filtro:
        query = query.filter(Servidor.lotacao == lotacao_filtro)

    servidores = query.order_by(Servidor.nome).all()

    funcoes_disponiveis = [r[0] for r in db.session.query(Servidor.funcao).distinct().order_by(Servidor.funcao).all() if r[0]]
    lotacoes_disponiveis = [r[0] for r in db.session.query(Servidor.lotacao).distinct().order_by(Servidor.lotacao).all() if r[0]]
    
    # --- LÓGICA FALTANTE ADICIONADA AQUI ---
    hoje = datetime.now().date()
    status_servidores = {}
    requerimentos_ativos = Requerimento.query.filter(
        Requerimento.status == "Aprovado", Requerimento.data_inicio_requerimento <= hoje
    ).all()

    for req in requerimentos_ativos:
        if not req.data_retorno_trabalho or req.data_retorno_trabalho > hoje:
            status_servidores[req.servidor_cpf] = req.natureza
    # --- FIM DA LÓGICA FALTANTE ---

    return render_template(
        "index.html", 
        servidores=servidores,
        funcoes_disponiveis=funcoes_disponiveis,
        lotacoes_disponiveis=lotacoes_disponiveis,
        status_servidores=status_servidores # <-- Variável agora sendo enviada
    )
    
    
@app.route("/delete/<path:id>")
@login_required
@admin_required
def delete_server(id):
    servidor = Servidor.query.get_or_404(id)
    dependencias = []
    
    if hasattr(servidor, 'contratos') and servidor.contratos: dependencias.append("contratos")
    if hasattr(servidor, 'requerimentos') and servidor.requerimentos: dependencias.append("requerimentos")
    if hasattr(servidor, 'pontos') and servidor.pontos: dependencias.append("registros de ponto")
    
    if dependencias:
        dependencias_str = ", ".join(dependencias)
        flash(f'Não é possível excluir o servidor "{servidor.nome}", pois ele possui vínculos com: {dependencias_str}.', "danger")
        return redirect(url_for("lista_servidores"))
    
    nome_servidor = servidor.nome
    try:
        if servidor.foto_filename and os.path.exists(os.path.join(app.config["UPLOAD_FOLDER"], servidor.foto_filename)):
            os.remove(os.path.join(app.config["UPLOAD_FOLDER"], servidor.foto_filename))
        for doc in servidor.documentos:
            doc_path = os.path.join(app.config["UPLOAD_FOLDER"], "documentos", doc.filename)
            if os.path.exists(doc_path):
                os.remove(doc_path)
        
        db.session.delete(servidor)
        db.session.commit()
        registrar_log(f'Excluiu o servidor: "{nome_servidor}".')
        flash(f'Servidor "{nome_servidor}" excluído com sucesso!', "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Ocorreu um erro ao tentar excluir o servidor: {e}", "danger")
    
    return redirect(url_for("lista_servidores"))    
    
@app.route("/importar_servidores", methods=["POST"])
@login_required
@admin_required
def importar_servidores():
    if "csv_file" not in request.files:
        flash("Nenhum arquivo enviado.", "danger")
        return redirect(url_for("lista_servidores"))
    
    file = request.files["csv_file"]
    if file.filename == "":
        flash("Nenhum arquivo selecionado.", "danger")
        return redirect(url_for("lista_servidores"))

    if file and file.filename.endswith(".csv"):
        try:
            # Lógica para ler e processar o arquivo CSV
            # (Esta parte do seu código original)
            db.session.commit()
            flash("Importação concluída com sucesso!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Ocorreu um erro ao processar o arquivo: {e}", "danger")
        
        return redirect(url_for("lista_servidores"))
    else:
        flash("Formato de arquivo inválido. Por favor, envie um arquivo .csv.", "warning")
        return redirect(url_for("lista_servidores"))

@app.route("/baixar_modelo_csv")
@login_required
def baixar_modelo_csv():
    header = [
        "Nº CONTRATO", "NOME", "FUNÇÃO", "LOTAÇÃO", 
        "CARGA HORÁRIA", "REMUNERAÇÃO", "VIGÊNCIA",
    ]
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(header)
    csv_content = output.getvalue()
    
    response = Response(
        csv_content.encode("utf-8-sig"),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment;filename=modelo_importacao_servidores.csv"
        },
    )
    return response



@app.route("/veiculo/<string:placa>/detalhes")
@login_required
@check_license
def detalhes_veiculo(placa):
    veiculo = Veiculo.query.get_or_404(placa)
    abastecimentos = Abastecimento.query.filter_by(veiculo_placa=placa).order_by(Abastecimento.quilometragem.asc()).all()
    manutencoes = Manutencao.query.filter_by(veiculo_placa=placa).order_by(Manutencao.data.desc()).all()
    indicadores = { "gasto_combustivel": sum(a.valor_total for a in abastecimentos), "gasto_manutencao": sum(m.custo for m in manutencoes), "total_litros": sum(a.litros for a in abastecimentos), "total_km_rodado": 0, "consumo_medio_geral": 0, "custo_medio_km": 0, }
    indicadores["gasto_total"] = indicadores["gasto_combustivel"] + indicadores["gasto_manutencao"]
    chart_labels = []
    chart_consumo_data = []
    chart_custo_km_data = []
    abastecimentos_com_analise = []
    if len(abastecimentos) > 1:
        indicadores["total_km_rodado"] = abastecimentos[-1].quilometragem - abastecimentos[0].quilometragem
        if indicadores["total_km_rodado"] > 0:
            litros_para_media = sum(a.litros for a in abastecimentos[:-1])
            if litros_para_media > 0:
                indicadores["consumo_medio_geral"] = indicadores["total_km_rodado"] / litros_para_media
            if indicadores["gasto_total"] > 0:
                indicadores["custo_medio_km"] = indicadores["gasto_total"] / indicadores["total_km_rodado"]
        for i in range(1, len(abastecimentos)):
            anterior = abastecimentos[i - 1]
            atual = abastecimentos[i]
            analise = {"abastecimento": atual, "km_rodado": 0, "consumo_kml": 0}
            km_rodado = atual.quilometragem - anterior.quilometragem
            if km_rodado > 0 and anterior.litros > 0:
                consumo_kml = km_rodado / anterior.litros
                custo_km = anterior.valor_total / km_rodado
                analise.update({"km_rodado": km_rodado, "consumo_kml": consumo_kml})
                chart_labels.append(atual.data.strftime("%d/%m"))
                chart_consumo_data.append(round(consumo_kml, 2))
                chart_custo_km_data.append(round(custo_km, 2))
            abastecimentos_com_analise.append(analise)
    abastecimentos_com_analise.reverse()
    
    return render_template("detalhes_veiculo.html", veiculo=veiculo,
                indicadores=indicadores, abastecimentos_com_analise=abastecimentos_com_analise,
                manutencoes=manutencoes, chart_labels=chart_labels, chart_consumo_data=chart_consumo_data, 
                chart_custo_km_data=chart_custo_km_data)    


@app.route("/add", methods=["POST"])
@login_required
def add_server():
    try:
        foto = request.files.get("foto")
        foto_filename = None
        if foto and foto.filename != "":
            foto_filename = secure_filename(foto.filename)
            foto.save(os.path.join(app.config["UPLOAD_FOLDER"], foto_filename))

        data_inicio_str = request.form.get("data_inicio")
        data_saida_str = request.form.get("data_saida")
        data_nascimento_str = request.form.get("data_nascimento")
        data_inicio_obj = datetime.strptime(data_inicio_str, "%Y-%m-%d").date() if data_inicio_str else None
        data_saida_obj = datetime.strptime(data_saida_str, "%Y-%m-%d").date() if data_saida_str else None
        data_nascimento_obj = datetime.strptime(data_nascimento_str, "%Y-%m-%d").date() if data_nascimento_str else None
        
        cpf_limpo = limpar_cpf(request.form.get("cpf"))
        remuneracao_str = request.form.get("remuneracao", "0").replace(".", "").replace(",", ".")
        remuneracao_val = float(remuneracao_str) if remuneracao_str else 0.0
        
        novo_servidor = Servidor(
            num_contrato=request.form.get("num_contrato"), nome=request.form.get("nome"), cpf=cpf_limpo, rg=request.form.get("rg"),
            data_nascimento=data_nascimento_obj, nome_mae=request.form.get("nome_mae"), email=request.form.get("email"),
            pis_pasep=request.form.get("pis_pasep"), tipo_vinculo=request.form.get("tipo_vinculo"), local_trabalho=request.form.get("local_trabalho"),
            classe_nivel=request.form.get("classe_nivel"), num_contra_cheque=request.form.get("num_contra_cheque"), nacionalidade=request.form.get("nacionalidade"),
            estado_civil=request.form.get("estado_civil"), telefone=request.form.get("telefone"), endereco=request.form.get("endereco"),
            funcao=request.form.get("funcao"), lotacao=request.form.get("lotacao"), carga_horaria=request.form.get("carga_horaria"),
            remuneracao=remuneracao_val, dados_bancarios=request.form.get("dados_bancarios"), data_inicio=data_inicio_obj,
            data_saida=data_saida_obj, observacoes=request.form.get("observacoes"), foto_filename=foto_filename,
        )
        db.session.add(novo_servidor)
        db.session.commit()
        registrar_log(f'Cadastrou o servidor: "{novo_servidor.nome}" (Vínculo: {novo_servidor.num_contrato}).')
        flash("Servidor cadastrado com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        registrar_log(f"Falha ao tentar cadastrar servidor. Erro: {e}")
        flash(f"Erro ao cadastrar servidor: {e}", "danger")
    return redirect(url_for("lista_servidores"))


@app.route("/editar/<path:id>", methods=["GET", "POST"])
@login_required
def editar_servidor(id):
    servidor = Servidor.query.get_or_404(id)
    if request.method == "POST":
        try:
            # Lógica para salvar os dados editados
            # (Esta parte do seu código original)
            db.session.commit()
            flash("Dados do servidor atualizados com sucesso!", "success")
            return redirect(url_for("lista_servidores"))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao atualizar servidor: {e}", "danger")
            return redirect(url_for("editar_servidor", id=id))
    return render_template("editar.html", servidor=servidor)
    
@app.route("/veiculos", methods=["GET", "POST"])
@login_required
def gerenciar_veiculos():
    if request.method == "POST":
        nova_placa = request.form.get("placa").upper().strip()
        veiculo_existente = Veiculo.query.get(nova_placa)
        if veiculo_existente:
            flash("Veículo com esta placa já cadastrado.", "danger")
            return redirect(url_for("gerenciar_veiculos"))

        novo_veiculo = Veiculo(
            placa=nova_placa,
            modelo=request.form.get("modelo"),
            tipo=request.form.get("tipo"),
            ano_fabricacao=int(request.form.get("ano_fabricacao") or 0)
        )
        db.session.add(novo_veiculo)
        db.session.commit()
        registrar_log(f"Cadastrou o veículo: Placa {novo_veiculo.placa}, Modelo {novo_veiculo.modelo}.")
        flash("Veículo cadastrado com sucesso!", "success")
        return redirect(url_for("gerenciar_veiculos"))

    hoje = datetime.now().date()
    veiculos = Veiculo.query.order_by(Veiculo.modelo).all()

    return render_template(
        "veiculos.html", # ATENÇÃO: Verifique se o nome deste template está correto
        veiculos=veiculos,
        hoje=hoje
    )


@app.route("/veiculos/excluir/<path:placa>")
@login_required
def excluir_veiculo(placa):
    veiculo = Veiculo.query.get_or_404(placa)
    try:
        db.session.delete(veiculo)
        db.session.commit()
        registrar_log(f"Excluiu o veículo: Placa {veiculo.placa}.")
        flash("Veículo excluído com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Não foi possível excluir o veículo. Erro: {e}", "danger")
    return redirect(url_for("gerenciar_veiculos"))
    
    
    
    
@app.route("/requerimentos")
@login_required
def listar_requerimentos():
    requerimentos = Requerimento.query.order_by(Requerimento.data_criacao.desc()).all()
    return render_template("requerimentos.html", requerimentos=requerimentos)


@app.route("/requerimentos/novo", methods=["GET", "POST"])
@login_required
def novo_requerimento():
    if request.method == "POST":
        try:
            cpf_servidor = limpar_cpf(request.form.get("cpf_busca"))
            servidor = Servidor.query.filter_by(cpf=cpf_servidor).first()
            if not servidor:
                flash("Servidor com o CPF informado não encontrado.", "danger")
                return redirect(url_for("novo_requerimento"))

            novo_req = Requerimento(
                autoridade_dirigida=request.form.get("autoridade_dirigida"),
                servidor_cpf=cpf_servidor,
                natureza=request.form.get("natureza"),
                data_inicio_requerimento=datetime.strptime(request.form.get("data_inicio_requerimento"), "%Y-%m-%d").date(),
                status="Em Análise",
                # Adicione outros campos do formulário aqui se necessário
            )
            db.session.add(novo_req)
            db.session.commit()
            flash("Requerimento criado com sucesso!", "success")
            return redirect(url_for("listar_requerimentos"))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao criar requerimento: {e}", "danger")
    return render_template("requerimento_form.html")

@app.route("/requerimento/pdf/<int:req_id>")
@login_required
def gerar_requerimento_pdf(req_id):
    requerimento = Requerimento.query.get_or_404(req_id)
    # ... (sua lógica de geração de PDF) ...
    # Exemplo simples:
    return f"Gerando PDF para o requerimento {requerimento.id} do servidor {requerimento.servidor.nome}"


@app.route("/combustivel", methods=["GET", "POST"])
@login_required
def lancar_abastecimento():
    if request.method == "POST":
        try:
            litros_str = request.form.get("litros", "").strip().replace(",", ".")
            valor_litro_str = request.form.get("valor_litro", "").strip().replace(",", ".")
            quilometragem_str = request.form.get("quilometragem", "").strip().replace(",", ".")
            litros = float(litros_str) if litros_str else 0.0
            valor_litro = float(valor_litro_str) if valor_litro_str else 0.0
            quilometragem_val = int(quilometragem_str) if quilometragem_str else 0
            valor_total = litros * valor_litro
            
            novo_abastecimento = Abastecimento(
                veiculo_placa=request.form.get("veiculo_placa"),
                motorista_id=request.form.get("motorista_id"),
                quilometragem=quilometragem_val,
                tipo_combustivel=request.form.get("tipo_combustivel"),
                litros=litros,
                valor_litro=valor_litro,
                valor_total=valor_total,
            )
            db.session.add(novo_abastecimento)
            db.session.commit()
            flash("Abastecimento registrado com sucesso!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao registrar abastecimento: {e}", "danger")
        
        return redirect(url_for("lancar_abastecimento"))

    veiculos = Veiculo.query.order_by(Veiculo.modelo).all()
    motoristas = Motorista.query.order_by(Motorista.nome).all()
    abastecimentos = Abastecimento.query.order_by(Abastecimento.data.desc()).limit(15).all()
    
    return render_template(
        "combustivel.html", # ATENÇÃO: Verifique se este é o nome correto do seu template
        veiculos=veiculos,
        motoristas=motoristas,
        abastecimentos=abastecimentos
    )


@app.route("/ponto/frequencia")
@login_required
@admin_required
def visualizar_frequencia():
    page = request.args.get("page", 1, type=int)
    registros = Ponto.query.order_by(Ponto.timestamp.desc()).paginate(
        page=page, per_page=50
    )
    return render_template("frequencia.html", registros=registros)

# Adicione também as outras rotas relacionadas se estiverem faltando, como a de registrar o ponto
@app.route("/ponto/registrar", methods=["GET", "POST"])
def registrar_ponto():
    if request.method == "POST":
        # ... (Sua lógica para salvar o ponto) ...
        return redirect(url_for("registrar_ponto"))

    escolas = Escola.query.filter(Escola.status == "Ativa", Escola.latitude.isnot(None)).order_by(Escola.nome).all()
    return render_template("registrar_ponto_com_foto.html", escolas=escolas)

@app.route("/bloco_de_notas")
@login_required
def bloco_de_notas():
    user = User.query.filter_by(username=session["username"]).first_or_404()
    notas = Nota.query.filter_by(user_id=user.id).order_by(Nota.data_criacao.desc()).all()
    return render_template("bloco_de_notas.html", notas=notas)


@app.route("/notas/add", methods=["POST"])
@login_required
def add_nota():
    user = User.query.filter_by(username=session["username"]).first_or_404()
    titulo = request.form.get("titulo")
    conteudo = request.form.get("conteudo")
    if not titulo:
        flash("O título da anotação é obrigatório.", "warning")
        return redirect(url_for("bloco_de_notas"))
    nova_nota = Nota(titulo=titulo, conteudo=conteudo, autor=user)
    db.session.add(nova_nota)
    db.session.commit()
    registrar_log(f'Criou a anotação: "{titulo}"')
    flash("Anotação criada com sucesso!", "success")
    return redirect(url_for("bloco_de_notas"))


@app.route("/notas/update/<int:id>", methods=["POST"])
@login_required
def update_nota(id):
    nota = Nota.query.get_or_404(id)
    if nota.autor.username != session["username"]:
        abort(403)
    nota.titulo = request.form.get("titulo")
    nota.conteudo = request.form.get("conteudo")
    db.session.commit()
    registrar_log(f'Editou a anotação: "{nota.titulo}"')
    flash("Anotação atualizada com sucesso!", "success")
    return redirect(url_for("bloco_de_notas"))


@app.route("/notas/delete/<int:id>")
@login_required
def delete_nota(id):
    nota = Nota.query.get_or_404(id)
    if nota.autor.username != session["username"]:
        abort(403)
    titulo_nota = nota.titulo
    db.session.delete(nota)
    db.session.commit()
    registrar_log(f'Excluiu a anotação: "{titulo_nota}"')
    flash("Anotação excluída com sucesso!", "success")
    return redirect(url_for("bloco_de_notas"))    
    
@app.route("/combustivel/relatorio", methods=["GET"])
@login_required
def relatorio_combustivel():
    # Coleta os filtros da URL
    placa_filtro = request.args.get("placa")
    query = db.session.query(Abastecimento).join(Veiculo).order_by(Abastecimento.veiculo_placa, Abastecimento.quilometragem)

    if placa_filtro:
        query = query.filter(Veiculo.placa == placa_filtro)

    resultados_filtrados = query.all()
    resultados_com_analise = []
    ultimo_abastecimento = {}

    for r in resultados_filtrados:
        placa = r.veiculo_placa
        analise = {"abastecimento": r, "km_rodado": 0, "consumo_kml": 0, "custo_km": 0}

        if placa in ultimo_abastecimento:
            anterior = ultimo_abastecimento[placa]
            km_rodado = r.quilometragem - anterior.quilometragem
            analise["km_rodado"] = km_rodado
            if km_rodado > 0 and anterior.litros > 0:
                analise["consumo_kml"] = km_rodado / anterior.litros
                analise["custo_km"] = anterior.valor_total / km_rodado

        resultados_com_analise.append(analise)
        ultimo_abastecimento[placa] = r
    
    veiculos = Veiculo.query.order_by(Veiculo.modelo).all()

    return render_template(
        "relatorio_combustivel.html",
        resultados=resultados_com_analise,
        veiculos=veiculos,
    )
    
    
@app.route("/combustivel/excluir/<int:id>")
@login_required
def excluir_abastecimento(id):
    abastecimento_para_excluir = Abastecimento.query.get_or_404(id)
    try:
        info_log = f"veículo placa {abastecimento_para_excluir.veiculo_placa}, {abastecimento_para_excluir.litros}L em {abastecimento_para_excluir.data.strftime('%d/%m/%Y')}"
        db.session.delete(abastecimento_para_excluir)
        db.session.commit()
        registrar_log(f"Excluiu o registro de abastecimento: {info_log}.")
        flash("Registro de abastecimento excluído com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir o registro: {e}", "danger")
    
    return redirect(url_for("lancar_abastecimento"))

@app.route("/ponto/qrcode")
@login_required
@admin_required
def exibir_qrcode_ponto():
    url_registro = url_for("registrar_ponto", _external=True)
    img = qrcode.make(url_registro)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_str = base64.b64encode(buf.getvalue()).decode("utf-8")
    registrar_log("Gerou o QR Code para registro de ponto.")
    return render_template("qrcode_ponto.html", qr_code_image=img_str)    

# ===================================================================
# PARTE 6: Importação e Registro dos Blueprints
# ===================================================================
from .patrimonio_routes import patrimonio_bp
from .merenda_routes import merenda_bp
from .motoristas_routes import motoristas_bp
from .escola_routes import escola_bp
from .transporte_routes import transporte_bp
from .protocolo_routes import protocolo_bp
from .contratos_routes import contratos_bp
from .frequencia_routes import frequencia_bp
from .backup_routes import backup_bp

app.register_blueprint(transporte_bp)
app.register_blueprint(protocolo_bp)
app.register_blueprint(contratos_bp)
app.register_blueprint(patrimonio_bp)
app.register_blueprint(merenda_bp)
app.register_blueprint(motoristas_bp)
app.register_blueprint(escola_bp)
app.register_blueprint(frequencia_bp)
app.register_blueprint(backup_bp)


# ===================================================================
# PARTE 7: Bloco de Execução Principal
# ===================================================================
if __name__ == "__main__":
    app.run(debug=True)