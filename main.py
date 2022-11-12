import os
import time
import math

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from dotenv import load_dotenv


def WaitForPage(element, driver):
    # Get current URL for handling if wait exceed timeout
    URL = driver.current_url
    try:
        WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.XPATH, element)))
    except TimeoutException:
        # Close all tabs, wait and relaunch URL
        while True:
            try:
                driver.close()
            except:
                break

        time.sleep(10)
        driver.get(URL)

def HandleCard(driver, card):
    global netChange

    # Check if card is foil
    try:
        card.find_element(By.XPATH, ".//td[7]/span")
        isFoil = True
    except:
        isFoil = False

    # Get card page link and open in a new tab
    cardLink = card.find_element(By.XPATH, ".//td[2]/div/div/a").get_attribute("href")
    cardName = cardLink.split('/')[-1]
    print(f"Checking {cardName}")    
    
    driver.execute_script("window.open('');")
    driver.switch_to.window(driver.window_handles[1])
    driver.get(cardLink)

    WaitForPage("/html/body/main/div[3]/div[1]/h1", driver)

    # If card is foil, check the box first
    if isFoil:
        driver.find_element(By.XPATH, "/html/body/main/div[4]/section[2]/div/div[2]/div[1]/div/div[1]/label/span[1]").click()
        time.sleep(1) # This is to avoid line below to give false positive
        WaitForPage("/html/body/main/div[3]/div[1]/h1", driver)

    # Get current price trend. This differs with whether there is a foil version or not
    # Check for existence of foil version
    isThereFoilVersion = True
    try:
        driver.find_element(By.XPATH, "/html/body/main/div[4]/section[2]/div/div[2]/div[1]/div/div[3]")
    except:
        isThereFoilVersion = False

    # Get current price trend (removing " $" and replacing ',' by '.')
    if isThereFoilVersion:
        priceTrend = float(driver.find_elements(By.XPATH, "/html/body/main/div[4]/section[2]/div/div[2]/div[1]/div/div[2]/div/div[2]/dl/dd/span")[-4].get_attribute("innerHTML")[:-2].replace(',', '.'))
    else:
        priceTrend = float(driver.find_elements(By.XPATH, "/html/body/main/div[4]/section[2]/div/div[2]/div[1]/div/div[1]/div/div[2]/dl/dd/span")[-4].get_attribute("innerHTML")[:-2].replace(',', '.'))

    # Get current sell price
    sellPrice = float(driver.find_element(By.XPATH, "/html/body/main/div[4]/section[5]/div/div[2]/div[1]/div[3]/div[1]/div/div/span").get_attribute("innerHTML")[:-2].replace(',', '.'))

    # Calculate the new sell price (with 2 decimal places) and check if current sell price is the same
    newSellPrice = round(0.9 * priceTrend, 2)
    if(sellPrice != newSellPrice):  # Values are different, change current sell price
        while True:
            # There can be more than 1 card listed
            numberOfCard = 1
            try:
                driver.find_element(By.XPATH, f"/html/body/main/div[4]/section[5]/div/div[2]/div[{numberOfCard}]/div[3]/div[3]/button[2]").click()
            except:
                break    # No more cards

            WaitForPage(f"/html/body/main/div[4]/section[5]/div/div[2]/div[{numberOfCard}]/div[4]/form/div[5]/div/input", driver)
            priceField = driver.find_element(By.XPATH, f"/html/body/main/div[4]/section[5]/div/div[2]/div[{numberOfCard}]/div[4]/form/div[5]/div/input")
            priceField.clear()
            priceField.send_keys(str(newSellPrice))
            driver.find_element(By.XPATH, f"/html/body/main/div[4]/section[5]/div/div[2]/div[{numberOfCard}]/div[4]/form/div[6]/div/div/button").click()
            # Wait for confirmation
            WaitForPage("/html/body/main/div[1]/div/div/h4", driver)

            numberOfCard += 1

        print(f"Changed {cardName} from {sellPrice} euros to {newSellPrice} euros - Price trend is {priceTrend} euros.")

        # Update net change
        netChange = netChange + newSellPrice - sellPrice

    # If it was foil, revert to normal mode
    if isFoil:
        driver.find_element(By.XPATH, "/html/body/main/div[4]/section[2]/div/div[2]/div[1]/div/div[1]/label/span[1]").click()
        time.sleep(1) # This is to avoid line below to give false positive
        WaitForPage("/html/body/main/div[3]/div[1]/h1", driver)

    # All done, close tab
    driver.close()
    driver.switch_to.window(driver.window_handles[0])
        
def LogIn(driver):
    # Get credentials
    load_dotenv()
    username = os.getenv("USER")
    password = os.getenv("PASSWORD")

    # Open the webpage
    driver.get("https://www.cardmarket.com/en/Magic")

    # Log in
    driver.find_element(By.XPATH, "/html/body/header/nav[1]/ul/li/div/button").click()
    driver.find_element(By.XPATH, "/html/body/header/nav[1]/div[3]/div/form/div[1]/div/input").send_keys(username)
    driver.find_element(By.XPATH, "/html/body/header/nav[1]/div[3]/div/form/div[2]/div/input").send_keys(password)
    driver.find_element(By.XPATH, "/html/body/header/nav[1]/div[3]/div/form/input[3]").click()

    # Wait until page is loaded
    WaitForPage("/html/body/header/nav[1]/ul/li/ul/li[2]/a", driver)
    print("Logged in")

    # Open active listings
    driver.find_element(By.XPATH, "/html/body/header/nav[1]/ul/li/ul/li[2]/a").click()
    driver.find_element(By.XPATH, "/html/body/header/nav[1]/ul/li/ul/li[2]/div/a[2]").click()
    WaitForPage("/html/body/section/div[1]/div/div[3]/div/div/div[2]/div/div/a", driver)
    driver.find_element(By.XPATH, "/html/body/section/div[1]/div/div[3]/div/div/div[2]/div/div/a").click()
    WaitForPage("/html/body/section/div[1]/div/div[3]/div[2]/div[2]/table/tbody/tr[1]/td[2]", driver)

    # Check number of cards, this will be used to flip pages (each shows 30 cards)
    numberCards = int(driver.find_element(By.XPATH, "/html/body/section/div[1]/div/div[3]/div[2]/div[1]/span[1]/span[1]/span").get_attribute("innerHTML"))
    numberPages = math.ceil(numberCards / 30)

    return numberPages


# This will be cool in the end
global netChange
netChange = 0

# Setup browser options
options = Options()
options.binary_location = "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\Brave.exe"
driver = webdriver.Chrome(options = options, executable_path="D:\\Python3.11\\pip\\Selenium\\chromedriver.exe")

numberPages = LogIn(driver)

# Iterate through every card
for page in range(numberPages):
    print(f"Page {page}")
    table = driver.find_element(By.XPATH, "/html/body/section/div[1]/div/div[3]/div[2]/div[2]/table/tbody")

    for card in table.find_elements(By.XPATH, ".//tr"):
        HandleCard(driver, card)
        time.sleep(0.5)   # Avoid rate limiting

    # Next page if not last
    if(page != numberPages - 1):
        driver.find_element(By.XPATH, "/html/body/section/div[1]/div/div[3]/div[2]/div[3]/span[3]/span[3]").click()
        time.sleep(3) # Prevent false positive
        WaitForPage("/html/body/section/div[1]/div/div[3]/div[2]/div[2]/table/tbody/tr[1]/td[2]/div/div/a", driver)
        
print(f"Finished reviewing - Net change is {netChange} euros")
driver.quit()