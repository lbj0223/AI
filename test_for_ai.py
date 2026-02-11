# ============================================
# 题镜 AI - 智能错题变式系统 (云端终极修正版)
# 开发者：LBJ | 状态：全云端环境适配
# ============================================

import os

# --- 1. 强制权限重定向 (必须放在最顶部) ---
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
# 2. 核心修复：硬编码配置与标准参数类
# ============================================

class ModelArgs:
    """最稳健的参数容器，确保 vars() 和点访问都能成功"""
    def __init__(self):
        self.config = "/tmp/config.yaml"
        self.checkpoint = "/tmp/weights.pth"
        self.resizer = "/tmp/image_resizer.pth"
        self.no_cuda = True
        self.no_gui = True

def ensure_model_files():
    """手动接管模型下载，并生成本地配置文件"""
    # 直接硬编码 YAML 配置内容，彻底解决 404 导致的 ValueError
    config_content = """
gpu: false
backbone:
  type: vit
  args:
    image_size: [224, 224]
    patch_size: 16
    width: 256
    layers: 4
    heads: 8
channels: 1
max_dimensions: [672, 192]
min_dimensions: [32, 32]
temperature: 0.00001
    """
    
    # 写入配置文件
    with open("/tmp/config.yaml", "w") as f:
        f.write(config_content.strip())

    # 下载模型权重
    base_url = "https://github.com/lukas-blecher/LaTeX-OCR/releases/download/v0.0.1/"
    files = {
        "weights.pth": base_url + "weights.pth",
        "image_resizer.pth": base_url + "image_resizer.pth"
    }
    
    for name, url in files.items():
        path = os.path.join("/tmp", name)
        if not os.path.exists(path):
            with st.spinner(f"正在同步 AI 核心组件 {name}..."):
                r = requests.get(url, stream=True)
                if r.status_code == 200:
                    with open(path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)

@st.cache_resource
def load_ocr_model():
    ensure_model_files()
    # 使用标准类实例，库内部可以完美识别 checkpoint 属性
    return LatexOCR(ModelArgs())

# ============================================
# 3. 数据库与 AI 逻辑 (保持云端配置)
# ============================================

db_config = st.secrets["postgres"] #

def get_db_connection():
    return psycopg2.connect(**db_config, sslmode='require')

def save_to_db(latex, ai_data):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        query = "INSERT INTO error_questions (ocr_latex, analysis, variants) VALUES (%s, %s, %s)"
        cur.execute(query, (latex, Json(ai_data['card']), Json(ai_data['exercises'])))
        conn.commit()
        cur.close(); conn.close()
        return True
    except Exception as e:
        st.error(f"保存失败: {e}"); return False

def fetch_history():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, ocr_latex, created_at FROM error_questions ORDER BY created_at DESC LIMIT 5")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return rows
    except Exception: return []

# ============================================
# 4. 界面布局
# ============================================

st.set_page_config(page_title="题镜 AI", layout="wide")
st.title("题镜 AI —— 智能错题变式系统")

with st.sidebar:
    st.header("🕒 云端历史看板")
    history = fetch_history()
    if history:
        for row in history:
            with st.expander(f"题目 ID: {row[0]} ({row[2].strftime('%m-%d %H:%M')})"):
                st.latex(row[1])
    else:
        st.write("暂无历史记录")

col1, col2 = st.columns([1, 1])

with col1:
    st.header("📸 错题录入")
    uploaded_file = st.file_uploader("上传图片", type=["png", "jpg", "jpeg"])
    if uploaded_file:
        img = Image.open(uploaded_file)
        st.image(img, width=400)
        if st.button("开始识别"):
            with st.spinner("AI 正在解析公式..."):
                model = load_ocr_model()
                st.session_state.latex_result = model(img)
                st.rerun()

with col2:
    st.header("🧠 智能分析")
    if 'latex_result' in st.session_state and st.session_state.latex_result:
        st.latex(st.session_state.latex_result)
        if st.button("✨ 构建变式"):
            client = OpenAI(api_key=st.secrets["DEEPSEEK_KEY"], base_url="https://api.deepseek.com")
            prompt = f"公式：{st.session_state.latex_result}。请按JSON输出card和exercises。"
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                response_format={'type': 'json_object'}
            )
            st.session_state.ai_data = json.loads(response.choices[0].message.content)

if 'ai_data' in st.session_state and st.session_state.ai_data:
    st.divider()
    if st.button("💾 存入云端错题本"):
        if save_to_db(st.session_state.latex_result, st.session_state.ai_data):
            st.toast("入库成功！", icon="✅"); st.balloons()
