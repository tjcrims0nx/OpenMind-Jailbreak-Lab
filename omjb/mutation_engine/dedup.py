import hashlib
import re
import unicodedata

def normalize(text):
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"\s+", " ", text).strip()

def dedup_key(text):
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()[:24]
