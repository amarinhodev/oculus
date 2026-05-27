import os
import re
import shutil
import config
from datetime import datetime

def merge_fragments(fragments):
    """Merges text fragments by removing incremental overlaps."""
    if not fragments: return ""
    unique_fragments = []
    for f in fragments:
        f = f.strip()
        if not f: continue
        if unique_fragments and f.lower().startswith(unique_fragments[-1].lower()):
            unique_fragments[-1] = f
        elif f not in unique_fragments:
            unique_fragments.append(f)
    return " ".join(unique_fragments)

def process_section(lines):
    """Processes a section (audio or chat) grouping by speaker and keeping timestamps."""
    processed_turns = []
    current_speaker = None
    current_time = None
    current_fragments = []
    
    for line in lines:
        line = line.strip()
        if not line or "Transcript saved using" in line or "ciepnfnceimjehngolkijpnbappkkiag" in line:
            continue
            
        speaker_match = re.match(r"^(.*?) \(\d{2}/\d{2}/\d{4}, (\d{2}:\d{2} [AP]M)\)$", line)
        
        if speaker_match:
            speaker = speaker_match.group(1)
            time_str = speaker_match.group(2)
            if speaker == "Você" or speaker == "You": speaker = config.USER_NAME
            
            if (speaker != current_speaker or time_str != current_time) and current_fragments:
                text = merge_fragments(current_fragments)
                if text:
                    processed_turns.append(f"**[{current_time}] {current_speaker}:** {text}")
                current_fragments = []
            
            current_speaker = speaker
            current_time = time_str
        else:
            current_fragments.append(line)
            
    if current_speaker and current_fragments:
        text = merge_fragments(current_fragments)
        if text:
            processed_turns.append(f"**[{current_time}] {current_speaker}:** {text}")
            
    return processed_turns

def process_files():
    if not os.path.exists(config.CAPTIONS_DIR): os.makedirs(config.CAPTIONS_DIR)
    if not os.path.exists(config.ARCHIVE_DIR): os.makedirs(config.ARCHIVE_DIR)
    
    files = [f for f in os.listdir(config.SOURCE_DIR) if f.startswith("Google Meet transcript") and f.endswith(".txt")]
    
    for filename in files:
        print(f"Processing: {filename}")
        source_path = os.path.join(config.SOURCE_DIR, filename)
        
        with open(source_path, 'r', encoding='utf-8') as f:
            content = f.read()

        parts = content.split("---------------")
        audio_lines = []
        chat_lines = []
        
        current_section = "audio"
        for p in parts:
            if "CHAT MESSAGES" in p:
                current_section = "chat"
                continue
            lines = p.strip().split('\n')
            if current_section == "audio": audio_lines.extend(lines)
            else: chat_lines.extend(lines)

        audio_processed = process_section(audio_lines)
        chat_processed = process_section(chat_lines)

        # Extraction of Date and Time for Filename
        fn_parts = filename.split("transcript-")
        meeting_title = "Meeting"
        time_fn = "00-00"
        
        if len(fn_parts) > 1:
            # Ex: "Meet at 07-04-2026, 04-57 PM on.txt"
            info = fn_parts[1].split(" at ")
            meeting_title = info[0].strip()
            datetime_str = info[1].split(" on.txt")[0] # "07-04-2026, 04-57 PM"
            
            try:
                dt_obj = datetime.strptime(datetime_str, "%d-%m-%Y, %I:%M %p")
                date_iso = dt_obj.strftime("%Y-%m-%d")
                time_fn = dt_obj.strftime("%H-%M")
            except:
                date_iso = datetime.now().strftime("%Y-%m-%d")
        else:
            date_iso = datetime.now().strftime("%Y-%m-%d")

        safe_title = "".join([c for c in meeting_title if c.isalnum() or c in (' ', '-', '_')]).replace(' ', '_')
        # Format: YYYY-MM-DD_HH-MM_Title.md
        new_filename = f"{date_iso}_{time_fn}_{safe_title}.md"
        dest_path = os.path.join(config.CAPTIONS_DIR, new_filename)
        
        with open(dest_path, 'w', encoding='utf-8') as f:
            f.write(f"# 🎙️ Transcription: {meeting_title}\n")
            f.write(f"**Date:** {date_iso.replace('-', '/')} | **Time:** {time_fn.replace('-', ':')}\n---\n\n")
            f.write("## 🔊 Audio Transcription\n\n")
            f.write("\n\n".join(audio_processed))
            
            if chat_processed:
                f.write("\n\n---\n## 💬 Chat Messages\n\n")
                f.write("\n\n".join(chat_processed))
            
        print(f"✅ Generated: {new_filename}")
        shutil.move(source_path, os.path.join(config.ARCHIVE_DIR, filename))

if __name__ == "__main__":
    process_files()
