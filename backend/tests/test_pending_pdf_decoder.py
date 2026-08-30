import base64

import api.data as data_api
from db.models import Document


def test_pending_pdf_document_decoder_success():
    """Decode a valid stored base64 PDF payload without altering its bytes."""

    pdf_bytes = b"%PDF-1.4\n%...\n%%EOF\n"
    document = Document(document_content=base64.b64encode(pdf_bytes).decode("ascii"))

    decoded = data_api.decode_pending_pdf_document_bytes(document)

    assert decoded == pdf_bytes
