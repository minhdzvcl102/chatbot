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
from vector_ultils import get_pdf_text_from_minio



app = Flask(__name__)

CORS(app, origins="http://localhost:5173")

@app.route('/')
def index():
    return "AI Service is running!"

@app.route('/data/process', methods=['POST'])
def handle_data_from_node():
    data = request.json
    print(f"Received data from frontend: {data.get('user_query', 'N/A')}")
    if not data:
        return jsonify({"error": "No data provided"}), 400

    messages = data.get('messages')
    user_query = data.get('user_query')

    # Ưu tiên xử lý mảng messages nếu có
    if messages and isinstance(messages, list):
        # Nếu chưa có system message ở đầu, prepend vào
        if not messages or messages[0].get('role') != 'system':
            system_message = {
                "role": "system",
                "content": (
                    "Bạn là trợ lý AI, hãy trả lời bằng tiếng Việt, hiểu các tham chiếu như 'đoạn trên', 'ý trước', và chấp nhận viết tắt, sai chính tả của người dùng."
                )
            }
            messages = [system_message] + messages
        try:
            response = process_ai_request(messages=messages)
            return jsonify({"status": "success", "ai_response": response}), 200
        except Exception as e:
            print(f"Error processing request: {e}")
            return jsonify({"error": str(e)}), 500
    # Nếu không có messages, fallback về user_query như cũ
    if not user_query:
        return jsonify({"error": "Missing 'user_query' in request data"}), 400
    if not isinstance(user_query, str):
        return jsonify({"error": "Invalid 'user_query' format, expected string"}), 400
    try:
        response = process_ai_request(user_query)
        return jsonify({"status": "success", "ai_response": response}), 200
    except Exception as e:
        print(f"Error processing request: {e}")
        return jsonify({"error": str(e)}), 500


