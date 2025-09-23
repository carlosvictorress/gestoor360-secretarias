import os
import io
import csv
import uuid
import locale
import qrcode
import base64
import re
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    make_response,
    send_from_directory,
    Response,
    abort,
)
from sqlalchemy import func, or_, and_
from flask_migrate import Migrate
from .patrimonio_routes import patrimonio_bp
from .merenda_routes import merenda_bp
from functools import wraps
from .motoristas_routes import motoristas_bp
import math  # 08/09/2025
from .models import Escola, Servidor, Ponto
from .merenda_routes import merenda_bp
from .escola_routes import escola_bp  # 1. Importe o novo blueprint
from .models import GAM, Servidor


from .utils import login_required, registrar_log, admin_required, fleet_required

from .transporte_routes import transporte_bp
from .extensions import db, bcrypt
from .protocolo_routes import protocolo_bp

from flask_sqlalchemy import SQLAlchemy

from datetime import datetime, timedelta
from werkzeug.utils import secure_filename

# from flask_bcrypt import Bcrypt
RAIO_PERMITIDO_METROS = 100
from flask import jsonify
from .models import *


from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether

from reportlab.platypus import Table, TableStyle, Paragraph, Spacer, ListFlowable
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from .contratos_routes import contratos_bp

# Importações para o gerador de PDF
from reportlab.lib.pagesizes import letter, landscape, A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    BaseDocTemplate,
    Frame,
    PageTemplate,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.units import cm, inch
from .frequencia_routes import frequencia_bp
from .backup_routes import backup_bp


# from transporte_models import RotaTransporte, AlunoTransporte
# from transporte_routes import transporte_bp
# Importação da biblioteca para escrever números por extenso
from num2words import num2words

# Configura o locale para o português do Brasil para formatar datas
try:
    locale.setlocale(locale.LC_TIME, "pt_BR.UTF-8")
except locale.Error:
    print("Locale pt_BR.UTF-8 não encontrado, usando o padrão do sistema.")


# --- 1. CONFIGURAÇÃO DA APLICAÇÃO ---
app = Flask(__name__)


@app.route("/static/css/<path:filename>")
def serve_css(filename):
    return send_from_directory(
        os.path.join(basedir, "static", "css"), filename, mimetype="text/css"
    )


basedir = os.path.abspath(os.path.dirname(__file__))
database_url = os.environ.get("DATABASE_URL")

