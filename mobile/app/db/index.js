import { Platform } from 'react-native';
import * as SQLite from 'expo-sqlite';

const isWeb = Platform.OS === 'web';
const db = isWeb ? null : SQLite.openDatabaseSync('herdoc_mobile.db');

const STORAGE_KEYS = {
  authState: 'herdoc_mobile_auth_state_v1',
  patients: 'herdoc_mobile_patients_v1',
  visits: 'herdoc_mobile_visits_v1',
  riskFlags: 'herdoc_mobile_risk_flags_v1',
  syncQueue: 'herdoc_mobile_sync_queue_v1',
  lastSyncedAt: 'herdoc_mobile_last_synced_at_v1',
};

const DATABASE_VERSION = 1;

function getWebStorageValue(key) {
  if (!isWeb || typeof window === 'undefined') {
    return null;
  }

  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function setWebStorageValue(key, value) {
  if (!isWeb || typeof window === 'undefined') {
    return;
  }

  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Ignore storage quota errors for local preview fallback.
  }
}

function getWebAuthStateMap() {
  const value = getWebStorageValue(STORAGE_KEYS.authState) || {};
  return typeof value === 'object' && value !== null ? value : {};
}

function setWebAuthStateMap(map) {
  setWebStorageValue(STORAGE_KEYS.authState, map);
}

function getWebPatients() {
  const value = getWebStorageValue(STORAGE_KEYS.patients) || [];
  return Array.isArray(value) ? value : [];
}

function setWebPatients(rows) {
  setWebStorageValue(STORAGE_KEYS.patients, rows);
}

function getWebVisits() {
  const value = getWebStorageValue(STORAGE_KEYS.visits) || [];
  return Array.isArray(value) ? value : [];
}

function setWebVisits(rows) {
  setWebStorageValue(STORAGE_KEYS.visits, rows);
}

function getWebRiskFlags() {
  const value = getWebStorageValue(STORAGE_KEYS.riskFlags) || [];
  return Array.isArray(value) ? value : [];
}

function setWebRiskFlags(rows) {
  setWebStorageValue(STORAGE_KEYS.riskFlags, rows);
}

function getWebSyncQueue() {
  const value = getWebStorageValue(STORAGE_KEYS.syncQueue) || [];
  return Array.isArray(value) ? value : [];
}

function setWebSyncQueue(rows) {
  setWebStorageValue(STORAGE_KEYS.syncQueue, rows);
}

