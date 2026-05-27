import os
import time
import subprocess
import config
from datetime import datetime

def get_files(directory):
    if not os.path.exists(directory): return set()
    return set([f for f in os.listdir(directory) if f.startswith("Google Meet transcript") and f.endswith(".txt")])

def analyze_file(md_path):
    """Triggers analysis via Gemini CLI for a specific file."""
    print(f"🚀 Triggering Jarvis Automation for: {md_path}")
    
    # Passing the preferred language from config to the AI prompt
    prompt = (f"Analyze the transcription {md_path} using the oculus-analyzer skill. "
              f"CRITICAL: Generate all output (summaries, tasks, notes) in {config.PREFERRED_LANGUAGE}. "
              "Identify contexts via RAG, extract tasks and decisions, "
              "and organize results according to the skill workflow. "
              "DO NOT ASK QUESTIONS, EXECUTE IMMEDIATELY.")
    
    cmd = ["gemini", "-y", "-p", prompt]
    subprocess.Popen(cmd, stdin=subprocess.DEVNULL, 
                     stdout=open(config.LOG_ANALYSIS, 'a'), 
                     stderr=open(config.LOG_ANALYSIS_ERROR, 'a'))

def run_batch_process():
    """Processes all TXT files in the folder now."""
    txt_files = get_files(config.SOURCE_DIR)
    if not txt_files: return
    
    print(f"📦 Processing batch of {len(txt_files)} files...")
    # Run the processor to convert all to MD
    subprocess.run([config.PYTHON_BIN, config.PROCESSOR_SCRIPT])
    
    # List generated MD files and trigger analyses
    md_files = [f for f in os.listdir(config.CAPTIONS_DIR) if f.endswith(".md")]
    today_str = datetime.now().strftime("%Y-%m-%d")
    for md in md_files:
        if md.startswith(today_str):
            analyze_file(os.path.join(config.CAPTIONS_DIR, md))

def run_watcher():
    print(f"👁️ O.C.U.L.U.S. Watcher Active. Monitoring: {config.SOURCE_DIR}")
    
    # Process pending files immediately on startup
    run_batch_process()

    known_files = get_files(config.SOURCE_DIR)
    while True:
        time.sleep(5)
        current_files = get_files(config.SOURCE_DIR)
        new_files = current_files - known_files
        
        if new_files:
            for new_file in new_files:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] New file detected: {new_file}")
            run_batch_process()
            known_files = get_files(config.SOURCE_DIR)

if __name__ == "__main__":
    if not os.path.exists(config.SOURCE_DIR): os.makedirs(config.SOURCE_DIR)
    run_watcher()
