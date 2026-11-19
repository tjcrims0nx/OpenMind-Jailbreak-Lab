"""Synchronous adapter for an operator-controlled guardrail endpoint."""
from __future__ import annotations
from urllib.parse import urlparse
from .core import Verdict

def httpx_submitter(endpoint: str, *, headers: dict[str,str] | None = None, timeout: float = 15.0):
    parsed=urlparse(endpoint)
    local_hosts={"localhost","127.0.0.1","::1"}
    if parsed.scheme!="https" and not (parsed.scheme=="http" and parsed.hostname in local_hosts):
        raise ValueError("endpoint must use HTTPS (HTTP is allowed only for loopback)")
    if not parsed.hostname:
        raise ValueError("endpoint must include a hostname")
    if timeout<=0:
        raise ValueError("timeout must be positive")
    try:
        import httpx
    except ImportError as exc:
        raise RuntimeError("install the optional API dependencies: pip install 'openmind-omjb[api]'") from exc

    def submit(payload: str) -> Verdict:
        with httpx.Client(timeout=timeout) as client:
            response=client.post(endpoint,json={"input":payload},headers=headers or {})
            response.raise_for_status()
            data=response.json()
        if not isinstance(data,dict):
            raise ValueError("response must be a JSON object")
        if "decision" in data:
            decision=str(data["decision"]).lower()
            if decision not in ("allow","review","block"):
                raise ValueError("unrecognized decision value")
            allowed=decision=="allow"
        elif "safe" in data and isinstance(data["safe"],bool):
            allowed=data["safe"]
        elif "flagged" in data and isinstance(data["flagged"],bool):
            allowed=not data["flagged"]
        else:
            raise ValueError("response must include decision, safe, or flagged")
        return Verdict(allowed=allowed,latency_ms=response.elapsed.total_seconds()*1000,raw=data)
    return submit
