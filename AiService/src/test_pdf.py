import os
import PyPDF2
from io import BytesIO

def test_pdf_extraction():
    """Test khả năng trích xuất text từ PDF"""
    print("=== Test PDF Text Extraction ===")
    
    # Kiểm tra thư mục uploads
    uploads_dir = os.path.join(os.path.dirname(__file__), 'uploads')
    if os.path.exists(uploads_dir):
        print(f"Thư mục uploads tồn tại: {uploads_dir}")
        files = os.listdir(uploads_dir)
        print(f"Các file trong uploads: {files}")
        
        # Tìm file PDF
        pdf_files = [f for f in files if f.lower().endswith('.pdf')]
        if pdf_files:
            pdf_file = pdf_files[0]
            pdf_path = os.path.join(uploads_dir, pdf_file)
            print(f"Tìm thấy file PDF: {pdf_path}")
            
            try:
                # Thử trích xuất text
                with open(pdf_path, 'rb') as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text() or ""
                    
                print(f"Độ dài text: {len(text)} ký tự")
                if text.strip():
                    print(f"200 ký tự đầu: {text[:200]}")
                    
                    # Tạo file .txt
                    txt_filename = pdf_file.rsplit('.', 1)[0] + '.txt'
                    txt_path = os.path.join(os.path.dirname(__file__), txt_filename)
                    
                    with open(txt_path, 'w', encoding='utf-8') as f:
                        f.write(text)
                    
                    print(f"Đã tạo file .txt: {txt_path}")
                    return True
                else:
                    print("Không trích xuất được text từ PDF")
                    return False
                    
            except Exception as e:
                print(f"Lỗi khi trích xuất PDF: {e}")
                return False
        else:
            print("Không tìm thấy file PDF nào trong thư mục uploads")
            return False
    else:
        print("Thư mục uploads không tồn tại")
        return False

if __name__ == "__main__":
    test_pdf_extraction() 