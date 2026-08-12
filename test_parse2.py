import sys
sys.path.append('backend')
from services.text_safety import strip_html_markup

payload = "<!--><script>alert(1)</script>-->"
print(repr(strip_html_markup(payload)))
