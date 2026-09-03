import json
import decimal
import re

json_string = '{"large": 1e400, "precise": 1.0000000000000001}'

def _reject_invalid_constants(constant: str) -> None:
    raise ValueError(f"Invalid JSON string: constant {constant} is not allowed")

class ExactDecimal:
    def __init__(self, value):
        self.value = str(value)

    def __repr__(self):
        return f"ExactDecimal({self.value})"

parsed = json.loads(
    json_string,
    parse_float=lambda x: ExactDecimal(x),
    parse_constant=_reject_invalid_constants
)

print(parsed)
