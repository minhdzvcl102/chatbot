# backend_python/ai_processor.py
import os
# Import client của OpenAI SDK
from openai import OpenAI, APIError, APIConnectionError, RateLimitError 
from dotenv import load_dotenv
client = OpenAI(
    api_key=os.getenv("ALIBABA_CLOUD_API_KEY"), # Lấy API Key từ .env
    base_url=os.getenv("ALIBABA_CLOUD_API_BASE") # Trỏ đến endpoint tương thích của Alibaba Cloud từ .env
)
system_message = {
    "role": "system",
    "content": (
        "Bạn là trợ lý AI thông minh, luôn trả lời bằng cùng ngôn ngữ với người dùng. "
        "Nếu người dùng viết tắt, sai chính tả, hãy tự động hiểu và trả lời đúng ý họ. "
        "Nếu có nội dung tài liệu, hãy ưu tiên trả lời dựa trên tài liệu đó."
    )
}
def process_ai_request(user_query: str = None, messages: list = None) -> str:
    """
    Xử lý yêu cầu AI bằng cách gọi OpenAI SDK (hoặc Alibaba Cloud endpoint tương thích).
    Tự động tiếp tục trả lời nếu bị cắt (finish_reason == 'length').
    Nếu truyền messages thì dùng luôn, nếu không thì tạo từ user_query.
    """
    if not client.api_key:
        raise ValueError("ALIBABA_CLOUD_API_KEY is not set in environment variables.")
    if not client.base_url:
        raise ValueError("ALIBABA_CLOUD_API_BASE is not set in environment variables.")

    alibaba_model_name = "qwen-turbo" 
    print(f"Sending query to Alibaba Cloud AI (via OpenAI SDK): {user_query if user_query else '[messages]'} using model {alibaba_model_name}")

    try:
        # Nếu có messages (mảng hội thoại), dùng luôn, nếu không thì tạo từ user_query
        if messages and isinstance(messages, list):
            chat_messages = messages
        else:
            chat_messages = [
                system_message,
                {"role": "user", "content": user_query}
            ]
        full_response = ""
        max_loops = 5  # tránh lặp vô hạn nếu model luôn trả về finish_reason == 'length'
        for _ in range(max_loops):
            completion = client.chat.completions.create(
                model=alibaba_model_name,
                messages=chat_messages,
                max_tokens=2048,  # Tăng giới hạn token
                temperature=0.7,
            )
            if completion.choices and len(completion.choices) > 0:
                ai_message = completion.choices[0].message.content
                finish_reason = getattr(completion.choices[0], 'finish_reason', None)
                print(f"Received AI response (finish_reason={finish_reason}): {ai_message}")
                full_response += ai_message
                if finish_reason == "length":
                    chat_messages.append({"role": "assistant", "content": ai_message})
                    chat_messages.append({"role": "user", "content": "Tiếp tục trả lời phần còn lại của câu hỏi trước."})
                    continue
                else:
                    return full_response
            else:
                print(f"Unexpected AI response format: {completion}")
                raise Exception(f"AI API returned unexpected format: {completion}")
        # Nếu lặp quá max_loops mà vẫn bị cắt, trả về những gì đã có
        return full_response
    except APIError as e:
        print(f"Alibaba Cloud API Error: Status Code: {e.status_code}, Response: {e.response}")
        raise Exception(f"AI API error: {e.message}")
    except APIConnectionError as e:
        print(f"Alibaba Cloud API Connection Error: {e}")
        raise Exception(f"Failed to connect to AI API: {e}")
    except RateLimitError as e:
        print(f"Alibaba Cloud API Rate Limit Exceeded: {e}")
        raise Exception(f"AI API rate limit exceeded: {e.message}")
    except Exception as e:
        print(f"An unexpected error occurred during AI processing: {e}")
        raise Exception(f"An internal error occurred: {e}")