const MIGRATIONS = [
  {
    version: 1,
    statements: [
      `CREATE TABLE IF NOT EXISTS schema_migrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        version INTEGER NOT NULL UNIQUE,
        applied_at TEXT NOT NULL DEFAULT (datetime('now'))
      );`,
      `CREATE TABLE IF NOT EXISTS auth_state (
        phone TEXT PRIMARY KEY,
        worker_id TEXT NOT NULL,
        name TEXT NOT NULL,
        pin_hash TEXT NOT NULL,
        failed_attempts INTEGER NOT NULL DEFAULT 0,
        locked_until TEXT,
        last_login_at TEXT
      );`,
      `CREATE TABLE IF NOT EXISTS patients (
        id TEXT PRIMARY KEY,
        worker_id TEXT NOT NULL,
        name TEXT NOT NULL,
        age INTEGER,
        village TEXT,
        edd TEXT,
        phone TEXT,
        status TEXT DEFAULT 'active',
        review_status TEXT DEFAULT 'pending',
        review_notes TEXT,
        review_updated_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
      );`,
      `CREATE INDEX IF NOT EXISTS ix_patients_worker_id ON patients (worker_id);`,
      `CREATE INDEX IF NOT EXISTS ix_patients_review_status ON patients (review_status);`,
      `CREATE TABLE IF NOT EXISTS visits (
        id TEXT PRIMARY KEY,
        patient_id TEXT NOT NULL,
        worker_id TEXT NOT NULL,
        visit_date TEXT NOT NULL,
        systolic_bp INTEGER,
        diastolic_bp INTEGER,
        blood_sugar INTEGER,
        body_temp_c REAL,
        heart_rate INTEGER,
        created_locally_at TEXT NOT NULL,
        synced_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      );`,
      `CREATE INDEX IF NOT EXISTS ix_visits_patient_id ON visits (patient_id);`,
      `CREATE INDEX IF NOT EXISTS ix_visits_worker_id ON visits (worker_id);`,
      `CREATE INDEX IF NOT EXISTS ix_visits_visit_date ON visits (visit_date);`,
      `CREATE TABLE IF NOT EXISTS risk_flags (
        id TEXT PRIMARY KEY,
        visit_id TEXT NOT NULL,
        model_risk_level TEXT NOT NULL,
        trend_adjusted_level TEXT NOT NULL,
        trend_reason TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      );`,
      `CREATE INDEX IF NOT EXISTS ix_risk_flags_visit_id ON risk_flags (visit_id);`,
      `CREATE INDEX IF NOT EXISTS ix_risk_flags_model_risk_level ON risk_flags (model_risk_level);`,
      `CREATE TABLE IF NOT EXISTS sync_queue (
        id TEXT PRIMARY KEY,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        payload TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0,
        last_error TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
      );`,
      `CREATE INDEX IF NOT EXISTS ix_sync_queue_status ON sync_queue (status);`,
      `CREATE INDEX IF NOT EXISTS ix_sync_queue_entity_type ON sync_queue (entity_type);`,
    ],
  },
];

export function initializeDatabase() {
  if (isWeb || !db) {
    return null;
  }

  try {
    db.execSync('PRAGMA journal_mode = WAL;');
    db.execSync('PRAGMA foreign_keys = ON;');
    db.execSync(`CREATE TABLE IF NOT EXISTS schema_migrations (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      version INTEGER NOT NULL UNIQUE,
      applied_at TEXT NOT NULL DEFAULT (datetime('now'))
    );`);

    const current = db.getFirstSync('SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations;');
    const currentVersion = Number(current?.version || 0);

    for (const migration of MIGRATIONS) {
      if (migration.version > currentVersion) {
        for (const statement of migration.statements) {
          db.execSync(statement);
        }
        db.runSync('INSERT INTO schema_migrations (version, applied_at) VALUES (?, datetime("now"));', [migration.version]);
      }
    }
  } catch (error) {
    if (__DEV__) {
      console.error('[HerDoc] SQLite init error:', error);
    }
    throw error;
  }

  return db;
}

export function getDatabase() {
  return db;
}

export function isDatabaseSupported() {
  return Boolean(db) && !isWeb;
}

export function getDatabaseVersion() {
  return DATABASE_VERSION;
}

export function getAuthStateByPhone(phone) {
  const normalizedPhone = String(phone || '').trim();
  if (!normalizedPhone) {
    return null;
  }

  if (isWeb) {
    const map = getWebAuthStateMap();
    return map[normalizedPhone] || null;
  }

  if (!db) {
    return null;
  }

  return db.getFirstSync(
    'SELECT phone, worker_id, name, pin_hash, failed_attempts, locked_until, last_login_at FROM auth_state WHERE phone = ?;',
    [normalizedPhone],
  );
}

