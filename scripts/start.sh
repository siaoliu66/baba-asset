#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# Change to the project root (one level up from scripts/)
cd "$SCRIPT_DIR/.." || exit

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

show_menu() {
    clear
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}    ASSET v2 - 快速啟動系統 (Rapid Launch) ${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo -e "1. ${GREEN}啟動系統 (Start Server)${NC}"
    echo -e "2. ${YELLOW}初始化資料庫 (Init DB)${NC}"
    echo -e "3. ${YELLOW}匯入預設資料 (Seed Data)${NC}"
    echo -e "4. ${RED}重置整個系統 (Reset All)${NC}"
    echo -e "q. ${NC}離開 (Quit)${NC}"
    echo -e "${BLUE}----------------------------------------${NC}"
    echo -n "請選擇操作 [1]: "
}

check_venv() {
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    elif [ -d "venv" ]; then
        source venv/bin/activate
    else
        echo -e "${YELLOW}警告: 未發現 .venv 或 venv，嘗試直接執行...${NC}"
    fi
}

start_server() {
    # Detect local IP - Multi-method for reliability
    # Priority 1: Reachable IP via socket
    LOCAL_IP=$(python3 -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(0); try: s.connect(('8.8.8.8', 1)); ip = s.getsockname()[0]; finally: s.close(); print(ip)" 2>/dev/null)
    
    # Priority 2: macOS standard interface addresses
    if [ -z "$LOCAL_IP" ] || [ "$LOCAL_IP" == "127.0.0.1" ] || [ "$LOCAL_IP" == "0.0.0.0" ]; then
        LOCAL_IP=$(ifconfig en0 | grep "inet " | awk '{print $2}' | head -n 1)
        if [ -z "$LOCAL_IP" ]; then
            LOCAL_IP=$(ifconfig en1 | grep "inet " | awk '{print $2}' | head -n 1)
        fi
    fi
    
    # Priority 3: Last resort Fallback
    LOCAL_IP=${LOCAL_IP:-"127.0.0.1"}

    # Kill existing process on port 5520
    PID=$(lsof -ti:5520)
    if [ ! -z "$PID" ]; then
        echo -e "${YELLOW}⚠️ 發現連接埠 5520 被佔用 (PID: $PID)，正在清理...${NC}"
        kill -9 $PID 2>/dev/null
    fi

    echo -e "\n${GREEN}🚀 啟動伺服器中 (SocketIO/HTTPS)...${NC}"
    echo -e "🔗 網卡位址: ${YELLOW}https://127.0.0.1:5520${NC}"
    echo -e "🔗 手機連線: ${YELLOW}https://${LOCAL_IP}:5520${NC}"
    echo -e "\n${BLUE}--- 手機掃描下方 QR Code 快速登入 ---${NC}"
    
    # Generate QR Code in terminal with better compatibility
    echo -e "${BLUE}----------------------------------------${NC}"
    echo -e "   📱 掃描此 QR Code 登入   "
    echo -e "${BLUE}----------------------------------------${NC}"
    
    python3 -c "
import qrcode
import sys

url = 'https://${LOCAL_IP}:5520'
qr = qrcode.QRCode(border=2)
qr.add_data(url)
qr.make(fit=True)

# Custom ASCII generation for better dark/light theme compatibility
# Use standard blocks that work in most terminals
# White block: █ (U+2588), Black (space)
matrix = qr.get_matrix()
white_block = '\033[7m  \033[0m' # Inverted space = white block
black_block = '  '

print(f'\nURL: {url}\n')
for row in matrix:
    line = ''
    for cell in row:
        if cell:
            line += white_block # True = black module, but in QR typically dark on light. 
            # In terminals, usually light text on dark bg.
            # Standard QR: Dark modules on Light background.
            # In terminal: One needs 'light' block for module, 'dark' for bg?
            # Actually, standard libs invert. 
            # Let's trust print_ascii(invert=True) but make sure it prints to stdout correctly.
            pass
            
# Fallback to standard lib but force tty
qr.print_ascii(out=sys.stdout, tty=True, invert=True)
"

    echo -e "\n${BLUE}----------------------------------------${NC}"
    echo -e "${YELLOW}若無法掃描，請手動輸入: https://${LOCAL_IP}:5520${NC}"
    echo -e "${RED}注意：您必須與電腦連線至同一個 Wi-Fi 網路${NC}"
    echo -e "${BLUE}----------------------------------------${NC}"
    echo -e "(按 Ctrl+C 可停止伺服器)"
    export FLASK_APP=app.py
    export FLASK_ENV=development
    python run.py
}

init_db() {
    echo -e "\n${YELLOW}正在初始化資料庫...${NC}"
    rm -rf migrations
    rm -f instance/asset_management.sqlite
    flask db init
    flask db migrate -m "Initial migration"
    flask db upgrade
    echo -e "${GREEN}資料庫初始化完成！${NC}"
    read -p "按 Enter 鍵返回選單..."
}

seed_data() {
    echo -e "\n${YELLOW}正在匯入預設資料...${NC}"
    python3 seed.py
    echo -e "${GREEN}資料匯入完成！${NC}"
    read -p "按 Enter 鍵返回選單..."
}

# Main Loop
check_venv

while true; do
    show_menu
    echo -n "請選擇操作 [1] (3秒後自動啟動): "
    if read -t 3 choice; then
        : # Input received
    else
        echo -e "\n${GREEN}⏱️ 自動啟動中...${NC}"
        choice=1
    fi
    choice=${choice:-1} # Default to 1

    case $choice in
        1)
            start_server
            break
            ;;
        2)
            init_db
            ;;
        3)
            seed_data
            ;;
        4)
            read -p "確定要重置所有資料嗎？這將刪除所有現有數據！(y/N): " confirm
            if [[ $confirm == "y" || $confirm == "Y" ]]; then
                init_db
                seed_data
            fi
            ;;
        q|Q)
            echo -e "👋 再見！"
            exit 0
            ;;
        *)
            echo -e "${RED}無效的選擇，請重試。${NC}"
            sleep 1
            ;;
    esac
done
