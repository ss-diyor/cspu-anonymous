from io import BytesIO

from pypdf import PdfReader, PdfWriter

from app.services.content import _sanitize_pdf_bytes, rendered_text, validate_content


def test_channel_post_layout_is_clean() -> None:
    assert (
        rendered_text("O‘qish qachondan", prefix="#1", footer="#question")
        == "#1\n\nO‘qish qachondan\n\n#question"
    )


def test_document_policy_allows_only_small_pdf() -> None:
    base = {
        "content_type": "document",
        "text": "",
        "file_size": 1024,
        "mime_type": "application/pdf",
        "file_name": "anonim.pdf",
    }
    assert validate_content(base) is None
    assert validate_content({**base, "mime_type": "application/x-msdownload"})
    assert validate_content({**base, "file_name": "virus.exe"})
    assert validate_content({**base, "file_size": 11 * 1024 * 1024})


def test_pdf_metadata_is_removed() -> None:
    source = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_metadata({"/Author": "Personal Name", "/Title": "Private title"})
    writer.write(source)

    cleaned = PdfReader(BytesIO(_sanitize_pdf_bytes(source.getvalue())))
    assert len(cleaned.pages) == 1
    assert not cleaned.metadata.get("/Author")
    assert not cleaned.metadata.get("/Title")
