import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Store:
    """Small transactional JSON repository. All service mutations use one transaction."""
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS records (bucket TEXT, id TEXT, value TEXT, PRIMARY KEY(bucket,id))")

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=30)
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def get(self, bucket, key, db=None):
        if db is None:
            with self.transaction() as conn:
                return self.get(bucket, key, conn)
        row = db.execute("SELECT value FROM records WHERE bucket=? AND id=?", (bucket, key)).fetchone()
        if row is None:
            raise KeyError(f"{bucket}/{key}")
        return json.loads(row[0])

    def list(self, bucket, db=None):
        if db is None:
            with self.transaction() as conn:
                return self.list(bucket, conn)
        return [json.loads(row[0]) for row in db.execute("SELECT value FROM records WHERE bucket=? ORDER BY rowid", (bucket,))]

    def put(self, bucket, key, value, db=None, immutable=False):
        if db is None:
            with self.transaction() as conn:
                return self.put(bucket, key, value, conn, immutable)
        sql = "INSERT INTO records VALUES (?,?,?)" if immutable else "INSERT OR REPLACE INTO records VALUES (?,?,?)"
        db.execute(sql, (bucket, key, json.dumps(value, ensure_ascii=False)))

    def delete(self, bucket, key, db):
        db.execute("DELETE FROM records WHERE bucket=? AND id=?", (bucket, key))
