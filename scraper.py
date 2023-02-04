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

def extract_page_data(bsObj, artist_name):
    '''
    Extract relevant data from page of auction results.

    Args:
        bsObj (Beautiful Soup obj): page HTML
        artist (str): Artist name to add to each row of data

    Returns:
        page_out (arr): List of work details extracted from `bsObj`. Each list
            item is a list of item details.
    '''

    print("\tExtracting page data...")

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
    print("\tPage data extracted.")

    return page_out


def load_cookies(driver, path=config.COOKIES_PATH):
    '''
    Load cookies from `path` if file exists, otherwise create a new file.
    Returns `cookies`
     
    Args:
        driver (obj): Selenium webdriver object
        path (str): Path to file where cookies are stored
    '''

    print("\nLoading cookies.")
    try:
        with open(path) as f:
            cookies = json.load(f)
    except FileNotFoundError:
        # Cookies file does not exist
        # create new cookies file
        cookies = []
        with open(path, 'w') as f:
            json.dump(cookies, f)
    finally:
        for cookie in cookies:
            driver.add_cookie(cookie)

    return  


def accept_cookies(driver):

    try:
        cookie_accept = driver.find_element(By.ID, config.ACCEPT_COOKIES_ID)
    except NoSuchElementException:
        # No pop-up
        return
    else:
        print("Clicking to accept cookies\n")
        cookie_accept.send_keys(Keys.ENTER)
        time.sleep(3)
        return


def close_signup(driver):
    # Close signup window if present
    try:
        close_signup = driver.find_element(By.XPATH, config.CLOSE_SIGNUP_XPATH) 
    except NoSuchElementException:
        # No pop-up
        return
    else:
        print("Clicking to close signup pop-up.\n")
        close_signup.send_keys(Keys.ENTER)
        time.sleep(3)
        return


def login(driver, email=config.LOGIN_EMAIL, pw=config.LOGIN_PW):
    
    # Check for Login button
    try:
        login_button = driver.find_element(By.XPATH, config.LOGIN_BUTTON_XPATH)
    except NoSuchElementException:
        # Login button not found; user is logged in
        # (Not necessarily true but presuming for now)
        return
    else:
        # Login

        print("Attempting to log in")
        
        # Click Login button
        login_button.send_keys(Keys.ENTER)
        time.sleep(3)

        # Input username and pw and submit
        try:
            user_email = driver.find_element(By.XPATH, config.USER_EMAIL_XPATH)
            user_pw = driver.find_element(By.XPATH, config.USER_PW_XPATH)
        except NoSuchElementException:
            print("Email or password fields not found in login form.")
            print("Closing driver.")
            driver.close()
            raise
        else:
            user_email.send_keys(email)
            user_pw.send_keys(pw + Keys.ENTER)
            print("Logged in.\n")
            time.sleep(3)
            return


def search_artist(driver, artist_name, search_url):
    '''
    Enters `artist_name` incrementally into search and selects once found.

    Args:
        artist_name (str): Name of artist to search
        driver (obj): Selenium webdriver object

    Returns:
        Bool: True if successfully found, False if there was an error
    '''
    # Load search page
    driver.get(search_url)
    time.sleep(2)

    print("\nSearching for {}".format(artist_name))

    # Get elements
    try:
        search_bar = driver.find_element(By.XPATH, config.SEARCH_BAR_XPATH)
        search_submit = driver.find_element(By.XPATH, config.SEARCH_SUBMIT_XPATH)
    except NoSuchElementException:
        # Search bar or search submit button not found
        print("Search bar or submit button not found.")
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
            # Artist found
            print("{} found!".format(artist_name))
            search_bar.send_keys(Keys.ARROW_DOWN)
            time.sleep(3)
            search_bar.send_keys(Keys.ENTER)
            time.sleep(3)
            search_submit.send_keys(Keys.ENTER)
            time.sleep(3)
            # Modify URL to display only paintings and past auctions
            current_url = driver.current_url
            suffix = config.URL_SUFFIX 
            modified_url = current_url[:current_url.find('?') + 1] + suffix
            driver.get(modified_url)
            time.sleep(3)
            return True

    return False


def crawl_artist(driver, wait, artist_name, output_file):
    '''
    Crawls through all pages of a given artist.

    Args:
        driver (obj): Selenium webdriver object
        artist (str): Artist to search for
        output_file (str): output file path

    returns:
        bool: True when complete
    '''

    print("\nCrawing: {}".format(artist_name))
    cur_page = 1
    parser = 'lxml'
    artist_data = []

    # Wait until page load
    print("Waiting for artist page to load")
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
        
        print("\n\nPage {}/{} loaded".format(cur_page, max_pages))

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

    print("\n\nArtist complete.")

    # Write results to file
    print("Writing results to file.")

    with open(output_file, 'a', newline='') as f:
        write = csv.writer(f, quoting=csv.QUOTE_NONNUMERIC)
        write.writerows(artist_data)


def crawl(output_file, artists, start_url=config.START_URL):
    '''
    Main crawling script.

    Args:
        start_url (str, optional): initial url
        output_file (str, optional): output file path
        artists (list, optional): list of artists to search

    '''
    # Initialize webdriver instance
    driver = webdriver.Safari()
    driver.set_window_size(1000, 2000)
    wait = WebDriverWait(driver, 10)

    # Initialize output variables
    headings = [
        'artist_name', 'col_0', 'title', 'date', 'medium', 'dims', 'col_1',
        'auction_date', 'auction_house', 'auction_sale', 'auction_lot', 'col_2',
        'price_realized', 'estimate', 'bought_in'
    ]
    not_found = []
    
    # Initialize output file if it doesn't already exist
    if not os.path.exists(output_file):
        with open(output_file, 'w', newline='') as f:
            write = csv.writer(f, quoting=csv.QUOTE_NONNUMERIC)
            write.writerow(headings)

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
        
        artist_name = unidecode(artist)

        # Fetch URL
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
        else:
            if response.status_code == 404:
                not_found.append(artist)
            else:
                driver.get(url)
                crawl_artist(driver, wait, artist_name, output_file)
        

    # Write cookies to file
    print("Writing cookies to file.")
    cookies = driver.get_cookies()
    with open(config.COOKIES_PATH, 'w') as f:
        json.dump(cookies, f)

    print("\nThe following artists were not found:")
    for artist in not_found:
        print("-{}".format(artist))
    
    # Close driver
    print("Closing driver.\n")
    driver.close()


def load_artists(path):
    '''
    Read in artist file.

    Args:
        path (str): file path

    Returns:
        arr: List of artist names
    '''
    with open(path, newline='') as f:
        artists = f.read().splitlines()
    return artists


if __name__ == '__main__':

    artists = load_artists(config.ARTIST_PATH)

    crawl(artists=artists[53:55], output_file=config.OUTPUT_FILE)
