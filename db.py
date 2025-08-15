
# db.py — SQLite engine + PRAGMAs, constraints, índices, views e seed dos baldes/dues
from sqlalchemy import create_engine
import sqlite3
from datetime import date, timedelta

DB_PATH = "finance.db"
ENGINE = create_engine(f"sqlite:///{DB_PATH}", future=True)

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    conn.execute("PRAGMA cache_size = -20000;")
    return conn

def init_db():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL CHECK(kind IN ('bucket')),
            priority_pre INTEGER DEFAULT 0 CHECK(priority_pre IN (0,1)),
            percentage REAL DEFAULT 0 CHECK(percentage >= 0 AND percentage <= 1),
            active INTEGER DEFAULT 1 CHECK(active IN (0,1))
        );
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            goal_type TEXT NOT NULL CHECK(goal_type IN ('debt','savings')),
            cost REAL DEFAULT 0 CHECK(cost >= 0),
            monthly_relief REAL DEFAULT 0 CHECK(monthly_relief >= 0),
            interest_pa REAL DEFAULT 0 CHECK(interest_pa >= 0),
            priority_weight REAL DEFAULT 0,
            color TEXT
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            description TEXT,
            t_type TEXT NOT NULL CHECK(t_type IN ('in','out','transfer')),
            value REAL NOT NULL CHECK(value >= 0),
            account_id INTEGER,
            bucket_id INTEGER,
            goal_id INTEGER,
            store TEXT,
            FOREIGN KEY(bucket_id) REFERENCES accounts(id) ON DELETE SET NULL,
            FOREIGN KEY(goal_id)   REFERENCES goals(id)    ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS dues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            due_date TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount >= 0),
            kind TEXT,
            note TEXT
        );
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS batches (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          created_at TEXT NOT NULL,
          kind TEXT NOT NULL,
          note TEXT
        );
        CREATE TABLE IF NOT EXISTS batch_items (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          batch_id INTEGER NOT NULL,
          tx_id INTEGER NOT NULL,
          FOREIGN KEY(batch_id) REFERENCES batches(id) ON DELETE CASCADE,
          FOREIGN KEY(tx_id)    REFERENCES transactions(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(date);
        CREATE INDEX IF NOT EXISTS idx_tx_bucket ON transactions(bucket_id, date);
        CREATE INDEX IF NOT EXISTS idx_accounts_active ON accounts(active);
        CREATE INDEX IF NOT EXISTS idx_goals_name ON goals(name);
        CREATE VIEW IF NOT EXISTS v_balances_by_bucket AS
        SELECT a.id AS bucket_id, a.name AS bucket,
               COALESCE(SUM(CASE WHEN t.t_type='in'       THEN t.value ELSE 0 END),0)
             + COALESCE(SUM(CASE WHEN t.t_type='transfer' THEN t.value ELSE 0 END),0)
             - COALESCE(SUM(CASE WHEN t.t_type='out'      THEN t.value ELSE 0 END),0) AS saldo
        FROM accounts a
        LEFT JOIN transactions t ON t.bucket_id = a.id
        WHERE a.kind='bucket' AND a.active=1
        GROUP BY a.id, a.name;
        CREATE VIEW IF NOT EXISTS v_totals_by_day AS
        SELECT date,
               SUM(CASE WHEN t_type='in'  THEN value ELSE 0 END) AS entradas,
               SUM(CASE WHEN t_type='out' THEN value ELSE 0 END) AS saidas,
               SUM(CASE WHEN t_type='in'  THEN value ELSE 0 END)
             - SUM(CASE WHEN t_type='out' THEN value ELSE 0 END) AS liquido
        FROM transactions
        GROUP BY date;
        """)
        # Seed baldes: só se não existir nenhum
        cur.execute("SELECT COUNT(*) FROM accounts WHERE kind='bucket';")
        if (cur.fetchone() or [0])[0] == 0:
            buckets = [
                ("Dízimo", "bucket", 1, 0.10, 1),
                ("OPEX", "bucket", 0, 0.60, 1),
                ("Empréstimos", "bucket", 0, 0.20, 1),
                ("NuPJ Cartões", "bucket", 0, 0.15, 1),
                ("Nu PF Ataque", "bucket", 0, 0.05, 1),
            ]
            cur.executemany("""
                INSERT INTO accounts (name, kind, priority_pre, percentage, active)
                VALUES (?, ?, ?, ?, ?);
            """, buckets)
        # Dues exemplos (editáveis)
        cur.execute("SELECT COUNT(*) FROM dues;")
        if (cur.fetchone() or [0])[0] == 0:
            today = date.today()
            dues = [
                ("Energia", (today + timedelta(days=5)).isoformat(), 280.00, "conta", "Conta de luz"),
                ("Água", (today + timedelta(days=8)).isoformat(), 120.00, "conta", "Conta de água"),
            ]
            cur.executemany("""
                INSERT INTO dues (name, due_date, amount, kind, note)
                VALUES (?, ?, ?, ?, ?);
            """, dues)
        conn.commit()