export function upsertAuthState({ phone, workerId, name, pinHash, failedAttempts = 0, lockedUntil = null, lastLoginAt = null }) {
  const normalizedPhone = String(phone || '').trim();
  if (!normalizedPhone || !workerId || !pinHash) {
    return null;
  }

  if (isWeb) {
    const map = getWebAuthStateMap();
    map[normalizedPhone] = {
      phone: normalizedPhone,
      worker_id: String(workerId),
      name: String(name || 'Worker'),
      pin_hash: String(pinHash),
      failed_attempts: Number(failedAttempts || 0),
      locked_until: lockedUntil || null,
      last_login_at: lastLoginAt || null,
    };
    setWebAuthStateMap(map);
    return map[normalizedPhone];
  }

  if (!db) {
    return null;
  }

  db.runSync(
    `INSERT INTO auth_state (phone, worker_id, name, pin_hash, failed_attempts, locked_until, last_login_at)
     VALUES (?, ?, ?, ?, ?, ?, ?)
     ON CONFLICT(phone) DO UPDATE SET
       worker_id = excluded.worker_id,
       name = excluded.name,
       pin_hash = excluded.pin_hash,
       failed_attempts = excluded.failed_attempts,
       locked_until = excluded.locked_until,
       last_login_at = excluded.last_login_at;`,
    [normalizedPhone, workerId, name, pinHash, failedAttempts, lockedUntil, lastLoginAt],
  );

  return getAuthStateByPhone(normalizedPhone);
}

export function resetAuthFailureState(phone) {
  const normalizedPhone = String(phone || '').trim();
  if (!normalizedPhone) {
    return;
  }

  if (isWeb) {
    const map = getWebAuthStateMap();
    const record = map[normalizedPhone];
    if (!record) {
      return;
    }
    record.failed_attempts = 0;
    record.locked_until = null;
    map[normalizedPhone] = record;
    setWebAuthStateMap(map);
    return;
  }

  if (!db) {
    return;
  }

  db.runSync(
    'UPDATE auth_state SET failed_attempts = 0, locked_until = NULL WHERE phone = ?;',
    [normalizedPhone],
  );
}

export function incrementAuthFailureState(phone) {
  const normalizedPhone = String(phone || '').trim();
  if (!normalizedPhone) {
    return 0;
  }

  if (isWeb) {
    const map = getWebAuthStateMap();
    const record = map[normalizedPhone] || { failed_attempts: 0 };
    const nextAttempts = Number(record.failed_attempts || 0) + 1;
    record.failed_attempts = nextAttempts;
    map[normalizedPhone] = record;
    setWebAuthStateMap(map);
    return nextAttempts;
  }

  if (!db) {
    return 0;
  }

  const current = getAuthStateByPhone(normalizedPhone) || { failed_attempts: 0 };
  const nextAttempts = Number(current.failed_attempts || 0) + 1;
  db.runSync('UPDATE auth_state SET failed_attempts = ? WHERE phone = ?;', [nextAttempts, normalizedPhone]);
  return nextAttempts;
}

export function lockAuthState(phone, lockUntilIso) {
  const normalizedPhone = String(phone || '').trim();
  if (!normalizedPhone) {
    return;
  }

  if (isWeb) {
    const map = getWebAuthStateMap();
    const record = map[normalizedPhone];
    if (!record) {
      return;
    }
    record.locked_until = lockUntilIso;
    record.failed_attempts = 5;
    map[normalizedPhone] = record;
    setWebAuthStateMap(map);
    return;
  }

  if (!db) {
    return;
  }

  db.runSync('UPDATE auth_state SET locked_until = ?, failed_attempts = 5 WHERE phone = ?;', [lockUntilIso, normalizedPhone]);
}

