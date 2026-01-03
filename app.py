import streamlit as st
import os
import subprocess
import glob
from groq import Groq
import math

# --- 頁面設定 ---
st.set_page_config(page_title="轉錄神器 V4.1 (繁體版)", page_icon="🇹🇼")
st.title("🎙️ 逐字稿轉錄神器 V4.1 (繁體優化版)")
st.markdown("### 支援：超長音檔 / 低記憶體模式 / 強制繁體中文")

# --- 1. 獲取 API Key ---
api_key = st.secrets.get("GROQ_API_KEY")
if not api_key:
    st.error("❌ 錯誤：未設定 GROQ_API_KEY，請至後台 Secrets 設定。")
    st.stop()

# --- 核心功能函數 ---

def save_uploaded_file(uploaded_file):
    """儲存使用者上傳的檔案"""
    try:
        file_ext = os.path.splitext(uploaded_file.name)[1].lower()
        if file_ext == "":
            file_ext = ".mp3"
        temp_filename = f"input_source{file_ext}"
        
        with open(temp_filename, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return temp_filename
    except Exception as e:
        st.error(f"檔案儲存失敗: {e}")
        return None

def split_audio_ffmpeg(input_file, chunk_time=600):
    """
    使用 FFmpeg 底層指令直接切割檔案 (不佔用 RAM)
    chunk_time: 切割秒數，預設 600秒 (10分鐘)
    """
    output_pattern = "chunk_%03d.mp3"
    
    # 清理舊的 chunk 檔案
    for f in glob.glob("chunk_*.mp3"):
        os.remove(f)

    # 組合 FFmpeg 指令
    cmd = [
        "ffmpeg",
        "-i", input_file,
        "-f", "segment",
        "-segment_time", str(chunk_time),
        "-c:a", "libmp3lame",
        "-b:a", "64k",
        "-ac", "1",
        "-reset_timestamps", "1",
        "-y", # 強制覆蓋
        output_pattern
    ]
    
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        chunks = sorted(glob.glob("chunk_*.mp3"))
        return chunks
    except subprocess.CalledProcessError as e:
        st.error("FFmpeg 切割失敗，請確認 packages.txt 內有包含 ffmpeg。")
        return []
    except Exception as e:
        st.error(f"系統錯誤: {e}")
        return []

def transcribe_with_groq(client, audio_file_path):
    """呼叫 Groq API 進行轉錄 (加入繁體提示詞)"""
    with open(audio_file_path, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(audio_file_path, file.read()),
            model="whisper-large-v3",
            language="zh", 
            # ▼▼▼ 關鍵修改：加入 prompt 強制引導為繁體中文 ▼▼▼
            prompt="以下是台灣的繁體中文逐字稿內容。請使用繁體中文 (Traditional Chinese) 進行轉錄，包含專有名詞與上下文，不要使用簡體字。",
            response_format="text"
        )
    return transcription

# --- 主介面 ---

st.info("💡 提示：本版本已針對「台灣繁體中文」進行優化，並使用低記憶體切割技術，可安心上傳長檔案。")

uploaded_file = st.file_uploader("請選擇 MP3 / M4A 檔案", type=["mp3", "m4a", "wav"])

if uploaded_file and st.button("🚀 開始轉錄"):
    client = Groq(api_key=api_key)
    status = st.empty()
    progress = st.progress(0, text="準備中...")
    
    try:
        # 1. 存檔
        status.info("⏳ 1/3 正在讀取檔案...")
        source_file = save_uploaded_file(uploaded_file)
        
        # 2. 切割
        status.info("✂️ 2/3 正在使用 FFmpeg 進行低耗能切割 (請稍候)...")
        chunks = split_audio_ffmpeg(source_file)
        
        if not chunks:
            st.error("切割失敗，無法產生音訊片段。")
            st.stop()
            
        # 刪除原始大檔
        if os.path.exists(source_file):
            os.remove(source_file)
        
        # 3. 轉錄
        full_text = ""
        total = len(chunks)
        
        for i, chunk in enumerate(chunks):
            status.info(f"🎙️ 3/3 AI 正在聽寫中 (繁體優化)... (進度 {i+1}/{total})")
            progress.progress((i)/total)
            
            try:
                text = transcribe_with_groq(client, chunk)
                full_text += text + "\n"
            except Exception as e:
                full_text += f"\n[第 {i+1} 段轉錄失敗: {e}]\n"
            
            if os.path.exists(chunk):
                os.remove(chunk)
        
        progress.progress(1.0)
        status.success("🎉 轉錄完成！")
        
        # 顯示結果
        st.text_area("轉錄逐字稿", full_text, height=400)
        st.download_button("📥 下載 .txt 文字檔", full_text, file_name="transcript_tc.txt")

    except Exception as e:
        st.error(f"發生未預期的錯誤: {e}")
