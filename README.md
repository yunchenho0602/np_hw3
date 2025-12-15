2025 網路程式設計概論 HW3 - 遊戲商城系統
===
專案說明
---
>這是一套實作多人連線遊戲商城系統，採用Client - Server架構，透過TCP socket溝通，並使用自定義protocol。

本系統包含三種Server以及Client
- **Server** : 使用者管理、房間管理、遊戲開始
- **Database Server** : 使用者與遊戲資料儲存
- **Game Server** : 遊戲邏輯

系統架構
---
    Client
    │
    ▼
    Lobby Server ─────► Database Server
    │
    ▼
    Game Server

專案目錄結構
---
所有指令均於根目錄(np_hw3)下操作

    np_hw3/
    │
    ├─ common/
    │   └─ protocol.py
    |   └─ constant.py
    │
    ├─ developer/
    │   └─ developer_client.py
    |   └─ create_game_template.py
    |   └─ game/
    |   └─ template/
    |       └─ protocol.py
    |       └─ game_server.py
    |       └─ client/
    |           └─ protocol.py
    |           └─ run.py
    │
    ├─ player/
    │   └─ player_client.py      
    │
    ├─ server/
    │   └─ db_server.py 
    |   └─ server.py        
    │
    ├─ main_client.py
    ├─ requirements.txt
    └─ README.md

環境需求
---
- 作業系統：Linux / macOS / Windows
- Python 版本：Python 3.8 以上

環境安裝
---
下載檔案
```python
git clone https://github.com/yunchenho0602/np_hw3.git
```
專案執行所需套件已整理至requirements.txt中，請在專案根目錄執行
```python
pip install -r requirements.txt
```
操作流程
---
**設定連線資訊**

    進入common/constant.py修改SERVER_PORT以及SERVER_IP
**啟動Server**
```python
python3 server/server.py
```
**啟動Client**
```python
python3 main_client.py
```
啟動Client後，即可選擇身分(開發者/玩家)，進入各自帳號管理介面，登入後進入功能選單。

開發者(developer)開發功能
---
- 進入開發者的功能選單後可以透過 **建立新專案** 創建符合平台的template
- 新專案會建立於 **/developer/game/** 中，此資料夾為開發者的工作區，欲上傳平台的遊戲請放置於此資料夾中。
