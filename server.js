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
        console.log("✅ Banco Conectado com Sucesso");
    } catch (e) {
        console.log("❌ Erro ao configurar Firebase:", e.message);
    }
}

const db = admin.database();
const SENHA_MESTRE = "cavalo777_";

// --- ROTAS DE AUTENTICAÇÃO E VIP ---

app.post('/login-abareta', (req, res) => {
    const { senha } = req.body;
    if (senha === SENHA_MESTRE) return res.json({ autorizado: true });
    res.status(401).json({ autorizado: false });
});

app.post('/validar-vip', async (req, res) => {
    const { codigo } = req.body;
    try {
        const snapshot = await db.ref(`codigos_vips/${codigo}`).once('value');
        if (snapshot.exists() && snapshot.val().status === "disponivel") {
            const dadosVip = snapshot.val();
            // Marcamos como usado apenas no momento do uso real
            res.json({ valido: true, duracaoHoras: dadosVip.validadeHoras || 24 });
        } else {
            res.json({ valido: false });
        }
    } catch (error) { res.status(500).json({ error: "Erro no servidor" }); }
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
    } catch (error) { res.status(500).json({ error: error.message }); }
});

// --- ROTAS DE GERENCIAMENTO DE GRUPOS ---

// NOVA ROTA: Impulsionar Grupo (A que estava faltando!)
app.post('/impulsionar-grupo', async (req, res) => {
    const { key, donoLocal } = req.body;
    try {
        const grupoRef = db.ref(`grupos/${key}`);
        const snapshot = await grupoRef.once('value');
        
        if (!snapshot.exists()) return res.status(404).json({ success: false, message: "Grupo não encontrado" });

        const grupoData = snapshot.val();
        if (grupoData.dono !== donoLocal) return res.status(403).json({ success: false, message: "Acesso negado" });

        const agora = Date.now();
        const espera = 60 * 60 * 1000; // 1 hora de intervalo
        const tempoPassado = agora - (grupoData.ultimoImpulso || 0);

        if (tempoPassado < espera) {
            return res.status(429).json({ success: false, message: "Aguarde o tempo de recarga" });
        }

        await grupoRef.update({ ultimoImpulso: agora });
        res.json({ success: true });
    } catch (e) {
        res.status(500).json({ success: false, error: e.message });
    }
});

// ROTA EDITAR: Com validação de VIP integrada
app.post('/editar-grupo', async (req, res) => {
    const { key, donoLocal, nome, link, descricao, categoria, foto, codigoVip } = req.body;
    try {
        const grupoRef = db.ref(`grupos/${key}`);
        const snapshot = await grupoRef.once('value');
        if (!snapshot.exists()) return res.status(404).json({ success: false, message: "Grupo não existe" });

        const grupoData = snapshot.val();
        if (grupoData.dono !== donoLocal) return res.status(403).json({ success: false, message: "Acesso negado" });

        let dadosUpdate = { nome, link, descricao, categoria, foto };

        // Lógica de Ativação de VIP via código no Edit
        if (codigoVip && codigoVip !== grupoData.vipCodigo) {
            const vipSnap = await db.ref(`codigos_vips/${codigoVip}`).once('value');
            if (vipSnap.exists() && vipSnap.val().status === "disponivel") {
                const infoVip = vipSnap.val();
                await db.ref(`codigos_vips/${codigoVip}`).update({ status: "usado" });
                
                dadosUpdate.vip = true;
                dadosUpdate.vipCodigo = codigoVip;
                dadosUpdate.vipAte = Date.now() + (infoVip.validadeHoras * 3600000);
            }
        }

        await grupoRef.update(dadosUpdate);
        res.json({ success: true });
    } catch (e) { 
        res.status(500).json({ success: false, error: e.message }); 
    }
});

// ROTA EXCLUIR
app.post('/excluir-grupo', async (req, res) => {
    const { key, donoLocal } = req.body;
    try {
        const grupoRef = db.ref(`grupos/${key}`);
        const snapshot = await grupoRef.once('value');
        if (snapshot.exists() && snapshot.val().dono === donoLocal) {
            await grupoRef.remove();
            return res.json({ success: true });
        }
        res.status(403).json({ success: false, message: "Sem permissão" });
    } catch (e) { 
        res.status(500).json({ success: false }); 
    }
});

// --- SISTEMAS AUTOMÁTICOS ---

async function limparVipsVencidos() {
    const agora = Date.now();
    try {
        const gruposRef = db.ref('grupos');
        const snapshot = await gruposRef.once('value');
        if (snapshot.exists()) {
            snapshot.forEach((child) => {
                const grupo = child.val();
                // Se for VIP e o tempo expirou, remove o status VIP
                if (grupo.vip === true && grupo.vipAte && agora > grupo.vipAte) {
                    db.ref(`grupos/${child.key}`).update({ 
                        vip: false, 
                        vipAte: null,
                        vipCodigo: null 
                    });
                    console.log(`⭐ VIP expirado para o grupo: ${grupo.nome}`);
                }
            });
        }
    } catch (e) {
        console.log("Erro na faxina VIP:", e.message);
    }
}

// Executa a cada 15 minutos
setInterval(limparVipsVencidos, 15 * 60 * 1000);

// INICIALIZAÇÃO DO SERVIDOR
const PORT = process.env.PORT || 10000;
app.listen(PORT, '0.0.0.0', () => { 
    console.log(`🚀 Servidor online na porta ${PORT}`); 
});
