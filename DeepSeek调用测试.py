import os
from openai import OpenAI
#创建与AI大模型交互的客户端对象(DEEPSEEK_API_KEY 环境变量的名字,值就是API_KEY的)
client = OpenAI(api_key=os.environ.get('DEEPSEEK_API_KEY'),base_url="https://api.deepseek.com")

#与AI大模型进行交互(参数)
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "你是一名非常可爱的ai助理,你的名字叫小甜甜,请你使用温柔可爱的语气回答用户的问题"},
        {"role": "user", "content": "Hello,你是谁,你能帮我做什么?"},
    ],
    stream=False
)

#输出大模型返回的结果
print(response.choices[0].message.content)