<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ganhar VIP - Missões</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        :root { --primary: #b78cff; --success: #2ecc71; --error: #ff4757; --warning: #ffa502; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #ebebeb; display: flex; flex-direction: column; align-items: center; padding: 20px; overflow-x: hidden; min-height: 100vh; margin: 0; }
        .card { background: #fff; padding: 25px; border-radius: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); width: 100%; max-width: 350px; text-align: center; position: relative; z-index: 1; }
        h2 { color: var(--primary); margin-bottom: 5px; }
        .moedas-display { font-size: 50px; font-weight: bold; color: #ff9800; margin: 10px 0; text-shadow: 1px 1px 2px rgba(0,0,0,0.1); }
        .btn-missao { display: block; background: #ff4500; color: white; text-decoration: none; padding: 16px; border-radius: 12px; font-weight: bold; margin-top: 20px; cursor: pointer; border: none; width: 100%; transition: 0.2s; font-size: 14px; }
        .btn-resgatar { background: var(--primary); margin-top: 12px; }
        .disabled { background: #ccc !important; cursor: not-allowed; pointer-events: none; }
        #toast-container { position: fixed; top: -100px; left: 50%; transform: translateX(-50%); background: #333; color: white; padding: 15px 25px; border-radius: 50px; display: flex; align-items: center; gap: 10px; font-weight: 500; box-shadow: 0 5px 15px rgba(0,0,0,0.3); transition: top 0.5s; z-index: 9999; }
        #toast-container.show { top: 25px; }
        #timer { font-size: 14px; color: #666; margin-top: 15px; background: #f8f8f8; padding: 8px; border-radius: 8px; display: inline-block; width: 100%; box-sizing: border-box; }
        .status { font-size: 13px; margin-top: 8px; color: var(--success); font-weight: bold; }
        .modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); display: none; justify-content: center; align-items: center; z-index: 10000; backdrop-filter: blur(4px); }
        .modal-vip { background: white; padding: 30px; border-radius: 25px; text-align: center; width: 85%; max-width: 320px; animation: popUp 0.3s ease-out; }
        @keyframes popUp { from { transform: scale(0.8); opacity: 0; } to { transform: scale(1); opacity: 1; } }
        .codigo-gerado { background: #f0f0f0; border: 2px dashed var(--primary); padding: 15px; font-size: 22px; font-weight: bold; color: #333; border-radius: 12px; margin: 15px 0; letter-spacing: 2px; }
        .btn-fechar { background: var(--primary); color: white; border: none; padding: 12px 25px; border-radius: 10px; font-weight: bold; cursor: pointer; width: 100%; }
        .footer-id { margin-top: auto; padding: 25px 20px; text-align: center; width: 100%; color: #888; font-size: 12px; }
        .id-container { display: inline-flex; align-items: center; gap: 8px; background: #e0e0e0; padding: 5px 12px; border-radius: 8px; margin-top: 5px; cursor: pointer; transition: 0.2s; }
        .id-badge { font-family: monospace; font-weight: bold; color: #444; }
    </style>
</head>
<body>

    <div id="toast-container"><span id="toast-icon"></span><span id="toast-message"></span></div>

    <div class="modal-overlay" id="modalVip">
        <div class="modal-vip">
            <div style="font-size: 40px;">⭐</div>
            <h3 style="margin: 10px 0; color: var(--primary);">VIP GERADO!</h3>
            <p style="font-size: 14px; color: #666; margin: 0;">Copie o código abaixo:</p>
            <div class="codigo-gerado" id="displayCodigo">...</div>
            <button class="btn-fechar" onclick="fecharModalVip()">COPIAR E FECHAR</button>
        </div>
    </div>

    <div class="card">
        <h2>Minhas Moedas</h2>
        <div class="moedas-display" id="moedasTxt">0</div>
        <p style="color: #666; font-size: 14px;">Junte 20 moedas para <b>24h de VIP</b></p>
        <div id="statusDia" class="status">Sincronizando...</div>
        <button id="btnVideo" class="btn-missao disabled">🎬 ASSISTIR VÍDEO AGORA</button>
        <div id="timer" style="display:none;">⏳ Validando em <span id="segundos">15</span>s...</div>
        <button id="btnResgatar" class="btn-missao btn-resgatar">⭐ GERAR VIP 24H (20 Moedas)</button>
    </div>

    <div class="footer-id">
        SEU ID DE USUÁRIO:<br>
        <div class="id-container" onclick="copiarMeuId()">
            <span id="exibirId" class="id-badge">...</span>
            <i class="fa-regular fa-copy"></i>
        </div>
    </div>

    <script type="module">
        import { initializeApp } from "https://www.gstatic.com/firebasejs/9.23.0/firebase-app.js";
        import { getDatabase, ref, set, onValue } from "https://www.gstatic.com/firebasejs/9.23.0/firebase-database.js";

        const firebaseConfig = {
            apiKey: "AIzaSyDsrYjO2yVTemKqwmJRzNjh5sfaMalPqhE",
            databaseURL: "https://cliques-4a2c1-default-rtdb.firebaseio.com",
            projectId: "cliques-4a2c1",
        };

        const app = initializeApp(firebaseConfig);
        const db = getDatabase(app);

        const CUSTO_VIP = 20;
        const LIMITE_DIA = 100; // Ajustado conforme seu print

        let meuId = localStorage.getItem('usuario_uid');
        if (!meuId) {
            meuId = "user_" + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('usuario_uid', meuId);
        }
        document.getElementById('exibirId').innerText = meuId;

        let moedas = parseInt(localStorage.getItem('moedasVip')) || 0;
        let limiteDiario = parseInt(localStorage.getItem('limiteDiario')) || 0;
        const hoje = new Date().toLocaleDateString();

        if (localStorage.getItem('ultimaDataMissao') !== hoje) {
            limiteDiario = 0;
            localStorage.setItem('limiteDiario', 0);
            localStorage.setItem('ultimaDataMissao', hoje);
        }

        function notify(msg, type = 'success') {
            const toast = document.getElementById('toast-container');
            document.getElementById('toast-message').innerText = msg;
            document.getElementById('toast-icon').innerText = type === 'success' ? '✅' : '❌';
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 3000);
        }

        window.copiarMeuId = () => {
            navigator.clipboard.writeText(meuId);
            notify("ID copiado!", "success");
        }

        window.fecharModalVip = () => {
            const cod = document.getElementById('displayCodigo').innerText;
            navigator.clipboard.writeText(cod);
            document.getElementById('modalVip').style.display = 'none';
            notify("Código copiado!", "success");
        }

        let meusVideos = [];
        onValue(ref(db, 'videos_shopee'), (snap) => {
            meusVideos = [];
            snap.forEach(c => { if(c.val().link) meusVideos.push(c.val().link); });
            atualizarTela();
        });

        function atualizarTela() {
            document.getElementById('moedasTxt').innerText = moedas;
            const btnVideo = document.getElementById('btnVideo');
            if (limiteDiario >= LIMITE_DIA) {
                btnVideo.classList.add('disabled');
                btnVideo.innerText = "LIMITE DIÁRIO ATINGIDO";
                document.getElementById('statusDia').innerText = "Volte amanhã!";
            } else if (meusVideos.length > 0) {
                btnVideo.classList.remove('disabled');
                btnVideo.innerText = "🎬 ASSISTIR VÍDEO AGORA";
                document.getElementById('statusDia').innerText = `Missões: ${limiteDiario}/${LIMITE_DIA} hoje`;
            }
        }

        document.getElementById('btnVideo').onclick = () => {
            if (limiteDiario >= LIMITE_DIA || meusVideos.length === 0) return;
            window.open(meusVideos[Math.floor(Math.random() * meusVideos.length)], '_blank');
            let tempo = 15;
            document.getElementById('btnVideo').classList.add('disabled');
            document.getElementById('timer').style.display = 'block';
            let count = setInterval(() => {
                tempo--;
                document.getElementById('segundos').innerText = tempo;
                if (tempo <= 0) {
                    clearInterval(count);
                    moedas++;
                    limiteDiario++;
                    localStorage.setItem('moedasVip', moedas);
                    localStorage.setItem('limiteDiario', limiteDiario);
                    document.getElementById('timer').style.display = 'none';
                    notify("Moeda ganha!", "success");
                    atualizarTela();
                }
            }, 1000);
        };

        document.getElementById('btnResgatar').onclick = async () => {
            if (moedas < CUSTO_VIP) return notify("Precisa de 20 moedas!", "error");
            
            // FREE- garante que o servidor entenda a origem
            const novoCodigo = "FREE-" + Math.random().toString(36).substr(2, 6).toUpperCase();
            
            try {
                // FORMATO EXATO QUE O SEU SERVIDOR (RENDER) BUSCA
                await set(ref(db, 'codigos_vips/' + novoCodigo), {
                    status: "disponivel",      // ESSENCIAL para o seu servidor validar
                    validadeHoras: 24,         // ESSENCIAL para o seu servidor
                    criadoEm: new Date().toISOString()
                });

                moedas -= CUSTO_VIP;
                localStorage.setItem('moedasVip', moedas);
                atualizarTela();
                
                document.getElementById('displayCodigo').innerText = novoCodigo;
                document.getElementById('modalVip').style.display = 'flex';

            } catch (e) { notify("Erro no banco!", "error"); }
        };

        atualizarTela();
    </script>
</body>
</html>