# route upload file
@app.route('/file/process', methods=['POST'])
def upload_file():
    print("=== UPLOAD FILE REQUEST ===")
    print("request.files:", request.files)
    print("request.form:", request.form)
    print("request.content_type:", request.content_type)
    content_type = request.content_type
    if content_type and content_type.startswith('application/json'):
        data = request.get_json()
        file_content = data.get('file_content')
        filename = data.get('filename', 'uploaded_file')
        print(f"[DEBUG] Đã nhận filename từ frontend: {filename}")
        if not file_content:
            return jsonify({"error": "No file content"}), 400
        try:
            file_bytes = base64.b64decode(file_content)
            file_obj = BytesIO(file_bytes)
            
            # Upload lên MinIO
            try:
                file_url = upload_file_to_minio(file_obj, filename, 'application/octet-stream')
                print(f"[DEBUG] Đã upload file lên MinIO: {file_url}")
            except Exception as minio_error:
                print(f"[WARNING] Lỗi upload MinIO: {minio_error}")
                file_url = "minio_upload_failed"

            # Kiểm tra xem có phải file PDF không (dựa trên content hoặc tên file)
            is_pdf = False
            if filename.strip().lower().endswith('.pdf'):
                is_pdf = True
                print(f"[DEBUG] File có đuôi .pdf: {filename}")
            else:
                # Kiểm tra magic bytes của PDF
                if file_bytes[:4] == b'%PDF':
                    is_pdf = True
                    print(f"[DEBUG] File có magic bytes PDF nhưng không có đuôi .pdf: {filename}")
                else:
                    print(f"[DEBUG] File không phải PDF: {filename}")

            # Nếu là file PDF, trích xuất text và lưu vào file txt trong folder pdf_texts cùng cấp với main.py
            if is_pdf:
                print(f"[DEBUG] Bắt đầu extract text từ PDF: {filename}")
                try:
                    # Đọc PDF trực tiếp từ bytes thay vì từ MinIO
                    import PyPDF2
                    pdf_reader = PyPDF2.PdfReader(BytesIO(file_bytes))
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text() or ""
                    
                    print(f"[DEBUG] Độ dài text extract được: {len(text)} ký tự")
                    if text.strip():
                        print(f"[DEBUG] 200 ký tự đầu: {text[:200]}")
                        
                        # Tạo tên file .txt trong folder pdf_texts cùng cấp với main.py
                        if not filename.lower().endswith('.pdf'):
                            base_name = filename
                        else:
                            base_name = filename.rsplit('.', 1)[0]
                        
                        txt_filename = base_name + '.txt'
                        txt_folder = os.path.join(os.path.dirname(__file__), "pdf_texts")
                        os.makedirs(txt_folder, exist_ok=True)
                        txt_path = os.path.join(txt_folder, txt_filename)
                        
                        print(f"[DEBUG] Bắt đầu ghi file text vào: {txt_path}")
                        with open(txt_path, 'w', encoding='utf-8') as f:
                            f.write(text)
                        print(f"[DEBUG] Đã ghi file text vào: {txt_path}")
                        
                        return jsonify({
                            "status": "success", 
                            "file_url": file_url,
                            "txt_file": txt_filename,
                            "txt_path": txt_path,
                            "text_length": len(text),
                            "message": f"PDF uploaded and text extracted to {txt_filename}"
                        }), 200
                    else:
                        print(f"[WARNING] Không extract được text từ PDF hoặc file PDF là scan/image!")
                        return jsonify({
                            "status": "warning", 
                            "file_url": file_url,
                            "message": "PDF uploaded but no text could be extracted (possibly scanned/image PDF)"
                        }), 200
                        
                except Exception as pdf_exc:
                    print(f"[ERROR] Không extract được PDF: {pdf_exc}")
                    return jsonify({
                        "status": "error", 
                        "file_url": file_url,
                        "message": f"PDF uploaded but text extraction failed: {str(pdf_exc)}"
                    }), 200
            else:
                print(f"[DEBUG] File không phải PDF: {filename}")
                return jsonify({
                    "status": "success", 
                    "file_url": file_url,
                    "message": f"File {filename} uploaded successfully"
                }), 200

        except Exception as e:
            print(f"[ERROR] Lỗi xử lý file: {e}")
            return jsonify({"error": str(e)}), 500
    else:
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        try:
            # Upload lên MinIO
            try:
                file_url = upload_file_to_minio(file.stream, file.filename, file.content_type)
                print(f"[DEBUG] Đã upload file lên MinIO: {file_url}")
            except Exception as minio_error:
                print(f"[WARNING] Lỗi upload MinIO: {minio_error}")
                file_url = "minio_upload_failed"
            
            # Kiểm tra xem có phải file PDF không
            is_pdf = False
            if file.filename.lower().endswith('.pdf'):
                is_pdf = True
                print(f"[DEBUG] File có đuôi .pdf: {file.filename}")
            else:
                # Đọc một phần file để kiểm tra magic bytes
                file.stream.seek(0)
                header = file.stream.read(4)
                file.stream.seek(0)
                if header == b'%PDF':
                    is_pdf = True
                    print(f"[DEBUG] File có magic bytes PDF nhưng không có đuôi .pdf: {file.filename}")
                else:
                    print(f"[DEBUG] File không phải PDF: {file.filename}")
            
            # Nếu là file PDF, trích xuất text và lưu vào file txt trong folder pdf_texts cùng cấp với main.py
            if is_pdf:
                print(f"[DEBUG] Bắt đầu extract text từ PDF: {file.filename}")
                try:
                    # Đọc PDF trực tiếp từ file stream
                    import PyPDF2
                    file.stream.seek(0)  # Reset stream position
                    pdf_reader = PyPDF2.PdfReader(file.stream)
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text() or ""
                    
                    print(f"[DEBUG] Độ dài text extract được: {len(text)} ký tự")
                    if text.strip():
                        print(f"[DEBUG] 200 ký tự đầu: {text[:200]}")
                        
                        # Tạo tên file .txt trong folder pdf_texts cùng cấp với main.py
                        if not file.filename.lower().endswith('.pdf'):
                            base_name = file.filename
                        else:
                            base_name = file.filename.rsplit('.', 1)[0]
                        
                        txt_filename = base_name + '.txt'
                        txt_folder = os.path.join(os.path.dirname(__file__), "pdf_texts")
                        os.makedirs(txt_folder, exist_ok=True)
                        txt_path = os.path.join(txt_folder, txt_filename)
                        
                        print(f"[DEBUG] Bắt đầu ghi file text vào: {txt_path}")
                        with open(txt_path, 'w', encoding='utf-8') as f:
                            f.write(text)
                        print(f"[DEBUG] Đã ghi file text vào: {txt_path}")
                        
                        return jsonify({
                            "status": "success", 
                            "file_url": file_url,
                            "txt_file": txt_filename,
                            "txt_path": txt_path,
                            "text_length": len(text),
                            "message": f"PDF uploaded and text extracted to {txt_filename}"
                        }), 200
                    else:
                        print(f"[WARNING] Không extract được text từ PDF hoặc file PDF là scan/image!")
                        return jsonify({
                            "status": "warning", 
                            "file_url": file_url,
                            "message": "PDF uploaded but no text could be extracted (possibly scanned/image PDF)"
                        }), 200
                        
                except Exception as pdf_exc:
                    print(f"[ERROR] Không extract được PDF: {pdf_exc}")
                    return jsonify({
                        "status": "error", 
                        "file_url": file_url,
                        "message": f"PDF uploaded but text extraction failed: {str(pdf_exc)}"
                    }), 200
            else:
                print(f"[DEBUG] File không phải PDF: {file.filename}")
                return jsonify({
                    "status": "success", 
                    "file_url": file_url,
                    "message": f"File {file.filename} uploaded successfully"
                }), 200
                
        except Exception as e:
            print(f"[ERROR] Lỗi xử lý file: {e}")
            return jsonify({"error": str(e)}), 500


