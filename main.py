from flask import Flask, render_template_string, jsonify, request, redirect, url_for, session
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import uuid
import requests
from datetime import datetime
import base64
import cv2
import tempfile

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'sua-chave-secreta-segura')
ADMIN_SENHA = os.getenv('ADMIN_SENHA', 'admin123')

client = MongoClient(os.getenv('MONGO_URI'))
db = client['video_site']
videos_collection = db['videos']
videos_gratis_collection = db['videos_gratis']
envios_collection = db['envios_criadores']
suporte_collection = db['suporte']
pagamentos_collection = db['pagamentos']
MP_TOKEN = os.getenv('MP_TOKEN')

CAPA_PADRAO = "https://files.catbox.moe/uw9r9l.png"

# ==========================================
# HEADERS DE SEGURANÇA
# ==========================================
@app.after_request
def adicionar_seguranca(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

# ==========================================
# SITE PRINCIPAL (CLIENTES) - ROTA RAIZ
# ==========================================
@app.route('/')
def index():
    if 'user_token' not in session:
        session['user_token'] = str(uuid.uuid4())
    
    user_token = session['user_token']
    
    pagos = list(pagamentos_collection.find({'user_token': user_token, 'status': 'aprovado'}, {'video_id': 1, '_id': 0}))
    videos_pagos_ids = [p['video_id'] for p in pagos]
    
    videos = list(videos_collection.find({}, {'_id': 0}))
    videos_gratis = list(videos_gratis_collection.find({}, {'_id': 0}))
    
    likes_usuario = session.get('likes_usuario', [])
    desbloqueios_gratis = session.get('desbloqueios_gratis', [])
    
    return render_template_string(HTML_SITE, 
                                  videos=videos, 
                                  videos_gratis=videos_gratis,
                                  videos_pagos_ids=videos_pagos_ids, 
                                  likes_usuario=likes_usuario,
                                  desbloqueios_gratis=desbloqueios_gratis)

@app.route('/curtir-video/<tipo>/<video_id>', methods=['POST'])
def curtir_video(tipo, video_id):
    if 'likes_usuario' not in session:
        session['likes_usuario'] = []
    
    if video_id in session['likes_usuario']:
        return jsonify({'sucesso': False, 'erro': 'Você já curtiu este vídeo!'}), 400
    
    collection = videos_collection if tipo == 'vip' else videos_gratis_collection
    res = collection.update_one({'id': video_id}, {'$inc': {'likes': 1}})
    
    if res.modified_count > 0:
        session['likes_usuario'].append(video_id)
        session.modified = True
        vid = collection.find_one({'id': video_id}, {'likes': 1, '_id': 0})
        return jsonify({'sucesso': True, 'likes': vid.get('likes', 1)})
    
    return jsonify({'sucesso': False, 'erro': 'Vídeo não encontrado'}), 404

@app.route('/incrementar-view/<tipo>/<video_id>', methods=['POST'])
def incrementar_view(tipo, video_id):
    collection = videos_collection if tipo == 'vip' else videos_gratis_collection
    collection.update_one({'id': video_id}, {'$inc': {'views': 1}})
    return jsonify({'sucesso': True})

@app.route('/desbloquear-gratis/<video_id>', methods=['POST'])
def desbloquear_gratis(video_id):
    if 'desbloqueios_gratis' not in session:
        session['desbloqueios_gratis'] = []
    if video_id not in session['desbloqueios_gratis']:
        session['desbloqueios_gratis'].append(video_id)
        session.modified = True
    return jsonify({'sucesso': True})

@app.route('/enviar-video-criador', methods=['POST'])
def enviar_video_criador():
    try:
        nome = request.form.get('nome', '').strip()
        gmail = request.form.get('gmail', '').strip()
        chave_pix = request.form.get('chave_pix', '').strip()
        titulo = request.form.get('titulo', '').strip()
        url_video = request.form.get('url_video', '').strip()
        preco_original = float(request.form.get('preco', '10.00'))
        
        preco_final = preco_original + 5.00
        
        termo_responsabilidade = request.form.get('termo')
        if not termo_responsabilidade or not nome or not gmail or not chave_pix or not titulo or not url_video:
            return jsonify({'sucesso': False, 'erro': 'Preencha todos os campos obrigatórios e aceite os termos!'}), 400

        envios_collection.insert_one({
            'id': str(uuid.uuid4()),
            'nome': nome,
            'gmail': gmail,
            'chave_pix': chave_pix,
            'titulo': titulo,
            'url_video': url_video,
            'preco_criador': preco_original,
            'preco_final': preco_final,
            'status': 'pendente',
            'criado_em': datetime.utcnow()
        })
        return jsonify({'sucesso': True})
    except Exception as e:
        return jsonify({'sucesso': False, 'erro': str(e)}), 500

@app.route('/gerar-pix', methods=['POST'])
def gerar_pix():
    try:
        user_token = session.get('user_token', str(uuid.uuid4()))
        session['user_token'] = user_token
        
        video_id = request.form.get('video_id', '')
        if not video_id:
            return jsonify({'sucesso': False, 'erro': 'Vídeo não especificado'}), 400
        
        video = videos_collection.find_one({'id': video_id})
        valor = float(video.get('preco', 10.00)) if video else 10.00
        titulo_video = video.get('titulo', 'Vídeo VIP') if video else 'Vídeo VIP'

        headers = {
            'Authorization': f'Bearer {MP_TOKEN}',
            'Content-Type': 'application/json'
        }
        payload = {
            "transaction_amount": valor,
            "description": f"Acesso VIP: {titulo_video}",
            "payment_method_id": "pix",
            "payer": {"email": f"cliente_{user_token[:8]}@tempmail.com"}
        }
        resp = requests.post("https://api.mercadopago.com/v1/payments", headers=headers, json=payload)
        pagamento = resp.json()
        
        if resp.status_code == 201:
            payment_id = str(pagamento.get('id'))
            pix_copia_cola_real = pagamento['point_of_interaction']['transaction_data']['qr_code']
            pix_fake = f"00020126580014br.gov.bcb.pix0136{str(uuid.uuid4())}5204000053039865802BR5925CONTEUDO VIP DIGITAL6009SAO PAULO62070503***6304"
            
            pagamentos_collection.insert_one({
                'payment_id': payment_id,
                'user_token': user_token,
                'video_id': video_id,
                'titulo_video': titulo_video,
                'status': 'pendente',
                'criado_em': datetime.utcnow()
            })
            
            return jsonify({'sucesso': True, 'payment_id': payment_id, 'pix_real': pix_copia_cola_real, 'pix_fake': pix_fake})
        else:
            return jsonify({'sucesso': False, 'erro': 'Falha na API de Pagamento'}), 500
    except Exception as e:
        return jsonify({'sucesso': False, 'erro': str(e)}), 500

@app.route('/checar-pagamento/<payment_id>', methods=['GET'])
def checar_pagamento(payment_id):
    try:
        user_token = session.get('user_token')
        reg = pagamentos_collection.find_one({'payment_id': payment_id, 'user_token': user_token})
        
        if not reg:
            return jsonify({'aprovado': False})
            
        if reg.get('status') == 'aprovado':
            return jsonify({'aprovado': True, 'video_id': reg.get('video_id')})
            
        headers = {'Authorization': f'Bearer {MP_TOKEN}'}
        resp = requests.get(f"https://api.mercadopago.com/v1/payments/{payment_id}", headers=headers)
        if resp.status_code == 200:
            dados = resp.json()
            if dados.get('status') == 'approved':
                pagamentos_collection.update_one({'payment_id': payment_id}, {'$set': {'status': 'aprovado'}})
                return jsonify({'aprovado': True, 'video_id': reg.get('video_id')})
                
        return jsonify({'aprovado': False})
    except Exception as e:
        return jsonify({'aprovado': False, 'erro': str(e)})

@app.route('/enviar-suporte', methods=['POST'])
def enviar_suporte():
    try:
        nome = request.form.get('nome', '').strip()
        gmail = request.form.get('gmail', '').strip()
        mensagem = request.form.get('mensagem', '').strip()[:50]

        if not nome or not gmail or not mensagem:
            return jsonify({'sucesso': False, 'erro': 'Preencha todos os campos!'}), 400

        suporte_collection.insert_one({
            'id': str(uuid.uuid4()),
            'nome': nome,
            'gmail': gmail,
            'mensagem': mensagem,
            'criado_em': datetime.utcnow()
        })
        return jsonify({'sucesso': True})
    except Exception as e:
        return jsonify({'sucesso': False, 'erro': str(e)}), 500

# ==========================================
# LOGIN E PAINEL DO ADMIN
# ==========================================
@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        senha_digitada = request.form.get('senha', '').strip()
        if ADMIN_SENHA and senha_digitada == ADMIN_SENHA.strip():
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

@app.route('/admin')
@requer_login
def dashboard():
    videos = list(videos_collection.find().sort('criado_em', -1))
    videos_gratis = list(videos_gratis_collection.find().sort('criado_em', -1))
    envios = list(envios_collection.find().sort('criado_em', -1))
    mensagens = list(suporte_collection.find().sort('criado_em', -1))
    pagamentos_aprovados = list(pagamentos_collection.find({'status': 'aprovado'}).sort('criado_em', -1))
    
    return render_template_string(DASHBOARD_HTML, 
                                  videos=videos, 
                                  videos_gratis=videos_gratis, 
                                  envios=envios, 
                                  mensagens=mensagens,
                                  pagamentos_aprovados=pagamentos_aprovados)

@app.route('/admin/adicionar', methods=['GET', 'POST'])
@requer_login
def adicionar():
    if request.method == 'POST':
        tipo_video = request.form.get('tipo_video', 'vip')
        titulo = request.form.get('titulo')
        url_video = request.form.get('url_video')
        preco = request.form.get('preco', '10.00')
        duracao = request.form.get('duracao', '').strip()
        tamanho = request.form.get('tamanho', '').strip()
        link_thumbnail = request.form.get('thumbnail_link', '').strip()
        
        if not titulo or not url_video:
            return render_template_string(ADICIONAR_HTML, erro='Preencha o título e o link direto do vídeo!')
        
        thumbnail = CAPA_PADRAO

        if link_thumbnail:
            thumbnail = link_thumbnail
        elif 'thumbnail_file' in request.files:
            file = request.files['thumbnail_file']
            if file and file.filename != '':
                img_bytes = file.read()
                encoded = base64.b64encode(img_bytes).decode('utf-8')
                mime_type = file.content_type or 'image/jpeg'
                thumbnail = f"data:{mime_type};base64,{encoded}"
        elif thumbnail == CAPA_PADRAO and url_video.startswith('http'):
            try:
                headers = {'User-Agent': 'Mozilla/5.0'}
                r = requests.get(url_video, headers=headers, stream=True, timeout=15)
                if r.status_code == 200:
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
                        for chunk in r.iter_content(chunk_size=16384):
                            if chunk:
                                tmp.write(chunk)
                        tmp_path = tmp.name

                    cap = cv2.VideoCapture(tmp_path)
                    success, frame = cap.read()
                    
                    if success and frame is not None:
                        frame_resized = cv2.resize(frame, (640, 360))
                        _, buffer = cv2.imencode('.jpg', frame_resized, [cv2.IMWRITE_JPEG_QUALITY, 80])
                        encoded_img = base64.b64encode(buffer).decode('utf-8')
                        thumbnail = f"data:image/jpeg;base64,{encoded_img}"
                    
                    cap.release()
                    os.unlink(tmp_path)
            except Exception as e:
                print("Erro ao extrair capa automática:", e)
                pass

        if 'video_file' in request.files:
            v_file = request.files['video_file']
            if v_file and v_file.filename != '':
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
                        tmp.write(v_file.read())
                        tmp_path = tmp.name
                    
                    cap = cv2.VideoCapture(tmp_path)
                    success, frame = cap.read()
                    
                    if success and frame is not None:
                        _, buffer = cv2.imencode('.jpg', frame)
                        encoded_img = base64.b64encode(buffer).decode('utf-8')
                        thumbnail = f"data:image/jpeg;base64,{encoded_img}"
                    
                    cap.release()
                    os.unlink(tmp_path)
                except Exception:
                    pass

        novo_video = {
            'id': str(uuid.uuid4()),
            'titulo': titulo,
            'url_video': url_video,
            'thumbnail': thumbnail,
            'tamanho': tamanho,
            'duracao': duracao,
            'preco': preco,
            'views': 0,
            'likes': 0,
            'ativo': True,
            'criado_em': datetime.utcnow()
        }

        if tipo_video == 'gratis':
            videos_gratis_collection.insert_one(novo_video)
        else:
            videos_collection.insert_one(novo_video)

        return redirect(url_for('dashboard'))
        
    return render_template_string(ADICIONAR_HTML, erro='')

@app.route('/admin/editar/<tipo>/<video_id>', methods=['GET', 'POST'])
@requer_login
def editar_video(tipo, video_id):
    collection = videos_collection if tipo == 'vip' else videos_gratis_collection
    video = collection.find_one({'id': video_id})
    if not video:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        titulo = request.form.get('titulo')
        url_video = request.form.get('url_video')
        preco = request.form.get('preco', '10.00')
        duracao = request.form.get('duracao', '').strip()
        tamanho = request.form.get('tamanho', '').strip()
        views = int(request.form.get('views', 0))
        likes = int(request.form.get('likes', 0))
        link_thumbnail = request.form.get('thumbnail_link', '').strip()

        thumbnail = video.get('thumbnail', CAPA_PADRAO)
        if link_thumbnail:
            thumbnail = link_thumbnail

        collection.update_one({'id': video_id}, {
            '$set': {
                'titulo': titulo,
                'url_video': url_video,
                'preco': preco,
                'duracao': duracao,
                'tamanho': tamanho,
                'views': views,
                'likes': likes,
                'thumbnail': thumbnail
            }
        })
        return redirect(url_for('dashboard'))

    return render_template_string(EDITAR_HTML, video=video, tipo=tipo)

@app.route('/admin/excluir/<tipo>/<video_id>')
@requer_login
def excluir_video(tipo, video_id):
    collection = videos_collection if tipo == 'vip' else videos_gratis_collection
    collection.delete_one({'id': video_id})
    return redirect(url_for('dashboard'))

@app.route('/admin/excluir-suporte/<msg_id>')
@requer_login
def excluir_suporte(msg_id):
    suporte_collection.delete_one({'id': msg_id})
    return redirect(url_for('dashboard'))

@app.route('/health')
def health():
    return "OK", 200

# ==========================================
# TEMPLATE DO SITE PRINCIPAL
# ==========================================
HTML_SITE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Plataforma de Vídeos VIP e Gratuitos</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        * {margin:0;padding:0;box-sizing:border-box;}
        body { background-color: #0d0d0d; color: #fff; display: flex; flex-direction: column; align-items: center; justify-content: space-between; min-height: 100vh; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; }
        header { width: 100%; background: #161b22; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #30363d; }
        header h1 { font-size: 18px; color: #25d366; }
        .btn-enviar-topo { background: #238636; color: #fff; padding: 8px 16px; border-radius: 20px; font-size: 13px; font-weight: bold; text-decoration: none; cursor: pointer; }
        
        .main-content { flex: 1; width: 100%; padding: 25px 15px; display: flex; flex-direction: column; align-items: center; }
        .secao-titulo { font-size: 18px; color: #25d366; margin: 25px 0 15px 0; font-weight: bold; width: 100%; max-width: 580px; text-align: left; border-left: 4px solid #25d366; padding-left: 8px; }
        
        #container-misturado { width: 100%; max-width: 580px; display: flex; flex-direction: column; gap: 30px; }
        .video-title { font-size: 16px; font-weight: 600; color: #e0e0e0; text-align: left; width: 100%; display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;}
        .video-title span.detalhes-info { font-size: 12px; color: #8b949e; font-weight: normal; }
        .video-title i { color: #25d366; margin-right: 5px; }
        
        .video-container { width: 100%; aspect-ratio: 16 / 9; border-radius: 14px; overflow: hidden; position: relative; background: #0d0d0d; box-shadow: 0px 15px 35px rgba(0,0,0,0.95); }
        .video-container video { width: 100%; height: 100%; object-fit: cover; }
        
        .capa-bloqueada { width: 100%; height: 100%; position: absolute; top: 0; left: 0; background-size: cover; background-position: center; display: flex; flex-direction: column; align-items: center; justify-content: center; backdrop-filter: blur(6px); z-index: 5; cursor: pointer; }
        .capa-bloqueada::before { content: ""; position: absolute; top:0; left:0; width:100%; height:100%; background: rgba(0,0,0,0.75); }
        .conteudo-bloqueio { position: relative; z-index: 6; display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 0 15px; pointer-events: none; }
        .conteudo-bloqueio i { font-size: 42px; color: #25d366; text-shadow: 0 0 15px rgba(37,211,102,0.6); }
        .conteudo-bloqueio p { font-size: 15px; font-weight: 600; color: #fff; }

        .btn-acao { display: inline-flex; align-items: center; justify-content: center; gap: 8px; background: linear-gradient(135deg, #25d366, #1ebe57); border: none; color: #000 !important; font-weight: 700; text-decoration: none; padding: 12px 24px; font-size: 15px; border-radius: 25px; cursor: pointer; box-shadow: 0 4px 15px rgba(37,211,102,0.4); pointer-events: auto; }
        .btn-desbloquear-gratis { background: linear-gradient(135deg, #229ED9, #1b85b8); color: #fff !important; }

        .video-stats-bar { display: flex; justify-content: space-between; align-items: center; width: 100%; background: #161b22; padding: 10px 15px; border-radius: 0 0 14px 14px; border: 1px solid #30363d; border-top: none; font-size: 13px; color: #8b949e; }
        .btn-like { background: transparent; border: none; color: #fff; cursor: pointer; font-size: 14px; display: flex; align-items: center; gap: 6px; transition: color 0.2s; }
        .btn-like:hover, .btn-like.curtido { color: #da3633; }
        .btn-like i { font-size: 16px; }

        .banner-ad { margin: 15px auto; width: 100%; display: flex; justify-content: center; }
        
        footer { width: 100%; background: #050505; border-top: 1px solid #1f1f1f; padding: 30px 15px; font-size: 14px; color: #777; margin-top: 40px; text-align: center; }
        .footer-links { margin-bottom: 12px; display: flex; justify-content: center; flex-wrap: wrap; gap: 20px; }
        footer a { color: #aaa; text-decoration: none; transition: color 0.2s; font-size: 14px; }
        footer a:hover { color: #25d366; }
        
        .modal { display: none; position: fixed; z-index: 9999; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); backdrop-filter: blur(8px); align-items: center; justify-content: center; padding: 20px; overflow-y: auto; }
        .modal-content { background: linear-gradient(160deg, #161b22, #0d1117); border: 1px solid #30363d; border-radius: 18px; max-width: 480px; width: 100%; padding: 30px; position: relative; text-align: left; box-shadow: 0 20px 40px rgba(0,0,0,0.9); max-height: 90vh; overflow-y: auto; }
        .modal-content h2 { color: #fff; font-size: 20px; margin-bottom: 15px; border-bottom: 1px solid #21262d; padding-bottom: 10px; display: flex; align-items: center; gap: 10px; }
        .modal-content h2 i { color: #25d366; }
        .close-btn { position: absolute; top: 20px; right: 20px; font-size: 22px; color: #8b949e; cursor: pointer; background: #21262d; width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
        .close-btn:hover { background: #da3633; color: #fff; }
        
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; font-size: 13px; color: #8b949e; margin-bottom: 6px; font-weight: 600; }
        .form-control { width: 100%; padding: 12px; background: #0d1117; border: 1px solid #30363d; color: #fff; border-radius: 8px; font-size: 14px; }
        textarea.form-control { height: 80px; resize: none; }
        .instrucao-box { background: #0d1117; border-left: 3px solid #229ED9; padding: 10px; font-size: 12px; color: #8b949e; margin-bottom: 15px; border-radius: 0 8px 8px 0; line-height: 1.4; }
        .checkbox-group { display: flex; align-items: flex-start; gap: 10px; font-size: 12px; color: #c9d1d9; margin: 15px 0; text-align: left; }
        .checkbox-group input { margin-top: 3px; transform: scale(1.2); }

        #toast-notificacao { visibility: hidden; min-width: 280px; background-color: #238636; color: #fff; text-align: center; border-radius: 12px; padding: 16px; position: fixed; z-index: 100000; left: 50%; bottom: 30px; transform: translateX(-50%); font-size: 15px; font-weight: 600; box-shadow: 0 5px 20px rgba(0,0,0,0.5); opacity: 0; transition: opacity 0.3s, bottom 0.3s; }
        #toast-notificacao.show { visibility: visible; opacity: 1; bottom: 50px; }
        .vazio { color: #888; font-size: 15px; padding: 30px; background: #161b22; border-radius: 12px; border: 1px solid #30363d; width: 100%; }
    </style>
</head>
<body oncontextmenu="return false;">
  
  <header>
      <h1><i class="fa-solid fa-play-circle"></i> Vídeos VIP & Grátis</h1>
      <button onclick="openModal('modalEnviarVideo')" class="btn-enviar-topo"><i class="fa-solid fa-cloud-arrow-up"></i> Enviar Meu Vídeo</button>
  </header>

  <div class="main-content">
    <div id="container-misturado">
        
        <!-- VÍDEOS GRATUITOS -->
        <div class="secao-titulo"><i class="fa-solid fa-gift"></i> Vídeos Gratuitos (Desbloqueie com Anúncio)</div>
        {% if videos_gratis %}
            {% for video in videos_gratis %}
            <div>
                <div class="video-title">
                    <span><i class="fa-solid fa-video"></i>{{ video.titulo }}</span>
                    <span class="detalhes-info">
                        {% if video.duracao %}⏱️ {{ video.duracao }}{% endif %} 
                        {% if video.tamanho %} | 📦 {{ video.tamanho }}{% endif %}
                    </span>
                </div>
                
                <div class="video-container" id="containerGratis_{{ video.id }}">
                    {% if video.id in desbloqueios_gratis %}
                    <video id="vidGratis_{{ video.id }}" src="{{ video.url_video }}" controls controlslist="nodownload" onplay="handlePlayGratis('{{ video.id }}')" onpause="handlePauseGratis('{{ video.id }}')" onended="handleEndedGratis('{{ video.id }}')" onloadedmetadata="setupFullscreenListener('{{ video.id }}')"></video>
                    {% else %}
                    <div class="capa-bloqueada" id="capaGratis_{{ video.id }}" style="background-image: url('{{ video.thumbnail }}');" onclick="desbloquearVideoGratis('{{ video.id }}', '{{ video.url_video }}')">
                        <div class="conteudo-bloqueio">
                            <i class="fa-solid fa-play-circle"></i>
                            <p>Vídeo Gratuito</p>
                            <button class="btn-acao btn-desbloquear-gratis">
                                <i class="fa-solid fa-unlock"></i> Assistir Vídeo (Ver Anúncio)
                            </button>
                        </div>
                    </div>
                    {% endif %}
                </div>
                <div class="video-stats-bar">
                    <span><i class="fa-solid fa-eye"></i> <span id="view_gratis_{{ video.id }}">{{ video.views }}</span> visualizações</span>
                    <button class="btn-like {% if video.id in likes_usuario %}curtido{% endif %}" onclick="curtirVideo('gratis', '{{ video.id }}')">
                        <i class="fa-solid fa-heart"></i> <span id="like_gratis_{{ video.id }}">{{ video.likes }}</span>
                    </button>
                </div>
            </div>
            {% endfor %}
        {% else %}
            <div class="vazio">Nenhum vídeo gratuito no momento.</div>
        {% endif %}

        <!-- VÍDEOS VIP PAGOS -->
        <div class="secao-titulo" style="margin-top: 20px;"><i class="fa-solid fa-crown" style="color: #ffd700;"></i> Vídeos Exclusivos VIP</div>
        {% if videos %}
            {% for video in videos %}
            <div>
                <div class="video-title">
                    <span><i class="fa-solid fa-fire"></i>{{ video.titulo }}</span>
                    <span class="detalhes-info">
                        {% if video.duracao %}⏱️ {{ video.duracao }}{% endif %} 
                        {% if video.tamanho %} | 📦 {{ video.tamanho }}{% endif %}
                    </span>
                </div>
                
                <div class="video-container" id="containerVideo_{{ video.id }}">
                    {% if video.id in videos_pagos_ids %}
                    <video src="{{ video.url_video }}" controls controlslist="nodownload" onplay="registrarView('vip', '{{ video.id }}')"></video>
                    {% else %}
                    <div class="capa-bloqueada" id="capa_{{ video.id }}" style="background-image: url('{{ video.thumbnail }}');" onclick="abrirModalLiberar('{{ video.id }}', '{{ video.titulo }}', '{{ video.tamanho }}', '{{ video.duracao }}', '{{ video.preco }}')">
                        <div class="conteudo-bloqueio">
                            <i class="fa-solid fa-lock"></i>
                            <p>Vídeo Exclusivo Bloqueado</p>
                            <button class="btn-acao">
                                <i class="fa-solid fa-lock-open"></i> Liberar Acesso VIP (R$ {{ video.preco }})
                            </button>
                        </div>
                    </div>
                    {% endif %}
                </div>
                <div class="video-stats-bar">
                    <span><i class="fa-solid fa-eye"></i> <span id="view_vip_{{ video.id }}">{{ video.views }}</span> visualizações</span>
                    <button class="btn-like {% if video.id in likes_usuario %}curtido{% endif %}" onclick="curtirVideo('vip', '{{ video.id }}')">
                        <i class="fa-solid fa-heart"></i> <span id="like_vip_{{ video.id }}">{{ video.likes }}</span>
                    </button>
                </div>
            </div>
            {% endfor %}
        {% else %}
            <div class="vazio">Nenhum vídeo VIP cadastrado no momento.</div>
        {% endif %}

        <!-- ANÚNCIOS DO ADSTERRA -->
        <div class="banner-ad">
            <script async="async" data-cfasync="false" src="https://bicea.org/21/1fd37c2a1d9d1e19537dc1d7d97cdc9b"></script>
            <div id="container-1fd37c2a1d9d1e19537dc1d7d97cdc9b"></div>
        </div>

    </div>
  </div>

    <footer>
        <div class="footer-links">
            <a href="#" onclick="openModal('termsModal'); return false;">Termos de Uso</a>
            <a href="#" onclick="openModal('privacyModal'); return false;">Política de Privacidade</a>
            <a href="#" onclick="openModal('supportModal'); return false;">Suporte</a>
        </div>
        <p>2020 - 2027 &copy; Todos os direitos reservados</p>
    </footer>

    <!-- MODAL DE ENVIO DE VÍDEO DO CRIADOR (CATBOX) -->
    <div id="modalEnviarVideo" class="modal" onclick="closeModalOutside(event,'modalEnviarVideo')">
        <div class="modal-content" onclick="event.stopPropagation()">
            <span class="close-btn" onclick="closeModal('modalEnviarVideo')">&times;</span>
            <h2><i class="fa-solid fa-cloud-arrow-up"></i> Enviar Meu Vídeo</h2>
            
            <div class="instrucao-box">
                <b>Como enviar pelo Catbox.moe:</b><br>
                1. Acesse o site <b>catbox.moe</b> no seu navegador.<br>
                2. Faça o upload do seu arquivo de vídeo.<br>
                3. Copie o <b>Link Direto do Arquivo</b> gerado (terminado em .mp4).<br>
                4. Cole o link no campo abaixo. O site cobra uma taxa fixa de R$ 5,00 por venda.
            </div>

            <form id="formEnviarCriador" onsubmit="enviarVideoCriadorForm(event)">
                <div class="form-group">
                    <label>Seu Nome Completo *</label>
                    <input type="text" name="nome" class="form-control" required placeholder="Digite seu nome">
                </div>
                <div class="form-group">
                    <label>Seu Gmail (para contato) *</label>
                    <input type="email" name="gmail" class="form-control" required placeholder="seuemail@gmail.com">
                </div>
                <div class="form-group">
                    <label>Sua Chave Pix (para receber seus lucros) *</label>
                    <input type="text" name="chave_pix" class="form-control" required placeholder="CPF, E-mail, Telefone ou Chave Aleatória">
                </div>
                <div class="form-group">
                    <label>Título do Vídeo *</label>
                    <input type="text" name="titulo" class="form-control" required placeholder="Título chamativo para o vídeo">
                </div>
                <div class="form-group">
                    <label>Link Direto do Vídeo (Catbox.moe) *</label>
                    <input type="text" name="url_video" class="form-control" required placeholder="https://files.catbox.moe/xxxxxx.mp4">
                </div>
                <div class="form-group">
                    <label>Quanto você quer cobrar pelo vídeo? (R$) *</label>
                    <input type="number" step="0.01" min="1.00" name="preco" class="form-control" required placeholder="Ex: 10.00">
                    <small style="color: #8b949e; font-size: 11px;">Taxa da plataforma: R$ 5,00. O preço final para o cliente será o valor escolhido + R$ 5,00.</small>
                </div>
                
                <div class="checkbox-group">
                    <input type="checkbox" name="termo" id="chkTermo" required>
                    <label for="chkTermo" style="font-size:11px; color:#8b949e; margin:0; cursor:pointer;">Por sua conta em risco, você confirma que seus dados estão certos e o conteúdo é de sua pessoa ou tem autorização expressa para comercialização.</label>
                </div>

                <button type="submit" class="btn-acao" style="width:100%; padding:12px; font-size:14px; margin-top:10px;">Enviar Vídeo para Análise</button>
            </form>
        </div>
    </div>

    <!-- MODAL DE LIBERAÇÃO PIX -->
    <div id="modalLiberar" class="modal" onclick="closeModalOutside(event,'modalLiberar')">
        <div class="modal-content" onclick="event.stopPropagation()">
            <span class="close-btn" onclick="closeModal('modalLiberar')">&times;</span>
            <h2><i class="fa-solid fa-shield-halved"></i> Liberação Instantânea</h2>
            <p id="modalTituloVid" style="color:#f0f6fc; font-weight:600; margin-bottom:12px; font-size:14px;"></p>
            <div class="modal-info-box" style="background:#0d1117; border:1px solid #21262d; border-radius:10px; padding:12px 15px; margin-bottom:15px; text-align:left;">
                <p style="color:#8b949e; font-size:13px; margin-bottom:6px; display:flex; justify-content:space-between;">Tamanho: <span id="modalTamanho" style="color:#f0f6fc;">Não informado</span></p>
                <p style="color:#8b949e; font-size:13px; margin-bottom:6px; display:flex; justify-content:space-between;">Duração: <span id="modalDuracao" style="color:#f0f6fc;">Não informada</span></p>
                <p style="color:#8b949e; font-size:13px; display:flex; justify-content:space-between;">Valor: <span style="color:#25d366; font-size:15px; font-weight:bold;">R$ <span id="modalPreco"></span></span></p>
            </div>
            <button onclick="gerarPixModal()" class="btn-acao" style="width:100%; padding:12px; font-size:14px;">Gerar Chave Pix de Pagamento</button>
            <div id="areaPixGerado" style="display:none; margin-top: 12px;">
                <p style="font-size:11px; color:#8b949e; margin-bottom:4px;">Copie o código abaixo e pague no app do seu banco:</p>
                <textarea id="pixCopiaCola" style="width:100%; height:75px; background:#0d1117; color:#25d366; border:1px solid #30363d; border-radius:10px; padding:10px; font-family:monospace; font-size:11px; text-align:center; resize:none;" readonly></textarea>
                <button onclick="copiarPixReal()" class="btn-acao" style="width:100%; background: linear-gradient(135deg, #229ED9, #1b85b8); color:#fff !important; margin-top:8px; padding:10px;"><i class="fa-solid fa-copy"></i> Copiar Código Pix</button>
                <p id="statusPagamento" style="font-size:12px; color:#e3b341; margin-top:10px; text-align:center;"><i class="fa-solid fa-spinner fa-spin"></i> Aguardando confirmação do pagamento...</p>
            </div>
        </div>
    </div>

    <!-- MODAL DE SUPORTE -->
    <div id="supportModal" class="modal" onclick="closeModalOutside(event,'supportModal')">
        <div class="modal-content" onclick="event.stopPropagation()">
            <span class="close-btn" onclick="closeModal('supportModal')">&times;</span>
            <h2><i class="fa-solid fa-headset"></i> Central de Suporte</h2>
            <form id="formSuporte" onsubmit="enviarMensagemSuporte(event)">
                <div class="form-group">
                    <label>Seu Nome *</label>
                    <input type="text" name="nome" class="form-control" required placeholder="Digite seu nome">
                </div>
                <div class="form-group">
                    <label>Seu Gmail *</label>
                    <input type="email" name="gmail" class="form-control" required placeholder="seuemail@gmail.com">
                </div>
                <div class="form-group">
                    <label>Qual o seu problema? (Máx. 50 caracteres) *</label>
                    <textarea name="mensagem" id="txtMensagem" class="form-control" maxlength="50" required placeholder="Descreva brevemente..." oninput="atualizarContador(this)"></textarea>
                    <div style="font-size: 11px; color: #666; text-align: right; margin-top: 3px;"><span id="charCount">50</span> caracteres restantes</div>
                </div>
                <button type="submit" class="btn-acao" style="width:100%; padding:12px; font-size:14px; margin-top:5px;">Enviar Mensagem</button>
            </form>
        </div>
    </div>

    <!-- MODAL TERMOS DE USO -->
    <div id="termsModal" class="modal" onclick="closeModalOutside(event,'termsModal')">
        <div class="modal-content" onclick="event.stopPropagation()">
            <span class="close-btn" onclick="closeModal('termsModal')">&times;</span>
            <h2><i class="fa-solid fa-file-contract"></i> Termos de Uso</h2>
            <p style="color:#8b949e; font-size:13px; line-height:1.5;">Ao utilizar nossa plataforma, você concorda estritamente com os termos de direitos autorais e transações financeiras.</p>
        </div>
    </div>

    <!-- MODAL POLÍTICA DE PRIVACIDADE -->
    <div id="privacyModal" class="modal" onclick="closeModalOutside(event,'privacyModal')">
        <div class="modal-content" onclick="event.stopPropagation()">
            <span class="close-btn" onclick="closeModal('privacyModal')">&times;</span>
            <h2><i class="fa-solid fa-user-shield"></i> Política de Privacidade</h2>
            <p style="color:#8b949e; font-size:13px; line-height:1.5;">Garantimos total segurança e sigilo dos seus dados de acesso e transações Pix.</p>
        </div>
    </div>
    
    <div id="toast-notificacao"><i class="fa-solid fa-circle-check"></i> <span id="toast-texto">Ação realizada com sucesso!</span></div>

    <script>
        let pixRealGlobal = "";
        let videoIdGlobal = "";
        let paymentIdGlobal = "";
        let intervaloChecagem = null;
        
        // URLs dos anúncios específicos solicitados
        const AD_URL_PLAY = "https://auctionr.org/4/5f6de430d75a855ddff7717775ff4ae3";
        const AD_URL_FULLSCREEN = "https://asiafilm.org/4/8b4a6a2776963b1423e3699abe0c63e0";
        const AD_URL_ENDED = "https://asiafilm.org/4/5875f3c51a281666d53e659422973930";

        // Função de controle de frequência para evitar spam excessivo de abas
        function dispararAnuncioControlado(urlAnuncio) {
            let ultimoTempo = localStorage.getItem('ultimo_anuncio_tempo') || 0;
            let agora = new Date().getTime();
            let intervaloMinimo = 2 * 60 * 1000; // 2 minutos de suavização

            if (agora - ultimoTempo > intervaloMinimo) {
                localStorage.setItem('ultimo_anuncio_tempo', agora);
                window.open(urlAnuncio, '_blank');
            }
        }

        function handlePlayGratis(videoId) {
            registrarView('gratis', videoId);
            dispararAnuncioControlado(AD_URL_PLAY);
        }

        function handlePauseGratis(videoId) {
            dispararAnuncioControlado(AD_URL_PLAY);
        }

        function handleEndedGratis(videoId) {
            // Ao terminar o vídeo grátis, abre o anúncio de encerramento
            window.location.href = AD_URL_ENDED;
        }

        function setupFullscreenListener(videoId) {
            let videoElement = document.getElementById('vidGratis_' + videoId);
            if (!videoElement) return;

            let fullScreenTriggered = false;

            videoElement.addEventListener('fullscreenchange', () => {
                if (document.fullscreenElement && !fullScreenTriggered) {
                    fullScreenTriggered = true;
                    window.open(AD_URL_FULLSCREEN, '_blank');
                }
            });
            // Compatibilidade com navegadores mobile/webkit
            videoElement.addEventListener('webkitfullscreenchange', () => {
                if (document.webkitFullscreenElement && !fullScreenTriggered) {
                    fullScreenTriggered = true;
                    window.open(AD_URL_FULLSCREEN, '_blank');
                }
            });
        }

        function abrirModalLiberar(vidId, t, tam, dur, pre) {
            videoIdGlobal = vidId;
            document.getElementById('modalTituloVid').innerText = t;
            document.getElementById('modalTamanho').innerText = tam ? tam : 'Não informado';
            document.getElementById('modalDuracao').innerText = dur ? dur : 'Não informada';
            document.getElementById('modalPreco').innerText = pre;
            document.getElementById('areaPixGerado').style.display = 'none';
            document.getElementById('modalLiberar').style.display = 'flex';
            if(intervaloChecagem) clearInterval(intervaloChecagem);
        }

        async function gerarPixModal() {
            let formData = new FormData();
            formData.append('video_id', videoIdGlobal);
            
            let res = await fetch('/gerar-pix', { method: 'POST', body: formData });
            let data = await res.json();
            if(data.sucesso) {
                pixRealGlobal = data.pix_real;
                paymentIdGlobal = data.payment_id;
                document.getElementById('pixCopiaCola').value = data.pix_fake;
                document.getElementById('areaPixGerado').style.display = 'block';
                
                intervaloChecagem = setInterval(verificarStatusPagamento, 4000);
            }
        }

        async function verificarStatusPagamento() {
            if(!paymentIdGlobal) return;
            let res = await fetch(`/checar-pagamento/${paymentIdGlobal}`);
            let data = await res.json();
            if(data.aprovado) {
                clearInterval(intervaloChecagem);
                document.getElementById('statusPagamento').innerHTML = "<i class='fa-solid fa-check-circle' style='color:#25d366'></i> Pagamento aprovado! Liberando vídeo...";
                
                setTimeout(() => {
                    closeModal('modalLiberar');
                    location.reload();
                }, 2000);
            }
        }

        function desbloquearVideoGratis(videoId, urlVideo) {
            dispararAnuncioControlado(AD_URL_PLAY);
            
            fetch(`/desbloquear-gratis/${videoId}`, { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                if(data.sucesso) {
                    let container = document.getElementById('containerGratis_' + videoId);
                    container.innerHTML = `<video id="vidGratis_${videoId}" src="${urlVideo}" controls controlslist="nodownload" onplay="handlePlayGratis('${videoId}')" onpause="handlePauseGratis('${videoId}')" onended="handleEndedGratis('${videoId}')" onloadedmetadata="setupFullscreenListener('${videoId}')"></video>`;
                    mostrarToast("Vídeo gratuito desbloqueado com sucesso!");
                }
            });
        }

        function registrarView(tipo, videoId) {
            fetch(`/incrementar-view/${tipo}/${videoId}`, { method: 'POST' });
        }

        function curtirVideo(tipo, videoId) {
            fetch(`/curtir-video/${tipo}/${videoId}`, { method: 'POST' })
            .then(async res => {
                let data = await res.json();
                if(res.ok && data.sucesso) {
                    document.getElementById(`like_${tipo}_${videoId}`).innerText = data.likes;
                    mostrarToast("Vídeo curtido com sucesso!");
                } else {
                    alert(data.erro || "Você já curtiu este vídeo.");
                }
            });
        }

        async function enviarVideoCriadorForm(e) {
            e.preventDefault();
            const form = document.getElementById('formEnviarCriador');
            const formData = new FormData(form);
            
            let res = await fetch('/enviar-video-criador', { method: 'POST', body: formData });
            let data = await res.json();
            if(data.sucesso) {
                closeModal('modalEnviarVideo');
                form.reset();
                mostrarToast("Seu vídeo foi enviado! Será analisado pela nossa equipe, responderemos em breve, fique de olho no seu Gmail.");
            } else {
                alert(data.erro || "Erro ao enviar vídeo.");
            }
        }

        async function enviarMensagemSuporte(e) {
            e.preventDefault();
            const form = document.getElementById('formSuporte');
            const formData = new FormData(form);
            
            let res = await fetch('/enviar-suporte', { method: 'POST', body: formData });
            let data = await res.json();
            if(data.sucesso) {
                closeModal('supportModal');
                form.reset();
                mostrarToast("Mensagem enviada com sucesso! Retornaremos em até 1 dia útil.");
            } else {
                alert(data.erro || "Erro ao enviar mensagem.");
            }
        }

        function copiarPixReal() {
            navigator.clipboard.writeText(pixRealGlobal);
            mostrarToast("Código Pix copiado com sucesso!");
        }

        function atualizarContador(textarea) {
            const restantes = 50 - textarea.value.length;
            document.getElementById('charCount').innerText = restantes;
        }

        function mostrarToast(texto) {
            const toast = document.getElementById("toast-notificacao");
            document.getElementById("toast-texto").innerText = texto;
            toast.className = "show";
            setTimeout(function(){ toast.className = toast.className.replace("show", ""); }, 5000);
        }

        function openModal(id) { document.getElementById(id).style.display='flex'; }
        function closeModal(id) { 
            document.getElementById(id).style.display='none'; 
            if(intervaloChecagem) clearInterval(intervaloChecagem);
        }
        function closeModalOutside(e,id) { if(e.target===e.currentTarget) closeModal(id); }
    </script>
</body>
</html>"""

LOGIN_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><title>Login Admin</title>
<style>body{background:#0d0d0d;color:#fff;font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;}
form{background:#161b22;padding:35px;border-radius:14px;border:1px solid #30363d;width:340px;text-align:center;}
input{width:100%;padding:12px;margin:12px 0;background:#0d1117;border:1px solid #30363d;color:#fff;border-radius:8px;font-size:14px;}
button{width:100%;padding:12px;background:#25d366;border:none;font-weight:bold;border-radius:8px;cursor:pointer;font-size:15px;}
.erro{color:#ff4500;font-size:13px;margin-bottom:10px;}</style>
</head>
<body>
    <form method="POST">
        <h2 style="color:#25d366; margin-bottom:15px;">Painel Admin</h2>
        {% if erro %}<div class="erro">{{ erro }}</div>{% endif %}
        <input type="password" name="senha" placeholder="Senha do Administrador" required>
        <button type="submit">Entrar</button>
    </form>
</body></html>"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><title>Dashboard Admin</title>
<style>
    body{background:#0d0d0d;color:#fff;font-family:sans-serif;padding:25px;max-width:1100px;margin:auto;}
    table{width:100%;border-collapse:collapse;margin-top:12px;margin-bottom:35px;background:#161b22;}
    th,td{padding:12px 15px;border:1px solid #30363d;text-align:left;font-size:14px;}
    th{background:#21262d;color:#f0f6fc;}
    a.btn{background:#25d366;color:#000;padding:10px 16px;text-decoration:none;border-radius:8px;font-weight:bold;font-size:14px;display:inline-block;}
    a.btn-del{background:#da3633;color:#fff;padding:6px 12px;text-decoration:none;border-radius:6px;font-size:13px;}
    a.btn-edit{background:#229ED9;color:#fff;padding:6px 12px;text-decoration:none;border-radius:6px;font-size:13px;margin-right:5px;}
    h2{color:#25d366;margin-top:30px;font-size:20px;border-bottom:1px solid #21262d;padding-bottom:8px;}
    h1{font-size:24px;}
</style>
</head>
<body>
    <h1>Painel Administrativo Completo</h1>
    <div style="margin-top:20px; margin-bottom:25px; display:flex; gap:15px; align-items:center;">
        <a href="/admin/adicionar" class="btn">➕ Adicionar Novo Vídeo</a>
        <a href="/admin/logout" style="color:#888;text-decoration:none;margin-left:auto;font-size:14px;font-weight:bold;">Sair do Painel</a>
    </div>

    <h2>💰 Histórico de Vendas / Pagamentos Aprovados (Pix)</h2>
    <table>
        <tr><th>ID do Pagamento</th><th>Título do Vídeo Comprado</th><th>Token do Usuário</th><th>Data e Hora</th></tr>
        {% for p in pagamentos_aprovados %}
        <tr>
            <td>{{ p.payment_id }}</td>
            <td style="color:#25d366; font-weight:bold;">{{ p.titulo_video if p.titulo_video else 'Vídeo VIP' }}</td>
            <td style="font-size:11px; color:#8b949e;">{{ p.user_token }}</td>
            <td>{{ p.criado_em.strftime('%d/%m/%Y %H:%M') }}</td>
        </tr>
        {% else %}
        <tr><td colspan="4" style="text-align:center; color:#888;">Nenhum pagamento aprovado no momento.</td></tr>
        {% endfor %}
    </table>

    <h2>Envios de Vídeos Feitos por Criadores</h2>
    <table>
        <tr><th>Nome</th><th>Gmail</th><th>Pix</th><th>Título</th><th>Preço Final</th><th>Link Direto</th><th>Data</th></tr>
        {% for e in envios %}
        <tr>
            <td>{{ e.nome }}</td>
            <td>{{ e.gmail }}</td>
            <td>{{ e.chave_pix }}</td>
            <td>{{ e.titulo }}</td>
            <td style="color:#25d366; font-weight:bold;">R$ {{ "%.2f"|format(e.preco_final) }}</td>
            <td><a href="{{ e.url_video }}" target="_blank" style="color:#229ED9;">Abrir Link</a></td>
            <td>{{ e.criado_em.strftime('%d/%m/%Y %H:%M') }}</td>
        </tr>
        {% else %}
        <tr><td colspan="7" style="text-align:center; color:#888;">Nenhum vídeo enviado por criadores.</td></tr>
        {% endfor %}
    </table>

    <h2>Gerenciar Vídeos VIP (Pagos)</h2>
    <table>
        <tr><th>Título</th><th>Preço</th><th>Views</th><th>Likes</th><th>Duração</th><th>Ações</th></tr>
        {% for v in videos %}
        <tr>
            <td>{{ v.titulo }}</td>
            <td>R$ {{ v.preco }}</td>
            <td>{{ v.views }}</td>
            <td>{{ v.likes }}</td>
            <td>{{ v.duracao if v.duracao else 'N/A' }}</td>
            <td>
                <a href="/admin/editar/vip/{{ v.id }}" class="btn-edit">Editar</a>
                <a href="/admin/excluir/vip/{{ v.id }}" class="btn-del">Excluir</a>
            </td>
        </tr>
        {% else %}
        <tr><td colspan="6" style="text-align:center; color:#888;">Nenhum vídeo VIP cadastrado.</td></tr>
        {% endfor %}
    </table>

    <h2>Gerenciar Vídeos Gratuitos</h2>
    <table>
        <tr><th>Título</th><th>Views</th><th>Likes</th><th>Duração</th><th>Ações</th></tr>
        {% for v in videos_gratis %}
        <tr>
            <td>{{ v.titulo }}</td>
            <td>{{ v.views }}</td>
            <td>{{ v.likes }}</td>
            <td>{{ v.duracao if v.duracao else 'N/A' }}</td>
            <td>
                <a href="/admin/editar/gratis/{{ v.id }}" class="btn-edit">Editar</a>
                <a href="/admin/excluir/gratis/{{ v.id }}" class="btn-del">Excluir</a>
            </td>
        </tr>
        {% else %}
        <tr><td colspan="5" style="text-align:center; color:#888;">Nenhum vídeo gratuito cadastrado.</td></tr>
        {% endfor %}
    </table>

    <h2>Mensagens de Suporte Recebidas</h2>
    <table>
        <tr><th>Nome</th><th>Gmail</th><th>Mensagem</th><th>Data</th><th>Ação</th></tr>
        {% for m in mensagens %}
        <tr>
            <td>{{ m.nome }}</td>
            <td>{{ m.gmail }}</td>
            <td>{{ m.mensagem }}</td>
            <td>{{ m.criado_em.strftime('%d/%m/%Y %H:%M') }}</td>
            <td><a href="/admin/excluir-suporte/{{ m.id }}" class="btn-del">Apagar</a></td>
        </tr>
        {% else %}
        <tr><td colspan="5" style="text-align:center; color:#888;">Nenhuma mensagem de suporte.</td></tr>
        {% endfor %}
    </table>
</body></html>"""

ADICIONAR_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><title>Adicionar Vídeo</title>
<style>body{background:#0d0d0d;color:#fff;font-family:sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;padding:25px;}
form{background:#161b22;padding:35px;border-radius:14px;border:1px solid #30363d;width:100%;max-width:460px;}
input, select, label {display:block;width:100%;text-align:left;}
label{font-size:14px;color:#8b949e;margin-top:12px;font-weight:600;}
input[type="text"], input[type="number"], select{padding:12px;margin-top:6px;background:#0d1117;border:1px solid #30363d;color:#fff;border-radius:8px;font-size:14px;}
input[type="file"]{margin-top:6px;color:#8b949e;font-size:13px;}
button{width:100%;padding:14px;background:#25d366;border:none;font-weight:bold;border-radius:8px;cursor:pointer;margin-top:25px;font-size:16px;color:#000;}
.erro{color:#ff4500;font-size:14px;margin-bottom:12px;text-align:center;}
</style>
</head>
<body>
    <form method="POST" enctype="multipart/form-data">
        <h2 style="color:#25d366; margin-bottom:15px;">Cadastrar Novo Vídeo</h2>
        {% if erro %}<div class="erro">{{ erro }}</div>{% endif %}
        
        <label>Tipo de Vídeo:</label>
        <select name="tipo_video">
            <option value="vip">Vídeo VIP (Pago)</option>
            <option value="gratis">Vídeo Gratuito (Desbloqueio com Anúncio)</option>
        </select>

        <label>Título do Vídeo:</label>
        <input type="text" name="titulo" required>
        
        <label>Link Direto do Vídeo (Catbox.moe):</label>
        <input type="text" name="url_video" placeholder="https://files.catbox.moe/xxxxxx.mp4" required>

        <label>Duração Real (Opcional - Ex: 05:40):</label>
        <input type="text" name="duracao" placeholder="Ex: 05:40">

        <label>Tamanho Real do Arquivo (Opcional - Ex: 120 MB):</label>
        <input type="text" name="tamanho" placeholder="Ex: 120 MB">
        
        <label>Enviar Vídeo para Extrair Capa Automática (Opcional):</label>
        <input type="file" name="video_file" accept="video/*">
        
        <label>OU Enviar Imagem da Capa:</label>
        <input type="file" name="thumbnail_file" accept="image/*">
        
        <label>OU Cole o Link Direto da Capa/Thumbnail:</label>
        <input type="text" name="thumbnail_link" placeholder="https://exemplo.com/foto.jpg">
        
        <label>Preço em R$ (Apenas para Vídeo VIP):</label>
        <input type="text" name="preco" value="10.00" required>
        
        <button type="submit">Salvar Vídeo</button>
    </form>
</body></html>"""

EDITAR_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><title>Editar Vídeo</title>
<style>body{background:#0d0d0d;color:#fff;font-family:sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;padding:25px;}
form{background:#161b22;padding:35px;border-radius:14px;border:1px solid #30363d;width:100%;max-width:460px;}
input, label {display:block;width:100%;text-align:left;}
label{font-size:14px;color:#8b949e;margin-top:12px;font-weight:600;}
input[type="text"], input[type="number"]{padding:12px;margin-top:6px;background:#0d1117;border:1px solid #30363d;color:#fff;border-radius:8px;font-size:14px;}
button{width:100%;padding:14px;background:#25d366;border:none;font-weight:bold;border-radius:8px;cursor:pointer;margin-top:25px;font-size:16px;color:#000;}
</style>
</head>
<body>
    <form method="POST">
        <h2 style="color:#25d366; margin-bottom:15px;">Editar Vídeo</h2>
        
        <label>Título do Vídeo:</label>
        <input type="text" name="titulo" value="{{ video.titulo }}" required>
        
        <label>Link Direto do Vídeo (Catbox.moe):</label>
        <input type="text" name="url_video" value="{{ video.url_video }}" required>

        <label>Duração:</label>
        <input type="text" name="duracao" value="{{ video.duracao }}">

        <label>Tamanho:</label>
        <input type="text" name="tamanho" value="{{ video.tamanho }}">

        <label>Preço (R$):</label>
        <input type="text" name="preco" value="{{ video.preco }}">

        <label>Número de Visualizações (Views):</label>
        <input type="number" name="views" value="{{ video.views }}" required>

        <label>Número de Curtidas (Likes):</label>
        <input type="number" name="likes" value="{{ video.likes }}" required>

        <label>Link da Capa (Thumbnail):</label>
        <input type="text" name="thumbnail_link" value="{{ video.thumbnail }}">
        
        <button type="submit">Salvar Alterações</button>
    </form>
</body></html>"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 10001)))
