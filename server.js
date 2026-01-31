// Arquivo: server.js
const express = require('express');
const admin = require('firebase-admin');
const cors = require('cors');
const crypto = require('crypto');

const app = express();
app.use(cors());
app.use(express.json());

// CONFIGURAÇÃO DO FIREBASE (Use as chaves do seu Admin SDK)
const serviceAccount = require("./sua-chave-firebase.json"); 
admin.initializeApp({
  credential: admin.credential.cert(serviceAccount),
  databaseURL: "https://cliques-4a2c1-default-rtdb.firebaseio.com"
});

const db = admin.database();

// ROTA PARA GERAR CÓDIGO (Você chama isso do seu Painel Admin)
app.post('/gerar-vip', async (req, res) => {
    const { senhaAdmin } = req.body;
    if (senhaAdmin !== "cavalo777_") return res.status(403).send("Negado");

    // Gera um código aleatório de 8 dígitos (ex: 8A2F-9D1L)
    const codigo = crypto.randomBytes(4).toString('hex').toUpperCase();
    
    try {
        await db.ref('codigos_vips/' + codigo).set({
            status: "disponivel",
            dataCriacao: new Date().toISOString()
        });
        res.json({ codigo });
    } catch (e) {
        res.status(500).send("Erro no banco");
    }
});

// ROTA PARA VALIDAR CÓDIGO (O site chama isso no envio do grupo)
app.post('/validar-vip', async (req, res) => {
    const { codigo } = req.body;
    const ref = db.ref('codigos_vips/' + codigo);
    const snapshot = await ref.once('value');

    if (snapshot.exists() && snapshot.val().status === "disponivel") {
        await ref.update({ status: "usado", dataUso: new Date().toISOString() });
        res.json({ valido: true });
    } else {
        res.json({ valido: false, msg: "Código inválido ou já usado" });
    }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Servidor rodando na porta ${PORT}`));
