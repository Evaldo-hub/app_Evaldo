from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime, date, time
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
import os
import json
from functools import wraps
from urllib.parse import quote
from flask import jsonify
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

# Importar serviços
try:
    from ia_service import ia_service
except ImportError as e:
    print(f"AVISO: IA Service não disponível: {e}")
    ia_service = None

try:
    from rag_service import rag_service
except ImportError as e:
    print(f"AVISO: RAG Service não disponível: {e}")
    rag_service = None

# ================= CONFIGURAÇÃO =================
app = Flask(__name__, static_folder='static')

app.config['SECRET_KEY'] = os.environ.get(
    'SECRET_KEY',
    'dev-secret-key-change-in-production'
)

# ================= ROTAS PWA =================
@app.route("/manifest.json")
def manifest():
    return app.send_static_file("manifest.json")

# ================= BANCO DE DADOS =================
db_url = os.environ.get("DATABASE_URL")

# 🔥 CORREÇÃO AQUI
if db_url:
    db_url = db_url.strip()

# Permite rodar local com SQLite
if not db_url:
    db_url = "sqlite:///ebserh_study.db"
    print("DATABASE_URL nao encontrada. Usando SQLite local.")

# Corrige padrão antigo do Render
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Inicializar SQLAlchemy
db = SQLAlchemy(app)

def init_db():
    """Inicializa o banco de dados"""
    try:
        if db_url.startswith('sqlite'):
            # SQLite local
            import sqlite3
            conn = sqlite3.connect("ebserh_study.db")
            cursor = conn.cursor()
            
            # Tabela de questões
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS questoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    disciplina TEXT NOT NULL,
                    semana INTEGER NOT NULL,
                    nivel TEXT NOT NULL CHECK (nivel IN ('Básico', 'Alto', 'Pegadinha')),
                    banca TEXT NOT NULL,
                    enunciado TEXT NOT NULL,
                    alternativas TEXT NOT NULL,
                    resposta_correta TEXT NOT NULL,
                    comentario TEXT NOT NULL
                )
            ''')
            
            # Tabela de desempenho
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS desempenho (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    questao_id INTEGER NOT NULL,
                    resposta_usuario TEXT NOT NULL,
                    acerto BOOLEAN NOT NULL,
                    data_resposta TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabela do plano de estudos
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS plano_estudos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    semana INTEGER NOT NULL UNIQUE,
                    conteudo TEXT NOT NULL,
                    disciplinas TEXT NOT NULL
                )
            ''')
            
            # Tabela de feedback da IA
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ia_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    questao_id INTEGER NOT NULL,
                    tipo TEXT NOT NULL,
                    conteudo TEXT NOT NULL,
                    utilidade INTEGER DEFAULT 0,
                    data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            print("Banco SQLite inicializado com sucesso!")
            
        else:
            # PostgreSQL - criar tabelas manualmente
            print("Criando tabelas no PostgreSQL...")
            
            # Tabela de questões
            db.session.execute(text('''
                CREATE TABLE IF NOT EXISTS questoes (
                    id BIGSERIAL PRIMARY KEY,
                    disciplina TEXT NOT NULL,
                    semana INTEGER NOT NULL,
                    nivel TEXT NOT NULL CHECK (nivel IN ('Básico', 'Alto', 'Pegadinha')),
                    banca TEXT NOT NULL,
                    enunciado TEXT NOT NULL,
                    alternativas TEXT NOT NULL,
                    resposta_correta TEXT NOT NULL,
                    comentario TEXT NOT NULL
                )
            '''))
            
            # Tabela de desempenho
            db.session.execute(text('''
                CREATE TABLE IF NOT EXISTS desempenho (
                    id BIGSERIAL PRIMARY KEY,
                    questao_id INTEGER NOT NULL,
                    resposta_usuario TEXT NOT NULL,
                    acerto BOOLEAN NOT NULL,
                    data_resposta TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            '''))
            
            # Tabela do plano de estudos
            db.session.execute(text('''
                CREATE TABLE IF NOT EXISTS plano_estudos (
                    id BIGSERIAL PRIMARY KEY,
                    semana INTEGER NOT NULL UNIQUE,
                    conteudo TEXT NOT NULL,
                    disciplinas TEXT NOT NULL
                )
            '''))
            
            # Tabela de feedback da IA
            db.session.execute(text('''
                CREATE TABLE IF NOT EXISTS ia_feedback (
                    id BIGSERIAL PRIMARY KEY,
                    questao_id INTEGER NOT NULL,
                    tipo TEXT NOT NULL,
                    conteudo TEXT NOT NULL,
                    utilidade INTEGER DEFAULT 0,
                    data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            '''))
            
            db.session.commit()
            print("Banco PostgreSQL inicializado com sucesso!")
            
    except Exception as e:
        print(f"Erro ao inicializar banco: {e}")
        raise e

