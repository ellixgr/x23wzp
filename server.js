const express = require('express');
const admin = require('firebase-admin');
const cors = require('cors');
const crypto = require('crypto');

const app = express();
app.use(cors());
app.use(express.json());

// CONFIGURAÇÃO DO FIREBASE
if (!admin.apps.length) {
    try {
        const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT);
        admin.initializeApp({
            credential: admin.credential.cert(serviceAccount),
            databaseURL: "https://cliques-4a2c1-default-rtdb.firebaseio.com"
        });
        console.log("✅ Banco Conectado");
    } catch (e) {
        console.log("❌ Erro Firebase:", e.message);
    }
}

const db = admin.database();
const SENHA_MESTRE = "cavalo777_"; // <--- SUA SENHA AQUI

// ROTA DE LOGIN (ATUALIZADA PARA O NOVO PAINEL ABARETA)
app.post('/login-abareta', (req, res) => {
    const { senha } = req.body;
    if (senha === SENHA_MESTRE) {
        return res.json({ autorizado: true });
    } else {
        res.status(401).json({ autorizado: false });
    }
});

// FAXINA AUTOMÁTICA
async function limparVipsVencidos() {
    console.log("🔍 Verificando validade dos VIPs...");
    const agora = Date.now();
    try {
        const gruposRef = db.ref('grupos');
        const snapshot = await gruposRef.once('value');
        if (snapshot.exists()) {
            snapshot.forEach((child) => {
                const grupo = child.val();
                if (grupo.vip === true) {
                    const dataVencimento = Number(grupo.vipAte);
                    if (dataVencimento && agora > dataVencimento) {
                        db.ref(`grupos/${child.key}`).update({ vip: false, vipAte: null });
                        console.log(`🚫 VIP removido: ${grupo.nome}`);
                    }
                }
            });
        }
    } catch (error) {
        console.error("❌ Erro na faxina:", error.message);
    }
}
setInterval(limparVipsVencidos, 15 * 60 * 1000);

// VALIDAR CÓDIGO VIP
app.post('/validar-vip', async (req, res) => {
    const { codigo } = req.body;
    try {
        const snapshot = await db.ref(`codigos_vips/${codigo}`).once('value');
        if (snapshot.exists() && snapshot.val().status === "disponivel") {
            const dadosVip = snapshot.val();
            await db.ref(`codigos_vips/${codigo}`).update({ status: "usado" });
            res.json({ valido: true, duracaoHoras: dadosVip.validadeHoras || 24 });
        } else {
            res.json({ valido: false });
        }
    } catch (error) {
        res.status(500).json({ error: "Erro no servidor" });
    }
});

// GERAR NOVO CÓDIGO VIP
app.post('/gerar-vip', async (req, res) => {
    const { senha, duracaoHoras } = req.body;
    if (senha !== SENHA_MESTRE) return res.status(403).json({ error: "Senha incorreta" });
    const codigo = crypto.randomBytes(4).toString('hex').toUpperCase();
    try {
        await db.ref(`codigos_vips/${codigo}`).set({
            status: "disponivel",
            validadeHoras: parseInt(duracaoHoras) || 24,
            criadoEm: new Date().toISOString()
        });
        res.json({ codigo: codigo });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// GERAR VIP GRÁTIS COM MOEDAS
app.post('/gerar-vip-gratis', async (req, res) => {
    const { moedas } = req.body;
    if (!moedas || moedas < 20) return res.status(400).json({ sucesso: false, mensagem: "Moedas insuficientes" });
    try {
        const codigoGerado = "FREE-" + crypto.randomBytes(4).toString('hex').toUpperCase();
        await db.ref(`codigos_vips/${codigoGerado}`).set({
            status: "disponivel",
            validadeHoras: 24,
            criadoEm: new Date().toISOString(),
            origem: "moedas_video"
        });
        res.json({ sucesso: true, codigo: codigoGerado });
    } catch (error) {
        res.status(500).json({ sucesso: false, error: "Erro no servidor" });
    }
});

const PORT = process.env.PORT || 10000;
app.listen(PORT, '0.0.0.0', () => {
    console.log(`Servidor rodando na porta ${PORT}`);
});
