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

from dotenv import load_dotenv


def WaitForPage(element, driver):
    global timeoutCounter   # If this reaches MAXTIMEOUT, exit program

    wait = random.uniform(3, 10) # random wait
    try:
        WebDriverWait(driver, wait).until(EC.presence_of_element_located((By.XPATH, element)))
    except TimeoutException:
        timeoutCounter += 1
        return True
    
    timeoutCounter = 0
    return False

def HandleCard(driver, card, priceFloor, priceCeil):
    global netChange, stageChange, cardsMoved, timeoutCounter, countSinceLastChange

    # Check if card is foil
    # card = /html/body/main/div[6/5(depends on if page is at max card count)]/div[2]/div[*]
    try:
        card.find_element(By.XPATH, ".//div[3]/div/div[2]/div/div[1]/span[2]")
        isFoil = True
    except:
        isFoil = False

    counter = 0
    while True:
        # Get card page link and open in a new tab
        try:
            cardLink = card.find_element(By.XPATH, ".//div[3]/div/div[1]/a").get_attribute("href")
        except:
            logging.warning(f"Couldn't get name of card {card}")
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
            #time.sleep(random.uniform(2, 3)) # Prevent false positive and rate limiting
        else:
            break

    logging.info(f"Checking {cardName}")    
    
    #time.sleep(random.uniform(0.5, 3))   # Avoid rate limiting
    driver.execute_script("window.open('');")
    driver.switch_to.window(driver.window_handles[1])
    driver.get(cardLink)

    while True:
        if WaitForPage("/html/body/main/div[2]/div[1]/h1", driver):
            if (timeoutCounter == 10):
                logging.warning(f"Timeout while opening tab for card {cardName}")
                return True
            driver.refresh()
            #time.sleep(random.uniform(2, 3)) # Prevent false positive and rate limiting
            continue
        break

    # Check for existence of foil version
    isThereFoilVersion = True
    try:
        driver.find_element(By.XPATH, "/html/body/main/div[3]/section[2]/div/div[2]/div[1]/div/div[1]/label")
    except:
        isThereFoilVersion = False

    #* there can be multiple cards for sale, each with their own prices. go through all
    numberOfCard = 1
    localTimeoutCounter = 0
    while True:
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
                        #time.sleep(random.uniform(2, 3)) # Prevent false positive and rate limiting
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
                countSinceLastChange = 0    # this is global
                driver.find_element(By.XPATH, f"/html/body/main/div[3]/section[5]/div/div[2]/div[{numberOfCard}]/div[3]/div[3]/div[2]").click()

                if WaitForPage("/html/body/div[3]/div/div/div[2]/div/form/div[5]", driver):
                    if (timeoutCounter == 10):
                        logging.warning(f"Timeout on changing card {cardName} price")
                        return True
                    driver.refresh()
                    #time.sleep(random.uniform(2, 3)) # Prevent false positive and rate limiting
                    continue

                fields = driver.find_elements(By.XPATH, "/html/body/div[3]/div/div/div[2]/div/form/div")
                priceField = fields[-2].find_element(By.XPATH, ".//div/input")
                priceField.clear()
                priceField.send_keys(str(newSellPrice))
                fields[-1].find_element(By.XPATH, ".//button").click()
                
                # Wait for confirmation
                if WaitForPage("/html/body/main/div[1]/div", driver):
                    localTimeoutCounter += 1
                    if(localTimeoutCounter == 10):
                        logging.warning(f"Timeout on price change confirmation for card {cardName}")
                        return True
                    driver.refresh()
                    #time.sleep(random.uniform(2, 3)) # Prevent false positive and rate limiting
                    continue

                logging.info(f"\tChanged from {sellPrice} to {newSellPrice} - trend is {priceTrend}")
                # Update net and stage change
                netChange = netChange + (newSellPrice - sellPrice)
                stageChange = stageChange + (newSellPrice - sellPrice)

                if(newSellPrice > priceCeil or newSellPrice < priceFloor):
                    cardsMoved += 1
            else:   # not changing price
                countSinceLastChange += 1    # this is global

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
                            #time.sleep(random.uniform(2, 3)) # Prevent false positive and rate limiting
                            continue
                        break
                except:
                    pass

            numberOfCard += 1

    # All done, close tab
    driver.close()
    driver.switch_to.window(driver.window_handles[0])
    return False
        
def LogIn(driver):
    global username, password

    # Open the webpage and wait for it to load
    driver.get(os.getenv("URL"))
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

    # Open active listings ! no longer needed, just straight to startingPrice
    #listingsLink = os.getenv("URL") + "/Stock/Offers/Singles"
    #driver.get(listingsLink)
    #WaitForPage("/html/body/main/div[7]/div[2]/div[1]/div[3]/div/div[1]/a", driver)

