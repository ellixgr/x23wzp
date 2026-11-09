from flask import Flask, render_template_string, jsonify, request, redirect, url_for, session
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import uuid
import requests
from datetime import datetime
import base64

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'sua-chave-secreta-segura')
ADMIN_SENHA = os.getenv('ADMIN_SENHA', 'admin123')

client = MongoClient(os.getenv('MONGO_URI'))
db = client['video_site']
videos_collection = db['videos']

CAPA_PADRAO = "https://files.catbox.moe/uw9r9l.png"

# ==========================================
# LOGIN DO ADMIN
# ==========================================
@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('senha') == ADMIN_SENHA:
            session['admin_logado'] = True
            return redirect(url_for('dashboard'))
        return render_template_string(LOGIN_HTML, erro='Senha incorreta')
    return render_template_string(LOGIN_HTML, erro='')

@app.route('/admin/logout')
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
# DASHBOARD DO PAINEL
# ==========================================
@app.route('/admin')
@requer_login
def dashboard():
    videos = list(videos_collection.find().sort('criado_em', -1))
    return render_template_string(DASHBOARD_HTML, videos=videos)

# ==========================================
# ADICIONAR VÍDEO (COM UPLOAD DE ARQUIVO OU LINK)
# ==========================================
@app.route('/admin/adicionar', methods=['GET', 'POST'])
@requer_login
def adicionar():
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        url_video = request.form.get('url_video')
        preco = request.form.get('preco', '10.00')
        link_thumbnail = request.form.get('thumbnail_link', '').strip()
        
        if not titulo or not url_video:
            return render_template_string(ADICIONAR_HTML, erro='Preencha o título e o link direto do vídeo!')
        
        thumbnail = CAPA_PADRAO

        # Verifica se o usuário enviou uma imagem direto da galeria
        if 'thumbnail_file' in request.files:
            file = request.files['thumbnail_file']
            if file and file.filename != '':
                # Converte a imagem da galeria para base64 para persistir com segurança no MongoDB
                img_bytes = file.read()
                encoded = base64.b64encode(img_bytes).decode('utf-8')
                mime_type = file.content_type or 'image/jpeg'
                thumbnail = f"data:{mime_type};base64,{encoded}"
        
        # Se não enviou arquivo mas digitou um link de imagem, usa o link
        if thumbnail == CAPA_PADRAO and link_thumbnail:
            thumbnail = link_thumbnail

        duracao_str = "01:30"
        tamanho_str = "25 MB"

        videos_collection.insert_one({
            'id': str(uuid.uuid4()),
            'titulo': titulo,
            'url_video': url_video,
            'thumbnail': thumbnail,
            'tamanho': tamanho_str,
            'duracao': duracao_str,
            'preco': preco,
            'ativo': True,
            'criado_em': datetime.utcnow()
        })
        return redirect(url_for('dashboard'))
        
    return render_template_string(ADICIONAR_HTML, erro='')

# ==========================================
# EXCLUIR VÍDEO
# ==========================================
@app.route('/admin/excluir/<video_id>')
@requer_login
def excluir(video_id):
    videos_collection.delete_one({'id': video_id})
    return redirect(url_for('dashboard'))

# Templates embutidos
LOGIN_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><title>Login Admin</title>
<style>body{background:#0d0d0d;color:#fff;font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;}
form{background:#161b22;padding:30px;border-radius:12px;border:1px solid #30363d;width:300px;text-align:center;}
input{width:100%;padding:10px;margin:10px 0;background:#0d1117;border:1px solid #30363d;color:#fff;border-radius:6px;}
button{width:100%;padding:10px;background:#25d366;border:none;font-weight:bold;border-radius:6px;cursor:pointer;}
.erro{color:#ff4500;font-size:13px;margin-bottom:10px;}</style>
</head>
<body>
    <form method="POST">
        <h2>Painel Admin</h2>
        {% if erro %}<div class="erro">{{ erro }}</div>{% endif %}
        <input type="password" name="senha" placeholder="Senha do Administrador" required>
        <button type="submit">Entrar</button>
    </form>
</body></html>"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><title>Dashboard Admin</title>
<style>body{background:#0d0d0d;color:#fff;font-family:sans-serif;padding:20px;max-width:800px;margin:auto;}
table{width:100%;border-collapse:collapse;margin-top:20px;background:#161b22;}
th,td{padding:12px;border:1px solid #30363d;text-align:left;font-size:14px;}
th{background:#21262d;}
a.btn{background:#25d366;color:#000;padding:8px 12px;text-decoration:none;border-radius:6px;font-weight:bold;font-size:13px;}
a.btn-del{background:#da3633;color:#fff;padding:6px 10px;text-decoration:none;border-radius:4px;}
</style>
</head>
<body>
    <h1>Gerenciar Vídeos</h1>
    <div style="margin-top:15px;">
        <a href="/admin/adicionar" class="btn">➕ Adicionar Novo Vídeo</a>
        <a href="/admin/logout" style="color:#888;float:right;text-decoration:none;margin-top:5px;">Sair</a>
    </div>
    <table>
        <tr><th>Título</th><th>Preço</th><th>Duração</th><th>Ações</th></tr>
        {% for v in videos %}
        <tr>
            <td>{{ v.titulo }}</td>
            <td>R$ {{ v.preco }}</td>
            <td>{{ v.duracao }}</td>
            <td><a href="/admin/excluir/{{ v.id }}" class="btn-del">Excluir</a></td>
        </tr>
        {% endfor %}
    </table>
</body></html>"""

ADICIONAR_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><title>Adicionar Vídeo</title>
<style>body{background:#0d0d0d;color:#fff;font-family:sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;padding:20px;}
form{background:#161b22;padding:30px;border-radius:12px;border:1px solid #30363d;width:100%;max-width:400px;}
input, label {display:block;width:100%;text-align:left;}
label{font-size:13px;color:#8b949e;margin-top:10px;}
input[type="text"]{padding:10px;margin-top:5px;background:#0d1117;border:1px solid #30363d;color:#fff;border-radius:6px;}
input[type="file"]{margin-top:5px;color:#8b949e;font-size:13px;}
button{width:100%;padding:12px;background:#25d366;border:none;font-weight:bold;border-radius:6px;cursor:pointer;margin-top:20px;}
.erro{color:#ff4500;font-size:13px;margin-bottom:10px;text-align:center;}
</style>
</head>
<body>
    <form method="POST" enctype="multipart/form-data">
        <h2>Cadastrar Vídeo</h2>
        {% if erro %}<div class="erro">{{ erro }}</div>{% endif %}
        
        <label>Título do Vídeo:</label>
        <input type="text" name="titulo" required>
        
        <label>Link Direto do Vídeo (.mp4):</label>
        <input type="text" name="url_video" required>
        
        <label>Enviar Imagem da Capa (Direto da Galeria):</label>
        <input type="file" name="thumbnail_file" accept="image/*">
        
        <label>OU Cole o Link da Capa:</label>
        <input type="text" name="thumbnail_link" placeholder="https://exemplo.com/foto.jpg">
        
        <label>Preço (R$):</label>
        <input type="text" name="preco" value="10.00" required>
        
        <button type="submit">Salvar Vídeo</button>
    </form>
</body></html>"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 10001)))
