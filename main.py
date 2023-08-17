import os
import time
import sys
import random
import signal
import logging
from datetime import datetime, timezone

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from dotenv import load_dotenv


def WaitForPage(element, driver):
    global timeoutCounter   # If this reaches MAXTIMEOUT, exit program

    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, element)))
    except TimeoutException:
        timeoutCounter += 1
        return True
    
    timeoutCounter = 0
    return False

def HandleCard(driver, card, priceFloor, priceCeil):
    global netChange, stageChange, cardsMoved, timeoutCounter

    # Check if card is foil
    try:
        card.find_element(By.XPATH, ".//div[3]/div/div[2]/div/div[1]/div/span[3]")
        isFoil = True
    except:
        isFoil = False

    counter = 0
    while True:
        # Get card page link and open in a new tab
        try:
            cardLink = card.find_element(By.XPATH, ".//div[3]/div/div[1]/div/a").get_attribute("href")
        except:
            logging.warning(f"Couldn't get name of card {card}")    #! Sometimes this happens, dunno why
            timeoutCounter += 1
            if(timeoutCounter == 10):
                return True
            return False
        
        cardName = cardLink.split('/')[-1]

        # Check if cardName has "isFoil=Y". If so, something went wrong
        if("isFoil=Y" in cardName):
            counter += 1
            if(counter == 10):
                return True
            driver.refresh()
            time.sleep(random.uniform(2, 3)) # Prevent false positive and rate limiting
        else:
            break

    logging.info(f"Checking {cardName}")    
    
    time.sleep(random.uniform(0.5, 3))   # Avoid rate limiting
    driver.execute_script("window.open('');")
    driver.switch_to.window(driver.window_handles[1])
    driver.get(cardLink)

    while True:
        if WaitForPage("/html/body/main/div[3]/div[1]/h1", driver):
            logging.warning(f"Timeout on opening tab for card {cardName}")
            if (timeoutCounter == 10):
                return True
            driver.refresh()
            time.sleep(random.uniform(2, 3)) # Prevent false positive and rate limiting
            continue
        break

    # If card is foil, check the box first
    if isFoil:
        try:    # Some cards only have a foil version
            driver.find_element(By.XPATH, "/html/body/main/div[4]/section[2]/div/div[2]/div[1]/div/div[1]/label/span[1]").click()
            time.sleep(random.uniform(2, 3)) # Prevent false positive and rate limiting
            while True:
                if WaitForPage("/html/body/main/div[3]/div[1]/h1", driver):
                    logging.warning(f"Timeout on changing card {cardName} to foil")
                    if (timeoutCounter == 10):
                        return True
                    driver.refresh()
                    time.sleep(random.uniform(2, 3)) # Prevent false positive and rate limiting
                    continue
                break
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
        localTimeoutCounter = 0
        while True:
            try:
                driver.find_element(By.XPATH, f"/html/body/main/div[4]/section[5]/div/div[2]/div[{numberOfCard}]/div[3]/div[3]/div[2]").click()
            except:
                break    # No more cards

            if WaitForPage("/html/body/div[3]/div/div/div[2]/div/form/div[5]", driver):
                logging.warning(f"Timeout on changing card {cardName} price")
                if (timeoutCounter == 10):
                    return True
                driver.refresh()
                time.sleep(random.uniform(2, 3)) # Prevent false positive and rate limiting
                continue

            priceField = driver.find_element(By.XPATH, "/html/body/div[3]/div/div/div[2]/div/form/div[5]/div/input")
            priceField.clear()
            priceField.send_keys(str(newSellPrice))
            driver.find_element(By.XPATH, "/html/body/div[3]/div/div/div[2]/div/form/div[6]/button").click()
            
            # Wait for confirmation
            if WaitForPage("/html/body/main/div[1]/div", driver):
                logging.warning(f"Timeout on price change confirmation for card {cardName}")
                localTimeoutCounter += 1
                if(localTimeoutCounter == 10):
                    return True
                driver.refresh()
                time.sleep(random.uniform(2, 3)) # Prevent false positive and rate limiting
                continue

            numberOfCard += 1
            if(newSellPrice > priceCeil or newSellPrice < priceFloor):
                cardsMoved += 1

        logging.info(f"\tChanged from {sellPrice} to {newSellPrice} - trend is {priceTrend}")

        # Update net and stage change
        netChange = netChange + (newSellPrice - sellPrice) * (numberOfCard - 1)
        stageChange = stageChange + (newSellPrice - sellPrice) * (numberOfCard - 1)

    # If it was foil, revert to normal mode
    if isFoil:
        try:    # Some cards only have a foil version
            driver.find_element(By.XPATH, "/html/body/main/div[4]/section[2]/div/div[2]/div[1]/div/div[1]/label/span[1]").click()
            time.sleep(random.uniform(2, 3)) # Prevent false positive and rate limiting
            while True:
                if WaitForPage("/html/body/main/div[3]/div[1]/h1", driver):
                    logging.warning(f"Timeout on reverting foil on card {cardName}")
                    if (timeoutCounter == 10):
                        return True
                    driver.refresh()
                    time.sleep(random.uniform(2, 3)) # Prevent false positive and rate limiting
                    continue
                break
        except:
            pass

    # All done, close tab
    driver.close()
    driver.switch_to.window(driver.window_handles[0])
    return False
        
