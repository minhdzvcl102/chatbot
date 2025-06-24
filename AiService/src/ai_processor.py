# backend_python/ai_processor.py
import os
# Import client của OpenAI SDK
from openai import OpenAI, APIError, APIConnectionError, RateLimitError 
from dotenv import load_dotenv
client = OpenAI(
    api_key=os.getenv("ALIBABA_CLOUD_API_KEY"), # Lấy API Key từ .env
    base_url=os.getenv("ALIBABA_CLOUD_API_BASE") # Trỏ đến endpoint tương thích của Alibaba Cloud từ .env
)
def process_ai_request(user_query: str) -> str:
    """
    Xử lý yêu cầu AI bằng cách gọi Alibaba Cloud DashScope thông qua OpenAI SDK.

    Args:
        user_query (str): Câu hỏi hoặc dữ liệu đầu vào từ người dùng (phải là chuỗi).

    Returns:
        str: Phản hồi đã xử lý từ API AI.
    """
    # Kiểm tra xem các biến môi trường cần thiết có được tải không
    if not client.api_key:
        raise ValueError("ALIBABA_CLOUD_API_KEY is not set in environment variables.")
    if not client.base_url:
        raise ValueError("ALIBABA_CLOUD_API_BASE is not set in environment variables.")

    alibaba_model_name = "qwen-turbo" 

    print(f"Sending query to Alibaba Cloud AI (via OpenAI SDK): {user_query} using model {alibaba_model_name}")

    try:
        # Sử dụng client.chat.completions.create giống hệt như với OpenAI gốc
        completion = client.chat.completions.create(
            model=alibaba_model_name,
            messages=[
                {"role": "user", "content": user_query}
            ],
            max_tokens=150, # Giới hạn độ dài phản hồi
            temperature=0.7, # Độ "sáng tạo" của phản hồi
            # timeout=60.0 # Timeout có thể được đặt trực tiếp trong create() nếu SDK hỗ trợ
        )

        # Trích xuất phản hồi giống như với OpenAI SDK
        if completion.choices and len(completion.choices) > 0:
            ai_message = completion.choices[0].message.content
            print(f"Received AI response: {ai_message}")
            return ai_message
        else:
            print(f"Unexpected Alibaba Cloud AI response format: {completion}")
            raise Exception(f"Alibaba Cloud AI API returned unexpected format: {completion}")

    except APIError as e:
        # Lỗi từ API (ví dụ: Invalid API Key, Rate Limit Exceeded, Model Not Found)
        print(f"Alibaba Cloud API Error: Status Code: {e.status_code}, Response: {e.response}")
        raise Exception(f"AI API error: {e.message}")
    except APIConnectionError as e:
        # Lỗi kết nối mạng (ví dụ: không thể kết nối tới URL)
        print(f"Alibaba Cloud API Connection Error: {e}")
        raise Exception(f"Failed to connect to AI API: {e}")
    except RateLimitError as e:
        # Lỗi vượt quá giới hạn rate limit
        print(f"Alibaba Cloud API Rate Limit Exceeded: {e}")
        raise Exception(f"AI API rate limit exceeded: {e.message}")
    except Exception as e:
        # Bất kỳ lỗi nào khác
        print(f"An unexpected error occurred during AI processing: {e}")
        raise Exception(f"An internal error occurred: {e}")