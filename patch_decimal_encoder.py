import re

with open("backend/api/tools.py", "r") as f:
    content = f.read()

new_class = """
class _DecimalEncoder(json.JSONEncoder):
    def iterencode(self, o, _one_shot=False):
        # Override iterencode to yield ExactDecimal string values directly
        for chunk in super().iterencode(o, _one_shot):
            yield chunk

class _ExactDecimal:
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return self.value
"""
# json dumps uses C extension and bypasses custom repr by default for dicts, UNLESS we use a custom type. But custom types go to default() which expects standard JSON types.
# Actually, python json dumps doesn't allow custom float formatting easily without simplejson.
# Let's find how we can make json.dumps emit EXACT decimal.
