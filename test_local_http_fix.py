import sys
sys.path.insert(0, "/app/backend")
from urllib.parse import unquote

def _validate(path):
    for raw_segment in path.split("/"):
        decoded_segment = raw_segment
        for _ in range(100):
            next_segment = unquote(decoded_segment, errors="strict")
            if next_segment == decoded_segment:
                break
            decoded_segment = next_segment
        else:
            if unquote(decoded_segment, errors="strict") != decoded_segment:
                raise ValueError("Limit exceeded")
        print(f"Segment: {decoded_segment}")
        if (
            decoded_segment in {".", ".."}
            or "/" in decoded_segment
            or "\\" in decoded_segment
        ):
            print("Traversal detected")

_validate("/api/%252e%252e/secret")
