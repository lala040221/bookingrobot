import sys
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent

def run(script: str):
    subprocess.run([sys.executable, str(BASE / script)], check=True)

def main():
    print("🚀 執行 auto_book.py...")
    run("auto_book.py")

    print("📚 執行 check_book.py...")
    run("check_book.py")

if __name__ == "__main__":
    main()
