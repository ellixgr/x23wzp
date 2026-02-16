const express = require('express');
const admin = require('firebase-admin');
const cors = require('cors');
const crypto = require('crypto');
const helmet = require('helmet');
const app = express();

// Configurações de Segurança e Middleware
app.use(helmet({ contentSecurityPolicy: false })); 
app.use(cors({ origin: '*' }));
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ limit: '10mb', extended: true }));

// Inicialização do Firebase
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
const SENHA_MESTRE = process.env.SENHA_MESTRE;

// ==========================================
//    ROTAS DO PAINEL ADM (CHAVE MESTRE)
// ==========================================

// Puxa todos os dados para o Painel de uma vez
app.get('/admin/dados', async (req, res) => {
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

// Aprovar ou Recusar solicitações
app.post('/admin/decidir', async (req, res) => {
    const { id, aprovar } = req.body;
    try {
        const refSol = db.ref(`solicitacoes/${id}`);
        if (aprovar) {
            const snap = await refSol.once('value');
            const dados = snap.val();
            if(dados) {
                await db.ref(`grupos/${id}`).set({ 
                    ...dados, 
                    status: 'aprovado', 
                    cliques: 0,
                    criadoEm: Date.now() 
                });
            }
        }
        await refSol.remove();
        res.json({ success: true });
    } catch (e) { res.status(500).json({ success: false, message: e.message }); }
});

// Adicionar Moedas via Painel
app.post('/admin/moedas/add', async (req, res) => {
    const { uid, qtd } = req.body;
    try {
        await db.ref(`usuarios/${uid}/moedas`).transaction(atual => (atual || 0) + qtd);
        res.json({ success: true });
    } catch (e) { res.status(500).json({ success: false }); }
});

// Gerar Código VIP via Painel
app.post('/admin/vip/gerar', async (req, res) => {
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

// Vídeos Shopee (Add/Delete)
app.post('/admin/video/add', async (req, res) => {
    try {
        await db.ref(`videos_shopee/${Date.now()}`).set({ link: req.body.link });
        res.json({ success: true });
    } catch (e) { res.status(500).json({ success: false }); }
});

app.post('/admin/video/delete', async (req, res) => {
    try {
        await db.ref(`videos_shopee/${req.body.id}`).remove();
        res.json({ success: true });
    } catch (e) { res.status(500).json({ success: false }); }
});

// Editar/Apagar Grupo via Monitoramento do Painel
app.post('/admin/grupo/edit', async (req, res) => {
    const { id, nome, link, foto } = req.body;
    try {
        await db.ref(`grupos/${id}`).update({ nome, link, foto });
        res.json({ success: true });
    } catch (e) { res.status(500).json({ success: false }); }
});

app.post('/admin/grupo/delete', async (req, res) => {
    try {
        await db.ref(`grupos/${req.body.id}`).remove();
        res.json({ success: true });
    } catch (e) { res.status(500).json({ success: false }); }
});

// ==========================================
//    ROTAS DO SITE (USUÁRIOS)
// ==========================================

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

// ==========================================
//    ROTAS DE GERENCIAMENTO DO USUÁRIO
// ==========================================

// Rota para o usuário editar o próprio grupo
app.post('/editar-grupo', async (req, res) => {
    const { key, donoLocal, nome, link, descricao, categoria, foto } = req.body;
    try {
        const refGrupo = db.ref(`grupos/${key}`);
        const snap = await refGrupo.once('value');
        const grupo = snap.val();

        // Verifica se o grupo existe e se quem está editando é o dono
        if (grupo && (grupo.dono === donoLocal || grupo.usuarioID === donoLocal)) {
            await refGrupo.update({ nome, link, descricao, categoria, foto });
            return res.json({ success: true });
        }
        res.status(403).json({ success: false, message: "Acesso negado ou grupo inexistente" });
    } catch (e) { res.status(500).json({ success: false, message: e.message }); }
});

// Rota para o usuário excluir o próprio grupo
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

// Rota para Impulsionar (Sobe o grupo para o topo)
app.post('/impulsionar-grupo', async (req, res) => {
    const { key, donoLocal } = req.body;
    try {
        const refGrupo = db.ref(`grupos/${key}`);
        const snap = await refGrupo.once('value');
        const grupo = snap.val();

        if (grupo && (grupo.dono === donoLocal || grupo.usuarioID === donoLocal)) {
            // Atualiza o timestamp do último impulso
            await refGrupo.update({ ultimoImpulso: Date.now() });
            return res.json({ success: true });
        }
        res.status(403).json({ success: false });
    } catch (e) { res.status(500).json({ success: false }); }
});


// Limpeza de VIPs Expirados
setInterval(async () => {
    const agora = Date.now();
    const snap = await db.ref('grupos').orderByChild('vip').equalTo(true).once('value');
    snap.forEach(child => {
        if (child.val().vipExpiraEm && agora > child.val().vipExpiraEm) {
            db.ref(`grupos/${child.key}`).update({ vip: false, vipExpiraEm: null });
        }
    });
}, 60000);

const PORT = process.env.PORT || 10000;
app.listen(PORT, '0.0.0.0', () => console.log(`🚀 Servidor Rodando na Porta ${PORT}`));
