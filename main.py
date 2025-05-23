import os
import time
import sys
import random
import signal
import logging
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium_stealth import stealth

from dotenv import load_dotenv, set_key


#? Misc.
def selectTCG():
    # check previous TCG
    previousTCG = os.getenv("TCG")
    
    # select new one
    if(previousTCG == "Magic"):
        TCG = "Pokemon"
    elif(previousTCG == "Pokemon"):
        TCG = "YuGiOh"
    elif(previousTCG == "YuGiOh"):
        TCG = "Magic"

    # save current TCG
    set_key(dotenv_path=".env", key_to_set="TCG", value_to_set=TCG)

    logging.info(f"Reviewing {TCG} cards")
    return TCG


#? selenium funcions
def WaitForPage(element, driver):
    global timeoutCounter   # If this reaches MAXTIMEOUT, exit program

    wait = random.uniform(5, 11) # random wait
    try:
        WebDriverWait(driver, wait).until(EC.presence_of_element_located((By.XPATH, element)))
    except TimeoutException:
        timeoutCounter += 1
        return True
    
    timeoutCounter = 0
    return False

def handler(signum, frame):
    logging.warning(f"User terminated program - Net change is {round(netChange, 2)}")
    driver.quit()
    quit()


#? Interaction with website
def LogIn(driver, TCG):
    global username, password

    # Open the webpage and wait for it to load
    URL = os.getenv("URL") + TCG
    driver.get(URL)
    while True:
      if WaitForPage("/html/body/header/div[1]/div/div/form/div/button", driver):
        if (timeoutCounter == 10):
          logging.warning(f"Timeout while loading webpage")
          return True
        continue
      break

    #logging.info("page is opened")
    # Accept cookies (this takes care of future problems)
    try:
        driver.find_element(By.XPATH, "/html/body/header/div[1]/div/div/form/div/button").click()
    except:
        pass

    # Log in
    driver.find_element(By.XPATH, "/html/body/header/nav[1]/ul/li/div/form/div[1]/div/input").send_keys(username)
    driver.find_element(By.XPATH, "/html/body/header/nav[1]/ul/li/div/form/div[2]/div/input").send_keys(password)
    driver.find_element(By.XPATH, "/html/body/header/nav[1]/ul/li/div/form/input[3]").click()
    
    # Wait until page is loaded
    WaitForPage("/html/body/header/nav[1]/ul/li/ul/li[2]/a", driver)
    #logging.info("Logged in")

def changePriceRange(priceFloor, driver, priceCeil, TCG):
    global stageChange, netChange

    logging.info(f"\tFinished range - Range change is {round(stageChange, 2)}; Net change is {round(netChange, 2)}")
    stageChange = 0

    priceCeil = round(priceFloor - 0.01, 2)
    priceFloor = round(priceFloor - 0.2 * priceFloor, 2)
    if(priceFloor <= 0):
        return False, False, False
    elif(priceFloor > priceCeil):
        priceFloor = priceCeil
        
    setPriceRange(driver, priceFloor, priceCeil, TCG)
    cardnumber = checkForMaxRange(driver, priceFloor, priceCeil)
    while(cardnumber == 300):
        if(priceFloor != priceCeil):
            priceFloor = round(priceFloor + 0.01, 2)
            setPriceRange(driver, priceFloor, priceCeil, TCG)
            cardnumber = checkForMaxRange(driver, priceFloor, priceCeil)
        else:
            break

    return priceFloor, priceCeil, cardnumber

def checkForMaxRange(driver, priceFloor, priceCeil):
    # Check if price range has more than 300 cards
    try:
        driver.find_element(By.XPATH, "/html/body/main/div[3]/div[2]/div[1]/small")
        return 300
    except:
        range = driver.find_element(By.XPATH, "/html/body/main/div[3]/div[2]/div[1]/div[1]/span/span[1]").text
        return range

