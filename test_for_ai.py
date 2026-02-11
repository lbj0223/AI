# ============================================
# 题镜 AI - 智能错题变式系统 (云端正式版)
# ============================================
# ============================================
# 1. 强制权限重定向（必须放在最最顶部！）
# ============================================
import os
# 告诉所有库：把临时文件、缓存和配置全部丢进 /tmp
os.environ['HOME'] = '/tmp'
os.environ['XDG_CONFIG_HOME'] = '/tmp'
os.environ['XDG_CACHE_HOME'] = '/tmp'

import streamlit as st
from pix2tex.cli import LatexOCR
# ... 其余 import 保持不变 ...
from PIL import Image
from openai import OpenAI
import json
import psycopg2
from psycopg2.extras import Json

# ============================================
# 1. 核心配置与初始化
# ============================================

# 读取云端 Secrets 配置
db_config = st.secrets["postgres"]

# 初始化 AI 客户端
client = OpenAI(
    api_key=st.secrets["DEEPSEEK_KEY"],
    base_url="https://api.deepseek.com"
)


# 【优化】使用缓存加载模型，避免重复下载导致的权限或内存问题
@st.cache_resource
def load_ocr_model():
    return LatexOCR()


# 初始化会话状态
if 'latex_result' not in st.session_state:
    st.session_state.latex_result = ""
if 'ai_data' not in st.session_state:
    st.session_state.ai_data = None


# ============================================
# 2. 数据库操作函数 (对齐 Neon 表结构)
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
        st.error(f"数据保存失败：{e}")
        return False


def fetch_history():
    """获取云端历史记录"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # 统一使用 error_questions 表名
        cur.execute("SELECT id, ocr_latex, created_at FROM error_questions ORDER BY created_at DESC LIMIT 5")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        return []


def clear_history():
    """清空所有记录"""
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

# --- 侧边栏：历史记录 ---
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
    if st.button("🗑️ 清空所有记录"):
        if clear_history():
            st.rerun()

# --- 主界面 ---
col1, col2 = st.columns([1, 1])

with col1:
    st.header("📸 第一步：错题录入")
    uploaded_file = st.file_uploader("上传题目图片", type=["png", "jpg", "jpeg"])

    if uploaded_file:
        img = Image.open(uploaded_file)
        st.image(img, caption="原始题目", use_container_width=True)

        if st.button("开始高精度 OCR 识别"):
            with st.spinner("AI 正在还原题目 DNA..."):
                # 使用带缓存的模型加载
                model = load_ocr_model()
                st.session_state.latex_result = model(img)
                st.rerun()

with col2:
    st.header("🧠 第二步：智能分析")
    if st.session_state.latex_result:
        st.subheader("题目还原 (LaTeX):")
        st.latex(st.session_state.latex_result)

        if st.button("✨ 第三步：构建变式与知识图谱"):
            with st.spinner("AI 正在生成分析..."):
                prompt = f"识别出的题目公式为：{st.session_state.latex_result}。请严格按JSON格式输出card和exercises。"
                try:
                    response = client.chat.completions.create(
                        model="deepseek-chat",
                        messages=[{"role": "user", "content": prompt}],
                        response_format={'type': 'json_object'}
                    )
                    st.session_state.ai_data = json.loads(response.choices[0].message.content)
                except Exception as e:
                    st.error(f"分析失败：{e}")

# --- 结果展示与保存 ---
if st.session_state.ai_data:
    st.divider()
    data = st.session_state.ai_data

    st.markdown("### 📘 知识复习卡片")
    c1, c2, c3 = st.columns(3)
    c1.info(f"**考点**\n\n{data['card'].get('point', '待分析')}")
    c2.info(f"**概念**\n\n{data['card'].get('concept', '待分析')}")
    c3.info(f"**技巧**\n\n{data['card'].get('tip', '待分析')}")

    st.markdown("### ✍️ 变式分级训练")
    for ex in data.get('exercises', []):
        with st.status(f"📝 {ex['type']}", expanded=False):
            st.markdown(ex['q'])
            st.divider()
            st.success(ex['a'])

    if st.button("💾 存入云端 AI 错题本"):
        if save_to_db(st.session_state.latex_result, data):
            st.toast("入库成功！", icon="✅")
            st.balloons()