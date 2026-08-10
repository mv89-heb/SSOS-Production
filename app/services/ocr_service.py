import os
from abc import ABC, abstractmethod

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".pdf"}
ALLOWED_MIME_TYPES = {
    "image/png", "image/jpeg", "image/bmp", "image/tiff", "application/pdf",
}


class OCRProviderError(Exception):
    pass


class OCRProvider(ABC):
    """Abstraction so the underlying OCR engine can be swapped without touching callers."""

    @abstractmethod
    def extract_text(self, file_path: str) -> str:
        raise NotImplementedError


class TesseractOCRProvider(OCRProvider):
    def extract_text(self, file_path: str) -> str:
        try:
            import pytesseract
            from PIL import Image
        except ImportError as exc:
            raise OCRProviderError(
                "pytesseract/Pillow are not installed; add them to requirements.txt "
                "and install the tesseract-ocr system package"
            ) from exc

        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            return self._extract_from_pdf(file_path, pytesseract)

        try:
            image = Image.open(file_path)
        except Exception as exc:
            raise OCRProviderError(f"Could not open image for OCR: {exc}") from exc

        return pytesseract.image_to_string(image)

    @staticmethod
    def _extract_from_pdf(file_path: str, pytesseract) -> str:
        try:
            from pdf2image import convert_from_path
        except ImportError as exc:
            raise OCRProviderError(
                "pdf2image is required for PDF OCR; add it to requirements.txt"
            ) from exc

        pages = convert_from_path(file_path)
        return "\n".join(pytesseract.image_to_string(page) for page in pages)


class NullOCRProvider(OCRProvider):
    """Used automatically when no OCR engine is installed, so uploads still succeed
    for validation/storage purposes without failing the whole request."""

    def extract_text(self, file_path: str) -> str:
        return ""


def validate_upload(filename: str, mime_type: str, file_size: int, max_size: int) -> None:
    if not filename:
        raise OCRProviderError("No filename provided")

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise OCRProviderError(f"Unsupported file extension: {ext}")

    if mime_type not in ALLOWED_MIME_TYPES:
        raise OCRProviderError(f"Unsupported MIME type: {mime_type}")

    if file_size > max_size:
        raise OCRProviderError(f"File exceeds maximum allowed size of {max_size} bytes")


class OCRService:
    def __init__(self, provider: OCRProvider = None):
        self.provider = provider or self._default_provider()

    @staticmethod
    def _default_provider() -> OCRProvider:
        try:
            import pytesseract  # noqa: F401
            return TesseractOCRProvider()
        except ImportError:
            return NullOCRProvider()

    def process_document(self, file_path: str) -> dict:
        if not os.path.exists(file_path):
            return {"status": "error", "message": "File not found", "text": "", "detected_items": []}

        try:
            text = self.provider.extract_text(file_path)
        except OCRProviderError as exc:
            return {"status": "error", "message": str(exc), "text": "", "detected_items": []}

        return {
            "status": "success",
            "text": text,
            "detected_items": self._parse_line_items(text),
        }

    @staticmethod
    def _parse_line_items(text: str) -> list:
        """Best-effort extraction of "<description> x<qty> <price>" style lines.
        Real catalog matching belongs in a downstream service; this only
        extracts a rough structure from raw OCR text."""
        items = []
        for line in (text or "").splitlines():
            line = line.strip()
            if not line:
                continue
            items.append({"raw_line": line})
        return items
