const Database = require('better-sqlite3');
const db = new Database('notify.db');
db.pragma('journal_mode = WAL');

db.exec(`
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    name TEXT,
    date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assignments (
    event_id INTEGER NOT NULL,
    zone TEXT NOT NULL,
    member_id INTEGER NOT NULL,
    PRIMARY KEY (event_id, zone)
);

CREATE TABLE IF NOT EXISTS reminders_sent (
    event_id INTEGER NOT NULL,
    member_id INTEGER,             -- NULL = mensagem de grupo (não é por pessoa)
    days_before INTEGER NOT NULL,
    sent_at TEXT NOT NULL,
    PRIMARY KEY (event_id, member_id, days_before)
);

CREATE TABLE IF NOT EXISTS confirmations (
    event_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    status TEXT NOT NULL,          -- 'confirmed' | 'declined'
    replied_at TEXT NOT NULL,
    PRIMARY KEY (event_id, member_id)
);
`);

/** Substitui todo o cache local pelo payload de sincronização vindo da app desktop. */
function replaceSchedule({ members, events, assignments }) {
    const tx = db.transaction(() => {
        db.prepare('DELETE FROM assignments').run();
        db.prepare('DELETE FROM events').run();
        db.prepare('DELETE FROM members').run();

        const insMember = db.prepare('INSERT INTO members (id, name, phone) VALUES (?, ?, ?)');
        for (const m of members) insMember.run(m.id, m.name, m.phone || '');

        const insEvent = db.prepare('INSERT INTO events (id, name, date) VALUES (?, ?, ?)');
        for (const e of events) insEvent.run(e.id, e.name || '', e.date);

        const insAssign = db.prepare(
            'INSERT INTO assignments (event_id, zone, member_id) VALUES (?, ?, ?)'
        );
        for (const a of assignments) insAssign.run(a.event_id, a.zone, a.member_id);
    });
    tx();
}

/** Eventos cuja data cai exatamente `daysBefore` dias a partir de hoje. */
function eventsDueForReminder(daysBefore) {
    return db.prepare(`
        SELECT * FROM events
        WHERE date(date) = date('now', '+' || ? || ' days')
    `).all(daysBefore);
}

function assignmentsForEvent(eventId) {
    return db.prepare(`
        SELECT a.zone, m.id AS member_id, m.name, m.phone
        FROM assignments a JOIN members m ON m.id = a.member_id
        WHERE a.event_id = ?
    `).all(eventId);
}

function wasReminderSent(eventId, memberId, daysBefore) {
    return !!db.prepare(
        'SELECT 1 FROM reminders_sent WHERE event_id = ? AND member_id IS ? AND days_before = ?'
    ).get(eventId, memberId, daysBefore);
}

function markReminderSent(eventId, memberId, daysBefore) {
    db.prepare(
        'INSERT OR IGNORE INTO reminders_sent (event_id, member_id, days_before, sent_at) VALUES (?, ?, ?, datetime(\'now\'))'
    ).run(eventId, memberId, daysBefore);
}

/** Atribuições pendentes de confirmação para um membro, mais recentes primeiro. */
function pendingAssignmentsForMember(memberId) {
    return db.prepare(`
        SELECT a.event_id, a.zone, e.name AS event_name, e.date
        FROM assignments a
        JOIN events e ON e.id = a.event_id
        WHERE a.member_id = ?
          AND date(e.date) >= date('now')
          AND NOT EXISTS (
              SELECT 1 FROM confirmations c
              WHERE c.event_id = a.event_id AND c.member_id = a.member_id
          )
        ORDER BY e.date ASC
    `).all(memberId);
}

function setConfirmation(eventId, memberId, status) {
    db.prepare(`
        INSERT INTO confirmations (event_id, member_id, status, replied_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(event_id, member_id) DO UPDATE SET status = excluded.status, replied_at = excluded.replied_at
    `).run(eventId, memberId, status);
}

function findMemberByPhone(phone) {
    return db.prepare('SELECT * FROM members WHERE phone = ?').get(phone);
}

function allConfirmationsWithNames() {
    return db.prepare(`
        SELECT e.id AS event_id, e.name AS event_name, e.date, m.name AS member_name,
               a.zone, c.status, c.replied_at
        FROM assignments a
        JOIN events e ON e.id = a.event_id
        JOIN members m ON m.id = a.member_id
        LEFT JOIN confirmations c ON c.event_id = a.event_id AND c.member_id = a.member_id
        WHERE date(e.date) >= date('now')
        ORDER BY e.date ASC
    `).all();
}

module.exports = {
    replaceSchedule,
    eventsDueForReminder,
    assignmentsForEvent,
    wasReminderSent,
    markReminderSent,
    pendingAssignmentsForMember,
    setConfirmation,
    findMemberByPhone,
    allConfirmationsWithNames,
};
