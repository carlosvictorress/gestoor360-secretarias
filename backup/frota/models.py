# models.py

# from .extensions import db
from datetime import datetime, time
from .app import db

# --- SEUS MODELOS ---


class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    username = db.Column(db.String(80), nullable=False)
    action = db.Column(db.String(255), nullable=False)
    ip_address = db.Column(db.String(45))


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="operador")
    notas = db.relationship(
        "Nota", backref="autor", lazy=True, cascade="all, delete-orphan"
    )


class Servidor(db.Model):
    __tablename__ = "servidor"
    # A Chave Primária é 'num_contrato', e não um 'id' inteiro.
    num_contrato = db.Column(db.String(50), primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    cpf = db.Column(db.String(14), unique=True, nullable=True)
    rg = db.Column(db.String(20))
    data_nascimento = db.Column(db.Date, nullable=True)
    nome_mae = db.Column(db.String(200), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    pis_pasep = db.Column(db.String(20), nullable=True)
    tipo_vinculo = db.Column(db.String(50), nullable=True) # Campo usado para filtrar efetivos
    local_trabalho = db.Column(db.String(150), nullable=True)
    classe_nivel = db.Column(db.String(50), nullable=True)
    num_contra_cheque = db.Column(db.String(50), nullable=True)
    nacionalidade = db.Column(db.String(50), default="brasileira")
    estado_civil = db.Column(db.String(50), default="solteiro(a)")
    telefone = db.Column(db.String(20))
    endereco = db.Column(db.String(250))
    funcao = db.Column(db.String(100))
    lotacao = db.Column(db.String(100))
    carga_horaria = db.Column(db.String(50))
    remuneracao = db.Column(db.Float)
    dados_bancarios = db.Column(db.String(200))
    data_inicio = db.Column(db.Date, nullable=True)
    data_saida = db.Column(db.Date, nullable=True)
    observacoes = db.Column(db.Text, nullable=True)
    foto_filename = db.Column(db.String(100), nullable=True)
    num_contrato_gerado = db.Column(db.String(10), unique=True, nullable=True)
    documentos = db.relationship(
        "Documento", backref="servidor", lazy=True, cascade="all, delete-orphan"
    )


class Veiculo(db.Model):
    placa = db.Column(db.String(10), primary_key=True)
    modelo = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    ano_fabricacao = db.Column(db.Integer)
    ano_modelo = db.Column(db.Integer)
    orgao = db.Column(db.String(150))
    abastecimentos = db.relationship(
        "Abastecimento", backref="veiculo", lazy=True, cascade="all, delete-orphan"
    )
    manutencoes = db.relationship(
        "Manutencao",
        backref="veiculo_manutencao",
        lazy=True,
        cascade="all, delete-orphan",
    )
    # CORREÇÃO: Adicionado o relacionamento inverso para a rota
    rota = db.relationship("RotaTransporte", back_populates="veiculo", uselist=False)
    autorizacao_detran = db.Column(db.String(50), nullable=True)
    validade_autorizacao = db.Column(db.Date, nullable=True)
    renavam = db.Column(db.String(50), nullable=True)
    certificado_tacografo = db.Column(db.String(50), nullable=True)
    data_emissao_tacografo = db.Column(db.Date, nullable=True)
    validade_tacografo = db.Column(db.Date, nullable=True)


class Abastecimento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    quilometragem = db.Column(db.Float, nullable=False)
    tipo_combustivel = db.Column(db.String(50), nullable=False)
    litros = db.Column(db.Float, nullable=False)
    valor_litro = db.Column(db.Float, nullable=False)
    valor_total = db.Column(db.Float, nullable=False)
    veiculo_placa = db.Column(
        db.String(10), db.ForeignKey("veiculo.placa"), nullable=False
    )
    # servidor_cpf = db.Column(db.String(14), db.ForeignKey('servidor.cpf'), nullable=False)
    # motorista = db.relationship('Servidor', backref=db.backref('abastecimentos', lazy=True))

    motorista_id = db.Column(db.Integer, db.ForeignKey("motorista.id"), nullable=False)
    motorista = db.relationship(
        "Motorista", backref=db.backref("abastecimentos", lazy=True)
    )


class Manutencao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False)
    quilometragem = db.Column(db.Float, nullable=False)
    tipo_servico = db.Column(db.String(150), nullable=False)
    custo = db.Column(db.Float, nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    oficina = db.Column(db.String(150), nullable=True)
    veiculo_placa = db.Column(
        db.String(10), db.ForeignKey("veiculo.placa"), nullable=False
    )


class Requerimento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    autoridade_dirigida = db.Column(db.String(200), nullable=False)
    servidor_cpf = db.Column(
        db.String(14), db.ForeignKey("servidor.cpf"), nullable=False
    )
    servidor = db.relationship(
        "Servidor", backref=db.backref("requerimentos", lazy=True)
    )
    natureza = db.Column(db.String(100), nullable=False)
    natureza_outro = db.Column(db.String(255), nullable=True)
    data_admissao = db.Column(db.Date, nullable=True)
    data_inicio_requerimento = db.Column(db.Date, nullable=False)
    duracao = db.Column(db.String(50), nullable=True)
    periodo_aquisitivo = db.Column(db.String(20), nullable=True)
    data_retorno_trabalho = db.Column(db.Date, nullable=True)
    data_conclusao = db.Column(db.Date, nullable=True)
    informacoes_complementares = db.Column(db.Text, nullable=True)
    parecer_juridico = db.Column(db.Text, nullable=True)
    data_criacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(50), nullable=False, default="Em Análise")


class Nota(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(120), nullable=False)
    conteudo = db.Column(db.Text, nullable=True)
    data_criacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class Documento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    servidor_id = db.Column(
        db.String(50), db.ForeignKey("servidor.num_contrato"), nullable=False
    )


class License(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    expiration_date = db.Column(db.DateTime, nullable=False)
    renewal_key = db.Column(db.String(100), unique=True, nullable=True)


class Ponto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    servidor_cpf = db.Column(
        db.String(14), db.ForeignKey("servidor.cpf"), nullable=False
    )
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    tipo = db.Column(db.String(10), nullable=False)

    # --- VERIFIQUE SE ESTES CAMPOS ESTÃO AQUI ---
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    foto_filename = db.Column(db.String(100), nullable=True)
    escola_id = db.Column(db.Integer, db.ForeignKey("escola.id"), nullable=True)
    # -------------------------------------------

    servidor_ponto = db.relationship(
        "Servidor",
        backref=db.backref("pontos", lazy=True, cascade="all, delete-orphan"),
    )
    escola = db.relationship("Escola", backref=db.backref("pontos", lazy=True))


class RotaTransporte(db.Model):
    __tablename__ = "rota_transporte"
    id = db.Column(db.Integer, primary_key=True)
    motorista_cpf = db.Column(
        db.String(14), db.ForeignKey("servidor.cpf"), nullable=False
    )
    veiculo_placa = db.Column(
        db.String(10), db.ForeignKey("veiculo.placa"), nullable=False
    )
    monitor_cpf = db.Column(db.String(14), db.ForeignKey("servidor.cpf"), nullable=True)
    escolas_manha = db.Column(db.String(500))
    itinerario_manha = db.Column(db.Text)
    qtd_alunos_manha = db.Column(db.Integer, default=0)
    coordenadas_manha = db.Column(db.Text, nullable=True)
    escolas_tarde = db.Column(db.String(500))
    itinerario_tarde = db.Column(db.Text)
    qtd_alunos_tarde = db.Column(db.Integer, default=0)
    coordenadas_tarde = db.Column(db.Text, nullable=True)

    horario_saida_manha = db.Column(db.Time, nullable=True)
    horario_volta_manha = db.Column(db.Time, nullable=True)
    horario_saida_tarde = db.Column(db.Time, nullable=True)
    horario_volta_tarde = db.Column(db.Time, nullable=True)

    trechos = db.relationship(
        "TrechoRota", backref="rota", lazy=True, cascade="all, delete-orphan"
    )

    # CORREÇÃO: Adicionados os relacionamentos para criar os atributos .motorista, .monitor e .veiculo
    motorista = db.relationship(
        "Servidor", foreign_keys=[motorista_cpf], backref="rotas_como_motorista"
    )
    monitor = db.relationship(
        "Servidor", foreign_keys=[monitor_cpf], backref="rotas_como_monitor"
    )
    veiculo = db.relationship(
        "Veiculo", back_populates="rota", foreign_keys=[veiculo_placa]
    )

    alunos = db.relationship(
        "AlunoTransporte", backref="rota", lazy=True, cascade="all, delete-orphan"
    )


class TrechoRota(db.Model):
    __tablename__ = "trecho_rota"
    id = db.Column(db.Integer, primary_key=True)
    rota_id = db.Column(db.Integer, db.ForeignKey("rota_transporte.id"), nullable=False)
    turno = db.Column(db.String(10), nullable=False)  # 'manha' ou 'tarde'
    tipo_viagem = db.Column(db.String(10), nullable=False)  # 'ida' ou 'volta'
    distancia_km = db.Column(db.Float, nullable=False)
    descricao = db.Column(db.String(200), nullable=True)


class AlunoTransporte(db.Model):
    __tablename__ = "aluno_transporte"
    id = db.Column(db.Integer, primary_key=True)
    nome_completo = db.Column(db.String(200), nullable=False)
    data_nascimento = db.Column(db.Date, nullable=False)
    ano_estudo = db.Column(
        db.String(50), nullable=False
    )  # Ex: "5º Ano", "Ensino Médio 2º Ano"
    turno = db.Column(db.String(20), nullable=False)  # "Manhã" ou "Tarde"
    escola = db.Column(db.String(200), nullable=False)
    zona = db.Column(db.String(20), nullable=False)
    nome_responsavel = db.Column(db.String(200), nullable=False)
    telefone_responsavel = db.Column(db.String(20), nullable=False)
    endereco_aluno = db.Column(db.String(300), nullable=False)
    rota_id = db.Column(db.Integer, db.ForeignKey("rota_transporte.id"), nullable=False)
    sexo = db.Column(db.String(20), nullable=True)  # Ex: Masculino, Feminino
    cor = db.Column(db.String(50), nullable=True)  # Ex: Branca, Parda, Preta, etc.
    nivel_ensino = db.Column(db.String(100), nullable=True)
    possui_deficiencia = db.Column(db.Boolean, default=False)
    tipo_deficiencia = db.Column(
        db.String(200), nullable=True
    )  # Campo para descrever a deficiência


class Protocolo(db.Model):
    __tablename__ = "protocolo"
    id = db.Column(db.Integer, primary_key=True)
    numero_protocolo = db.Column(db.String(20), unique=True, nullable=False)
    assunto = db.Column(db.String(300), nullable=False)
    tipo_documento = db.Column(db.String(100), nullable=False)
    interessado = db.Column(db.String(200), nullable=False)
    setor_origem = db.Column(db.String(150), nullable=False)
    setor_atual = db.Column(db.String(150), nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default="Aberto")
    motivo_cancelamento = db.Column(db.Text, nullable=True)
    tramitacoes = db.relationship(
        "Tramitacao", backref="protocolo", lazy=True, cascade="all, delete-orphan"
    )
    anexos = db.relationship(
        "Anexo", backref="protocolo", lazy=True, cascade="all, delete-orphan"
    )


class Tramitacao(db.Model):
    __tablename__ = "tramitacao"
    id = db.Column(db.Integer, primary_key=True)
    protocolo_id = db.Column(db.Integer, db.ForeignKey("protocolo.id"), nullable=False)
    setor_origem = db.Column(db.String(150), nullable=False)
    setor_destino = db.Column(db.String(150), nullable=False)
    data_envio = db.Column(db.DateTime, default=datetime.utcnow)
    despacho = db.Column(db.Text, nullable=True)
    usuario_responsavel = db.Column(db.String(100))


class Anexo(db.Model):
    __tablename__ = "anexo"
    id = db.Column(db.Integer, primary_key=True)
    protocolo_id = db.Column(db.Integer, db.ForeignKey("protocolo.id"), nullable=False)
    nome_arquivo = db.Column(db.String(255), nullable=False)
    nome_original = db.Column(db.String(255), nullable=False)
    data_upload = db.Column(db.DateTime, default=datetime.utcnow)


class Contrato(db.Model):
    __tablename__ = "contrato"
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), unique=True, nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    servidor_cpf = db.Column(
        db.String(14), db.ForeignKey("servidor.cpf"), nullable=False
    )
    conteudo = db.Column(db.Text, nullable=False)
    assinatura_secretaria_tipo = db.Column(db.String(20), default="manual")
    assinatura_secretaria_dados = db.Column(db.String(255), nullable=True)
    data_geracao = db.Column(db.DateTime, default=datetime.utcnow)

    # --- ALTERAÇÃO APLICADA AQUI ---
    # Remova o 'cascade' para que a exclusão não seja automática.
    servidor = db.relationship("Servidor", backref="contratos")


class Patrimonio(db.Model):
    __tablename__ = "patrimonio"
    id = db.Column(db.Integer, primary_key=True)
    numero_patrimonio = db.Column(db.String(50), unique=True, nullable=False)
    descricao = db.Column(db.String(300), nullable=False)
    categoria = db.Column(db.String(100), nullable=True)
    status = db.Column(
        db.String(50), nullable=False, default="Ativo"
    )  # Ex: Ativo, Manutenção, Baixado
    localizacao = db.Column(
        db.String(200), nullable=False
    )  # Ex: "SEMED - Sala do Secretário", "Escola X - Sala 10"
    data_aquisicao = db.Column(db.Date, nullable=True)
    valor_aquisicao = db.Column(db.Float, nullable=True)
    observacoes = db.Column(db.Text, nullable=True)

    # Relacionamento com o servidor responsável
    servidor_responsavel_cpf = db.Column(
        db.String(14), db.ForeignKey("servidor.cpf"), nullable=True
    )
    responsavel = db.relationship(
        "Servidor", backref=db.backref("patrimonios_responsaveis", lazy=True)
    )

    # Histórico de movimentações
    movimentacoes = db.relationship(
        "MovimentacaoPatrimonio",
        backref="patrimonio",
        lazy=True,
        cascade="all, delete-orphan",
    )


class MovimentacaoPatrimonio(db.Model):
    __tablename__ = "movimentacao_patrimonio"
    id = db.Column(db.Integer, primary_key=True)
    patrimonio_id = db.Column(
        db.Integer, db.ForeignKey("patrimonio.id"), nullable=False
    )
    data_movimentacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # De onde veio
    local_origem = db.Column(db.String(200), nullable=False)
    responsavel_anterior_cpf = db.Column(
        db.String(14), db.ForeignKey("servidor.cpf"), nullable=True
    )

    # Para onde foi
    local_destino = db.Column(db.String(200), nullable=False)
    responsavel_novo_cpf = db.Column(
        db.String(14), db.ForeignKey("servidor.cpf"), nullable=True
    )

    # Quem registrou a movimentação
    usuario_registro = db.Column(db.String(80), nullable=False)

    responsavel_anterior = db.relationship(
        "Servidor", foreign_keys=[responsavel_anterior_cpf]
    )
    responsavel_novo = db.relationship("Servidor", foreign_keys=[responsavel_novo_cpf])


class Escola(db.Model):
    __tablename__ = "escola"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False, unique=True)
    endereco = db.Column(db.String(300))
    telefone = db.Column(db.String(20))

    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    diretor_cpf = db.Column(db.String(14), db.ForeignKey("servidor.cpf"))
    responsavel_merenda_cpf = db.Column(db.String(14), db.ForeignKey("servidor.cpf"))
    status = db.Column(
        db.String(20), nullable=False, default="Ativa"
    )  # Ativa / Inativa

    diretor = db.relationship("Servidor", foreign_keys=[diretor_cpf])
    responsavel_merenda = db.relationship(
        "Servidor", foreign_keys=[responsavel_merenda_cpf]
    )


