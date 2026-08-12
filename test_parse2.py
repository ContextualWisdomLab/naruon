import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
from services.text_safety import strip_html_markup


def main() -> None:
    payload = "<!--><script>alert(1)</script>-->"
    print(repr(strip_html_markup(payload)))


if __name__ == "__main__":
    main()
