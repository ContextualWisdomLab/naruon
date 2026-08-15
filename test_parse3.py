import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
from services.text_safety import _mask_angle_emails, _PlainTextHTMLParser, _strip_tag_like_segments


def main() -> None:
    payload = "<!--><script>alert(1)</script>-->"

    decoded = payload
    masked, placeholders = _mask_angle_emails(decoded)
    print("masked:", repr(masked))
    parser = _PlainTextHTMLParser()
    parser.feed(masked)
    parser.close()
    text = parser.get_text()
    print("text after parser get_text (normalized):", repr(text))

    print("after get_text but raw joins:", repr("".join(parser._parts)))
    print("just _strip_tag_like_segments directly on parser._parts:", _strip_tag_like_segments("".join(parser._parts)))

    cleaned_lines = []
    for line in text.splitlines():
        cleaned_lines.append(_strip_tag_like_segments(line))
    text = "\n".join(cleaned_lines).strip()
    for token, original in placeholders.items():
        text = text.replace(token, original)
    print("text after second loop:", repr(text))


if __name__ == "__main__":
    main()