if database_url:
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url or "sqlite:///" + os.path.join(
    basedir, "servidores.db"
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "uma-chave-secreta-muito-dificil-de-adivinhar"
app.config["UPLOAD_FOLDER"] = "uploads"

db.init_app(app)
bcrypt.init_app(app)
migrate = Migrate(app, db)
app.register_blueprint(transporte_bp)
app.register_blueprint(protocolo_bp)
app.register_blueprint(contratos_bp)
app.register_blueprint(patrimonio_bp)
app.register_blueprint(merenda_bp)
app.register_blueprint(motoristas_bp)
app.register_blueprint(escola_bp)
app.register_blueprint(frequencia_bp)
app.register_blueprint(backup_bp)


# --- 3. COMANDOS DE BANCO DE DADOS ---


@app.cli.command("expirar-licenca")
def expirar_licenca_command():
    """Define a data de expiração da licença para ontem."""
    with app.app_context():
        licenca = License.query.first()
        if not licenca:
            print("Nenhuma licença encontrada para expirar.")
            return

        data_expirada = datetime.utcnow() - timedelta(days=1)
        licenca.expiration_date = data_expirada
        db.session.commit()

        print("\nLicença definida como EXPIRADA.")
        print(f"A nova data de expiração é: {data_expirada.strftime('%d/%m/%Y')}")


@app.cli.command("alterar-licenca")
def alterar_licenca_command():
    """Altera a data de expiração da licença existente."""
    with app.app_context():
        licenca = License.query.first()
        if not licenca:
            print(
                "Nenhuma licença encontrada. Use 'flask init-license' para criar uma."
            )
            return

        try:
            dias_str = input(
                f"A licença atual expira em {licenca.expiration_date.strftime('%d/%m/%Y')}. Deseja estender por quantos dias a partir de HOJE? "
            )
            dias = int(dias_str)

            nova_data_expiracao = datetime.utcnow() + timedelta(days=dias)
            licenca.expiration_date = nova_data_expiracao
            db.session.commit()

            print("\nLicença alterada com sucesso!")
            print(
                f"A nova data de expiração é: {nova_data_expiracao.strftime('%d/%m/%Y')}"
            )

        except ValueError:
            print("Erro: Por favor, digite um número válido de dias.")
        except Exception as e:
            db.session.rollback()
            print(f"Ocorreu um erro ao alterar a licença: {e}")


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


@app.cli.command("init-license")
def init_license_command():
    with app.app_context():
        license_exists = License.query.first()
        if not license_exists:
            initial_expiration = datetime.utcnow() + timedelta(days=30)
            new_license = License(id=1, expiration_date=initial_expiration)
            db.session.add(new_license)
            db.session.commit()
            print(
                f"Licença inicial criada com sucesso! Expira em: {initial_expiration.strftime('%d/%m/%Y')}"
            )
        else:
            print("A licença já existe no sistema.")


# --- 4. FUNÇÕES GLOBAIS E DECORADORES ---
@app.context_processor
def inject_year():
    return {"current_year": datetime.utcnow().year}


def limpar_cpf(cpf):
    if cpf:
        return re.sub(r"\D", "", cpf)
    return None


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


def check_license(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        allowed_routes = [
            "login",
            "logout",
            "renovar_licenca",
            "admin_licenca",
            "static",
            "uploaded_file",
            "registrar_ponto",
        ]
        if request.endpoint in allowed_routes:
            return f(*args, **kwargs)
        licenca = License.query.first()
        if not licenca or licenca.expiration_date < datetime.utcnow():
            if session.get("role") == "admin":
                return f(*args, **kwargs)
            flash(
                "Sua licença de uso do sistema expirou. Por favor, renove sua assinatura para continuar.",
                "warning",
            )
            return redirect(url_for("renovar_licenca"))
        return f(*args, **kwargs)

    return decorated_function


# app.py


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
                A4[1] - 2.5 * cm,
                width=17 * cm,
                height=2.2 * cm,
                preserveAspectRatio=True,
                mask="auto",
            )

    canvas.restoreState()


# (Aqui vem a função cabecalho_e_rodape_moderno e o resto do seu código...)


def cabecalho_e_rodape_moderno(canvas, doc, titulo_doc="Relatório"):
    """
    Cria um cabeçalho e rodapé com o logo à esquerda e título à direita.
    """
    canvas.saveState()
    cor_principal = colors.HexColor("#004d40")

    # --- Cabeçalho ---
    # Logo da Secretaria no canto superior esquerdo
    image_path = os.path.join(basedir, "static", "timbre.jpg")
    if os.path.exists(image_path):
        from reportlab.lib.utils import ImageReader

        # Lógica para calcular a altura proporcional e não achatar a imagem
        img_reader = ImageReader(image_path)
        img_width, img_height = img_reader.getSize()
        aspect = img_height / float(img_width)

        logo_width = 5 * cm  # Largura desejada do logo
        logo_height = logo_width * aspect  # Altura calculada para manter a proporção

        logo = Image(image_path, width=logo_width, height=logo_height)
        # Posição Y ajustada para o novo tamanho do logo
        logo.drawOn(
            canvas, doc.leftMargin, A4[1] - doc.topMargin + 1.2 * cm - logo_height
        )

    # Título do Documento (agora na cor preta, sem fundo)
    canvas.setFont("Helvetica-Bold", 18)
    canvas.setFillColor(colors.black)
    # Posição ajustada para ficar ao lado do logo
    canvas.drawString(
        doc.leftMargin + logo_width + 0.5 * cm,
        A4[1] - doc.topMargin + 0.8 * cm,
        titulo_doc,
    )

    # --- Rodapé ---
    canvas.setFillColor(cor_principal)
    canvas.rect(
        doc.leftMargin,
        doc.bottomMargin - 0.5 * cm,
        doc.width,
        0.3 * cm,
        fill=1,
        stroke=0,
    )
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawString(
        doc.leftMargin,
        doc.bottomMargin - 0.4 * cm,
        f"SysEduca | Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
    )
    canvas.drawRightString(
        doc.width + doc.leftMargin, doc.bottomMargin - 0.4 * cm, f"Página {doc.page}"
    )

    canvas.restoreState()


# --- 5. ROTAS DA APLICAÇÃO --- (continua o resto do seu código)
# ...
# --- 5. ROTAS DA APLICAÇÃO ---


# ROTAS DE AUTENTICAÇÃO E LICENÇA
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("usuario")
        password = request.form.get("senha")
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            session["logged_in"] = True
            session["username"] = user.username
            session["role"] = user.role
            registrar_log("Fez login no sistema.")
            flash("Login realizado com sucesso!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Usuário ou senha inválidos.", "danger")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    registrar_log("Fez logout do sistema.")
    session.clear()
    flash("Você saiu do sistema.", "info")
    return redirect(url_for("login"))


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


# ROTAS PRINCIPAIS
@app.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/")
@login_required
@check_license
def dashboard():
    total_servidores = db.session.query(func.count(Servidor.num_contrato)).scalar()
    remuneracao_media = db.session.query(func.avg(Servidor.remuneracao)).scalar()
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
    funcao_labels = [item[0] or "Não Especificado" for item in servidores_por_funcao]
    funcao_data = [item[1] for item in servidores_por_funcao]
    lotacao_labels = [item[0] or "Não Especificado" for item in servidores_por_lotacao]
    lotacao_data = [item[1] for item in servidores_por_lotacao]
    hoje = datetime.now().date()
    data_limite = hoje + timedelta(days=60)
    contratos_a_vencer = (
        Servidor.query.filter(
            Servidor.data_saida.isnot(None),
            Servidor.data_saida >= hoje,
            Servidor.data_saida <= data_limite,
        )
        .order_by(Servidor.data_saida.asc())
        .all()
    )
    servidores_incompletos = (
        Servidor.query.filter(
            or_(
                Servidor.cpf == None,
                Servidor.cpf == "",
                Servidor.rg == None,
                Servidor.rg == "",
                Servidor.endereco == None,
                Servidor.endereco == "",
            )
        )
        .order_by(Servidor.nome)
        .all()
    )
    return render_template(
        "dashboard.html",
        total_servidores=total_servidores,
        remuneracao_media=remuneracao_media,
        contratos_a_vencer=contratos_a_vencer,
        funcao_labels=funcao_labels,
        funcao_data=funcao_data,
        lotacao_labels=lotacao_labels,
        lotacao_data=lotacao_data,
        servidores_incompletos=servidores_incompletos,
    )


@app.route("/logs")
@login_required
@admin_required
@check_license
def ver_logs():
    page = request.args.get("page", 1, type=int)
    logs_pagination = Log.query.order_by(Log.timestamp.desc()).paginate(
        page=page, per_page=25, error_out=False
    )
    return render_template("logs.html", logs=logs_pagination)


# ROTAS DE USUÁRIOS
@app.route("/usuarios")
@login_required
@admin_required
@check_license
def lista_usuarios():
    usuarios = User.query.order_by(User.username).all()
    return render_template("usuarios.html", usuarios=usuarios)


@app.route("/usuarios/add", methods=["POST"])
@login_required
@admin_required
@check_license
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
@check_license
def editar_usuario(id):
    user = User.query.get_or_404(id)
    if request.method == "POST":
        if (
            user.role == "admin"
            and User.query.filter_by(role="admin").count() == 1
            and request.form.get("role") == "operador"
        ):
            flash(
                "Não é possível remover o status de administrador do último admin do sistema.",
                "danger",
            )
            return redirect(url_for("editar_usuario", id=id))
        new_username = request.form.get("username")
        user_exists = User.query.filter(
            User.username == new_username, User.id != id
        ).first()
        if user_exists:
            flash("Este nome de usuário já está em uso.", "danger")
            return render_template("editar_usuario.html", user=user)
        user.username = new_username
        user.role = request.form.get("role")
        new_password = request.form.get("password")
        if new_password:
            user.password_hash = bcrypt.generate_password_hash(new_password).decode(
                "utf-8"
            )
        db.session.commit()
        registrar_log(f'Editou o usuário: "{user.username}".')
        flash("Usuário atualizado com sucesso!", "success")
        return redirect(url_for("lista_usuarios"))
    return render_template("editar_usuario.html", user=user)


@app.route("/usuarios/delete/<int:id>")
@login_required
@admin_required
@check_license
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


# ROTAS DO BLOCO DE NOTAS
@app.route("/bloco_de_notas")
@login_required
@check_license
def bloco_de_notas():
    user = User.query.filter_by(username=session["username"]).first_or_404()
    notas = (
        Nota.query.filter_by(user_id=user.id).order_by(Nota.data_criacao.desc()).all()
    )
    return render_template("bloco_de_notas.html", notas=notas)


@app.route("/notas/add", methods=["POST"])
@login_required
@check_license
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
@check_license
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
@check_license
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


# ROTAS DE SERVIDORES
# app.py


@app.route("/servidores")
@login_required
@check_license
def lista_servidores():
    # --- Início da Lógica Original de Busca e Filtro ---
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

    funcoes_disponiveis = [
        r[0]
        for r in db.session.query(Servidor.funcao)
        .distinct()
        .order_by(Servidor.funcao)
        .all()
        if r[0]
    ]
    lotacoes_disponiveis = [
        r[0]
        for r in db.session.query(Servidor.lotacao)
        .distinct()
        .order_by(Servidor.lotacao)
        .all()
        if r[0]
    ]
    # --- Fim da Lógica Original ---

    # --- Início da Nova Lógica para Status de Requerimentos ---
    hoje = datetime.now().date()
    status_servidores = {}

    # Busca todos os requerimentos que foram aprovados e estão atualmente ativos
    requerimentos_ativos = Requerimento.query.filter(
        Requerimento.status == "Aprovado", Requerimento.data_inicio_requerimento <= hoje
    ).all()

    for req in requerimentos_ativos:
        # Verifica se o requerimento ainda está dentro do período de validade (sem data de retorno ou a data de retorno é futura)
        if not req.data_retorno_trabalho or req.data_retorno_trabalho > hoje:
            status_servidores[req.servidor_cpf] = req.natureza
    # --- Fim da Nova Lógica ---

    # O retorno agora inclui o dicionário 'status_servidores' para ser usado no template
    return render_template(
        "index.html",
        servidores=servidores,
        funcoes_disponiveis=funcoes_disponiveis,
        lotacoes_disponiveis=lotacoes_disponiveis,
        status_servidores=status_servidores,
    )


# app.py


@app.route("/add", methods=["POST"])
@login_required
@check_license
def add_server():
    try:
        # Pega a foto, se enviada
        foto = request.files.get("foto")
        foto_filename = None
        if foto and foto.filename != "":
            foto_filename = secure_filename(foto.filename)
            foto.save(os.path.join(app.config["UPLOAD_FOLDER"], foto_filename))

        # Pega as datas do formulário e converte para objeto Date
        data_inicio_str = request.form.get("data_inicio")
        data_saida_str = request.form.get("data_saida")
        data_nascimento_str = request.form.get("data_nascimento")

        data_inicio_obj = (
            datetime.strptime(data_inicio_str, "%Y-%m-%d").date()
            if data_inicio_str
            else None
        )
        data_saida_obj = (
            datetime.strptime(data_saida_str, "%Y-%m-%d").date()
            if data_saida_str
            else None
        )
        data_nascimento_obj = (
            datetime.strptime(data_nascimento_str, "%Y-%m-%d").date()
            if data_nascimento_str
            else None
        )

        # Limpa o CPF e converte a remuneração
        cpf_limpo = limpar_cpf(request.form.get("cpf"))
        remuneracao_str = (
            request.form.get("remuneracao", "0").replace(".", "").replace(",", ".")
        )
        remuneracao_val = float(remuneracao_str) if remuneracao_str else 0.0

        # Cria o novo servidor com TODOS os campos do formulário
        novo_servidor = Servidor(
            num_contrato=request.form.get("num_contrato"),
            nome=request.form.get("nome"),
            cpf=cpf_limpo,
            rg=request.form.get("rg"),
            data_nascimento=data_nascimento_obj,
            nome_mae=request.form.get("nome_mae"),
            email=request.form.get("email"),
            pis_pasep=request.form.get("pis_pasep"),
            tipo_vinculo=request.form.get("tipo_vinculo"),
            local_trabalho=request.form.get("local_trabalho"),
            classe_nivel=request.form.get("classe_nivel"),
            num_contra_cheque=request.form.get("num_contra_cheque"),
            nacionalidade=request.form.get("nacionalidade"),
            estado_civil=request.form.get("estado_civil"),
            telefone=request.form.get("telefone"),
            endereco=request.form.get("endereco"),
            funcao=request.form.get("funcao"),
            lotacao=request.form.get("lotacao"),
            carga_horaria=request.form.get("carga_horaria"),
            remuneracao=remuneracao_val,
            dados_bancarios=request.form.get("dados_bancarios"),
            data_inicio=data_inicio_obj,
            data_saida=data_saida_obj,
            observacoes=request.form.get("observacoes"),
            foto_filename=foto_filename,
        )
        db.session.add(novo_servidor)
        db.session.commit()
        registrar_log(
            f'Cadastrou o servidor: "{novo_servidor.nome}" (Vínculo: {novo_servidor.num_contrato}).'
        )
        flash("Servidor cadastrado com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        registrar_log(f"Falha ao tentar cadastrar servidor. Erro: {e}")
        flash(f"Erro ao cadastrar servidor: {e}", "danger")
    return redirect(url_for("lista_servidores"))


@app.route("/editar/<path:id>", methods=["GET", "POST"])
@login_required
@check_license
def editar_servidor(id):
    servidor = Servidor.query.get_or_404(id)
    if request.method == "POST":
        try:
            foto = request.files.get("foto")
            if foto and foto.filename != "":
                if servidor.foto_filename and os.path.exists(
                    os.path.join(app.config["UPLOAD_FOLDER"], servidor.foto_filename)
                ):
                    os.remove(
                        os.path.join(
                            app.config["UPLOAD_FOLDER"], servidor.foto_filename
                        )
                    )
                foto_filename = secure_filename(foto.filename)
                foto.save(os.path.join(app.config["UPLOAD_FOLDER"], foto_filename))
                servidor.foto_filename = foto_filename
            data_inicio_str = request.form.get("data_inicio")
            data_saida_str = request.form.get("data_saida")
            servidor.data_inicio = (
                datetime.strptime(data_inicio_str, "%Y-%m-%d").date()
                if data_inicio_str
                else None
            )
            servidor.data_saida = (
                datetime.strptime(data_saida_str, "%Y-%m-%d").date()
                if data_saida_str
                else None
            )
            remuneracao_str = (
                request.form.get("remuneracao", "0").replace(".", "").replace(",", ".")
            )
            servidor.remuneracao = float(remuneracao_str) if remuneracao_str else 0.0
            servidor.nome = request.form.get("nome")
            servidor.cpf = limpar_cpf(request.form.get("cpf"))
            servidor.rg = request.form.get("rg")
            servidor.nome_mae = request.form.get("nome_mae")
            servidor.email = request.form.get("email")
            servidor.pis_pasep = request.form.get("pis_pasep")
            servidor.tipo_vinculo = request.form.get("tipo_vinculo")
            servidor.local_trabalho = request.form.get("local_trabalho")
            servidor.classe_nivel = request.form.get("classe_nivel")
            servidor.num_contra_cheque = request.form.get("num_contra_cheque")
            servidor.nacionalidade = request.form.get("nacionalidade")
            servidor.estado_civil = request.form.get("estado_civil")
            servidor.telefone = request.form.get("telefone")
            servidor.endereco = request.form.get("endereco")
            servidor.funcao = request.form.get("funcao")
            servidor.lotacao = request.form.get("lotacao")
            servidor.carga_horaria = request.form.get("carga_horaria")
            servidor.dados_bancarios = request.form.get("dados_bancarios")
            servidor.observacoes = request.form.get("observacoes")
            db.session.commit()
            registrar_log(f'Atualizou os dados do servidor: "{servidor.nome}".')
            flash("Dados do servidor atualizados com sucesso!", "success")
            return redirect(url_for("lista_servidores"))
        except Exception as e:
            db.session.rollback()
            registrar_log(
                f'Falha ao tentar atualizar o servidor "{servidor.nome}". Erro: {e}'
            )
            flash(f"Erro ao atualizar servidor: {e}", "danger")
            return redirect(url_for("editar_servidor", id=id))
    return render_template("editar.html", servidor=servidor)


@app.route("/delete/<path:id>")
@login_required
@admin_required
@check_license
def delete_server(id):
    servidor = Servidor.query.get_or_404(id)

    # --- LÓGICA DE VERIFICAÇÃO ABRANGENTE ---
    dependencias = []
    if servidor.contratos:
        dependencias.append("contratos")
    if servidor.abastecimentos:
        dependencias.append("registros de abastecimento")
    if servidor.requerimentos:
        dependencias.append("requerimentos")
    if servidor.pontos:
        dependencias.append("registros de ponto")
    if servidor.rotas_como_motorista:
        dependencias.append("rotas de transporte (como motorista)")
    if servidor.rotas_como_monitor:
        dependencias.append("rotas de transporte (como monitor)")

    # Se a lista de dependências não estiver vazia, impede a exclusão
    if dependencias:
        # Formata a lista de dependências para uma string legível
        dependencias_str = ", ".join(dependencias)
        flash(
            f'Não é possível excluir o servidor "{servidor.nome}", pois ele possui vínculos com: {dependencias_str}.',
            "danger",
        )
        return redirect(url_for("lista_servidores"))
    # --- FIM DA VERIFICAÇÃO ---

    nome_servidor = servidor.nome
    try:
        # Esta parte agora só será executada se o servidor não tiver nenhuma dependência
        if servidor.foto_filename and os.path.exists(
            os.path.join(app.config["UPLOAD_FOLDER"], servidor.foto_filename)
        ):
            os.remove(os.path.join(app.config["UPLOAD_FOLDER"], servidor.foto_filename))
        for doc in servidor.documentos:
            doc_path = os.path.join(
                app.config["UPLOAD_FOLDER"], "documentos", doc.filename
            )
            if os.path.exists(doc_path):
                os.remove(doc_path)

        db.session.delete(servidor)
        db.session.commit()

        registrar_log(f'Excluiu o servidor: "{nome_servidor}".')
        flash(f'Servidor "{nome_servidor}" excluído com sucesso!', "success")

    except Exception as e:
        db.session.rollback()
        registrar_log(
            f'Falha ao tentar excluir o servidor "{nome_servidor}". Erro: {e}'
        )
        flash(f"Ocorreu um erro inesperado ao tentar excluir o servidor: {e}", "danger")

    return redirect(url_for("lista_servidores"))


@app.route("/requerimentos")
@login_required
@check_license
def listar_requerimentos():
    # Ordena por data de criação, dos mais novos para os mais antigos
    requerimentos = Requerimento.query.order_by(Requerimento.data_criacao.desc()).all()
    return render_template("requerimentos.html", requerimentos=requerimentos)

    # app.py


# ... (outras rotas) ...


@app.route("/requerimentos/novo", methods=["GET", "POST"])
@login_required
@check_license
def novo_requerimento():
    if request.method == "POST":
        try:
            # Pega o CPF do campo de busca e limpa
            cpf_servidor = limpar_cpf(request.form.get("cpf_busca"))
            if not cpf_servidor:
                flash("O CPF do servidor é obrigatório.", "danger")
                return redirect(url_for("novo_requerimento"))

            # Verifica se o servidor existe
            servidor = Servidor.query.filter_by(cpf=cpf_servidor).first()
            if not servidor:
                flash("Servidor com o CPF informado não encontrado.", "danger")
                return redirect(url_for("novo_requerimento"))

            # Cria a nova instância do Requerimento
            novo_req = Requerimento(
                autoridade_dirigida=request.form.get("autoridade_dirigida"),
                servidor_cpf=cpf_servidor,
                natureza=request.form.get("natureza"),
                natureza_outro=request.form.get("natureza_outro"),
                data_admissao=(
                    datetime.strptime(
                        request.form.get("data_admissao"), "%Y-%m-%d"
                    ).date()
                    if request.form.get("data_admissao")
                    else None
                ),
                data_inicio_requerimento=datetime.strptime(
                    request.form.get("data_inicio_requerimento"), "%Y-%m-%d"
                ).date(),
                duracao=request.form.get("duracao"),
                periodo_aquisitivo=request.form.get("periodo_aquisitivo"),
                informacoes_complementares=request.form.get(
                    "informacoes_complementares"
                ),
                parecer_juridico=request.form.get("parecer_juridico"),
                status="Em Análise",  # Status inicial padrão
            )

            db.session.add(novo_req)
            db.session.commit()

            registrar_log(
                f"Criou novo requerimento (ID: {novo_req.id}) para o servidor {servidor.nome}."
            )
            flash("Requerimento criado com sucesso!", "success")
            return redirect(url_for("listar_requerimentos"))

        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao criar requerimento: {e}", "danger")
            return redirect(url_for("novo_requerimento"))

    # Se for um GET, apenas exibe o formulário
    return render_template("requerimento_form.html")

    # Adicione este código em app.py


@app.route("/requerimentos/editar/<int:req_id>", methods=["GET", "POST"])
@login_required
@check_license
def editar_requerimento(req_id):
    req = Requerimento.query.get_or_404(req_id)
    if request.method == "POST":
        try:
            # Atualiza os campos do requerimento com os dados do formulário
            req.autoridade_dirigida = request.form.get("autoridade_dirigida")
            req.natureza = request.form.get("natureza")
            req.natureza_outro = (
                request.form.get("natureza_outro") if req.natureza == "Outro" else None
            )
            req.data_admissao = (
                datetime.strptime(request.form.get("data_admissao"), "%Y-%m-%d").date()
                if request.form.get("data_admissao")
                else None
            )
            req.data_inicio_requerimento = datetime.strptime(
                request.form.get("data_inicio_requerimento"), "%Y-%m-%d"
            ).date()
            req.duracao = request.form.get("duracao")
            req.periodo_aquisitivo = request.form.get("periodo_aquisitivo")
            req.informacoes_complementares = request.form.get(
                "informacoes_complementares"
            )
            req.parecer_juridico = request.form.get("parecer_juridico")

            db.session.commit()

            registrar_log(
                f"Editou o requerimento ID {req.id} para o servidor {req.servidor.nome}."
            )
            flash("Requerimento atualizado com sucesso!", "success")
            return redirect(url_for("listar_requerimentos"))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao atualizar o requerimento: {e}", "danger")
            return redirect(url_for("editar_requerimento", req_id=req_id))

    # Método GET: apenas exibe o formulário preenchido
    return render_template("editar_requerimento.html", requerimento=req)


# app.py

# ... (adicionar após a rota novo_requerimento) ...


# Rota para exibir e salvar a edição de um requerimento
@app.route("/requerimentos/mudar-status-modal", methods=["POST"])
@login_required
@check_license
def mudar_status_requerimento_modal():
    try:
        req_id = request.form.get("req_id", type=int)
        novo_status = request.form.get("novo_status")

        if not req_id or not novo_status:
            flash("Dados inválidos para alterar o status.", "danger")
            return redirect(url_for("listar_requerimentos"))

        req = Requerimento.query.get_or_404(req_id)

        # Validação do status
        status_permitidos = ["Aprovado", "Recusado", "Concluído", "Em Análise"]
        if novo_status not in status_permitidos:
            flash("Status inválido.", "danger")
            return redirect(url_for("listar_requerimentos"))

        # Atualiza o status e a data de conclusão
        req.status = novo_status
        if novo_status in ["Aprovado", "Recusado", "Concluído"]:
            req.data_conclusao = datetime.now().date()
        else:
            req.data_conclusao = None

        db.session.commit()
        registrar_log(
            f'Alterou o status do requerimento ID {req.id} para "{novo_status}".'
        )
        flash(
            f'Status do requerimento #{req.id} alterado para "{novo_status}" com sucesso!',
            "info",
        )

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao alterar status: {e}", "danger")

    return redirect(url_for("listar_requerimentos"))

    # Método GET: apenas exibe o formulário preenchido
    return render_template("editar_requerimento.html", requerimento=req)


# Rota para mudar o status do requerimento
@app.route("/requerimentos/mudar-status/<int:req_id>/<string:novo_status>")
@login_required
@check_license
def mudar_status_requerimento(req_id, novo_status):
    req = Requerimento.query.get_or_404(req_id)
    # Valida se o status recebido é um dos esperados
    status_permitidos = ["Aprovado", "Recusado", "Concluído", "Em Análise"]
    if novo_status not in status_permitidos:
        flash("Status inválido.", "danger")
        return redirect(url_for("listar_requerimentos"))

    try:
        req.status = novo_status
        # Se o status for final, registra a data. Se voltar para "Em Análise", limpa a data.
        if novo_status in ["Aprovado", "Recusado", "Concluído"]:
            req.data_conclusao = datetime.now().date()
        else:
            req.data_conclusao = None

        db.session.commit()
        registrar_log(
            f'Alterou o status do requerimento ID {req.id} para "{novo_status}".'
        )
        flash(
            f'Status do requerimento #{req.id} alterado para "{novo_status}" com sucesso!',
            "info",
        )
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao alterar status: {e}", "danger")

    return redirect(url_for("listar_requerimentos"))


@app.route("/requerimento/pdf/<int:req_id>")
@login_required
@check_license
def gerar_requerimento_pdf(req_id):
    requerimento = Requerimento.query.get_or_404(req_id)
    servidor = requerimento.servidor

    buffer = io.BytesIO()
    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=4 * cm,
        bottomMargin=2.5 * cm,
    )

    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    template = PageTemplate(
        id="main_template",
        frames=[frame],
        onPage=lambda canvas, doc: cabecalho_e_rodape_moderno(
            canvas, doc, "Requerimento Funcional"
        ),
    )
    doc.addPageTemplates([template])

    styles = getSampleStyleSheet()

    # --- ESTILO DOS RÓTULOS COM FUNDO VERDE ---
    label_style = ParagraphStyle(
        name="LabelHeader",
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=colors.white,  # Texto na cor branca
        backColor=colors.HexColor("#004d40"),  # Fundo na cor verde
        alignment=TA_CENTER,  # Alinhamento à esquerda para um visual limpo
        paddingLeft=4,
        paddingTop=3,
        paddingBottom=3,
    )
    # Estilo dos dados volta ao normal, sem negrito e alinhado à esquerda
    data_style = ParagraphStyle(
        name="Data",
        fontName="Helvetica",
        fontSize=10,
        alignment=TA_LEFT,
        leftIndent=20,
        spaceBefore=6,
    )

    story = []

    # Estilo da grade
    box_grid_style = TableStyle(
        [
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]
    )

    # Função auxiliar para criar o conteúdo da célula
    def criar_celula(label, data):
        return [Paragraph(label, label_style), Paragraph(data or " ", data_style)]

    # Montagem do formulário com as correções
    tabela1 = Table(
        [
            [
                criar_celula(
                    "AUTORIDADE A QUEM É DIRIGIDA", requerimento.autoridade_dirigida
                )
            ]
        ],
        colWidths=[18 * cm],
    )
    tabela2 = Table(
        [[criar_celula("NOME COMPLETO DO(A) SERVIDOR(A)", servidor.nome)]],
        colWidths=[18 * cm],
    )

    data_nasc = (
        servidor.data_nascimento.strftime("%d/%m/%Y")
        if servidor.data_nascimento
        else " "
    )
    tabela3 = Table(
        [
            [
                criar_celula("CARGO/FUNÇÃO", servidor.funcao),
                criar_celula("CLASSE/NÍVEL", servidor.classe_nivel),
                criar_celula("DATA DE NASCIMENTO", data_nasc),
            ]
        ],
        colWidths=[6 * cm, 6 * cm, 6 * cm],
    )

    data_adm = (
        requerimento.data_admissao.strftime("%d/%m/%Y")
        if requerimento.data_admissao
        else " "
    )
    tabela4 = Table(
        [
            [
                criar_celula("DATA DE ADMISSÃO", data_adm),
                criar_celula("LOTAÇÃO", servidor.lotacao),
                criar_celula("Nº DE CONTRA CHEQUE", servidor.num_contra_cheque),
                criar_celula("TELEFONE", servidor.telefone),
            ]
        ],
        colWidths=[4.5 * cm, 4.5 * cm, 4.5 * cm, 4.5 * cm],
    )

    tabela5 = Table(
        [
            [
                criar_celula("LOCAL DE TRABALHO", servidor.local_trabalho),
                criar_celula("ENDEREÇO RESIDENCIAL", servidor.endereco),
            ]
        ],
        colWidths=[9 * cm, 9 * cm],
    )

    natureza_req = (
        requerimento.natureza_outro
        if requerimento.natureza == "Outro"
        else requerimento.natureza
    )
    data_inicio_req = (
        requerimento.data_inicio_requerimento.strftime("%d/%m/%Y")
        if requerimento.data_inicio_requerimento
        else " "
    )
    tabela6 = Table(
        [
            [
                criar_celula("NATUREZA DO REQUERIMENTO", natureza_req),
                criar_celula("INÍCIO", data_inicio_req),
                criar_celula("PERÍODO DE AQUISIÇÃO", requerimento.periodo_aquisitivo),
            ]
        ],
        colWidths=[9 * cm, 4.5 * cm, 4.5 * cm],
    )

    tabela7 = Table(
        [
            [
                criar_celula(
                    "INFORMAÇÕES COMPLEMENTARES",
                    requerimento.informacoes_complementares,
                ),
                criar_celula("PARECER JURÍDICO", requerimento.parecer_juridico),
            ]
        ],
        colWidths=[9 * cm, 9 * cm],
        rowHeights=4 * cm,
    )

    tabela8 = Table(
        [[[Paragraph("ASSINATURA DO REQUERENTE", label_style)]]],
        colWidths=[18 * cm],
        rowHeights=2 * cm,
    )

    tabela9 = Table(
        [
            [
                [
                    Paragraph("SETOR DE RECURSOS HUMANOS", label_style),
                    Spacer(1, 1 * cm),
                    Paragraph("ASSINATURA E CARIMBO", styles["Normal"]),
                ],
                [
                    Paragraph("CHEFE IMEDIATO DO SETOR", label_style),
                    Spacer(1, 1 * cm),
                    Paragraph("ASSINATURA", styles["Normal"]),
                ],
            ]
        ],
        colWidths=[9 * cm, 9 * cm],
        rowHeights=2.5 * cm,
    )

    for t in [
        tabela1,
        tabela2,
        tabela3,
        tabela4,
        tabela5,
        tabela6,
        tabela7,
        tabela8,
        tabela9,
    ]:
        t.setStyle(box_grid_style)
        story.append(t)
        story.append(Spacer(1, 0.2 * cm))

    liberado_check = "☐"
    nao_liberado_check = "☐"
    liberacao_style = ParagraphStyle(
        name="Liberacao", fontName="Helvetica", fontSize=10, alignment=TA_LEFT
    )
    tabela10 = Table(
        [
            [
                Paragraph(f"{liberado_check} SERVIDOR LIBERADO", liberacao_style),
                Paragraph(
                    f"{nao_liberado_check} SERVIDOR NÃO LIBERADO", liberacao_style
                ),
            ]
        ],
        colWidths=[9 * cm, 9 * cm],
    )
    story.append(tabela10)

    doc.build(story)

    buffer.seek(0)
    response = make_response(buffer.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    nome_arquivo = (
        f'Requerimento_{requerimento.id}_{servidor.nome.replace(" ", "_")}.pdf'
    )
    response.headers["Content-Disposition"] = f"inline; filename={nome_arquivo}"

    registrar_log(
        f'Gerou o PDF do requerimento ID {req_id} para o servidor "{servidor.nome}".'
    )

    return response


@app.route("/api/servidor/<string:cpf>")
@login_required
def get_servidor_data(cpf):
    cpf_limpo = limpar_cpf(cpf)
    servidor = Servidor.query.filter_by(cpf=cpf_limpo).first()

    if not servidor:
        return jsonify({"error": "Servidor não encontrado"}), 404

    # Validação do vínculo do servidor
    if servidor.tipo_vinculo != "Servidor Efetivo":
        return (
            jsonify(
                {
                    "error": f"Requerimentos disponíveis apenas para Servidores Efetivos. Vínculo atual: {servidor.tipo_vinculo}"
                }
            ),
            403,
        )

    servidor_data = {
        "nome": servidor.nome,
        "funcao": servidor.funcao,
        "classe_nivel": servidor.classe_nivel,
        "data_nascimento": (
            servidor.data_nascimento.strftime("%d/%m/%Y")
            if servidor.data_nascimento
            else ""
        ),
        "data_admissao": (
            servidor.data_inicio.strftime("%Y-%m-%d") if servidor.data_inicio else ""
        ),  # data_inicio é a data de admissão
        "lotacao": servidor.lotacao,
        "num_contra_cheque": servidor.num_contra_cheque,
        "telefone": servidor.telefone,
        "local_trabalho": servidor.local_trabalho,
        "endereco": servidor.endereco,
    }
    return jsonify(servidor_data)


# ROTAS DE VEÍCULOS E COMBUSTÍVEL
@app.route("/veiculos", methods=["GET", "POST"])
@login_required
@fleet_required
@check_license
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
            ano_fabricacao=int(request.form.get("ano_fabricacao") or 0),
            ano_modelo=int(request.form.get("ano_modelo") or 0),
            orgao=request.form.get("orgao"),
            autorizacao_detran=request.form.get("autorizacao_detran") or None,
            validade_autorizacao=(
                datetime.strptime(
                    request.form.get("validade_autorizacao"), "%Y-%m-%d"
                ).date()
                if request.form.get("validade_autorizacao")
                else None
            ),
            renavam=request.form.get("renavam")
            or None,  # <-- Argumento duplicado foi removido daqui
            certificado_tacografo=request.form.get("certificado_tacografo") or None,
            data_emissao_tacografo=(
                datetime.strptime(
                    request.form.get("data_emissao_tacografo"), "%Y-%m-%d"
                ).date()
                if request.form.get("data_emissao_tacografo")
                else None
            ),
            validade_tacografo=(
                datetime.strptime(
                    request.form.get("validade_tacografo"), "%Y-%m-%d"
                ).date()
                if request.form.get("validade_tacografo")
                else None
            ),
        )
        db.session.add(novo_veiculo)
        db.session.commit()
        registrar_log(
            f"Cadastrou o veículo: Placa {novo_veiculo.placa}, Modelo {novo_veiculo.modelo}."
        )
        flash("Veículo cadastrado com sucesso!", "success")
        return redirect(url_for("gerenciar_veiculos"))

    hoje = datetime.now().date()
    data_limite = hoje + timedelta(days=30)

    veiculos_com_alerta = (
        Veiculo.query.filter(
            or_(
                and_(
                    Veiculo.validade_tacografo != None,
                    Veiculo.validade_tacografo <= data_limite,
                ),
                and_(
                    Veiculo.validade_autorizacao != None,
                    Veiculo.validade_autorizacao <= data_limite,
                ),
            )
        )
        .order_by(Veiculo.modelo)
        .all()
    )

    veiculos = Veiculo.query.order_by(Veiculo.modelo).all()

    return render_template(
        "veiculos.html",
        veiculos=veiculos,
        veiculos_com_alerta=veiculos_com_alerta,
        hoje=hoje,
        data_limite=data_limite,
    )


@app.route("/veiculos/excluir/<path:placa>")
@login_required
@fleet_required
@check_license
def excluir_veiculo(placa):
    veiculo = Veiculo.query.get_or_404(placa)
    try:
        db.session.delete(veiculo)
        db.session.commit()
        registrar_log(f"Excluiu o veículo: Placa {veiculo.placa}.")
        flash(
            "Veículo e seus registros de abastecimento foram excluídos com sucesso!",
            "success",
        )
    except Exception as e:
        db.session.rollback()
        flash(f"Não foi possível excluir o veículo. Erro: {e}", "danger")
    return redirect(url_for("gerenciar_veiculos"))


# app.py


@app.route("/veiculo/<string:placa>/detalhes")
@login_required
@check_license
def detalhes_veiculo(placa):
    veiculo = Veiculo.query.get_or_404(placa)
    abastecimentos = (
        Abastecimento.query.filter_by(veiculo_placa=placa)
        .order_by(Abastecimento.quilometragem.asc())
        .all()
    )
    # Busca o histórico de manutenções
    manutencoes = (
        Manutencao.query.filter_by(veiculo_placa=placa)
        .order_by(Manutencao.data.desc())
        .all()
    )

    # Cálculos dos Indicadores
    indicadores = {
        "gasto_combustivel": sum(a.valor_total for a in abastecimentos),
        "gasto_manutencao": sum(m.custo for m in manutencoes),
        "total_litros": sum(a.litros for a in abastecimentos),
        "total_km_rodado": 0,
        "consumo_medio_geral": 0,
        "custo_medio_km": 0,
    }
    indicadores["gasto_total"] = (
        indicadores["gasto_combustivel"] + indicadores["gasto_manutencao"]
    )

    chart_labels = []
    chart_consumo_data = []
    chart_custo_km_data = []
    abastecimentos_com_analise = []

    if len(abastecimentos) > 1:
        indicadores["total_km_rodado"] = (
            abastecimentos[-1].quilometragem - abastecimentos[0].quilometragem
        )
        if indicadores["total_km_rodado"] > 0:
            litros_para_media = sum(a.litros for a in abastecimentos[:-1])
            if litros_para_media > 0:
                indicadores["consumo_medio_geral"] = (
                    indicadores["total_km_rodado"] / litros_para_media
                )
            if indicadores["gasto_total"] > 0:
                indicadores["custo_medio_km"] = (
                    indicadores["gasto_total"] / indicadores["total_km_rodado"]
                )

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

    return render_template(
        "detalhes_veiculo.html",
        veiculo=veiculo,
        indicadores=indicadores,
        abastecimentos_com_analise=abastecimentos_com_analise,
        manutencoes=manutencoes,  # Envia o histórico de manutenções
        chart_labels=chart_labels,
        chart_consumo_data=chart_consumo_data,
        chart_custo_km_data=chart_custo_km_data,
    )

    # app.py


@app.route("/veiculo/<string:placa>/manutencao/add", methods=["POST"])
@login_required
@check_license
def add_manutencao(placa):
    veiculo = Veiculo.query.get_or_404(placa)
    try:
        data = datetime.strptime(request.form.get("data_manutencao"), "%Y-%m-%d").date()
        quilometragem = float(
            request.form.get("km_manutencao").replace(".", "").replace(",", ".")
        )
        custo = float(request.form.get("custo_manutencao").replace(",", "."))

        nova_manutencao = Manutencao(
            data=data,
            quilometragem=quilometragem,
            tipo_servico=request.form.get("tipo_servico"),
            custo=custo,
            descricao=request.form.get("descricao"),
            oficina=request.form.get("oficina"),
            veiculo_placa=placa,
        )
        db.session.add(nova_manutencao)
        db.session.commit()
        registrar_log(f"Registrou manutenção de R${custo} para o veículo {placa}.")
        flash("Registro de manutenção salvo com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao salvar manutenção: {e}", "danger")

    return redirect(url_for("detalhes_veiculo", placa=placa))


@app.route("/manutencao/excluir/<int:id>")
@login_required
@fleet_required
@check_license
def excluir_manutencao(id):
    manutencao = Manutencao.query.get_or_404(id)
    placa_veiculo = manutencao.veiculo_placa
    try:
        db.session.delete(manutencao)
        db.session.commit()
        registrar_log(
            f"Excluiu registro de manutenção ID {id} do veículo {placa_veiculo}."
        )
        flash("Registro de manutenção excluído com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir registro: {e}", "danger")

    return redirect(url_for("detalhes_veiculo", placa=placa_veiculo))


@app.route("/combustivel", methods=["GET", "POST"])
@login_required
@check_license
def lancar_abastecimento():
    if request.method == "POST":
        try:
            # Pegando os valores como string primeiro
            litros_str = request.form.get("litros", "").strip().replace(",", ".")
            valor_litro_str = (
                request.form.get("valor_litro", "").strip().replace(",", ".")
            )

            # --- LINHA FALTANTE ADICIONADA AQUI ---
            quilometragem_str = (
                request.form.get("quilometragem", "").strip().replace(",", ".")
            )

            # Convertendo para float, tratando o caso de string vazia
            litros = float(litros_str) if litros_str else 0.0
            valor_litro = float(valor_litro_str) if valor_litro_str else 0.0

            # --- CONVERSÃO DA QUILOMETRAGEM ADICIONADA AQUI ---
            # Use int() se a quilometragem for sempre um número inteiro
            quilometragem_val = int(quilometragem_str) if quilometragem_str else 0

            # Calcula o valor total
            valor_total = litros * valor_litro

            novo_abastecimento = Abastecimento(
                veiculo_placa=request.form.get("veiculo_placa"),
                motorista_id=request.form.get("motorista_id"),
                # --- AGORA A VARIÁVEL EXISTE E O CÓDIGO FUNCIONA ---
                quilometragem=quilometragem_val,
                tipo_combustivel=request.form.get("tipo_combustivel"),
                litros=litros,
                valor_litro=valor_litro,
                valor_total=valor_total,
            )
            db.session.add(novo_abastecimento)
            db.session.commit()
            registrar_log(
                f"Lançou abastecimento de {litros}L para o veículo {novo_abastecimento.veiculo_placa}."
            )
            flash("Abastecimento registrado com sucesso!", "success")

            return redirect(
                url_for("lancar_abastecimento")
            )  # Mover redirect para dentro do try/if

        except (ValueError, TypeError):
            db.session.rollback()
            flash(
                "Erro: valores numéricos inválidos (litros, valor, quilometragem). Verifique se os campos estão preenchidos corretamente.",
                "danger",
            )
            registrar_log("Falha ao lançar abastecimento: erro de conversão de valor.")
            # Quando dá erro, é melhor redirecionar também para limpar o formulário
            return redirect(url_for("lancar_abastecimento"))

    # Esta parte (GET request) continua igual
    veiculos = Veiculo.query.order_by(Veiculo.modelo).all()
    motoristas = Motorista.query.order_by(Motorista.nome).all()
    abastecimentos = (
        Abastecimento.query.order_by(Abastecimento.data.desc()).limit(15).all()
    )

    return render_template(
        "combustivel.html",
        veiculos=veiculos,
        motoristas=motoristas,
        abastecimentos=abastecimentos,
    )


@app.route("/combustivel/excluir/<int:id>")
@login_required
@fleet_required
@check_license
def excluir_abastecimento(id):
    # Procura o registro de abastecimento pelo ID. Se não encontrar, retorna erro 404.
    abastecimento_para_excluir = Abastecimento.query.get_or_404(id)

    try:
        # Guarda informações para o log antes de deletar
        info_log = f"veículo placa {abastecimento_para_excluir.veiculo_placa}, {abastecimento_para_excluir.litros}L em {abastecimento_para_excluir.data.strftime('%d/%m/%Y')}"

        # Deleta o objeto do banco de dados
        db.session.delete(abastecimento_para_excluir)

        # Confirma a transação
        db.session.commit()

        # Registra a ação no log
        registrar_log(f"Excluiu o registro de abastecimento: {info_log}.")
        flash("Registro de abastecimento excluído com sucesso!", "success")

    except Exception as e:
        # Em caso de erro, desfaz a transação
        db.session.rollback()
        flash(f"Erro ao excluir o registro: {e}", "danger")

    # Redireciona de volta para a página principal de abastecimentos
    return redirect(url_for("lancar_abastecimento"))


@app.route("/combustivel/relatorio/mensal/selecionar")
@login_required
@fleet_required
@check_license
def pagina_relatorio_mensal():
    return render_template("relatorio_mensal.html")


# app.py


@app.route("/combustivel/relatorio", methods=["GET"])
@login_required
@fleet_required
@check_license
def relatorio_combustivel():
    # Coleta os filtros da URL
    dia_str = request.args.get("dia")
    mes_str = request.args.get("mes")
    ano_str = request.args.get("ano")
    placa_filtro = request.args.get("placa")

    # Prepara a query inicial, ordenando para que os cálculos possam ser feitos em sequência
    query = (
        db.session.query(Abastecimento)
        .join(Veiculo)
        .order_by(Abastecimento.veiculo_placa, Abastecimento.quilometragem)
    )

    # Aplica o filtro de placa se existir
    if placa_filtro:
        query = query.filter(Veiculo.placa == placa_filtro)

    # Lógica de filtro por data
    if ano_str and ano_str.strip():
        try:
            ano = int(ano_str)
            data_inicio, data_fim = None, None
            if dia_str and dia_str.strip() and mes_str and mes_str.strip():
                mes, dia = int(mes_str), int(dia_str)
                data_inicio = datetime(ano, mes, dia)
                data_fim = data_inicio + timedelta(days=1)
            elif mes_str and mes_str.strip():
                mes = int(mes_str)
                data_inicio = datetime(ano, mes, 1)
                data_fim = (
                    datetime(ano, mes + 1, 1) if mes < 12 else datetime(ano + 1, 1, 1)
                )
            else:
                data_inicio = datetime(ano, 1, 1)
                data_fim = datetime(ano + 1, 1, 1)

            if data_inicio and data_fim:
                query = query.filter(
                    Abastecimento.data >= data_inicio, Abastecimento.data < data_fim
                )
        except (ValueError, TypeError):
            flash("Data inválida para o filtro.", "danger")
            return redirect(url_for("relatorio_combustivel"))

    # Executa a query
    resultados_filtrados = query.all()

    # --- INÍCIO DA NOVA LÓGICA DE CÁLCULO DE INDICADORES ---
    resultados_com_analise = []
    ultimo_abastecimento = (
        {}
    )  # Dicionário para guardar o último registro de cada veículo

    for r in resultados_filtrados:
        placa = r.veiculo_placa
        analise = {"abastecimento": r, "km_rodado": 0, "consumo_kml": 0, "custo_km": 0}

        # Verifica se já temos um registro anterior para este veículo
        if placa in ultimo_abastecimento:
            anterior = ultimo_abastecimento[placa]

            # Calcula a distância percorrida
            km_rodado = r.quilometragem - anterior.quilometragem
            analise["km_rodado"] = km_rodado

            # Evita divisão por zero e resultados ilógicos
            if km_rodado > 0 and anterior.litros > 0:
                # O consumo é calculado com base nos litros do abastecimento ANTERIOR
                consumo = km_rodado / anterior.litros
                analise["consumo_kml"] = consumo

                # O custo por KM é baseado no valor do abastecimento ANTERIOR
                custo_km = anterior.valor_total / km_rodado
                analise["custo_km"] = custo_km

        resultados_com_analise.append(analise)
        # Atualiza o último abastecimento para o atual, para ser usado no próximo cálculo
        ultimo_abastecimento[placa] = r
    # --- FIM DA NOVA LÓGICA DE CÁLCULO ---

    # Busca todos os veículos para popular o filtro da página
    veiculos = Veiculo.query.order_by(Veiculo.modelo).all()

    return render_template(
        "relatorio_combustivel.html",
        resultados=resultados_com_analise,
        veiculos=veiculos,
    )


# app.py


@app.route("/combustivel/relatorio/pdf/filtrado")
@login_required
@fleet_required
@check_license
def exportar_combustivel_pdf():
    # Coleta os filtros da URL
    dia_str = request.args.get("dia")
    mes_str = request.args.get("mes")
    ano_str = request.args.get("ano")
    placa_filtro = request.args.get("placa")

    # Prepara a query inicial, ordenando para os cálculos
    query = (
        db.session.query(Abastecimento)
        .join(Veiculo)
        .order_by(Abastecimento.veiculo_placa, Abastecimento.quilometragem)
    )

    # Aplica o filtro de placa se existir
    if placa_filtro:
        query = query.filter(Veiculo.placa == placa_filtro)

    # Lógica de filtro por data
    if ano_str and ano_str.strip():
        try:
            ano = int(ano_str)
            data_inicio, data_fim = None, None
            if dia_str and dia_str.strip() and mes_str and mes_str.strip():
                mes, dia = int(mes_str), int(dia_str)
                data_inicio = datetime(ano, mes, dia)
                data_fim = data_inicio + timedelta(days=1)
            elif mes_str and mes_str.strip():
                mes = int(mes_str)
                data_inicio = datetime(ano, mes, 1)
                data_fim = (
                    datetime(ano, mes + 1, 1) if mes < 12 else datetime(ano + 1, 1, 1)
                )
            else:
                data_inicio = datetime(ano, 1, 1)
                data_fim = datetime(ano + 1, 1, 1)

            if data_inicio and data_fim:
                query = query.filter(
                    Abastecimento.data >= data_inicio, Abastecimento.data < data_fim
                )
        except (ValueError, TypeError):
            flash("Data inválida para o filtro.", "danger")
            return redirect(url_for("relatorio_combustivel"))

    resultados_filtrados = query.all()

    # --- INÍCIO DA LÓGICA DE CÁLCULO (IDÊNTICA À DO RELATÓRIO HTML) ---
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
    # --- FIM DA LÓGICA DE CÁLCULO ---

    # Envia os dados já calculados para a função que desenha o PDF
    return gerar_pdf_combustivel(
        resultados_com_analise, "Relatório de Abastecimento e Consumo"
    )


@app.route("/combustivel/relatorio/pdf/mes_atual")
@login_required
@fleet_required
@check_license
def relatorio_combustivel_mensal_pdf():
    hoje = datetime.now()
    ano, mes = hoje.year, hoje.month
    data_inicio = datetime(ano, mes, 1)
    data_fim = datetime(ano, mes + 1, 1) if mes < 12 else datetime(ano + 1, 1, 1)

    resultados = (
        Abastecimento.query.filter(
            Abastecimento.data >= data_inicio, Abastecimento.data < data_fim
        )
        .order_by(Abastecimento.data.asc())
        .all()
    )

    return gerar_pdf_combustivel(
        resultados, f"Relatório de Abastecimento - {hoje.strftime('%B/%Y')}"
    )


# app.py

# app.py


def gerar_pdf_combustivel(resultados, titulo):
    buffer = io.BytesIO()
    # Usando o modo paisagem (landscape) para caber mais colunas
    doc = BaseDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=3 * cm,
        bottomMargin=2.5 * cm,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    template = PageTemplate(
        id="main_template", frames=[frame], onPage=cabecalho_e_rodape
    )
    doc.addPageTemplates([template])

    styles = getSampleStyleSheet()
    # Estilos para as células da tabela
    p_style = ParagraphStyle(
        name="CustomNormal", parent=styles["Normal"], alignment=TA_CENTER, fontSize=8
    )
    p_style_alerta = ParagraphStyle(
        name="Alerta", parent=p_style, textColor=colors.red
    )  # Estilo para consumo alto
    header_style = ParagraphStyle(
        name="CustomHeader",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=9,
        fontName="Helvetica-Bold",
    )

    story = [Paragraph(titulo, styles["h1"]), Spacer(1, 1 * cm)]

    if not resultados:
        story.append(
            Paragraph(
                "Nenhum registro encontrado para o período selecionado.",
                styles["Normal"],
            )
        )
    else:
        # --- NOVOS CABEÇALHOS DA TABELA ---
        table_data = [
            [
                Paragraph(h, header_style)
                for h in [
                    "Data",
                    "Veículo",
                    "KM Atual",
                    "Litros",
                    "KM Rodado",
                    "KM/L",
                    "Custo/KM",
                    "Valor Total",
                ]
            ]
        ]

        # --- PREENCHIMENTO DA TABELA COM OS DADOS DA ANÁLISE ---
        for item in resultados:
            r = item["abastecimento"]

            # Escolhe o estilo do consumo (normal ou alerta)
            consumo_style = p_style
            if (
                item["consumo_kml"] > 0 and item["consumo_kml"] < 7.0
            ):  # Ajuste o valor 7.0 conforme sua frota
                consumo_style = p_style_alerta

            row = [
                Paragraph(r.data.strftime("%d/%m/%Y"), p_style),
                Paragraph(f"{r.veiculo.modelo} ({r.veiculo_placa})", p_style),
                Paragraph(f"{r.quilometragem:.1f}".replace(".", ","), p_style),
                Paragraph(f"{r.litros:.2f}".replace(".", ","), p_style),
            ]

            # Adiciona os campos calculados
            if item["km_rodado"] > 0:
                row.extend(
                    [
                        Paragraph(
                            f"{item['km_rodado']:.1f}".replace(".", ","), p_style
                        ),
                        Paragraph(
                            f"{item['consumo_kml']:.2f}".replace(".", ","),
                            consumo_style,
                        ),
                        Paragraph(
                            f"R$ {item['custo_km']:.2f}".replace(".", ","), p_style
                        ),
                    ]
                )
            else:
                row.extend(
                    [
                        Paragraph("--", p_style),
                        Paragraph("--", p_style),
                        Paragraph("--", p_style),
                    ]
                )

            row.append(Paragraph(f"R$ {r.valor_total:.2f}".replace(".", ","), p_style))
            table_data.append(row)

        # --- NOVAS LARGURAS DAS COLUNAS ---
        table = Table(
            table_data,
            colWidths=[
                2 * cm,
                5 * cm,
                2.5 * cm,
                2 * cm,
                2.5 * cm,
                2.5 * cm,
                2.5 * cm,
                2.5 * cm,
            ],
        )

        style = TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#004d40")),
                # --- CORREÇÃO APLICADA AQUI ---
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]
        )
        for i, row in enumerate(table_data[1:], 1):
            if i % 2 == 0:
                style.add("BACKGROUND", (0, i), (-1, i), colors.HexColor("#E0E0E0"))
        table.setStyle(style)
        story.append(table)

    doc.build(story)
    buffer.seek(0)

    response = make_response(buffer.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = (
        f'attachment; filename=relatorio_abastecimento_{datetime.now().strftime("%Y-%m-%d")}.pdf'
    )
    registrar_log(f'Gerou um PDF: "{titulo}".')
    return response


# ROTAS DE DOCUMENTOS, RELATÓRIOS E CONTRATOS
@app.route("/documentos/upload/<path:servidor_id>", methods=["POST"])
@login_required
@check_license
def upload_documento(servidor_id):
    servidor = Servidor.query.get_or_404(servidor_id)
    if "documento" not in request.files:
        flash("Nenhum arquivo enviado.", "danger")
        return redirect(url_for("editar_servidor", id=servidor_id))
    file = request.files["documento"]
    description = request.form.get("descricao")
    if file.filename == "" or not description:
        flash("A descrição e o arquivo são obrigatórios.", "warning")
        return redirect(url_for("editar_servidor", id=servidor_id))
    if file:
        filename = str(uuid.uuid4().hex) + "_" + secure_filename(file.filename)
        upload_path = os.path.join(app.config["UPLOAD_FOLDER"], "documentos")
        os.makedirs(upload_path, exist_ok=True)
        file.save(os.path.join(upload_path, filename))
        novo_documento = Documento(
            filename=filename, description=description, servidor_id=servidor_id
        )
        db.session.add(novo_documento)
        db.session.commit()
        registrar_log(
            f'Anexou o documento "{description}" para o servidor "{servidor.nome}".'
        )
        flash("Documento anexado com sucesso!", "success")
    return redirect(url_for("editar_servidor", id=servidor_id))


@app.route("/documentos/download/<int:documento_id>")
@login_required
@check_license
def download_documento(documento_id):
    documento = Documento.query.get_or_404(documento_id)
    docs_folder = os.path.join(app.config["UPLOAD_FOLDER"], "documentos")
    return send_from_directory(docs_folder, documento.filename, as_attachment=True)


@app.route("/documentos/delete/<int:documento_id>")
@login_required
@admin_required
@check_license
def delete_documento(documento_id):
    documento = Documento.query.get_or_404(documento_id)
    servidor_id = documento.servidor_id
    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"], "documentos", documento.filename
    )
    if os.path.exists(file_path):
        os.remove(file_path)
    desc_documento = documento.description
    nome_servidor = documento.servidor.nome
    db.session.delete(documento)
    db.session.commit()
    registrar_log(
        f'Excluiu o documento "{desc_documento}" do servidor "{nome_servidor}".'
    )
    flash("Documento excluído com sucesso!", "success")
    return redirect(url_for("editar_servidor", id=servidor_id))


