import streamlit as st
import json
import os
import sys
import subprocess
import time
import pandas as pd
import glob
from datetime import datetime
import csv

# Page Config
st.set_page_config(
    page_title="MPI Video Downloader Pro",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load CSS
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

if os.path.exists('style.css'):
    local_css('style.css')

# Initialize session state
if 'download_process' not in st.session_state:
    st.session_state.download_process = None
if 'download_active' not in st.session_state:
    st.session_state.download_active = False
if 'download_stats' not in st.session_state:
    st.session_state.download_stats = {'total': 0, 'success': 0, 'failed': 0, 'start_time': None}
if 'pause_requested' not in st.session_state:
    st.session_state.pause_requested = False
if 'completed_downloads' not in st.session_state:
    st.session_state.completed_downloads = []

# Sidebar Configuration
st.sidebar.title("⚙️ Configuration")
num_ranks = st.sidebar.slider("Number of MPI Ranks", min_value=1, max_value=8, value=4, 
                               help="More ranks = faster parallel downloads")
output_dir = st.sidebar.text_input("Output Directory", value="downloads")

st.sidebar.divider()
st.sidebar.subheader("Advanced Options")
retry_failed = st.sidebar.checkbox("Auto-retry failed downloads", value=True)
max_retries = st.sidebar.number_input("Max retries", min_value=1, max_value=5, value=2)
video_quality = st.sidebar.selectbox("Video Quality", ["best", "worst", "720p", "1080p", "480p"])

# Main Title
st.markdown("""
    <div style='text-align: center; padding: 2rem 0;'>
        <h1 style='background: linear-gradient(90deg, #ff4b4b 0%, #ff904b 100%); 
                   -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                   font-size: 3rem; font-weight: bold;'>
            🚀 MPI Video Downloader Pro
        </h1>
        <p style='color: #888; font-size: 1.2rem;'>High-Performance Parallel Video Downloading</p>
    </div>
""", unsafe_allow_html=True)

# Create Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📥 Download", "📊 Progress", "✅ Completed", "📈 Statistics"])

# ==================== TAB 1: DOWNLOAD ====================
with tab1:
    st.markdown("### 🎯 Enter Video URLs")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        urls_input = st.text_area(
            "Video URLs (one per line)", 
            height=200,
            placeholder="https://www.youtube.com/watch?v=...\nhttps://vimeo.com/...\nhttps://www.youtube.com/shorts/...",
            key="urls_input"
        )
    
    with col2:
        st.markdown("##### 📁 Bulk Import")
        uploaded_file = st.file_uploader("Upload URL list (TXT/CSV)", type=['txt', 'csv'])
        
        if uploaded_file:
            content = uploaded_file.read().decode('utf-8')
            if uploaded_file.name.endswith('.csv'):
                lines = content.split('\n')
                urls_from_file = [line.split(',')[0].strip() for line in lines if line.strip()]
            else:
                urls_from_file = [line.strip() for line in content.split('\n') if line.strip()]
            
            st.session_state.urls_input = '\n'.join(urls_from_file)
            st.success(f"✅ Loaded {len(urls_from_file)} URLs")
            st.rerun()
    
    st.divider()
    
    # Control Buttons
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        start_button = st.button("▶️ Start Download", type="primary", use_container_width=True,
                                 disabled=st.session_state.download_active)
    
    with col2:
        pause_button = st.button("⏸️ Pause", use_container_width=True,
                                disabled=not st.session_state.download_active)
    
    with col3:
        resume_button = st.button("▶️ Resume", use_container_width=True,
                                  disabled=not st.session_state.pause_requested)
    
    with col4:
        stop_button = st.button("⏹️ Stop", use_container_width=True,
                               disabled=not st.session_state.download_active)
    
    # Handle Pause
    if pause_button:
        st.session_state.pause_requested = True
        pause_flag = os.path.join(output_dir, "pause.flag")
        with open(pause_flag, 'w') as f:
            f.write('paused')
        st.warning("⏸️ Pause requested. Waiting for current downloads to complete...")
    
    # Handle Resume
    if resume_button:
        st.session_state.pause_requested = False
        pause_flag = os.path.join(output_dir, "pause.flag")
        if os.path.exists(pause_flag):
            os.remove(pause_flag)
        st.success("▶️ Resuming downloads...")
        st.rerun()
    
    # Handle Stop
    if stop_button:
        if st.session_state.download_process:
            st.session_state.download_process.terminate()
            st.session_state.download_active = False
            st.session_state.download_process = None
            st.error("⏹️ Download stopped.")
            st.rerun()
    
    # Handle Start
    if start_button:
        if not urls_input.strip():
            st.error("⚠️ Please enter at least one URL.")
        else:
            # Prepare URLs
            urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
            
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            
            config = {
                "urls": urls,
                "num_ranks": num_ranks,
                "output_dir": output_dir,
                "retry_failed": retry_failed,
                "max_retries": max_retries,
                "video_quality": video_quality
            }
            
            with open("config.json", "w") as f:
                json.dump(config, f)
            
            # Clean up old files
            for f in glob.glob(os.path.join(output_dir, "status_rank_*.json")):
                os.remove(f)
            for f in glob.glob(os.path.join(output_dir, "*.flag")):
                os.remove(f)
            
            # Reset stats
            st.session_state.download_stats = {
                'total': len(urls),
                'success': 0,
                'failed': 0,
                'start_time': time.time()
            }
            st.session_state.completed_downloads = []
            
            # Run MPI Command
            python_executable = sys.executable if sys.executable else os.path.abspath(os.path.join(".venv", "Scripts", "python.exe"))
            script_path = os.path.abspath("mpi_video_downloader.py")
            
            cmd = f'mpiexec -n {num_ranks} "{python_executable}" "{script_path}"'
            process = subprocess.Popen(cmd, shell=True)
            
            st.session_state.download_process = process
            st.session_state.download_active = True
            
            st.success(f"✅ Started download with {num_ranks} ranks!")
            st.rerun()

# ==================== TAB 2: PROGRESS ====================
with tab2:
    if st.session_state.download_active:
        st.markdown("### 🔄 Live Download Progress")
        
        # Create containers for each rank
        rank_containers = []
        for rank in range(num_ranks):
            with st.container():
                st.markdown(f"""
                    <div style='background: linear-gradient(135deg, #1e1e1e 0%, #2a2a2a 100%);
                                padding: 1.5rem; border-radius: 12px; margin-bottom: 1rem;
                                border-left: 4px solid #ff4b4b;'>
                        <h4 style='margin: 0; color: #ff4b4b;'>Rank {rank}</h4>
                    </div>
                """, unsafe_allow_html=True)
                
                col1, col2 = st.columns([3, 1])
                status_text = col1.empty()
                progress_bar = col1.empty()
                stats_col = col2.empty()
                
                rank_containers.append({
                    'status': status_text,
                    'progress': progress_bar,
                    'stats': stats_col
                })
        
        # Monitoring Loop
        while st.session_state.download_active:
            process = st.session_state.download_process
            
            # Check if process finished
            if process and process.poll() is not None:
                st.session_state.download_active = False
                break
            
            # Check pause flag
            pause_flag = os.path.join(output_dir, "pause.flag")
            is_paused = os.path.exists(pause_flag)
            
            # Read status files
            all_data = []
            active_ranks = 0
            
            for rank in range(num_ranks):
                status_file = os.path.join(output_dir, f"status_rank_{rank}.json")
                
                if os.path.exists(status_file):
                    try:
                        with open(status_file, "r", encoding='utf-8') as f:
                            status = json.load(f)
                        
                        current_url = status.get('current_url', None)
                        state = status.get('status', 'idle')
                        completed = status.get('completed', [])
                        
                        # Update UI for this rank
                        container = rank_containers[rank]
                        
                        if is_paused and state == 'downloading':
                            container['status'].warning(f"⏸️ Paused - Current: {current_url or 'Idle'}")
                            container['progress'].progress(50)
                        elif state == 'downloading' and current_url:
                            container['status'].info(f"⬇️ Downloading: {current_url[:60]}...")
                            container['progress'].progress(50)
                            active_ranks += 1
                        elif state == 'idle':
                            container['status'].success(f"✅ Idle - Completed: {len(completed)} videos")
                            container['progress'].progress(100)
                        else:
                            container['status'].info(f"⏳ Status: {state}")
                            container['progress'].progress(25)
                        
                        container['stats'].metric("Completed", len(completed))
                        
                        # Collect data
                        all_data.extend(completed)
                        
                    except (json.JSONDecodeError, PermissionError):
                        pass
                else:
                    rank_containers[rank]['status'].info(f"⏳ Waiting for initialization...")
            
            # Update global stats
            if all_data:
                success_count = sum(1 for item in all_data if item.get('status') == 'success')
                failed_count = sum(1 for item in all_data if item.get('status') == 'error')
                
                st.session_state.download_stats['success'] = success_count
                st.session_state.download_stats['failed'] = failed_count
                st.session_state.completed_downloads = all_data
            
            # Check completion
            if active_ranks == 0 and process and process.poll() is not None:
                st.session_state.download_active = False
                break
            
            time.sleep(0.5)
        
        if not st.session_state.download_active:
            st.success("🎉 All downloads completed!")
            
            # Save log
            log_file = os.path.join(output_dir, f"download_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'stats': st.session_state.download_stats,
                    'downloads': st.session_state.completed_downloads,
                    'timestamp': datetime.now().isoformat()
                }, f, indent=2)
            
            st.info(f"📝 Log saved: {log_file}")
            st.rerun()
    else:
        st.info("👆 Start a download from the Download tab to see progress here.")

