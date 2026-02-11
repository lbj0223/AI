# ============================================
# 题镜 AI - 智能错题变式系统 (云端稳定版)
# 开发者：LBJ | 核心功能：OCR识别 -> AI分析 -> 云端存储
# ============================================

# --- 1. 权限与环境重定向 (必须放在最顶部) ---
import os
import argparse

# 强行将所有可能的缓存和配置目录指向可写的 /tmp 文件夹
os.environ['HOME'] = '/tmp'
os.environ['XDG_CONFIG_HOME'] = '/tmp'
os.environ['XDG_CACHE_HOME'] = '/tmp'

import streamlit as st
from pix2tex.cli import LatexOCR
from PIL import Image
from openai import OpenAI
import json
import psycopg2
from psycopg2.extras import Json

# ============================================
# 2. 核心配置初始化
# ============================================

# 从 Streamlit Secrets 读取配置
db_config = st.secrets["postgres"]

# 初始化 DeepSeek 客户端
client = OpenAI(
    api_key=st.secrets["DEEPSEEK_KEY"],
    base_url="https://api.deepseek.com"
)


@st.cache_resource
def load_ocr_model():
    """
    使用路径注入方案解决 PermissionError
    """
    # 构造自定义路径，绕过只读的 site-packages 目录
    tmp_checkpoint = "/tmp/latest.pth"
    tmp_config = "/tmp/config.json"

    args = argparse.Namespace(
        config=tmp_config,
        checkpoint=tmp_checkpoint,
        no_cuda=True,
        no_gui=True
    )

    try:
        # 尝试带参数启动，这会强制库在 /tmp 下操作
        return LatexOCR(args)
    except Exception:
        # 备选方案：标准启动（已配合顶部的 os.environ 重定向）
        return LatexOCR()


# 初始化 Session 状态
if 'latex_result' not in st.session_state:
    st.session_state.latex_result = ""
if 'ai_data' not in st.session_state:
    st.session_state.ai_data = None


# ============================================
# 3. 数据库操作 (对齐 Neon error_questions 表)
# ============================================

def get_db_connection():
    """建立带 SSL 的云端连接"""
    return psycopg2.connect(**db_config, sslmode='require')


def save_to_db(latex, ai_data):
    """保存数据到你在 Neon 创建的 error_questions 表"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
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
        st.error(f"云端同步失败：{e}")
        return False


def fetch_history():
    """获取最近 5 条云端历史"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, ocr_latex, created_at FROM error_questions ORDER BY created_at DESC LIMIT 5")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception:
        return []


def clear_history():
    """清空云端表数据"""
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
# 4. Streamlit UI 布局
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

# --- 主界面：录入与分析 ---
col1, col2 = st.columns([1, 1])

with col1:
    st.header("📸 第一步：错题录入")
    uploaded_file = st.file_uploader("上传题目图片", type=["png", "jpg", "jpeg"])

    if uploaded_file:
        img = Image.open(uploaded_file)
        st.image(img, caption="原始题目", use_container_width=True)

        if st.button("开始高精度 OCR 识别"):
            with st.spinner("AI 正在下载模型并还原题目... (首次运行较慢)"):
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
                prompt = f"识别出的题目公式为：{st.session_state.latex_result}。请严格按 JSON 格式输出 card 和 exercises。"
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
    c1.info(f"**核心考点**\n\n{data['card'].get('point', 'N/A')}")
    c2.info(f"**概念复习**\n\n{data['card'].get('concept', 'N/A')}")
    c3.info(f"**解题大招**\n\n{data['card'].get('tip', 'N/A')}")

    st.markdown("### ✍️ 变式强化训练")
    for ex in data.get('exercises', []):
        with st.status(f"📝 {ex['type']}", expanded=False):
            st.markdown(ex['q'])
            st.divider()
            st.success(ex['a'])

    if st.button("💾 存入云端 AI 错题本"):
        if save_to_db(st.session_state.latex_result, data):
            st.toast("入库成功！已更新云端学情档案", icon="✅")
            st.balloons()