# ============================================
# 题镜 AI - 智能错题变式系统 (云端正式版)
# 核心功能：OCR识别 -> AI分析 -> 变式生成 -> 云端存储
# ============================================

import os

# 【关键修复】必须在导入 LatexOCR 之前设置环境，解决 PermissionError
os.environ['XDG_CONFIG_HOME'] = '/tmp'

import streamlit as st
from pix2tex.cli import LatexOCR
from PIL import Image
from openai import OpenAI
import json
import psycopg2
from psycopg2.extras import Json

# ============================================
# 1. 核心配置与初始化
# ============================================

# 从 Secrets 读取 Neon 云数据库配置
db_config = st.secrets["postgres"]

# 初始化 DeepSeek 客户端
client = OpenAI(
    api_key=st.secrets["DEEPSEEK_KEY"],
    base_url="https://api.deepseek.com"
)


# 使用缓存加载 OCR 模型，防止重复下载和内存溢出
@st.cache_resource
def load_ocr_model():
    return LatexOCR()


# 初始化会话状态
if 'latex_result' not in st.session_state:
    st.session_state.latex_result = ""
if 'ai_data' not in st.session_state:
    st.session_state.ai_data = None


# ============================================
# 2. 数据库操作函数 (统一使用 Neon 表结构)
# ============================================

def get_db_connection():
    """建立云端数据库连接"""
    return psycopg2.connect(**db_config)


def save_to_db(latex, ai_data):
    """保存识别结果和AI分析到 error_questions 表"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # 对应你在 Neon SQL Editor 中创建的字段
        query = """
        INSERT INTO error_questions (ocr_latex, analysis, variants)
        VALUES (%s, %s, %s)
        """
        cur.execute(query, (
            latex,
            Json(ai_data['card']),
            Json(ai_data['exercises'])
        ))

        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"云端保存失败：{e}")
        return False


def fetch_history():
    """获取云端历史记录"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # 按时间倒序查出最近的 5 条
        cur.execute("SELECT id, ocr_latex, created_at FROM error_questions ORDER BY created_at DESC LIMIT 5")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        # 如果表还未创建或连接失败，返回空列表
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
        st.error(f"清空失败：{e}")
        return False


# ============================================
# 3. Streamlit 页面布局
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
                st.info("已同步至云端错题本")
    else:
        st.write("暂无历史记录，快去上传第一道题吧！")

    st.divider()
    if st.button("🗑️ 清空所有记录"):
        if clear_history():
            st.toast("云端记录已扫除", icon="🧹")
            st.rerun()

st.caption("核心理念：‘拍一题，练三题，通一类’")

# --- 主界面：错题录入 ---
col1, col2 = st.columns([1, 1])

with col1:
    st.header("📸 第一步：错题录入")
    uploaded_file = st.file_uploader("上传题目图片", type=["png", "jpg", "jpeg"])

    if uploaded_file:
        img = Image.open(uploaded_file)
        st.image(img, caption="原始题目", use_container_width=True)

        if st.button("开始高精度 OCR 识别"):
            with st.spinner("AI 正在还原题目 DNA..."):
                # 调用缓存的加载函数
                model = load_ocr_model()
                st.session_state.latex_result = model(img)
                st.rerun()

with col2:
    st.header("🧠 第二步：智能分析")
    if st.session_state.latex_result:
        st.subheader("题目还原 (LaTeX):")
        st.latex(st.session_state.latex_result)

        if st.button("✨ 第三步：构建变式与知识图谱"):
            with st.spinner("DeepSeek 正在解析考点..."):
                prompt = f"""
                你现在是"题镜 AI"专家。识别出的题目公式为：{st.session_state.latex_result}
                请严格按 JSON 格式输出：
                {{
                  "card": {{ "point": "考点名称", "concept": "概念复习", "tip": "解题技巧" }},
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
                    st.error(f"AI 分析失败：{e}")

# --- 结果展示与保存 ---
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
            st.success(f"**【题镜 AI 深度解析】**\n{ex['a']}")

    st.write("---")
    if st.button("💾 存入云端 AI 错题本"):
        with st.spinner("正在同步至 Neon 云端 PostgreSQL..."):
            if save_to_db(st.session_state.latex_result, data):
                st.toast("入库成功！已更新云端学情档案", icon="✅")
                st.balloons()