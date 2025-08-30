import os
import requests
import time
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GITHUB_REPO = os.getenv("GITHUB_REPOSITORY", "unknown/repo")
GITHUB_ACTOR = os.getenv("GITHUB_ACTOR", "unknown")
GITHUB_SERVER_URL = "https://github.com"
GITHUB_SHA = os.getenv("GITHUB_SHA", "")[:7]
BRANCH = os.getenv("KERNEL_BRANCH", "unknown")
ROM_TYPE = os.getenv("ROM_TYPE", "unknown")
ALL_ROM_TYPES = os.getenv("ALL_ROM_TYPES", "")
STATUS = os.getenv("BUILD_STATUS", "failure")
KERNEL_SOURCE_URL = os.getenv("KERNEL_SOURCE_URL", "")
ZIP_PATHS = os.getenv("ZIP_PATHS", "").split(",")
TIME_NOW = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

def telegram_api(method):
    return f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"

def sizeof_fmt(num, suffix="B"):
    for unit in ["", "K", "M", "G", "T"]:
        if abs(num) < 1024.0:
            return f"{num:.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}P{suffix}"

def format_status_message():
    status_icon = "✅" if STATUS == "success" else "❌"
    title = "Build Successful" if STATUS == "success" else "Build Failed"
    
    # Determine build type
    rom_types = ALL_ROM_TYPES.split(",")
    if len(rom_types) == 2 and "AOSP" in rom_types and "MIUI" in rom_types:
        build_type = "AOSP + MIUI"
    elif "AOSP" in rom_types:
        build_type = "AOSP Only"
    elif "MIUI" in rom_types:
        build_type = "MIUI Only"
    else:
        build_type = "Unknown"
    
    # Get individual statuses if available
    status_details = []
    if "AOSP" in rom_types:
        aosp_status = os.getenv("AOSP_STATUS", "unknown")
        status_icon_aosp = "✅" if aosp_status == "success" else "❌"
        status_details.append(f"{status_icon_aosp} AOSP")
    
    if "MIUI" in rom_types:
        miui_status = os.getenv("MIUI_STATUS", "unknown")
        status_icon_miui = "✅" if miui_status == "success" else "❌"
        status_details.append(f"{status_icon_miui} MIUI")
    
    status_detail_text = " | ".join(status_details) if status_details else ""
    
    return f"""{status_icon} *{title} - {build_type}*

*Build Name:* Kernel Compilation
*Initiated By:* {GITHUB_ACTOR}
*Machine:* GitHub Actions Runner
*Build ID:* {os.getenv("GITHUB_RUN_ID", "unknown")}
*Repository:* [{GITHUB_REPO}]({GITHUB_SERVER_URL}/{GITHUB_REPO})
*Branch:* `{BRANCH}`
*Kernel Source:* [Realking_Kernel]({KERNEL_SOURCE_URL})

*Status:* {status_icon} {STATUS.capitalize()}
*Build Details:* {status_detail_text}

🕒 *Time:* {TIME_NOW}
""".strip()

def send_text_message(text, parse_mode="Markdown"):
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }
    response = requests.post(telegram_api("sendMessage"), json=payload)
    return response.json().get("result", {}).get("message_id")

def edit_text_message(message_id, text, parse_mode="Markdown"):
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }
    requests.post(telegram_api("editMessageText"), json=payload)

def delete_message(message_id):
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_id": message_id,
    }
    requests.post(telegram_api("deleteMessage"), json=payload)

def simulate_progress_bar(percent, size_sent, size_total):
    filled = int(percent / 5)
    empty = 20 - filled
    return f"*Progress:* [`{'█' * filled}{'░' * empty}`] ({percent:.1f}% | {sizeof_fmt(size_sent)}/{sizeof_fmt(size_total)})"

def upload_file_with_progress(file_path):
    if not os.path.exists(file_path):
        return None

    file_size = os.path.getsize(file_path)
    filename = os.path.basename(file_path)

    # Send initial upload message
    upload_msg = f"""📦 *Uploading File*
*Name:* `{filename}`
*Size:* {sizeof_fmt(file_size)}
*Status:* Uploading...
"""
    message_id = send_text_message(upload_msg)

    # Simulate progress
    for progress in range(0, 101, 10):
        progress_text = simulate_progress_bar(progress, (progress/100)*file_size, file_size)
        edit_text_message(message_id, upload_msg + "\n" + progress_text)
        time.sleep(0.3)

    # Actually upload the file
    with open(file_path, "rb") as f:
        response = requests.post(
            telegram_api("sendDocument"),
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"📦 `{filename}`"},
            files={"document": (filename, f)},
        )
    
    if response.status_code == 200:
        # Update to show uploaded status briefly, then delete
        uploaded_msg = upload_msg.replace("Uploading...", "✅ Uploaded")
        edit_text_message(message_id, uploaded_msg)
        time.sleep(2)
        delete_message(message_id)
        return True
    else:
        # If upload failed, show error
        error_msg = upload_msg.replace("Uploading...", "❌ Upload Failed")
        edit_text_message(message_id, error_msg)
        return False

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials not set, skipping notification")
        return

    # Send main status message
    status_message = format_status_message()
    send_text_message(status_message)

    # Only upload files if build was successful
    if STATUS.lower() == "success":
        for zip_path in ZIP_PATHS:
            zip_path = zip_path.strip()
            if zip_path and os.path.exists(zip_path):
                upload_file_with_progress(zip_path)
                # Small delay between uploads
                time.sleep(1)

if __name__ == "__main__":
    main()
