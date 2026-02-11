# ============================================
# 题镜 AI - 智能错题变式系统 (云端终极稳定版)
# 开发者：LBJ | 核心功能：OCR识别 -> AI分析 -> 云端存储
# ============================================

import os

# --- 【最高优先级】权限与路径重定向 ---
# 必须在导入 LatexOCR 之前运行，强制所有缓存和配置进入可写的 /tmp
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
import requests

# ============================================
# 1. 核心修复：兼容性配置类
# ============================================

class LatexConfig(dict):
    """
    【计科专业级方案】
    继承 dict 以满足 Munch.update 需求 (解决 ValueError)
    重写 __getattr__ 以支持点符号访问 .config (解决 AttributeError)
    """
    def __getattr__(self, name):
        if name in self:
            return self[name]
        raise AttributeError(f"'LatexConfig' object has no attribute '{name}'")

def ensure_model_files():
    """手动同步 AI 模型至云端临时目录，彻底避开权限报错"""
    base_url = "https://github.com/lukas-blecher/LaTeX-OCR/releases/download/v0.0.1/"
    files = {
        "latest.pth": base_url + "latest.pth",
        "config.json": base_url + "config.json"
    }
    for name, url in files.items():
        path = os.path.join("/tmp", name)
        if not os.path.exists(path):
            with st.spinner(f"正在同步 AI 核心组件 {name} ..."):
                r = requests.get(url, stream=True)
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

@st.cache_resource
def load_ocr_model():
    # 1. 确保模型文件在可写目录中
    ensure_model_files()
    
    # 2. 构造“双能”配置对象
    params = LatexConfig({
        "config": "/tmp/config.json", 
        "checkpoint": "/tmp/latest.pth", 
        "no_cuda": True, 
        "no_gui": True
    })
    
    # 3. 注入配置，适配库内部逻辑
    return LatexOCR(params)

# ============================================
# 2. 云端数据库操作 (对齐 Neon 架构)
# ============================================

db_config = st.secrets["postgres"]

def get_db_connection():
    """建立带 SSL 的安全云端连接"""
    return psycopg2.connect(**db_config, sslmode='require')

def save_to_db(latex, ai_data):
    """保存至 Neon 云端的 error_questions 表"""
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
    """获取最近 5 条云端历史记录"""
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

# ============================================
# 3. 页面界面逻辑
# ============================================

st.set_page_config(page_title="题镜 AI", layout="wide")
st.title("题镜 AI —— 智能错题变式系统")

# 侧边栏：历史看板
with st.sidebar:
    st.header("🕒 云端历史看板")
    history = fetch_history()
    if history:
        for row in history:
            with st.expander(f"题目 ID: {row[0]} ({row[2].strftime('%m-%d %H:%M')})"):
                st.latex(row[1])
    else:
        st.write("暂无历史记录，快去上传第一道题吧！")

# 主界面布局
col1, col2 = st.columns([1, 1])

with col1:
    st.header("📸 第一步：错题录入")
    uploaded_file = st.file_uploader("上传题目图片", type=["png", "jpg", "jpeg"])
    if uploaded_file:
        img = Image.open(uploaded_file)
        st.image(img, caption="原始题目", use_container_width=True)

        if st.button("开始高精度 OCR 识别"):
            with st.spinner("AI 正在还原题目 DNA... (首次运行需下载模型)"):
                model = load_ocr_model()
                st.session_state.latex_result = model(img)
                st.rerun()

with col2:
    st.header("🧠 第二步：智能分析")
    if 'latex_result' in st.session_state and st.session_state.latex_result:
        st.subheader("题目还原 (LaTeX):")
        st.latex(st.session_state.latex_result)

        if st.button("✨ 第三步：构建变式与知识图谱"):
            with st.spinner("DeepSeek 正在解析..."):
                client = OpenAI(
                    api_key=st.secrets["DEEPSEEK_KEY"],
                    base_url="https://api.deepseek.com"
                )
                prompt = f"识别出的题目公式为：{st.session_state.latex_result}。请严格按 JSON 格式输出 card 和 exercises。"
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={'type': 'json_object'}
                )
                st.session_state.ai_data = json.loads(response.choices[0].message.content)

# 展示结果并存入数据库
if 'ai_data' in st.session_state and st.session_state.ai_data:
    st.divider()
    data = st.session_state.ai_data
    st.markdown("### 📘 知识复习卡片")
    c1, c2, c3 = st.columns(3)
    c1.info(f"**核心考点**\n\n{data['card'].get('point', 'N/A')}")
    c2.info(f"**概念复习**\n\n{data['card'].get('concept', 'N/A')}")
    c3.info(f"**解题技巧**\n\n{data['card'].get('tip', 'N/A')}")

    if st.button("💾 存入云端 AI 错题本"):
        if save_to_db(st.session_state.latex_result, data):
            st.toast("入库成功！已更新云端学情档案", icon="✅")
            st.balloons()
