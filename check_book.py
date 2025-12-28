import os
import re
import time
from datetime import datetime

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://pub-tyn-reha-shihao.leaftech.tw/"
LINE_NOTIFY_API = "https://notify-api.line.me/api/notify"


def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    return webdriver.Chrome(options=options)


def line_notify(message: str):
    token = os.environ.get("LINE_NOTIFY_TOKEN", "").strip()
    if not token:
        print("ℹ️ 沒有設定 LINE_NOTIFY_TOKEN，跳過通知。")
        print(message)
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {"message": message}
    r = requests.post(LINE_NOTIFY_API, headers=headers, data=data, timeout=20)
    print("📨 Line notify status:", r.status_code)


def login(driver, wait):
    ac = os.environ["REHA_AC"]
    ps = os.environ["REHA_PS"]

    driver.get(BASE_URL)
    account_input = wait.until(EC.presence_of_element_located((By.NAME, "ac")))
    account_input.clear()
    account_input.send_keys(ac)

    password_input = driver.find_element(By.NAME, "ps")
    password_input.clear()
    password_input.send_keys(ps)

    driver.find_element(By.CSS_SELECTOR, "input[type='submit']").click()
    wait.until(EC.presence_of_element_located((By.LINK_TEXT, "訂車查詢")))


def check_dispatched(driver):
    # 你的表格解析邏輯保留，但「去重」先改成：只要找到車號就列出
    rows = driver.find_elements(By.XPATH, "//tr")
    current_date = None
    msgs = []

    date_pattern = re.compile(r"\d{4}-\d{2}-\d{2}")

    for row in rows:
        tds = row.find_elements(By.TAG_NAME, "td")

        # 日期行
        if len(tds) == 1 and "bgcolor" in row.get_attribute("outerHTML"):
            date_text = tds[0].text.strip()
            if date_pattern.fullmatch(date_text):
                current_date = datetime.strptime(date_text, "%Y-%m-%d")
            else:
                current_date = None
            continue

        # 明細行
        if current_date and len(tds) >= 6:
            time_str = tds[0].text.strip()
            car_number = tds[4].text.strip()
            if car_number:
                msgs.append(f"{current_date.strftime('%Y-%m-%d')} {time_str} ➜ 車號: {car_number}")

    return msgs


def main():
    driver = get_driver()
    wait = WebDriverWait(driver, 15)

    try:
        login(driver, wait)
        driver.find_element(By.LINK_TEXT, "訂車查詢").click()
        time.sleep(1)

        msgs = check_dispatched(driver)
        if msgs:
            message = "✅ 派車成功紀錄：\n" + "\n".join(msgs)
            line_notify(message)
        else:
            print("🔍 沒有派車車號紀錄")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
