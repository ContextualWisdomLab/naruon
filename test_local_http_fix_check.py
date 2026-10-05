import sys
sys.path.insert(0, "/app/backend")
from core.local_http import validate_local_request_target, LocalHTTPValidationError

try:
    print(validate_local_request_target("/api/%252e%252e/secret"))
    print("VULNERABLE!")
except LocalHTTPValidationError as e:
    print("SAFE:", e)
