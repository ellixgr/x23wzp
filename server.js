const express = require('express');
const admin = require('firebase-admin');
const cors = require('cors');
const crypto = require('crypto');

const app = express();

// CONFIGURAÇÃO DO CORS - PERFEITA PARA GITHUB PAGES + RENDER
app.use(cors({
    origin: '*',
    methods: ['GET', 'POST'],
    allowedHeaders: ['Content-Type']
}));

app.use(express.json());

// CONFIGURAÇÃO DO FIREBASE (ADMIN SDK)
if (!admin.apps.length) {
    try {
        const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT);
        admin.initializeApp({
            credential: admin.credential.cert(serviceAccount),
            databaseURL: "https://cliques-4a2c1-default-rtdb.firebaseio.com"
        });
        console.log("✅ Servidor Autenticado como Admin");
    } catch (e) {
        console.log("❌ Erro Fatal no JSON da Service Account:", e.message);
    }
}

const db = admin.database();
const SENHA_MESTRE = "cavalo777_";

// --- ROTA DE MOEDAS (BLINDADA) ---
app.post('/ganhar-moeda', async (req, res) => {
    const { usuarioID } = req.body;

    if (!usuarioID) return res.json({ success: false, message: "ID ausente" });

    try {
        const moedasRef = db.ref(`usuarios/${usuarioID}/moedas`);
        
        const resultado = await moedasRef.transaction((valorAtual) => {
            let total = valorAtual || 0;
            if (total >= 20) return; // Trava interna: não permite passar de 20
            return total + 1;
        });

        if (!resultado.committed) {
            // Retornamos 200 (Sucesso técnico) mas success: false (regra de negócio)
            // Isso evita que o botão 'Validando' trave por erro de rede
            return res.json({ 
                success: false, 
                message: "Limite diário atingido! Volte amanhã." 
            });
        }

        return res.json({ 
            success: true, 
            novasMoedas: resultado.snapshot.val() 
        });

    } catch (error) {
        console.error("Erro Moeda:", error.message);
        return res.json({ success: false, message: "Erro temporário, tente de novo." });
    }
});

// --- ROTA DE CLIQUES (RÁPIDA) ---
app.post('/contar-clique', async (req, res) => {
    const { key } = req.body;
    if (!key) return res.status(400).send("Faltando ID");

    try {
        await db.ref(`grupos/${key}/cliques`).transaction(c => (c || 0) + 1);
        res.json({ success: true });
    } catch (e) { res.status(500).send("Erro"); }
});

// --- SISTEMA VIP E GRUPOS ---
app.post('/login-abareta', (req, res) => {
    const { senha } = req.body;
    res.json({ autorizado: (senha === SENHA_MESTRE) });
});

app.post('/gerar-vip', async (req, res) => {
    const { senha, duracaoHoras } = req.body;
    if (senha !== SENHA_MESTRE) return res.status(403).json({ error: "🔒" });
    
    const codigo = crypto.randomBytes(4).toString('hex').toUpperCase();
    try {
        await db.ref(`codigos_vips/${codigo}`).set({
            status: "disponivel",
            validadeHoras: parseInt(duracaoHoras) || 24,
            criadoEm: new Date().toISOString()
        });
        res.json({ codigo });
    } catch (e) { res.status(500).json({ error: e.message }); }
});

app.post('/salvar-grupo', async (req, res) => {
    const { nome, link, categoria, descricao, foto, dono, codigoVip } = req.body;
    try {
        let e_vip = false;
        let validade = null;
        
        if (codigoVip) {
            const vipSnap = await db.ref(`codigos_vips/${codigoVip}`).once('value');
            if (vipSnap.exists() && vipSnap.val().status === "disponivel") {
                e_vip = true;
                validade = Date.now() + (vipSnap.val().validadeHoras * 3600000);
                await db.ref(`codigos_vips/${codigoVip}`).update({ status: "usado" });
            }
        }

        await db.ref('solicitacoes').push().set({
            nome, link, categoria, descricao, foto, dono, codigoVip,
            vip: e_vip, vipAte: validade, status: "pendente", criadoEm: Date.now()
        });
        res.json({ success: true, message: "Enviado!" });
    } catch (e) { res.status(500).json({ error: e.message }); }
});

// --- FAXINA AUTOMÁTICA (RODA EM SEGUNDO PLANO) ---
const limparVips = async () => {
    const agora = Date.now();
    try {
        const snap = await db.ref('grupos').orderByChild('vip').equalTo(true).once('value');
        snap.forEach((child) => {
            const g = child.val();
            if (g.vipAte && agora > g.vipAte) {
                db.ref(`grupos/${child.key}`).update({ vip: false, vipAte: null });
            }
        });
    } catch (e) { /* Silencioso */ }
};
setInterval(limparVips, 30 * 60 * 1000); // A cada 30 min

// --- INICIALIZAÇÃO ---
const PORT = process.env.PORT || 10000;
app.listen(PORT, '0.0.0.0', () => { 
    console.log(`🚀 Servidor voando na porta ${PORT}`); 
});
