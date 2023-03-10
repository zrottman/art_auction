from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
import csv
import requests
import time
import json
from math import ceil
import os
from unidecode import unidecode
import config.scraper_config as config
import logging

logging.basicConfig(level=logging.INFO if config.VERBOSE else logging.WARNING)

def extract_page_data(bsObj, artist_name):
    '''
    Extracts relevant information about artowkrs from a page of auction results.

    Parameters:
        bsObj (bs4.BeautifulSoup): The Beautiful Soup object containing the 
            HTML of the page.
        artist_name (str): The name of the artist to associate with the works 
            of art.

    Returns:
        page_out (List[List[str]]): A list of lists, where each inner list
            contains information about a single work of art.The information
            includes:
                - artist_name
                - title
                - date
                - medium
                - dims
                - auction_date
                - auction_house
                - auction_sale
                - auction_lot
                - price_realized
                - estimate
    '''

    rows = bsObj.select(config.ROWS_CLASS)
    page_out = []

    for row in rows:
        work_data = {}
        work_data['artist_name'] = artist_name
        cols = row.find_all('div', class_={config.COLS_CLASS[0], config.COLS_CLASS[1]})

        # Column 0: Title, Date, Medium, Dims
        try:
            work_data['col_0'] = cols[0].get_text("|", strip=True).split('|')
        except:
            pass 

        # Title
        try:
            work_data['title'] = cols[0].i.get_text(strip=True)
        except:
            pass

        # Date
        try:
            work_data['date'] = cols[0].i.next_sibling.get_text(strip=True)
        except:
            pass

        # Medium and Dims
        medium_and_dims = cols[0].find_all('div', class_=config.FIELD_CLASS)
        try:
            work_data['medium'] = medium_and_dims[0].get_text(strip=True)
        except:
            pass

        try:
            work_data['dims'] = medium_and_dims[1].get_text(strip=True)
        except:
            pass

        # Column 1: Auction date, house, sale, lot
        try:
            work_data['col_1'] = cols[1].get_text("|", strip=True).split('|')
        except:
            pass

        # Auction Date
        try:
            work_data['auction_date'] = cols[1].find(class_=config.DATE_CLASS).get_text(strip=True)
        except:
            pass

        # Auction house, sale, and lot
        house_sale_lot = cols[1].find_all('div', class_=config.FIELD_CLASS)
        if len(house_sale_lot) == 3: # We have all three fields, slot 'em in
            work_data['auction_house'] = house_sale_lot[0].get_text(strip=True).replace('\n', ' ')
            work_data['auction_sale'] = house_sale_lot[1].get_text(strip=True).replace('\n', ' ')
            work_data['auction_lot'] = house_sale_lot[2].get_text(strip=True).replace('\n', ' ')
        else: # We are missing fields
            try:
                work_data['auction_lot'] = cols[1].find(string=re.compile('(L|l)ot')).parent.get_text().replace('\n', ' ')
            except:
                pass

        # Column 2: Price, Est, Diff from est
        try:
            work_data['col_2'] = cols[2].get_text("|", strip=True).split('|')
        except:
            pass

        # Price Realized
        try:
            work_data['price_realized'] = cols[2].find(class_=config.PRICE_CLASS).get_text(strip=True).replace('\n', ' ')
        except:
            pass

        # Bought In
        try:
            cols[2].find(class_=config.BOUGHT_IN_CLASS).get_text(strip=True).replace('\n', ' ')
        except:
            pass
        else:
            work_data['bought_in'] = 1

        # Estimate
        try:
            work_data['estimate'] = cols[2].find(class_=config.FIELD_CLASS).get_text(strip=True).replace('\n', ' ')
        except:
            pass
        
        page_out.append([
            work_data.get('artist_name', ''),
            work_data.get('col_0', ''),
            work_data.get('title', ''),
            work_data.get('date', ''),
            work_data.get('medium', ''),
            work_data.get('dims', ''),
            work_data.get('col_1', ''),
            work_data.get('auction_date', ''),
            work_data.get('auction_house', ''),
            work_data.get('auction_sale', ''),
            work_data.get('auction_lot', ''),
            work_data.get('col_2', ''),
            work_data.get('price_realized', ''),
            work_data.get('estimate', ''),
            work_data.get('bought_in')
        ])

    return page_out


def load_cookies(driver, path=config.COOKIES_PATH):
    '''
    Loads cookies from path if file exists, otherwise creates a new file.
     
    Parameters:
        driver (selenium.webdriver obj): Selenium webdriver object
        path (str): Path to file where cookies are stored in JSON format.
    '''

    logging.info("\nLoading cookies.")

    if not os.path.exists(path):
        # Cookies file does not exist; create new cookies file
        cookies = []
        with open(path, 'w') as f:
            json.dump(cookies, f)
    else:
        with open(path) as f:
            cookies = json.load(f)
    
    for cookie in cookies:
        driver.add_cookie(cookie)

    return  


