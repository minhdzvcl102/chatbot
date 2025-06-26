import os
from minio import Minio
from minio.error import S3Error
from io import BytesIO
import PyPDF2
from minio import Minio

def upload_file_to_minio(file_obj, filename, content_type):
    minio_client = Minio(
        os.getenv("MINIO_ENDPOINT"),
        access_key=os.getenv("MINIO_ACCESS_KEY"),
        secret_key=os.getenv("MINIO_SECRET_KEY"),
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true"
    )
    bucket_name = os.getenv("MINIO_BUCKET")

    # Tạo bucket nếu chưa có
    if not minio_client.bucket_exists(bucket_name):
        minio_client.make_bucket(bucket_name)

    try:
        minio_client.put_object(
            bucket_name,
            filename,
            file_obj,
            length=-1,
            part_size=10*1024*1024,
            content_type=content_type
        )
        file_url = f"http://{os.getenv('MINIO_ENDPOINT')}/{bucket_name}/{filename}"
        return file_url
    except S3Error as e:
        raise Exception(f"MinIO upload error: {e}")

# Tạo hàm để lấy text từ file PDF đã upload lên MinIO
# Hàm này sẽ đọc file PDF từ MinIO và trích xuất văn bản từ nó
def get_pdf_text_from_minio(filename):
    minio_client = Minio(
        os.getenv("MINIO_ENDPOINT"),
        access_key=os.getenv("MINIO_ACCESS_KEY"),
        secret_key=os.getenv("MINIO_SECRET_KEY"),
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true"
    )
    bucket_name = os.getenv("MINIO_BUCKET")
    response = minio_client.get_object(bucket_name, filename)
    pdf_bytes = response.read()
    response.close()
    response.release_conn()
    pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() or ""
    return text