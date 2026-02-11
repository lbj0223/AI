import sys
import io
from openai import OpenAI

# 强制 Python 输出使用 UTF-8 编码，解决你遇到的 ascii 报错
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 请确保填写你真实的 DeepSeek API Key
client = OpenAI(api_key="sk-0af76a43d8224550b8aacc3637fd3ab7", base_url="https://api.deepseek.com")

def test_connectivity():
    print("--- 正在测试‘题镜 AI’大脑连通性 ---")
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你现在是题镜 AI 助教。"},
                {"role": "user", "content": "你好，请确认你的身份。"},
            ],
            stream=False
        )
        print("\n[连通成功！]")
        print("AI 回复内容：", response.choices[0].message.content)
    except Exception as e:
        print("\n[连通失败]")
        # 捕捉并打印错误，同时处理编码
        print("错误原因：", str(e))

if __name__ == "__main__":
    test_connectivity()