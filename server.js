const express = require('express');
const admin = require('firebase-admin');
const cors = require('cors');
const crypto = require('crypto');
const helmet = require('helmet');
const app = express();
app.use(helmet()); 
app.use(cors({
    origin: '*',
    methods: ['GET', 'POST'],
    allowedHeaders: ['Content-Type']
}));
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ limit: '10mb', extended: true }));
if (!admin.apps.length) {
    try {
        const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT);
        admin.initializeApp({
            credential: admin.credential.cert(serviceAccount),
            databaseURL: "https://cliques-4a2c1-default-rtdb.firebaseio.com"
        });
        console.log("✅ Servidor Autenticado");
    } catch (e) {
        console.error("❌ Erro na Service Account");
        process.exit(1);
    }
}
const db = admin.database();
const SENHA_MESTRE = process.env.SENHA_MESTRE;
app.post('/ganhar-moeda', async (req, res) => {
    const { usuarioID } = req.body;
    if (!usuarioID) return res.status(400).json({ success: false });

    try {
        const moedasRef = db.ref(`usuarios/${usuarioID}/moedas`);
        await moedasRef.transaction((atual) => (atual || 0) + 1);
        res.json({ success: true });
    } catch (e) {
        res.status(500).json({ success: false });
    }
});

app.get('/status-usuario/:usuarioID', async (req, res) => {
    const { usuarioID } = req.params;
    try {
        const snap = await db.ref(`usuarios/${usuarioID}`).once('value');
        const dados = snap.val();
        res.json({
            success: true,
            moedas: dados?.moedas || 0,
            id: usuarioID
        });
    } catch (e) {
        res.status(500).json({ success: false });
    }
});

app.post('/resgatar-vip-server', async (req, res) => {
    const { usuarioID } = req.body;
    try {
        const userRef = db.ref(`usuarios/${usuarioID}`);
        const snap = await userRef.once('value');
        const moedas = snap.val()?.moedas || 0;

        if (moedas < 30) {
            return res.json({ success: false, message: "Moedas insuficientes! Você precisa de 30." });
        }

        const novoCodigo = "VIP-" + crypto.randomBytes(3).toString('hex').toUpperCase();
        
        await db.ref(`codigos_vips/${novoCodigo}`).set({
            status: "disponivel",
            validadeHoras: 5,
            criadoEm: new Date().toISOString()
        });
        await userRef.update({ moedas: 0 });

        res.json({ success: true, codigo: novoCodigo });
    } catch (e) {
        res.status(500).json({ success: false });
    }
});

app.post('/contar-clique', async (req, res) => {
    const { key } = req.body;
    if (!key) return res.status(400).send();
    try {
        await db.ref(`grupos/${key}/cliques`).transaction(c => (c || 0) + 1);
        res.json({ success: true });
    } catch (e) { res.status(500).send(); }
});

app.post('/editar-grupo', async (req, res) => {
    const { key, donoLocal, nome, link, descricao, categoria, foto, codigoVip } = req.body;
    try {
        const refGrupo = db.ref(`grupos/${key}`);
        const snapshot = await refGrupo.once('value');
        const dados = snapshot.val();

        if (dados && dados.dono === donoLocal) {
            let updateDados = { nome, link, descricao, categoria, foto };
            if (codigoVip) {
                const vipSnap = await db.ref(`codigos_vips/${codigoVip}`).once('value');
                if (vipSnap.exists() && vipSnap.val().status === "disponivel") {
                    updateDados.vip = true;
                    updateDados.vipExpiraEm = Date.now() + (parseInt(vipSnap.val().validadeHoras) * 3600000);
                    await db.ref(`codigos_vips/${codigoVip}`).update({ status: "usado" });
                }
            }

            await refGrupo.update(updateDados);
            return res.json({ success: true, isVip: updateDados.vip || dados.vip });
        }
        res.json({ success: false, message: "Acesso Negado" });
    } catch (e) { res.status(500).json({ success: false }); }
});


