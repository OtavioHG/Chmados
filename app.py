import os
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = '123'  # Chave secreta para CSRF e sessões
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///suporte.db'  # URL do banco de dados
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Desativa as notificações de modificação
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')  # Pasta de uploads para arquivos anexados

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # Define a view para login

# Modelo de Usuário
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

    def __init__(self, email, password):
        self.email = email
        self.password = generate_password_hash(password)  # Armazena o hash da senha no banco de dados

    def verify_password(self, password):
        return check_password_hash(self.password, password)  # Verifica se a senha fornecida corresponde ao hash

# Modelo de Chamado
class Chamado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tipo_pedido = db.Column(db.String(50), nullable=False)
    prioridade_do_chamado = db.Column(db.Integer, nullable=False)
    tipo_do_chamado = db.Column(db.String(50), nullable=False)
    assunto_do_chamado = db.Column(db.String(50), nullable=False)
    descricao_do_chamado = db.Column(db.Text, nullable=False)
    arquivo_anexo = db.Column(db.String(255))
    status = db.Column(db.String(20), nullable=False, default='Aberto')
    mensagens = db.relationship('Mensagem', backref='chamado', cascade='all, delete-orphan')

# Modelo de Mensagem
class Mensagem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    remetente_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    destinatario_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    mensagem = db.Column(db.Text, nullable=False)
    data_envio = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    chamado_id = db.Column(db.Integer, db.ForeignKey('chamado.id', ondelete='CASCADE'), nullable=False)

    remetente = db.relationship('User', foreign_keys=[remetente_id])
    destinatario = db.relationship('User', foreign_keys=[destinatario_id])

# Carrega o usuário no Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Cria o banco de dados
with app.app_context():
    db.create_all()

# Verifica e cria o diretório de uploads, se necessário
uploads_dir = app.config['UPLOAD_FOLDER']
if not os.path.exists(uploads_dir):
    os.makedirs(uploads_dir)

# Rota de login
@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and user.verify_password(password):
            login_user(user)
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Credenciais incorretas!!! Favor tentar novamente.', 'error')

    return render_template('login.html')

# Rota de registro
@app.route("/registro", methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        # Validação simples de email e senha
        if not email or not password:
            flash('Por favor, preencha todos os campos.', 'error')
            return redirect(url_for('registro'))
        
        # Verifica se o email já está cadastrado
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Já existe uma conta com este email. Por favor, faça login.', 'error')
            return redirect(url_for('login'))
        
        # Cria um novo usuário
        new_user = User(email=email, password=password)

        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Registro realizado com sucesso! Faça login para continuar.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Erro ao registrar: {str(e)}', 'error')
            return redirect(url_for('registro'))

    return render_template('registro.html')

# Rota de logout
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash('Logout realizado com sucesso!', 'success')
    return redirect(url_for('index'))

# Rota inicial
@app.route("/", methods=['GET', 'POST'])
def index():
    return render_template("index.html")

# Rota para criar um novo chamado
@app.route("/criar_chamado", methods=['GET', 'POST'])
@login_required
def criar_chamado():
    if request.method == 'POST':
        tipo_pedido = request.form['tipo_pedido']
        prioridade_do_chamado = int(request.form['prioridade_do_chamado'])
        tipo_do_chamado = request.form['tipo_do_chamado']
        assunto_do_chamado = request.form['assunto_do_chamado'][:50]
        descricao_do_chamado = request.form['descricao_do_chamado'].strip()
        arquivo = request.files['arquivo_anexo']

        try:
            caminho_arquivo = None
            if arquivo and arquivo.filename != '':
                if arquivo.filename.split('.')[-1].lower() not in ['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'mp3', 'mp4']:
                    flash('Tipo de arquivo não permitido. Tipos permitidos: txt, pdf, png, jpg, jpeg, gif, zip, mp3, mp4', 'error')
                    return redirect(url_for('criar_chamado'))

                filename = secure_filename(arquivo.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                arquivo.save(filepath)
                caminho_arquivo = filename  # Salva apenas o nome do arquivo

            chamado = Chamado(
                cliente_id=current_user.id,
                tipo_pedido=tipo_pedido,
                prioridade_do_chamado=prioridade_do_chamado,
                tipo_do_chamado=tipo_do_chamado,
                assunto_do_chamado=assunto_do_chamado,
                descricao_do_chamado=descricao_do_chamado,
                arquivo_anexo=caminho_arquivo,
                status='Aberto'
            )
            db.session.add(chamado)
            db.session.commit()
            flash('Chamado criado com sucesso!', 'success')
            return redirect(url_for('meus_chamados'))

        except Exception as e:
            db.session.rollback()  # Reverte qualquer alteração pendente no banco de dados
            flash(f'Erro ao criar chamado: {str(e)}', 'error')

    return render_template('criar_chamado.html')

# Rota para listar os chamados do usuário atual
@app.route("/meus_chamados")
@login_required
def meus_chamados():
    chamados = Chamado.query.filter_by(cliente_id=current_user.id).all()
    return render_template('meus_chamados.html', chamados=chamados)

# Rota para visualizar mensagens de um chamado específico
@app.route("/chamado/<int:chamado_id>/mensagens")
@login_required
def visualizar_mensagens(chamado_id):
    chamado = Chamado.query.get_or_404(chamado_id)
    # Garante que apenas os participantes do chamado podem visualizar as mensagens
    if current_user.id != chamado.cliente_id:
        abort(403)

    return render_template('mensagens.html', chamado=chamado)

# Rota para enviar mensagens para um chamado específico
@app.route("/chamado/<int:chamado_id>/enviar_mensagem", methods=['POST'])
@login_required
def enviar_mensagem(chamado_id):
    chamado = Chamado.query.get_or_404(chamado_id)
    destinatario_id = chamado.cliente_id if current_user.id != chamado.cliente_id else chamado.cliente_id
    mensagem = request.form['mensagem']

    nova_mensagem = Mensagem(
        remetente_id=current_user.id,
        destinatario_id=destinatario_id,
        mensagem=mensagem,
        chamado_id=chamado_id
    )

    try:
        db.session.add(nova_mensagem)
        db.session.commit()
        flash('Mensagem enviada com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao enviar mensagem: {str(e)}', 'error')

    return redirect(url_for('visualizar_mensagens', chamado_id=chamado_id))


# Rota para deletar um chamado
@app.route("/deletar_chamado/<int:chamado_id>", methods=['POST'])
@login_required
def deletar_chamado(chamado_id):
    chamado = Chamado.query.get_or_404(chamado_id)
    # Verifica se o usuário atual é o proprietário do chamado
    if chamado.cliente_id != current_user.id:
        abort(403)
    
    # Verifica se o chamado tem um arquivo anexado
    if chamado.arquivo_anexo:
        try:
            # Constrói o caminho completo para o arquivo
            caminho_arquivo = os.path.join(app.config['UPLOAD_FOLDER'], chamado.arquivo_anexo)
            # Deleta o arquivo
            os.remove(caminho_arquivo)
        except FileNotFoundError:
            flash('Arquivo anexado não encontrado para deletar.', 'error')
        except Exception as e:
            flash(f'Erro ao deletar arquivo anexado: {str(e)}', 'error')

    # Deleta o chamado do banco de dados
    db.session.delete(chamado)
    db.session.commit()
    flash('Chamado deletado com sucesso!', 'success')
    return redirect(url_for('meus_chamados'))


if __name__ == '__main__':
    app.run(debug=True)
