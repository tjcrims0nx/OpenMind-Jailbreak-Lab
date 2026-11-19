"""Provider adapters for authorized evaluation; standard library only."""
from __future__ import annotations
import abc,json,os,time,urllib.error,urllib.parse,urllib.request
from dataclasses import dataclass,field
from typing import Any

@dataclass
class Message:
    role:str
    content:str
@dataclass
class Generation:
    text:str
    model:str=""
    raw:dict=field(default_factory=dict)
    latency_ms:float=0.0
class Target(abc.ABC):
    name="base"
    def config(self)->dict: return {"name":self.name,"class":type(self).__name__}
    @abc.abstractmethod
    def generate(self,messages:list[Message],**params:Any)->Generation: ...
class EchoTarget(Target):
    name="echo"
    def generate(self,messages,**params): return Generation("[echo] "+(messages[-1].content if messages else ""),"echo")

_ALLOWED_PARAMS={"temperature","top_p","max_tokens","stop","seed"}
def _safe_params(params):
    unknown=set(params)-_ALLOWED_PARAMS
    if unknown: raise ValueError("unsupported generation parameters: "+", ".join(sorted(unknown)))
    return params
class _HTTPMixin:
    def _post(self,path,payload,headers):
        req=urllib.request.Request(self.base_url+path,data=json.dumps(payload).encode(),
            headers={"Content-Type":"application/json",**headers},method="POST")
        try:
            with urllib.request.urlopen(req,timeout=self.timeout) as response: return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc: raise RuntimeError(f"provider returned HTTP {exc.code}") from exc
        except (urllib.error.URLError,TimeoutError) as exc: raise RuntimeError(f"provider connection failed: {type(exc).__name__}") from exc
class OpenAICompatTarget(Target,_HTTPMixin):
    def __init__(self,name,base_url,api_key,model,timeout=60):
        if not base_url.startswith(("https://","http://localhost","http://127.0.0.1")): raise ValueError("use HTTPS, or an explicit localhost endpoint")
        self.name,self.base_url,self.api_key,self.model,self.timeout=name,base_url.rstrip("/"),api_key,model,timeout
    def config(self): return {"name":self.name,"class":type(self).__name__,"base_url":self.base_url,"model":self.model}
    def generate(self,messages,**params):
        start=time.monotonic(); data=self._post("/chat/completions",{"model":self.model,"messages":[m.__dict__ for m in messages],**_safe_params(params)},{"Authorization":"Bearer "+self.api_key})
        try: content=data["choices"][0]["message"]["content"]
        except (KeyError,IndexError,TypeError) as exc: raise RuntimeError("unexpected chat-completions response") from exc
        if isinstance(content,list): content="".join(x.get("text","") for x in content if isinstance(x,dict))
        return Generation(str(content or ""),self.model,{},(time.monotonic()-start)*1000)
class AnthropicTarget(Target,_HTTPMixin):
    def __init__(self,name,base_url,api_key,model,timeout=60,max_tokens=1024):
        if not base_url.startswith("https://"): raise ValueError("Anthropic endpoint must use HTTPS")
        self.name,self.base_url,self.api_key,self.model,self.timeout,self.max_tokens=name,base_url.rstrip("/"),api_key,model,timeout,max_tokens
    def config(self): return {"name":self.name,"class":type(self).__name__,"base_url":self.base_url,"model":self.model}
    def generate(self,messages,**params):
        start=time.monotonic(); system="\n".join(m.content for m in messages if m.role=="system")
        payload={"model":self.model,"max_tokens":self.max_tokens,"messages":[m.__dict__ for m in messages if m.role!="system"],**_safe_params(params)}
        if system: payload["system"]=system
        data=self._post("/v1/messages",payload,{"x-api-key":self.api_key,"anthropic-version":"2023-06-01"})
        content="".join(b.get("text","") for b in data.get("content",[]) if isinstance(b,dict))
        return Generation(content,self.model,{},(time.monotonic()-start)*1000)
class OllamaTarget(Target,_HTTPMixin):
    def __init__(self,name,base_url,model,timeout=120):
        if not base_url.startswith(("http://localhost","http://127.0.0.1","https://")): raise ValueError("Ollama endpoint must be HTTPS or localhost")
        self.name,self.base_url,self.model,self.timeout=name,base_url.rstrip("/"),model,timeout
    def config(self): return {"name":self.name,"class":type(self).__name__,"base_url":self.base_url,"model":self.model}
    def generate(self,messages,**params):
        start=time.monotonic(); data=self._post("/api/chat",{"model":self.model,"messages":[m.__dict__ for m in messages],"stream":False,"options":_safe_params(params)},{})
        try: content=data["message"]["content"]
        except (KeyError,TypeError) as exc: raise RuntimeError("unexpected Ollama response") from exc
        return Generation(content,self.model,{},(time.monotonic()-start)*1000)
class GeminiTarget(Target,_HTTPMixin):
    def __init__(self,name,api_key,model,base_url="https://generativelanguage.googleapis.com",timeout=60):
        if not base_url.startswith("https://"): raise ValueError("Gemini endpoint must use HTTPS")
        self.name,self.api_key,self.model,self.base_url,self.timeout=name,api_key,model,base_url.rstrip("/"),timeout
    def config(self): return {"name":self.name,"class":type(self).__name__,"base_url":self.base_url,"model":self.model}
    def generate(self,messages,**params):
        start=time.monotonic(); params=_safe_params(params)
        system="\n".join(m.content for m in messages if m.role=="system")
        contents=[{"role":"model" if m.role=="assistant" else "user","parts":[{"text":m.content}]} for m in messages if m.role!="system"]
        payload={"contents":contents}
        if system: payload["systemInstruction"]={"parts":[{"text":system}]}
        generation={}
        if "temperature" in params: generation["temperature"]=params["temperature"]
        if "top_p" in params: generation["topP"]=params["top_p"]
        if "max_tokens" in params: generation["maxOutputTokens"]=params["max_tokens"]
        if "stop" in params: generation["stopSequences"]=params["stop"] if isinstance(params["stop"],list) else [params["stop"]]
        if generation: payload["generationConfig"]=generation
        path="/v1beta/models/"+urllib.parse.quote(self.model,safe="")+":generateContent?key="+urllib.parse.quote(self.api_key,safe="")
        data=self._post(path,payload,{})
        try: text="".join(p.get("text","") for p in data["candidates"][0]["content"]["parts"] if isinstance(p,dict))
        except (KeyError,IndexError,TypeError) as exc: raise RuntimeError("unexpected Gemini generateContent response") from exc
        return Generation(text,self.model,{},(time.monotonic()-start)*1000)

def target_from_env(kind,model,base_url=None,api_key_env=None):
    if kind=="echo": return EchoTarget()
    if kind=="ollama": return OllamaTarget(kind,base_url or "http://localhost:11434",model)
    env=api_key_env or {"gemini":"GEMINI_API_KEY","anthropic":"ANTHROPIC_API_KEY"}.get(kind,"OPENAI_API_KEY")
    key=os.environ.get(env,"")
    if not key: raise ValueError(f"missing environment variable {env}")
    if kind=="gemini": return GeminiTarget(kind,key,model,base_url or "https://generativelanguage.googleapis.com")
    if kind=="anthropic": return AnthropicTarget(kind,base_url or "https://api.anthropic.com",key,model)
    if kind in {"openai","openai-compatible"}: return OpenAICompatTarget(kind,base_url or "https://api.openai.com/v1",key,model)
    raise ValueError(f"unsupported target: {kind}")
