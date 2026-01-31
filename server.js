const express = require('express');
const admin = require('firebase-admin');
const cors = require('cors');
const crypto = require('crypto');

const app = express();
app.use(cors());
app.use(express.json());

// CONFIGURAÇÃO DIRETA E BRUTA
if (!admin.apps.length) {
    try {
        const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT);
        admin.initializeApp({
            credential: admin.credential.cert(serviceAccount),
            databaseURL: "https://gruposwhatsapp-ed18b-default-rtdb.firebaseio.com"
        });
        console.log("✅ FIREBASE CONECTADO!");
    } catch (e) {
        console.log("❌ ERRO NA CHAVE SERVICE ACCOUNT:", e.message);
    }
}

const db = admin.database();
const SENHA_MESTRE = "cavalo777_";

// ROTA GERAR VIP
app.post('/gerar-vip', async (req, res) => {
    const { senha, duracaoHoras } = req.body;

    if (senha !== SENHA_MESTRE) {
        return res.status(403).json({ error: "Senha Admin Incorreta" });
    }

    const codigo = crypto.randomBytes(4).toString('hex').toUpperCase();
    
    try {
        // Tentativa de salvar na raiz do banco para evitar erro de pasta
        await db.ref(`codigos_vips/${codigo}`).set({
            status: "disponivel",
            validade: parseInt(duracaoHoras) || 24,
            criadoEm: new Date().toISOString()
        });
        
        console.log(`✅ CÓDIGO ${codigo} GERADO COM SUCESSO!`);
        res.json({ codigo: codigo });
    } catch (error) {
        console.log("❌ ERRO AO SALVAR NO FIREBASE:", error.message);
        res.status(500).json({ error: "Erro no Firebase", detalhes: error.message });
    }
});

// LOGIN ADMIN
app.post('/login-admin', (req, res) => {
    const { senha } = req.body;
    if (senha === SENHA_MESTRE) return res.json({ autorizado: true });
    res.status(401).json({ autorizado: false });
});

const PORT = process.env.PORT || 10000;
app.listen(PORT, () => console.log(`🚀 Servidor na porta ${PORT}`));
