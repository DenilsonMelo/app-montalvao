
# logic.py — Regras de negócio
from typing import List, Dict, Any, Tuple
from datetime import date, timedelta
import sqlite3

def get_buckets(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    cur = conn.execute("""
        SELECT id, name, kind, priority_pre, percentage, active
        FROM accounts
        WHERE kind='bucket'
        ORDER BY id ASC;
    """)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]

def list_buckets(conn: sqlite3.Connection):
    cur = conn.execute("""
        SELECT id, name
        FROM accounts
        WHERE kind='bucket' AND active=1
        ORDER BY id ASC;
    """)
    return cur.fetchall()

def save_buckets(conn: sqlite3.Connection, buckets: List[Dict[str, Any]]):
    for b in buckets:
        if b.get("id"):
            conn.execute("""
                UPDATE accounts
                   SET name=?, kind='bucket', priority_pre=?, percentage=?, active=?
                 WHERE id=?;
            """, (b["name"], int(b.get("priority_pre",0)), float(b.get("percentage",0) or 0), int(b.get("active",1)), int(b["id"])))
        else:
            conn.execute("""
                INSERT INTO accounts (name, kind, priority_pre, percentage, active)
                VALUES (?, 'bucket', ?, ?, ?);
            """, (b["name"], int(b.get("priority_pre",0)), float(b.get("percentage",0) or 0), int(b.get("active",1))))
    conn.commit()

def delete_buckets_not_in(conn: sqlite3.Connection, keep_ids: List[int]):
    q = "DELETE FROM accounts WHERE kind='bucket' AND id NOT IN (" + ",".join("?"*len(keep_ids)) + ")" if keep_ids else "DELETE FROM accounts WHERE kind='bucket'"
    conn.execute(q, keep_ids if keep_ids else [])
    conn.commit()