class ProdutoMerenda(db.Model):
    __tablename__ = "produto_merenda"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False, unique=True)
    unidade_medida = db.Column(
        db.String(20), nullable=False
    )  # Ex: KG, Litro, Unidade, Pacote
    categoria = db.Column(db.String(100))  # Ex: Hortifrúti, Grãos, Proteína
    estoque_atual = db.Column(db.Float, nullable=False, default=0.0)


class EstoqueMovimento(db.Model):
    __tablename__ = "estoque_movimento"
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(
        db.Integer, db.ForeignKey("produto_merenda.id"), nullable=False
    )
    tipo = db.Column(db.String(10), nullable=False)  # 'Entrada' ou 'Saída'
    quantidade = db.Column(db.Float, nullable=False)
    data_movimento = db.Column(db.DateTime, default=datetime.utcnow)

    # Para Entradas
    fornecedor = db.Column(db.String(200))
    lote = db.Column(db.String(50))
    data_validade = db.Column(db.Date)

    # Para Saídas
    solicitacao_id = db.Column(db.Integer, db.ForeignKey("solicitacao_merenda.id"))

    # Rastreabilidade
    usuario_responsavel = db.Column(db.String(80), nullable=False)

    produto = db.relationship("ProdutoMerenda", backref="movimentos")
    solicitacao = db.relationship("SolicitacaoMerenda")