def LogIn(driver):
    global username, password

    # Open the webpage and wait for it to load
    driver.get(os.getenv("URL"))
    WaitForPage("/html/body/header/div[1]/div/div/form/button", driver)

    logging.info("page is opened")
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
    logging.info("Logged in")

    # Open active listings
    listingsLink = os.getenv("URL") + "/Stock/Offers/Singles"
    driver.get(listingsLink)
    WaitForPage("/html/body/main/div[7]/div[2]/div[1]/div[3]/div/div[1]/a", driver)

def setPriceRange(driver, price, priceCeil):
    # Filter by price
    URLaddon = f"?minPrice={price}&maxPrice={priceCeil}"
    link = os.getenv("URL") + "/Stock/Offers/Singles" + URLaddon
    driver.get(link)

    if(price != priceCeil):
        logging.info(f"\tChecking from {price} to {priceCeil}")
    else:
        logging.info(f"\tChecking {price}")

    WaitForPage("/html/body/main/div[6]/div[2]", driver)
    time.sleep(random.uniform(2, 3)) # Prevent false positive and rate limiting

def changePriceRange(priceFloor, driver, priceCeil):
    global stageChange, netChange

    logging.info(f"Finished range - Range change is {round(stageChange, 2)}; Net change is {round(netChange, 2)}")
    stageChange = 0

    priceCeil = round(priceFloor - 0.01, 2)
    priceFloor = round(priceFloor - 0.1 * priceFloor, 2)
    if(priceFloor < 0):
        return False, False
    elif(priceFloor > priceCeil):
        priceFloor = priceCeil
        
    setPriceRange(driver, priceFloor, priceCeil)
    priceFloor, priceCeil = checkForMaxRange(driver, priceFloor, priceCeil)

    return priceFloor, priceCeil

def handler(signum, frame):
    logging.warning(f"User terminated program - Net change is {round(netChange, 2)}")
    quit()
     
def checkForMaxRange(driver, priceFloor, priceCeil):
    while True:
        # Check if price range has more than 300 cards
        try:
            driver.find_element(By.XPATH, "/html/body/main/div[5]/small")
            logging.warning("Range has 300+ cards")
            # If program reaches here, too many cards. Try to change price range
            if(priceFloor != priceCeil):
                priceFloor = round(priceFloor + 0.01, 2)
                setPriceRange(driver, priceFloor, priceCeil)
            else:
                break
        except:
            range = driver.find_element(By.XPATH, "/html/body/main/div[5]/div[1]/span/span[1]").text
            logging.info(f"\tRange has {range} cards")
            break

    return priceFloor, priceCeil