export function insertPatient(patient) {
  const normalized = {
    id: String(patient?.id || ''),
    worker_id: String(patient?.worker_id || ''),
    name: String(patient?.name || '').trim(),
    age: patient?.age == null || patient?.age === '' ? null : Number(patient.age),
    village: String(patient?.village || '').trim(),
    edd: patient?.edd ? String(patient.edd).trim() : null,
    phone: patient?.phone ? String(patient.phone).trim() : null,
    status: patient?.status || 'active',
    review_status: patient?.review_status || 'pending',
    review_notes: patient?.review_notes || null,
    review_updated_at: patient?.review_updated_at || null,
    created_at: patient?.created_at || new Date().toISOString(),
    updated_at: patient?.updated_at || new Date().toISOString(),
  };

  if (!normalized.id || !normalized.worker_id || !normalized.name || !normalized.village || !normalized.edd) {
    return null;
  }

  if (isWeb) {
    const rows = getWebPatients();
    const existingIndex = rows.findIndex((item) => item.id === normalized.id);
    const record = { ...normalized };
    if (existingIndex >= 0) {
      rows[existingIndex] = record;
    } else {
      rows.push(record);
    }
    setWebPatients(rows);
    enqueueSyncItem('patient', record.id, record);
    return record;
  }

  if (!db) {
    return null;
  }

  db.runSync(
    `INSERT INTO patients (id, worker_id, name, age, village, edd, phone, status, review_status, review_notes, review_updated_at, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
     ON CONFLICT(id) DO UPDATE SET
       worker_id = excluded.worker_id,
       name = excluded.name,
       age = excluded.age,
       village = excluded.village,
       edd = excluded.edd,
       phone = excluded.phone,
       status = excluded.status,
       review_status = excluded.review_status,
       review_notes = excluded.review_notes,
       review_updated_at = excluded.review_updated_at,
       updated_at = excluded.updated_at;`,
    [
      normalized.id,
      normalized.worker_id,
      normalized.name,
      normalized.age,
      normalized.village,
      normalized.edd,
      normalized.phone,
      normalized.status,
      normalized.review_status,
      normalized.review_notes,
      normalized.review_updated_at,
      normalized.created_at,
      normalized.updated_at,
    ],
  );

  const saved = getPatientById(normalized.id);
  if (saved) {
    enqueueSyncItem('patient', saved.id, saved);
  }
  return saved;
}

export function getPatientById(id) {
  const patientId = String(id || '');
  if (!patientId) {
    return null;
  }

  if (isWeb) {
    return getWebPatients().find((patient) => patient.id === patientId) || null;
  }

  if (!db) {
    return null;
  }
  return db.getFirstSync('SELECT * FROM patients WHERE id = ?;', [patientId]);
}

export function listAllPatients(workerId) {
  if (isWeb) {
    const patients = getWebPatients();
    const rows = workerId ? patients.filter((patient) => patient.worker_id === String(workerId)) : patients;
    return [...rows].sort((a, b) => String(a.name || '').localeCompare(String(b.name || '')));
  }

  if (!db) {
    return [];
  }
  if (workerId) {
    return db.getAllSync('SELECT * FROM patients WHERE worker_id = ? ORDER BY name ASC;', [String(workerId)]);
  }
  return db.getAllSync('SELECT * FROM patients ORDER BY name ASC;');
}

export function insertVisit(visit) {
  const normalized = {
    id: String(visit?.id || ''),
    patient_id: String(visit?.patient_id || ''),
    worker_id: String(visit?.worker_id || ''),
    visit_date: String(visit?.visit_date || new Date().toISOString().split('T')[0]).trim(),
    systolic_bp: visit?.systolic_bp == null || visit?.systolic_bp === '' ? null : Number(visit.systolic_bp),
    diastolic_bp: visit?.diastolic_bp == null || visit?.diastolic_bp === '' ? null : Number(visit.diastolic_bp),
    blood_sugar: visit?.blood_sugar == null || visit?.blood_sugar === '' ? null : Number(visit.blood_sugar),
    body_temp_c: visit?.body_temp_c == null || visit?.body_temp_c === '' ? null : Number(visit.body_temp_c),
    heart_rate: visit?.heart_rate == null || visit?.heart_rate === '' ? null : Number(visit.heart_rate),
    created_locally_at: String(visit?.created_locally_at || new Date().toISOString()),
    synced_at: visit?.synced_at || null,
    created_at: visit?.created_at || new Date().toISOString(),
  };

  if (!normalized.id || !normalized.patient_id || !normalized.worker_id) {
    return null;
  }

  if (isWeb) {
    const rows = getWebVisits();
    const existingIndex = rows.findIndex((item) => item.id === normalized.id);
    const record = { ...normalized };
    if (existingIndex >= 0) {
      rows[existingIndex] = record;
    } else {
      rows.push(record);
    }
    setWebVisits(rows);
    enqueueSyncItem('visit', record.id, record);
    return record;
  }

  if (!db) {
    return null;
  }

  db.runSync(
    `INSERT INTO visits (id, patient_id, worker_id, visit_date, systolic_bp, diastolic_bp, blood_sugar, body_temp_c, heart_rate, created_locally_at, synced_at, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
     ON CONFLICT(id) DO UPDATE SET
       patient_id = excluded.patient_id,
       worker_id = excluded.worker_id,
       visit_date = excluded.visit_date,
       systolic_bp = excluded.systolic_bp,
       diastolic_bp = excluded.diastolic_bp,
       blood_sugar = excluded.blood_sugar,
       body_temp_c = excluded.body_temp_c,
       heart_rate = excluded.heart_rate,
       created_locally_at = excluded.created_locally_at,
       synced_at = excluded.synced_at;`,
    [
      normalized.id,
      normalized.patient_id,
      normalized.worker_id,
      normalized.visit_date,
      normalized.systolic_bp,
      normalized.diastolic_bp,
      normalized.blood_sugar,
      normalized.body_temp_c,
      normalized.heart_rate,
      normalized.created_locally_at,
      normalized.synced_at,
      normalized.created_at,
    ],
  );

  const saved = getVisitById(normalized.id);
  if (saved) {
    enqueueSyncItem('visit', saved.id, saved);
  }
  return saved;
}

