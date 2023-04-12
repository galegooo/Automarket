import os
import time
import sys
import random
import signal

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from dotenv import load_dotenv


def WaitForPage(element, driver):
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, element)))
    except TimeoutException:
        return True
    
    return False

def HandleCard(driver, card):
    global netChange, stageChange

    # Check if card is foil
    try:
        card.find_element(By.XPATH, ".//div[3]/div/div[2]/div/div[1]/span[3]")
        isFoil = True
    except:
        isFoil = False

    # Get card page link and open in a new tab
    try:
        cardLink = card.find_element(By.XPATH, ".//div[3]/div/div[1]/a").get_attribute("href")
    except:
        print("Couldn't get name of card ", card)
        return True
    
    cardName = cardLink.split('/')[-1]
    print(f"Checking {cardName}", end = "")    
    
    time.sleep(random.uniform(1, 4))   # Avoid rate limiting
    driver.execute_script("window.open('');")
    driver.switch_to.window(driver.window_handles[1])
    driver.get(cardLink)

    if WaitForPage("/html/body/main/div[3]/div[1]/h1", driver):
        print("Timeout on opening tab for card ", cardName)
        return True

    # If card is foil, check the box first
    if isFoil:
        try:    # Some cards only have a foil version
            driver.find_element(By.XPATH, "/html/body/main/div[4]/section[2]/div/div[2]/div[1]/div/div[1]/label/span[1]").click()
            time.sleep(random.uniform(2, 3)) # Prevent false positive and rate limiting
            if WaitForPage("/html/body/main/div[3]/div[1]/h1", driver):
                print("Timeout on changing card ", cardName, " to foil")
                return True
        except:
            pass

    # Get current price trend. This differs with whether there is a foil version or not
    # Check for existence of foil version
    isThereFoilVersion = True
    try:
        driver.find_element(By.XPATH, "/html/body/main/div[4]/section[2]/div/div[2]/div[1]/div/div[1]/label")
    except:
        isThereFoilVersion = False

    # Get current price trend and price minimum (removing " $" and replacing ',' by '.')
    if isThereFoilVersion:
        priceTrend = float(driver.find_elements(By.XPATH, "/html/body/main/div[4]/section[2]/div/div[2]/div[1]/div/div[2]/div/div[2]/dl/dd/span")[-4].get_attribute("innerHTML")[:-2].replace(',', '.'))

        priceFrom = float(driver.find_elements(By.XPATH, "/html/body/main/div[4]/section[2]/div/div[2]/div[1]/div/div[2]/div/div[2]/dl/dd")[-5].get_attribute("innerHTML")[:-2].replace(',', '.'))
    else:
        priceTrend = float(driver.find_elements(By.XPATH, "/html/body/main/div[4]/section[2]/div/div[2]/div[1]/div/div[1]/div/div[2]/dl/dd/span")[-4].get_attribute("innerHTML")[:-2].replace(',', '.'))

        priceFrom = float(driver.find_elements(By.XPATH, "/html/body/main/div[4]/section[2]/div/div[2]/div[1]/div/div[1]/div/div[2]/dl/dd")[-5].get_attribute("innerHTML")[:-2].replace(',', '.'))

    # Get current sell price
    sellPrice = float(driver.find_element(By.XPATH, "/html/body/main/div[4]/section[5]/div/div[2]/div[1]/div[3]/div[1]/div/div/span").get_attribute("innerHTML")[:-2].replace(',', '.'))


    # Calculate the new sell price (with 2 decimal places) and check if current sell price is the same
    newSellPrice = round(abs(0.95 * (priceTrend - priceFrom)) + priceFrom, 2)
    if(sellPrice != newSellPrice):  # Values are different, change current sell price
        # There can be more than 1 card listed
        numberOfCard = 1
        while True:
            try:
                driver.find_element(By.XPATH, f"/html/body/main/div[4]/section[5]/div/div[2]/div[{numberOfCard}]/div[3]/div[3]/div[2]").click()
            except:
                break    # No more cards

            if WaitForPage("/html/body/div[3]/div/div/div[2]/div/form/div[5]", driver):
                print("Timeout on changing card ", cardName, " price")
                return True

            priceField = driver.find_element(By.XPATH, "/html/body/div[3]/div/div/div[2]/div/form/div[5]/div/input")
            priceField.clear()
            priceField.send_keys(str(newSellPrice))
            driver.find_element(By.XPATH, "/html/body/div[3]/div/div/div[2]/div/form/div[6]/button").click()
            
            # Wait for confirmation
            if WaitForPage("/html/body/main/div[1]/div", driver):
                print("Timeout on price change confirmation for card ", cardName)
                return True

            numberOfCard += 1

        print(f" -> changed from {sellPrice} to {newSellPrice} - trend is {priceTrend}")

        # Update net and stage change
        netChange = netChange + (newSellPrice - sellPrice) * (numberOfCard - 1)
        stageChange = stageChange + (newSellPrice - sellPrice) * (numberOfCard - 1)
    else:
        print("")

    # If it was foil, revert to normal mode
    if isFoil:
        try:    # Some cards only have a foil version
            driver.find_element(By.XPATH, "/html/body/main/div[4]/section[2]/div/div[2]/div[1]/div/div[1]/label/span[1]").click()
            time.sleep(random.uniform(2, 3)) # Prevent false positive and rate limiting
            if WaitForPage("/html/body/main/div[3]/div[1]/h1", driver):
                print("Timeout on reverting foil on card ", cardName)
                return True
        except:
            pass

    # All done, close tab
    driver.close()
    driver.switch_to.window(driver.window_handles[0])
    return False
        
