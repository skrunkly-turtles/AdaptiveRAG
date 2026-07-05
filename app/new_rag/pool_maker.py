"""
This Python file sorts the data logged in generator.py into pools as defined in the data folder.
It is all deterministic:
(1) A large raw data pool
(2) Pools specified for each category
(3) A large file of summaries/trends/statistics.
"""

import asyncio
import aiosqlite
import os
from datetime import datetime
from models import Data

DB_PATH = 'vitals.db'

async def _init_db(db: aiosqlite.Connection) -> None:
    """Creates the unified tables and adds critical lookup indexes."""
    await db.execute("PRAGMA journal_mode=WAL")
    
    # 1. Consolidated table handles all metrics cleanly in single rows
    await db.execute("""
        CREATE TABLE IF NOT EXISTS all_logs (
            time      TEXT,
            hr        INTEGER,
            o2        REAL,
            elevation REAL,
            temp      REAL
        )
    """)
    
    # CRITICAL INDEX: Ensures your get_data function runs instantly!
    await db.execute("CREATE INDEX IF NOT EXISTS idx_logs_time ON all_logs(time);")
    
    await db.execute("""
        CREATE TABLE IF NOT EXISTS summaries (
            metric TEXT PRIMARY KEY,
            num    INTEGER,
            avg    REAL,
            min    REAL,
            max    REAL,
            med    REAL
        )
    """)
    await db.commit()

async def clear_db() -> None:
    """Clears the database safely on startup."""
    os.makedirs('data', exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await _init_db(db)
        await db.execute("DELETE FROM all_logs")
        await db.execute("DELETE FROM summaries")
        await db.commit()
        print("Database initialized and cleared.")

async def log_reading(db: aiosqlite.Connection, reading: Data) -> None:
    """Inserts the unified row into the database using an active connection."""
    time_str = reading.time.isoformat() if isinstance(reading.time, datetime) else str(reading.time)
    await db.execute(
        "INSERT INTO all_logs (time, hr, o2, elevation, temp) VALUES (?, ?, ?, ?, ?)",
        (time_str, reading.hr, reading.o2, reading.elevation, reading.temp)
    )

async def calc_summaries(db: aiosqlite.Connection) -> None:
    """
    Computes updated statistics efficiently. SQLite handles count/avg/min/max, 
    and we pull a heavily optimized sub-query purely for calculating the median.
    """
    for metric in ("hr", "o2", "elevation", "temp"):
        # 1. Let SQLite process the bulk heavy lifting instantly
        async with db.execute(f"""
            SELECT COUNT({metric}), AVG({metric}), MIN({metric}), MAX({metric}) 
            FROM all_logs WHERE {metric} IS NOT NULL
        """) as cursor:
            row = await cursor.fetchone()
            if not row or row[0] == 0:
                continue
            num, avg, mn, mx = row

        # 2. Optimized Median: fetch ONLY the middle row(s) instead of all rows
        # We order them and use LIMIT/OFFSET to jump straight to the middle value
        mid_index = num // 2
        if num % 2 == 1:
            query = f"SELECT {metric} FROM all_logs WHERE {metric} IS NOT NULL ORDER BY {metric} ASC LIMIT 1 OFFSET {mid_index}"
            async with db.execute(query) as cursor:
                res = await cursor.fetchone()
                med = res[0] if res else 0
        else:
            query = f"SELECT {metric} FROM all_logs WHERE {metric} IS NOT NULL ORDER BY {metric} ASC LIMIT 2 OFFSET {mid_index - 1}"
            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()
                med = (rows[0][0] + rows[1][0]) / 2 if len(rows) == 2 else 0

        # 3. Save calculations back to database
        await db.execute("""
            INSERT INTO summaries (metric, num, avg, min, max, med)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(metric) DO UPDATE SET
                num = excluded.num,
                avg = excluded.avg,
                min = excluded.min,
                max = excluded.max,
                med = excluded.med
        """, (metric, num, round(avg, 2), round(mn, 2), round(mx, 2), round(med, 2)))

async def process_incoming(data: dict) -> None:
    """
    Process incoming data packets smoothly every 2 seconds.
    Uses a single connection to completely avoid write lock errors.
    """
    new_reading = Data(**data)
    
    # Open ONE connection for the entire request cycle
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        
        # Log the data point and update summaries sequentially in the same transaction
        await log_reading(db, new_reading)
        await calc_summaries(db)
        
        await db.commit()