def skipToPage(page, priceFloor, priceCeil, TCG):
    logging.info(f"Skipping to page {page}")
    
    URLaddon = f"?minPrice={priceFloor}&maxPrice={priceCeil}&site={page}"
    link = os.getenv("URL") + TCG + "/Stock/Offers/Singles" + URLaddon
    driver.get(link)

    while True:
        if WaitForPage("/html/body/main/div[6]/div[2]", driver):
            if (timeoutCounter == 10):
                logging.warning("Timeout on changing price range")
                driver.quit()
                return True
            driver.refresh()
            continue
        break


#? Algorithm functions
def HandleCard(driver, card, priceFloor, priceCeil):    # card = /html/body/main/div[3]/div[2]/div[2/3]/div[2]/div[*]
    global netChange, stageChange, cardsMoved, timeoutCounter

    # Get card page link and open in a new tab
    try:
        cardLink = card.find_element(By.XPATH, ".//div[3]/div/div[1]/a").get_attribute("href")
    except:
        logging.warning(f"Couldn't get name of card {card}")
        return True
    
    cardName = cardLink.split('/')[-1]

    # Check if cardName has "isFoil=Y". If so, something went wrong
    if("isFoil=Y" in cardName):
        return True

    logging.info(f"Checking {cardName}")    
    
    #time.sleep(random.uniform(0.5, 1))   # Avoid rate limiting
    driver.execute_script("window.open('');")
    driver.switch_to.window(driver.window_handles[1])
    driver.get(cardLink)    #! how is this working? not specifing website

    while True:
        if WaitForPage("/html/body/main/div[2]/div[1]/h1", driver):
            if (timeoutCounter == 10):
                logging.warning(f"Timeout while opening tab for card {cardName}")
                return True
            driver.refresh()
            continue
        break

    # Check for existence of foil version
    try:
        driver.find_element(By.XPATH, "/html/body/main/div[3]/section[2]/div/div[2]/div[1]/div/div[1]/label")
        isThereFoilVersion = True
    except:
        isThereFoilVersion = False

    #* there can be multiple cards for sale, each with their own prices. go through all
    numberOfCard = 1
    localTimeoutCounter = 0
    while True:
        #time.sleep(random.uniform(0.5, 1))   # Avoid rate limiting
        try:    # check if there is another card
            # Get current sell price
            sellPrice = float(driver.find_element(By.XPATH, f"/html/body/main/div[3]/section[5]/div/div[2]/div[{numberOfCard}]/div[3]/div[1]/div/div/span").get_attribute("innerHTML")[:-2].replace(',', '.'))

            # Get quality of card
            quality = driver.find_element(By.XPATH, f"/html/body/main/div[3]/section[5]/div/div[2]/div[{numberOfCard}]/div[2]/div/div[2]/div/div[1]/a/span").get_attribute("innerHTML")

            # check if card is foil
            try:
                driver.find_element(By.XPATH, f"/html/body/main/div[3]/section[5]/div/div[2]/div[{numberOfCard}]/div[2]/div/div[2]/div/div[1]/span[2]")
                isFoil = True
            except:
                isFoil = False
        
        except:
            break    # No more cards

        
        # If card is foil, check the box first
        if isFoil:
            try:    # Some cards only have a foil version
                driver.find_element(By.XPATH, "/html/body/main/div[3]/section[2]/div/div[2]/div[1]/div/div[1]/label/span[1]").click()
                time.sleep(random.uniform(2, 3)) # Prevent false positive and rate limiting
                while True:
                    if WaitForPage("/html/body/main/div[2]/div[1]/h1", driver):
                        if (timeoutCounter == 10):
                            logging.warning(f"Timeout on changing card {cardName} to foil")
                            return True
                        driver.refresh()
                        continue
                    break
            except:
                pass

        #* Get current price trend and price minimum (removing " $" and replacing ',' by '.')
        if isThereFoilVersion:
            # Not guaranteed to have a price trend (cards that never sell)
            try:
                priceTrend = float(driver.find_elements(By.XPATH, "/html/body/main/div[3]/section[2]/div/div[2]/div[1]/div/div[2]/div/div[2]/dl/dd/span")[-4].get_attribute("innerHTML")[:-2].replace(',', '.'))

                priceFrom = float(driver.find_elements(By.XPATH, "/html/body/main/div[3]/section[2]/div/div[2]/div[1]/div/div[2]/div/div[2]/dl/dd")[-5].get_attribute("innerHTML")[:-2].replace(',', '.'))
            except:
                # Only use "from" price
                priceTrend = 0

                priceFrom = float(driver.find_elements(By.XPATH, "/html/body/main/div[3]/section[2]/div/div[2]/div[1]/div/div[2]/div/div[2]/dl/dd")[-4].get_attribute("innerHTML")[:-2].replace(',', '.'))
        else:
            try:
                priceTrend = float(driver.find_elements(By.XPATH, "/html/body/main/div[3]/section[2]/div/div[2]/div[1]/div/div[1]/div/div[2]/dl/dd/span")[-4].get_attribute("innerHTML")[:-2].replace(',', '.'))
            except:
                # Only use "from" price
                priceTrend = 0

            priceFrom = float(driver.find_elements(By.XPATH, "/html/body/main/div[3]/section[2]/div/div[2]/div[1]/div/div[1]/div/div[2]/dl/dd")[-5].get_attribute("innerHTML")[:-2].replace(',', '.'))

        # Calculate the new sell price (with 2 decimal places) and check if current sell price is the same. if there is no trend, set at the From
        if(priceTrend != 0):
            #! this depends on the quality. change this accordingly
            if(quality == "NM"):
                percentage = 0.95    
            elif(quality == "EX"):
                percentage = 0.9
            elif(quality == "GD"):
                percentage = 0.85
            elif(quality == "LP"):
                percentage = 0.8
            elif(quality == "PL"):
                percentage = 0.7
            elif(quality == "PO"):
                percentage = 0.6
            else:
                logging.warning(f"Got invalid card quality -> {quality}")

            newSellPrice = round(abs(percentage * (priceTrend - priceFrom)) + priceFrom, 2)
        else:
            newSellPrice = round(priceFrom, 2)

        if(sellPrice != newSellPrice):  # Values are different, change current sell price
            driver.find_element(By.XPATH, f"/html/body/main/div[3]/section[5]/div/div[2]/div[{numberOfCard}]/div[3]/div[3]/div[2]").click()

            if WaitForPage("/html/body/div[3]/div/div/div[2]/div/form/div[5]", driver):
                if (timeoutCounter == 10):
                    logging.warning(f"Timeout on opening window to change card {cardName} price")
                    return True
                driver.refresh()
                continue

            fields = driver.find_elements(By.XPATH, "/html/body/div[3]/div/div/div[2]/div/form/div")
            priceField = fields[-2].find_element(By.XPATH, ".//div/input")
            priceField.clear()
            priceField.send_keys(str(newSellPrice))
            fields[-1].find_element(By.XPATH, ".//button").click()
            
            # Wait for confirmation
            if WaitForPage("/html/body/main/div[1]/div", driver):
                localTimeoutCounter += 1
                time.sleep(localTimeoutCounter * random.uniform(4, 10)) # incrementing wait
                if(localTimeoutCounter == 10):
                    logging.warning(f"Timeout on price change confirmation on card {cardName}")
                    return True
                driver.refresh()    
                continue

            logging.info(f"\tChanged from {sellPrice} to {newSellPrice} - trend is {priceTrend}")
            priceDiff = abs(newSellPrice - sellPrice)
            percentageChange = priceDiff / sellPrice
            if(percentageChange > 0.25 and priceDiff >= 0.1):   
                logging.info(f"^^^^CHANGED {round(percentageChange * 100, 2)}%^^^^")
                
            # Update net and stage change
            netChange = netChange + (newSellPrice - sellPrice)
            stageChange = stageChange + (newSellPrice - sellPrice)

            if(newSellPrice > priceCeil or newSellPrice < priceFloor):
                cardsMoved += 1

        # If it was foil, revert to normal mode
        if isFoil:
            try:    # Some cards only have a foil version
                driver.find_element(By.XPATH, "/html/body/main/div[3]/section[2]/div/div[2]/div[1]/div/div[1]/label/span[1]").click()
                time.sleep(random.uniform(2, 3)) # Prevent false positive and rate limiting
                while True:
                    if WaitForPage("/html/body/main/div[2]/div[1]/h1", driver):
                        if (timeoutCounter == 10):
                            logging.warning(f"Timeout on reverting foil on card {cardName}")
                            return True
                        driver.refresh()
                        continue
                    break
            except:
                pass

        numberOfCard += 1

    # All done, close tab
    driver.close()
    driver.switch_to.window(driver.window_handles[0])
    return False
        
