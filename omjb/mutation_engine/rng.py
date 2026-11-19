import hashlib,random
def derive_rng(seed,*parts):
 material="|".join(map(str,(seed,*parts))).encode("utf-8")
 return random.Random(int.from_bytes(hashlib.sha256(material).digest()[:8],"big"))