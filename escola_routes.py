from flask import Blueprint, render_template, request, redirect, url_for, flash
from .extensions import db
from .models import Escola
from .utils import login_required, admin_required # Protege as rotas
from .utils import role_required

escola_bp = Blueprint('escola', __name__)

@escola_bp.route('/escolas')
@login_required
@role_required('RH', 'admin')
def listar_escolas():
    """Exibe a lista de todas as escolas cadastradas."""
    escolas = Escola.query.order_by(Escola.nome).all()
    return render_template('escolas.html', escolas=escolas)

@escola_bp.route('/escolas/nova', methods=['GET', 'POST'])
@login_required
@admin_required
@role_required('RH', 'admin')
def nova_escola():
    """Exibe o formulário para adicionar uma nova escola e processa o envio."""
    if request.method == 'POST':
        try:
            nome = request.form.get('nome')
            endereco = request.form.get('endereco')
            telefone = request.form.get('telefone')
            latitude = request.form.get('latitude')
            longitude = request.form.get('longitude')
            status = request.form.get('status', 'Ativa')

            # Validação simples
            if not nome or not latitude or not longitude:
                flash('Nome, Latitude e Longitude são campos obrigatórios.', 'warning')
                return redirect(url_for('escola.nova_escola'))

            nova_escola = Escola(
                nome=nome,
                endereco=endereco,
                telefone=telefone,
                latitude=float(latitude) if latitude else None,
                longitude=float(longitude) if longitude else None,
                status=status
            )
            db.session.add(nova_escola)
            db.session.commit()
            flash(f'Escola "{nome}" cadastrada com sucesso!', 'success')
            return redirect(url_for('escola.listar_escolas'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar escola: {e}', 'danger')
            
    return render_template('escola_form.html', titulo="Cadastrar Nova Escola")

@escola_bp.route('/escolas/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
@role_required('RH', 'admin')
def editar_escola(id):
    """Exibe o formulário para editar uma escola existente e processa a atualização."""
    escola = Escola.query.get_or_404(id)
    if request.method == 'POST':
        try:
            escola.nome = request.form.get('nome')
            escola.endereco = request.form.get('endereco')
            escola.telefone = request.form.get('telefone')
            latitude = request.form.get('latitude')
            longitude = request.form.get('longitude')
            escola.status = request.form.get('status')
            
            if not escola.nome or not latitude or not longitude:
                flash('Nome, Latitude e Longitude são campos obrigatórios.', 'warning')
                return render_template('escola_form.html', escola=escola, titulo=f"Editar Escola: {escola.nome}")

            escola.latitude = float(latitude) if latitude else None
            escola.longitude = float(longitude) if longitude else None
            
            db.session.commit()
            flash(f'Dados da escola "{escola.nome}" atualizados com sucesso!', 'success')
            return redirect(url_for('escola.listar_escolas'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao editar escola: {e}', 'danger')

    return render_template('escola_form.html', escola=escola, titulo=f"Editar Escola: {escola.nome}")