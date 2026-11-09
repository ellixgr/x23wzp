from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import uuid
import re
from urllib.parse import urlparse

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
ADMIN_SENHA = os.getenv('ADMIN_SENHA', 'admin123')

client = MongoClient(os.getenv('MONGO_URI'))
db = client['video_site']
videos_collection = db['videos']

# ==========================================
# LOGIN
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('senha') == ADMIN_SENHA:
            session['admin_logado'] = True
            return redirect(url_for('dashboard'))
        return render_template('painel_login.html', erro='Senha incorreta')
    return render_template('painel_login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

def requer_login(p):
    def verifica(*args, **kwargs):
        if not session.get('admin_logado'):
            return redirect(url_for('login'))
        return p(*args, **kwargs)
    verifica.__name__ = p.__name__
    return verifica

# ==========================================
# PAINEL PRINCIPAL
# ==========================================
@app.route('/')
@requer_login
def dashboard():
    videos = list(videos_collection.find().sort('criado_em', -1))
    return render_template('painel.html', videos=videos)

# ==========================================
# ADICIONAR VÍDEO
# ==========================================
@app.route('/adicionar', methods=['GET', 'POST'])
@requer_login
def adicionar():
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        link_embed = request.form.get('link_embed')
        link_download = request.form.get('link_download', '')
        capa_url = request.form.get('capa_url', '')
        
        if not titulo or not link_embed:
            return render_template('painel_adicionar.html', erro='Preencha título e link do vídeo')
        
        videos_collection.insert_one({
            'id': str(uuid.uuid4()),
            'titulo': titulo,
            'link_embed': link_embed,
            'link_download': link_download,
            'capa_url': capa_url,
            'ativo': True,
            'criado_em': request.form.headers.get('Date', '')
        })
        return redirect(url_for('dashboard'))
    return render_template('painel_adicionar.html')

# ==========================================
# EXCLUIR VÍDEO
# ==========================================
@app.route('/excluir/<video_id>')
@requer_login
def excluir(video_id):
    videos_collection.delete_one({'id': video_id})
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 10001)))
