# utils_rounds.py
import hashlib, random

def _seed_int(s: str) -> int:
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest()[:12], 16)

def deterministic_shuffle(ids, seed_text: str):
    rnd = random.Random(_seed_int(seed_text))
    ids = list(ids)
    rnd.shuffle(ids)
    return ids