def execute_query(query, params=None, fetch_one=False, fetch_all=True, commit=False):
    """Executa query de forma consistente em SQLite e PostgreSQL"""
    try:
        if db_url.startswith('sqlite'):
            # SQLite local
            import sqlite3
            conn = sqlite3.connect("ebserh_study.db")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if params is None:
                result = cursor.execute(query)
            else:
                result = cursor.execute(query, params)
            
            # Fazer commit automaticamente para INSERT/UPDATE/DELETE
            if commit or any(keyword in query.upper() for keyword in ['INSERT', 'UPDATE', 'DELETE']):
                conn.commit()
            
            if fetch_one:
                data = result.fetchone()
                if data:
                    data = dict(data)  # Converter Row para dict
            elif fetch_all:
                data = result.fetchall()
                data = [dict(row) for row in data]  # Converter cada Row para dict
            else:
                data = result.rowcount if hasattr(result, 'rowcount') else 0
            
            conn.close()
            return data
        else:
            # PostgreSQL via SQLAlchemy
            if params is None:
                result = db.session.execute(text(query))
            else:
                # Garantir que params seja dicionário para PostgreSQL
                if isinstance(params, list):
                    # Converter lista para dicionário baseado em posição
                    param_dict = {}
                    for i, param in enumerate(params):
                        param_dict[f'param_{i}'] = param
                    # Substituir ? por :param_i na query
                    pg_query = query
                    for i in range(len(params)):
                        pg_query = pg_query.replace('?', f':param_{i}', 1)
                    result = db.session.execute(text(pg_query), param_dict)
                else:
                    result = db.session.execute(text(query), params)
            
            # Fazer commit automaticamente para INSERT/UPDATE/DELETE
            if commit or any(keyword in query.upper() for keyword in ['INSERT', 'UPDATE', 'DELETE']):
                db.session.commit()
            
            if fetch_one:
                data = result.fetchone()
                if data:
                    data = dict(data)  # Converter Row para dict
            elif fetch_all:
                data = result.fetchall()
                data = [dict(row) for row in data]  # Converter cada Row para dict
            else:
                data = result.rowcount if hasattr(result, 'rowcount') else 0
            
            return data
            
    except Exception as e:
        print(f"Erro na query: {query}, params: {params}, erro: {e}")
        raise e

# Adicionar filtro personalizado para JSON
@app.template_filter('from_json')
def from_json(value):
    import json
    return json.loads(value)

# ================= ROTAS PRINCIPAIS =================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/plano')
def plano():
    try:
        plano = execute_query('SELECT * FROM plano_estudos ORDER BY semana')
        return render_template('plano.html', plano=plano)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/questoes')
