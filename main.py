from flask import Flask, render_template_string, jsonify, request, redirect, url_for, session
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import uuid
import requests
from datetime import datetime

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
ADMIN_SENHA = os.getenv('ADMIN_SENHA')

# Conexão MongoDB
client = MongoClient(os.getenv('MONGO_URI'))
db = client['video_site']
videos_collection = db['videos']
MP_TOKEN = os.getenv('MP_TOKEN')

# Capa padrão automática solicitada
CAPA_PADRAO = "https://files.catbox.moe/uw9r9l.png"

# ==========================================
# HEADERS DE SEGURANÇA E PROTEÇÃO CONTRA ATAQUES
# ==========================================
@app.after_request
def adicionar_seguranca(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

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
        thumbnail = request.form.get('thumbnail', '').strip()
        preco = request.form.get('preco', '10.00')
        
        if not titulo or not url_video:
            return render_template_string(ADICIONAR_HTML, erro='Preencha o título e o link do vídeo!')
        
        # Obedece rigorosamente o link da capa inserido no painel ADM; se estiver vazio, usa a padrão.
        if not thumbnail:
            thumbnail = CAPA_PADRAO

        videos_collection.insert_one({
            'id': str(uuid.uuid4()),
            'titulo': titulo,
            'url_video': url_video,
            'thumbnail': thumbnail,
            'tamanho': '25 MB',
            'duracao': '01:30',
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
# TEMPLATES HTML EMBUTIDOS (SEO, SEGURANÇA E DESIGN PROFISSIONAL)
# ==========================================
HTML_SITE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vídeos Exclusivos e Conteúdos VIP | Acesso Imediato</title>
    <meta name="description" content="Assista aos melhores vídeos exclusivos, conteúdos VIP atualizados diariamente com liberação instantânea via Pix.">
    <meta name="keywords" content="videos exclusivos, conteudos vip, midias, pix, entretenimento">
    <meta name="robots" content="index, follow">
    <meta property="og:title" content="Vídeos Exclusivos e Conteúdos VIP">
    <meta property="og:description" content="Acesse vídeos exclusivos e libere seu conteúdo instantaneamente.">
    <meta property="og:type" content="website">
    
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        * {margin:0;padding:0;box-sizing:border-box;}
        body { background-color: #0d0d0d; color: #fff; display: flex; flex-direction: column; align-items: center; justify-content: space-between; min-height: 100vh; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; }
        .main-content { flex: 1; width: 100%; padding: 20px 15px; display: flex; flex-direction: column; align-items: center; }
        #container-misturado { width: 100%; max-width: 580px; display: flex; flex-direction: column; gap: 25px; }
        
        .video-title { font-size: 15px; font-weight: 600; color: #e0e0e0; text-align: left; width: 100%; display: flex; align-items: center; gap: 8px; }
        .video-title i { color: #25d366; }
        .video-container { width: 100%; aspect-ratio: 16 / 9; border-radius: 14px; overflow: hidden; position: relative; background: #0d0d0d; box-shadow: 0px 15px 35px rgba(0,0,0,0.95); }
        video { width: 100%; height: 100%; object-fit: cover; background: #0d0d0d; }
        .video-overlay { position: absolute; top: 0; left: 0; width: 100%; height: calc(100% - 48px); z-index: 2; cursor: pointer; }
        .play-overlay-btn { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 60px; color: rgba(255,255,255,0.9); z-index: 3; pointer-events: none; text-shadow: 0 4px 10px rgba(0,0,0,0.8); }
        
        .btn-telegram-overlay { position: absolute; bottom: 48px; left: 0; width: 100%; padding: 15px 10px 5px 10px; background: linear-gradient(to top, rgba(13,13,13,0.95), transparent); z-index: 5; display: flex; justify-content: center; }
        .btn-acao { display: inline-flex; align-items: center; justify-content: center; gap: 8px; background: linear-gradient(135deg, #25d366, #1ebe57); border: none; color: #000 !important; font-weight: 700; text-decoration: none; padding: 10px 22px; font-size: 14px; border-radius: 25px; cursor: pointer; box-shadow: 0 4px 15px rgba(37,211,102,0.4); transition: transform 0.2s, box-shadow 0.2s; }
        .btn-acao:hover { transform: scale(1.03); box-shadow: 0 6px 20px rgba(37,211,102,0.6); }
        
        .custom-controls { position: absolute; bottom: 0; left: 0; width: 100%; height: 48px; display: flex; justify-content: space-between; align-items: center; background: rgba(13,13,13,0.95); padding: 0 20px; z-index: 4; }
        .custom-controls button { background: transparent; border: none; color: #ccc; font-size: 18px; cursor: pointer; }
        .banner-ad { margin: 10px auto; width: 100%; display: flex; justify-content: center; }
        
        .hub-promo-card { background: linear-gradient(145deg, #161b22, #0d1117); border: 1px solid #30363d; border-radius: 14px; padding: 15px; text-decoration: none; color: #fff; display: flex; flex-direction: column; align-items: center; gap: 10px; box-shadow: 0 8px 25px rgba(0,0,0,0.8); transition: transform 0.2s, border-color 0.2s; }
        .hub-promo-card:hover { transform: translateY(-2px); border-color: #25d366; }
        .hub-promo-card img { width: 100%; max-height: 160px; object-fit: cover; border-radius: 10px; }
        .hub-promo-text { font-size: 14px; font-weight: 600; color: #f0f6fc; }
        .hub-promo-btn { background: #238636; color: #fff; padding: 6px 16px; border-radius: 20px; font-size: 12px; font-weight: bold; }

        footer { width: 100%; background: #050505; border-top: 1px solid #1f1f1f; padding: 22px 15px; font-size: 14px; color: #777; margin-top: 30px; }
        footer a { color: #999; text-decoration: none; margin: 0 10px; }
        
        .modal { display: none; position: fixed; z-index: 9999; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); backdrop-filter: blur(8px); align-items: center; justify-content: center; padding: 20px; animation: fadeIn 0.3s ease; }
        .modal-content { background: linear-gradient(160deg, #161b22, #0d1117); border: 1px solid #30363d; border-radius: 18px; max-width: 440px; width: 100%; padding: 30px; position: relative; text-align: left; box-shadow: 0 20px 40px rgba(0,0,0,0.9); }
        .modal-content h2 { color: #fff; font-size: 20px; margin-bottom: 15px; border-bottom: 1px solid #21262d; padding-bottom: 10px; display: flex; align-items: center; gap: 10px; }
        .modal-content h2 i { color: #25d366; }
        .modal-info-box { background: #0d1117; border: 1px solid #21262d; border-radius: 10px; padding: 12px 15px; margin-bottom: 15px; }
        .modal-info-box p { color: #8b949e; font-size: 14px; margin-bottom: 6px; display: flex; justify-content: space-between; }
        .modal-info-box p span { color: #f0f6fc; font-weight: 600; }
        .close-btn { position: absolute; top: 20px; right: 20px; font-size: 22px; color: #8b949e; cursor: pointer; background: #21262d; width: 35px; height: 35px; border-radius: 50%; display: flex; align-items: center; justify-content: center; transition: background 0.2s, color 0.2s; }
        .close-btn:hover { background: #da3633; color: #fff; }
        .pix-textarea { width: 100%; height: 80px; background: #0d1117; color: #25d366; border: 1px solid #30363d; border-radius: 10px; padding: 12px; font-family: monospace; font-size: 12px; text-align: center; resize: none; margin-top: 10px; }
        
        #toast-notificacao { visibility: hidden; min-width: 250px; background-color: #238636; color: #fff; text-align: center; border-radius: 12px; padding: 14px; position: fixed; z-index: 100000; left: 50%; bottom: 30px; transform: translateX(-50%); font-size: 14px; font-weight: 600; box-shadow: 0 5px 20px rgba(0,0,0,0.5); opacity: 0; transition: opacity 0.3s, bottom 0.3s; }
        #toast-notificacao.show { visibility: visible; opacity: 1; bottom: 50px; }

        .vazio { color: #888; font-size: 15px; padding: 30px; background: #161b22; border-radius: 12px; border: 1px solid #30363d; width: 100%; }
        @keyframes fadeIn { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }
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
                <!-- Respeita explicitamente a thumbnail cadastrada no banco de dados -->
                <video id="meuVideo{{ loop.index }}" preload="metadata" playsinline crossorigin="anonymous" poster="{{ video.thumbnail }}">
                    <source src="{{ video.url_video }}" type="video/mp4">
                </video>
                <div class="btn-telegram-overlay">
                    <button onclick="abrirModalLiberar('{{ video.titulo }}', '{{ video.tamanho }}', '{{ video.duracao }}', '{{ video.preco }}')" class="btn-acao">
                        <i class="fa-solid fa-lock-open"></i> Liberar Acesso VIP
                    </button>
                </div>
                <div class="custom-controls">
                    <button onclick="togglePlay('{{ loop.index }}')"><i id="playIcon{{ loop.index }}" class="fa-solid fa-play"></i></button>
                    <button onclick="toggleMute('{{ loop.index }}')"><i id="muteIcon{{ loop.index }}" class="fa-solid fa-volume-high"></i></button>
                    <button onclick="toggleFS('{{ loop.index }}')"><i class="fa-solid fa-expand"></i></button>
                </div>
            </div>

            {% if loop.index == 1 %}
            <div class="banner-ad">
                <script>atOptions = { 'key' : '3e1fe799cb19b129dba9470a4e2f2556', 'format' : 'iframe', 'height' : 250, 'width' : 300, 'params' : {} };</script>
                <script src="https://bicea.org/22/3e1fe799cb19b129dba9470a4e2f2556"></script>
            </div>
            
            <div class="banner-ad">
                <a href="https://app.hub.xyz/r/NN4WTT5R" target="_blank" class="hub-promo-card">
                    <img src="https://files.catbox.moe/prb59o.webp" alt="Tarefas Diárias">
                    <div class="hub-promo-text">Ganhe dinheiro fazendo tarefas do dia a dia</div>
                    <span class="hub-promo-btn">Participar Agora</span>
                </a>
            </div>
            {% endif %}

            {% endfor %}
        {% else %}
            <div class="vazio">Nenhum vídeo cadastrado no momento. O conteúdo será atualizado em breve.</div>
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
            <h2><i class="fa-solid fa-shield-halved"></i> Liberação Instantânea</h2>
            <p id="modalTituloVid" style="color:#f0f6fc; font-weight:600; margin-bottom:15px; font-size:15px;"></p>
            
            <div class="modal-info-box">
                <p>Tamanho do arquivo: <span id="modalTamanho"></span></p>
                <p>Duração total: <span id="modalDuracao"></span></p>
                <p>Valor do acesso: <span style="color:#25d366; font-size:16px;">R$ <span id="modalPreco"></span></span></p>
            </div>

            <button onclick="gerarPixModal()" class="btn-acao" style="width:100%; padding:12px; font-size:15px;">Gerar Chave Pix de Pagamento</button>
            
            <div id="areaPixGerado" style="display:none; margin-top: 15px;">
                <p style="font-size:12px; color:#8b949e; margin-bottom:5px;">Copie o código abaixo e pague no app do seu banco:</p>
                <textarea id="pixCopiaCola" class="pix-textarea" readonly></textarea>
                <button onclick="copiarPixReal()" class="btn-acao" style="width:100%; background: linear-gradient(135deg, #229ED9, #1b85b8); color:#fff !important; margin-top:10px; padding:10px;"><i class="fa-solid fa-copy"></i> Copiar Código Pix</button>
            </div>
        </div>
    </div>
    
    <div id="toast-notificacao"><i class="fa-solid fa-circle-check"></i> Código Pix copiado com sucesso!</div>

    <script>
        let pixRealGlobal = "";
        
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
            mostrarToast();
        }

        function mostrarToast() {
            const toast = document.getElementById("toast-notificacao");
            toast.className = "show";
            setTimeout(function(){ toast.className = toast.className.replace("show", ""); }, 3500);
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
        function closeModalOutside(e,id) { if(e.target===e.currentTarget) closeModal(id); }
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
<label>Link Direto do Vídeo (.mp4):</label><input type="text" name="url_video" required>
<label>Link da Capa (Opcional - se vazio usa a padrão):</label><input type="text" name="thumbnail" placeholder="Cole o link da foto de capa aqui">
<label>Preço (R$):</label><input type="text" name="preco" value="10.00" required>
<button type="submit">Salvar Vídeo</button></form></body></html>"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 10000)))