# ==================== TAB 3: COMPLETED ====================
with tab3:
    st.markdown("### ✅ Completed Downloads")
    
    if st.session_state.completed_downloads:
        # Filter options
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            filter_status = st.selectbox("Filter by status", ["All", "Success", "Error"])
        
        with col2:
            search_query = st.text_input("🔍 Search by title", "")
        
        with col3:
            st.write("")
            st.write("")
            if st.button("🔄 Refresh"):
                st.rerun()
        
        # Filter data
        filtered_data = st.session_state.completed_downloads
        
        if filter_status != "All":
            filtered_data = [d for d in filtered_data if d.get('status') == filter_status.lower()]
        
        if search_query:
            filtered_data = [d for d in filtered_data 
                           if search_query.lower() in d.get('title', '').lower()]
        
        st.divider()
        
        # Display as cards
        if filtered_data:
            cols = st.columns(3)
            
            for i, item in enumerate(filtered_data):
                with cols[i % 3]:
                    if item.get('status') == 'success':
                        file_path = item.get('file_path', '')
                        
                        if os.path.exists(file_path):
                            st.video(file_path)
                            st.markdown(f"**{item.get('title', 'Unknown')}**")
                            st.caption(f"⏱️ {item.get('time', 0):.1f}s | Rank {item.get('rank', '?')}")
                        else:
                            st.error(f"❌ File not found: {file_path}")
                    else:
                        st.error(f"❌ Failed: {item.get('title', item.get('url', 'Unknown'))}")
                        st.caption(f"Error: {item.get('error', 'Unknown error')}")
        else:
            st.info("No downloads match your filters.")
    else:
        st.info("No completed downloads yet. Start a download to see results here!")

