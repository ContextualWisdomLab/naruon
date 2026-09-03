import json

class RawFloat:
    def __init__(self, value):
        self.value = value

class RawEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, RawFloat):
            return {"__raw_float__": obj.value}
        return super().default(obj)

data = {"large": RawFloat("1e400"), "precise": RawFloat("1.0000000000000001")}
formatted = json.dumps(data, indent=2, cls=RawEncoder)

import re
formatted = re.sub(r'\{\n\s+"__raw_float__": "(.*?)"\n\s+\}', r'\1', formatted)
print(formatted)
