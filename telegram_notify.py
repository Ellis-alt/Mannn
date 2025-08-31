import os
import requests
import time
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TG_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")
GITHUB_REPO = os.getenv("GITHUB_REPOSITORY", "unknown/repo")
GITHUB_ACTOR = os.getenv("GITHUB_ACTOR", "unknown")
GITHUB_SERVER_URL = "https://github.com"
GITHUB_SHA = os.getenv("GITHUB_SHA", "")[:7]
BRANCH = os.getenv("KERNEL_BRANCH", "unknown")
ROM_TYPE = os.getenv("ROM_TYPE", "unknown")
KERNEL_SOURCE_URL = os.getenv("KERNEL_SOURCE_URL", "")
ZIP_PATH = os.getenv("ZIP_PATH", "")
BUILD_STATUS = os.getenv("BUILD_STATUS", "in_progress")
BUILD_START = time.time()
RUN_ID = os.getenv("GITHUB_RUN_ID", "unknown")
WORKFLOW_NAME = os.getenv("GITHUB_WORKFLOW", "Build Kernel")
STEP_NAME = os.getenv("CURRENT_STAGE", "Initializing")

LIVE_MESSAGE_ID_PATH = "live_message_id.txt"


def telegram_api(method):
    return f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"


def sizeof_fmt(num, suffix="B"):
    for unit in ["", "K", "M", "G", "T"]:
        if abs(num) < 1024.0:
            return f"{num:.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}P{suffix}"


def progress_bar(percent):
    filled = int(percent / 5)
    empty = 20 - filled
    return f"[`{'█' * filled}{'░' * empty}`] ({percent:.1f}%)"


def get_elapsed_time():
    elapsed = int(time.time() - BUILD_START)
    mins, secs = divmod(elapsed, 60)
    return f"{mins} mins {secs} secs"


def build_live_message(stage="Starting", percent=0):
    title = f"🚀 *Live Build Progress - {ROM_TYPE}*"
    repo_url = f"{GITHUB_SERVER_URL}/{GITHUB_REPO}"
    branch_url = f"{repo_url}/tree/{BRANCH}"

    message = f"""{title}

*Workflow:* {WORKFLOW_NAME}
*Initiated By:* {GITHUB_ACTOR}
*Build ID:* `{RUN_ID}`
*Repository:* [{GITHUB_REPO}]({repo_url})
*Branch:* [`{BRANCH}`]({branch_url})
*Kernel Source:* [Link]({KERNEL_SOURCE_URL})

*Progress:* {progress_bar(percent)}
*Stage:* `{stage}`
*Build Time:* {get_elapsed_time()}
"""
    return message


def send_initial_message():
    message = build_live_message()
    response = requests.post(telegram_api("sendMessage"), json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    })

    message_id = response.json().get("result", {}).get("message_id")
    if message_id:
        with open(LIVE_MESSAGE_ID_PATH, "w") as f:
            f.write(str(message_id))


def update_live_message(stage, percent):
    try:
        with open(LIVE_MESSAGE_ID_PATH) as f:
            message_id = int(f.read())
    except FileNotFoundError:
        return

    message = build_live_message(stage, percent)
    requests.post(telegram_api("editMessageText"), json={
        "chat_id": TELEGRAM_CHAT_ID,
        "message_id": message_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    })


def delete_live_message():
    try:
        with open(LIVE_MESSAGE_ID_PATH) as f:
            message_id = int(f.read())
        requests.post(telegram_api("deleteMessage"), json={
            "chat_id": TELEGRAM_CHAT_ID,
            "message_id": message_id,
        })
    except FileNotFoundError:
        pass


def send_final_message(status):
    title_icon = "✅" if status == "success" else "❌"
    title = f"{title_icon} *Build {'Success' if status == 'success' else 'Failed'} - {ROM_TYPE}*"
    repo_url = f"{GITHUB_SERVER_URL}/{GITHUB_REPO}"
    branch_url = f"{repo_url}/tree/{BRANCH}"

    message = f"""{title}

*Workflow:* {WORKFLOW_NAME}
*Initiated By:* {GITHUB_ACTOR}
*Build ID:* `{RUN_ID}`
*Repository:* [{GITHUB_REPO}]({repo_url})
*Branch:* [`{BRANCH}`]({branch_url})
*Kernel Source:* [Link]({KERNEL_SOURCE_URL})

*Build Time:* {get_elapsed_time()}
"""
    requests.post(telegram_api("sendMessage"), json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    })


def upload_file_with_progress(file_path):
    if not os.path.exists(file_path):
        return False

    file_size = os.path.getsize(file_path)
    filename = os.path.basename(file_path)

    msg = f"""📦 *Uploading File*
*Name:* `{filename}`
*Size:* {sizeof_fmt(file_size)}
*Status:* Uploading...
"""
    r = requests.post(telegram_api("sendMessage"), json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown"
    })
    msg_id = r.json().get("result", {}).get("message_id")

    for progress in range(0, 101, 10):
        prog_bar = progress_bar(progress)
        updated_msg = msg + f"\n*Progress:* {prog_bar}"
        requests.post(telegram_api("editMessageText"), json={
            "chat_id": TELEGRAM_CHAT_ID,
            "message_id": msg_id,
            "text": updated_msg,
            "parse_mode": "Markdown"
        })
        time.sleep(0.3)

    with open(file_path, "rb") as f:
        requests.post(telegram_api("sendDocument"), data={
            "chat_id": TELEGRAM_CHAT_ID,
            "caption": f"📦 `{filename}`",
            "parse_mode": "Markdown"
        }, files={"document": (filename, f)})

    time.sleep(2)
    requests.post(telegram_api("deleteMessage"), json={
        "chat_id": TELEGRAM_CHAT_ID,
        "message_id": msg_id
    })


def main():
    action = os.getenv("TELEGRAM_ACTION", "start")
    stage = os.getenv("CURRENT_STAGE", "Initializing")
    progress = float(os.getenv("PROGRESS", "0"))

    if action == "start":
        send_initial_message()
    elif action == "update":
        update_live_message(stage, progress)
    elif action == "end":
        delete_live_message()
        send_final_message(BUILD_STATUS)
        if BUILD_STATUS == "success" and ZIP_PATH and os.path.exists(ZIP_PATH):
            upload_file_with_progress(ZIP_PATH)


if __name__ == "__main__":
    main()
