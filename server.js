const express = require('express');
const admin = require('firebase-admin');
const cors = require('cors');
const crypto = require('crypto');

const app = express();
app.use(cors());
app.use(express.json());

// CONFIGURAÇÃO REVISADA E PROTEGIDA
if (!admin.apps.length) {
    try {
        // Tenta ler a variável de ambiente do Render
        const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT);
        
        admin.initializeApp({
            credential: admin.credential.cert(serviceAccount),
            // URL EXATA do seu banco (sem barra no final para evitar erro)
            databaseURL: "https://gruposwhatsapp-ed18b-default-rtdb.firebaseio.com"
        });
        console.log("✅ FIREBASE CONECTADO COM SUCESSO!");
    } catch (e) {
        console.log("❌ ERRO AO INICIALIZAR FIREBASE:", e.message);
    }
}

const db = admin.database();
const SENHA_MESTRE = "cavalo777_";

// ROTA PARA GERAR O CÓDIGO VIP
app.post('/gerar-vip', async (req, res) => {
    const { senha, duracaoHoras } = req.body;

    // Verifica a senha administrativa
    if (senha !== SENHA_MESTRE) {
        return res.status(403).json({ error: "Senha Admin Incorreta" });
    }

    // Gera um código aleatório de 8 caracteres (Ex: A1B2C3D4)
    const codigo = crypto.randomBytes(4).toString('hex').toUpperCase();
    
    try {
        // Salva o código no Realtime Database
        await db.ref(`codigos_vips/${codigo}`).set({
            status: "disponivel",
            validadeHoras: parseInt(duracaoHoras) || 24,
            criadoEm: new Date().toISOString()
        });
        
        console.log(`✅ SUCESSO: Código ${codigo} salvo no banco.`);
        res.json({ codigo: codigo });
    } catch (error) {
        console.log("❌ ERRO AO GRAVAR NO BANCO:", error.message);
        res.status(500).json({ error: "Erro ao salvar no banco de dados", detalhes: error.message });
    }
});

// ROTA DE LOGIN DO ADMIN
app.post('/login-admin', (req, res) => {
    const { senha } = req.body;
    if (senha === SENHA_MESTRE) {
        return res.json({ autorizado: true });
    }
    res.status(401).json({ autorizado: false });
});

// PORTA DO SERVIDOR (RENDER)
const PORT = process.env.PORT || 10000;
app.listen(PORT, () => {
    console.log(`🚀 Servidor rodando e pronto na porta ${PORT}`);
});
