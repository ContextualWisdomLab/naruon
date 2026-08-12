import sys
sys.path.append('backend')
from services.text_safety import _is_tag_like_segment, _strip_tag_like_segments, _PlainTextHTMLParser
import html

parser = _PlainTextHTMLParser()
parser.feed("<!--><script>alert(1)</script>-->")
parser.close()
text = parser.get_text()
print("Parsed text:", repr(text))
print("Strip tag like segments:", repr(_strip_tag_like_segments(text)))

# also look at what the parser does with <!-->
parser2 = _PlainTextHTMLParser()
parser2.feed("<!-->")
parser2.close()
print("Parsed <!-->:", repr(parser2.get_text()))