export function getVisitById(id) {
  const visitId = String(id || '');
  if (!visitId) {
    return null;
  }

  if (isWeb) {
    return getWebVisits().find((visit) => visit.id === visitId) || null;
  }

  if (!db) {
    return null;
  }
  return db.getFirstSync('SELECT * FROM visits WHERE id = ?;', [visitId]);
}

export function listPatientVisits(patientId) {
  const pid = String(patientId || '');
  if (!pid) {
    return [];
  }

  if (isWeb) {
    const visits = getWebVisits().filter((v) => v.patient_id === pid);
    return [...visits].sort((a, b) => {
      const dateA = new Date(a.visit_date || a.created_locally_at || 0).getTime();
      const dateB = new Date(b.visit_date || b.created_locally_at || 0).getTime();
      return dateB - dateA;
    });
  }

  if (!db) {
    return [];
  }
  return db.getAllSync(
    'SELECT * FROM visits WHERE patient_id = ? ORDER BY visit_date DESC, created_locally_at DESC;',
    [pid],
  );
}

export function insertRiskFlag(flag) {
  const normalized = {
    id: String(flag?.id || ''),
    visit_id: String(flag?.visit_id || ''),
    model_risk_level: String(flag?.model_risk_level || 'yellow').toLowerCase(),
    trend_adjusted_level: String(flag?.trend_adjusted_level || flag?.model_risk_level || 'yellow').toLowerCase(),
    trend_reason: flag?.trend_reason ? String(flag.trend_reason).trim() : null,
    created_at: flag?.created_at || new Date().toISOString(),
  };

  if (!normalized.id || !normalized.visit_id) {
    return null;
  }

  if (isWeb) {
    const flags = getWebRiskFlags();
    const existingIndex = flags.findIndex((item) => item.id === normalized.id);
    const record = { ...normalized };
    if (existingIndex >= 0) {
      flags[existingIndex] = record;
    } else {
      flags.push(record);
    }
    setWebRiskFlags(flags);
    enqueueSyncItem('risk_flag', record.id, record);
    return record;
  }

  if (!db) {
    return null;
  }

  db.runSync(
    `INSERT INTO risk_flags (id, visit_id, model_risk_level, trend_adjusted_level, trend_reason, created_at)
     VALUES (?, ?, ?, ?, ?, ?)
     ON CONFLICT(id) DO UPDATE SET
       visit_id = excluded.visit_id,
       model_risk_level = excluded.model_risk_level,
       trend_adjusted_level = excluded.trend_adjusted_level,
       trend_reason = excluded.trend_reason;`,
    [
      normalized.id,
      normalized.visit_id,
      normalized.model_risk_level,
      normalized.trend_adjusted_level,
      normalized.trend_reason,
      normalized.created_at,
    ],
  );

  const saved = getRiskFlagById(normalized.id);
  if (saved) {
    enqueueSyncItem('risk_flag', saved.id, saved);
  }
  return saved;
}