def main():
    global timeoutCounter   # If this reaches 10, exit program
    timeoutCounter = 0
    
    # Handle Ctrl+C from user
    signal.signal(signal.SIGINT, handler)

    # Set up logging
    now = datetime.now()
    filename = now.strftime("/home/galego/Automarket/%Y%m%d_%H%M%S")
    logging.basicConfig(filename = filename, encoding = "utf-8", level = logging.INFO)
    startingTime = now.strftime("%Y/%m/%d %H:%M:%S")
    logging.info(f"Starting review at {startingTime}")

    # Check if a command line argument was given (price to start from)
    priceToStart = 1
    if(len(sys.argv) > 1):
        priceToStart = float(sys.argv[1])
    else:
        priceToStart = float(input("From which price would you like to start? "))

    # Get environment variables
    logging.info("loading env vars")
    load_dotenv()
    global username, password
    username = os.getenv("LOGINUSER")
    password = os.getenv("PASSWORD")
    chromedriver = os.getenv("CHROMEDRIVER")
    
    # Setup browser options
    try:
        options = uc.ChromeOptions()
        options.binary_location = os.getenv("BROWSER")
        options.add_argument('--disable-popup-blocking')
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        driver = uc.Chrome(driver_executable_path=chromedriver, use_subprocess=True, options=options)
    except Exception as e:
        print(e)
        exit(1)


    # Show overall change in the end
    global netChange, stageChange
    netChange = 0
    stageChange = 0

    # To make sure every card is seen
    global cardsMoved

    logging.info("going to log in")
    LogIn(driver)

    priceFloor = priceToStart
    if(priceFloor == 1):
        priceCeil = 1000
    else:
        priceCeil = round(priceFloor + 0.1 * priceFloor, 2)

    setPriceRange(driver, priceFloor, priceCeil)
    priceFloor, priceCeil = checkForMaxRange(driver, priceFloor, priceCeil)

    reset = False
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
        cards = driver.find_elements(By.XPATH, table)
        cardsMoved = 0
        for card in cards:
            if HandleCard(driver, card, priceFloor, priceCeil):
                reset = True
                break

        if reset:
            break

        # * This method will eventually check cards that were already checked. Still, better to check twice than none. It may also happen that it doesn't check enough cards, still better than checking none
        check = cardsMoved
        while(cardsMoved != 0):
            # Refresh page and check cards that underflew to this page (cardsMoved)
            driver.refresh()
            time.sleep(random.uniform(2, 3)) # Prevent false positive and rate limiting
            WaitForPage(table, driver)

            # Check if range has more than 300 cards
            tooManyCards = False
            try:
                driver.find_element(By.XPATH, "/html/body/main/div[5]/small")
                table = "/html/body/main/div[7]"
                tooManyCards = True
            except:
                table = "/html/body/main/div[6]"

            table += "/div[2]/div"

            cards = driver.find_elements(By.XPATH, table)
            iter = 0
            check = cardsMoved
            cardsMoved = 0
            for card in reversed(cards):
                if HandleCard(driver, card, priceFloor, priceCeil):
                    reset = True
                    break
                iter += 1
                if(iter == check):
                    break
                
        # Check if there's another page
        if not tooManyCards:
            skipButton = "/html/body/main/div[5]/div[2]/div/a[2]"
        else:
            skipButton = "/html/body/main/div[6]/div[2]/div/a[2]"

        try:
            driver.find_element(By.XPATH, skipButton).click()
            time.sleep(random.uniform(2, 3)) # Prevent false positive and rate limiting
            WaitForPage(table, driver)
        except: # No more pages, change price range
            priceFloor, priceCeil = changePriceRange(priceFloor, driver, priceCeil)
            if(priceFloor == False):
                break
            
    now = datetime.now()
    finishingTime = now.strftime("%Y/%m/%d %H:%M:%S")
    logging.info(f"Finished review at {finishingTime} - Net change is {round(netChange, 2)}")
    driver.quit()
    quit()

if(__name__ == "__main__"):
    main()