@app.route("/baixar_modelo_csv")
@login_required
def baixar_modelo_csv():
    header = [
        "Nº CONTRATO",
        "NOME",
        "FUNÇÃO",
        "LOTAÇÃO",
        "CARGA HORÁRIA",
        "REMUNERAÇÃO",
        "VIGÊNCIA",
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


@app.route("/importar_servidores", methods=["POST"])
@login_required
@admin_required
@check_license
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
            file_content = file.stream.read().decode("utf-8-sig")
            dialect = csv.Sniffer().sniff(file_content[:1024])
            stream = io.StringIO(file_content)
            csv_input = csv.DictReader(stream, dialect=dialect)
            novos_servidores = []
            skipped_count = 0
            for row in csv_input:
                num_contrato = row.get("Nº CONTRATO")
                if not num_contrato:
                    skipped_count += 1
                    continue
                servidor_existente = Servidor.query.get(num_contrato)
                if servidor_existente:
                    skipped_count += 1
                    continue
                data_inicio_obj, data_saida_obj = None, None
                vigencia = row.get("VIGÊNCIA", "").strip()
                if " a " in vigencia:
                    try:
                        inicio_str, fim_str = vigencia.split(" a ")
                        data_inicio_obj = datetime.strptime(
                            inicio_str.strip(), "%d/%m/%Y"
                        ).date()
                        data_saida_obj = datetime.strptime(
                            fim_str.strip(), "%d/%m/%Y"
                        ).date()
                    except ValueError:
                        pass
                remuneracao_str = (
                    row.get("REMUNERAÇÃO", "0")
                    .replace("R$", "")
                    .replace(".", "")
                    .replace(",", ".")
                    .strip()
                )
                remuneracao_val = float(remuneracao_str) if remuneracao_str else 0.0
                novo_servidor = Servidor(
                    num_contrato=num_contrato,
                    nome=row.get("NOME"),
                    funcao=row.get("FUNÇÃO"),
                    lotacao=row.get("LOTAÇÃO"),
                    carga_horaria=row.get("CARGA HORÁRIA"),
                    remuneracao=remuneracao_val,
                    data_inicio=data_inicio_obj,
                    data_saida=data_saida_obj,
                    cpf=None,
                )
                novos_servidores.append(novo_servidor)
            if novos_servidores:
                db.session.add_all(novos_servidores)
                db.session.commit()
            added_count = len(novos_servidores)
            registrar_log(f"Importou {added_count} novos servidores via CSV.")
            flash(
                f"Importação concluída! {added_count} servidores adicionados. {skipped_count} registros ignorados (duplicados ou inválidos).",
                "success",
            )
        except Exception as e:
            db.session.rollback()
            flash(f"Ocorreu um erro ao processar o arquivo: {e}", "danger")
        return redirect(url_for("lista_servidores"))
    else:
        flash(
            "Formato de arquivo inválido. Por favor, envie um arquivo .csv.", "warning"
        )
        return redirect(url_for("lista_servidores"))


@app.route("/exportar_csv")
@login_required
@check_license
def exportar_csv():
    query = Servidor.query
    termo_busca = request.args.get("termo")
    funcao_filtro = request.args.get("funcao")
    lotacao_filtro = request.args.get("lotacao")
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
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    header = [
        "Nº CONTRATO",
        "NOME",
        "FUNÇÃO",
        "LOTAÇÃO",
        "CARGA HORÁRIA",
        "REMUNERAÇÃO",
        "VIGÊNCIA",
    ]
    writer.writerow(header)
    for s in servidores:
        vigencia = ""
        if s.data_inicio:
            vigencia += s.data_inicio.strftime("%d/%m/%Y")
        if s.data_saida:
            vigencia += f" a {s.data_saida.strftime('%d/%m/%Y')}"
        remuneracao = (
            f"{s.remuneracao:.2f}".replace(".", ",") if s.remuneracao else "0,00"
        )
        writer.writerow(
            [
                s.num_contrato,
                s.nome,
                s.funcao,
                s.lotacao,
                s.carga_horaria,
                remuneracao,
                vigencia,
            ]
        )
    csv_content = output.getvalue()
    response = Response(
        csv_content.encode("utf-8-sig"),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=relatorio_servidores.csv"},
    )
    registrar_log("Exportou dados de servidores para CSV.")
    return response


@app.route("/relatorio/html")
@login_required
@check_license
def gerar_relatorio_html():
    servidores = Servidor.query.order_by(Servidor.nome).all()
    data_emissao = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    registrar_log("Gerou um relatório de servidores em HTML.")
    return render_template(
        "relatorio_template.html", servidores=servidores, data_emissao=data_emissao
    )


@app.route("/relatorio/servidores/pdf")
@login_required
@check_license
def gerar_relatorio_pdf():
    # Busca todos os servidores ordenados por nome
    servidores = Servidor.query.order_by(Servidor.nome).all()

    buffer = io.BytesIO()
    # Usando o modo paisagem (landscape) para caber mais colunas
    doc = BaseDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=3 * cm,
        bottomMargin=2.5 * cm,
    )

    # Reutiliza a função de cabeçalho e rodapé que você já tem
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    template = PageTemplate(
        id="main_template", frames=[frame], onPage=cabecalho_e_rodape
    )
    doc.addPageTemplates([template])

    styles = getSampleStyleSheet()
    p_style = ParagraphStyle(
        name="CustomNormal", parent=styles["Normal"], alignment=TA_CENTER, fontSize=8
    )
    header_style = ParagraphStyle(
        name="CustomHeader",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=9,
        fontName="Helvetica-Bold",
    )

    story = [
        Paragraph("Relatório Geral de Servidores", styles["h1"]),
        Spacer(1, 1 * cm),
    ]

    if not servidores:
        story.append(Paragraph("Nenhum servidor cadastrado.", styles["Normal"]))
    else:
        # Define os cabeçalhos da tabela
        table_data = [
            [
                Paragraph(h, header_style)
                for h in ["Nome", "CPF", "Função", "Lotação", "Vínculo", "Telefone"]
            ]
        ]
        # Preenche a tabela com os dados dos servidores
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

        # Define a largura das colunas
        table = Table(
            table_data, colWidths=[7 * cm, 3.5 * cm, 4 * cm, 4 * cm, 3.5 * cm, 3 * cm]
        )

        # Aplica o estilo na tabela
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
    # Define o nome do arquivo para o navegador
    response.headers["Content-Disposition"] = (
        f'inline; filename=relatorio_servidores_{datetime.now().strftime("%Y-%m-%d")}.pdf'
    )

    registrar_log("Gerou o PDF do Relatório Geral de Servidores.")
    return response