# ==================== TAB 4: STATISTICS ====================
with tab4:
    st.markdown("### 📈 Download Statistics")
    
    if st.session_state.download_stats['total'] > 0:
        stats = st.session_state.download_stats
        
        # Metrics row
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total URLs", stats['total'])
        
        with col2:
            st.metric("✅ Successful", stats['success'], 
                     delta=f"{stats['success']/stats['total']*100:.1f}%" if stats['total'] > 0 else "0%")
        
        with col3:
            st.metric("❌ Failed", stats['failed'],
                     delta=f"{stats['failed']/stats['total']*100:.1f}%" if stats['total'] > 0 else "0%",
                     delta_color="inverse")
        
        with col4:
            if stats['start_time']:
                elapsed = time.time() - stats['start_time']
                st.metric("⏱️ Time Elapsed", f"{elapsed:.1f}s")
        
        st.divider()
        
        # Charts
        if st.session_state.completed_downloads:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### Success Rate")
                success_rate = stats['success'] / stats['total'] * 100 if stats['total'] > 0 else 0
                st.progress(success_rate / 100)
                st.markdown(f"**{success_rate:.1f}%** success rate")
            
            with col2:
                st.markdown("#### Download Times")
                times = [d.get('time', 0) for d in st.session_state.completed_downloads 
                        if d.get('status') == 'success']
                if times:
                    avg_time = sum(times) / len(times)
                    st.metric("Average Time", f"{avg_time:.2f}s")
                    st.metric("Total Time", f"{sum(times):.2f}s")
            
            # Detailed table
            st.divider()
            st.markdown("#### Detailed Results")
            
            df = pd.DataFrame(st.session_state.completed_downloads)
            if not df.empty:
                display_df = df[['rank', 'title', 'status', 'time']].copy()
                display_df['time'] = display_df['time'].round(2)
                st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("Start a download to see statistics here!")

# Footer
st.divider()
st.markdown("""
    <div style='text-align: center; color: #666; padding: 1rem;'>
        <p>MPI Video Downloader Pro | Powered by MPI4Py & yt-dlp</p>
    </div>
""", unsafe_allow_html=True)