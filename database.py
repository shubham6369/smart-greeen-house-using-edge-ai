"""
database.py - Simple SQLite Local Storage for Smart Greenhouse.
Stores sensor telemetry, actuator operations, and alerts permanently on the laptop.
Easy to explain to your teacher: standard SQLite with parameterized SQL queries.
"""

import sqlite3
import pandas as pd
from datetime import datetime
from pathlib import Path

# Database file path
DB_DIR = Path(__file__).resolve().parent / "data"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "greenhouse.db"

def get_connection():
    """Create a thread-safe connection to local SQLite database."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables on first launch."""
    with get_connection() as conn:
        # Table 1: Sensor telemetry history
        conn.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                temperature REAL,
                humidity REAL,
                soil_moisture REAL,
                light_lux REAL,
                is_valid INTEGER DEFAULT 1,
                scenario TEXT DEFAULT 'NORMAL',
                source TEXT DEFAULT 'simulated'
            )
        """)
        # Ensure 'source' column exists if upgrading from earlier version
        try:
            conn.execute("ALTER TABLE readings ADD COLUMN source TEXT DEFAULT 'simulated'")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Table 2: Automation events and alerts
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                subsystem TEXT NOT NULL,
                action TEXT NOT NULL,
                message TEXT NOT NULL
            )
        """)
        conn.commit()

def save_reading(temperature, humidity, soil_moisture, light_lux, is_valid=True, scenario="NORMAL", source="simulated"):
    """Insert a new environmental reading with explicit source attribution."""
    ts = datetime.now().isoformat()
    with get_connection() as conn:
        cur = conn.execute("""
            INSERT INTO readings (timestamp, temperature, humidity, soil_moisture, light_lux, is_valid, scenario, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ts, temperature, humidity, soil_moisture, light_lux, 1 if is_valid else 0, scenario, source))
        conn.commit()
        return cur.lastrowid

def log_event(subsystem, action, message):
    """Log an actuator trigger, mode change, or alert."""
    ts = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO events (timestamp, subsystem, action, message)
            VALUES (?, ?, ?, ?)
        """, (ts, subsystem, action, message))
        conn.commit()

def get_recent_readings(limit=100):
    """Fetch recent sensor readings as a Pandas DataFrame for Plotly charts."""
    with get_connection() as conn:
        df = pd.read_sql_query("""
            SELECT timestamp, temperature, humidity, soil_moisture, light_lux, is_valid, scenario, source
            FROM readings
            ORDER BY id DESC
            LIMIT ?
        """, conn, params=(limit,))
        if not df.empty:
            df = df.iloc[::-1].reset_index(drop=True)  # Chronological order
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df

def get_recent_events(limit=20):
    """Fetch recent automation and actuator events."""
    with get_connection() as conn:
        cur = conn.execute("""
            SELECT timestamp, subsystem, action, message
            FROM events
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cur.fetchall()]

# Auto-initialize on import
init_db()