class SolicitacaoMerenda(db.Model):
    __tablename__ = "solicitacao_merenda"
    id = db.Column(db.Integer, primary_key=True)
    escola_id = db.Column(db.Integer, db.ForeignKey("escola.id"), nullable=False)
    data_solicitacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_entrega = db.Column(db.DateTime)
    status = db.Column(
        db.String(50), default="Pendente"
    )  # Pendente, Autorizada, Entregue, Cancelada

    # Rastreabilidade completa
    solicitante_cpf = db.Column(
        db.String(14), db.ForeignKey("servidor.cpf"), nullable=False
    )
    autorizador_cpf = db.Column(db.String(14), db.ForeignKey("servidor.cpf"))
    entregador_cpf = db.Column(db.String(14), db.ForeignKey("servidor.cpf"))

    escola = db.relationship("Escola", backref="solicitacoes")
    itens = db.relationship(
        "SolicitacaoItem", backref="solicitacao", cascade="all, delete-orphan"
    )

    solicitante = db.relationship("Servidor", foreign_keys=[solicitante_cpf])
    autorizador = db.relationship("Servidor", foreign_keys=[autorizador_cpf])
    entregador = db.relationship("Servidor", foreign_keys=[entregador_cpf])


class SolicitacaoItem(db.Model):
    __tablename__ = "solicitacao_item"
    id = db.Column(db.Integer, primary_key=True)
    solicitacao_merenda_id = db.Column(
        db.Integer, db.ForeignKey("solicitacao_merenda.id"), nullable=False
    )
    produto_id = db.Column(
        db.Integer, db.ForeignKey("produto_merenda.id"), nullable=False
    )
    quantidade_solicitada = db.Column(db.Float, nullable=False)

    produto = db.relationship("ProdutoMerenda")


