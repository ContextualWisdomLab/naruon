import json

class DecimalDummy(float):
    def __init__(self, value):
        self.value = value
    def __repr__(self):
        return self.value

print(json.dumps({"a": DecimalDummy("1.0000000000000001")}))
