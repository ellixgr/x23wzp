const express = require('express');
const admin = require('firebase-admin');
const cors = require('cors');
const crypto = require('crypto');
const helmet = require('helmet');
const app = express();
app.use(helmet({ contentSecurityPolicy: false })); 
app.use(cors({ origin: '*' }));
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ limit: '10mb', extended: true }));
if (!admin.apps.length) {
    try {
        const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT);
        admin.initializeApp({
            credential: admin.credential.cert(serviceAccount),
            databaseURL: "https://cliques-4a2c1-default-rtdb.firebaseio.com"
        });
        console.log("✅ Servidor Autenticado com Chave Mestre");
    } catch (e) {
        console.error("❌ Erro Crítico na Service Account");
        process.exit(1);
    }
}
const db = admin.database();
const SENHA_MESTRE = process.env.ADMIN_PASS || process.env.SENHA_MESTRE;
const verificarAdmin = (req, res, next) => {
    const senhaRecebida = req.headers['x-admin-pass'];
    if (!senhaRecebida || senhaRecebida !== SENHA_MESTRE) {
        return res.status(401).json({ success: false, message: "Acesso Negado: Senha Inválida" });
    }
    next();
};
app.get('/admin/dados', verificarAdmin, async (req, res) => {
    try {
        const snapshot = await db.ref('/').once('value');
        const d = snapshot.val() || {};        
        const grupos = d.grupos || {};
        const usuarios = d.usuarios || {};
        const agora = Date.now();
        res.json({
            stats: {
                visitas: d.visitas || 0,
                vips: Object.values(grupos).filter(g => (g.vipExpiraEm || g.vipAte) > agora).length,
                grupos: Object.keys(grupos).length,
                users: Object.keys(usuarios).length
            },
            solicitacoes: d.solicitacoes || {},
            grupos: grupos,
            usuarios: usuarios,
            codigos: d.codigos_vips || {},
            videos: d.videos_shopee || {}
        });
    } catch (e) { res.status(500).json({ error: e.message }); }
});

app.get('/listar-grupos', async (req, res) => {
  try {
    const [gruposSnap, solicitacoesSnap] = await Promise.all([
      db.ref('grupos').once('value'),
      db.ref('solicitacoes').once('value')
    ]);
    const aprovados = gruposSnap.val() || {};
    const pendentes = solicitacoesSnap.val() || {};
    const listaTotal = [];
    Object.keys(aprovados).forEach(key => {
      listaTotal.push({ ...aprovados[key], key, aprovado: true });
    });
    Object.keys(pendentes).forEach(key => {
      listaTotal.push({ ...pendentes[key], key, aprovado: false });
    });
    res.json(listaTotal);
  } catch (error) {
    res.status(500).json({ error: "Erro ao buscar dados" });
  }
});

