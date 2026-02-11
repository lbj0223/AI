# ============================================
# 题镜 AI - 智能错题变式系统
# 核心功能：OCR识别 -> AI分析 -> 变式生成 -> 知识图谱
# 开发者：LBJ
# ============================================

# 导入必要的第三方库
import streamlit as st                    # Streamlit Web框架
from pix2tex.cli import LatexOCR         # 数学公式OCR识别库
from PIL import Image                    # 图像处理库
from openai import OpenAI                # DeepSeek AI大模型API
import json                              # JSON数据处理
import psycopg2                          # PostgreSQL数据库连接
from psycopg2.extras import Json         # PostgreSQL JSON字段支持
# 数据库统一配置（请确保信息与你 pgAdmin 中的一致）
# 1. 放在文件顶部的全局配置
db_config = st.secrets["postgres"]

# 2. 在具体函数里使用（例如你之前的 fetch_history）
def fetch_history():
    try:
        # 每次调用时才建立连接，用完就关，这样最稳定
        conn = psycopg2.connect(**db_config)
        # ... 你的代码逻辑 ...
    except Exception as e:
        st.error(f"连接失败: {e}")
# ============================================
# 1. 核心配置初始化
# ============================================

# 初始化DeepSeek AI大模型客户端
# 注意：请在生产环境中使用环境变量存储API密钥
client = OpenAI(
    api_key=st.secrets["DEEPSEEK_KEY"],
    base_url="https://api.deepseek.com"
)

# ============================================
# 2. Session状态管理
# 用于在用户会话期间持久化数据
# ============================================

# 初始化会话状态变量
if 'latex_result' not in st.session_state:
    st.session_state.latex_result = ""      # 存储OCR识别的LaTeX公式结果
if 'ai_data' not in st.session_state:
    st.session_state.ai_data = None         # 存储AI分析生成的数据


# ============================================
# 3. 数据库操作函数
# ============================================
def save_to_db(latex, ai_data):
    """
    将识别结果和AI分析数据保存到PostgreSQL数据库
    
    参数:
        latex (str): OCR识别出的LaTeX公式
        ai_data (dict): AI分析生成的知识点和变式数据
    
    返回:
        bool: 保存成功返回True，失败返回False
    """
    try:
        # 建立数据库连接
        conn = psycopg2.connect(
            dbname="AI",          # 数据库名称
            user="postgres",      # 用户名
            password="123456",    # 密码
            host="198.181.34.168",     # 主机地址
            port="5432"           # 端口号
        )
        cur = conn.cursor()

        # 准备SQL插入语句
        query = """
        INSERT INTO tj_ai_records (original_latex, analysis_json, exercises_json)
        VALUES (%s, %s, %s)
        """

        # 执行插入操作
        # Json()函数自动将Python字典转换为PostgreSQL的JSONB格式
        cur.execute(query, (
            latex,                    # 原始LaTeX公式
            Json(ai_data['card']),    # 知识点分析卡片
            Json(ai_data['exercises']) # 变式练习数据
        ))

        conn.commit()  # 提交事务
        cur.close()
        conn.close()
        return True
    except Exception as e:
        # 错误处理：在Web界面显示具体错误信息
        st.error(f"数据库写入失败：{e}")
        return False

def fetch_history():
    try:
        conn = psycopg2.connect(
            dbname="AI",
            user="postgres",
            password="123456",
            host="198.181.34.168",
            port="5432"
        )
        cur = conn.cursor()
        # 按时间倒序查出最近的 5 条
        cur.execute("SELECT id, original_latex, created_at FROM tj_ai_records ORDER BY created_at DESC LIMIT 5")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        st.error(f"读取历史失败：{e}")
        return []


def clear_history():
    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        # 谨慎操作：清空所有记录
        cur.execute("DELETE FROM tj_ai_records")
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"清空失败：{e}")
        return False


# ============================================
# 4. Streamlit页面配置和主界面
# ============================================

# 配置页面基本信息
st.set_page_config(
    page_title="题镜 AI",      # 浏览器标签页标题
    layout="wide"             # 宽屏布局，更适合数据分析展示
)

# 页面主标题
st.title("题镜 AI —— 智能错题变式系统")


# ============================================
# 5. 侧边栏 - 历史记录看板
# ============================================
with st.sidebar:
    st.header("🕒 历史记录看板")
    
    # 获取历史记录数据
    history = fetch_history()
    
    if history:
        # 遍历显示每条历史记录
        for row in history:
            # row[0]: 记录ID, row[1]: LaTeX公式, row[2]: 创建时间
            with st.expander(f"题目 ID: {row[0]} ({row[2].strftime('%m-%d %H:%M')})"):
                st.latex(row[1])  # 以数学公式形式显示
                st.info("可在 Django 后台查看完整变式")
    else:
        # 无历史记录时的提示
        st.write("暂无历史记录，快去上传第一道题吧！")
    st.divider()
    if st.button("🗑️ 清空所有历史"):
        if clear_history():
            st.toast("历史记录已全部清空", icon="🧹")
            st.rerun()  # 强制刷新页面，看到空白看板

# 页面副标题 - 核心理念说明
st.caption("核心理念：‘拍一题，练三题，通一类’")


