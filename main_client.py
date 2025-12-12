import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

def main() :
    while True :
        print("\n=== Game Store System ===")
        print("1. 我是玩家 (Player)")
        print("2. 我是開發者 (Developer)")
        print("3. 離開")
        choice = input("請選擇身分 (1-3): ").strip()

        if choice == '1' :
            from player.player_client import PlayerClient
            print("\n>> 啟動玩家客戶端...")
            client = PlayerClient()
            client.main_menu()
        
        elif choice == '2' :
            from developer.developer_client import DevClient
            print("\n>> 啟動開發者客戶端...")
            client = DevClient()
            client.start()

        elif choice == '3' :
            print("Bye!")
            sys.exit(0)
        
        else :
            print("無效選項")

if __name__ == "__main__" :
    main()