def questoes():
    disciplina = request.args.get('disciplina', '')
    semana = request.args.get('semana', '')
    nivel = request.args.get('nivel', '')
    
    try:
        # Obter disciplinas
        disciplinas = execute_query('SELECT DISTINCT disciplina FROM questoes ORDER BY disciplina')
        
        # Obter semanas
        semanas = execute_query('SELECT DISTINCT semana FROM questoes ORDER BY semana')
        
        # Construir query de questões com filtros
        query = 'SELECT * FROM questoes WHERE 1=1'
        params = []
        
        if disciplina:
            query += ' AND disciplina = ?'
            params.append(disciplina)
        
        if semana:
            query += ' AND semana = ?'
            params.append(semana)
        
        if nivel:
            query += ' AND nivel = ?'
            params.append(nivel)
        
        query += ' ORDER BY disciplina, semana, nivel'
        
        questoes = execute_query(query, params)
        
        return render_template('questoes.html', 
                             questoes=questoes, 
                             disciplinas=disciplinas,
                             semanas=semanas,
                             filtros={'disciplina': disciplina, 'semana': semana, 'nivel': nivel})
                             
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/questao/<int:questao_id>')
def questao_detalhe(questao_id):
    try:
        questao = execute_query('SELECT * FROM questoes WHERE id = ?', [questao_id], fetch_one=True)
        
        if questao is None:
            return "Questão não encontrada", 404
        
        return render_template('questao.html', questao=questao)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/responder', methods=['POST'])
