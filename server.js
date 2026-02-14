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

// CORRIGIDO: Agora lê 'usado' e 'horas' como no seu print
app.post('/validar-vip', async (req, res) => {
    const { codigo } = req.body;
    try {
        const snapshot = await db.ref(`codigos_vips/${codigo}`).once('value');
        if (snapshot.exists()) {
            const dados = snapshot.val();
            // Verifica se usado é false (conforme seu print 1000024257.png)
            if (dados.usado === false) {
                return res.json({ valido: true, duracaoHoras: dados.horas || 24 });
            }
        }
        res.json({ valido: false });
    } catch (error) { res.status(500).json({ error: "Erro no servidor" }); }
});

// CORRIGIDO: Gera seguindo o padrão do seu banco (usado: false, horas: X)
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

// --- SOLICITAÇÕES (MANTIDAS) ---

app.post('/salvar-grupo', async (req, res) => {
    const { nome, link, categoria, descricao, foto, dono, codigoVip } = req.body;
    try {
        let e_vip = false;
        let validade = null;
        
        if (codigoVip) {
            const vipSnap = await db.ref(`codigos_vips/${codigoVip}`).once('value');
            if (vipSnap.exists()) {
                const vData = vipSnap.val();
                if (vData.usado === false) {
                    e_vip = true;
                    validade = Date.now() + (parseInt(vData.horas) * 3600000);
                }
            }
        }

        const novaSolicitacaoRef = db.ref('solicitacoes').push();
        await novaSolicitacaoRef.set({
            nome, link, categoria, descricao, foto, dono, codigoVip,
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

        // CORREÇÃO VIP NA EDIÇÃO: Bate com o padrão 'usado' e 'horas'
        if (codigoVip && codigoVip !== grupoData.vipCodigo) {
            const vipSnap = await db.ref(`codigos_vips/${codigoVip}`).once('value');
            if (vipSnap.exists()) {
                const vData = vipSnap.val();
                if (vData.usado === false) {
                    await db.ref(`codigos_vips/${codigoVip}`).update({ usado: true });
                    dadosUpdate.vip = true;
                    dadosUpdate.vipCodigo = codigoVip;
                    dadosUpdate.vipAte = Date.now() + (parseInt(vData.horas) * 3600000);
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
                if (grupo.vip === true && grupo.vipAte && agora > grupo.vipAte) {
                    db.ref(`grupos/${child.key}`).update({ vip: false, vipAte: null, vipCodigo: null });
                }
            });
        }
    } catch (e) { console.log("Erro na limpeza VIP:", e.message); }
}

setInterval(limparVipsVencidos, 15 * 60 * 1000);

const PORT = process.env.PORT || 10000;
app.listen(PORT, '0.0.0.0', () => { console.log(`🚀 Servidor online na porta ${PORT}`); });