def accept_cookies(driver):
    '''
    In the event of a prompt to accept cookies, click accept.

    Parameters:
        driver (selenium.webdriver obj): Selenium webdriver object
    '''

    try:
        cookie_accept = driver.find_element(By.ID, config.ACCEPT_COOKIES_ID)
    except NoSuchElementException:
        # No pop-up
        return
    else:
        logging.info("Clicking to accept cookies\n")
        cookie_accept.send_keys(Keys.ENTER)
        time.sleep(3)
        return


def close_signup(driver):
    '''
    In the event of a prompt to sign up, close signup window.

    Parameters:
        driver (selenium.webdriver obj): Selenium webdriver object
    '''

    # Close signup window if present
    try:
        close_signup = driver.find_element(By.XPATH, config.CLOSE_SIGNUP_XPATH) 
    except NoSuchElementException:
        # No pop-up
        return
    else:
        logging.info("Clicking to close signup pop-up.\n")
        close_signup.send_keys(Keys.ENTER)
        time.sleep(3)
        return


def login(driver, email=config.LOGIN_EMAIL, pw=config.LOGIN_PW):
    '''
    In the event that user is not logged in, automate login.

    Parameters:
        driver (selenium.webdriver obj): Selenium webdriver object
        email (str, optional): The user's email (default is config.LOGIN_EMAIL.
        pw (str, optional): The user's password (default is config.LOGIN_PW.
    '''

    # Check for presence of login button
    try:
        login_button = driver.find_element(By.XPATH, config.LOGIN_BUTTON_XPATH)
    except NoSuchElementException:
        # Login button not found; user is (presumably) logged in
        return
    else:
        # Login
        
        # Click Login button
        logging.info("Attempting to log in")
        login_button.send_keys(Keys.ENTER)
        time.sleep(3)

        # Input username and pw and submit
        try:
            user_email = driver.find_element(By.XPATH, config.USER_EMAIL_XPATH)
            user_pw = driver.find_element(By.XPATH, config.USER_PW_XPATH)
        except NoSuchElementException:
            logging.warning("Email or password fields not found in login form.")
            logging.warning("Closing driver.")
            driver.close()
            raise
        else:
            user_email.send_keys(email)
            user_pw.send_keys(pw + Keys.ENTER)
            logging.info("Logged in.\n")
            time.sleep(3)
            return


def search_artist(driver, artist_name, search_url):
    '''
    Not currently implemented. Enters `artist_name` character-by-character
    into search bar and clicks once the top search result matches `artist_name`.

    Parameters:
        artist_name (str): The name of artist to search
        driver (selenium.webdriver obj): Selenium webdriver object

    Returns:
        Bool: True if successfully found, False if there was an error
    '''
    
    # Load search page
    driver.get(search_url)
    time.sleep(2)

    logging.info("\nSearching for {}".format(artist_name))

    # Get HTML elements
    try:
        search_bar = driver.find_element(By.XPATH, config.SEARCH_BAR_XPATH)
        search_submit = driver.find_element(By.XPATH, config.SEARCH_SUBMIT_XPATH)
    except NoSuchElementException:
        # Search bar or search submit button not found
        logging.warning("Search bar or submit button not found.")
        driver.close()
        raise

    # Input artist name incrementally until first search result matches
    for char in artist_name.lower():
        search_bar.send_keys(char)
        time.sleep(2)

        try:
            first_result = driver.find_element(By.XPATH, config.FIRST_RESULT_XPATH)
        except NoSuchElementException:
            # No results yet
            continue

        if first_result.text.lower() == artist_name.lower():

            # Artist found, navigate to that page
            search_bar.send_keys(Keys.ARROW_DOWN)
            time.sleep(3)
            search_bar.send_keys(Keys.ENTER)
            time.sleep(3)
            search_submit.send_keys(Keys.ENTER)
            time.sleep(3)

            # Get URL and modify
            current_url = driver.current_url
            modified_url = current_url[:current_url.find('?') + 1] + config.URL_SUFFIX_SEARCH
            driver.get(modified_url)
            time.sleep(3)
            
            return True

    return False


