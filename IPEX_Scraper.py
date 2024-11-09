from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
import os
import requests
from urllib.parse import urljoin

# URL and path to chromedriver
website = 'https://ipex.eu/IPEXL-WEB/search/document/results'
path = '/usr/local/bin/chromedriver'

# Base directory for downloaded files
base_dir = os.path.join(os.getcwd(), "Wetsvoorstellen")
if not os.path.exists(base_dir):
    os.makedirs(base_dir)

# Initialize the driver
service = Service(path)
driver = webdriver.Chrome(service=service)
driver.get(website)

# Wait until the page is fully loaded
driver.implicitly_wait(10)

# Step 1: Click on language selection button and choose Dutch
language_dropdown_button = WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable((By.ID, "languageMenu"))
)
language_dropdown_button.click()

# Use JavaScript to click the Dutch option
dutch_option = WebDriverWait(driver, 10).until(
    EC.visibility_of_element_located((By.XPATH, "//a[@title='NL - Nederlands']"))
)
driver.execute_script("arguments[0].click();", dutch_option)
time.sleep(2)

# Step 2: Click on the "Type" button and select "Documenten"
type_button = WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable((By.XPATH, "//button[@aria-controls='type']"))
)
driver.execute_script("arguments[0].scrollIntoView();", type_button)
driver.execute_script("arguments[0].click();", type_button)

documents_checkbox = driver.find_element(
    By.XPATH, "//ul[@id='type']//label[.//span[text()='Documenten']]//input[@type='checkbox']"
)
documents_checkbox.click()
time.sleep(2)

# Step 3: Click on the "Evenement" button and select "Ja" for "Met redenen omkleed advies"
event_button = WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable((By.XPATH, "//button[@aria-controls='events']"))
)
driver.execute_script("arguments[0].scrollIntoView();", event_button)
driver.execute_script("arguments[0].click();", event_button)

reasoned_opinion_yes_button = driver.find_element(
    By.XPATH, "//h5[contains(text(), 'Met redenen omklees advies')]/following-sibling::ul[1]//label[contains(text(), 'Ja')]//input[@type='checkbox']"
)
reasoned_opinion_yes_button.click()
time.sleep(2)

# Step 4: Click the "Laad meer" button until all results are loaded
while True:
    try:
        load_more_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Laad meer')]"))
        )
        driver.execute_script("arguments[0].scrollIntoView();", load_more_button)
        time.sleep(1)
        load_more_button.click()
        time.sleep(10)  # Increased delay to avoid rate limiting
    except:
        print("All results loaded.")
        break

# Step 5: Collect links of each result
result_links = []
results = driver.find_elements(By.CSS_SELECTOR, "app-document-output.srch-card a.srch-card-title")
for result in results:
    link = result.get_attribute("href")
    result_links.append(link)

# Function to handle file download with retry on 429 errors
def download_file(url, folder, file_name):
    if not url:  # Skip if URL is empty
        print(f"Skipping empty URL for {file_name}")
        return

    # Construct file path
    file_path = os.path.join(folder, file_name)
    if os.path.exists(file_path):  # If file already exists, add a suffix
        file_path = os.path.join(folder, f"{file_name}_duplicate")

    retries = 3
    for attempt in range(retries):
        try:
            response = requests.get(url, stream=True)
            if response.status_code == 429:
                # Wait before retrying on a 429 error
                time.sleep(10 * (attempt + 1))
                continue
            response.raise_for_status()

            with open(file_path, 'wb') as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
            print(f"Downloaded {file_name} to {folder}")
            break
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == retries - 1:
                print(f"Failed to download {file_name} after {retries} attempts.")

