# backend_python/ai_processor.py
import os
import requests # Bạn cần cài đặt thư viện 'requests': pip install requests

def process_ai_request(user_query: str) -> str:
    """
    Xử lý yêu cầu AI bằng cách gọi một API AI bên ngoài (ví dụ: OpenAI).

    Args:
        user_query (str): Câu hỏi hoặc dữ liệu đầu vào từ người dùng.

    Returns:
        str: Phản hồi đã xử lý từ API AI.

    Raises:
        ValueError: Nếu khóa API không được tìm thấy.
        requests.exceptions.RequestException: Nếu có lỗi khi gọi API AI.
    """
    # 1. Lấy API Key từ biến môi trường
    # Đảm bảo bạn đã đặt OPENAI_API_KEY trong file .env của mình
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set in environment variables.")

    # 2. Định nghĩa URL và headers cho API AI
    # Đây là ví dụ cho OpenAI Chat Completions API
    BASE_API_URL =os.getenv("BASE_API_URL")
    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json"
    }

    # 3. Chuẩn bị payload (dữ liệu gửi đi) cho API AI
    payload = {
        "model": "owen-alibaba", # Hoặc mô hình khác như "gpt-4"
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": user_query}
        ],
        "max_tokens": 150, # Giới hạn độ dài phản hồi
        "temperature": 0.7 # Độ "sáng tạo" của phản hồi
    }

    print(f"Sending query to AI: {user_query}")

    try:
        # 4. Gửi yêu cầu POST đến API AI
        response = requests.post(BASE_API_URL, headers=headers, json=payload, timeout=60) # Thêm timeout
        response.raise_for_status() # Ném lỗi nếu trạng thái HTTP là 4xx hoặc 5xx

        # 5. Xử lý phản hồi từ API AI
        ai_response_data = response.json()
        
        # Kiểm tra xem phản hồi có đúng định dạng không
        if 'choices' in ai_response_data and len(ai_response_data['choices']) > 0:
            ai_message = ai_response_data['choices'][0]['message']['content']
            print(f"Received AI response: {ai_message}")
            return ai_message
        else:
            # Xử lý trường hợp không có lựa chọn hoặc phản hồi không mong muốn
            print(f"Unexpected AI response format: {ai_response_data}")
            return "Sorry, I couldn't get a clear response from the AI."

    except requests.exceptions.Timeout:
        raise requests.exceptions.RequestException("AI API request timed out.")
    except requests.exceptions.ConnectionError:
        raise requests.exceptions.RequestException("Could not connect to AI API.")
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err} - Response: {response.text}")
        raise requests.exceptions.RequestException(f"AI API returned an error: {response.text}")
    except Exception as e:
        print(f"An unexpected error occurred during AI processing: {e}")
        raise requests.exceptions.RequestException(f"An unexpected error occurred: {e}")

# Các hàm xử lý AI khác có thể được thêm vào đây
# def process_image_with_ai(image_data):
#     # Logic xử lý ảnh với AI
#     pass