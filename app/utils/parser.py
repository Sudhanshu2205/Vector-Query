from pathlib import Path

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None


class DocumentParser:
    """Parse documents from PDF and TXT files."""

    @staticmethod
    def _get_text_encodings(file_path: str) -> list[str]:
        """Return likely encodings for TXT files created on different platforms."""
        file_prefix = Path(file_path).read_bytes()[:4]

        if file_prefix.startswith((b"\xff\xfe", b"\xfe\xff")):
            return ["utf-16", "utf-8-sig", "utf-8", "latin-1"]
        if file_prefix.startswith(b"\xef\xbb\xbf"):
            return ["utf-8-sig", "utf-8", "utf-16", "latin-1"]
        return ["utf-8", "utf-8-sig", "utf-16", "latin-1"]
    
    @staticmethod
    def parse_pdf(file_path: str) -> str:
        """
        Extract text from a PDF file.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Extracted text content
        """
        text = ""
        try:
            if PdfReader is None:
                raise ValueError(
                    "PDF support requires the 'pypdf' package, which is not available "
                    "in the current Python environment."
                )

            reader = PdfReader(file_path)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        except Exception as e:
            raise ValueError(f"Failed to parse PDF: {str(e)}")
        return text
    
    @staticmethod
    def parse_txt(file_path: str) -> str:
        """
        Extract text from a TXT file.
        
        Args:
            file_path: Path to the TXT file
            
        Returns:
            Extracted text content
        """
        last_error = None

        for encoding in DocumentParser._get_text_encodings(file_path):
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError as exc:
                last_error = exc
            except Exception as e:
                raise ValueError(f"Failed to parse TXT: {str(e)}")

        raise ValueError(
            f"Failed to parse TXT: unable to decode {file_path} with supported encodings"
        ) from last_error
    
    @staticmethod
    def parse_document(file_path: str) -> str:
        """
        Parse document based on file extension.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Extracted text content
        """
        extension = Path(file_path).suffix.lower()
        
        if extension == '.pdf':
            return DocumentParser.parse_pdf(file_path)
        elif extension == '.txt':
            return DocumentParser.parse_txt(file_path)
        else:
            raise ValueError(f"Unsupported file format: {extension}. Only PDF and TXT are supported.")
