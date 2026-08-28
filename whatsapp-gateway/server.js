const express = require('express');
const cors = require('cors');
const QRCode = require('qrcode');
const qrcodeTerminal = require('qrcode-terminal');
const { Client, LocalAuth } = require('whatsapp-web.js');
const path = require('path');

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

const PORT = process.env.PORT || 8080;

let currentQrCode = null;
let isConnected = false;
let connectedNumber = null;

// Armazenamento em memória de grupos detectados
const knownGroups = {}; // { '120363...@g.us': 'Nome do Grupo' }

// ==========================================
// 🛡️ REGRAS ANTI-BAN & FILA DE ENVIO INTELIGENTE
// ==========================================
const messageQueue = [];
let isProcessingQueue = false;
const lastSentToNumber = {};

const SECURITY_CONFIG = {
    minDelayBetweenMsgsMs: 3000,
    maxDelayBetweenMsgsMs: 5000,
    minIntervalSameNumberMs: 15000,
    simulateTyping: true
};

console.log('========================================================');
console.log('  🛡️ GATEWAY WHATSAPP COM SUPORTE A GRUPOS & ANTI-BAN');
console.log('  🌐 Painel Web: http://localhost:' + PORT);
console.log('========================================================\n');

const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: path.join(__dirname, '.wwebjs_auth')
    }),
    puppeteer: {
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu'
        ]
    }
});

client.on('qr', (qr) => {
    currentQrCode = qr;
    isConnected = false;
    console.log('\n[WhatsApp] Novo QR Code gerado. Acesse http://localhost:' + PORT);
    try {
        qrcodeTerminal.generate(qr, { small: true });
    } catch (e) {}
});

client.on('ready', async () => {
    isConnected = true;
    currentQrCode = null;
    connectedNumber = client.info?.wid?.user || 'Conectado';
    console.log(`\n✅ WHATSAPP CONECTADO COM SUCESSO! (+${connectedNumber})`);
    
    // Tenta carregar grupos em segundo plano
    setTimeout(scanInitialGroups, 3000);
});

client.on('auth_failure', (msg) => {
    console.error('[WhatsApp] Falha na autenticação:', msg);
    isConnected = false;
});

client.on('disconnected', (reason) => {
    console.log('[WhatsApp] Desconectado:', reason);
    isConnected = false;
    currentQrCode = null;
    connectedNumber = null;
    client.initialize();
});

// Listener Inteligente: Captura qualquer mensagem de grupo e armazena o ID automaticamente
client.on('message', async (msg) => {
    try {
        if (msg.from && msg.from.endsWith('@g.us')) {
            const chat = await msg.getChat();
            const groupName = chat.name || 'Grupo WhatsApp';
            knownGroups[msg.from] = groupName;
            console.log(`[Grupo Detectado em Tempo Real] "${groupName}" -> ${msg.from}`);
        }
    } catch (e) {}
});

client.on('message_create', async (msg) => {
    try {
        if (msg.to && msg.to.endsWith('@g.us')) {
            const chat = await msg.getChat();
            const groupName = chat.name || 'Grupo WhatsApp';
            knownGroups[msg.to] = groupName;
        }
    } catch (e) {}
});

client.initialize();

async function scanInitialGroups() {
    try {
        const chats = await client.getChats();
        for (const c of (chats || [])) {
            if (c.isGroup || (c.id?._serialized && c.id._serialized.endsWith('@g.us'))) {
                knownGroups[c.id._serialized] = c.name || 'Grupo';
            }
        }
        console.log(`[WhatsApp] ${Object.keys(knownGroups).length} grupos sincronizados com sucesso.`);
    } catch (e) {
        console.log("[WhatsApp] Sincronização inicial de grupos será feita sob demanda.");
    }
}