app.post('/excluir-grupo', async (req, res) => {
    const { key, donoLocal } = req.body;
    try {
        const refGrupo = db.ref(`grupos/${key}`);
        const snapshot = await refGrupo.once('value');
        const dados = snapshot.val();
        if (dados && dados.dono === donoLocal) {
            await refGrupo.remove();
            return res.json({ success: true });
        }
        res.json({ success: false });
    } catch (e) { res.status(500).json({ success: false }); }
});

app.post('/impulsionar-grupo', async (req, res) => {
    const { key, donoLocal } = req.body;
    try {
        const refGrupo = db.ref(`grupos/${key}`);
        const snapshot = await refGrupo.once('value');
        if (snapshot.val().dono === donoLocal) {
            await refGrupo.update({ ultimoImpulso: Date.now() });
            return res.json({ success: true });
        }
        res.json({ success: false });
    } catch (e) { res.status(500).json({ success: false }); }
});

app.post('/login-abareta', (req, res) => {
    const { senha } = req.body;
    if (!SENHA_MESTRE || senha !== SENHA_MESTRE) return res.json({ autorizado: false });
    res.json({ autorizado: true });
});

app.post('/gerar-vip', async (req, res) => {
    const { senha, duracaoHoras } = req.body;
    if (!SENHA_MESTRE || senha !== SENHA_MESTRE) return res.status(403).json({ error: "🔒" });
    const codigo = crypto.randomBytes(4).toString('hex').toUpperCase();
    try {
        await db.ref(`codigos_vips/${codigo}`).set({
            status: "disponivel",
            validadeHoras: parseInt(duracaoHoras) || 24,
            criadoEm: new Date().toISOString()
        });
        res.json({ codigo });
    } catch (e) { res.status(500).json({ error: "Erro" }); }
});

app.post('/salvar-grupo', async (req, res) => {
    const { nome, link, categoria, descricao, foto, dono, codigoVip } = req.body;
    try {
        let e_vip = false;
        let validade = 0; // Inicia com 0 em vez de null para evitar erros no Firebase

        if (codigoVip) {
            const vipSnap = await db.ref(`codigos_vips/${codigoVip}`).once('value');
            if (vipSnap.exists() && vipSnap.val().status === "disponivel") {
                e_vip = true;
                validade = Date.now() + (parseInt(vipSnap.val().validadeHoras) * 3600000);
                await db.ref(`codigos_vips/${codigoVip}`).update({ status: "usado" });
            }
        }

        const novoRef = db.ref('grupos').push();
        await novoRef.set({
            nome, link, categoria, descricao, foto, dono,
            vip: e_vip, 
            vipExpiraEm: validade,
            status: "aprovado", 
            criadoEm: Date.now(), 
            cliques: 0
        });
        res.json({ success: true, isVip: e_vip }); 
    } catch (e) { 
        console.error(e);
        res.status(500).json({ error: "Erro ao salvar" }); 
    }
});


const limparVips = async () => {
    const agora = Date.now();
    try {
        const snap = await db.ref('grupos').orderByChild('vip').equalTo(true).once('value');
        if (!snap.exists()) return;
        snap.forEach((child) => {
            const g = child.val();
            if (g.vipExpiraEm && agora > g.vipExpiraEm) {
                db.ref(`grupos/${child.key}`).update({ vip: false, vipExpiraEm: null });
            }
        });
    } catch (e) { }
};
setInterval(limparVips, 1 * 60 * 1000); (1 minuto)

process.on('uncaughtException', (err) => console.error('⚠️ Erro Grave:', err.message));
process.on('unhandledRejection', (reason) => console.error('⚠️ Rejeição Silenciosa:', reason));

const PORT = process.env.PORT || 10000;
const server = app.listen(PORT, '0.0.0.0', () => { 
    console.log(`🚀 Servidor Blindado na porta ${PORT}`); 
});

server.keepAliveTimeout = 65000;
server.headersTimeout = 66000;