# ROTAS DE PONTO ELETRÔNICO
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


def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371e3  # Raio da Terra em metros
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# Função para limpar CPF (já deve existir no seu arquivo)
def limpar_cpf(cpf):
    if cpf:
        return "".join(filter(str.isdigit, cpf))
    return None


@app.route("/ponto/registrar", methods=["GET", "POST"])
def registrar_ponto():
    """
    Rota para registrar o ponto eletrônico.
    - GET: Exibe o formulário com a lista de escolas.
    - POST: Valida a geolocalização, a foto e o CPF antes de registrar.
    """
    # --- TAREFA 2: Lógica de validação quando o formulário é ENVIADO ---
    if request.method == "POST":
        # 1. Obter todos os dados enviados pelo formulário
        cpf_input = request.form.get("cpf")
        tipo_ponto = request.form.get("tipo")
        latitude_str = request.form.get("latitude")
        longitude_str = request.form.get("longitude")
        foto_base64 = request.form.get("foto")
        escola_id = request.form.get("escola_id")

        # 2. Validação inicial para garantir que todos os dados essenciais foram recebidos
        if not all(
            [cpf_input, tipo_ponto, latitude_str, longitude_str, foto_base64, escola_id]
        ):
            flash(
                "Dados incompletos ou falha na captura da localização/foto. Por favor, tente novamente.",
                "danger",
            )
            return redirect(url_for("registrar_ponto"))

        # 3. Validar a Escola selecionada
        escola = Escola.query.get(escola_id)
        if not escola or not escola.latitude or not escola.longitude:
            flash(
                "A escola selecionada é inválida ou não possui coordenadas cadastradas. Contate o administrador.",
                "danger",
            )
            return redirect(url_for("registrar_ponto"))

        # 4. Validar a Geolocalização do Usuário
        latitude_usuario = float(latitude_str)
        longitude_usuario = float(longitude_str)
        distancia = calcular_distancia(
            escola.latitude, escola.longitude, latitude_usuario, longitude_usuario
        )

        if distancia > RAIO_PERMITIDO_METROS:
            flash(
                f'Registro bloqueado. Sua localização está a {int(distancia)} metros da escola "{escola.nome}", fora do limite permitido de {RAIO_PERMITIDO_METROS} metros.',
                "danger",
            )
            return redirect(url_for("registrar_ponto"))

        # 5. Validar o Servidor (CPF)
        cpf_limpo = limpar_cpf(cpf_input)
        servidor = Servidor.query.filter_by(cpf=cpf_limpo).first()
        if not servidor:
            flash(
                "CPF não encontrado no sistema. Verifique o número digitado.", "danger"
            )
            return redirect(url_for("registrar_ponto"))

        # 6. Processar e Salvar a Foto
        foto_filename = None
        try:
            header, encoded = foto_base64.split(",", 1)
            foto_data = base64.b64decode(encoded)
            timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            foto_filename = f"ponto_{cpf_limpo}_{timestamp_str}.jpg"

            # Garante que a pasta de destino exista
            fotos_path = os.path.join(app.config["UPLOAD_FOLDER"], "fotos_ponto")
            os.makedirs(fotos_path, exist_ok=True)

            with open(os.path.join(fotos_path, foto_filename), "wb") as f:
                f.write(foto_data)
        except Exception as e:
            flash(f"Ocorreu um erro ao processar a sua foto: {e}", "danger")
            return redirect(url_for("registrar_ponto"))

        # 7. Salvar o registro de ponto no banco de dados
        try:
            novo_ponto = Ponto(
                servidor_cpf=cpf_limpo,
                tipo=tipo_ponto,
                latitude=latitude_usuario,
                longitude=longitude_usuario,
                ip_address=request.remote_addr,
                foto_filename=foto_filename,
                escola_id=escola.id,
            )
            db.session.add(novo_ponto)
            db.session.commit()
            flash(
                f'{servidor.nome}, seu ponto em "{escola.nome}" foi registrado com sucesso!',
                "success",
            )
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar o registro no banco de dados: {e}", "danger")

        return redirect(url_for("registrar_ponto"))

    # --- TAREFA 1: Lógica para preparar o formulário quando a página é ABERTA ---
    # Busca no banco de dados todas as escolas ativas que possuem coordenadas cadastradas.
    escolas = (
        Escola.query.filter(Escola.status == "Ativa", Escola.latitude.isnot(None))
        .order_by(Escola.nome)
        .all()
    )

    # Renderiza a página HTML, enviando a lista de escolas para o frontend.
    return render_template("registrar_ponto_com_foto.html", escolas=escolas)