# Iterate through each result to scrape data and download files
data = []
for link in result_links:
    driver.get(link)
    time.sleep(2)

    # Scrape document code and name with error handling
    try:
        doc_code = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h1.section-title.document-detail-title"))
        ).text
    except Exception as e:
        print(f"Failed to locate document code: {e}")
        continue  # Skip to the next result if this one fails

    doc_name = driver.find_element(By.CSS_SELECTOR, "p.ipx-lead").text
    doc_code_cleaned = doc_code.replace("/", "-")  # Replace slashes to avoid path issues

    # Folder path for the document
    doc_folder = os.path.join(base_dir, doc_code_cleaned)
    if not os.path.exists(doc_folder):
        os.makedirs(doc_folder)

    # Scrape counts of reasoned opinions, political dialogues, and important information
    try:
        reasoned_opinions = driver.find_element(By.CSS_SELECTOR, ".btn-opinion .tag-count").text
    except:
        reasoned_opinions = "0"
    try:
        political_dialogues = driver.find_element(By.CSS_SELECTOR, ".btn-dialog .tag-count").text
    except:
        political_dialogues = "0"
    try:
        important_information = driver.find_element(By.CSS_SELECTOR, ".btn-exchange .tag-count").text
    except:
        important_information = "0"

    # Date-related fields
    try:
        adoption_date = driver.find_element(By.XPATH, "//li[strong[text()='Aannamedatum:']]/span").text
    except:
        adoption_date = ""
    try:
        legal_basis = driver.find_element(By.XPATH, "//li[strong[text()='Rechtsgrondslag:']]/span").text
    except:
        legal_basis = ""
    try:
        reference_letter_date = driver.find_element(By.XPATH,
                                                    "//li[strong[contains(text(), 'Verwijsbrief')]]/span").text
    except:
        reference_letter_date = ""
    try:
        subsidiarity_deadline = driver.find_element(By.XPATH,
                                                    "//li[strong[text()='Subsidiariteitstermijn:']]/span").text
    except:
        subsidiarity_deadline = ""

    # Collect links to parliaments with reasoned opinions
    parliament_links = []
    try:
        reasoned_parliament_elements = driver.find_elements(By.CSS_SELECTOR, ".scrutiny-box.ipx-card a .btn-opinion")
        for reasoned_element in reasoned_parliament_elements:
            parent_link = reasoned_element.find_element(By.XPATH, "./ancestor::a").get_attribute("href")
            parliament_links.append(parent_link)
    except Exception as e:
        print(f"Error while collecting parliament links: {e}")

    # Scrape details for each parliament that issued a reasoned opinion
    parliament_data = []
    for parliament_link in parliament_links:
        driver.get(parliament_link)
        time.sleep(2)

        # Scrape parliament name
        try:
            parliament_name = driver.find_element(By.XPATH, "//h1[contains(@class, 'flag')]").text.strip()
        except:
            parliament_name = ""

        # Folder for parliament within the document folder
        parliament_folder = os.path.join(doc_folder, parliament_name)
        if not os.path.exists(parliament_folder):
            os.makedirs(parliament_folder)

        # Scrape reasoned opinion date
        try:
            reasoned_opinion_date = driver.find_element(By.CSS_SELECTOR,
                                                        ".title-opinion + h4.lisbon-block-date").text.strip()
        except:
            reasoned_opinion_date = ""

        # Download files from "Gekoppelde bestanden" section
        try:
            button = driver.find_element(By.XPATH, "//button[normalize-space(text())='Gekoppelde bestanden']")
            if button.get_attribute("aria-expanded") == "false":
                button.click()
                time.sleep(1)

            files_section = driver.find_element(By.XPATH,
                                                "//div[@aria-hidden='false']//div[contains(@class, 'ipx-files-list')]")
            files = files_section.find_elements(By.XPATH, ".//a[@download]")
            for file in files:
                file_url = urljoin(website, file.get_attribute("href"))
                file_name = file.get_attribute("title") or file.text.strip()
                if file_name:
                    download_file(file_url, parliament_folder, file_name)
                else:
                    print("Skipping file with empty name.")
        except Exception as e:
            print(f"Error downloading 'Gekoppelde bestanden' for {parliament_name} - {doc_code}: {e}")

        # Download files from "Met redenen omkleed advies" section
        try:
            opinion_section = driver.find_element(By.XPATH,
                                                  "//h3[contains(text(), 'Met redenen omkleed advies')]/following-sibling::ul")
            opinion_files = opinion_section.find_elements(By.TAG_NAME, "a")
            for opinion_file in opinion_files:
                opinion_url = urljoin(website, opinion_file.get_attribute("href"))
                opinion_name = opinion_file.text.strip()
                if opinion_name:
                    download_file(opinion_url, parliament_folder, opinion_name)
                else:
                    print("Skipping file with empty name in 'Met redenen omkleed advies' section.")
        except Exception as e:
            print(f"Error downloading 'Met redenen omkleed advies' for {parliament_name} - {doc_code}: {e}")

        # Append parliament data
        parliament_data.append({
            "Parliament Name": parliament_name,
            "Reasoned Opinion Date": reasoned_opinion_date
        })

    # Add collected data for the current document
    data.append({
        "Document Code": doc_code,
        "Document Name": doc_name,
        "Reasoned Opinions": reasoned_opinions,
        "Political Dialogues": political_dialogues,
        "Important Information to Exchange": important_information,
        "Adoption Date": adoption_date,
        "Legal Basis": legal_basis,
        "Reference Letter Date": reference_letter_date,
        "Subsidiarity Deadline": subsidiarity_deadline,
        "Parliament Data": parliament_data
    })

# Convert data to DataFrame
df = pd.DataFrame(data)

# Export DataFrame to CSV
df.to_csv("ipex_results.csv", index=False)

print("Data successfully exported to ipex_results.csv")

# Close the driver
driver.quit()