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
        console.log("✅ Banco Conectado");
    } catch (e) {
        console.log("❌ Erro Firebase:", e.message);
    }
}

const db = admin.database();
const SENHA_MESTRE = "cavalo777_";

// --- ROTAS QUE JÁ ESTAVAM PERFEITAS ---

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
            await db.ref(`codigos_vips/${codigo}`).update({ status: "usado" });
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

app.post('/gerar-vip-gratis', async (req, res) => {
    const { moedas } = req.body;
    if (!moedas || moedas < 20) return res.status(400).json({ sucesso: false, mensagem: "Moedas insuficientes" });
    try {
        const codigoGerado = "FREE-" + crypto.randomBytes(4).toString('hex').toUpperCase();
        await db.ref(`codigos_vips/${codigoGerado}`).set({
            status: "disponivel",
            validadeHoras: 24,
            criadoEm: new Date().toISOString(),
            origem: "moedas_video"
        });
        res.json({ sucesso: true, codigo: codigoGerado });
    } catch (error) { res.status(500).json({ sucesso: false, error: "Erro no servidor" }); }
});

// --- NOVAS ROTAS PARA CONTORNAR A REGRA DO E-MAIL ---

// ROTA EDITAR: O Admin SDK ignora a trava de e-mail do Firebase JSON
app.post('/editar-grupo', async (req, res) => {
    const { key, donoLocal, nome, link, descricao, categoria, foto, codigoVip } = req.body;
    try {
        const grupoRef = db.ref(`grupos/${key}`);
        const snapshot = await grupoRef.once('value');
        if (!snapshot.exists()) return res.status(404).json({ success: false, message: "Grupo não existe" });

        const grupoData = snapshot.val();
        // Segurança: Só o dono do ID pode mexer
        if (grupoData.dono !== donoLocal) return res.status(403).json({ success: false, message: "Acesso negado" });

        let dadosUpdate = { nome, link, descricao, categoria, foto };

        // Se enviou código VIP, valida e ativa
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
    } catch (e) { res.status(500).json({ success: false }); }
});

// ROTA EXCLUIR: O usuário comum não consegue deletar via site, mas o servidor sim
app.post('/excluir-grupo', async (req, res) => {
    const { key, donoLocal } = req.body;
    try {
        const grupoRef = db.ref(`grupos/${key}`);
        const snapshot = await grupoRef.once('value');
        if (snapshot.exists() && snapshot.val().dono === donoLocal) {
            await grupoRef.remove();
            return res.json({ success: true });
        }
        res.status(403).json({ success: false });
    } catch (e) { res.status(500).json({ success: false }); }
});

// FAXINA AUTOMÁTICA
async function limparVipsVencidos() {
    const agora = Date.now();
    try {
        const gruposRef = db.ref('grupos');
        const snapshot = await gruposRef.once('value');
        if (snapshot.exists()) {
            snapshot.forEach((child) => {
                const grupo = child.val();
                if (grupo.vip === true && grupo.vipAte && agora > grupo.vipAte) {
                    db.ref(`grupos/${child.key}`).update({ vip: false, vipAte: null });
                }
            });
        }
    } catch (e) {}
}
setInterval(limparVipsVencidos, 15 * 60 * 1000);

const PORT = process.env.PORT || 10000;
app.listen(PORT, '0.0.0.0', () => { console.log(`Rodando na porta ${PORT}`); });
