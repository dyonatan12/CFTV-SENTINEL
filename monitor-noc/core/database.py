import os
import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger("cftv.database")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "cftv_sentinel.db")

class Database:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Tabela de Histórico de Alertas
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        device_id TEXT NOT NULL,
                        device_name TEXT NOT NULL,
                        client_id TEXT DEFAULT 'default',
                        client_name TEXT DEFAULT 'Geral',
                        status TEXT NOT NULL, -- 'OFFLINE', 'ONLINE'
                        event_type TEXT NOT NULL, -- 'CAMERA_DOWN', 'CAMERA_RECOVERED', 'NVR_DOWN', 'NVR_RECOVERED'
                        failures INTEGER DEFAULT 0,
                        channel TEXT DEFAULT 'ALL',
                        message TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts (timestamp DESC)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_client ON alerts (client_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_device ON alerts (device_id)")
                conn.commit()
        except Exception as e:
            logger.error(f"Erro ao inicializar banco de dados ({self.db_path}): {e}")

    def log_alert(
        self,
        device_id: str,
        device_name: str,
        status: str,
        event_type: str,
        client_id: str = "default",
        client_name: str = "Geral",
        failures: int = 0,
        channel: str = "ALL",
        message: str = ""
    ) -> int:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO alerts (
                        device_id, device_name, client_id, client_name,
                        status, event_type, failures, channel, message, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    device_id, device_name, client_id, client_name,
                    status, event_type, failures, channel, message,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Erro ao gravar alerta no banco: {e}")
            return -1

    def list_alerts(
        self,
        client_id: Optional[str] = None,
        device_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[List[dict], int]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM alerts WHERE 1=1"
                params = []

                if client_id and client_id != "all":
                    query += " AND client_id = ?"
                    params.append(client_id)
                if device_id:
                    query += " AND device_id = ?"
                    params.append(device_id)
                if status:
                    query += " AND status = ?"
                    params.append(status.upper())

                # Contagem total
                count_query = f"SELECT COUNT(*) as total FROM ({query})"
                cursor.execute(count_query, params)
                total = cursor.fetchone()["total"]

                # Busca paginada
                query += " ORDER BY id DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [dict(r) for r in rows], total
        except Exception as e:
            logger.error(f"Erro ao consultar histórico de alertas: {e}")
            return [], 0

    def clear_old_alerts(self, days: int = 30) -> int:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM alerts 
                    WHERE timestamp < datetime('now', '-' || ? || ' days')
                """, (days,))
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Erro ao limpar alertas antigos: {e}")
            return 0

DB = Database()
