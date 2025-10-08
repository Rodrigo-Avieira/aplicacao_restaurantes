from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
import os


#configuração inicial
baseDir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)

#configurando BD SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(baseDir, 'restaurante.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False #desatvando os warnings

#inicializar SQLAlchemy com o app Flask
db = SQLAlchemy(app)

#-----Modelar banco de dados-----
#tabela para os garçons
class Garcom(db.Model):
    id = db.Column(db.Integer, primary_key =True)
    nome = db.Column(db.String(100), nullable=False)
    #usar numero de celular como login
    telefone = db.Column(db.String(10), unique=True, nullable=False)
    senha_hash = db.Column(db.String(128), nullable=False)

#tabela mesas
class Mesa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Livre')#status mesa pode ser livre, ocupado, reservado
    
    #relação: uma mesa pode ter varios pedidos
    pedidos = db.relationship('Pedido', backref='mesa', lazy=True)
    
#tabela dos produtos do cardapio
class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.String(255))
    preco = db.Column(db.Float, nullable=False)
    categoria = db.Column(db.String(50), nullable=False)#pode ser: bebidas, couvert, prato_principal, sobremesa
    
#tabela principal dos pedidos (comandas)
class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), nullable=False, default='Aberto')#status aberto, fechado, reservado
    data_hora = db.Column(db.DateTime, server_default=db.func.now())
    total = db.Column(db.Float, default=0.0)
    
    #relações com chaves estrangeiras
    mesa_id = db.Column(db.Integer, db.ForeignKey('mesa.id'), nullable=False)
    garcom_id = db.Column(db.Integer, db.ForeignKey('garcom.id'), nullable=False)
    
    #relação: um pedido é composto por vários itens
    itens = db.relationship('ItemPedido', backref='pedido', lazy=True)
    
#tabela para os itens de cada pedido
class ItemPedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quantidade = db.Column(db.Integer, nullable=False, default=1)
    
    #relações com chaves estrageiras
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedido.id'), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'), nullable=False)
    
    #relação: traz os detalhes do produto para os itens
    produto = db.relationship('Produto')

#rotas da aplicação
@app.route('/')
def index():
    return "<h1>Teste servidor Flask</h1>"

#rota pagina das mesas
@app.route('/mesas')
def view_mesas():
    mesas = Mesa.query.order_by(Mesa.numero).all()
    return render_template('mesas.html', mesas=mesas)

#rota para pagina de comanda da mesa
@app.route('/mesa/<int:id_mesa>')
def view_mesa_individual(id_mesa):
    #busca mesa pelo id na url, se n econtrar puxa 404
    mesa = Mesa.query.get_or_404(id_mesa)
    return render_template('pedido.html', mesa=mesa)

#API endpoints
@app.route('/api/cardapio')
def get_cardapio():
    #pegar todos os produtos do bd
    produtos = Produto.query.all()
    
    #transforma a lista de obj Produto em um dict
    cardapio_lista = []
    for produto in produtos:
        cardapio_lista.append({
            'id' : produto.id,  
            'nome' : produto.nome,  
            'descricao' : produto.descricao, 
            'preco' : produto.preco, 
            'categoria' : produto.categoria
            })           
    return jsonify(cardapio_lista)

#adicionando pedidos com POST
@app.route('/api/pedido/adicionar', methods=['POST'])
def adicionar_item_pedido():
    #pegar os dados enviados pelo js (fetch)
    data = request.get_json()
    mesa_id = data.get('mesa_id')
    produto_id = data.get('produto_id')
    
    #validação simples
    if not mesa_id or not produto_id:
        return jsonify({'success': False, 'message': 'Faltam dados.'}), 400
    
    #busca mesa no banco de dados
    mesa = Mesa.query.get(mesa_id)
    if not mesa:
        return jsonify({'success': False, 'message': 'Mesa não encontrada.'}), 404
    
    #logica principal
    #verificar se já existe um pedido aberto pra esssa mesa
    pedido = Pedido.query.filter_by(mesa_id=mesa_id, status='aberto').first()
    
    #se Ñ tiver pedido, cria um novo
    if not pedido:
        pedido = Pedido(mesa_id=mesa_id, garcom_id=1, status='aberto')
        db.session.add(pedido)
        #se pedido criado, mesa ocupada
        mesa.status = 'ocupado'
        
    #cria novo item de pedido pra associar ao pedido
    novo_item = ItemPedido(pedido=pedido, produto_id=produto_id)
    db.session.add(novo_item)
    
    #salvando no bd
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Item adicionado com sucesso'})

