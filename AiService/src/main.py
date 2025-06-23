import os 
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from .ai_processor import process_ai_request
# from .vector_ultils import intialize_vector_store

app = Flask(__name__)
CORS(app, resources={r"/data/process": {"origins": "http://localhost:5173"}})
@app.route('/')
def index():
    return "AI Service is running!"

@app.route('/data/process', methods=['POST'])
def handle_data_from_node():
    data = request.json
    print(f"Received data from frontend: {data['user_query']}")
    # print(f"Type of data: {type(data)}")
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    try:
        response = process_ai_request(data['user_query'])
        return jsonify(response), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
if __name__ == '__main__':
    app.run(debug=True, port=5000) # Chạy ứncg dụng Flask trên cổng 5000