def setPriceRange(driver, price, priceCeil, TCG):
    # Filter by price
    URLaddon = f"?minPrice={price}&maxPrice={priceCeil}"
    link = os.getenv("URL") + TCG + "/Stock/Offers/Singles" + URLaddon
    driver.get(link)

    if(price != priceCeil):
        logging.info(f"---->Checking from {price} to {priceCeil}")
    else:
        logging.info(f"---->Checking {price}")

    while True:
        if WaitForPage("/html/body/main/div[2]/div/h1", driver):
            if (timeoutCounter == 10):
                logging.warning("Timeout on changing price range")
                driver.quit()
                quit()
            driver.refresh()
            continue
        break

    return False

def iterateCards(driver, priceFloor, priceCeil, cardsInRange, TCG):
    global cardsMoved # To make sure every card is seen

    while True:
        #? this check is necessary for when priceCeil == priceFloor && more than 300 cards
        cardnumber = checkForMaxRange(driver, priceFloor, priceCeil)
        if(cardnumber == 300):
            logging.info("\tRange has 300+ cards")
            tooManyCards = True
            table = "/html/body/main/div[3]/div[2]/div[3]/div[2]"
        else:
            logging.info(f"\tRange has {cardnumber} cards")
            tooManyCards = False
            table = "/html/body/main/div[3]/div[2]/div[2]/div[2]"       

        cardsintable = table + "/div"
        cards = driver.find_elements(By.XPATH, cardsintable)
        cardsMoved = 0
        slowdown = random.randint(1, 5)
        cardsUntilSlowdown = 0    # count how many cards were checked to trigger slowdown
        for card in cards:
            if HandleCard(driver, card, priceFloor, priceCeil): # if this returns true, something went wrong
                return

            cardsUntilSlowdown = cardsUntilSlowdown + 1
            if(cardsUntilSlowdown >= slowdown):   # slow down because of rate limiting
                time.sleep(random.uniform(4, 10))
                slowdown = random.randint(1, 5)
                cardsUntilSlowdown = 0


        # * This method will eventually check cards that were already checked. Still, better to check twice than none. It may also happen that it doesn't check enough cards, still better than checking none
        check = cardsMoved
        while(cardsMoved != 0):
            # Refresh page and check cards that underflew to this page (cardsMoved)
            driver.refresh()
            time.sleep(random.uniform(2, 5)) # Prevent false positive and rate limiting
            while True:
                if WaitForPage(table, driver):
                    if (timeoutCounter == 10):
                        logging.warning(f"Timeout while refreshing page")
                        return
                    driver.refresh()
                    continue
                break

            cardnumber = checkForMaxRange(driver, priceFloor, priceCeil)
            if(cardnumber == 300):
                tooManyCards = True
                table = "/html/body/main/div[3]/div[2]/div[3]/div[2]"
            else:
                tooManyCards = False
                table = "/html/body/main/div[3]/div[2]/div[2]/div[2]"  

            cardsintable = table + "/div"
            cards = driver.find_elements(By.XPATH, cardsintable)
            check = cardsMoved
            cardsMoved = 0
            for iter, card in enumerate(reversed(cards)):
                if HandleCard(driver, card, priceFloor, priceCeil):
                    return
                
                if(iter == check - 1):
                    break

        # Check if there's another page
        if not tooManyCards:
            skipButton = "/html/body/main/div[3]/div[2]/div[1]/div[2]/div/a[2]"
        else:
            skipButton = "/html/body/main/div[3]/div[2]/div[2]/div[2]/div/a[2]"

        try:
            driver.find_element(By.XPATH, skipButton).click()
            time.sleep(random.uniform(2, 5)) # Prevent false positive
            WaitForPage(table, driver)
        except: # No more pages, change price range
            priceFloor, priceCeil, cardsInRange = changePriceRange(priceFloor, driver, priceCeil, TCG)
            if(priceFloor == False):
                break   # end