class Cardapio(db.Model):
    __tablename__ = "cardapio"
    id = db.Column(db.Integer, primary_key=True)
    escola_id = db.Column(db.Integer, db.ForeignKey("escola.id"), nullable=False)
    # --- ALTERAÇÃO APLICADA AQUI ---
    mes = db.Column(
        db.Integer, nullable=False
    )  # Armazena o número do mês (ex: 8 para Agosto)
    ano = db.Column(db.Integer, nullable=False)  # Armazena o ano (ex: 2025)
    observacoes = db.Column(db.Text)

    escola = db.relationship("Escola", backref="cardapios")
    pratos = db.relationship(
        "PratoDiario", backref="cardapio", cascade="all, delete-orphan"
    )
    historico = db.relationship(
        "HistoricoCardapio", backref="cardapio", cascade="all, delete-orphan"
    )

    # Garante que só exista um cardápio por escola para cada mês/ano
    __table_args__ = (
        db.UniqueConstraint("escola_id", "mes", "ano", name="_escola_mes_ano_uc"),
    )


class PratoDiario(db.Model):
    __tablename__ = "prato_diario"
    id = db.Column(db.Integer, primary_key=True)
    cardapio_id = db.Column(db.Integer, db.ForeignKey("cardapio.id"), nullable=False)
    # --- ALTERAÇÃO APLICADA AQUI ---
    data_prato = db.Column(db.Date, nullable=False)  # Armazena a data exata do prato
    nome_prato = db.Column(db.String(200), nullable=False)


