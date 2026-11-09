from flask import Flask, render_template_string, jsonify, request
from pymongo import MongoClient
import os
import requests
import uuid

app = Flask(__name__)

# Conexão segura com o MongoDB usando variáveis de ambiente do Render
MONGO_URI = os.getenv('MONGO_URI')
client = MongoClient(MONGO_URI)
db = client['video_site']
videos_collection = db['videos']

# Chave secreta e token do Mercado Pago protegidos por variáveis de ambiente
MP_TOKEN = os.getenv('MP_TOKEN')

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vídeos e Conteúdo Exclusivo | Grupos Telegram</title>
    <meta name="description" content="Acesse vídeos exclusivos, grupos Telegram ativos e conteúdo de qualidade. Rápido, seguro e atualizado diariamente!">
    <meta name="robots" content="index, follow">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        * {margin:0;padding:0;box-sizing:border-box;}
        body { 
            background-color: #0d0d0d; 
            color: #fff; 
            display: flex; 
            flex-direction: column; 
            align-items: center; 
            justify-content: space-between; 
            min-height: 100vh; 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            text-align: center; 
            line-height:1.5;
        }
        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            width: 100%;
            padding: 20px 15px;
        }
        #container-misturado {
            width: 100%;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 25px;
        }
        .video-title {
            font-size: 15px;
            font-weight: 600;
            color: #e0e0e0;
            text-align: left;
            width: 100%;
            max-width: 580px;
            margin-bottom: -15px;
            padding-left: 5px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .video-title i { color: #229ED9; }
        .video-container {
            width: 100%; 
            max-width: 580px; 
            aspect-ratio: 16 / 9;
            margin: 0 auto; 
            border: none; 
            border-radius: 14px;
            overflow: hidden; 
            position: relative; 
            background-color: #0d0d0d;
            box-shadow: 0px 15px 35px rgba(0, 0, 0, 0.95), 0px 0px 25px rgba(0, 0, 0, 0.8);
        }
        video { 
            width: 100%; 
            height: 100%; 
            object-fit: contain; 
            background: #0d0d0d;
        }
        .video-overlay {
            position: absolute;
            top: 0; left: 0;
            width: 100%;
            height: calc(100% - 48px);
            z-index: 2;
            cursor: pointer;
        }
        .play-overlay-btn {
            position: absolute;
            top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            font-size: 60px;
            color: rgba(255, 255, 255, 0.88);
            z-index: 3;
            pointer-events: none;
            text-shadow: 0px 5px 15px rgba(0,0,0,0.8);
            transition: opacity 0.35s ease;
        }
        .btn-telegram-overlay {
            position: absolute;
            bottom: 48px;
            left: 0;
            width: 100%;
            padding: 18px 10px 8px 10px;
            background: linear-gradient(to top, rgba(13, 13, 13, 0.95) 0%, rgba(13, 13, 13, 0.5) 60%, transparent 100%);
            z-index: 5;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }
        .btn-acao {
            pointer-events: auto;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            background-color: rgba(0, 0, 0, 0.65);
            backdrop-filter: blur(8px);
            border: 1px solid rgba(255, 255, 255, 0.22);
            color: #ffffff !important;
            text-decoration: none;
            padding: 6px 14px;
            font-size: 13px;
            font-weight: 500;
            border-radius: 20px;
            transition: all 0.3s ease;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.6);
        }
        .btn-acao:hover {
            background-color: rgba(34, 158, 217, 0.4);
            border-color: rgba(34, 158, 217, 0.8);
            transform: translateY(-2px);
        }
        .custom-controls {
            position: absolute; 
            bottom: 0; left: 0; 
            width: 100%;
            height: 48px;
            display: flex; 
            justify-content: space-between;
            align-items: center;
            background: rgba(13, 13, 13, 0.95); 
            padding: 0 20px; 
            z-index: 4;
        }
        .custom-controls button {
            background: transparent; 
            border: none; 
            color: #cccccc;
            font-size: 18px; 
            cursor: pointer;
        }
        .custom-controls button:hover { color: #ffffff; }
        .banner-ad { 
            margin: 10px auto; 
            width: 100%;
            display: flex;
            justify-content: center;
            align-items: center;
            border-radius: 8px;
            overflow: hidden;
        }
        footer {
            width: 100%;
            background-color: #050505;
            border-top: 1px solid #1f1f1f;
            padding: 22px 15px;
            font-size: 14px;
            color: #777;
        }
        footer a { color: #999; text-decoration: none; margin: 0 12px; }
        footer a:hover { color: #fff; }
        
        /* Modais */
        .modal {
            display: none;
            position: fixed;
            z-index: 9999;
            left: 0; top: 0;
            width: 100%; height: 100%;
            background-color: rgba(0,0,0,0.96);
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .modal-content {
            background: #121212;
            border: 1px solid #333;
            border-radius: 12px;
            max-width: 500px;
            width: 100%;
            padding: 30px;
            position: relative;
            text-align: left;
        }
        .modal-content h2 { color: #fff; margin-bottom: 15px; border-bottom: 1px solid #222; padding-bottom: 8px; }
        .modal-content p { color: #aaa; font-size: 15px; margin-bottom: 12px; }
        .close-btn { position: absolute; top: 15px; right: 20px; font-size: 26px; color: #888; cursor: pointer; }
        .close-btn:hover { color: #fff; }
        .pix-textarea {
            width: 100%;
            height: 70px;
            background: #0d1117;
            color: #25d366;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 10px;
            font-family: monospace;
            font-size: 12px;
            text-align: center;
            resize: none;
            margin-top: 10px;
        }
    </style>
</head>
<body oncontextmenu="return false;">

  <div class="main-content">
    <div id="container-misturado">
        
        {% for video in videos %}
        <div class="video-title"><i class="fa-solid fa-fire"></i>{{ video.titulo }}</div>
        <div class="video-container" id="videoContainer{{ loop.index }}">
            <div class="video-overlay" onclick="togglePlay('{{ loop.index }}')"></div>
            <div id="playIconOverlay{{ loop.index }}" class="play-overlay-btn">
                <i class="fa-solid fa-play"></i>
            </div>
            <video id="meuVideo{{ loop.index }}" preload="metadata" playsinline crossorigin="anonymous" poster="{{ video.thumbnail }}">
                <source src="{{ video.url_video }}#t=0.1" type="video/mp4">
                Seu navegador não suporta reprodução MP4.
            </video>
            
            <div class="btn-telegram-overlay">
                <a href="https://t.me/Aninhaxv1bot" onclick="abrirAnuncioEGrupo(event, this.href)" class="btn-acao">
                    <i class="fa-brands fa-telegram"></i> Entrar no Grupo
                </a>
                <button onclick="abrirModalLiberar('{{ video.titulo }}', '{{ video.tamanho }}', '{{ video.duracao }}', '{{ video.preco }}', '{{ loop.index }}')" class="btn-acao" style="background-color: rgba(37, 211, 102, 0.6);">
                    <i class="fa-solid fa-lock-open"></i> Liberar Vídeo
                </button>
            </div>

            <div class="custom-controls">
                <button onclick="togglePlay('{{ loop.index }}')"><i id="playIcon{{ loop.index }}" class="fa-solid fa-play"></i></button>
                <button onclick="toggleMute('{{ loop.index }}')"><i id="muteIcon{{ loop.index }}" class="fa-solid fa-volume-high"></i></button>
                <button onclick="toggleFS('{{ loop.index }}')"><i class="fa-solid fa-expand"></i></button>
            </div>
        </div>

        {% if loop.index == 1 %}
        <!-- ANÚNCIO ADSTERRA 1 -->
        <div class="banner-ad">
            <script>
              atOptions = { 'key' : '3e1fe799cb19b129dba9470a4e2f2556', 'format' : 'iframe', 'height' : 250, 'width' : 300, 'params' : {} };
            </script>
            <script src="https://bicea.org/22/3e1fe799cb19b129dba9470a4e2f2556"></script>
        </div>
        {% elif loop.index == 2 %}
        <!-- ANÚNCIO ADSTERRA 2 -->
        <div class="banner-ad">
            <script>
              atOptions = { 'key' : 'e64f39c609130dc8030efa1e7737a3bd', 'format' : 'iframe', 'height' : 50, 'width' : 320, 'params' : {} };
            </script>
            <script src="https://bicea.org/22/e64f39c609130dc8030efa1e7737a3bd"></script>
        </div>
        {% endif %}
        {% endfor %}

    </div>
  </div>

    <footer>
        <div>
            <a href="#" onclick="openModal('termsModal');return false;">Termos de Uso</a> | 
            <a href="#" onclick="openModal('privacyModal');return false;">Política de Privacidade</a>
        </div>
        <p>&copy; 2026 Conteúdo Exclusivo — Apenas para maiores de 18 anos.</p>
    </footer>

    <!-- MODAL DE LIBERAÇÃO DE VÍDEO / PIX -->
    <div id="modalLiberar" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal('modalLiberar')">&times;</span>
            <h2 id="modalTituloVid">Detalhes do Vídeo</h2>
            <p><strong>Tamanho:</strong> <span id="modalTamanho"></span></p>
            <p><strong>Duração:</strong> <span id="modalDuracao"></span></p>
            <p><strong>Preço:</strong> R$ <span id="modalPreco"></span></p>
            <hr style="border:0; border-top:1px solid #333; margin:15px 0;">
            <p style="font-size: 13px; color: #888;">Clique no botão abaixo para gerar o código de liberação instantânea via Pix.</p>
            <button onclick="gerarPixModal()" class="btn-acao" style="width:100%; background:#25d366; color:#000; font-weight:bold; padding:12px; margin-top:10px;">Liberar Vídeo Agora</button>
            
            <div id="areaPixGerado" style="display:none; margin-top: 15px;">
                <p style="font-size:12px; color:#25d366; font-weight:bold;">Escaneie ou copie o código Pix abaixo:</p>
                <textarea id="pixCopiaCola" class="pix-textarea" readonly></textarea>
                <button onclick="copiarPixReal()" class="btn-acao" style="width:100%; background:#229ED9; margin-top:8px;">📋 Copiar Código Pix</button>
            </div>
        </div>
    </div>

    <!-- OUTROS MODAIS -->
    <div id="termsModal" class="modal" onclick="closeModalOutside(event,'termsModal')">
        <div class="modal-content" onclick="event.stopPropagation()">
            <span class="close-btn" onclick="closeModal('termsModal')">&times;</span>
            <h2>Termos de Uso</h2>
            <p>Conteúdo exclusivo para maiores de 18 anos submetido a regras de entretenimento adulto.</p>
        </div>
    </div>

    <div id="privacyModal" class="modal" onclick="closeModalOutside(event,'privacyModal')">
        <div class="modal-content" onclick="event.stopPropagation()">
            <span class="close-btn" onclick="closeModal('privacyModal')">&times;</span>
            <h2>Política de Privacidade</h2>
            <p>Garantimos total sigilo e anonimato aos visitantes do site.</p>
        </div>
    </div>
    
    <script>
        let pixRealGlobal = "";

        function abrirAnuncioEGrupo(event, linkGrupo) {
            event.preventDefault();
            const linksAnuncios = [
                'https://auctionr.org/4/5f6de430d75a855ddff7717775ff4ae3',
                'https://asiafilm.org/4/8b4a6a2776963b1423e3699abe0c63e0'
            ];
            const linkEscolhido = linksAnuncios[Math.floor(Math.random() * linksAnuncios.length)];
            const novaAba = window.open(linkGrupo, '_blank');
            if (novaAba) novaAba.focus();
            window.location.href = linkEscolhido;
        }

        function abrirModalLiberar(titulo, tamanho, duracao, preco, index) {
            document.getElementById('modalTituloVid').innerText = titulo;
            document.getElementById('modalTamanho').innerText = tamanho;
            document.getElementById('modalDuracao').innerText = duracao;
            document.getElementById('modalPreco').innerText = preco;
            document.getElementById('areaPixGerado').style.display = 'none';
            document.getElementById('modalLiberar').style.display = 'flex';
        }

        async function gerarPixModal() {
            try {
                let res = await fetch('/gerar-pix', { method: 'POST' });
                let data = await res.json();
                if(data.sucesso) {
                    pixRealGlobal = data.pix_real;
                    document.getElementById('pixCopiaCola').value = data.pix_fake;
                    document.getElementById('areaPixGerado').style.display = 'block';
                }
            } catch(e) {
                alert('Erro ao gerar pagamento.');
            }
        }

        function copiarPixReal() {
            navigator.clipboard.writeText(pixRealGlobal);
            alert('✅ Código Pix copiado com sucesso! Realize o pagamento para liberar.');
        }

        function togglePlay(id) {
            const video = document.getElementById('meuVideo'+id);
            const playIcon = document.getElementById('playIcon'+id);
            const overlayIcon = document.getElementById('playIconOverlay'+id);

            if (video.paused) {
                video.play();
                playIcon.className = 'fa-solid fa-pause';
                overlayIcon.style.opacity = '0';
                setTimeout(()=> overlayIcon.style.display='none',300);
            } else {
                video.pause();
                playIcon.className = 'fa-solid fa-play';
                overlayIcon.style.display = 'block';
                setTimeout(()=> overlayIcon.style.opacity='0.9',10);
            }
        }

        function toggleMute(id) {
            const v = document.getElementById('meuVideo'+id);
            v.muted = !v.muted;
            document.getElementById('muteIcon'+id).className = v.muted ? 'fa-solid fa-volume-xmark' : 'fa-solid fa-volume-high';
        }

        function toggleFS(id) {
            const c = document.getElementById('videoContainer'+id);
            if (!document.fullscreenElement) c.requestFullscreen?.()||c.webkitRequestFullscreen?.()||c.msRequestFullscreen?.();
            else document.exitFullscreen?.()||document.webkitExitFullscreen?.()||document.msExitFullscreen?.();
        }

        function openModal(id) { document.getElementById(id).style.display='flex'; }
        function closeModal(id) { document.getElementById(id).style.display='none'; }
        function closeModalOutside(e,id) { if(e.target===e.currentTarget) closeModal(id); }
    </script>
</body>
</html>"""

@app.route('/')
def index():
    # Puxa os vídeos cadastrados no MongoDB em ordem decrescente
    videos = list(videos_collection.find({}, {'_id': 0}))
    return render_template_string(HTML_TEMPLATE, videos=videos)

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
            "payer": {
                "email": "cliente@email.com"
            }
        }
        resp = requests.post("https://api.mercadopago.com/v1/payments", headers=headers, json=payload)
        pagamento = resp.json()
        
        if resp.status_code == 201:
            pix_copia_cola_real = pagamento['point_of_interaction']['transaction_data']['qr_code']
            # Cria um código aleatório/fake para exibir visualmente na tela do usuário
            pix_fake = f"00020126580014br.gov.bcb.pix0136{str(uuid.uuid4())}5204000053039865802BR5925CONTEUDO VIP DIGITAL6009SAO PAULO62070503***6304"
            return jsonify({'sucesso': True, 'pix_real': pix_copia_cola_real, 'pix_fake': pix_fake})
        else:
            return jsonify({'sucesso': False, 'erro': 'Falha na API do Mercado Pago'}), 500
    except Exception as e:
        return jsonify({'sucesso': False, 'erro': str(e)}), 500

# Rota Health Check essencial para o UptimeRobot pinar e manter o bot/site acordado 24h
@app.route('/health')
def health():
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 10000)))
