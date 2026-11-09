from flask import Flask, render_template_string, jsonify, request, redirect, url_for, session
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import uuid
import requests
from datetime import datetime
import cv2

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
ADMIN_SENHA = os.getenv('ADMIN_SENHA')

# Conexão MongoDB
client = MongoClient(os.getenv('MONGO_URI'))
db = client['video_site']
videos_collection = db['videos']
MP_TOKEN = os.getenv('MP_TOKEN')

# ==========================================
# SITE PRINCIPAL (CLIENTES)
# ==========================================
@app.route('/')
def index():
    videos = list(videos_collection.find({}, {'_id': 0}))
    return render_template_string(HTML_SITE, videos=videos)

@app.route('/gerar-pix', methods=['POST'])
def gerar_pix():
    try:
        headers = {
            'Authorization': f'Bearer {MP_TOKEN}',
            'Content-Type': 'application/json'
        }
        payload = {
            "transaction_amount": 10.00,
            "description": "Liberacao de Video Exclusivo",
            "payment_method_id": "pix",
            "payer": {"email": "cliente@email.com"}
        }
        resp = requests.post("https://api.mercadopago.com/v1/payments", headers=headers, json=payload)
        pagamento = resp.json()
        
        if resp.status_code == 201:
            pix_copia_cola_real = pagamento['point_of_interaction']['transaction_data']['qr_code']
            pix_fake = f"00020126580014br.gov.bcb.pix0136{str(uuid.uuid4())}5204000053039865802BR5925CONTEUDO VIP DIGITAL6009SAO PAULO62070503***6304"
            return jsonify({'sucesso': True, 'pix_real': pix_copia_cola_real, 'pix_fake': pix_fake})
        else:
            return jsonify({'sucesso': False, 'erro': 'Falha na API'}), 500
    except Exception as e:
        return jsonify({'sucesso': False, 'erro': str(e)}), 500

# ==========================================
# PAINEL ADMINISTRATIVO
# ==========================================
def requer_login(f):
    def decorada(*args, **kwargs):
        if not session.get('admin_logado'):
            return redirect('/painel')
        return f(*args, **kwargs)
    decorada.__name__ = f.__name__
    return decorada

@app.route('/painel', methods=['GET', 'POST'])
def login():
    erro = ''
    if request.method == 'POST':
        senha_digitada = request.form.get('senha', '').strip()
        if ADMIN_SENHA and senha_digitada == ADMIN_SENHA.strip():
            session['admin_logado'] = True
            return redirect('/admin/dashboard')
        else:
            erro = 'Senha incorreta!'
    return render_template_string(LOGIN_HTML, erro=erro)

@app.route('/admin/logout')
def logout():
    session.clear()
    return redirect('/painel')

@app.route('/admin/dashboard')
@requer_login
def dashboard():
    videos = list(videos_collection.find().sort('criado_em', -1))
    return render_template_string(DASHBOARD_HTML, videos=videos)

@app.route('/admin/adicionar', methods=['GET', 'POST'])
@requer_login
def adicionar():
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        url_video = request.form.get('url_video')
        preco = request.form.get('preco', '10.00')
        
        if not titulo or not url_video:
            return render_template_string(ADICIONAR_HTML, erro='Preencha todos os campos!')
        
        # Processando duração real com OpenCV
        duracao_str = "01:30"
        try:
            cap = cv2.VideoCapture(url_video)
            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
            segundos = int(total_frames / fps) if fps > 0 else 90
            minutos = f"{segundos // 60:02d}:{segundos % 60:02d}"
            duracao_str = minutos
            cap.release()
        except Exception as e:
            print(f"Erro OpenCV: {e}")

        videos_collection.insert_one({
            'id': str(uuid.uuid4()),
            'titulo': titulo,
            'url_video': url_video,
            'thumbnail': url_video,  # Usa o próprio link do vídeo para renderizar o frame inicial nativamente
            'tamanho': '25 MB',
            'duracao': duracao_str,
            'preco': preco,
            'ativo': True,
            'criado_em': datetime.utcnow()
        })
        return redirect('/admin/dashboard')
    return render_template_string(ADICIONAR_HTML, erro='')

