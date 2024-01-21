from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
from flask import Flask, request, jsonify
from duckduckgo_search import DDGS
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import time
import re

app = Flask(__name__)
CORS(app, origins='*')

def search_engine(keyword, location,  num_results):
    query = f"{keyword} {location}"
    time.sleep(2)
    print(f"Performing DuckDuckGo search for: {query}")
    with DDGS() as ddgs:
        results = [r for r in ddgs.text(f"{query}", max_results=num_results)]
        print(results)
        return results

def search_map(keyword, location,  num_results):
    query = f"{keyword} {location}"
    time.sleep(2)
    print(f"Performing DuckDuckGo maps for: {query}")
    with DDGS() as ddgs:
        results = []
        for r in ddgs.maps(query, place=location, max_results=num_results):
            # Extract relevant information
            result_info = {                
                'url': r.get('url', ''),
                'phone': r.get('phone', ''),
            }
            results.append(result_info)

        return results

def find_contact_page_url(soup, base_url):
    # You can customize this function to look for different patterns or keywords
    # that may indicate a "Contact Us" page link on the home page.
    patterns = [re.compile(r'contact[-_]us', re.IGNORECASE), re.compile(r'contact', re.IGNORECASE)]
    
    for pattern in patterns:
        contact_links = soup.find_all('a', href=pattern)
        for link in contact_links:
            href_value = link.get('href', '')
            if is_valid_url(href_value):
                return href_value
    
    return None

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def scrape_contact_page(contact_page_url):
    try:
        print(f"Scraping contact page data from {contact_page_url}")

        response = requests.get(contact_page_url)
        if response.status_code == 200:
            print(f"Successfully fetched data from {contact_page_url}")

            contact_soup = BeautifulSoup(response.text, 'html.parser')

            # Scrape Email from the contact page
            email = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', contact_soup.text).group() if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', contact_soup.text) else ''

            # Scrape Phone Numbers from the contact page
            phone_numbers = re.findall(r'\b\d{10,}\b', contact_soup.text)

            return email, phone_numbers
        else:
            print(f"Failed to fetch data from {contact_page_url}. Status code: {response.status_code}")
            return None, None
    except Exception as e:
        print(f"Error while scraping {contact_page_url}: {e}")
        return None, None
    
# ... (previous code)

def scrape_url(url):
    try:
        print(f"Scraping data from {url}")

        response = requests.get(url)
        if response.status_code == 200:
            print(f"Successfully fetched data from {url}")

            soup = BeautifulSoup(response.text, 'html.parser')

            # Scrape Email from the home page
            email = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', soup.text).group() if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', soup.text) else ''

            # Scrape Phone Numbers from the home page
            raw_phone_numbers = re.findall(r'\b(?:\+?(\d{1,3}))?[-. (]*\b(\d{3})[-. )]*(\d{3})[-. ]*(\d{4})\b', soup.text)
            phone_numbers = [''.join(filter(str.isdigit, ''.join(num))) for num in raw_phone_numbers]

            # If email is not found, try finding contact information on the "Contact Us" page
            if not email:
                contact_page_url = find_contact_page_url(soup, url)
                if contact_page_url:
                    print(f"Contact page found: {contact_page_url}")
                    email, contact_page_phone_numbers = scrape_contact_page(contact_page_url)
                    phone_numbers.extend(contact_page_phone_numbers)

            # Scrape Social Media URLs
            social_media_urls = {
                'facebook': get_valid_url(soup.find('a', href=re.compile(r'facebook\.com'))),
                'instagram': get_valid_url(soup.find('a', href=re.compile(r'instagram\.com'))),
                'linkedin': get_valid_url(soup.find('a', href=re.compile(r'linkedin\.com'))),
                'twitter': get_valid_url(soup.find('a', href=re.compile(r'twitter\.com'))),
                'pinterest': get_valid_url(soup.find('a', href=re.compile(r'pinterest\.com'))),
            }

            scraped_data = {
                'url': url,
                'email': email,
                'phone_numbers': phone_numbers,
                'facebook': social_media_urls['facebook'],
                'instagram': social_media_urls['instagram'],
                'twitter': social_media_urls['twitter'],
                'linkedin': social_media_urls['linkedin'],
                'pinterest': social_media_urls['pinterest'],
            }

            print(f"Scraped data from {url}: {scraped_data}")
            return scraped_data
        else:
            print(f"Failed to fetch data from {url}. Status code: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error while scraping {url}: {e}")
        return None

def get_valid_url(tag):
    href_value = tag.get('href') if tag else ''
    try:
        # Attempt to parse the href value as a URL
        parsed_url = urlparse(href_value)
        if parsed_url.scheme and parsed_url.netloc:
            return href_value
        else:
            print(f"Invalid URL detected in href: {href_value}")
            return ''
    except ValueError:
        print(f"Invalid URL detected in href: {href_value}")
        return ''


@app.route('/scrape', methods=['POST'])
def scrape():
    try:
        data = request.get_json()
        keyword = data.get('keyword', '')
        location = data.get('location', '')
        
        # Search using both text and maps methods
        search_results = search_engine(keyword, location, num_results=5)
        search_maps = search_map(keyword, location, num_results=5)

        # Combine the results from both methods
        combined_results = search_results + search_maps
        print(combined_results)

        # Use ThreadPoolExecutor for concurrent scraping
        with ThreadPoolExecutor(max_workers=10) as executor:
            scraped_data = list(filter(None, executor.map(scrape_url, [result.get('url', '') if 'url' in result else result.get('href', '') for result in combined_results])))
        
        return jsonify({"data":scraped_data})
    except Exception as e:
        print(f"Error in /scrape endpoint: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run()