#rota para atualizar comandas
@app.route('/api/pedido/aberto/<int:mesa_id>')
def get_pedido_aberto(mesa_id):
    mesa = Mesa.query.get_or_404(mesa_id)
    pedido = Pedido.query.filter_by(mesa_id=mesa_id, status='aberto').first()

    if not pedido:
        return jsonify({'itens': [], 'total': 0, 'status_mesa': mesa.status, 'pedido_id': None})

    itens = ItemPedido.query.filter_by(pedido_id=pedido.id).all()
    
    itens_pedido = []
    total = 0
    # loop na variável itens.
    for item in itens:
        produto = Produto.query.get(item.produto_id)
        if produto:
            itens_pedido.append({
                'id': item.id,
                'nome': produto.nome,
                'quantidade': item.quantidade,
                'preco_unitario': produto.preco
            })
            total += produto.preco * item.quantidade

    pedido.total = total
    db.session.commit()
    
    return jsonify({
        'pedido_id': pedido.id,
        'itens': itens_pedido, 
        'total': total,
        'status_mesa': mesa.status
    })

@app.route('/api/item/remover', methods=['POST'])
def remover_item_pedido():
    data = request.get_json()
    item_id = data.get('item_id')

    if not item_id:
        return jsonify({'success': False, 'message': 'ID do item não fornecido.'}), 400

    # Busca o item específico no banco
    item_para_remover = ItemPedido.query.get(item_id)

    if not item_para_remover:
        return jsonify({'success': False, 'message': 'Item não encontrado no pedido.'}), 404

    # Remove o item da sessão do banco de dados
    db.session.delete(item_para_remover)
    # Salva a remoção
    db.session.commit()

    return jsonify({'success': True, 'message': 'Item removido com sucesso!'})

@app.route('/api/pedido/finalizar', methods=['POST'])
def finalizar_pedido():
    data = request.get_json()
    pedido_id = data.get('pedido_id')

    pedido = Pedido.query.get(pedido_id)
    if not pedido:
        return jsonify({'success': False, 'message': 'Pedido não encontrado.'}), 404

    # Busca a mesa associada ao pedido
    mesa = Mesa.query.get(pedido.mesa_id)
    if not mesa:
        return jsonify({'success': False, 'message': 'Mesa não encontrada.'}), 404

    # Altera os status
    pedido.status = 'fechado'
    mesa.status = 'livre'

    db.session.commit()

    return jsonify({'success': True, 'message': 'Pedido finalizado com sucesso!'})

# --- teste povoando o db ---
@app.cli.command('seed')
def seed_db():
    """Povoa o banco de dados com dados iniciais."""
    
    # Apaga tudo do banco de dados para garantir um estado limpo
    db.drop_all()
    db.create_all()
    print('Banco de dados zerado e tabelas recriadas.')

    # --- Adicionar Mesas ---
    mesas_a_criar = []
    for i in range(1, 6): # Cria mesas de 1 a 5
        nova_mesa = Mesa(numero=i, status='livre')
        mesas_a_criar.append(nova_mesa)
    db.session.add_all(mesas_a_criar)
    print(f'{len(mesas_a_criar)} mesas foram criadas.')

    # --- Adicionar Produtos (Cardápio) ---
    cardapio_inicial = [
        Produto(nome='Risoto Funghi', descricao='Cremoso risoto com cogumelos funghi secchi hidratados.', preco=45.50, categoria='prato_principal'),
        Produto(nome='Refrigerante Lata', descricao='Coca-Cola, Guaraná ou outros', preco=6.00, categoria='bebida'),
        Produto(nome='Pudim de Leite', descricao='Pudim de leite condensado com calda de caramelo', preco=12.00, categoria='sobremesa')
    ]
    db.session.add_all(cardapio_inicial)
    print(f'{len(cardapio_inicial)} produtos foram adicionados ao cardápio.')
    
    # Salva todas as alterações no banco
    db.session.commit()
    print('Banco de dados populado com sucesso!')
    
#inicializando servidor
if __name__ == '__main__':
    app.run(debug=True)