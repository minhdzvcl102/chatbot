import os
from dotenv import load_dotenv # Chỉ import một lần

load_dotenv() 

from flask import Flask, request, jsonify
from flask_cors import CORS
from ai_processor import process_ai_request # Bây giờ, ai_processor có thể đọc biến môi trường
# import minio
from minio import Minio
from minio.error import S3Error
from vector_ultils import upload_file_to_minio
import base64
from io import BytesIO


app = Flask(__name__)

CORS(app, resources={r"/data/process": {"origins": "http://localhost:5173"}})

@app.route('/')
def index():
    return "AI Service is running!"

@app.route('/data/process', methods=['POST'])
def handle_data_from_node():
    data = request.json
    
    print(f"Received data from frontend: {data.get('user_query', 'N/A')}")
    # print(f"Type of data: {type(data)}")
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    user_query = data.get('user_query')
    if not user_query:
        return jsonify({"error": "Missing 'user_query' in request data"}), 400
    if not isinstance(user_query, str):
        return jsonify({"error": "Invalid 'user_query' format, expected string"}), 400
        
    try:
        response = process_ai_request(user_query) 
        return jsonify({"status": "success", "ai_response": response}), 200 # Trả về response có cấu trúc
    except Exception as e:
        print(f"Error processing request: {e}") 
        return jsonify({"error": str(e)}), 500


# route upload file
@app.route('/file/process', methods=['POST'])
def upload_file():
    print("request.files:", request.files)
    print("request.form:", request.form)
    print("request.content_type:", request.content_type)
    # ...phần còn lại giữ nguyên...
    content_type = request.content_type
    if content_type and content_type.startswith('application/json'):
        data = request.get_json()
        file_content = data.get('file_content')
        filename = data.get('filename', 'uploaded_file')
        if not file_content:
            return jsonify({"error": "No file content"}), 400
        try:
            file_bytes = base64.b64decode(file_content)
            file_obj = BytesIO(file_bytes)
            file_url = upload_file_to_minio(file_obj, filename, 'application/octet-stream')
            return jsonify({"status": "success", "file_url": file_url}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        # Xử lý như cũ với form-data
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        try:
            file_url = upload_file_to_minio(file.stream, file.filename, file.content_type)
            return jsonify({"status": "success", "file_url": file_url}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000) # Chạy ứng dụng Flask trên cổng 5000

