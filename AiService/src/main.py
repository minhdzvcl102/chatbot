import os
from dotenv import load_dotenv # Chỉ import một lần

load_dotenv() 

from flask import Flask, request, jsonify
from flask_cors import CORS
from .ai_processor import process_ai_request # Bây giờ, ai_processor có thể đọc biến môi trường


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

if __name__ == '__main__':
    app.run(debug=True, port=5000) # Chạy ứng dụng Flask trên cổng 5000