class HistoricoCardapio(db.Model):
    __tablename__ = "historico_cardapio"
    id = db.Column(db.Integer, primary_key=True)
    cardapio_id = db.Column(db.Integer, db.ForeignKey("cardapio.id"), nullable=False)
    usuario = db.Column(db.String(80), nullable=False)
    data_modificacao = db.Column(db.DateTime, default=datetime.utcnow)
    descricao_mudanca = db.Column(
        db.Text, nullable=False
    )  # Ex: "Alterou o prato de Terça-feira de 'Macarronada' para 'Arroz com Frango'."


# models.py

# ... (todos os seus outros modelos) ...


class Motorista(db.Model):
    __tablename__ = "motorista"  # Renomeia a tabela no banco de dados
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)

    # NOVOS CAMPOS ADICIONADOS
    tipo_vinculo = db.Column(db.String(50))  # Efetivo, Contratado, Terceirizado
    secretaria = db.Column(db.String(150))  # Secretaria a que pertence

    rg = db.Column(db.String(20))
    cpf = db.Column(db.String(14), unique=True)
    endereco = db.Column(db.String(250))
    telefone = db.Column(db.String(20))
    cnh_numero = db.Column(db.String(20))
    cnh_categoria = db.Column(db.String(5))
    cnh_validade = db.Column(db.Date)
    rota_descricao = db.Column(db.String(300))
    turno = db.Column(db.String(50))
    veiculo_modelo = db.Column(db.String(100))
    veiculo_ano = db.Column(db.Integer)
    veiculo_placa = db.Column(db.String(10))
    documentos = db.relationship(
        "DocumentoMotorista",
        backref="motorista",
        lazy=True,
        cascade="all, delete-orphan",
    )