def LogIn(driver):
    global username, password

    # Open the webpage
    driver.get(os.getenv("URL"))

    # Accept cookies (this takes care of future problems)
    try:
        driver.find_element(By.XPATH, "/html/body/header/div[1]/div/div/form/button").click()
    except:
        pass

    # Log in
    driver.find_element(By.XPATH, "/html/body/header/nav[1]/ul/li/div/form/div[1]/div/input").send_keys(username)
    driver.find_element(By.XPATH, "/html/body/header/nav[1]/ul/li/div/form/div[2]/div/input").send_keys(password)
    driver.find_element(By.XPATH, "/html/body/header/nav[1]/ul/li/div/form/input[3]").click()
    
    # Wait until page is loaded
    WaitForPage("/html/body/header/nav[1]/ul/li/ul/li[2]/a", driver)
    print("Logged in")

    # Open active listings
    driver.find_element(By.XPATH, "/html/body/header/nav[1]/ul/li/ul/li[2]/a").click()
    driver.find_element(By.XPATH, "/html/body/header/nav[1]/ul/li/ul/li[2]/div/a[2]").click()
    WaitForPage("/html/body/main/div[4]/div/a", driver)
    driver.find_element(By.XPATH, "/html/body/main/div[4]/div/a").click()
    WaitForPage("/html/body/main/div[7]/div[2]/div[1]/div[3]/div/div[1]/a", driver)

def setPriceRange(driver, price, priceCeil):
    if(price == 1):
        print(f"Checking from {price}")
        # Filter by price
        driver.find_element(By.XPATH, "/html/body/main/div[4]/div/form/div[4]/div/div[1]/input").send_keys(price)
        driver.find_element(By.XPATH, "/html/body/main/div[4]/div/form/div[6]/input").click()
    else:
        print(f"\nChecking from {price} to {priceCeil}")

        # Filter by price
        driver.find_element(By.XPATH, "/html/body/main/div[4]/div/form/div[4]/div/div[1]/input").clear()
        driver.find_element(By.XPATH, "/html/body/main/div[4]/div/form/div[4]/div/div[1]/input").send_keys(price)

        driver.find_element(By.XPATH, "/html/body/main/div[4]/div/form/div[4]/div/div[2]/input").clear()
        driver.find_element(By.XPATH, "/html/body/main/div[4]/div/form/div[4]/div/div[2]/input").send_keys(priceCeil)

        driver.find_element(By.XPATH, "/html/body/main/div[4]/div/form/div[6]/input").click()

    WaitForPage("/html/body/main/div[6]/div[2]", driver)
    time.sleep(random.uniform(2, 3)) # Prevent false positive and rate limiting