# route hỏi câu hỏi về file PDF đã upload
# Hàm này sẽ lấy nội dung PDF từ MinIO và gửi câu hỏi đến AI để trả lời
@app.route('/pdf/ask', methods=['POST'])
def ask_pdf():
    data = request.get_json()
    filename = data.get('filename')
    messages = data.get('messages')
    question = None
    if messages and isinstance(messages, list):
        question = messages[-1]['content'] if messages else None
    else:
        question = data.get('question')
    if not question:
        return jsonify({"error": "Missing question"}), 400

    # 1. Truy vấn DB trước (giả sử có hàm search_in_db)
    db_result = search_in_db(question)
    if db_result:
        return jsonify({"source": "database", "answer": db_result}), 200

    # 2. Nếu có file PDF, thử tìm trong PDF
    if filename:
        try:
            pdf_text = get_pdf_text_from_minio(filename)
            # Luôn prepend message system hướng dẫn AI về ngôn ngữ và vai trò
            system_message = {
                "role": "system",
                "content": (
                    "Bạn là trợ lý AI thông minh, luôn trả lời bằng cùng ngôn ngữ với người dùng. "
                    "Nếu người dùng viết tắt, sai chính tả, hãy tự động hiểu và trả lời đúng ý họ. "
                    "Nếu có nội dung tài liệu, hãy ưu tiên trả lời dựa trên tài liệu đó."
                )
            }
            if messages and isinstance(messages, list):
                pdf_system_message = {"role": "system", "content": f"Nội dung tài liệu:\n{pdf_text}"}
                full_messages = [system_message, pdf_system_message] + messages
                pdf_answer = process_ai_request(messages=full_messages)
            else:
                prompt = (
                    "Bạn là trợ lý AI thông minh, luôn trả lời bằng cùng ngôn ngữ với người dùng. "
                    "Nếu người dùng viết tắt, sai chính tả, hãy tự động hiểu và trả lời đúng ý họ. "
                    "Nếu có nội dung tài liệu, hãy ưu tiên trả lời dựa trên tài liệu đó.\n" +
                    f"Nội dung tài liệu:\n{pdf_text}\n\nCâu hỏi: {question}\nTrả lời:"
                )
                pdf_answer = process_ai_request(user_query=prompt)
            if pdf_answer and pdf_answer.strip():
                return jsonify({"source": "pdf", "answer": pdf_answer}), 200
        except Exception as e:
            print(f"Error reading PDF: {e}")
            return jsonify({"error": f"Error reading PDF: {e}"}), 500

    # 3. Nếu không có, hỏi AI gốc
    try:
        # Luôn prepend message system cho chat thường
        system_message = {
            "role": "system",
            "content": (
                "Bạn là trợ lý AI thông minh, luôn trả lời bằng cùng ngôn ngữ với người dùng. "
                "Nếu người dùng viết tắt, sai chính tả, hãy tự động hiểu và trả lời đúng ý họ."
            )
        }
        if messages and isinstance(messages, list):
            full_messages = [system_message] + messages
            api_answer = process_ai_request(messages=full_messages)
        else:
            prompt = (
                "Bạn là trợ lý AI thông minh, luôn trả lời bằng cùng ngôn ngữ với người dùng. "
                "Nếu người dùng viết tắt, sai chính tả, hãy tự động hiểu và trả lời đúng ý họ.\n" +
                question
            )
            api_answer = process_ai_request(user_query=prompt)
        if api_answer and api_answer.strip():
            return jsonify({"source": "api", "answer": api_answer}), 200
        else:
            return jsonify({"error": "Không tìm thấy câu trả lời phù hợp."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def search_in_db(question):
    # TODO: Thay thế bằng truy vấn DB thực tế nếu cần
    # Ví dụ: nếu câu hỏi chứa từ khóa đặc biệt thì trả về kết quả mẫu
    if "xin chào" in question.lower():
        return "Chào bạn! Đây là câu trả lời từ database."
    return None

if __name__ == '__main__':
    app.run(debug=True, port=5000) # Chạy ứng dụng Flask trên cổng 5000