export function getRiskFlagById(id) {
  const flagId = String(id || '');
  if (!flagId) {
    return null;
  }

  if (isWeb) {
    return getWebRiskFlags().find((flag) => flag.id === flagId) || null;
  }

  if (!db) {
    return null;
  }
  return db.getFirstSync('SELECT * FROM risk_flags WHERE id = ?;', [flagId]);
}

export function getRiskFlagByVisitId(visitId) {
  const vid = String(visitId || '');
  if (!vid) {
    return null;
  }

  if (isWeb) {
    return getWebRiskFlags().find((flag) => flag.visit_id === vid) || null;
  }

  if (!db) {
    return null;
  }
  return db.getFirstSync('SELECT * FROM risk_flags WHERE visit_id = ?;', [vid]);
}

export function getRiskFlagsByVisitIds(visitIds) {
  if (!visitIds?.length) {
    return [];
  }

  if (isWeb) {
    const flags = getWebRiskFlags();
    return flags.filter((f) => visitIds.includes(f.visit_id));
  }

  if (!db) {
    return [];
  }
  const placeholders = visitIds.map(() => '?').join(', ');
  return db.getAllSync(`SELECT * FROM risk_flags WHERE visit_id IN (${placeholders});`, visitIds);
}

export function getAllSyncQueueEntries(status) {
  if (isWeb || !db) {
    return [];
  }
  if (status) {
    return db.getAllSync(
      'SELECT id, entity_type, entity_id, payload, status, attempts, last_error, created_at, updated_at FROM sync_queue WHERE status = ? ORDER BY created_at ASC;',
      [status],
    );
  }
  return db.getAllSync(
    'SELECT id, entity_type, entity_id, payload, status, attempts, last_error, created_at, updated_at FROM sync_queue ORDER BY created_at ASC;',
  );
}

