const fs = require('fs');
const path = require('path');
const qrcode = require('qrcode-terminal');
const pino = require('pino');
const {
    default: makeWASocket,
    useMultiFileAuthState,
    DisconnectReason,
    fetchLatestBaileysVersion,
} = require('@whiskeysockets/baileys');

const db = require('./db');

const config = JSON.parse(fs.readFileSync('./config.json', 'utf8'));
const SCHEDULE_PATH = path.join(__dirname, '..', 'schedule_data.json');
const ZONE_LABELS = { live: 'Live', luzes: 'Luzes', slide: 'Slide', coord: 'Coordenação' };
const logger = pino({ level: 'info' });

let sock = null;

function toJid(phone) {
    return `${String(phone).replace(/\D/g, '')}@s.whatsapp.net`;
}

function eventLabel(ev) {
    return `${ev.name ? ev.name + ' — ' : ''}${ev.date}`;
}

function loadScheduleIntoCache() {
    if (!fs.existsSync(SCHEDULE_PATH)) {
        logger.warn(`Sem schedule_data.json em ${SCHEDULE_PATH} — nada para sincronizar.`);
        return;
    }
    const payload = JSON.parse(fs.readFileSync(SCHEDULE_PATH, 'utf8'));
    db.replaceSchedule(payload);
}

// ---------- Envio de lembretes ----------

async function sendGroupReminder(ev, assignments, daysBefore) {
    if (!config.groupId) return;
    if (db.wasReminderSent(ev.id, null, daysBefore)) return;

    const lines = assignments.map(a => `• ${ZONE_LABELS[a.zone] || a.zone}: ${a.name}`);
    const text = `📅 *Lembrete de escala*\n${eventLabel(ev)}\n\n${lines.join('\n')}`;

    await sock.sendMessage(config.groupId, { text });
    db.markReminderSent(ev.id, null, daysBefore);
}

async function sendPersonalReminders(ev, assignments, daysBefore) {
    for (const a of assignments) {
        if (!a.phone) continue;
        if (db.wasReminderSent(ev.id, a.member_id, daysBefore)) continue;

        const text =
            `Olá ${a.name}! 👋\n` +
            `Estás escalado(a) para *${ZONE_LABELS[a.zone] || a.zone}* em ${eventLabel(ev)}.\n\n` +
            `Podes confirmar respondendo *CONFIRMO* ou *NÃO CONSIGO*?`;

        await sock.sendMessage(toJid(a.phone), { text });
        db.markReminderSent(ev.id, a.member_id, daysBefore);
    }
}

async function runReminderCheck() {
    for (const daysBefore of config.reminderDaysBefore) {
        const events = db.eventsDueForReminder(daysBefore);
        for (const ev of events) {
            const assignments = db.assignmentsForEvent(ev.id);
            if (assignments.length === 0) continue;
            try {
                await sendGroupReminder(ev, assignments, daysBefore);
                await sendPersonalReminders(ev, assignments, daysBefore);
            } catch (err) {
                logger.error({ err, eventId: ev.id }, 'Falha a enviar lembrete');
            }
        }
    }
}

// ---------- Respostas de confirmação ----------

const CONFIRM_WORDS = ['confirmo', 'confirmado', 'sim', 'ok', 'okay', 'vou', 'consigo'];
const DECLINE_WORDS = ['não consigo', 'nao consigo', 'não posso', 'nao posso', 'não vou', 'nao vou', 'não'];

function classifyReply(text) {
    const t = text.trim().toLowerCase();
    if (DECLINE_WORDS.some(w => t.includes(w))) return 'declined';
    if (CONFIRM_WORDS.some(w => t.includes(w))) return 'confirmed';
    return null;
}

async function handleIncomingDM(jid, text) {
    const phone = jid.split('@')[0];
    const member = db.findMemberByPhone(phone);
    if (!member) return;

    const status = classifyReply(text);
    if (!status) return;

    const pending = db.pendingAssignmentsForMember(member.id);
    if (pending.length === 0) return;

    const target = pending[0];
    db.setConfirmation(target.event_id, member.id, status);

    const ack = status === 'confirmed'
        ? `Boa, ${member.name}! Confirmado para ${eventLabel(target)}. 👍`
        : `Ok, ${member.name}, fica registado que não consegues em ${eventLabel(target)}. Vou avisar para se arranjar substituto.`;
    await sock.sendMessage(jid, { text: ack });

    if (status === 'declined' && config.groupId) {
        await sock.sendMessage(config.groupId, {
            text: `⚠️ ${member.name} não pode em ${eventLabel(target)} (${ZONE_LABELS[target.zone] || target.zone}). Precisa de substituto.`,
        });
    }
}

// ---------- Ligação (sessão curta, não fica sempre ligado) ----------

function connect() {
    return new Promise(async (resolve, reject) => {
        const { state, saveCreds } = await useMultiFileAuthState('auth_state');
        const { version } = await fetchLatestBaileysVersion();

        sock = makeWASocket({ version, auth: state, logger, printQRInTerminal: false });
        sock.ev.on('creds.update', saveCreds);

        sock.ev.on('connection.update', (update) => {
            const { connection, lastDisconnect, qr } = update;
            if (qr) {
                console.log('\nEscaneia este QR code no WhatsApp (Dispositivos ligados > Ligar dispositivo):\n');
                qrcode.generate(qr, { small: true });
            }
            if (connection === 'open') {
                resolve();
            } else if (connection === 'close') {
                const code = lastDisconnect?.error?.output?.statusCode;
                if (code === DisconnectReason.loggedOut) {
                    reject(new Error('Sessão perdida (logged out) — apaga auth_state/ e faz login outra vez.'));
                } else {
                    reject(new Error(`Ligação fechada antes de abrir (código ${code}).`));
                }
            }
        });

        sock.ev.on('messages.upsert', async ({ messages, type }) => {
            if (type !== 'notify') return;
            for (const msg of messages) {
                if (msg.key.fromMe) continue;
                if (msg.key.remoteJid?.endsWith('@g.us')) continue;
                const text = msg.message?.conversation || msg.message?.extendedTextMessage?.text || '';
                if (!text) continue;
                try {
                    await handleIncomingDM(msg.key.remoteJid, text);
                } catch (err) {
                    logger.error({ err }, 'Falha a processar resposta');
                }
            }
        });
    });
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// ---------- Modo utilitário: listar grupos (uso único, para descobrir groupId) ----------

async function listGroupsAndExit() {
    await connect();
    await sleep(3000);
    const groups = await sock.groupFetchAllParticipating();
    for (const g of Object.values(groups)) {
        console.log(`${g.id}\t${g.subject}`);
    }
    process.exit(0);
}

// ---------- Arranque principal ----------

async function main() {
    if (process.argv.includes('--groups')) {
        return listGroupsAndExit();
    }

    loadScheduleIntoCache();
    await connect();

    await runReminderCheck();

    // Janela curta para receber respostas pendentes (o WhatsApp entrega-as ao
    // ligar, mesmo sem o serviço estar sempre online).
    await sleep(config.waitMsForRepliesMs || 25000);

    sock.end();
    process.exit(0);
}

main().catch(err => {
    logger.error({ err }, 'Falha no serviço de notificações');
    process.exit(1);
});