def setPriceRange(driver, price, priceCeil):
    # Filter by price
    URLaddon = f"?minPrice={price}&maxPrice={priceCeil}"
    link = os.getenv("URL") + "/Stock/Offers/Singles" + URLaddon
    driver.get(link)

    if(price != priceCeil):
        logging.info(f"---->Checking from {price} to {priceCeil}")
    else:
        logging.info(f"---->Checking {price}")

    while True:
        if WaitForPage("/html/body/main/div[6]/div[2]", driver):
            if (timeoutCounter == 10):
                logging.warning("Timeout on changing price range")
                driver.quit()
                return True
            driver.refresh()
            continue
        break

    return False

def changePriceRange(priceFloor, driver, priceCeil):
    global stageChange, netChange

    logging.info(f"\tFinished range - Range change is {round(stageChange, 2)}; Net change is {round(netChange, 2)}")
    stageChange = 0

    priceCeil = round(priceFloor - 0.01, 2)
    priceFloor = round(priceFloor - 0.1 * priceFloor, 2)
    if(priceFloor < 0):
        return False, False
    elif(priceFloor > priceCeil):
        priceFloor = priceCeil
        
    if(setPriceRange(driver, priceFloor, priceCeil)):   #timeout
        return False, False
    priceFloor, priceCeil = checkForMaxRange(driver, priceFloor, priceCeil)

    return priceFloor, priceCeil

def handler(signum, frame):
    logging.warning(f"User terminated program - Net change is {round(netChange, 2)}")
    driver.quit()
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
                if(setPriceRange(driver, priceFloor, priceCeil)):   #timeout
                    return False, False
            else:
                break
        except:
            range = driver.find_element(By.XPATH, "/html/body/main/div[4]/div[1]/span/span[1]").text
            logging.info(f"\tRange has {range} cards")
            break

    return priceFloor, priceCeil

def main():
    global timeoutCounter, countSinceLastChange, driver   # If this reaches 10, exit program
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

    # Check if a command line argument was given (price to start from)
    priceToStart = 1
    if(len(sys.argv) > 1):
        priceToStart = float(sys.argv[1])
    #else:
        #priceToStart = float(input("From which price would you like to start? "))

    global username, password
    username = os.getenv("LOGINUSER")
    password = os.getenv("PASSWORD")

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

    # Show overall change in the end
    global netChange, stageChange
    netChange = 0
    stageChange = 0

    # To make sure every card is seen
    global cardsMoved

    #logging.info("going to log in")
    if LogIn(driver):
      driver.quit()
      quit()

    priceFloor = priceToStart
    if(priceFloor == 1):
        priceCeil = 1000
    else:
        priceCeil = round(priceFloor + 0.1 * priceFloor, 2)

    if(setPriceRange(driver, priceFloor, priceCeil)):   #timeout
        driver.quit()
        quit()
    priceFloor, priceCeil = checkForMaxRange(driver, priceFloor, priceCeil)
    if(priceFloor == False and priceCeil == False):
        driver.quit()
        quit()

    reset = False
    # Iterate through every card
    while True:
        # Check if range has more than 300 cards
        tooManyCards = False
        try:
            driver.find_element(By.XPATH, "/html/body/main/div[5]/small")
            table = "/html/body/main/div[6]"
            tooManyCards = True
        except:
            table = "/html/body/main/div[5]"

        table += "/div[2]/div"
        cards = driver.find_elements(By.XPATH, table)
        cardsMoved = 0
        countSinceLastChange = 0    # this is global
        for card in cards:
            if HandleCard(driver, card, priceFloor, priceCeil):
                reset = True
                break

            slowdown = random.randint(2, 6)
            if(countSinceLastChange > slowdown):   # haven't changed the price in a bit, slow down because of rate limiting
                time.sleep(random.uniform(2, 7))
                countSinceLastChange = 0    

        if reset:
            break

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
                        driver.quit()
                        return True
                    driver.refresh()
                    #time.sleep(random.uniform(2, 3)) # Prevent false positive and rate limiting
                    continue
                break

            # Check if range has more than 300 cards
            tooManyCards = False
            try:
                driver.find_element(By.XPATH, "/html/body/main/div[5]/small")
                table = "/html/body/main/div[6]"
                tooManyCards = True
            except:
                table = "/html/body/main/div[5]"

            table += "/div[2]/div"

            cards = driver.find_elements(By.XPATH, table)
            check = cardsMoved
            cardsMoved = 0
            for iter, card in enumerate(reversed(cards)):
                if HandleCard(driver, card, priceFloor, priceCeil):
                    reset = True
                    break
                
                if(iter == check - 1):
                    break

        # Check if there's another page
        if not tooManyCards:
            skipButton = "/html/body/main/div[4]/div[2]/div/a[2]"
        else:
            skipButton = "/html/body/main/div[5]/div[2]/div/a[2]"

        try:
            driver.find_element(By.XPATH, skipButton).click()
            #time.sleep(random.uniform(2, 3)) # Prevent false positive and rate limiting
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
