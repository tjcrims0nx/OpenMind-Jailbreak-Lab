"""SQLite evidence store with additive migrations; secrets are never persisted."""
import hashlib,json,sqlite3,time
SCHEMA="""PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY,name TEXT,target TEXT,config TEXT,started_at REAL,finished_at REAL);
CREATE TABLE IF NOT EXISTS results(id INTEGER PRIMARY KEY,run_id INTEGER NOT NULL REFERENCES runs(id),probe_id TEXT,probe_category TEXT,prompt TEXT,system TEXT,response TEXT,response_sha256 TEXT,detector_label TEXT,detector_score REAL,detector_reason TEXT,bypass INTEGER,meta TEXT,created_at REAL,pipeline_result TEXT,provenance TEXT);
CREATE TABLE IF NOT EXISTS adjudications(id INTEGER PRIMARY KEY,result_id INTEGER NOT NULL REFERENCES results(id),label TEXT,notes TEXT,adjudicated_at REAL);
CREATE TABLE IF NOT EXISTS guard_observations(id INTEGER PRIMARY KEY,result_id INTEGER NOT NULL REFERENCES results(id),stage TEXT NOT NULL,decision TEXT NOT NULL,findings TEXT NOT NULL,created_at REAL);
CREATE INDEX IF NOT EXISTS idx_results_run ON results(run_id);
CREATE INDEX IF NOT EXISTS idx_guard_result ON guard_observations(result_id);
"""
class Store:
    def __init__(self,path="openmind.db"):
        self.conn=sqlite3.connect(path); self.conn.row_factory=sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._ensure_column("results","pipeline_result","TEXT")
        self._ensure_column("results","provenance","TEXT")
        self.conn.commit()
    def _ensure_column(self,table,column,definition):
        cols={r["name"] for r in self.conn.execute(f"PRAGMA table_info({table})")}
        if column not in cols: self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    def close(self): self.conn.close()
    def create_run(self,name,target,config):
        cur=self.conn.execute("INSERT INTO runs(name,target,config,started_at) VALUES(?,?,?,?)",(name,target,json.dumps(config),time.time()))
        self.conn.commit(); return cur.lastrowid
    def finish_run(self,rid):
        self.conn.execute("UPDATE runs SET finished_at=? WHERE id=?",(time.time(),rid)); self.conn.commit()
    def add_result(self,rid,probe,response,detection,guard=None,pipeline_result=None):
        sha=hashlib.sha256(response.encode()).hexdigest()
        pr=pipeline_result.to_dict() if hasattr(pipeline_result,"to_dict") else pipeline_result
        provenance=getattr(probe,"provenance_record",None)
        if hasattr(provenance,"to_dict"): provenance=provenance.to_dict()
        cur=self.conn.execute("""INSERT INTO results(run_id,probe_id,probe_category,prompt,system,response,response_sha256,detector_label,detector_score,detector_reason,bypass,meta,created_at,pipeline_result,provenance)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rid,probe.id,probe.category,probe.prompt,probe.system,response,sha,detection.label,detection.score,detection.reason,
             None if detection.bypass is None else int(detection.bypass),json.dumps(probe.meta),time.time(),
             json.dumps(pr) if pr is not None else None,json.dumps(provenance) if provenance else None))
        self.conn.commit(); return cur.lastrowid
    def add_guard_observation(self,result_id,stage,decision,findings):
        if stage not in {"input","output"} or decision not in {"allow","review","block"}: raise ValueError("invalid guard observation")
        self.conn.execute("INSERT INTO guard_observations(result_id,stage,decision,findings,created_at) VALUES(?,?,?,?,?)",(result_id,stage,decision,json.dumps(findings),time.time()))
        self.conn.commit()
    def get_guard_observations(self,result_id):
        return [dict(x) for x in self.conn.execute("SELECT * FROM guard_observations WHERE result_id=? ORDER BY id",(result_id,))]
    def get_run(self,rid):
        row=self.conn.execute("SELECT * FROM runs WHERE id=?",(rid,)).fetchone(); return dict(row) if row else {}
    def get_results(self,rid):
        return [dict(x) for x in self.conn.execute("SELECT * FROM results WHERE run_id=? ORDER BY id",(rid,))]
    def get_adjudicated_results(self,rid):
        return [dict(x) for x in self.conn.execute("""SELECT r.*,a.label AS adjudicated_label,a.notes AS adjudication_notes,a.adjudicated_at
            FROM results r JOIN adjudications a ON a.result_id=r.id
            WHERE r.run_id=? AND a.id=(SELECT MAX(a2.id) FROM adjudications a2 WHERE a2.result_id=r.id) ORDER BY r.id""",(rid,))]
    def get_results_with_adjudication(self,rid):
        return [dict(x) for x in self.conn.execute("""SELECT r.*,a.label AS adj_label,a.notes AS adj_notes,a.adjudicated_at AS adj_at
            FROM results r LEFT JOIN adjudications a ON a.result_id=r.id
            AND a.id=(SELECT MAX(a2.id) FROM adjudications a2 WHERE a2.result_id=r.id)
            WHERE r.run_id=? ORDER BY r.id""",(rid,))]
    def list_runs(self):
        return [dict(x) for x in self.conn.execute("SELECT * FROM runs ORDER BY id")]
    def add_adjudication(self,result_id,label,notes=""):
        if label not in ("refusal","compliance","partial","unclear","skip"): raise ValueError("invalid adjudication label")
        self.conn.execute("INSERT INTO adjudications(result_id,label,notes,adjudicated_at) VALUES(?,?,?,?)",(result_id,label,notes,time.time())); self.conn.commit()
    def unadjudicated(self,rid):
        return [dict(x) for x in self.conn.execute("""SELECT r.* FROM results r LEFT JOIN adjudications a ON a.result_id=r.id WHERE r.run_id=? AND a.id IS NULL ORDER BY r.id""",(rid,))]
