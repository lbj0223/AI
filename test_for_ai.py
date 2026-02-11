# ============================================
# 题镜 AI - 智能错题变式系统
# 核心功能：OCR识别 -> AI分析 -> 变式生成 -> 云端存储
# 开发者：LBJ
# ============================================

import streamlit as st
from pix2tex.cli import LatexOCR
from PIL import Image
from openai import OpenAI
import json
import psycopg2
from psycopg2.extras import Json

# ============================================
# 1. 核心配置与数据库初始化
# ============================================

# 从 Streamlit Secrets 读取统一配置
db_config = st.secrets["postgres"]
DEEPSEEK_KEY = st.secrets["DEEPSEEK_KEY"]

# 初始化 DeepSeek 客户端
client = OpenAI(
    api_key=DEEPSEEK_KEY,
    base_url="https://api.deepseek.com"
)

# 初始化会话状态
if 'latex_result' not in st.session_state:
    st.session_state.latex_result = ""
if 'ai_data' not in st.session_state:
    st.session_state.ai_data = None


# ============================================
# 2. 数据库操作函数 (全部对齐 Neon 云端)
# ============================================

def get_db_connection():
    """统一获取带 SSL 的云端数据库连接"""
    return psycopg2.connect(**db_config, sslmode='require')


def save_to_db(latex, ai_data):
    """保存识别结果和AI分析到 Neon 云端"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # 注意：表名已改为你在 Neon SQL Editor 中创建的 error_questions
        query = """
        INSERT INTO error_questions (ocr_latex, analysis, variants)
        VALUES (%s, %s, %s)
        """

        cur.execute(query, (
            latex,  # 原始公式
            Json(ai_data['card']),  # 知识点分析
            Json(ai_data['exercises'])  # 变式练习内容
        ))

        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"云端同步失败：{e}")
        return False


def fetch_history():
    """从云端获取历史记录"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # 查询 Neon 云端表数据
        cur.execute("SELECT id, ocr_latex, created_at FROM error_questions ORDER BY created_at DESC LIMIT 5")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        # 如果是第一次运行，表还没创建，这里会静默处理
        return []


def clear_history():
    """清空云端所有历史记录"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM error_questions")
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"云端清空失败：{e}")
        return False


# ============================================
# 3. Streamlit UI 界面 (保持原样，仅做微调)
# ============================================

st.set_page_config(page_title="题镜 AI", layout="wide")
st.title("题镜 AI —— 智能错题变式系统")

# --- 侧边栏：云端历史看板 ---
with st.sidebar:
    st.header("🕒 云端历史看板")
    history = fetch_history()
    if history:
        for row in history:
            with st.expander(f"题目 ID: {row[0]} ({row[2].strftime('%m-%d %H:%M')})"):
                st.latex(row[1])
    else:
        st.write("暂无历史记录，快去上传第一道题吧！")

    st.divider()
    if st.button("🗑️ 清空所有云端历史"):
        if clear_history():
            st.toast("云端数据已扫除", icon="🧹")
            st.rerun()

st.caption("核心理念：‘拍一题，练三题，通一类’")

# --- 主界面：录入与分析 ---
col1, col2 = st.columns([1, 1])

with col1:
    st.header("📸 第一步：错题录入")
    uploaded_file = st.file_uploader("上传题目图片", type=["png", "jpg", "jpeg"])

    if uploaded_file:
        img = Image.open(uploaded_file)
        st.image(img, caption="待处理题目", use_container_width=True)

        if st.button("开始高精度 OCR 识别"):
            with st.spinner("正在还原题目 DNA..."):
                model = LatexOCR()
                st.session_state.latex_result = model(img)
                st.rerun()

with col2:
    st.header("🧠 第二步：智能分析")
    if st.session_state.latex_result:
        st.subheader("题目无损还原 (LaTeX):")
        st.latex(st.session_state.latex_result)

        if st.button("✨ 第三步：构建变式与知识图谱"):
            with st.spinner("AI 正在深度解析..."):
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
                    response = client.chat.completions.create(
                        model="deepseek-chat",
                        messages=[{"role": "user", "content": prompt}],
                        response_format={'type': 'json_object'}
                    )
                    st.session_state.ai_data = json.loads(response.choices[0].message.content)
                except Exception as e:
                    st.error(f"AI 分析超时，请稍后再试：{e}")

# --- 结果展示与云端存入 ---
if st.session_state.ai_data:
    st.divider()
    data = st.session_state.ai_data

    st.markdown("### 📘 知识复习卡片")
    c1, c2, c3 = st.columns(3)
    c1.info(f"**核心考点**\n\n{data['card']['point']}")
    c2.info(f"**核心概念**\n\n{data['card']['concept']}")
    c3.info(f"**解题大招**\n\n{data['card']['tip']}")

    st.markdown("### ✍️ 变式分级强化训练")
    for ex in data['exercises']:
        with st.status(f"📝 {ex['type']}", expanded=False):
            st.markdown(f"**【题目内容】**\n{ex['q']}")
            st.divider()
            st.success(f"**【深度解析】**\n{ex['a']}")

    st.write("---")
    if st.button("💾 存入云端 AI 错题本"):
        with st.spinner("正在同步至 Neon 云端..."):
            if save_to_db(st.session_state.latex_result, data):
                st.toast("入库成功！已更新云端学情档案", icon="✅")
                st.balloons()