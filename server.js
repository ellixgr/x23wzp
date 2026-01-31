const express = require('express');
const admin = require('firebase-admin');
const cors = require('cors');
const crypto = require('crypto');

const app = express();
app.use(cors());
app.use(express.json());

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
const SENHA_MESTRE = "cavalo777_";

// ROTA QUE FALTAVA (O SEU SITE PRECISA DESTA)
app.post('/validar-vip', async (req, res) => {
    const { codigo } = req.body;
    try {
        const snapshot = await db.ref(`codigos_vips/${codigo}`).once('value');
        if (snapshot.exists() && snapshot.val().status === "disponivel") {
            await db.ref(`codigos_vips/${codigo}`).update({ status: "usado" });
            res.json({ valido: true });
        } else {
            res.json({ valido: false });
        }
    } catch (error) {
        res.status(500).json({ error: "Erro no servidor" });
    }
});

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

app.post('/login-admin', (req, res) => {
    if (req.body.senha === SENHA_MESTRE) return res.json({ autorizado: true });
    res.status(401).json({ autorizado: false });
});

const PORT = process.env.PORT || 10000;
app.listen(PORT, () => console.log(`Rodando na porta ${PORT}`));