app.get('/admin/dados-publicos', async (req, res) => {
    try {
        const snapshot = await db.ref('videos_shopee').once('value');
        res.json({ videos: snapshot.val() || {} });
    } catch (e) {
        res.status(500).json({ videos: {} });
    }
});
app.post('/admin/decidir', verificarAdmin, async (req, res) => {
    const { id, aprovar } = req.body;
    try {
        const refSol = db.ref(`solicitacoes/${id}`);
        if (aprovar) {
            const snap = await refSol.once('value');
            const dados = snap.val();
            if(dados) {
                const expira = Number(dados.vipExpiraEm) || 0;
                const ehVip = (dados.vip === true || dados.vip === "true");
                await db.ref(`grupos/${id}`).set({ 
                    ...dados, 
                    status: 'aprovado', 
                    cliques: 0,
                    vip: ehVip, 
                    vipExpiraEm: expira, 
                    criadoEm: Date.now() 
                });
            }
        }
        await refSol.remove();
        res.json({ success: true });
    } catch (e) { res.status(500).json({ success: false, message: e.message }); }
});
app.post('/admin/moedas/add', verificarAdmin, async (req, res) => {
    const { uid, qtd } = req.body;
    try {
        await db.ref(`usuarios/${uid}/moedas`).transaction(atual => (atual || 0) + qtd);
        res.json({ success: true });
    } catch (e) { res.status(500).json({ success: false }); }
});
app.post('/admin/vip/gerar', verificarAdmin, async (req, res) => {
    const { horas } = req.body;
    try {
        const cod = "VIP-" + crypto.randomBytes(3).toString('hex').toUpperCase();
        await db.ref(`codigos_vips/${cod}`).set({
            status: "disponivel",
            validadeHoras: horas,
            usado: false,
            criadoEm: Date.now()
        });
        res.json({ success: true, codigo: cod });
    } catch (e) { res.status(500).json({ success: false }); }
});
app.post('/admin/video/add', verificarAdmin, async (req, res) => {
    try {
        await db.ref(`videos_shopee/${Date.now()}`).set({ link: req.body.link });
        res.json({ success: true });
    } catch (e) { res.status(500).json({ success: false }); }
});
app.post('/admin/video/delete', verificarAdmin, async (req, res) => {
    try {
        await db.ref(`videos_shopee/${req.body.id}`).remove();
        res.json({ success: true });
    } catch (e) { res.status(500).json({ success: false }); }
});
app.post('/admin/grupo/edit', verificarAdmin, async (req, res) => {
    const { id, nome, link, foto } = req.body;
    try {
        await db.ref(`grupos/${id}`).update({ nome, link, foto });
        res.json({ success: true });
    } catch (e) { res.status(500).json({ success: false }); }
});
app.post('/admin/grupo/delete', verificarAdmin, async (req, res) => {
    try {
        await db.ref(`grupos/${req.body.id}`).remove();
        res.json({ success: true });
    } catch (e) { res.status(500).json({ success: false }); }
});
app.post('/ganhar-moeda', async (req, res) => {
    const { usuarioID } = req.body;
    if (!usuarioID) return res.status(400).json({ success: false });
    try {
        await db.ref(`usuarios/${usuarioID}/moedas`).transaction((atual) => (atual || 0) + 1);
        res.json({ success: true });
    } catch (e) { res.status(500).json({ success: false }); }
});
app.get('/status-usuario/:usuarioID', async (req, res) => {
    try {
        const snap = await db.ref(`usuarios/${req.params.usuarioID}`).once('value');
        res.json({ success: true, moedas: snap.val()?.moedas || 0, id: req.params.usuarioID });
    } catch (e) { res.status(500).json({ success: false }); }
});
app.post('/salvar-grupo', async (req, res) => {
    const { nome, link, categoria, descricao, foto, dono, codigoVip } = req.body;
    try {
        const gSnap = await db.ref('grupos').orderByChild('link').equalTo(link).once('value');
        if (gSnap.exists()) return res.json({ success: false, message: "Link já cadastrado!" });
        let e_vip = false;
        let expira = 0;
        if (codigoVip) {
            const vSnap = await db.ref(`codigos_vips/${codigoVip}`).once('value');
            if (vSnap.exists() && vSnap.val().status === "disponivel") {
                e_vip = true;
                expira = Date.now() + (vSnap.val().validadeHoras * 3600000);
                await db.ref(`codigos_vips/${codigoVip}`).update({ status: "usado", usado: true });
            }
        }
        await db.ref('solicitacoes').push().set({
            nome, link, categoria, descricao, foto, dono,
            vip: e_vip, vipExpiraEm: expira, status: "pendente", criadoEm: Date.now()
        });
        res.json({ success: true, message: "Enviado para aprovação!" });
    } catch (e) { res.status(500).json({ error: e.message }); }
});
app.post('/contar-clique', async (req, res) => {
    try {
        await db.ref(`grupos/${req.body.key}/cliques`).transaction(c => (c || 0) + 1);
        res.json({ success: true });
    } catch (e) { res.status(500).send(); }
});
app.post('/editar-grupo', async (req, res) => {
    const { key, donoLocal, nome, link, descricao, categoria, foto, codigoVip } = req.body;
    try {
        const refGrupo = db.ref(`grupos/${key}`);
        const snap = await refGrupo.once('value');
        const grupo = snap.val();
        if (snap.exists() && (grupo.dono === donoLocal || grupo.usuarioID === donoLocal)) {
            let updates = { nome, link, descricao, categoria, foto };
            if (codigoVip && codigoVip.trim() !== "") {
                const codLimpo = codigoVip.trim();
                const vSnap = await db.ref(`codigos_vips/${codLimpo}`).once('value');
                
                if (vSnap.exists() && vSnap.val().status === "disponivel") {
                    const infoVip = vSnap.val();
                    updates.vip = true;
                    updates.vipExpiraEm = Date.now() + (Number(infoVip.validadeHoras) * 3600000);
                    await db.ref(`codigos_vips/${codLimpo}`).update({ status: "usado", usado: true });
                }
            }
            await refGrupo.update(updates);
            return res.json({ success: true, message: "Atualizado com sucesso!" });
        }
        res.status(403).json({ success: false, message: "Acesso negado" });
    } catch (e) {
        res.status(500).json({ success: false, message: e.message });
    }
});
app.post('/excluir-grupo', async (req, res) => {
    const { key, donoLocal } = req.body;
    try {
        const refGrupo = db.ref(`grupos/${key}`);
        const snap = await refGrupo.once('value');
        const grupo = snap.val();
        if (grupo && (grupo.dono === donoLocal || grupo.usuarioID === donoLocal)) {
            await refGrupo.remove();
            return res.json({ success: true });
        }
        res.status(403).json({ success: false });
    } catch (e) { res.status(500).json({ success: false }); }
});
app.post('/impulsionar-grupo', async (req, res) => {
    const { key, donoLocal } = req.body;
    try {
        const refGrupo = db.ref(`grupos/${key}`);
        const snap = await refGrupo.once('value');
        const grupo = snap.val();
        if (grupo && (grupo.dono === donoLocal || grupo.usuarioID === donoLocal)) {
            await refGrupo.update({ ultimoImpulso: Date.now() });
            return res.json({ success: true });
        }
        res.status(403).json({ success: false });
    } catch (e) { res.status(500).json({ success: false }); }
});
// Versão otimizada para não travar no Zeabur
setInterval(async () => {
    try {
        const agora = Date.now();
        // Buscamos apenas uma vez e processamos em segundo plano
        const snap = await db.ref('grupos').orderByChild('vip').equalTo(true).once('value');
        const updates = {};
        
        snap.forEach(child => {
            const dados = child.val();
            if (dados.vipExpiraEm && agora > dados.vipExpiraEm) {
                updates[`grupos/${child.key}/vip`] = false;
                updates[`grupos/${child.key}/vipExpiraEm`] = null;
            }
        });

        if (Object.keys(updates).length > 0) {
            await db.ref().update(updates);
            console.log(`✅ VIPs expirados limpos: ${Object.keys(updates).length}`);
        }
    } catch (e) {
        console.error("Erro na limpeza de VIPs:", e.message);
    }
}, 300000);

app.post('/resgatar-vip-server', async (req, res) => {
    const { usuarioID } = req.body;
    try {
        const userRef = db.ref(`usuarios/${usuarioID}`);
        const snap = await userRef.once('value');
        const moedas = snap.val()?.moedas || 0;
        if (moedas >= 30) {
            const cod = "VIP-" + crypto.randomBytes(3).toString('hex').toUpperCase();
            await db.ref(`codigos_vips/${cod}`).set({
                status: "disponivel",
                validadeHoras: 5,
                usado: false,
                criadoEm: Date.now()
            });
            await userRef.update({ moedas: moedas - 30 });
            return res.json({ success: true, codigo: cod });
        } else {
            return res.status(400).json({ success: false, message: "Moedas insuficientes!" });
        }
    } catch (e) {
        console.error(e);
        res.status(500).json({ success: false, message: "Erro interno no servidor." });
    }
});
const PORT = process.env.PORT || 8080;
app.listen(PORT, '0.0.0.0', () => console.log(`🚀 Servidor Rodando na Porta ${PORT}`));
