import sqlite3, os
import config

DB_PATH = os.path.join(config.DATA_DIR, "signals.db")

def init_db():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS signals(
            ts TEXT,
            coin_id TEXT,
            signal TEXT,
            price REAL,
            stop REAL,
            target REAL,
            rr REAL,
            expected_return_pct REAL,
            ema200 REAL,
            rsi14 REAL,
            atr14 REAL
        )
    """)
    conn.commit()
    conn.close()

def insert_signal(s):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO signals VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        s["timestamp"], s["coin_id"], s["signal"], s["price"], s["stop"],
        s["target"], s["rr"], s["expected_return_pct"], s["ema200"],
        s["rsi14"], s["atr14"]
    ))
    conn.commit()
    conn.close()