@app.route("/ponto/frequencia")
@login_required
@admin_required
def visualizar_frequencia():
    page = request.args.get("page", 1, type=int)
    registros = Ponto.query.order_by(Ponto.timestamp.desc()).paginate(
        page=page, per_page=50
    )
    return render_template("frequencia.html", registros=registros)


# --- 6. BLOCO PRINCIPAL ---
if __name__ == "__main__":
    app.run(debug=True)


@app.route("/offline")
def offline():
    """
    Serve a página que é exibida quando o usuário está sem conexão
    e tenta acessar uma página que não está no cache.
    """
    return render_template("offline.html")


@app.route("/test")
def test_route():
    return "O servidor recarregou o codigo. A rota de teste funciona!"


# --- 6. BLOCO PRINCIPAL ---
if __name__ == "__main__":
    app.run(debug=True)


@app.route("/relatorio/combustivel/tce-pi")
@login_required
@fleet_required
@check_license
def relatorio_combustivel_tce_pi():
    """
    Gera um relatório de abastecimento no formato CSV exigido pelo TCE-PI.
    """
    try:
        abastecimentos = (
            Abastecimento.query.join(
                Servidor, Abastecimento.servidor_cpf == Servidor.cpf
            )
            .join(Veiculo)
            .order_by(Abastecimento.data.asc())
            .all()
        )

        output = io.StringIO()
        writer = csv.writer(output, delimiter=";")

        header = [
            "unidade_gestora",
            "exercicio",
            "mes_referencia",
            "numero_notafiscal",
            "data_notafiscal",
            "cpf_condutor",
            "nome_condutor",
            "placa_veiculo",
            "quilometragem",
            "tipo_combustivel",
            "quantidade_combustivel",
            "valor_unitario",
            "valor_total",
            "cnpj_fornecedor",
        ]
        writer.writerow(header)

        for r in abastecimentos:
            row = [
                "",
                r.data.year,
                r.data.month,
                "",
                r.data.strftime("%Y-%m-%d"),
                r.motorista.cpf,  # <-- CORRIGIDO AQUI
                r.motorista.nome,  # <-- CORRIGIDO AQUI
                r.veiculo.placa,
                f"{r.quilometragem:.1f}".replace(".", ","),
                r.tipo_combustivel,
                f"{r.litros:.2f}".replace(".", ","),
                f"{r.valor_litro:.2f}".replace(".", ","),
                f"{r.valor_total:.2f}".replace(".", ","),
                "",
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
@fleet_required
def selecionar_relatorio_veiculos():
    return render_template("selecionar_relatorio_veiculos.html")


# @app.route('/relatorio/veiculos/gerar', methods=['POST'])
# @login_required
# @fleet_required
# def gerar_relatorio_veiculos_mensal():
# try:
# ano = int(request.form.get('ano'))
# mes = int(request.form.get('mes'))

# data_inicio = datetime(ano, mes, 1)
# if mes == 12:
# data_fim = datetime(ano + 1, 1, 1)
# else:
# data_fim = datetime(ano, mes + 1, 1)

# abastecimentos_do_mes = Abastecimento.query.join(Veiculo).filter(
# Abastecimento.data >= data_inicio,
# Abastecimento.data < data_fim
# ).order_by(Veiculo.placa, Abastecimento.quilometragem.asc()).all()

# if not abastecimentos_do_mes:
# flash(f'Nenhum abastecimento encontrado para {mes}/{ano}.', 'warning')
# return redirect(url_for('selecionar_relatorio_veiculos'))

# dados_processados = []
# km_anterior_por_veiculo = {}
# for r in abastecimentos_do_mes:
# placa = r.veiculo.placa
# km_inicial = km_anterior_por_veiculo.get(placa, 0)
# km_final = r.quilometragem
# dados_processados.append({
# 'modelo': r.veiculo.modelo,
# 'placa': placa,
# 'renavam': r.veiculo.renavam or '',
# 'ano_fab': r.veiculo.ano_fabricacao or '',
# 'ano_mod': r.veiculo.ano_modelo or '',
# 'tipo_veiculo': r.veiculo.tipo or 'AUTOMOVEL',
# 'orgao_localizacao': r.veiculo.orgao or '',
# 'qtde_abastecimento': f"{r.litros:.2f}".replace('.', ','),
# 'combustivel_abastecimento': r.tipo_combustivel,
# 'km_inicial_mes': f"{km_inicial:.1f}".replace('.', ',') if km_inicial else '',
# 'km_final_mes': f"{km_final:.1f}".replace('.', ',')
# })
# km_anterior_por_veiculo[placa] = km_final

# output = io.StringIO()


# header = [
# 'modelo', 'placa', 'renavam', 'ano_fab', 'ano_mod',
# 'tipo_veiculo','orgao_localizacao', 'capacidade', 'qtde_abastecimento', 'combustivel_abastecimento', 'km_inicial_mes', 'km_final_mes'
# ]
# writer = csv.DictWriter(output, fieldnames=header, delimiter=';')
# writer.writeheader()
# writer.writerows(dados_processados)

# response = Response(
# output.getvalue().encode('utf-8-sig'),
# mimetype='text/csv',
# headers={'Content-Disposition': f'attachment;filename=relatorio_detalhado_{mes}-{ano}.csv'}
# )
# return response

# except Exception as e:
# db.session.rollback()
# flash(f'Ocorreu um erro ao gerar o relatório: {e}', 'danger')
# return redirect(url_for('selecionar_relatorio_veiculos'))


# Em app.py


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


@app.route("/relatorio/combustivel/extrato/selecionar")
@login_required
@fleet_required
def selecionar_extrato_combustivel():
    return render_template("selecionar_extrato_combustivel.html")


# Rota que gera o CSV detalhado com uma linha por abastecimento
@app.route("/relatorio/combustivel/extrato/gerar", methods=["POST"])
@login_required
@fleet_required
def gerar_extrato_combustivel_csv():
    try:
        ano = int(request.form.get("ano"))
        mes = int(request.form.get("mes"))

        data_inicio = datetime(ano, mes, 1)
        if mes == 12:
            data_fim = datetime(ano + 1, 1, 1)
        else:
            data_fim = datetime(ano, mes + 1, 1)

        # Busca todos os abastecimentos individuais no período selecionado
        abastecimentos = (
            Abastecimento.query.join(Veiculo)
            .join(Servidor)
            .filter(Abastecimento.data >= data_inicio, Abastecimento.data < data_fim)
            .order_by(Veiculo.modelo, Abastecimento.data.asc())
            .all()
        )

        if not abastecimentos:
            flash(f"Nenhum abastecimento encontrado para {mes}/{ano}.", "warning")
            return redirect(url_for("selecionar_extrato_combustivel"))

        output = io.StringIO()
        writer = csv.writer(output, delimiter=";")

        # Define o cabeçalho com as informações do veículo e do abastecimento
        header = [
            "Data",
            "Modelo",
            "Placa",
            "Renavam",
            "Ano Fabricação",
            "Ano Modelo",
            "Motorista",
            "Quilometragem",
            "Litros",
            "Valor por Litro",
            "Valor Total",
        ]
        writer.writerow(header)

        # Itera sobre cada abastecimento e cria uma linha para ele
        for r in abastecimentos:
            writer.writerow(
                [
                    r.data.strftime("%d/%m/%Y"),
                    r.veiculo.modelo,
                    r.veiculo.placa,
                    r.veiculo.renavam or "",
                    r.veiculo.ano_fabricacao or "",
                    r.veiculo.ano_modelo or "",
                    r.motorista.nome,
                    f"{r.quilometragem:.1f}".replace(".", ","),
                    f"{r.litros:.2f}".replace(".", ","),
                    f"R$ {r.valor_litro:.2f}".replace(".", ","),
                    f"R$ {r.valor_total:.2f}".replace(".", ","),
                ]
            )

        response = Response(
            output.getvalue().encode("utf-8-sig"),
            mimetype="text/csv",
            headers={
                "Content-Disposition": f"attachment;filename=extrato_abastecimentos_{mes}-{ano}.csv"
            },
        )
        return response

    except Exception as e:
        db.session.rollback()
        flash(f"Ocorreu um erro ao gerar o extrato: {e}", "danger")
        return redirect(url_for("selecionar_extrato_combustivel"))


# Em app.py


# Adicione esta função de teste temporária ao final do arquivo
@app.route("/debug-veiculos")
def debug_veiculos():
    try:
        # Tenta buscar todos os veículos do banco de dados
        veiculos_no_db = Veiculo.query.all()

        if not veiculos_no_db:
            return "DIAGNÓSTICO: A consulta `Veiculo.query.all()` não retornou NENHUM resultado. Para o sistema, a tabela de veículos está vazia."

        # Se encontrar veículos, mostra a contagem e os dados do primeiro
        resposta = f"<h1>Diagnóstico do Banco de Dados</h1>"
        resposta += f"<p><b>Sucesso!</b> A consulta encontrou {len(veiculos_no_db)} veículo(s) no banco de dados.</p>"
        resposta += "<h3>Dados do primeiro veículo encontrado:</h3>"

        primeiro_veiculo = veiculos_no_db[0]

        # Usamos getattr para verificar com segurança se os atributos existem
        resposta += f"<b>Placa:</b> {getattr(primeiro_veiculo, 'placa', 'N/A')}<br>"
        resposta += f"<b>Modelo:</b> {getattr(primeiro_veiculo, 'modelo', 'N/A')}<br>"
        resposta += f"<b>Renavam:</b> {getattr(primeiro_veiculo, 'renavam', 'N/A')}<br>"
        resposta += f"<hr><b>Verificação das colunas de ano:</b><br>"
        resposta += f"<b>Ano Fabricação (novo):</b> {getattr(primeiro_veiculo, 'ano_fabricacao', 'NÃO EXISTE')}<br>"
        resposta += f"<b>Ano Modelo (novo):</b> {getattr(primeiro_veiculo, 'ano_modelo', 'NÃO EXISTE')}<br>"
        resposta += (
            f"<b>Ano (antigo):</b> {getattr(primeiro_veiculo, 'ano', 'NÃO EXISTE')}<br>"
        )

        return resposta

    except Exception as e:
        # Se ocorrer um erro na consulta, o problema é mais sério (ex: coluna não encontrada)
        return f"<h1>Erro no Diagnóstico</h1><p>Ocorreu um erro ao tentar consultar a tabela de veículos. Isso geralmente indica um problema com a migração do banco de dados.</p> <h3>Detalhes do Erro:</h3><pre>{e}</pre>"


@app.route("/gam/novo", methods=["GET", "POST"])
@login_required  # Adicione suas verificações de login/permissão
def criar_gam():
    if request.method == "POST":
        servidor_id = request.form.get("servidor_id")

        # Extrai os dados do documento para o formulário
        observacoes = "A requerente é efetiva da rede municipal de ensino, tendo sido admitida em 03/11/1997 para a funo Auxiliar de Servios Gerais Classe E, nvel VI, lotada atualmente no Centro de Atendimento Educacional Especializado (CAEE). Na declarao mdica, datada do dia 08 de abril de 2025, o mdico psiquiatra recomenda 90 dias de afastamento das suas atividades laborais, pois declara que a servidora se encontra em episdio de mania do quadro de transtorno afetivo de bipolaridade."[
            cite_start
        ]  # [cite: 1, 2]
        cid_10 = request.form.get("cid10")  # [cite: 3]

        servidor = Servidor.query.get(servidor_id)
        if not servidor:
            flash("Servidor não encontrado!", "danger")
            return redirect(url_for("criar_gam"))

        nova_guia = GAM(
            servidor_id=servidor_id,
            observacoes_chefia=observacoes,  # Você pode montar este texto dinamicamente
            cid10=cid_10,
            data_emissao=datetime.now(),
        )
        db.session.add(nova_guia)
        db.session.commit()

        flash("Guia de Atendimento Médico gerada com sucesso!", "success")
        return redirect(url_for("imprimir_gam", gam_id=nova_guia.id))

    # Carrega apenas servidores efetivos para o formulário
    servidores_efetivos = Servidor.query.filter_by(
        tipo="Efetivo"
    ).all()  # Adapte este filtro à sua base
    return render_template("criar_gam.html", servidores=servidores_efetivos)


# Rota para exibir e imprimir a GAM
@app.route("/gam/imprimir/<int:gam_id>")
@login_required
def imprimir_gam(gam_id):
    guia = GAM.query.get_or_404(gam_id)
    return render_template("relatorio_gam.html", guia=guia)