def handler(signum, frame):
    print(f"User terminated program - Net change is {round(netChange, 2)}")
    quit()
    
signal.signal(signal.SIGINT, handler)

# Check if a command line argument was given (price to start from)
priceToStart = 1
if(len(sys.argv) > 1):
    priceToStart = float(sys.argv[1])

# Show overall change in the end
global netChange, stageChange
netChange = 0
stageChange = 0

# Get environment variables
load_dotenv()
global username, password
username = os.getenv("LOGINUSER")
password = os.getenv("PASSWORD")

# Setup browser options
options = uc.ChromeOptions()
options.binary_location = os.getenv("BRAVE")
options.add_argument('--disable-popup-blocking')
options.add_argument("--headless=new")
options.add_argument("--window-size=1920,1080")
driver = uc.Chrome(use_subprocess=True, options=options)
# * driver_executable_path=os.getenv("CHROMEDRIVER") is not needed in Linux 


LogIn(driver)

priceFloor = priceToStart
if(priceFloor == 1):
    setPriceRange(driver, priceFloor, False)
else:
    priceCeil = round(priceFloor + 0.1 * priceFloor, 2)
    setPriceRange(driver, priceFloor, priceCeil)

while True:
    # Check if new price range has more than 300 cards
    try:
        driver.find_element(By.XPATH, "/html/body/main/div[5]/small")
        print("Range has 300+ cards")
        # If program reaches here, too many cards. Try to change price range again
        if(priceFloor != priceCeil):
            priceFloor = round(priceFloor + 0.01, 2)
            setPriceRange(driver, priceFloor, priceCeil)
        else:
            break
    except:
        break

reset = False
global lastCardChecked  # To make sure every card is read

# Iterate through every card
while True:
    # Check if range has more than 300 cards
    tooManyCards = False
    try:
        driver.find_element(By.XPATH, "/html/body/main/div[5]/small")
        table = "/html/body/main/div[7]"
        tooManyCards = True
    except:
        table = "/html/body/main/div[6]"

    table += "/div[2]/div"
    try:    # Page can have 0 cards
        cards = driver.find_elements(By.XPATH, table)
        for card in cards:
            if HandleCard(driver, card):
                reset = True
                break
    except:
        pass

    if reset:
        print("Reset triggered")
        break

    # Check if there's another page
    if not tooManyCards:
        skipButton = "/html/body/main/div[5]/div[2]/div/a[2]"
    else:
        skipButton = "/html/body/main/div[6]/div[2]/div/a[2]"

    try:
        driver.find_element(By.XPATH, skipButton).click()
        time.sleep(random.uniform(2, 3)) # Prevent false positive and rate limiting
        reset = WaitForPage(table, driver)
    except: # No more pages, change price range
        priceCeil = round(priceFloor - 0.01, 2)
        priceFloor = round(priceFloor - 0.1 * priceFloor, 2)
        if(priceFloor == priceCeil):
            priceFloor = round(priceFloor - 0.01, 2)
        if(priceFloor < 0):
            print("Reached price floor < 0")
            break

        print(f"Finished range - Range change is {round(stageChange, 2)}; Net change is {round(netChange, 2)}")
        stageChange = 0
        setPriceRange(driver, priceFloor, priceCeil)

        while True:
            # Check if new price range has more than 300 cards
            try:
                driver.find_element(By.XPATH, "/html/body/main/div[5]/small")
                print("Range has 300+ cards")
                # If program reaches here, too many cards. Try to change price range again
                if(priceFloor != priceCeil):
                    priceFloor = round(priceFloor + 0.01, 2)
                    setPriceRange(driver, priceFloor, priceCeil)
                else:
                    break
            except:
                break
        
print(f"Finished reviewing - Net change is {round(netChange, 2)}")
driver.quit()
quit()
