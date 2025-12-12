import os
import shutil
import argparse

def create_game(name):
    root = os.path.dirname(__file__)
    src = os.path.join(root, "template")
    dest = os.path.join(root, "game", name)

    if not os.path.exists(src):
        print(f"模板不存在: template")
        return

    if os.path.exists(dest):
        print("遊戲已存在")
        return
    
    shutil.copytree(src, dest)
    print(f"[成功] 建立新遊戲於 developer/game/{name}/ ")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--template", default="generic")
    args = parser.parse_args()

    create_game(args.name)