export function enqueueSyncItem(entityType, entityId, payload) {
  const normalizedType = String(entityType || 'unknown').toLowerCase();
  const normalizedId = String(entityId || '');
  const id = `${normalizedType}-${normalizedId}-${Date.now()}`;
  const payloadStr = typeof payload === 'string' ? payload : JSON.stringify(payload ?? null);

  if (isWeb) {
    const q = getWebSyncQueue();
    // Idempotent: avoid queuing exact same pending item twice
    const existing = q.find((it) => it.entity_type === normalizedType && it.entity_id === normalizedId && it.status === 'pending');
    if (existing) {
      existing.payload = payloadStr;
      existing.updated_at = new Date().toISOString();
      setWebSyncQueue(q);
      return existing.id;
    }
    const item = {
      id,
      entity_type: normalizedType,
      entity_id: normalizedId,
      payload: payloadStr,
      status: 'pending',
      attempts: 0,
      last_error: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    q.push(item);
    setWebSyncQueue(q);
    return id;
  }

  if (!db) {
    return null;
  }

  // Idempotent check
  const existing = db.getFirstSync(
    "SELECT id FROM sync_queue WHERE entity_type = ? AND entity_id = ? AND status = 'pending';",
    [normalizedType, normalizedId],
  );
  if (existing) {
    db.runSync(
      'UPDATE sync_queue SET payload = ?, updated_at = datetime("now") WHERE id = ?;',
      [payloadStr, existing.id],
    );
    return existing.id;
  }

  db.runSync(
    'INSERT INTO sync_queue (id, entity_type, entity_id, payload, status, attempts, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 0, datetime("now"), datetime("now"));',
    [id, normalizedType, normalizedId, payloadStr, 'pending'],
  );
  return id;
}

export function getPendingSyncItemsCount() {
  if (isWeb) {
    return getWebSyncQueue().filter((item) => item.status === 'pending').length;
  }
  if (!db) {
    return 0;
  }
  const row = db.getFirstSync("SELECT COUNT(*) AS cnt FROM sync_queue WHERE status = 'pending';");
  return Number(row?.cnt || 0);
}

export function getPendingSyncQueueEntries() {
  if (isWeb) {
    return getWebSyncQueue().filter((item) => item.status === 'pending');
  }
  if (!db) {
    return [];
  }
  return db.getAllSync(
    "SELECT id, entity_type, entity_id, payload, status, attempts, last_error, created_at, updated_at FROM sync_queue WHERE status = 'pending' ORDER BY created_at ASC;",
  );
}

export function markSyncQueueItemsCompleted(queueIds = []) {
  if (!queueIds?.length) {
    return;
  }
  if (isWeb) {
    const q = getWebSyncQueue();
    q.forEach((item) => {
      if (queueIds.includes(item.id)) {
        item.status = 'synced';
        item.updated_at = new Date().toISOString();
      }
    });
    setWebSyncQueue(q);
    return;
  }
  if (!db) {
    return;
  }
  const placeholders = queueIds.map(() => '?').join(', ');
  db.runSync(
    `UPDATE sync_queue SET status = 'synced', updated_at = datetime('now') WHERE id IN (${placeholders});`,
    queueIds,
  );
}

export function markSyncQueueItemFailed(id, errorMessage) {
  if (!id) {
    return;
  }
  if (isWeb) {
    const q = getWebSyncQueue();
    const item = q.find((it) => it.id === id);
    if (item) {
      item.attempts = Number(item.attempts || 0) + 1;
      item.last_error = String(errorMessage || 'Sync failed');
      item.updated_at = new Date().toISOString();
      setWebSyncQueue(q);
    }
    return;
  }
  if (!db) {
    return;
  }
  db.runSync(
    'UPDATE sync_queue SET attempts = attempts + 1, last_error = ?, updated_at = datetime("now") WHERE id = ?;',
    [String(errorMessage || 'Sync failed'), String(id)],
  );
}

export function applyServerPatientReview({ patientId, status, notes, reviewedAt }) {
  const pid = String(patientId || '');
  if (!pid) {
    return;
  }
  if (isWeb) {
    const patients = getWebPatients();
    const p = patients.find((item) => item.id === pid);
    if (p) {
      p.review_status = status || p.review_status;
      p.review_notes = notes !== undefined ? notes : p.review_notes;
      p.review_updated_at = reviewedAt || new Date().toISOString();
      setWebPatients(patients);
    }
    return;
  }
  if (!db) {
    return;
  }
  db.runSync(
    'UPDATE patients SET review_status = ?, review_notes = ?, review_updated_at = ?, updated_at = datetime("now") WHERE id = ?;',
    [status || 'pending', notes || null, reviewedAt || new Date().toISOString(), pid],
  );
}

export function getLastSyncedAt() {
  if (isWeb) {
    return getWebStorageValue(STORAGE_KEYS.lastSyncedAt) || null;
  }
  return null;
}

export function setLastSyncedAt(timestamp) {
  if (isWeb) {
    setWebStorageValue(STORAGE_KEYS.lastSyncedAt, timestamp);
  }
}

export function setSyncQueueStatus(id, status, { lastError = null } = {}) {
  if (isWeb || !db) {
    return;
  }
  db.runSync(
    'UPDATE sync_queue SET status = ?, last_error = ?, updated_at = datetime("now"), attempts = attempts + CASE WHEN ? = 1 THEN 1 ELSE 0 END WHERE id = ?;',
    [String(status || 'pending'), lastError ? String(lastError) : null, lastError ? 1 : 0, String(id || '')],
  );
}

