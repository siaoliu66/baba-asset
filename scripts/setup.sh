#!/bin/bash

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}    ASSET v2 - 系統環境建置精靈        ${NC}"
echo -e "${BLUE}========================================${NC}"

# 1. Check Python
echo -e "${GREEN}[1/4] 檢查 Python 環境...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}錯誤: 找不到 python3，請先安裝 Python。${NC}"
    exit 1
fi
python3 --version

# 2. Virtual Env
echo -e "${GREEN}[2/4] 檢查虛擬環境...${NC}"
if [ ! -d "venv" ]; then
    echo "建立 venv..."
    python3 -m venv venv
fi
source venv/bin/activate

# 3. Install Deps
echo -e "${GREEN}[3/4] 安裝相依套件...${NC}"
pip install -r requirements.txt
pip install pyopenssl # Ensure SSL support

# 4. DB Init
echo -e "${GREEN}[4/4] 初始化資料庫...${NC}"
if [ ! -d "migrations" ]; then
    echo "初始化 Migrations..."
    flask db init
fi
flask db migrate -m "Auto migration"
flask db upgrade

# 5. Admin Seed
echo -e "${GREEN}[5/4] 檢查管理員帳號...${NC}"
# Run a python snippet to check/create admin
python3 -c "
from app import create_app, db
from core.models.auth import User
app = create_app()
with app.app_context():
    if not User.query.filter_by(username='admin').first():
        print('建立預設管理員 (admin/admin)...')
        u = User(username='admin', email='admin@example.com', role_id=1)
        u.set_password('admin')
        db.session.add(u)
        db.session.commit()
    else:
        print('管理員已存在。')
"

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✅ 環境建置完成！${NC}"
echo -e "請執行 ${BLUE}./scripts/start.sh${NC} 啟動系統"
