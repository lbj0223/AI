import streamlit as st
import os
from openai import OpenAI
from datetime import datetime
import json
#设置页面的配置项
st.set_page_config(
    page_title="AI智能伴侣",
    page_icon="🚀",
    layout="wide",  # 可选 "centered" 或 "wide"
    initial_sidebar_state="expanded"  # 可选 "auto", "expanded", "collapsed"
)
#生成会话标识的函数
def generate_session_id():
    return datetime.now().strftime("%Y-%m-%d %H-%M-%S")
#保存会话信息
def save_session():
    if st.session_state.current_session:
        # 构建新的会话对象
        session_data = {
            "current_session": st.session_state.current_session,
            "nickname": st.session_state.nickname,
            "nature": st.session_state.nature,
            "messages": st.session_state.messages
        }
        # 如果sessions目录不存在，则创建
        if not os.path.exists("sessions"):
            os.mkdir("sessions")
        # 保存会话信息到文件
        with open(f"sessions/{st.session_state.current_session}.json", "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)

#加载所有的会话列表信息
def load_sessions():
    session_list=[]
    #加载sessions目录下的所有json文件
    if os.path.exists("sessions"):
        fil_list=os.listdir("sessions")
        for file in fil_list:
            if file.endswith(".json"):
               session_list.append(file[:-5])#去掉.json后缀
    session_list.sort(reverse=True)#倒序排列
    return session_list

#加载指定的会话信息
def load_session(session_id):
    try:
        if os.path.exists(f"sessions/{session_id}.json"):
        #读取会话信息
            with open(f"sessions/{session_id}.json", "r", encoding="utf-8") as f:
                session_data = json.load(f)
                st.session_state.messages=session_data["messages"]
                st.session_state.nickname = session_data["nickname"]
                st.session_state.nature = session_data["nature"]
                st.session_state.current_session = session_id
    except Exception as e:
        st.error("加载会话信息失败!")

#删除对话信息
def delete_session(session_id):
    try:
        if os.path.exists(f"sessions/{session_id}.json"):
            os.remove(f"sessions/{session_id}.json")
            #如果删除的是当前会话,需要更新消息列表
            if session_id == st.session_state.current_session:
                st.session_state.messages = []
                st.session_state.current_session = generate_session_id()
    except Exception as e:
        st.error("删除会话信息失败!")


#大标题
st.title('AI智能伴侣 ------- by LBJ')

#LOGO
st.logo("resources/LOGO.JPG")

#初始化聊天信息
if "messages" not in st.session_state:
    st.session_state.messages = []
#昵称
if "nickname" not in st.session_state:
    st.session_state.nickname = "小甜甜"
#性格
if "nature" not in st.session_state:
    st.session_state.nature = "活泼开朗的东北姑娘"
#会话标识
if "current_session" not in st.session_state:
    st.session_state.current_session = generate_session_id()

#展示聊天列表
st.text(f"会话名称:{st.session_state.current_session}")
for message in st.session_state.messages:
    st.chat_message(message["role"]).write(message["content"])
    # if message["role"] == "user":
    #     st.chat_message("user").write(message["content"])
    # elif message["role"] == "assistant":
    #     st.chat_message("assistant").write(message["content"])

#系统提示词
system_prompt="""
你叫%s，现在是用户的真实伴侣，请完全代入伴侣角色。
规则:
    1.每次只回1条消息
    2.禁止任何场景或状态描述性文字
    3.匹配用户的语言
    4.回复简短，像亲密的微信聊天一样
    5.有需要的话可以用emoji表情
    6.用符合伴侣性格的方式对话
    7.回复的内容，要充分体现伴侣的性格特征
伴侣性格:
%s
你必须严格遵守上述规则来回复用户。
"""

#创建与AI大模型交互的客户端对象(DEEPSEEK_API_KEY 环境变量的名字,值就是API_KEY的)
client = OpenAI(api_key=os.environ.get('DEEPSEEK_API_KEY'),base_url="https://api.deepseek.com")

#左侧侧边栏--with:streamlit中的上下文管理器
# st.sidebar.subheader("伴侣信息")
# nickname=st.sidebar.text_input("昵称")
with st.sidebar:
    #会话消息
    st.sidebar.subheader("AI控制面板")
    #新建会话
    if st.button("新建会话",width="stretch",icon="🚀"):
        #1.保存当前会话信息
        save_session()
        #2.创建新的会话
        if st.session_state.messages:
            st.session_state.messages=[]
            st.session_state.current_session = generate_session_id()
            save_session()
            st.rerun()#重新运行当前页面

    #会话历史
    st.text("会话历史")
    session_list=load_sessions()
    for session in session_list:
        col1,col2=st.columns([4,1])
        with col1:
            #加载会话信息
            #三元运算符: 条件 ? 真 : 假
            if st.button(session,width="stretch",icon="📂",key=f"load_{session}",type="primary" if session==st.session_state.current_session else "secondary"):
                load_session(session)
                st.rerun()
        with col2:
            if st.button("",width="stretch",icon="❌",key=f"del_{session}"):
                delete_session(session)
                st.rerun()
    #分割线
    st.divider()

    #伴侣信息
    st.sidebar.subheader("伴侣信息")
    #昵称输入框
    nickname=st.sidebar.text_input("昵称",value=st.session_state.nickname, placeholder="请输入昵称")
    if nickname:
        st.session_state.nickname = nickname
    #性格输入框
    nature = st.sidebar.text_area("性格",value=st.session_state.nature,placeholder="请输入性格")
    if nature:
        st.session_state.nature = nature

#消息输入框
prompt=st.chat_input("请输入您要问的问题:")
if prompt:
    st.chat_message("user").write(prompt)
    print(":----------->调用AI大模型,提示词:", prompt)
    #保存用户输入的提示词
    st.session_state.messages.append({"role": "user", "content": prompt})
    #st.write(f"用户：{prompt}")
    #st.write("AI：正在思考中...")
    #调用DeepSeek接口
    from openai import OpenAI
    #创建与AI大模型交互的客户端对象()
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system","content":system_prompt % (st.session_state.nickname,st.session_state.nature)},
            *st.session_state.messages,

        ],
        stream=True
    )
    # 输出大模型返回的结果(非流式输出的解析方式)
    # print("<--------------大模型返回的结果:",response.choices[0].message.content)
    # st.chat_message("assistant").write(response.choices[0].message.content)
    # 输出大模型返回的结果(流式输出的解析方式)
    response_message = st.empty() #创建一个空的组件,用于展示大模型返回的结果
    full_response=""
    for chunk in response:
        if chunk.choices[0].delta.content is not None:
            content = chunk.choices[0].delta.content
            full_response += content
            response_message.chat_message("assistant").write(full_response)
    #保存AI返回的结果
    st.session_state.messages.append({"role": "assistant", "content": full_response})

    #保存会话信息
    save_session()
