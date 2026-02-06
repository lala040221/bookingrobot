import os
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


BASE_URL = "https://pub-tyn-reha-shihao.leaftech.tw/"
TIME_SLOTS = ["11:15", "17:45"]          # 你要嘗試的時段
VALID_WEEKDAYS = {1,3,5}               # Tue/Thu/Sat (Mon=0)


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
from selenium.common.exceptions import TimeoutException

def click_confirm_submit(driver, wait):
    driver.switch_to.default_content()

    # 1) 進 selDay iframe
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "selDay")))

    # 2) 找到「確認訂車」submit
    btn = wait.until(EC.presence_of_element_located(
        (By.XPATH, "//input[@type='submit' and contains(@value,'確認訂車')]")
    ))

    # 3) 保險：捲到可視範圍 + JS click（避免被遮住/不可點）
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
    wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//input[@type='submit' and contains(@value,'確認訂車')]")
    ))
    driver.execute_script("arguments[0].click();", btn)
    print("✅ 已點擊『確認訂車』")

    driver.switch_to.default_content()

    # 4) 如果網站有跳 confirm/alert，順便接受
    try:
        alert = WebDriverWait(driver, 3).until(EC.alert_is_present())
        print("🟡 alert:", alert.text)
        alert.accept()
        print("✅ 已按下 alert OK/Yes")
    except TimeoutException:
        pass

    return True
def check_and_book(driver, wait, date_str, radio_elem, is_backup=False):
    print(f"▶ 檢查日期: {date_str} {'(候補)' if is_backup else ''}")

    radio_elem.click()
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "selDay")))

    picked = []
    try:
        for ts in TIME_SLOTS:
            clicked = False
            for _ in range(3):
                slot_cells = driver.find_elements(By.XPATH, f"//td[contains(normalize-space(.), '{ts}')]")
                if not slot_cells:
                    time.sleep(0.3)
                    continue

                for cell in slot_cells:
                    links = cell.find_elements(By.XPATH, ".//a[contains(., '可訂車')]")
                    if links:
                        print(f"✅ {ts} 有空位，可預約")
                        links[0].click()
                        picked.append(ts)
                        clicked = True
                        break

                if clicked:
                    time.sleep(0.5)  # 等頁面更新
                    break

                time.sleep(0.3)

            if not clicked:
                print(f"🔍 {ts} 沒有可訂車")

        if len(picked) != len(TIME_SLOTS):
            print(f"❌ 只成功點到 {picked}，未達成需要的 {TIME_SLOTS}，不按下一步")
            return False

        # 兩個都點到 -> 按下一步
        # 先試 iframe 內
        try:
            next_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@type='submit' and (@value='下一步' or contains(@value,'下一步'))]"))
            )
            next_btn.click()
            print("➡（iframe內）已成功點擊『下一步』")
            return True
        except Exception as e1:
            print("⚠ iframe 內找不到『下一步』，改在外層找…", type(e1).__name__)

        # 再試 iframe 外
        driver.switch_to.default_content()
        try:
            next_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@type='submit' and (@value='下一步' or contains(@value,'下一步'))]"))
            )
            next_btn.click()
            print("➡（外層）已成功點擊『下一步』")
            return True
        except Exception as e2:
            print("❌ 外層也找不到『下一步』：", type(e2).__name__)
            print("🔎 目前網址：", driver.current_url)
            return False

    finally:
        # 確保離開 iframe
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
    


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
        debug_buttons_everywhere(driver)
def debug_buttons_everywhere(driver):
    def dump_in_current_context(tag):
        elems = driver.find_elements(By.TAG_NAME, tag)
        print(f"\n---- <{tag}> count = {len(elems)} ----")
        for i, el in enumerate(elems[:30]):  # 最多印 30 個避免爆量
            txt = (el.text or "").strip()
            t = el.get_attribute("type")
            val = el.get_attribute("value")
            name = el.get_attribute("name")
            eid = el.get_attribute("id")
            cls = el.get_attribute("class")
            if tag == "input" and t not in ("submit", "button"):
                continue
            if tag in ("button", "a") and not txt and not val:
                continue
            print(i, f"type={t!r} value={val!r} text={txt!r} id={eid!r} name={name!r} class={cls!r}")

    driver.switch_to.default_content()
    print("\n========== DEBUG: default_content ==========")
    dump_in_current_context("input")
    dump_in_current_context("button")
    dump_in_current_context("a")

    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    print(f"\n========== DEBUG: iframes count = {len(iframes)} ==========")
    for idx, fr in enumerate(iframes):
        print(idx, "name=", fr.get_attribute("name"),
                 "id=", fr.get_attribute("id"),
                 "src=", fr.get_attribute("src"))

    # 逐一進每個 iframe 掃按鈕
    for idx in range(len(iframes)):
        try:
            driver.switch_to.default_content()
            iframes = driver.find_elements(By.TAG_NAME, "iframe")  # 重新抓，避免 stale
            driver.switch_to.frame(iframes[idx])
            print(f"\n========== DEBUG: inside iframe[{idx}] ==========")
            dump_in_current_context("input")
            dump_in_current_context("button")
            dump_in_current_context("a")
        except Exception as e:
            print(f"⚠ iframe[{idx}] debug failed:", type(e).__name__)
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
            # ok = click_confirm_submit(driver, wait)
            # if ok:
            #     print("🎉 已嘗試送出（請到網站確認是否成功）")
            #     return True
            # else:
            #     return False
            ok = check_and_book(driver, wait, date_str, radio, is_backup=True)
            if ok:
                # 進到填表頁面：填行程 + 送出
                fill_trip_info_fixed(driver, wait)
                #fill_trip_info_fixed(driver, wait)
                ok = click_confirm_submit(driver, wait)
                return ok

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
