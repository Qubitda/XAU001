from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from apps.common.uploads import validate_uploaded_document
from config.exceptions import DomainError


class UploadValidationTests(SimpleTestCase):
    def test_accepts_pdf_magic(self):
        f = SimpleUploadedFile("tax.pdf", b"%PDF-1.4 demo", content_type="application/pdf")
        self.assertEqual(validate_uploaded_document(f), "application/pdf")

    def test_rejects_exe(self):
        f = SimpleUploadedFile("malware.exe", b"MZ\x90\x00fake", content_type="application/octet-stream")
        with self.assertRaises(DomainError) as ctx:
            validate_uploaded_document(f)
        self.assertEqual(ctx.exception.error_code, "DOCUMENT_TYPE_INVALID")

    def test_rejects_mismatch(self):
        f = SimpleUploadedFile("x.pdf", b"%PDF-1.4", content_type="image/png")
        with self.assertRaises(DomainError) as ctx:
            validate_uploaded_document(f)
        self.assertEqual(ctx.exception.error_code, "DOCUMENT_TYPE_MISMATCH")
