const express = require('express');
const admin = require('firebase-admin');
const cors = require('cors');
const crypto = require('crypto');

const app = express();
app.use(cors());
app.use(express.json());

// CONFIGURAÇÃO DO FIREBASE
try {
    const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT);
    admin.initializeApp({
      credential: admin.credential.cert(serviceAccount),
      databaseURL: "https://gruposwhatsapp-ed18b-default-rtdb.firebaseio.com"
    });
    console.log("Firebase conectado!");
} catch (error) {
    console.error("Erro Firebase:", error.message);
}

const db = admin.database();

// --- 1. CONFIGURAÇÃO DA SENHA (DICA: USE VARIÁVEL DE AMBIENTE DEPOIS) ---
const SENHA_MESTRE = "cavalo777_";

// --- 2. NOVA ROTA DE LOGIN DO ADMIN ---
app.post('/login-admin', (req, res) => {
    const { senha } = req.body;
    if (senha === SENHA_MESTRE) {
        res.json({ autorizado: true });
    } else {
        res.status(401).json({ autorizado: false });
    }
});

// --- 3. ROTA DE GERAR VIP (ATUALIZADA COM TEMPO) ---
app.post('/gerar-vip', async (req, res) => {
    const { senha, duracaoHoras } = req.body; // Agora recebe a duração
    
    if (senha !== SENHA_MESTRE) return res.status(403).send("Negado");

    const codigo = crypto.randomBytes(4).toString('hex').toUpperCase();
    
    try {
        await db.ref('codigos_vips/' + codigo).set({
            status: "disponivel",
            horasValidade: duracaoHoras || 24, // Salva se é 24h, 48h, etc.
            dataCriacao: new Date().toISOString()
        });
        res.json({ codigo });
    } catch (e) {
        res.status(500).json({ error: "Erro no banco", detalhes: e.message });
    }
});

// ROTA PARA VALIDAR CÓDIGO
app.post('/validar-vip', async (req, res) => {
    const { codigo } = req.body;
    try {
        const ref = db.ref('codigos_vips/' + codigo);
        const snapshot = await ref.once('value');

        if (snapshot.exists() && snapshot.val().status === "disponivel") {
            await ref.update({ status: "usado", dataUso: new Date().toISOString() });
            res.json({ valido: true });
        } else {
            res.json({ valido: false });
        }
    } catch (e) {
        res.status(500).json({ error: "Erro" });
    }
});

const PORT = process.env.PORT || 10000;
app.listen(PORT, () => {
    console.log(`Servidor na porta ${PORT}`);
});