# ============================================
# 6. 核心功能模块
# ============================================

# --- 第一部分：错题录入 (图像上传和OCR识别) ---
col1, col2 = st.columns([1, 1])  # 创建两列布局

with col1:
    st.header("📸 第一步：错题录入")
    
    # 文件上传组件
    uploaded_file = st.file_uploader(
        "上传题目图片", 
        type=["png", "jpg", "jpeg"]  # 支持的图片格式
    )

    if uploaded_file:
        # 显示上传的图片
        img = Image.open(uploaded_file)
        st.image(img, caption="原始题目", width="stretch")

        # OCR识别按钮
        if st.button("开始高精度 OCR 识别"):
            with st.spinner("题镜 AI 正在通过图片还原题目 DNA..."):
                # 初始化LaTeX OCR模型
                model = LatexOCR()
                # 执行OCR识别
                st.session_state.latex_result = model(img)
                # 重新运行页面以更新状态
                st.rerun()

with col2:
    st.header("🧠 第二步：智能分析")
    
    # 只有在OCR识别完成后才显示分析功能
    if st.session_state.latex_result:
        st.subheader("题目无损还原 (LaTeX):")
        # 以数学公式形式显示识别结果
        st.latex(st.session_state.latex_result)

        # AI分析按钮
        if st.button("✨ 第三步：构建变式与知识图谱"):
            with st.spinner("AI 正在深度解析考点并生成练习..."):
                # 构造AI提示词
                prompt = f"""
                你现在是"题镜 AI"专家。识别出的题目公式为：{st.session_state.latex_result}
                请严格按 JSON 格式输出：
                {{
                  "card": {{ "point": "考点名称", "concept": "一句话概念复习", "tip": "解题关键技巧" }},
                  "exercises": [
                    {{ "type": "平行变式", "q": "题目内容", "a": "解析内容" }},
                    {{ "type": "进阶变式", "q": "题目内容", "a": "解析内容" }},
                    {{ "type": "应用变式", "q": "题目内容", "a": "解析内容" }}
                  ]
                }}
                """
                
                try:
                    # 调用DeepSeek AI大模型
                    response = client.chat.completions.create(
                        model="deepseek-chat",                    # 使用DeepSeek聊天模型
                        messages=[{"role": "user", "content": prompt}],
                        response_format={'type': 'json_object'}   # 要求JSON格式响应
                    )
                    # 解析AI返回的JSON数据
                    st.session_state.ai_data = json.loads(response.choices[0].message.content)
                except Exception as e:
                    # 错误处理
                    st.error(f"分析失败：{e}")

# --- 【重点】第三部分：结果展示区 ---
# 只有AI分析完成后才显示结果
if st.session_state.ai_data:
    st.divider()  # 分割线
    data = st.session_state.ai_data

    # ============================================
    # 7. 知识复习卡片展示
    # ============================================
    st.markdown("### 📘 知识复习卡片")
    
    # 创建三列布局展示知识点
    c1, c2, c3 = st.columns(3)
    with c1:
        st.info(f"**核心考点**\n\n{data['card']['point']}")
    with c2:
        st.info(f"**核心概念**\n\n{data['card']['concept']}")
    with c3:
        st.info(f"**解题大招**\n\n{data['card']['tip']}")


    # ============================================
    # 8. 变式分级强化训练
    # ============================================
    st.markdown("### ✍️ 变式分级强化训练")

    # 不同题型的样式配置映射
    style_map = {
        "平行变式": {"icon": "🟢", "label": "基础巩固", "help": "巩固原题逻辑，变换数值场景"},
        "进阶变式": {"icon": "🟡", "label": "思维挑战", "help": "增加干扰条件，训练高阶思维"},
        "应用变式": {"icon": "🔴", "label": "跨界迁移", "help": "结合生活场景，提升迁移能力"}
    }

    # 遍历展示每个变式题目
    for ex in data['exercises']:
        # 获取当前题型的样式配置
        config = style_map.get(ex['type'], {"icon": "🔹", "label": "拓展练习", "help": ""})

        # 使用可折叠的状态卡片展示
        with st.status(f"{config['icon']} {ex['type']} —— {config['label']}", expanded=False):
            st.write(f"*{config['help']}*")
            
            # 显示题目内容
            st.markdown(f"**【题目内容】**")
            st.markdown(ex['q'])

            st.divider()

            # 显示AI解析内容
            st.markdown(f"**【题镜 AI 深度解析】**")
            st.success(ex['a'])


    # ============================================
    # 9. 数据保存功能
    # ============================================
    st.write("---")
    
    # 创建保存区域布局
    col_db1, col_db2 = st.columns([1, 2])

    with col_db1:
        # 保存到数据库按钮
        if st.button("💾 存入 AI 错题本"):
            with st.spinner("数据正在同步至云端 PostgreSQL..."):
                # 调用数据库保存函数
                success = save_to_db(st.session_state.latex_result, data)
                if success:
                    # 保存成功的反馈
                    st.toast("入库成功！已自动更新个人学情档案", icon="✅")
                    st.success("本题已存入 PostgreSQL 数据库，可用于后续 Django 后台调用。")
    
    # 庆祝动画效果
    st.balloons()