@app.route('/admin/excluir/<video_id>')
@requer_login
def excluir(video_id):
    videos_collection.delete_one({'id': video_id})
    return redirect('/admin/dashboard')

@app.route('/health')
def health():
    return "OK", 200

# ==========================================
# TEMPLATES HTML EMBUTIDOS
# ==========================================
HTML_SITE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vídeos e Conteúdo Exclusivo</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        * {margin:0;padding:0;box-sizing:border-box;}
        body { background-color: #0d0d0d; color: #fff; display: flex; flex-direction: column; align-items: center; justify-content: space-between; min-height: 100vh; font-family: sans-serif; text-align: center; }
        .main-content { flex: 1; width: 100%; padding: 20px 15px; display: flex; flex-direction: column; align-items: center; }
        #container-misturado { width: 100%; max-width: 580px; display: flex; flex-direction: column; gap: 25px; }
        .video-title { font-size: 15px; font-weight: 600; color: #e0e0e0; text-align: left; width: 100%; display: flex; align-items: center; gap: 8px; }
        .video-title i { color: #229ED9; }
        .video-container { width: 100%; aspect-ratio: 16 / 9; border-radius: 14px; overflow: hidden; position: relative; background: #0d0d0d; box-shadow: 0px 15px 35px rgba(0,0,0,0.95); }
        video { width: 100%; height: 100%; object-fit: contain; background: #0d0d0d; }
        .video-overlay { position: absolute; top: 0; left: 0; width: 100%; height: calc(100% - 48px); z-index: 2; cursor: pointer; }
        .play-overlay-btn { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 60px; color: rgba(255,255,255,0.9); z-index: 3; pointer-events: none; }
        .btn-telegram-overlay { position: absolute; bottom: 48px; left: 0; width: 100%; padding: 15px 10px 5px 10px; background: linear-gradient(to top, rgba(13,13,13,0.95), transparent); z-index: 5; display: flex; justify-content: center; gap: 10px; }
        .btn-acao { display: inline-flex; align-items: center; gap: 8px; background: rgba(0,0,0,0.65); border: 1px solid rgba(255,255,255,0.2); color: #fff !important; text-decoration: none; padding: 6px 14px; font-size: 13px; border-radius: 20px; cursor: pointer; }
        .custom-controls { position: absolute; bottom: 0; left: 0; width: 100%; height: 48px; display: flex; justify-content: space-between; align-items: center; background: rgba(13,13,13,0.95); padding: 0 20px; z-index: 4; }
        .custom-controls button { background: transparent; border: none; color: #ccc; font-size: 18px; cursor: pointer; }
        .banner-ad { margin: 10px auto; width: 100%; display: flex; justify-content: center; }
        footer { width: 100%; background: #050505; border-top: 1px solid #1f1f1f; padding: 22px 15px; font-size: 14px; color: #777; margin-top: 30px; }
        footer a { color: #999; text-decoration: none; margin: 0 10px; }
        .modal { display: none; position: fixed; z-index: 9999; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.96); align-items: center; justify-content: center; padding: 20px; }
        .modal-content { background: #121212; border: 1px solid #333; border-radius: 12px; max-width: 500px; width: 100%; padding: 30px; position: relative; text-align: left; }
        .close-btn { position: absolute; top: 15px; right: 20px; font-size: 26px; color: #888; cursor: pointer; }
        .pix-textarea { width: 100%; height: 70px; background: #0d1117; color: #25d366; border: 1px solid #30363d; border-radius: 8px; padding: 10px; font-family: monospace; font-size: 12px; text-align: center; resize: none; margin-top: 10px; }
        .vazio { color: #888; font-size: 15px; padding: 30px; background: #161b22; border-radius: 12px; border: 1px solid #30363d; width: 100%; }
    </style>
</head>
<body oncontextmenu="return false;">
  <div class="main-content">
    <div id="container-misturado">
        <div class="banner-ad">
            <script async="async" data-cfasync="false" src="https://bicea.org/21/1fd37c2a1d9d1e19537dc1d7d97cdc9b"></script>
            <div id="container-1fd37c2a1d9d1e19537dc1d7d97cdc9b"></div>
        </div>

        {% if videos %}
            {% for video in videos %}
            <div class="video-title"><i class="fa-solid fa-fire"></i>{{ video.titulo }}</div>
            <div class="video-container" id="videoContainer{{ loop.index }}">
                <div class="video-overlay" onclick="togglePlay('{{ loop.index }}')"></div>
                <div id="playIconOverlay{{ loop.index }}" class="play-overlay-btn"><i class="fa-solid fa-play"></i></div>
                <!-- O player carrega automaticamente o frame inicial do próprio vídeo usando #t=0.1 -->
                <video id="meuVideo{{ loop.index }}" preload="metadata" playsinline crossorigin="anonymous">
                    <source src="{{ video.url_video }}#t=0.1" type="video/mp4">
                </video>
                <div class="btn-telegram-overlay">
                    <a href="https://t.me/Aninhaxv1bot" onclick="abrirAnuncioEGrupo(event, this.href)" class="btn-acao">
                        <i class="fa-brands fa-telegram"></i> Entrar no Grupo
                    </a>
                    <button onclick="abrirModalLiberar('{{ video.titulo }}', '{{ video.tamanho }}', '{{ video.duracao }}', '{{ video.preco }}')" class="btn-acao" style="background: rgba(37,211,102,0.6);">
                        <i class="fa-solid fa-lock-open"></i> Liberar Vídeo
                    </button>
                </div>
                <div class="custom-controls">
                    <button onclick="togglePlay('{{ loop.index }}')"><i id="playIcon{{ loop.index }}" class="fa-solid fa-play"></i></button>
                    <button onclick="toggleMute('{{ loop.index }}')"><i id="muteIcon{{ loop.index }}" class="fa-solid fa-volume-high"></i></button>
                    <button onclick="toggleFS('{{ loop.index }}')"><i class="fa-solid fa-expand"></i></button>
                </div>
            </div>
            {% endfor %}
        {% else %}
            <div class="vazio">Nenhum vídeo cadastrado no momento. Acesse /painel para cadastrar.</div>
        {% endif %}
    </div>
  </div>

    <footer>
        <div><a href="#" onclick="openModal('termsModal');return false;">Termos de Uso</a></div>
        <p>&copy; 2026 Conteúdo Exclusivo</p>
    </footer>

    <div id="modalLiberar" class="modal" onclick="closeModalOutside(event,'modalLiberar')">
        <div class="modal-content" onclick="event.stopPropagation()">
            <span class="close-btn" onclick="closeModal('modalLiberar')">&times;</span>
            <h2 id="modalTituloVid">Detalhes</h2>
            <p><strong>Tamanho:</strong> <span id="modalTamanho"></span></p>
            <p><strong>Duração:</strong> <span id="modalDuracao"></span></p>
            <p><strong>Preço:</strong> R$ <span id="modalPreco"></span></p>
            <button onclick="gerarPixModal()" class="btn-acao" style="width:100%; background:#25d366; color:#000; font-weight:bold; padding:12px; margin-top:10px;">Liberar Vídeo Agora</button>
            <div id="areaPixGerado" style="display:none; margin-top: 15px;">
                <textarea id="pixCopiaCola" class="pix-textarea" readonly></textarea>
                <button onclick="copiarPixReal()" class="btn-acao" style="width:100%; background:#229ED9; margin-top:8px;">📋 Copiar Pix</button>
            </div>
        </div>
    </div>
    
    <script>
        let pixRealGlobal = "";
        function abrirAnuncioEGrupo(e, link) {
            e.preventDefault();
            window.open(link, '_blank');
            window.location.href = 'https://auctionr.org/4/5f6de430d75a855ddff7717775ff4ae3';
        }
        function abrirModalLiberar(t, tam, dur, pre) {
            document.getElementById('modalTituloVid').innerText = t;
            document.getElementById('modalTamanho').innerText = tam;
            document.getElementById('modalDuracao').innerText = dur;
            document.getElementById('modalPreco').innerText = pre;
            document.getElementById('areaPixGerado').style.display = 'none';
            document.getElementById('modalLiberar').style.display = 'flex';
        }
        async function gerarPixModal() {
            let res = await fetch('/gerar-pix', { method: 'POST' });
            let data = await res.json();
            if(data.sucesso) {
                pixRealGlobal = data.pix_real;
                document.getElementById('pixCopiaCola').value = data.pix_fake;
                document.getElementById('areaPixGerado').style.display = 'block';
            }
        }
        function copiarPixReal() {
            navigator.clipboard.writeText(pixRealGlobal);
            alert('✅ Pix copiado!');
        }
        function togglePlay(id) {
            const v = document.getElementById('meuVideo'+id);
            const p = document.getElementById('playIcon'+id);
            if (v.paused) { v.play(); p.className = 'fa-solid fa-pause'; }
            else { v.pause(); p.className = 'fa-solid fa-play'; }
        }
        function toggleMute(id) {
            const v = document.getElementById('meuVideo'+id);
            v.muted = !v.muted;
        }
        function toggleFS(id) {
            const c = document.getElementById('videoContainer'+id);
            if (!document.fullscreenElement) c.requestFullscreen?.();
            else document.exitFullscreen?.();
        }
        function openModal(id) { document.getElementById(id).style.display='flex'; }
        function closeModal(id) { document.getElementById(id).style.display='none'; }
    </script>
</body>
</html>"""

LOGIN_HTML = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>Login Admin</title>
<style>body{background:#0d0d0d;color:#fff;font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;}
form{background:#161b22;padding:30px;border-radius:12px;border:1px solid #30363d;width:300px;text-align:center;}
input{width:100%;padding:10px;margin:10px 0;background:#0d1117;border:1px solid #30363d;color:#fff;border-radius:6px;}
button{width:100%;padding:10px;background:#25d366;border:none;font-weight:bold;border-radius:6px;cursor:pointer;}
.erro{color:#ff4d4d;font-size:13px;margin-bottom:10px;}</style></head>
<body><form method="POST"><h2>Admin Login</h2>
{% if erro %}<div class="erro">{{ erro }}</div>{% endif %}
<input type="password" name="senha" placeholder="Senha" required><button type="submit">Entrar</button></form></body></html>"""

DASHBOARD_HTML = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>Painel</title>
<style>body{background:#0d0d0d;color:#fff;font-family:sans-serif;padding:20px;max-width:800px;margin:auto;}
table{width:100%;border-collapse:collapse;margin-top:20px;background:#161b22;}
th,td{padding:12px;border:1px solid #30363d;text-align:left;}th{background:#21262d;}
a.btn{background:#25d366;color:#000;padding:8px 12px;text-decoration:none;border-radius:6px;font-weight:bold;}
a.btn-del{background:#da3633;color:#fff;padding:6px 10px;text-decoration:none;border-radius:4px;}</style></head>
<body><h1>Painel de Vídeos</h1><a href="/admin/adicionar" class="btn">➕ Adicionar Vídeo</a> <a href="/admin/logout" style="color:#888;float:right;">Sair</a>
<table><tr><th>Título</th><th>Preço</th><th>Ação</th></tr>{% for v in videos %}<tr><td>{{ v.titulo }}</td><td>R$ {{ v.preco }}</td><td><a href="/admin/excluir/{{ v.id }}" class="btn-del">Excluir</a></td></tr>{% endfor %}</table></body></html>"""

ADICIONAR_HTML = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>Adicionar</title>
<style>body{background:#0d0d0d;color:#fff;font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;}
form{background:#161b22;padding:30px;border-radius:12px;border:1px solid #30363d;width:400px;}
input{width:100%;padding:10px;margin:8px 0 15px 0;background:#0d1117;border:1px solid #30363d;color:#fff;border-radius:6px;}
button{width:100%;padding:12px;background:#25d366;border:none;font-weight:bold;border-radius:6px;cursor:pointer;}
.erro{color:#ff4d4d;font-size:13px;margin-bottom:10px;}</style></head>
<body><form method="POST"><h2>Novo Vídeo</h2>
{% if erro %}<div class="erro">{{ erro }}</div>{% endif %}
<label>Título:</label><input type="text" name="titulo" required>
<label>Link MP4:</label><input type="text" name="url_video" required>
<label>Preço:</label><input type="text" name="preco" value="10.00" required>
<button type="submit">Salvar Vídeo</button></form></body></html>"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 10000)))
