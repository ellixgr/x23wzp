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

// --- NOVO: SISTEMA DE MOEDAS SEGURO ---

app.post('/ganhar-moeda', async (req, res) => {
    const { usuarioID } = req.body;

    if (!usuarioID) {
        return res.status(400).json({ success: false, message: "ID do usuário ausente" });
    }

    try {
        const moedasRef = db.ref(`usuarios/${usuarioID}/moedas`);
        
        // Transação garante que o incremento seja atômico e seguro no servidor
        const resultado = await moedasRef.transaction((valorAtual) => {
            let total = valorAtual || 0;
            
            // TRAVA DE SEGURANÇA: Limite de 20 moedas
            if (total >= 20) {
                return; // Cancela a transação se já atingiu o limite
            }
            
            return total + 1;
        });

        // Se o resultado da transação não foi "committed", é porque caiu na trava do limite
        if (!resultado.committed) {
            return res.status(429).json({ 
                success: false, 
                message: "Limite de 20 moedas atingido por hoje!" 
            });
        }

        res.json({ 
            success: true, 
            novasMoedas: resultado.snapshot.val() 
        });

    } catch (error) {
        console.error("Erro ao creditar moeda:", error.message);
        res.status(500).json({ success: false, message: "Erro no servidor de moedas" });
    }
});

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

// --- SOLICITAÇÕES ---

app.post('/salvar-grupo', async (req, res) => {
    const { nome, link, categoria, descricao, foto, dono, codigoVip } = req.body;
    try {
        let e_vip = false;
        let validade = null;
        
        if (codigoVip) {
            const vipSnap = await db.ref(`codigos_vips/${codigoVip}`).once('value');
            if (vipSnap.exists() && vipSnap.val().status === "disponivel") {
                e_vip = true;
                validade = Date.now() + (vipSnap.val().validadeHoras * 3600000);
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

// --- NOVO: FUNÇÃO PARA CONTAR CLIQUES VIA SERVER (RENDER) ---

app.post('/contar-clique', async (req, res) => {
    const { key } = req.body;
    if (!key) return res.status(400).json({ error: "Key ausente" });

    try {
        const cliqueRef = db.ref(`grupos/${key}/cliques`);
        // Incremento atômico seguro feito pelo Admin SDK
        await cliqueRef.transaction((valorAtual) => {
            return (valorAtual || 0) + 1;
        });
        res.json({ success: true });
    } catch (error) {
        console.error("Erro ao contar clique:", error.message);
        res.status(500).json({ error: "Erro interno ao processar clique" });
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
    } catch (e) { console.log("Erro na faxina VIP:", e.message); }
}

setInterval(limparVipsVencidos, 15 * 60 * 1000);

const PORT = process.env.PORT || 10000;
app.listen(PORT, '0.0.0.0', () => { console.log(`🚀 Servidor online na porta ${PORT}`); });
