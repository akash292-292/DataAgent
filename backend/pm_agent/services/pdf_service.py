import io
import PyPDF2
import pdfplumber
from typing import Dict, Any

class PDFService:
    """Service for extracting text from PDF files"""
    
    def __init__(self):
        pass
    
    def extract_text_from_pdf(self, file_content: bytes) -> Dict[str, Any]:
        """Extract text from PDF file using multiple methods for better accuracy"""
        try:
            # Method 1: Try pdfplumber first (better for complex layouts)
            text_from_pdfplumber = self._extract_with_pdfplumber(file_content)
            
            # Method 2: Fallback to PyPDF2 if pdfplumber fails
            if not text_from_pdfplumber.strip():
                text_from_pypdf2 = self._extract_with_pypdf2(file_content)
                if text_from_pypdf2.strip():
                    return {
                        'success': True,
                        'text': text_from_pypdf2,
                        'method': 'PyPDF2'
                    }
            
            if text_from_pdfplumber.strip():
                return {
                    'success': True,
                    'text': text_from_pdfplumber,
                    'method': 'pdfplumber'
                }
            
            return {
                'success': False,
                'error': 'No text content found in PDF'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Error processing PDF: {str(e)}'
            }
    
    def _extract_with_pdfplumber(self, file_content: bytes) -> str:
        """Extract text using pdfplumber (better for tables and complex layouts)"""
        try:
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                text_parts = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                
                # Also try to extract tables
                for page in pdf.pages:
                    tables = page.extract_tables()
                    for table in tables:
                        if table:
                            table_text = []
                            for row in table:
                                if row:
                                    row_text = []
                                    for cell in row:
                                        if cell:
                                            row_text.append(str(cell).strip())
                                    if row_text:
                                        table_text.append(' | '.join(row_text))
                            if table_text:
                                text_parts.append('\n'.join(table_text))
                
                return '\n'.join(text_parts)
                
        except Exception as e:
            print(f"pdfplumber extraction failed: {str(e)}")
            return ""
    
    def _extract_with_pypdf2(self, file_content: bytes) -> str:
        """Extract text using PyPDF2 (fallback method)"""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            text_parts = []
            
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            
            return '\n'.join(text_parts)
            
        except Exception as e:
            print(f"PyPDF2 extraction failed: {str(e)}")
            return ""

# Create service instance
pdf_service = PDFService()