def responder_questao():
    questao_id = request.form.get('questao_id')
    resposta = request.form.get('resposta')
    
    try:
        questao = execute_query('SELECT * FROM questoes WHERE id = ?', [questao_id], fetch_one=True)
        
        acerto = resposta == questao['resposta_correta']
        
        # Registrar resposta
        execute_query('''
            INSERT INTO desempenho (questao_id, resposta_usuario, acerto)
            VALUES (?, ?, ?)
        ''', [questao_id, resposta, acerto], fetch_all=False, commit=True)
        
        return jsonify({
            'acerto': acerto,
            'resposta_correta': questao['resposta_correta'],
            'comentario': questao['comentario']
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/desempenho')
def desempenho():
    try:
        # Estatísticas gerais
        stats = execute_query('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN acerto = 1 THEN 1 ELSE 0 END) as acertos,
                ROUND(SUM(CASE WHEN acerto = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as percentual_acerto
            FROM desempenho
        ''', fetch_one=True)
        
        # Desempenho por disciplina
        desempenho_disciplina = execute_query('''
            SELECT 
                q.disciplina,
                COUNT(*) as total,
                SUM(CASE WHEN d.acerto = 1 THEN 1 ELSE 0 END) as acertos,
                ROUND(SUM(CASE WHEN d.acerto = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as percentual_acerto
            FROM desempenho d
            JOIN questoes q ON d.questao_id = q.id
            GROUP BY q.disciplina
            ORDER BY percentual_acerto DESC
        ''')
        
        # Erros recorrentes
        erros_recorrentes = execute_query('''
            SELECT 
                q.disciplina,
                q.nivel,
                COUNT(*) as erros,
                q.enunciado
            FROM desempenho d
            JOIN questoes q ON d.questao_id = q.id
            WHERE d.acerto = 0
            GROUP BY q.id
            HAVING erros > 1
            ORDER BY erros DESC
            LIMIT 10
        ''')
        
        return render_template('desempenho.html', 
                             stats=stats,
                             desempenho_disciplina=desempenho_disciplina,
                             erros_recorrentes=erros_recorrentes)
                             
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/simulado')
def simulado():
    return render_template('simulado.html')

@app.route('/gerar_simulado', methods=['POST'])
def gerar_simulado():
    num_questoes = int(request.form.get('num_questoes', 10))
    disciplinas = request.form.getlist('disciplinas')
    niveis = request.form.getlist('niveis')
    
    try:
        query = 'SELECT * FROM questoes WHERE 1=1'
        params = []
        
        if disciplinas:
            placeholders = ','.join(['?' for _ in disciplinas])
            query += f' AND disciplina IN ({placeholders})'
            params.extend(disciplinas)
        
        if niveis:
            placeholders = ','.join(['?' for _ in niveis])
            query += f' AND nivel IN ({placeholders})'
            params.extend(niveis)
        
        questoes_disponiveis = execute_query(query, params)
        
        # Selecionar questões aleatórias
        import random
        questoes_simulado = random.sample(
            [dict(q) for q in questoes_disponiveis], 
            min(num_questoes, len(questoes_disponiveis))
        )
        
        # Armazenar simulado na sessão
        session['simulado_atual'] = questoes_simulado
        session['simulado_index'] = 0
        
        return redirect(url_for('realizar_simulado'))
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/realizar_simulado')
def realizar_simulado():
    if 'simulado_atual' not in session:
        return redirect(url_for('simulado'))
    
    questoes = session['simulado_atual']
    index = session.get('simulado_index', 0)
    
    if index >= len(questoes):
        return redirect(url_for('resultado_simulado'))
    
    questao_atual = questoes[index]
    
    return render_template('simulado_questao.html', 
                         questao=questao_atual, 
                         numero=index + 1, 
                         total=len(questoes))

@app.route('/responder_simulado', methods=['POST'])
def responder_simulado():
    if 'simulado_atual' not in session:
        return redirect(url_for('simulado'))
    
    resposta = request.form.get('resposta')
    questao_id = request.form.get('questao_id')
    
    # Registrar resposta do simulado
    if 'respostas_simulado' not in session:
        session['respostas_simulado'] = []
    
    session['respostas_simulado'].append({
        'questao_id': questao_id,
        'resposta': resposta
    })
    
    # Avançar para próxima questão
    session['simulado_index'] = session.get('simulado_index', 0) + 1
    
    return redirect(url_for('realizar_simulado'))

@app.route('/resultado_simulado')
def resultado_simulado():
    if 'simulado_atual' not in session or 'respostas_simulado' not in session:
        return redirect(url_for('simulado'))
    
    questoes = session['simulado_atual']
    respostas = session['respostas_simulado']
    
    acertos = 0
    resultados = []
    
    for i, resposta in enumerate(respostas):
        questao = questoes[i]
        questao_db = execute_query('SELECT * FROM questoes WHERE id = ?', [questao['id']], fetch_one=True)
        
        acerto = resposta['resposta'] == questao_db['resposta_correta']
        if acerto:
            acertos += 1
        
        resultados.append({
            'questao': dict(questao_db),
            'resposta_usuario': resposta['resposta'],
            'acerto': acerto
        })
    
    percentual = round((acertos / len(questoes)) * 100, 2)
    
    # Limpar sessão do simulado
    session.pop('simulado_atual', None)
    session.pop('simulado_index', None)
    session.pop('respostas_simulado', None)
    
    return render_template('resultado_simulado.html', 
                         resultados=resultados,
                         acertos=acertos,
                         total=len(questoes),
                         percentual=percentual)

# ==================== ROTAS DA IA ====================

@app.route('/ia/explicar_erro/<int:questao_id>', methods=['POST'])
def ia_explicar_erro(questao_id):
    """Rota para IA explicar erro do aluno"""
    try:
        data = request.get_json()
        resposta_usuario = data.get('resposta_usuario', '')
        
        questao = execute_query('SELECT * FROM questoes WHERE id = ?', [questao_id], fetch_one=True)
        
        if not questao:
            return jsonify({'error': 'Questão não encontrada'}), 404
        
        # Montar dicionário da questão
        questao_dict = dict(questao)
        questao_dict['alternativas'] = json.loads(questao_dict['alternativas'])
        
        # Gerar explicação com IA
        if not ia_service:
            return jsonify({'error': 'IA Service não disponível'}), 503
        
        explicacao = ia_service.explicar_erro(questao_dict, resposta_usuario)
        
        # Salvar feedback da IA
        execute_query('''
            INSERT INTO ia_feedback (questao_id, tipo, conteudo)
            VALUES (?, ?, ?)
        ''', [questao_id, 'explicacao_erro', explicacao], fetch_all=False, commit=True)
        
        return jsonify({
            'explicacao': explicacao,
            'status': 'sucesso'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/ia/gerar_dica/<int:questao_id>', methods=['POST'])
def ia_gerar_dica(questao_id):
    """Rota para IA gerar dica de memória"""
    try:
        questao = execute_query('SELECT * FROM questoes WHERE id = ?', [questao_id], fetch_one=True)
        
        if not questao:
            return jsonify({'error': 'Questão não encontrada'}), 404
        
        # Montar dicionário da questão
        questao_dict = dict(questao)
        questao_dict['alternativas'] = json.loads(questao_dict['alternativas'])
        
        # Gerar dica com IA
        if not ia_service:
            return jsonify({'error': 'IA Service não disponível'}), 503
        
        dica = ia_service.gerar_dica_memoria(questao_dict)
        
        # Salvar feedback da IA
        execute_query('''
            INSERT INTO ia_feedback (questao_id, tipo, conteudo)
            VALUES (?, ?, ?)
        ''', [questao_id, 'dica_memoria', dica], fetch_all=False, commit=True)
        
        return jsonify({
            'dica': dica,
            'status': 'sucesso'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/ia/sugerir_revisao', methods=['POST'])
def ia_sugerir_revisao():
    """Rota para IA sugerir plano de revisão baseado em erros"""
    try:
        # Obter erros recentes do usuário
        erros_data = execute_query('''
            SELECT q.* FROM desempenho d
            JOIN questoes q ON d.questao_id = q.id
            WHERE d.acerto = 0
            ORDER BY d.data_resposta DESC
            LIMIT 10
        ''')
        
        # Montar lista de erros
        erros_recentes = []
        for erro_data in erros_data:
            erro_dict = dict(erro_data)
            erro_dict['alternativas'] = json.loads(erro_dict['alternativas'])
            erros_recentes.append(erro_dict)
        
        # Gerar sugestão com IA
        if not ia_service:
            return jsonify({'error': 'IA Service não disponível'}), 503
        
        sugestao = ia_service.sugerir_revisao(erros_recentes)
        
        return jsonify({
            'sugestao': sugestao,
            'total_erros': len(erros_recentes),
            'status': 'sucesso'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/ia/gerar_questoes', methods=['POST'])
def ia_gerar_questoes():
    """Rota para IA gerar questões inéditas (função admin)"""
    try:
        data = request.get_json()
        disciplina = data.get('disciplina', '')
        nivel = data.get('nivel', 'Básico')
        quantidade = data.get('quantidade', 1)
        
        # Gerar questões com IA
        if not ia_service:
            return jsonify({'error': 'IA Service não disponível'}), 503
        
        questoes_geradas = ia_service.gerar_questao_inedita(disciplina, nivel, quantidade)
        
        return jsonify({
            'questoes': questoes_geradas,
            'status': 'sucesso'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/importar')
def importar():
    """Página de importação automática de questões"""
    return render_template('importar.html')

@app.route('/ia/importar_questao_texto', methods=['POST'])
def ia_importar_questao_texto():
    """Importa questão automaticamente a partir de texto colado"""
    try:
        print("DEBUG: Rota /ia/importar_questao_texto chamada")
        
        if not request.is_json:
            print("DEBUG: Request não é JSON")
            return jsonify({'error': 'Request deve ser JSON'}), 400
        
        data = request.get_json()
        print(f"DEBUG: JSON recebido: {data}")
        
        if not data:
            print("DEBUG: JSON está vazio")
            return jsonify({'error': 'JSON está vazio'}), 400
        
        texto_questao = data.get('texto', '')
        disciplina = data.get('disciplina', 'Lei 12.550/2011')
        nivel = data.get('nivel', 'Básico')
        semana = data.get('semana', '1')
        banca = data.get('banca', 'CESPE')
        tipo = data.get('tipo', 'Múltipla Escolha')
        
        print(f"DEBUG: texto_questao: '{texto_questao[:100]}...'")
        print(f"DEBUG: disciplina: {disciplina}")
        print(f"DEBUG: nivel: {nivel}")
        print(f"DEBUG: semana: {semana}")
        print(f"DEBUG: banca: {banca}")
        print(f"DEBUG: tipo: {tipo}")
        
        if not texto_questao or texto_questao.strip() == '':
            print("DEBUG: Texto da questão está vazio")
            return jsonify({'error': 'Texto da questão não fornecido'}), 400
        
        # Importar questão usando o serviço de IA
        if not ia_service:
            return jsonify({'error': 'IA Service não disponível'}), 503
        
        print("DEBUG: Chamando ia_service.importar_questao_texto")
        questao = ia_service.importar_questao_texto(texto_questao, disciplina, nivel)
        
        print(f"DEBUG: Questão parseada: {questao}")
        
        if not questao:
            print("DEBUG: Não foi possível parsear a questão")
            return jsonify({'error': 'Não foi possível parsear a questão. Verifique o formato.'}), 400
        
        # Adicionar metadados da questão
        questao['semana'] = semana
        questao['banca'] = banca
        questao['tipo'] = tipo
        
        # Armazenar temporariamente para salvar depois
        session['questao_temp'] = questao
        
        print("DEBUG: Questão importada com sucesso")
        
        return jsonify({
            'status': 'sucesso',
            'questao': questao,
            'mensagem': f'Questão importada com sucesso para {disciplina} - {nivel}'
        })
        
    except Exception as e:
        print(f"DEBUG: Exceção: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/ia/salvar_questao_importada', methods=['POST'])
def ia_salvar_questao_importada():
    """Salva a questão importada no banco de dados"""
    try:
        data = request.get_json()
        
        # Obter questão temporária da sessão
        questao_temp = session.get('questao_temp')
        if not questao_temp:
            return jsonify({'error': 'Nenhuma questão para salvar. Importe uma questão primeiro.'}), 400
        
        # Atualizar metadados com os dados do formulário
        disciplina = data.get('disciplina', questao_temp.get('disciplina', 'Lei 12.550/2011'))
        semana = data.get('semana', questao_temp.get('semana', '1'))
        banca = data.get('banca', questao_temp.get('banca', 'CESPE'))
        nivel = data.get('nivel', questao_temp.get('nivel', 'Básico'))
        tipo = data.get('tipo', questao_temp.get('tipo', 'Múltipla Escolha'))
        
        # Salvar no banco de dados
        execute_query('''
            INSERT INTO questoes (
                disciplina, semana, nivel, banca, enunciado, 
                alternativas, resposta_correta, comentario
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', [
            disciplina,
            int(semana),
            nivel,
            banca,
            questao_temp['enunciado'],
            json.dumps(questao_temp['alternativas']),
            questao_temp['resposta'],
            questao_temp.get('comentario', 'Questão importada automaticamente')
        ], fetch_all=False, commit=True)
        
        # Obter ID da questão inserida
        if db_url.startswith('sqlite'):
            import sqlite3
            conn = sqlite3.connect("ebserh_study.db")
            cursor = conn.cursor()
            cursor.execute("SELECT last_insert_rowid()")
            questao_id = cursor.fetchone()[0]
            conn.close()
        else:
            result = db.session.execute(text('SELECT lastval()'))
            questao_id = result.scalar()
        
        # Limpar sessão
        session.pop('questao_temp', None)
        
        return jsonify({
            'status': 'sucesso',
            'questao_id': questao_id,
            'mensagem': 'Questão salva com sucesso!'
        })
        
    except Exception as e:
        print(f"DEBUG: Erro ao salvar questão: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/ia/feedback', methods=['POST'])
def ia_feedback():
    """Rota para registrar feedback do usuário sobre a IA"""
    try:
        data = request.get_json()
        questao_id = data.get('questao_id')
        tipo = data.get('tipo')  # explicacao_erro, dica_memoria, etc.
        utilidade = data.get('utilidade', 0)  # 1-5
        
        # Atualizar feedback existente ou registrar novo
        execute_query('''
            UPDATE ia_feedback 
            SET utilidade = ?
            WHERE questao_id = ? AND tipo = ?
            ORDER BY data DESC
            LIMIT 1
        ''', [utilidade, questao_id, tipo], fetch_all=False)
        
        return jsonify({'status': 'feedback_registrado'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== ROTAS ADMIN ====================

@app.route('/admin')
def admin():
    """Painel administrativo para gerenciamento de questões"""
    return render_template('admin.html')

@app.route('/admin/adicionar_questoes', methods=['POST'])
def admin_adicionar_questoes():
    """Adiciona questões geradas pela IA ao banco"""
    try:
        data = request.get_json()
        questoes = data.get('questoes', [])
        
        if not questoes:
            return jsonify({'error': 'Nenhuma questão para adicionar'}), 400
        
        adicionadas = 0
        for questao in questoes:
            # Validação básica
            if not all(key in questao for key in ['disciplina', 'enunciado', 'alternativas', 'resposta_correta']):
                continue
            
            # Adicionar semana padrão (última semana)
            max_semana_result = execute_query('SELECT MAX(semana) FROM questoes', fetch_one=True)
            max_semana = max_semana_result['MAX(semana)'] or 12
            
            execute_query('''
                INSERT INTO questoes (
                    disciplina, semana, nivel, banca, enunciado, 
                    alternativas, resposta_correta, comentario
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', [
                questao['disciplina'],
                max_semana,
                questao.get('nivel', 'Básico'),
                questao.get('banca', 'IA-Gerada'),
                questao['enunciado'],
                json.dumps(questao['alternativas']),
                questao['resposta_correta'],
                questao.get('comentario', 'Questão gerada por IA')
            ], fetch_all=False, commit=True)
            adicionadas += 1
        
        return jsonify({
            'status': 'sucesso',
            'adicionadas': adicionadas,
            'total_recebidas': len(questoes)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/estatisticas')
def api_estatisticas():
    """API para estatísticas do banco de questões"""
    try:
        # Total de questões
        total_questoes_result = execute_query('SELECT COUNT(*) as total FROM questoes', fetch_one=True)
        total_questoes = total_questoes_result['total']
        
        # Questões geradas por IA
        questoes_ia_result = execute_query('SELECT COUNT(*) as total FROM questoes WHERE banca = "IA-Gerada"', fetch_one=True)
        questoes_ia = questoes_ia_result['total']
        
        # Número de disciplinas
        disciplinas_result = execute_query('SELECT COUNT(DISTINCT disciplina) as total FROM questoes', fetch_one=True)
        disciplinas = disciplinas_result['total']
        
        # Questões pegadinha
        pegadinhas_result = execute_query('SELECT COUNT(*) as total FROM questoes WHERE nivel = "Pegadinha"', fetch_one=True)
        pegadinhas = pegadinhas_result['total']
        
        return jsonify({
            'total_questoes': total_questoes,
            'questoes_ia': questoes_ia,
            'disciplinas': disciplinas,
            'pegadinhas': pegadinhas
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/limpar_questoes_ia', methods=['POST'])
def admin_limpar_questoes_ia():
    """Remove questões geradas por IA (função de limpeza)"""
    try:
        execute_query('DELETE FROM questoes WHERE banca = "IA-Gerada"', fetch_all=False)
        
        return jsonify({
            'status': 'sucesso',
            'message': 'Questões IA removidas com sucesso!'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== ROTAS DE HEALTH CHECK ====================

@app.route('/health')
def health_check():
    """Health check para Render"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'environment': os.getenv('FLASK_ENV', 'development')
    }), 200

@app.route('/init_db')
def init_db_route():
    """Rota para inicializar banco de dados via web"""
    try:
        init_db()
        return jsonify({
            'status': 'sucesso',
            'message': 'Banco de dados inicializado com sucesso!'
        })
    except Exception as e:
        return jsonify({
            'status': 'erro',
            'message': f'Erro ao inicializar banco: {str(e)}'
        }), 500

# ==================== INICIALIZAÇÃO ====================

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
