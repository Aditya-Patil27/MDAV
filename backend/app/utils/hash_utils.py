import hashlib
import json
from datetime import datetime


def compute_file_hash(file_path: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def compute_data_hash(data: dict) -> str:
    data_str = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(data_str.encode()).hexdigest()


def compute_block_hash(previous_hash: str, data_hash: str, timestamp: str) -> str:
    block_data = f"{previous_hash}{data_hash}{timestamp}"
    return hashlib.sha256(block_data.encode()).hexdigest()
