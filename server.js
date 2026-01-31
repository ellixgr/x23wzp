// Arquivo: server.js completo e corrigido para Render
const express = require('express');
const admin = require('firebase-admin');
const cors = require('cors');
const crypto = require('crypto');

const app = express();
app.use(cors());
app.use(express.json());

// CONFIGURAÇÃO DO FIREBASE (Usando a variável de ambiente do Render)
try {
    const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT);
    
    admin.initializeApp({
      credential: admin.credential.cert(serviceAccount),
      // Usei o URL do seu projeto Firebase conforme seus prints anteriores
      databaseURL: "https://gruposwhatsapp-ed18b-default-rtdb.firebaseio.com"
    });
    
    console.log("Firebase conectado com sucesso!");
} catch (error) {
    console.error("Erro ao inicializar Firebase. Verifique a variável FIREBASE_SERVICE_ACCOUNT.");
    console.error(error.message);
}

const db = admin.database();

// ROTA PARA GERAR CÓDIGO (Senha: cavalo777_)
app.post('/gerar-vip', async (req, res) => {
    const { senhaAdmin } = req.body;
    if (senhaAdmin !== "cavalo777_") return res.status(403).send("Negado");

    // Gera um código aleatório de 8 dígitos
    const codigo = crypto.randomBytes(4).toString('hex').toUpperCase();
    
    try {
        await db.ref('codigos_vips/' + codigo).set({
            status: "disponivel",
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
    
    if (!codigo) {
        return res.json({ valido: false, msg: "Código não fornecido" });
    }

    try {
        const ref = db.ref('codigos_vips/' + codigo);
        const snapshot = await ref.once('value');

        if (snapshot.exists() && snapshot.val().status === "disponivel") {
            // Marca como usado para ninguém usar o mesmo código duas vezes
            await ref.update({ status: "usado", dataUso: new Date().toISOString() });
            res.json({ valido: true });
        } else {
            res.json({ valido: false, msg: "Código inválido ou já usado" });
        }
    } catch (e) {
        res.status(500).json({ error: "Erro na validação", detalhes: e.message });
    }
});

// Porta padrão que o Render exige (10000) ou a do processo
const PORT = process.env.PORT || 10000;
app.listen(PORT, () => {
    console.log(`Servidor rodando e pronto na porta ${PORT}`);
});