class DocumentoMotorista(db.Model):
    __tablename__ = "documento_motorista"  # Renomeia a tabela no banco de dados
    id = db.Column(db.Integer, primary_key=True)
    motorista_id = db.Column(db.Integer, db.ForeignKey("motorista.id"), nullable=False)
    tipo_documento = db.Column(db.String(100), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class GAM(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    servidor_num_contrato = db.Column(db.String(50), db.ForeignKey("servidor.num_contrato"), nullable=False)
    servidor = db.relationship("Servidor", backref="gams", foreign_keys=[servidor_num_contrato])

    # --- CAMPOS DETALHADOS DO FORMULÁRIO ---
    # Seção "Observações da Chefia"
    texto_inicial_observacoes = db.Column(db.Text, nullable=True) # "A requerente é efetiva..."

    # Seção do Laudo Médico
    data_laudo = db.Column(db.Date, nullable=True) # "datada do dia..."
    medico_laudo = db.Column(db.String(200), nullable=True) # "o médico psiquiatra..."
    dias_afastamento_laudo = db.Column(db.Integer, nullable=True) # "recomenda 90 dias..."
    justificativa_laudo = db.Column(db.Text, nullable=True) # "pois declara que a servidora..."

    # Seção do CID e Encaminhamento
    cid10 = db.Column(db.String(20), nullable=True)
    
    data_emissao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(50), nullable=False, default="Emitida")
