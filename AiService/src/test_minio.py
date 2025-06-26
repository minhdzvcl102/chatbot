import os
from dotenv import load_dotenv
from minio import Minio
from minio.error import S3Error
import PyPDF2
from io import BytesIO

load_dotenv()

def test_minio_connection():
    """Test kết nối MinIO và lấy file"""
    print("=== Test MinIO Connection ===")
    
    try:
        # Kết nối MinIO
        minio_client = Minio(
            os.getenv("MINIO_ENDPOINT"),
            access_key=os.getenv("MINIO_ACCESS_KEY"),
            secret_key=os.getenv("MINIO_SECRET_KEY"),
            secure=os.getenv("MINIO_SECURE", "false").lower() == "true"
        )
        bucket_name = os.getenv("MINIO_BUCKET")
        
        print(f"MinIO Endpoint: {os.getenv('MINIO_ENDPOINT')}")
        print(f"Bucket: {bucket_name}")
        
        # Kiểm tra bucket có tồn tại không
        if minio_client.bucket_exists(bucket_name):
            print(f"Bucket {bucket_name} tồn tại")
            
            # Lấy danh sách objects
            objects = list(minio_client.list_objects(bucket_name))
            print(f"Số file trong bucket: {len(objects)}")
            
            for obj in objects:
                print(f"File: {obj.object_name}")
                
                # Nếu là file PDF, thử trích xuất text
                if obj.object_name.lower().endswith('.pdf'):
                    print(f"Tìm thấy file PDF: {obj.object_name}")
                    
                    try:
                        # Lấy file từ MinIO
                        response = minio_client.get_object(bucket_name, obj.object_name)
                        pdf_bytes = response.read()
                        response.close()
                        response.release_conn()
                        
                        # Trích xuất text
                        pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
                        text = ""
                        for page in pdf_reader.pages:
                            text += page.extract_text() or ""
                        
                        print(f"Độ dài text: {len(text)} ký tự")
                        
                        if text.strip():
                            print(f"200 ký tự đầu: {text[:200]}")
                            
                            # Tạo file .txt cùng cấp với main.py
                            txt_filename = obj.object_name.rsplit('.', 1)[0] + '.txt'
                            txt_path = os.path.join(os.path.dirname(__file__), txt_filename)
                            
                            with open(txt_path, 'w', encoding='utf-8') as f:
                                f.write(text)
                            
                            print(f"Đã tạo file .txt: {txt_path}")
                            return True
                        else:
                            print("Không trích xuất được text từ PDF")
                            
                    except Exception as e:
                        print(f"Lỗi khi xử lý PDF: {e}")
                        
        else:
            print(f"Bucket {bucket_name} không tồn tại")
            
    except Exception as e:
        print(f"Lỗi kết nối MinIO: {e}")
        return False

if __name__ == "__main__":
    test_minio_connection() 