def add_transaction(conn: sqlite3.Connection, tx: Dict[str, Any]) -> int:
    cur = conn.execute("""
        INSERT INTO transactions (date, description, t_type, value, account_id, bucket_id, goal_id, store)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        tx["date"],
        tx.get("description",""),
        tx["t_type"],
        float(tx["value"]),
        tx.get("account_id"),
        tx.get("bucket_id"),
        tx.get("goal_id"),
        tx.get("store","")
    ))
    conn.commit()
    return cur.lastrowid

def delete_transactions_by_ids(conn: sqlite3.Connection, ids: List[int]):
    if not ids: 
        return
    q = "DELETE FROM transactions WHERE id IN (" + ",".join("?"*len(ids)) + ")"
    conn.execute(q, ids)
    conn.commit()

# ---- batches ----
def create_batch(conn: sqlite3.Connection, kind: str, note: str = "") -> int:
    cur = conn.execute("INSERT INTO batches (created_at, kind, note) VALUES (?, ?, ?);", (date.today().isoformat(), kind, note))
    conn.commit()
    return cur.lastrowid

def add_batch_item(conn: sqlite3.Connection, batch_id: int, tx_id: int):
    conn.execute("INSERT INTO batch_items (batch_id, tx_id) VALUES (?, ?);", (batch_id, tx_id))
    conn.commit()

def undo_batch(conn: sqlite3.Connection, batch_id: int):
    cur = conn.execute("SELECT tx_id FROM batch_items WHERE batch_id=?;", (batch_id,))
    ids = [r[0] for r in cur.fetchall()]
    if ids:
        delete_transactions_by_ids(conn, ids)
    conn.execute("DELETE FROM batch_items WHERE batch_id=?;", (batch_id,))
    conn.execute("DELETE FROM batches WHERE id=?;", (batch_id,))
    conn.commit()

# ---- saldos/totais ----
def balances_by_bucket(conn: sqlite3.Connection):
    try:
        cur = conn.execute("SELECT bucket_id AS id, bucket AS name, saldo FROM v_balances_by_bucket;")
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception:
        cur = conn.execute("""
            SELECT a.id, a.name,
                   COALESCE(SUM(CASE WHEN t.t_type='in' THEN t.value ELSE 0 END),0)
                 + COALESCE(SUM(CASE WHEN t.t_type='transfer' THEN t.value ELSE 0 END),0)
                 - COALESCE(SUM(CASE WHEN t.t_type='out' THEN t.value ELSE 0 END),0) AS saldo
            FROM accounts a
            LEFT JOIN transactions t ON t.bucket_id = a.id
            WHERE a.kind='bucket' AND a.active=1
            GROUP BY a.id, a.name
            ORDER BY a.id ASC;
        """)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

def totals_by_day(conn: sqlite3.Connection, days: int = 30):
    since = (date.today() - timedelta(days=days)).isoformat()
    try:
        cur = conn.execute("SELECT date, entradas, saidas, liquido FROM v_totals_by_day WHERE date >= ? ORDER BY date ASC;", (since,))
    except Exception:
        cur = conn.execute("""
            WITH base AS (
                SELECT date, 
                       SUM(CASE WHEN t_type='in' THEN value ELSE 0 END) AS entradas,
                       SUM(CASE WHEN t_type='out' THEN value ELSE 0 END) AS saidas
                FROM transactions
                WHERE date >= ?
                GROUP BY date
            )
            SELECT date, entradas, saidas, (entradas - saidas) AS liquido
            FROM base
            ORDER BY date ASC;
        """, (since,))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]

def totals_by_month(conn: sqlite3.Connection):
    cur = conn.execute("""
        WITH agg AS (
            SELECT substr(date,1,7) AS ym,
                   SUM(CASE WHEN t_type='in' THEN value ELSE 0 END) AS entradas,
                   SUM(CASE WHEN t_type='out' THEN value ELSE 0 END) AS saidas
            FROM transactions
            GROUP BY ym
        )
        SELECT ym, entradas, saidas, (entradas - saidas) AS liquido
        FROM agg
        ORDER BY ym ASC;
    """)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]

# ---- distribuição diária ----
def _round2(x: float) -> float:
    return float(f"{x:.2f}")

def distribute_daily(conn: sqlite3.Connection, value: float, date_str: str, description: str, store: str) -> Tuple[list, int]:
    # lista de baldes ativos
    cur = conn.execute("""
        SELECT id, name, priority_pre, percentage
        FROM accounts
        WHERE kind='bucket' AND active=1
        ORDER BY id ASC;
    """)
    rows = cur.fetchall()
    if not rows:
        return ([], None)

    # separa prioritários e não prior
    pri  = [r for r in rows if r[2] == 1]
    npri = [r for r in rows if r[2] == 0]

    allocations = []
    # 1) aloca prioritários em cima do total
    pri_sum = 0.0
    for (bid, name, _, pct) in pri:
        amt = _round2(value * float(pct or 0))
        pri_sum += amt
        allocations.append([bid, name, amt])
    pri_sum = _round2(pri_sum)

    # 2) restante para não prioritários proporcionalmente
    remaining = max(0.0, _round2(value - pri_sum))
    npri_total_pct = sum(float(p or 0) for (_, _, _, p) in npri)
    if remaining > 0 and npri and npri_total_pct > 0:
        base = []
        acc = 0.0
        for i, (bid, name, _, pct) in enumerate(npri):
            if i == len(npri) - 1:
                amt = _round2(remaining - acc)
            else:
                frac = float(pct or 0) / float(npri_total_pct)
                amt = _round2(remaining * frac)
                acc = _round2(acc + amt)
            base.append([bid, name, amt])
        allocations.extend(base)

    # grava transações 'in' e cria batch para desfazer
    batch_id = create_batch(conn, "distribute", note=f"Distribuição de {value} em {date_str}")
    for (bid, name, amt) in allocations:
        if amt <= 0: 
            continue
        tx_id = add_transaction(conn, {
            "date": date_str,
            "description": description or f"Entrada distribuída — {name}",
            "t_type": "in",
            "value": amt,
            "bucket_id": bid,
            "store": store or ""
        })
        add_batch_item(conn, batch_id, tx_id)

    # retorno amigável
    out = [{"bucket_id": bid, "bucket": name, "value": amt} for (bid, name, amt) in allocations if amt > 0]
    return (out, batch_id)

# ---- objetivos ----
def goals_with_scores(conn: sqlite3.Connection, strategy: str = "avalanche"):
    cur = conn.execute("""
        SELECT id, name, goal_type, cost, monthly_relief, interest_pa, priority_weight, color
        FROM goals;
    """)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    def score(row):
        if strategy == "avalanche":
            return (row["monthly_relief"] or 0) / (row["cost"] or 1e-9)
        if strategy == "snowball":
            return -(row["cost"] or 0)
        return row.get("priority_weight") or 0

    for r in rows:
        r["score"] = score(r)
    rows.sort(key=lambda x: x["score"], reverse=True)
    return rows

def attack_ready(conn: sqlite3.Connection):
    cur = conn.execute("""
        SELECT a.id FROM accounts a 
        WHERE a.kind='bucket' AND a.name='Nu PF Ataque' AND a.active=1
        LIMIT 1;
    """)
    row = cur.fetchone()
    if not row:
        return (None, 0.0, None)

    bucket_id = row[0]

    cur = conn.execute("""
        SELECT 
          COALESCE(SUM(CASE WHEN t_type='in' THEN value ELSE 0 END),0)
        + COALESCE(SUM(CASE WHEN t_type='transfer' THEN value ELSE 0 END),0)
        - COALESCE(SUM(CASE WHEN t_type='out' THEN value ELSE 0 END),0) AS saldo
        FROM transactions WHERE bucket_id=?;
    """, (bucket_id,))
    saldo = cur.fetchone()[0] or 0.0

    goals = goals_with_scores(conn, "avalanche")
    if not goals:
        return (None, saldo, None)

    best = goals[0]
    return (best["name"], saldo, best["cost"])

def upsert_goal(conn: sqlite3.Connection, name: str, goal_type: str, cost: float, monthly_relief: float, color: str, interest_pa: float = 0.0, priority_weight: float = 0.0):
    cur = conn.execute("SELECT id FROM goals WHERE name = ?;", (name,))
    row = cur.fetchone()
    if row:
        conn.execute("""
            UPDATE goals
            SET goal_type=?, cost=?, monthly_relief=?, color=?, interest_pa=?, priority_weight=?
            WHERE id=?;
        """, (goal_type, float(cost), float(monthly_relief), color, float(interest_pa), float(priority_weight), int(row[0])))
    else:
        conn.execute("""
            INSERT INTO goals (name, goal_type, cost, monthly_relief, color, interest_pa, priority_weight)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (name, goal_type, float(cost), float(monthly_relief), color, float(interest_pa), float(priority_weight)))
    conn.commit()