#? main
def main():
    global timeoutCounter, driver   # If this reaches 10, exit program
    timeoutCounter = 0
    
    # Handle Ctrl+C from user
    signal.signal(signal.SIGINT, handler)

    # Load environment variables
    load_dotenv()
    
    # Set up logging
    now = datetime.now()
    logDir = str(os.getenv("LOGDIR"))
    filename = now.strftime(logDir + "%Y%m%d_%H%M%S")
    logging.basicConfig(filename = filename, encoding = "utf-8", level = logging.INFO)
    startingTime = now.strftime("%Y/%m/%d %H:%M:%S")
    logging.info(f"Starting review at {startingTime}")

    # Check if a command line argument was given (price to start from and/or page)
    priceToStart = 1
    pageToStart = 1
    if(len(sys.argv) == 3):
        pageToStart = int(sys.argv[2]) 
        priceToStart = float(sys.argv[1])
    elif(len(sys.argv) == 2):
        priceToStart = float(sys.argv[1])

    global username, password
    username = os.getenv("LOGINUSER")
    password = os.getenv("PASSWORD")
    
    # Select TCG to check
    TCG = selectTCG()

    # Setup browser options
    try:
        options = webdriver.ChromeOptions()
        options.binary_location = os.getenv("BROWSER")

        #?logging.info("setting browser options")
        # random user agents to choose from
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15',
            ]
        user_agent = random.choice(user_agents)
        options.add_argument("--no-sandbox")
        options.add_argument(f'user-agent={user_agent}')
        options.add_argument("--headless")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--blink-settings=imagesEnabled=false")    # disable loading images
        driver = webdriver.Chrome(options=options)
        stealth(driver, languages=["en-US", "en"], vendor="Google Inc.", platform="Win32", webgl_vendor="Intel Inc.", renderer="Intel Iris OpenGL Engine", fix_hairline=True)   # needed to bypass cloudflare
        #logging.info("set")
    except Exception as e:
        print("got an error ->", e)
        logging.info(e)
        exit(1)

    # To show overall change in the end
    global netChange, stageChange
    netChange = 0
    stageChange = 0

    #logging.info("going to log in")
    if LogIn(driver, TCG):
      driver.quit()
      quit()

    priceFloor = priceToStart
    priceCeil = priceToStart
    if(priceFloor == 1):
        priceCeil = 1000
    elif(priceFloor > 0.1):   # below 10 cents search each value individually (lots of cards): priceFloor = priceCeil
        priceCeil = round(priceFloor + 0.2 * priceFloor, 2)

    setPriceRange(driver, priceFloor, priceCeil, TCG)
    cardnumber = checkForMaxRange(driver, priceFloor, priceCeil)
    while(cardnumber == 300):
        logging.info("\tRange has 300+ cards")
        if(priceFloor != priceCeil):
            priceFloor = round(priceFloor + 0.01, 2)
            setPriceRange(driver, priceFloor, priceCeil, TCG)
            cardnumber = checkForMaxRange(driver, priceFloor, priceCeil)
        else:
            break

    if(pageToStart != 1):
        skipToPage(pageToStart, priceFloor, priceCeil, TCG)

    #* Iterate through every card
    iterateCards(driver, priceFloor, priceCeil, cardnumber, TCG)
            
    now = datetime.now()
    finishingTime = now.strftime("%Y/%m/%d %H:%M:%S")
    logging.info(f"Finished review at {finishingTime} - Net change is {round(netChange, 2)}")
    driver.quit()
    quit()


if(__name__ == "__main__"):
    main()
