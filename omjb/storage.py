"""SQLite evidence store; API credentials are never persisted."""
import hashlib, json, sqlite3, time
SCHEMA = """PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY,name TEXT,target TEXT,config TEXT,started_at REAL,finished_at REAL);
CREATE TABLE IF NOT EXISTS results(id INTEGER PRIMARY KEY,run_id INTEGER NOT NULL REFERENCES runs(id),probe_id TEXT,probe_category TEXT,prompt TEXT,system TEXT,response TEXT,response_sha256 TEXT,detector_label TEXT,detector_score REAL,detector_reason TEXT,bypass INTEGER,meta TEXT,created_at REAL);
CREATE TABLE IF NOT EXISTS adjudications(id INTEGER PRIMARY KEY,result_id INTEGER NOT NULL REFERENCES results(id),label TEXT,notes TEXT,adjudicated_at REAL);
CREATE INDEX IF NOT EXISTS idx_results_run ON results(run_id);
"""
class Store:
    def __init__(self, path="openmind.db"):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
    def close(self):
        self.conn.close()
    def create_run(self, name, target, config):
        cur = self.conn.execute("INSERT INTO runs(name,target,config,started_at) VALUES(?,?,?,?)", (name,target,json.dumps(config),time.time()))
        self.conn.commit()
        return cur.lastrowid
    def finish_run(self, rid):
        self.conn.execute("UPDATE runs SET finished_at=? WHERE id=?", (time.time(),rid))
        self.conn.commit()
    def add_result(self, rid, probe, response, detection):
        sha = hashlib.sha256(response.encode()).hexdigest()
        cur = self.conn.execute("""INSERT INTO results(run_id,probe_id,probe_category,prompt,system,response,response_sha256,detector_label,detector_score,detector_reason,bypass,meta,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rid,probe.id,probe.category,probe.prompt,probe.system,response,sha,detection.label,detection.score,detection.reason,None if detection.bypass is None else int(detection.bypass),json.dumps(probe.meta),time.time()))
        self.conn.commit()
        return cur.lastrowid
    def get_run(self, rid):
        row = self.conn.execute("SELECT * FROM runs WHERE id=?", (rid,)).fetchone()
        return dict(row) if row else {}
    def get_results(self, rid):
        return [dict(x) for x in self.conn.execute("SELECT * FROM results WHERE run_id=? ORDER BY id", (rid,))]
    def list_runs(self):
        return [dict(x) for x in self.conn.execute("SELECT * FROM runs ORDER BY id")]
    def add_adjudication(self, result_id, label, notes=""):
        if label not in ("refusal","compliance","partial","unclear","skip"):
            raise ValueError("invalid adjudication label")
        self.conn.execute("INSERT INTO adjudications(result_id,label,notes,adjudicated_at) VALUES(?,?,?,?)",(result_id,label,notes,time.time()))
        self.conn.commit()
    def unadjudicated(self, rid):
        return [dict(x) for x in self.conn.execute("""SELECT r.* FROM results r LEFT JOIN adjudications a ON a.result_id=r.id WHERE r.run_id=? AND a.id IS NULL ORDER BY r.id""",(rid,))]
