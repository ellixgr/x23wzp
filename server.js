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

/**
 * FUNÇÃO DE FAXINA AUTOMÁTICA
 * Verifica grupos com VIP vencido e os transforma em grupos normais.
 */
async function limparVipsVencidos() {
    console.log("🔍 Faxina pesada iniciada...");
    const agora = Date.now();
    try {
        const gruposRef = db.ref('grupos');
        const snapshot = await gruposRef.once('value');

        if (snapshot.exists()) {
            snapshot.forEach((child) => {
                const grupo = child.val();
                
                // SÓ ENTRA SE FOR VIP **E** TIVER A DATA GRAVADA
                if (grupo.vip === true && grupo.vipAte) {
                    const dataVencimento = Number(grupo.vipAte);

                    // SÓ REMOVE SE A DATA REALMENTE PASSOU
                    if (agora > dataVencimento) {
                        db.ref(`grupos/${child.key}`).update({
                            vip: false,
                            vipAte: null
                        });
                        console.log(`🚫 VIP expirado: ${grupo.nome}`);
                    }
                } 
                // Se for VIP mas não tem data, a gente ignora pra não remover por erro
                else if (grupo.vip === true && !grupo.vipAte) {
                    console.log(`⚠️ Grupo ${grupo.nome} é VIP mas está sem data. Ignorado para segurança.`);
                }
            });
        }
    } catch (error) {
        console.error("❌ Erro na faxina:", error.message);
    }
}


// Executa a limpeza a cada 15 minutos (900.000 milissegundos)
setInterval(limparVipsVencidos, 15 * 60 * 1000);

// ROTA PARA VALIDAR O CÓDIGO E RETORNAR O TEMPO DE VIP
app.post('/validar-vip', async (req, res) => {
    const { codigo } = req.body;
    try {
        const snapshot = await db.ref(`codigos_vips/${codigo}`).once('value');
        if (snapshot.exists() && snapshot.val().status === "disponivel") {
            const dadosVip = snapshot.val();
            // Marca como usado
            await db.ref(`codigos_vips/${codigo}`).update({ status: "usado" });
            
            // Retorna 'valido' e a quantidade de horas que o VIP deve durar
            res.json({ 
                valido: true, 
                duracaoHoras: dadosVip.validadeHoras || 24 
            });
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
app.listen(PORT, () => {
    console.log(`🚀 Servidor rodando na porta ${PORT}`);
    // Executa uma limpeza assim que o servidor ligar
    limparVipsVencidos();
});
