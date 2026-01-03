import streamlit as st
import os
import subprocess
import glob
from groq import Groq
import math

# --- 頁面設定 ---
st.set_page_config(page_title="轉錄神器 V4 (省力版)", page_icon="⚡")
st.title("🎙️ 逐字稿轉錄神器 V4.0")
st.markdown("### 支援：超長音檔 / 低記憶體模式 / 絕對不崩潰")

# --- 1. 獲取 API Key ---
api_key = st.secrets.get("GROQ_API_KEY")
if not api_key:
    st.error("❌ 錯誤：未設定 GROQ_API_KEY，請至後台 Secrets 設定。")
    st.stop()

# --- 核心功能函數 (改用 FFmpeg 直接處理) ---

def save_uploaded_file(uploaded_file):
    """儲存使用者上傳的檔案"""
    try:
        file_ext = os.path.splitext(uploaded_file.name)[1].lower()
        if file_ext == "":
            file_ext = ".mp3" # 預設
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
    # -i 輸入檔
    # -f segment -segment_time 600: 每 600 秒切一段
    # -c:a libmp3lame -b:a 64k -ac 1: 轉成 MP3 64k 單聲道 (標準化格式)
    # -reset_timestamps 1: 重置時間戳記
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
        # 執行指令
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # 抓取生成的所有檔案並排序
        chunks = sorted(glob.glob("chunk_*.mp3"))
        return chunks
    except subprocess.CalledProcessError as e:
        st.error("FFmpeg 切割失敗，請確認 packages.txt 內有包含 ffmpeg。")
        return []
    except Exception as e:
        st.error(f"系統錯誤: {e}")
        return []

def transcribe_with_groq(client, audio_file_path):
    with open(audio_file_path, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(audio_file_path, file.read()),
            model="whisper-large-v3",
            language="zh", 
            response_format="text"
        )
    return transcription

# --- 主介面 ---

st.info("💡 提示：本版本使用 FFmpeg 硬碟切割技術，專門處理 1-3 小時以上的長音檔，不會再發生記憶體不足錯誤。")

uploaded_file = st.file_uploader("請選擇 MP3 / M4A 檔案", type=["mp3", "m4a", "wav"])

if uploaded_file and st.button("🚀 開始轉錄"):
    client = Groq(api_key=api_key)
    status = st.empty()
    progress = st.progress(0, text="準備中...")
    
    try:
        # 1. 存檔
        status.info("⏳ 1/3 正在讀取檔案...")
        source_file = save_uploaded_file(uploaded_file)
        
        # 2. 切割 (使用新技術)
        status.info("✂️ 2/3 正在使用 FFmpeg 進行低耗能切割 (請稍候)...")
        chunks = split_audio_ffmpeg(source_file)
        
        if not chunks:
            st.error("切割失敗，無法產生音訊片段。")
            st.stop()
            
        # 刪除原始大檔釋放空間
        if os.path.exists(source_file):
            os.remove(source_file)
        
        # 3. 轉錄
        full_text = ""
        total = len(chunks)
        
        for i, chunk in enumerate(chunks):
            status.info(f"🎙️ 3/3 AI 正在聽寫中... (進度 {i+1}/{total})")
            progress.progress((i)/total)
            
            try:
                text = transcribe_with_groq(client, chunk)
                full_text += text + "\n"
            except Exception as e:
                full_text += f"\n[第 {i+1} 段轉錄失敗: {e}]\n"
            
            # 處理完馬上刪
            if os.path.exists(chunk):
                os.remove(chunk)
        
        progress.progress(1.0)
        status.success("🎉 轉錄完成！")
        
        # 顯示結果
        st.text_area("轉錄逐字稿", full_text, height=400)
        st.download_button("📥 下載 .txt 文字檔", full_text, file_name="transcript.txt")

    except Exception as e:
        st.error(f"發生未預期的錯誤: {e}")
