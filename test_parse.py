import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
from services.text_safety import _strip_tag_like_segments, _PlainTextHTMLParser


def main() -> None:
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


if __name__ == "__main__":
    main()
