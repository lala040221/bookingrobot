import os
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


BASE_URL = "https://pub-tyn-reha-shihao.leaftech.tw/"
TIME_SLOTS = ["11:15", "17:45"]          # 你要嘗試的時段
VALID_WEEKDAYS = {1, 3, 5}               # Tue/Thu/Sat (Mon=0)


def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    return webdriver.Chrome(options=options)


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

    login_button = driver.find_element(By.CSS_SELECTOR, "input[type='submit']")
    login_button.click()

    # 登入後會有「預約訂車」連結
    wait.until(EC.presence_of_element_located((By.LINK_TEXT, "預約訂車")))


def pick_valid_dates(driver):
    radios = driver.find_elements(By.CSS_SELECTOR, "input[type='radio'][name='DT']")
    valid = []
    for radio in radios:
        date_str = radio.get_attribute("value")
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d")
        except Exception:
            continue
        if d.weekday() in VALID_WEEKDAYS:
            valid.append((date_str, radio))
    return valid


def check_and_book(driver, wait, date_str, radio_elem, is_backup=False):
    print(f"▶ 檢查日期: {date_str} {'(候補)' if is_backup else ''}")

    # 點日期 radio
    radio_elem.click()

    # iframe 內容可能要等一下
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "selDay")))

    try:
        # 依序嘗試時段
        for ts in TIME_SLOTS:
            slot_cells = driver.find_elements(By.XPATH, f"//td[contains(., '{ts}')]")
            if not slot_cells:
                print(f"⚠ 找不到 {ts} 的欄位")
                continue

            booked_this_ts = False
            for cell in slot_cells:
                links = cell.find_elements(By.XPATH, ".//a[contains(., '可訂車')]")
                if links:
                    print(f"✅ {ts} 有空位，可預約")
                    links[0].click()
                    booked_this_ts = True
                    break

            if booked_this_ts:
                # 點完「可訂車」通常會出現下一步
                try:
                    driver.switch_to.default_content()
                    next_btn = wait.until(
                        EC.element_to_be_clickable((By.XPATH, "//input[@type='submit' and @value='下一步']"))
                    )
                    next_btn.click()
                    print("➡ 成功點擊『下一步』")
                    return True
                except Exception:
                    print("❌ 沒找到『下一步』，可能已預約過或流程不同")
                    return False

        print("🔍 兩個時段都沒有可訂車")
        return False

    finally:
        driver.switch_to.default_content()


def fill_trip_info_fixed(driver, wait):
    # 這段你原本寫在候補流程裡，我保留（如果頁面不同，可能要再調 selector）
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "selDay")))
    try:
        def pick_option(select_name, contains_text):
            sel = driver.find_element(By.NAME, select_name)
            for opt in sel.find_elements(By.TAG_NAME, "option"):
                if contains_text in opt.text:
                    opt.click()
                    return True
            return False

        pick_option("fromHistory1", "南豐街")
        pick_option("toHistory1", "長庚桃園")
        pick_option("fromHistory2", "長庚桃園")
        pick_option("toHistory2", "南豐街")

        driver.find_element(By.ID, "radio_companion1_1").click()
        driver.find_element(By.ID, "radio_purpose1_1").click()
        driver.find_element(By.ID, "radio_companion2_1").click()
        driver.find_element(By.ID, "radio_purpose2_1").click()

        print("📋 陪同與目的完成 ✅")

    finally:
        driver.switch_to.default_content()


def try_backup_flow(driver, wait):
    print("已額滿，嘗試候補")

    backup_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(., '候補訂車')]")))
    backup_btn.click()

    # 候補頁面會重新產生 radio
    time.sleep(1)
    radios = driver.find_elements(By.CSS_SELECTOR, "input[type='radio'][name='DT']")

    for radio in radios:
        date_str = radio.get_attribute("value")
        d = datetime.strptime(date_str, "%Y-%m-%d")
        if d.weekday() in VALID_WEEKDAYS:
            ok = check_and_book(driver, wait, date_str, radio, is_backup=True)
            if ok:
                # 進到填表頁面：填行程 + 送出
                fill_trip_info_fixed(driver, wait)
                try:
                    confirm_btn = wait.until(
                        EC.element_to_be_clickable((By.XPATH, "//input[@type='submit' and contains(@value, '確認訂車')]"))
                    )
                    confirm_btn.click()
                    print("✅ 已成功候補訂車")
                    return True
                except Exception as e:
                    print("❌ 找不到『確認訂車』按鈕", e)
                    return False

    print("🔍 候補頁沒有符合星期二/四/六的日期")
    return False


def main():
    driver = get_driver()
    wait = WebDriverWait(driver, 15)

    try:
        login(driver, wait)
        driver.find_element(By.LINK_TEXT, "預約訂車").click()

        valid_dates = pick_valid_dates(driver)
        for date_str, radio in valid_dates:
            print(f"嘗試預約：{date_str}")
            ok = check_and_book(driver, wait, date_str, radio)
            if ok:
                print("✅ 預約流程已進下一步（若還要填表可再加）")
                return

        # 都沒成功 → 候補
        try_backup_flow(driver, wait)

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
