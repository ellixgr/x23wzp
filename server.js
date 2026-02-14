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
        if (snapshot.exists()) {
            const dados = snapshot.val();
            if (dados.usado === false) {
                return res.json({ valido: true, duracaoHoras: dados.horas || 24 });
            }
        }
        res.json({ valido: false });
    } catch (error) { res.status(500).json({ error: "Erro no servidor" }); }
});

app.post('/gerar-vip', async (req, res) => {
    const { senha, duracaoHoras } = req.body;
    if (senha !== SENHA_MESTRE) return res.status(403).json({ error: "Senha incorreta" });
    const codigo = crypto.randomBytes(4).toString('hex').toUpperCase();
    try {
        await db.ref(`codigos_vips/${codigo}`).set({
            usado: false,
            horas: parseInt(duracaoHoras) || 24,
            criadoEm: new Date().toISOString()
        });
        res.json({ codigo: codigo });
    } catch (error) { res.status(500).json({ error: error.message }); }
});

// --- SOLICITAÇÕES CORRIGIDAS ---

app.post('/salvar-grupo', async (req, res) => {
    const { nome, link, categoria, descricao, foto, dono, codigoVip } = req.body;
    try {
        let e_vip = false;
        let validade = null;
        
        if (codigoVip && codigoVip.trim() !== "") {
            const vipSnap = await db.ref(`codigos_vips/${codigoVip}`).once('value');
            if (vipSnap.exists()) {
                const vData = vipSnap.val();
                if (vData.usado === false) {
                    // QUEIMA O CÓDIGO NA HORA DO ENVIO
                    await db.ref(`codigos_vips/${codigoVip}`).update({ usado: true });
                    e_vip = true;
                    // Define validade + 2 minutos de folga para não dar erro de fuso horário
                    validade = Date.now() + (parseInt(vData.horas) * 3600000) + 120000;
                } else {
                    return res.status(400).json({ success: false, message: "Código já utilizado!" });
                }
            } else {
                return res.status(400).json({ success: false, message: "Código inválido!" });
            }
        }

        const novaSolicitacaoRef = db.ref('solicitacoes').push();
        await novaSolicitacaoRef.set({
            nome, link, categoria, descricao, foto, dono, 
            codigoVip: e_vip ? codigoVip : null,
            vip: e_vip,
            vipAte: validade,
            status: "pendente", 
            motivo: "",
            criadoEm: Date.now()
        });
        res.json({ success: true, message: "Enviado para análise!" });
    } catch (e) {
        res.status(500).json({ success: false, error: e.message });
    }
});

// --- GERENCIAMENTO DE GRUPOS ---

app.post('/impulsionar-grupo', async (req, res) => {
    const { key, donoLocal } = req.body;
    try {
        const grupoRef = db.ref(`grupos/${key}`);
        const snapshot = await grupoRef.once('value');
        if (!snapshot.exists()) return res.status(404).json({ success: false, message: "Grupo não encontrado" });

        const grupoData = snapshot.val();
        if (grupoData.dono !== donoLocal) return res.status(403).json({ success: false, message: "Acesso negado" });

        const agora = Date.now();
        const espera = 60 * 60 * 1000;
        const tempoPassado = agora - (grupoData.ultimoImpulso || 0);

        if (tempoPassado < espera) return res.status(429).json({ success: false, message: "Aguarde o tempo de recarga" });

        await grupoRef.update({ ultimoImpulso: agora });
        res.json({ success: true });
    } catch (e) {
        res.status(500).json({ success: false, error: e.message });
    }
});

app.post('/editar-grupo', async (req, res) => {
    const { key, donoLocal, nome, link, descricao, categoria, foto, codigoVip } = req.body;
    try {
        const grupoRef = db.ref(`grupos/${key}`);
        const snapshot = await grupoRef.once('value');
        if (!snapshot.exists()) return res.status(404).json({ success: false, message: "Grupo não existe" });

        const grupoData = snapshot.val();
        if (grupoData.dono !== donoLocal) return res.status(403).json({ success: false, message: "Acesso negado" });

        let dadosUpdate = { nome, link, descricao, categoria, foto };

        if (codigoVip && codigoVip !== grupoData.vipCodigo) {
            const vipSnap = await db.ref(`codigos_vips/${codigoVip}`).once('value');
            if (vipSnap.exists()) {
                const vData = vipSnap.val();
                if (vData.usado === false) {
                    // MARCA COMO USADO
                    await db.ref(`codigos_vips/${codigoVip}`).update({ usado: true });
                    dadosUpdate.vip = true;
                    dadosUpdate.vipCodigo = codigoVip;
                    // Validade + 2 minutos de folga
                    dadosUpdate.vipAte = Date.now() + (parseInt(vData.horas) * 3600000) + 120000;
                }
            }
        }

        await grupoRef.update(dadosUpdate);
        res.json({ success: true });
    } catch (e) { 
        res.status(500).json({ success: false, error: e.message }); 
    }
});

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
        const snapshot = await db.ref('grupos').once('value');
        if (snapshot.exists()) {
            snapshot.forEach((child) => {
                const grupo = child.val();
                // Só limpa se o tempo ATUAL for maior que a validade + uma margem de erro
                if (grupo.vip === true && grupo.vipAte && agora > (grupo.vipAte + 5000)) {
                    db.ref(`grupos/${child.key}`).update({ vip: false, vipAte: null, vipCodigo: null });
                }
            });
        }
    } catch (e) { console.log("Erro na limpeza VIP:", e.message); }
}

// Limpa a cada 15 minutos
setInterval(limparVipsVencidos, 15 * 60 * 1000);

const PORT = process.env.PORT || 10000;
app.listen(PORT, '0.0.0.0', () => { console.log(`🚀 Servidor online na porta ${PORT}`); });
