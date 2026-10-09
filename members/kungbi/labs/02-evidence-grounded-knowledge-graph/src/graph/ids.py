"""Publication copy: generic code; demo/test data are synthetic, not measured results."""
"""Shared deterministic graph identifiers."""
import hashlib


def make_identity_id(source: str, source_id: str) -> str:
    digest = hashlib.sha256(f"{source}\0{source_id}".encode()).hexdigest()
    return f"identity:{source}:{digest}"
