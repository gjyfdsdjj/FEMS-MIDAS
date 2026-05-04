import os
import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "telemetry_buffer.db"


class LocalBuffer:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.getenv(
            "EDGE_BUFFER_DB",
            str(DEFAULT_DB_PATH),
        )
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS telemetry_buffer (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    factory_id    INTEGER NOT NULL,
                    node_id       TEXT    NOT NULL,
                    temperature_c REAL    NOT NULL,
                    humidity_pct  REAL    NOT NULL,
                    measured_at   TEXT    NOT NULL
                )
            """)

    def save(self, payload: dict) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO telemetry_buffer
                    (factory_id, node_id, temperature_c, humidity_pct, measured_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    payload["factory_id"],
                    payload["node_id"],
                    payload["temperature_c"],
                    payload["humidity_pct"],
                    payload["timestamp"],
                ),
            )

    def get_all(self) -> list[dict]:
        """버퍼의 모든 레코드를 읽기만 함 (삭제 안 함)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT id, factory_id, node_id, temperature_c, humidity_pct, measured_at "
                "FROM telemetry_buffer ORDER BY id"
            )
            rows = cursor.fetchall()
        return [
            {
                "_id":           row[0],
                "factory_id":    row[1],
                "node_id":       row[2],
                "temperature_c": row[3],
                "humidity_pct":  row[4],
                "timestamp":     row[5],
            }
            for row in rows
        ]

    def delete(self, ids: list[int]) -> None:
        """ACK 확인 후 해당 레코드 삭제."""
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"DELETE FROM telemetry_buffer WHERE id IN ({placeholders})", ids
            )

    def count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM telemetry_buffer").fetchone()[0]