def crawl_artist(driver, artist_name, output_file):
    '''
    Crawls through all pages of a given artist.

    Args:
        driver (obj): Selenium webdriver object
        artist (str): Artist to search for
        output_file (str): output file path

    returns:
        bool: True when complete
    '''

    logging.info("\nCrawing: {}".format(artist_name))
    cur_page = 1
    parser = 'lxml'
    artist_data = []

    # Wait until page load
    time.sleep(5)

    # Get number of pages
    try:
        num_results = driver.find_element(By.XPATH, config.NUM_RESULTS_XPATH).text
    except NoSuchElementException:
        # Default to 100
        max_pages = 100
    else:
        max_pages = ceil(int(num_results[:num_results.find(' ')])/10)

    # Loop until no more pages
    while cur_page <= max_pages:
        
        logging.info("\tPage {}/{} loaded".format(cur_page, max_pages))

        # Get HTML and extract info
        page_source = driver.page_source
        bsObj = BeautifulSoup(page_source, parser)
        page_data = extract_page_data(bsObj, artist_name)
        artist_data.extend(page_data)


        # Get Next link
        try:
            next_button = driver.find_element(By.XPATH, config.NEXT_BUTTON_XPATH)
        except NoSuchElementException:
            # This is the last page
            break

        if next_button.text.startswith('Next'):
            '''
            Issue discovered: For pages with more than 1000 works, the max page
            shows 100 but you can still keep clicking next.
            '''
        
            # Click Next button
            next_button.send_keys(Keys.ENTER)

            # Increment cur_page
            cur_page += 1

            # Wait until next page loads
            time.sleep(3)
        else:
            # This is the last page
            break

    logging.info("\nArtist complete.")

    # Write results to file
    logging.info("Writing results to file.")

    with open(output_file, 'a', newline='') as f:
        write = csv.writer(f, quoting=csv.QUOTE_NONNUMERIC)
        write.writerows(artist_data)


def crawl(output_file, artists, start_url=config.START_URL):
    '''
    Crawl a website to scrape auction information about artists.

    Parameters:
        output_file (str): Path to the output file where the scraped data
            will be stored.
        artists (list): List of artists to search for information.
        start_url (str, optional): The initial URL to start the crawl
            (default is config.START_URL)

    Returns:
        list: A names of artists that were not found during the crawl.
    '''

    # Initialize output variables
    headings = [
        'artist_name', 'col_0', 'title', 'date', 'medium', 'dims', 'col_1',
        'auction_date', 'auction_house', 'auction_sale', 'auction_lot', 'col_2',
        'price_realized', 'estimate', 'bought_in'
    ]
    not_found = []
    
    # Create output file if it doesn't already exist
    if not os.path.exists(output_file):
        with open(output_file, 'w', newline='') as f:
            write = csv.writer(f, quoting=csv.QUOTE_NONNUMERIC)
            write.writerow(headings)

    # Initialize webdriver instance
    driver = webdriver.Safari()
    driver.set_window_size(1000, 2000)
    
    # Load cookies
    load_cookies(driver, config.COOKIES_PATH)

    # Load start page
    driver.get(start_url)
    time.sleep(3)

    # Accept cookies if necessary
    accept_cookies(driver)
    
    # Close signup pop up if necessary
    close_signup(driver)

    # Login if necessary
    login(driver)

    # Scrape loop
    for artist in artists:
        
        # Resolve non-standard characters in artist name
        artist_name = unidecode(artist)

        # Build artist URL
        url = (
            config.URL_PREFIX +
            artist_name.lower().replace(' ', '-') +
            config.URL_SUFFIX
        )

        # Check for validity of URL
        try:
            response = requests.get(url)
        except requests.exceptions.TooManyRedirects:
            not_found.append(artist)
        except requests.exceptions.HTTPError:
            not_found.append(artist)
        else:
            driver.get(url)
            crawl_artist(driver, artist_name, output_file)

    # Write cookies to file
    logging.info("Writing cookies to file.")
    cookies = driver.get_cookies()
    with open(config.COOKIES_PATH, 'w') as f:
        json.dump(cookies, f)

    # Close driver
    logging.info("Closing driver.\n")
    driver.close()

    return not_found


def load_artists(path):
    '''
    Loads the list of artist names from a text file. Each artist name should
    have its own line in the file.

    Parameters:
        path (str): The file path tot he text file containing the list of 
            artist names.

    Returns:
        List: A list of artist names.
    '''
    
    # Open the text file in read mode and read contents
    with open(path, newline='') as f:
        # Split the contents into a list of artist names by splitting on newlines
        artists = f.read().splitlines()
    
    # Return the list of artist names
    return artists


if __name__ == '__main__':

    # Load artist names
    artists = load_artists(config.ARTIST_PATH)
    
    # Crawl
    not_found = crawl(artists=artists[53:55], output_file=config.OUTPUT_FILE)

    # Print nmes of artists not found
    print("The following artists were not found:")
    for artist in not_found:
        print("\t-{}".format(artist))