// ==========================================
// 📦 PROCESSADOR DE FILA COM SUPORTE A GRUPOS
// ==========================================
function getRandomDelay(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

async function processQueue() {
    if (isProcessingQueue || messageQueue.length === 0) return;
    isProcessingQueue = true;

    while (messageQueue.length > 0) {
        const item = messageQueue.shift();
        const { targetPhone, textMessage, resolve, reject } = item;

        try {
            if (!isConnected) {
                throw new Error("WhatsApp desconectado");
            }

            const rawTarget = targetPhone.toString().trim();
            const isGroup = rawTarget.includes('@g.us') || rawTarget.includes('-');
            let chatId = null;

            if (isGroup) {
                chatId = rawTarget.endsWith('@g.us') ? rawTarget : `${rawTarget}@g.us`;
            } else {
                const clean = rawTarget.replace(/\D/g, '');
                try {
                    const idData = await client.getNumberId(clean);
                    if (idData && idData._serialized) {
                        chatId = idData._serialized;
                    }
                } catch (e) {}

                if (!chatId && clean.startsWith('55') && clean.length === 13) {
                    const withoutNine = clean.slice(0, 4) + clean.slice(5);
                    try {
                        const idData = await client.getNumberId(withoutNine);
                        if (idData && idData._serialized) {
                            chatId = idData._serialized;
                        }
                    } catch (e) {}
                }

                if (!chatId) {
                    chatId = clean.includes('@') ? clean : `${clean}@c.us`;
                }
            }

            // Cooldown de segurança
            const now = Date.now();
            if (lastSentToNumber[chatId]) {
                const elapsed = now - lastSentToNumber[chatId];
                if (elapsed < SECURITY_CONFIG.minIntervalSameNumberMs) {
                    const waitTime = SECURITY_CONFIG.minIntervalSameNumberMs - elapsed;
                    console.log(`[Anti-Ban] Aguardando cooldown de ${Math.round(waitTime/1000)}s para ${chatId}...`);
                    await new Promise(r => setTimeout(r, waitTime));
                }
            }

            // Digitação humana
            if (SECURITY_CONFIG.simulateTyping) {
                try {
                    const chat = await client.getChatById(chatId);
                    await chat.sendStateTyping();
                    await new Promise(r => setTimeout(r, getRandomDelay(1000, 2000)));
                    await chat.clearState();
                } catch (e) {}
            }

            const result = await client.sendMessage(chatId, textMessage);
            lastSentToNumber[chatId] = Date.now();

            console.log(`[WhatsApp] ✅ Mensagem enviada para ${chatId} (Fila restante: ${messageQueue.length})`);
            resolve(result);

            if (messageQueue.length > 0) {
                const delay = getRandomDelay(SECURITY_CONFIG.minDelayBetweenMsgsMs, SECURITY_CONFIG.maxDelayBetweenMsgsMs);
                console.log(`[Anti-Ban] ⏳ Pausa de segurança de ${(delay/1000).toFixed(1)}s...`);
                await new Promise(r => setTimeout(r, delay));
            }

        } catch (err) {
            console.error(`[WhatsApp] ❌ Erro ao enviar para ${targetPhone}:`, err.message);
            reject(err);
        }
    }

    isProcessingQueue = false;
}

function enqueueMessage(targetPhone, textMessage) {
    return new Promise((resolve, reject) => {
        messageQueue.push({ targetPhone, textMessage, resolve, reject });
        processQueue();
    });
}

// ROTA JSON DE GRUPOS COM BUSCA PROFUNDA
app.get('/groups', async (req, res) => {
    if (!isConnected || !client) {
        return res.json({ groups: [], total: 0, message: "WhatsApp não conectado" });
    }

    try {
        if (client.pupPage) {
            const raw = await client.pupPage.evaluate(async () => {
                try {
                    let list = [];
                    if (window.Store && window.Store.Chat) {
                        list = window.Store.Chat.models || [];
                    }
                    return list.map(c => {
                        const serialized = c.id ? (c.id._serialized || String(c.id)) : '';
                        const name = c.name || c.formattedTitle || (c.contact ? c.contact.name : '') || 'Grupo';
                        const isGrp = c.isGroup || serialized.endsWith('@g.us') || (c.id && c.id.server === 'g.us');
                        return { id: serialized, name, isGroup: isGrp };
                    });
                } catch (err) {
                    return [];
                }
            });

            for (const item of (raw || [])) {
                if (item.isGroup && item.id) {
                    knownGroups[item.id] = item.name;
                }
            }
        }
    } catch (e) {
        console.error("Erro na busca profunda:", e.message);
    }

    // Fallback getChats
    try {
        const chats = await client.getChats();
        for (const c of (chats || [])) {
            const serialized = c.id?._serialized || String(c.id);
            if (c.isGroup || serialized.endsWith('@g.us')) {
                knownGroups[serialized] = c.name || knownGroups[serialized] || 'Grupo';
            }
        }
    } catch (e) {}

    const groupsList = Object.keys(knownGroups).map(id => ({
        id,
        name: knownGroups[id]
    }));

    return res.json({ groups: groupsList, total: groupsList.length });
});

// ROTA VISUAL: Painel Dinâmico
app.get('/', async (req, res) => {
    let contentHtml = '';

    if (isConnected) {
        contentHtml = `
            <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); padding: 18px; border-radius: 18px; margin-top: 12px;">
                <div style="font-size: 40px; margin-bottom: 4px;">🟢</div>
                <h3 style="color: #10b981; margin: 0; font-size: 17px; font-weight: bold;">WhatsApp Conectado!</h3>
                <p style="color: #e2e8f0; font-size: 13px; margin-top: 4px;">Número Ativo: <strong>+${connectedNumber}</strong></p>
                <div style="display: flex; justify-content: space-around; margin-top: 12px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.1); font-size: 11px;">
                    <div><span style="color: #94a3b8;">Fila:</span> <strong id="queue-count" style="color: #6366f1;">${messageQueue.length}</strong></div>
                    <div><span style="color: #94a3b8;">Proteção:</span> <strong style="color: #10b981;">Anti-Ban Ativa 🛡️</strong></div>
                </div>
            </div>

            <!-- SEÇÃO DE GRUPOS DINÂMICA -->
            <div style="margin-top: 18px; border-top: 1px solid #1e293b; padding-top: 14px; text-align: left;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <h4 style="margin: 0; font-size: 13px; color: #cbd5e1;">👥 Grupos do WhatsApp:</h4>
                    <button onclick="loadGroups()" style="background: #334155; color: #94a3b8; border: none; padding: 4px 8px; border-radius: 6px; font-size: 10px; cursor: pointer;">
                        🔄 Atualizar
                    </button>
                </div>
                <p style="margin: 0 0 10px 0; font-size: 11px; color: #64748b;">
                    Clique em <strong>Copiar ID</strong> e cole no campo de WhatsApp do CFTV Monitor:
                </p>
                <div id="groups-container" style="max-height: 180px; overflow-y: auto; background: rgba(0,0,0,0.3); border-radius: 12px; padding: 6px;">
                    <div style="text-align: center; padding: 15px; color: #94a3b8; font-size: 11px;">
                        Buscando grupos conectados...
                    </div>
                </div>

                <div style="background: rgba(99, 102, 241, 0.1); border: 1px solid rgba(99, 102, 241, 0.2); border-radius: 10px; padding: 10px; margin-top: 12px; font-size: 11px; color: #c7d2fe;">
                    💡 <strong>Dica Rápida:</strong> Se um grupo novo não aparecer na lista acima, basta enviar qualquer mensagem dentro dele no seu WhatsApp (ex: <code>!cftv</code>) que ele será detectado na hora!
                </div>
            </div>

            <script>
                async function loadGroups() {
                    const container = document.getElementById('groups-container');
                    try {
                        const res = await fetch('/groups');
                        const data = await res.json();
                        if (!data.groups || data.groups.length === 0) {
                            container.innerHTML = '<div style="text-align: center; padding: 15px; color: #94a3b8; font-size: 11px;">Nenhum grupo sincronizado ainda.<br>Envie uma mensagem no grupo pelo WhatsApp para detectá-lo!</div>';
                            return;
                        }
                        container.innerHTML = data.groups.map(g => \`
                            <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 8px; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 11px;">
                                <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 250px;">
                                    <strong style="color: #f1f5f9; display: block; overflow: hidden; text-overflow: ellipsis;">👥 \${g.name}</strong>
                                    <code style="color: #818cf8; font-size: 10px;">\${g.id}</code>
                                </div>
                                <button onclick="navigator.clipboard.writeText('\${g.id}'); this.innerText='Copiado!'; setTimeout(()=>this.innerText='Copiar ID', 2000)" 
                                    style="background: #4f46e5; color: white; border: none; padding: 4px 8px; border-radius: 6px; font-size: 10px; cursor: pointer; font-weight: bold; flex-shrink: 0; margin-left: 8px;">
                                    Copiar ID
                                </button>
                            </div>
                        \`).join('');
                    } catch (e) {
                        container.innerHTML = '<div style="text-align: center; padding: 10px; color: #f87171; font-size: 11px;">Erro ao carregar lista de grupos.</div>';
                    }
                }
                loadGroups();
                setInterval(loadGroups, 8000);
            </script>
        `;
    } else if (currentQrCode) {
        try {
            const qrDataUrl = await QRCode.toDataURL(currentQrCode, { width: 280, margin: 2 });
            contentHtml = `
                <div style="background: #ffffff; padding: 12px; border-radius: 18px; display: inline-block; box-shadow: 0 10px 30px rgba(0,0,0,0.5); margin-top: 15px;">
                    <img src="${qrDataUrl}" alt="QR Code WhatsApp" style="display: block; width: 240px; height: 240px;" />
                </div>
                <p style="color: #cbd5e1; font-size: 12px; margin-top: 12px;">
                    Abra o WhatsApp > Aparelhos Conectados > Conectar um aparelho
                </p>
                <script>setTimeout(() => location.reload(), 5000);</script>
            `;
        } catch (e) {
            contentHtml = '<p style="color: #ef4444;">Erro ao gerar QR Code.</p>';
        }
    } else {
        contentHtml = `
            <div style="color: #f59e0b; padding: 25px;">
                <div style="font-size: 35px;">⏳</div>
                <p style="margin-top: 10px; font-size: 13px;">Iniciando motor do WhatsApp...</p>
            </div>
            <script>setTimeout(() => location.reload(), 2500);</script>
        `;
    }

    res.send(`
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Gateway WhatsApp - CFTV Monitor</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    background: #090d16;
                    color: #f8fafc;
                    margin: 0;
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    text-align: center;
                    padding: 20px 0;
                }
                .card {
                    background: #0f172a;
                    border: 1px solid #1e293b;
                    border-radius: 24px;
                    padding: 25px;
                    max-width: 480px;
                    width: 92%;
                    box-shadow: 0 20px 50px rgba(0,0,0,0.6);
                }
                h1 { font-size: 18px; margin: 0; color: #fff; }
                p.sub { font-size: 11px; color: #64748b; margin: 2px 0 10px 0; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>GATEWAY WHATSAPP & GRUPOS</h1>
                <p class="sub">CFTV MONITOR • Porta ${PORT}</p>
                ${contentHtml}
                <div style="margin-top: 18px; padding-top: 12px; border-top: 1px solid #1e293b; display: flex; justify-content: space-around; font-size: 11px;">
                    <a href="http://localhost:8001" style="color: #6366f1; text-decoration: none; font-weight: bold;">← Painel v2.0</a>
                    <a href="http://localhost:8000" style="color: #10b981; text-decoration: none; font-weight: bold;">Painel v1.0 →</a>
                </div>
            </div>
        </body>
        </html>
    `);
});

// ROTA POST: /message/sendText/:instance
app.post('/message/sendText/:instance', async (req, res) => {
    try {
        const body = req.body;
        const number = body.number || body.phone;
        const text = body.textMessage?.text || body.text || body.message;

        if (!number || !text) {
            return res.status(400).json({ error: "Campos 'number' e 'text' são obrigatórios" });
        }

        enqueueMessage(number, text)
            .then(() => console.log(`[HTTP Callback] Sucesso para ${number}`))
            .catch(err => console.error(`[HTTP Callback Error] ${err.message}`));

        return res.status(200).json({
            status: "QUEUED",
            message: "Mensagem na fila de envio seguro",
            target: number
        });
    } catch (err) {
        return res.status(500).json({ error: err.message });
    }
});

// ROTA POST: /send
app.post('/send', async (req, res) => {
    try {
        const { number, message, text } = req.body;
        const msgText = message || text;

        if (!number || !msgText) {
            return res.status(400).json({ error: "Campos 'number' e 'message' são obrigatórios" });
        }

        enqueueMessage(number, msgText);
        return res.status(200).json({ status: "QUEUED", message: "Na fila segura" });
    } catch (err) {
        return res.status(500).json({ error: err.message });
    }
});

app.listen(PORT, () => {
    console.log(`[CFTV-WhatsApp] Servidor HTTP pronto em http://localhost:${PORT}`);
});
