import streamlit as st
from datetime import datetime, date
import pyperclip
import math
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time
import pandas as pd
import easygui
import os
import requests
import json
from selenium.webdriver.common.action_chains import ActionChains
from lxml import html
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.keys import Keys
from PIL import Image
from datetime import datetime
import base64
from selenium.webdriver.support import expected_conditions as EC

# --- Set page config ---
st.set_page_config(page_title="EPR Dashboard Scraper", layout="centered")

def convert_cat(text):
    roman = ['I', 'II', 'III', 'IV', 'V']
    text = re.sub(r'\b([1-5])\b', lambda m: roman[int(m.group(1))-1], text)
    text = text.replace('-', ' ').replace('CAT', 'Cat').replace('cat', 'Cat').strip()
    return text

def custom_wait_clickable_and_click(elem, attempts=20):
    count = 0
    a='no success'
    while count < attempts:
        try:
            if(a!='success'):
                elem.click()
                a='success'
            elif(a=='success'):
                break
        except:
            time.sleep(1)
            count = count + 1

def scrape():
    try:
        cookies_data = driver.execute_cdp_cmd("Network.getAllCookies", {})
        login_token = None
        for cookie in cookies_data["cookies"]:
            if cookie["name"] == "login-token":
                login_token = cookie["value"]
                break
    except Exception as e:
        print("❌ Failed to retrieve cookies:", e)
        return
    # -------------------------------- HOME PART-------------------------------------------
    try:
        st.info("📅 Fetching Target Data...")
        driver.get('https://eprplastic.cpcb.gov.in/#/epr/pibo-dashboard-view')
        time.sleep(5)
    except Exception as e:
        st.error(f"Error: {e}")
        return
    
    ROMANS = ['', 'I', 'II', 'III', 'IV']
    
    def to_roman(cat):
        if cat.startswith("CAT-") and cat[4:].isdigit():
            n = int(cat[4:])
            return f"CAT {ROMANS[n]}" if n < len(ROMANS) else cat
        return cat
    
    def scrape_table(financial_year):
        try:
            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, table_head_path)))
            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, table_path)))
    
            headers = [h.text.strip() for h in driver.find_elements(By.XPATH, table_head_path + '/tr/th')]
            rows = driver.find_elements(By.XPATH, table_path + '//tbody/tr')
            data = [
                [to_roman(td.text.strip()) if i == 0 else td.text.strip()
                 for i, td in enumerate(row.find_elements(By.TAG_NAME, 'td'))]
                for row in rows
            ]
    
            df = pd.DataFrame(data, columns=headers)
            df['Financial Year'] = financial_year
            return df
        except Exception as e:
            st.error(f"Error scraping table for year {financial_year}: {e}")
        return pd.DataFrame()
    
    # Table paths
    table_path = '//*[@id="simple-table-with-pagination"]'
    table_head_path = '//*[@id="simple_table_header"]'
    
    Target_df = pd.DataFrame()
    
    # Loop using the working logic
    x = 1
    while True:
        try:
            # Click dropdown (updated to working XPath)
            dropdown_xpath = '//span[@title="Clear all"]/following::span[1]'
            WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, dropdown_xpath))).click()
            time.sleep(1)
    
            # Get all available options
            section_links = WebDriverWait(driver, 20).until(
                EC.presence_of_all_elements_located((By.XPATH, '//div[@role="option"]'))
            )
    
            if x > len(section_links):
                break
    
            financial_year = section_links[x-1].text.strip()
            section_links[x-1].click()
            # print(f"📅 Scraping data for Financial Year: {financial_year}")
            time.sleep(2)
    
            year_df = scrape_table(financial_year)
            Target_df = pd.concat([Target_df, year_df], ignore_index=True)
            # st.success("✅ Successfully scraped data")
    
            x += 1
    
        except Exception as e:
            st.error(f"❌ Error processing financial year {x}: {e}")
            
    st.success("✅ Successfully Fetched the Target Data!")

#----------------- Producer B&C Part--------------------------------------------
    consumption_regn_df = pd.DataFrame()

    try:
        st.info("📅 Fetching Consumption Data...")
        driver.get('https://eprplastic.cpcb.gov.in/#/epr/producer-list')
        time.sleep(5)

        driver.find_element(By.XPATH, '//*[@id="ScrollableSimpleTableBody"]/tr/td[8]/span/span[1]').click()
        time.sleep(2)

        driver.find_element(By.XPATH, '//*[@id="product-comments-tab"]/span').click()
        time.sleep(2)

        table_xpath = '/html/body/app-root/app-epr/app-pibo-new-view-form/div[1]/section/div/div[3]/div/div[2]/div[1]/div[2]/table'
        time.sleep(3)

        table_element = driver.find_element(By.XPATH, table_xpath)
        table_html = table_element.get_attribute('outerHTML')

        soup = BeautifulSoup(table_html, 'html.parser')
        table = soup.find('table')

        fixed_headers = [
            "Sl. No.", "State Name", "Year", "Category of Plastic", "Material type",
            "Pre Consumer Waste Plastic Quantity (TPA)", "Pre Consumer Waste Recycled Plastic %",
            "Pre Consumer Waste Recycle Consumption", "Post Consumer Waste Plastic Quantity (TPA)",
            "Post Consumer Waste Recycled Plastic %", "Post Consumer Waste Recycle Consumption",
            "Export Quantity Plastic Quantity (TPA)", "Export Quantity Recycled Plastic %",
            "Export Quantity Recycle Consumption", "Total Consumption"
        ]

        data = []
        tbody = table.find('tbody') if table else None
        if tbody:
            rows = tbody.find_all('tr')
            sl_no, state, year = "", "", ""
            for row in rows:
                cols = [td.get_text(strip=True) for td in row.find_all('td')]
                length = len(cols)

                if length == 2:
                    sl_no, state = cols[0] or sl_no, cols[1] or state

                elif length == 1:
                    year = cols[0] or year

                elif length == 7:
                    try:
                        cat_text = cols[0]
                        category = cat_text.split("(")[1].replace(")", "").strip() if "(" in cat_text else ""
                        material = cat_text.split("(")[0].strip() if "(" in cat_text else cat_text.strip()

                        pre_qty, pre_recycled = cols[1], cols[2]
                        pre_recycle_consumption = float(pre_qty) * (float(pre_recycled) / 100) if pre_qty and pre_recycled else 0

                        post_qty, post_recycled = cols[3], cols[4]
                        post_recycle_consumption = float(post_qty) * (float(post_recycled) / 100) if post_qty and post_recycled else 0

                        export_qty, export_recycled = cols[5], cols[6]
                        export_recycle_consumption = float(export_qty) * (float(export_recycled) / 100) if export_qty and export_recycled else 0

                        total_consumption = float(pre_qty) + float(post_qty) + float(export_qty)

                        data.append([
                            sl_no, state, year, category, material,
                            pre_qty, pre_recycled, pre_recycle_consumption,
                            post_qty, post_recycled, post_recycle_consumption,
                            export_qty, export_recycled, export_recycle_consumption,
                            total_consumption
                        ])
                    except:
                        continue

                elif length == 5:
                    try:
                        cat_text = cols[0]
                        category = cat_text.split("(")[1].replace(")", "").strip() if "(" in cat_text else ""
                        material = cat_text.split("(")[0].strip() if "(" in cat_text else cat_text.strip()

                        pre_qty, post_qty, export_qty, export_recycled = cols[1], cols[2], cols[3], cols[4]
                        export_recycle_consumption = float(export_qty) * (float(export_recycled) / 100) if export_qty and export_recycled else 0
                        total_consumption = float(pre_qty) + float(post_qty) + float(export_qty)

                        data.append([
                            sl_no, state, year, category, material,
                            pre_qty, None, None,
                            post_qty, None, None,
                            export_qty, export_recycled, export_recycle_consumption,
                            total_consumption
                        ])
                    except:
                        continue

        consumption_regn_df = pd.DataFrame(data, columns=fixed_headers)

        if 'Category of Plastic' in consumption_regn_df.columns:
            consumption_regn_df['Category of Plastic'] = (
                consumption_regn_df['Category of Plastic']
                .astype(str)
                .str.replace(r'[\\/\-_,]', '', regex=True)
                .str.strip()
            )
        consumption_regn_df['Type_of_entity'] = st.session_state.get('entity_type', '')
        consumption_regn_df['entity_name'] = st.session_state.get('entity_name', '')
        consumption_regn_df['email_id'] = st.session_state.get('email_id', '')
        st.success("✅ Consumption Registration Data scraped successfully")

    except Exception as e:
        st.error(f"❌ Failed to fetch Consumption Registration Data: {e}")

#-------------------------Wallet Nested Part-----------------------------------------------
    try:
        st.info("📅 Fetching Credit Wallet Data")
        driver.get('https://eprplastic.cpcb.gov.in/#/epr/pibo-wallet')
        time.sleep(3)
        driver.refresh()

        # Extract session state variables
        entity_type = st.session_state.get('entity_type', '')
        entity_name = st.session_state.get('entity_name', '')
        email_id = st.session_state.get('email_id', '')

        # Initialize lists
        a2 = b = c = c2 = c3 = d = e1 = f = g = h = i2 = j = k = l = m = n = o = p = q = []

        a2,b,c,c2,c3,d,e1,f,g,h,i2,j,k,l,m,n,o,p,q = ([] for _ in range(19))

        x = 1
        while True:
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//table[@id='simple-table-with-pagination']/tbody/tr[1]/td[8]/span/span/em")
                    )
                )
                xpath = f"//table[@id='simple-table-with-pagination']/tbody/tr[{x}]/td[8]/span/span/em"
                target_element = driver.find_element(By.XPATH, xpath)
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_element)

                sno = driver.find_element(By.XPATH, f'//table[@id="simple-table-with-pagination"]/tbody/tr[{x}]/td[1]').text
                date = driver.find_element(By.XPATH, f'//table[@id="simple-table-with-pagination"]/tbody/tr[{x}]/td[2]/span').text
                credit = driver.find_element(By.XPATH, f'//table[@id="simple-table-with-pagination"]/tbody/tr[{x}]/td[5]/span').text

                # Try clicking eye icon
                for _ in range(5):
                    try:
                        driver.find_element(By.XPATH, xpath).click()
                        break
                    except WebDriverException:
                        time.sleep(1)

                time.sleep(3)
                tree = html.fromstring(driver.page_source)
                job = tree.xpath('//h5[text()="Transfered Certificates"]/parent::div/parent::div//table[@id="simple-table-with-pagination"]/tbody/tr//td/span[@title]')

                z = [i.xpath('./@title')[0].strip() for i in job if i.xpath('./@title')]

                i = 0
                while i + 12 < len(z):
                    a2.append(sno)
                    b.append(date)
                    c.append(credit)
                    c2.append(entity_type)
                    c3.append(entity_name)
                    d.append(z[i])
                    e1.append(z[i+1])
                    f.append(z[i+2])
                    g.append(z[i+3].replace("-", " "))
                    h.append(z[i+4])
                    i2.append(z[i+5])
                    j.append(z[i+6])
                    k.append(z[i+7])
                    l.append(z[i+8])
                    m.append(z[i+9])
                    n.append(z[i+10])
                    o.append(z[i+11])
                    p.append(z[i+12])
                    q.append(email_id)
                    i += 13

                # Try closing the modal
                for _ in range(5):
                    try:
                        driver.find_element(By.XPATH, '//button[@id="closeSubmitModal"]/span').click()
                        break
                    except WebDriverException:
                        time.sleep(1)

                x += 1
            except Exception:
                break

        # Create DataFrame
        df_wallet_credit = pd.DataFrame({
            'SL_No': a2,
            'Date': b,
            'Credited_From': c,
            'Certificate_ID': d,
            'Value': e1,
            'Certificate_Owner': f,
            'Category': g,
            'Processing_Type': h,
            'Transaction_ID': i2,
            'Available_Potential_Prior_Generation': j,
            'Available_Potential_After_Generation': k,
            'Used_Potential_Prior_Generation': l,
            'Used_Potential_After_Generation': m,
            'Cumulative_Potential': n,
            'Generated_At': o,
            'Validity': p,
            'Type_of_entity': c2,
            'entity_name': c3,
            'email_id': q
        })

        st.success("✅ Credit Wallet Data fetched successfully")

    except Exception as e:
        df_wallet_credit = pd.DataFrame(columns=[
            'SL_No','Date','Credited_From','Certificate_ID','Value',
            'Certificate_Owner','Category','Processing_Type','Transaction_ID',
            'Available_Potential_Prior_Generation','Available_Potential_After_Generation',
            'Used_Potential_Prior_Generation','Used_Potential_After_Generation',
            'Cumulative_Potential','Generated_At','Validity','Type_of_entity','entity_name','email_id'
        ])
        st.error(f"⚠️ Error fetching Credit Wallet Data: {e}")


    try:
        st.info("📅 Fetching Debit Wallet Data")
        driver.get('https://eprplastic.cpcb.gov.in/#/epr/pibo-wallet')
        time.sleep(3)
        driver.refresh()

        # Click on Debit Transactions tab
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//a[text()="Debit Transactions"]'))).click()
        time.sleep(3)

        # Get session info
        entity_type = st.session_state.get('entity_type', '')
        entity_name = st.session_state.get('entity_name', '')
        email_id = st.session_state.get('email_id', '')

        # Initialize lists
        a2,b,c,c2,c3,d,e1,f,g,h,i2,j,k,l,m,n,o,p,q = ([] for _ in range(19))

        x = 1
        while True:
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//table[@id='simple-table-with-pagination']/tbody/tr[1]/td[8]/span/span/em")
                    )
                )
                xpath = f"//table[@id='simple-table-with-pagination']/tbody/tr[{x}]/td[8]/span/span/em"
                target_element = driver.find_element(By.XPATH, xpath)
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_element)

                sno = driver.find_element(By.XPATH, f'//table[@id="simple-table-with-pagination"]/tbody/tr[{x}]/td[1]').text
                date = driver.find_element(By.XPATH, f'//table[@id="simple-table-with-pagination"]/tbody/tr[{x}]/td[2]/span').text
                debit_to = driver.find_element(By.XPATH, f'//table[@id="simple-table-with-pagination"]/tbody/tr[{x}]/td[5]/span').text

                for _ in range(5):
                    try:
                        driver.find_element(By.XPATH, xpath).click()
                        break
                    except WebDriverException:
                        time.sleep(1)

                time.sleep(3)
                tree = html.fromstring(driver.page_source)
                job = tree.xpath('//h5[text()="Transfered Certificates"]/parent::div/parent::div//table[@id="simple-table-with-pagination"]/tbody/tr//td/span[@title]')
                z = [ii.xpath('./@title')[0].strip() for ii in job if ii.xpath('./@title')]

                i = 0
                while i + 12 < len(z):  # Ensure at least 13 elements
                    a2.append(sno)
                    b.append(date)
                    c.append(debit_to)
                    c2.append(entity_type)
                    c3.append(entity_name)
                    d.append(z[i])
                    e1.append(z[i+1])
                    f.append(z[i+2])
                    g.append(z[i+3].replace("-", " "))
                    h.append(z[i+4])
                    i2.append(z[i+5])
                    j.append(z[i+6])
                    k.append(z[i+7])
                    l.append(z[i+8])
                    m.append(z[i+9])
                    n.append(z[i+10])
                    o.append(z[i+11])
                    p.append(z[i+12])
                    q.append(email_id)
                    i += 13

                for _ in range(5):
                    try:
                        driver.find_element(By.XPATH, '//button[@id="closeSubmitModal"]/span').click()
                        break
                    except WebDriverException:
                        time.sleep(1)

                x += 1
            except Exception:
                break

        # Create DataFrame after loop
        df_wallet_debit = pd.DataFrame({
            'SL_No': a2,
            'Date': b,
            'Transfer To (PIBO)': c,
            'Certificate_ID': d,
            'Value': e1,
            'Certificate_Owner': f,
            'Category': g,
            'Processing_Type': h,
            'Transaction_ID': i2,
            'Available_Potential_Prior_Generation': j,
            'Available_Potential_After_Generation': k,
            'Used_Potential_Prior_Generation': l,
            'Used_Potential_After_Generation': m,
            'Cumulative_Potential': n,
            'Generated_At': o,
            'Validity': p,
            'Type_of_entity': c2,
            'entity_name': c3,
            'email_id': q
        })

        st.success("✅ Debit Wallet Data fetched successfully")

    except Exception as e:
        print(f"❌ Failed Debit wallet data: {e}")
        df_wallet_debit = pd.DataFrame(columns=[
            'SL_No','Date','Transfer To (PIBO)','Certificate_ID','Value',
            'Certificate_Owner','Category','Processing_Type','Transaction_ID',
            'Available_Potential_Prior_Generation','Available_Potential_After_Generation',
            'Used_Potential_Prior_Generation','Used_Potential_After_Generation',
            'Cumulative_Potential','Generated_At','Validity','Type_of_entity','entity_name','email_id'
        ])
        st.error("❌ Failed to fetch Debit Wallet Data")

#--------------------------DIfferent Transactions Wallet Part-----------------------------------------

    try:
        st.info("📥 Fetching Different Wallet Transactions")
        driver.get('https://eprplastic.cpcb.gov.in/#/epr/pibo-wallet')
        time.sleep(3)
        driver.refresh()

        # Get session info
        entity_type = st.session_state.get('entity_type', '')
        entity_name = st.session_state.get('entity_name', '')
        email_id = st.session_state.get('email_id', '')

        scroll_container_xpath = '/html/body/app-root/app-epr/app-pibo-wallet/div[1]/div'
        scroll_container = driver.find_element(By.XPATH, scroll_container_xpath)
        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll_container)
        time.sleep(3)

        tab_paths = {
            "Credit Transactions": '/html/body/app-root/app-epr/app-pibo-wallet/div[1]/div/section[2]/div/div[3]/div/div[1]/ul/li[1]/a',
            "Debit Transactions": '/html/body/app-root/app-epr/app-pibo-wallet/div[1]/div/section[2]/div/div[3]/div/div[1]/ul/li[2]/a',
            "Certificate Generations": '/html/body/app-root/app-epr/app-pibo-wallet/div[1]/div/section[2]/div/div[3]/div/div[1]/ul/li[3]/a',
            "Filing Transactions": '/html/body/app-root/app-epr/app-pibo-wallet/div[1]/div/section[2]/div/div[3]/div/div[1]/ul/li[4]/a',
        }

        table_xpath = '//*[@id="simple-table-with-pagination"]'
        header_xpath = '//*[@id="simple_table_header"]/tr/th'
        tables_dict = {}

        def extract_table_data(table_html, driver, header_xpath):
            headers = []
            try:
                header_elements = driver.find_elements(By.XPATH, header_xpath)
                headers = [h.text.strip() for h in header_elements if h.text.strip()]
            except Exception as e:
                st.warning(f"⚠️ Header extraction error: {e}")

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(table_html, 'html.parser')
            table = soup.find('table')
            data = []

            tbody = table.find('tbody')
            rows = tbody.find_all('tr') if tbody else table.find_all('tr')
            for row in rows:
                if row.get('id') == 'simple_table_header':
                    continue
                cols = row.find_all(['td', 'th'])
                row_data = [col.get_text(strip=True) for col in cols]
                if row_data:
                    data.append(row_data)

            if not data:
                return pd.DataFrame(columns=headers)

            if not headers:
                max_cols = max(len(r) for r in data)
                headers = [f"Column_{i+1}" for i in range(max_cols)]

            normalized_data = []
            for r in data:
                if len(r) < len(headers):
                    r += [''] * (len(headers) - len(r))
                elif len(r) > len(headers):
                    r = r[:len(headers)]
                normalized_data.append(r)

            df = pd.DataFrame(normalized_data, columns=headers)
            return df

        def split_certificate_category(df):
            import re
            if 'Certificate Category' in df.columns:
                cat_list, rec_eol_list = [], []
                for val in df['Certificate Category']:
                    match = re.search(r'(Cat)[\s\-_]*([IVXLCDM]+)', val, re.IGNORECASE)
                    if match:
                        cat_part = f"{match.group(1)} {match.group(2).upper()}"
                        rest_part = val[match.end():].strip(" -_/")
                    else:
                        cat_part = val
                        rest_part = ""
                    cat_list.append(cat_part)
                    rec_eol_list.append(rest_part)

                df['Certificate Category'] = cat_list
                cert_cat_index = df.columns.get_loc('Certificate Category')
                df.insert(cert_cat_index + 1, 'Rec_Eol', rec_eol_list)
            return df

        first_tab_name, first_tab_xpath = list(tab_paths.items())[0]
        try:
            st.write(f"🔍 Extracting: **{first_tab_name}**")
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, table_xpath)))
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll_container)
            time.sleep(2)

            table_element = driver.find_element(By.XPATH, table_xpath)
            table_html = table_element.get_attribute('outerHTML')

            df = extract_table_data(table_html, driver, header_xpath)
            df = split_certificate_category(df)
            # 🔁 Add session info columns
            df["Type_of_entity"] = entity_type
            df["entity_name"] = entity_name
            df["email_id"] = email_id
            tables_dict[first_tab_name] = df
            globals()[first_tab_name.replace(" ", "_") + "_df"] = df
            st.success(f"✅ {first_tab_name}: {len(df)} rows")

        except Exception as e:
            st.error(f"❌ Error extracting '{first_tab_name}': {e}")

        for tab_name, tab_xpath in list(tab_paths.items())[1:]:
            try:
                st.write(f"🔄 Switching to tab: **{tab_name}**")
                WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, tab_xpath))).click()
                time.sleep(2)

                scroll_container = driver.find_element(By.XPATH, scroll_container_xpath)
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll_container)
                time.sleep(2)

                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, table_xpath)))
                table_element = driver.find_element(By.XPATH, table_xpath)
                table_html = table_element.get_attribute('outerHTML')

                df = extract_table_data(table_html, driver, header_xpath)
                df = split_certificate_category(df)

                # 🔁 Add session info columns
                df["Type_of_entity"] = entity_type
                df["entity_name"] = entity_name
                df["email_id"] = email_id
                tables_dict[tab_name] = df
                globals()[tab_name.replace(" ", "_") + "_df"] = df
                st.success(f"✅ {tab_name}: {len(df)} rows")

            except Exception as e:
                st.warning(f"⚠️ Could not extract '{tab_name}': {e}")

    except Exception as e:
        st.error(f"❌ Error during Different Wallet Transactions scraping: {e}")

#-------------------------PIBO OPERATIONS:- Material Procurement Data Part-----------------------------------------------

    try:
        st.info("🔄 Fetching Material Procurement Data...")
        driver.get('https://eprplastic.cpcb.gov.in/#/epr/pibo-operations/material')
        time.sleep(5)
        driver.refresh()

        table_xpath = '//*[@id="simple-table-with-pagination"]'
        scroll_xpath = '//*[@id="ScrollableSimpleTableBody"]'
        PAGE_SIZE = 50
        headers, all_rows = [], []

        # Get session info
        entity_type = st.session_state.get('entity_type', '')
        entity_name = st.session_state.get('entity_name', '')
        email_id = st.session_state.get('email_id', '')

        # Set From Date
        try:
            from_date_path = driver.find_element(By.XPATH, '//*[@id="date_from"]')
            from_date_path.send_keys('04/01/2020')
            time.sleep(2)
        except Exception as e:
            st.warning("⚠️ Could not set date: " + str(e))

        # Click Fetch Button
        try:
            fetch_btn_path = driver.find_element(By.XPATH, '/html/body/app-root/app-epr/app-pibo-operations/div[1]/div[2]/div/div/div/div/div[1]/div[3]/button')
            fetch_btn_path.click()
            time.sleep(3)
        except Exception as e:
            st.warning("⚠️ Could not click fetch: " + str(e))

        # Calculate total pages
        try:
            stop_text = driver.find_element(By.XPATH, '//table/tbody/tr/td/div[1]/div/span').text
            total_entries = [int(i) for i in stop_text.split() if i.isdigit()][-1]
            total_pages = math.ceil(total_entries / PAGE_SIZE)
        except Exception as e:
            st.warning(f"⚠️ Could not determine number of pages: {e}")
            total_pages = 1

        count = 0
        while count < total_pages:
            try:
                # Scroll to make sure rows are visible
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, scroll_xpath)))
                scroll = driver.find_element(By.XPATH, scroll_xpath)
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll)
                time.sleep(1)

                # Extract table rows
                table = driver.find_element(By.XPATH, table_xpath)
                if not headers:
                    headers = [th.text.strip() for th in table.find_elements(By.XPATH, ".//thead/tr/th")]
                rows = table.find_elements(By.XPATH, ".//tbody/tr")
                for row in rows:
                    cols = [td.text.strip() for td in row.find_elements(By.TAG_NAME, "td")]
                    all_rows.append(cols)

                count += 1

                if count >= total_pages:
                    break

                # Click next button
                next_buttons = driver.find_elements(By.CLASS_NAME, 'action-button')
                if len(next_buttons) < 2:
                    st.warning("⚠️ 'Next' button not found.")
                    break
                next_button = next_buttons[1]
                custom_wait_clickable_and_click(next_button)
                time.sleep(2)

                # Force refresh (if required)
                try:
                    click = driver.find_element(By.XPATH, '/html/body/app-root/app-epr/app-pibo-operations/div[1]/div[3]/div/div/div/div/div[2]/input')
                    custom_wait_clickable_and_click(click)
                    time.sleep(1)
                except:
                    pass

            except Exception as e:
                st.warning(f"⚠️ Page {count+1} error: {e}")
                break

        # Normalize and convert to DataFrame
        try:
            max_cols = len(headers)
            normalized = [row + [''] * (max_cols - len(row)) for row in all_rows]
            material_procurement_df = pd.DataFrame(normalized, columns=headers)
            material_procurement_df = material_procurement_df.loc[:, material_procurement_df.columns != '']
        except:
            material_procurement_df = pd.DataFrame()

        # Add extra columns
        material_procurement_df["Type_of_entity"] = entity_type
        material_procurement_df["entity_name"] = entity_name
        material_procurement_df["email_id"] = email_id

        st.success("✅ Material Procurement data fetched successfully!")

    except Exception as e:
        st.error(f"❌ Error during procurement scraping: {e}")


#----------------------------PIBO OPERATIONS:- Sales Part------------------------------------------

    try:
        st.info("📅 Fetching SALES Data")
        driver.get('https://eprplastic.cpcb.gov.in/#/epr/pibo-operations/sales')
        time.sleep(5)


        # Get session info
        entity_type = st.session_state.get('entity_type', '')
        entity_name = st.session_state.get('entity_name', '')
        email_id = st.session_state.get('email_id', '')

        start_year = 2020
        current_year = datetime.now().year
        current_month = datetime.now().month

        end_year = current_year if current_month >= 4 else current_year - 1

        df_sales = pd.DataFrame()

        for year in range(start_year, end_year + 1):
            driver.refresh()
            time.sleep(2)
            from_date = f"04/01/{year}"
            to_date = f"03/31/{year+1}"

            try:
                time.sleep(3)
                date_input = driver.find_element(By.XPATH, "//input[@id='date_from']")
                date_input.clear()
                date_input.send_keys(from_date)

                date_end_input = driver.find_element(By.XPATH, "//input[@id='date_to']")
                date_end_input.clear()
                date_end_input.send_keys(to_date)

                click = driver.find_element(By.XPATH, '//button[contains(text(),"Fetch")]')
                custom_wait_clickable_and_click(click)

                df = pd.DataFrame()
                count = 0
                stop = driver.find_element(By.XPATH, '//table/tbody/tr/td/div[1]/div/span').text
                stop = [int(i) for i in stop.split() if i.isdigit()][-1]
                stop = math.ceil(stop / 50)

                while count < stop:
                    time.sleep(1)
                    count += 1
                    job = driver.find_element(By.ID, 'ScrollableSimpleTableBody')
                    soup = BeautifulSoup(job.get_attribute('innerHTML'), 'html.parser')
                    data = soup.find_all("span", class_="ng-star-inserted") or soup.find_all("td", class_="row-item")
                    z = [i.text.replace("\n", "").strip() for i in data]

                    a2, b, c, d, e1, f, g, h, h1, i2, j, k, l,l1, m, n, o, p, q, r, s = [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], []
                    i = 0
                    while i < len(z):
                        a2.append(z[i])
                        b.append(z[i+1])
                        c.append(z[i+2])
                        d.append(z[i+3])
                        e1.append(z[i+4])
                        f.append(z[i+5])
                        g.append(z[i+6])
                        h.append(z[i+7])
                        h1.append("Cat I" if "Containers" in z[i+7] else z[i+7])
                        i2.append(z[i+8])
                        j.append(z[i+9])
                        k.append(z[i+10])
                        l.append(z[i+11])
                        try:
                            recycle_consumption = float(z[i+10]) * (float(z[i+11]) / 100)
                        except (ValueError, TypeError):
                            recycle_consumption = "N/A"
                        l1.append(recycle_consumption)
                        m.append(z[i+12])
                        n.append(z[i+13])
                        o.append(z[i+14])
                        p.append(z[i+15])
                        q.append(entity_type)
                        r.append(entity_name)
                        s.append(email_id)

                        if len(z) > i+18 and z[i+16] == "" and z[i+17] == "" and z[i+18] == "":
                            i += 19
                        elif len(z) > i+17 and z[i+16] == "" and z[i+17] == "":
                            i += 18
                        else:
                            i += 16

                    df1 = pd.DataFrame({
                        'Registration Type': a2,
                        'Entity Type': b,
                        'Name of the Entity': c,
                        'State': d,
                        'Address': e1,
                        'Mobile Number': f,
                        'Plastic Material Type': g,
                        'Category of Plastic': h,
                        'Category': h1,
                        'Financial Year': i2,
                        'Date': j,
                        'Total Plastic Qty (Tons)': k,
                        'Recycled Plastic %': l,
                        'Recycle Consumption': l1,
                        'GST': m,
                        'GST Paid': n,
                        'EPR invoice No': o,
                        'GST E-Invoice No': p,
                        'Type_of_entity': q,
                        'entity_name': r,
                        'email_id': s
                    })

                    if df1.empty:
                        continue
                    if count == 1:
                        df = df1
                    else:
                        new = df.tail(50).reset_index(drop=True)
                        df1 = df1.reset_index(drop=True)

                        if list(new.columns) == list(df1.columns):
                            try:
                                comp = new.compare(df1)
                                if not comp.empty:
                                    df = pd.concat([df, df1], ignore_index=True)
                            except Exception as e:
                                df = pd.concat([df, df1], ignore_index=True)
                        else:
                            df = pd.concat([df, df1], ignore_index=True)

                    next_button = driver.find_elements(By.CLASS_NAME, 'action-button')[1]
                    custom_wait_clickable_and_click(next_button)
                    click = driver.find_element(By.XPATH, '/html/body/app-root/app-epr/app-pibo-operations/div[1]/div[3]/div/div/div/div/div[2]/input')
                    custom_wait_clickable_and_click(click)

                df_sales = pd.concat([df_sales, df], ignore_index=True)
        
            except Exception as e:
                continue
        st.success("✅ SALES Data fetched successfully")

    except Exception as e:
        st.error(f"❌ Failed Sales Data")
        df_sales = pd.DataFrame(columns=[
        'Registration Type', 'Entity Type', 'Name of the Entity', 'State', 'Address',
        'Mobile Number', 'Plastic Material Type', 'Category of Plastic', 'Category', 'Financial Year',
        'Date', 'Total Plastic Qty (Tons)', 'Recycled Plastic %', 'Recycle Consumption', 'GST', 'GST Paid',
        'EPR invoice No', 'GST E-Invoice No','Type_of_entity','entity_name','email_id'
    ])
        pass

#------------------------------------Annual Consumption -----------------------------------------------------------------
    try:
        st.info("📅 Fetching Annual Consumption Data")
        driver.get('https://eprplastic.cpcb.gov.in/#/epr/filing/total-quantity')
        time.sleep(3)

        # Get session info
        entity_type = st.session_state.get('entity_type', '')
        entity_name = st.session_state.get('entity_name', '')
        email_id = st.session_state.get('email_id', '')

        # Define XPaths
        dropdown_path = "//span[@class='ng-arrow-wrapper']"
        year_tab = [
            '//div[@role="option"][1]',
            '//div[@role="option"][2]',
            '//div[@role="option"][3]'
        ]
        table_head_path = '/html/body/app-root/app-epr/app-total-quant-pw/div/div[2]/div/div/div/div/table/thead/tr'
        table_body_path = '/html/body/app-root/app-epr/app-total-quant-pw/div/div[2]/div/div/div/div/table/tbody'

        # Initialize storage
        annual_consumption_df = pd.DataFrame()
        headers_extracted = False

        for year_xpath in year_tab:
            # Step 1: Open dropdown
            dropdown = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, dropdown_path))
            )
            dropdown.click()
            time.sleep(1)

            # Step 2: Click year option
            year_option = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, year_xpath))
            )
            year_option.click()
            time.sleep(2)

            # Step 3: Extract headers once
            if not headers_extracted:
                head_row = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, table_head_path))
                )
                headers = [th.text.strip() for th in head_row.find_elements(By.TAG_NAME, 'th')]
                headers_extracted = True

            # Step 4: Extract table rows
            body_rows = driver.find_elements(By.XPATH, f"{table_body_path}/tr")
            rows_data = []
            for row in body_rows:
                cols = [td.text.strip() for td in row.find_elements(By.TAG_NAME, 'td')]
                if any(cols):  # Only add non-empty rows
                    rows_data.append(cols)

            # Step 5: Append data
            temp_df = pd.DataFrame(rows_data, columns=headers)
            annual_consumption_df = pd.concat([annual_consumption_df, temp_df], ignore_index=True)

            # Add extra columns
            annual_consumption_df["Type_of_entity"] = entity_type
            annual_consumption_df["entity_name"] = entity_name
            annual_consumption_df["email_id"] = email_id


        st.success("✅ Annual Consumption Data extracted successfully")

    except Exception as e:
        st.error(f"❌ Error during Annual Consumption scraping: {e}")

#---------------------------------Annual Statewise PW Generation Part------------------------------------------------

    try:
        st.info("📅 Fetching Consumption AR Data")

        driver.get('https://eprplastic.cpcb.gov.in/#/epr/filing/state-wise-plastic-waste')
        time.sleep(5)

        # Get session info
        entity_type = st.session_state.get('entity_type', '')
        entity_name = st.session_state.get('entity_name', '')
        email_id = st.session_state.get('email_id', '')

        x = 1
        data = []
        while True:
            try:
                WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, '//*[@name="select_fin_year"]/div/span'))).click()
                section_links = WebDriverWait(driver, 2).until(EC.presence_of_all_elements_located((By.XPATH, '//div[@role="option"]')))
                if x > len(section_links):
                    break
                financial_year = section_links[x-1].text.strip()
                section_links[x-1].click()
                time.sleep(2)
                rows = WebDriverWait(driver, 5).until(EC.presence_of_all_elements_located((By.XPATH, '//table[@class="table table-bordered scrollable-table pw-generated"]/tbody/tr[position()>2]')))
                time.sleep(3)
                tree = html.fromstring(driver.page_source)
                rows = tree.xpath('//table[@class="table table-bordered scrollable-table pw-generated"]/tbody/tr[position()>0]')
            
                sl_no = ""
                state = ""
                year = ""
            
                for row in rows:
                    cells = row.xpath('./td')
                    texts = [cell.text for cell in cells]
            
                    if len(texts) == 2:
                        sl_no = texts[0].strip() or sl_no
                        state = texts[1].strip() or sl_no
                    elif len(texts) == 1:
                        year = texts[0].strip() or year
                    elif len(texts) == 7:
                        category = convert_cat(texts[0].split("(")[1].replace(")",""))
                        material = texts[0].split("(")[0].strip()
                        pre_qty = texts[1].strip()
                        pre_recycled = texts[2].strip()
                        try:
                            pre_recycle_consumption = float(texts[1]) * (float(texts[2]) / 100)
                        except (ValueError, TypeError):
                            pre_recycle_consumption = 0
                        post_qty = texts[3].strip()
                        post_recycled = texts[4].strip()
                        try:
                            post_recycle_consumption = float(texts[3]) * (float(texts[4]) / 100)
                        except (ValueError, TypeError):
                            post_recycle_consumption = 0
                        export_qty = texts[5].strip()
                        export_recycled = texts[6].strip()
                        try:
                            export_recycle_consumption = float(texts[5]) * (float(texts[6]) / 100)
                        except (ValueError, TypeError):
                            export_recycle_consumption = 0
                        try:
                            total_consumption = (float(pre_qty) if pre_qty else 0) + (float(post_qty) if post_qty else 0) + (float(export_qty) if export_qty else 0)
                        except:
                            total_consumption = 0
                        data.append([sl_no,state,year,category,material,pre_qty,pre_recycled,pre_recycle_consumption,
                            post_qty,post_recycled,post_recycle_consumption,export_qty,export_recycled,
                            export_recycle_consumption,total_consumption,entity_type,entity_name,email_id
                        ])
                    
                    elif len(texts) == 5:
                        category = convert_cat(texts[0].split("(")[1].replace(")",""))
                        material = texts[0].split("(")[0].strip()
                        pre_qty = texts[1].strip()
                        pre_recycled = None
                        pre_recycle_consumption = None

                        post_qty = texts[2].strip()
                        post_recycled = None
                        post_recycle_consumption = None
                        export_qty = texts[3].strip()
                        export_recycled = texts[4].strip()
                        try:
                            export_recycle_consumption = float(texts[3]) * (float(texts[4]) / 100)
                        except (ValueError, TypeError):
                            export_recycle_consumption = 0
                        total_consumption = (float(pre_qty) if pre_qty else 0) + (float(post_qty) if post_qty else 0) + (float(export_qty) if export_qty else 0)

                        data.append([sl_no,state,year,category,material,pre_qty,pre_recycled,pre_recycle_consumption,
                            post_qty,post_recycled,post_recycle_consumption,export_qty,export_recycled,
                            export_recycle_consumption,total_consumption,entity_type,entity_name,email_id
                        ])
                    elif len(texts) == 4:
                        category = convert_cat(texts[0].split("(")[1].replace(")",""))
                        material = texts[0].split("(")[0].strip()
                        pre_qty = texts[1].strip()
                        pre_recycled = None
                        pre_recycle_consumption = None

                        post_qty = texts[2].strip()
                        post_recycled = None
                        post_recycle_consumption = None
                        export_qty = texts[3].strip()
                        export_recycled = None
                        export_recycle_consumption = None
                        total_consumption = (float(pre_qty) if pre_qty else 0) + (float(post_qty) if post_qty else 0) + (float(export_qty) if export_qty else 0)
                        data.append([sl_no,state,year,category,material,pre_qty,pre_recycled,pre_recycle_consumption,
                                    post_qty,post_recycled,post_recycle_consumption,export_qty,export_recycled,
                                    export_recycle_consumption,total_consumption,entity_type,entity_name,email_id
                        ])
                    else:
                        continue
                x+=1
            except Exception as e:
                x += 1

        headers = [
            "Sl. No.","State Name","Year","Category of Plastic","Material type","Pre Consumer Waste Plastic Quantity (TPA)",
            "Pre Consumer Waste Recycled Plastic %","Pre Consumer Waste Recycle Consumption","Post Consumer Waste Plastic Quantity (TPA)",
            "Post Consumer Waste Recycled Plastic %","Post Consumer Waste Recycle Consumption","Export Quantity Plastic Quantity (TPA)",
            "Export Quantity Recycled Plastic %","Export Quantity Recycle Consumption",'Total Consumption','Type_of_entity','entity_name','email_id'
        ]
                
        cat_df = pd.DataFrame(data, columns=headers)
        st.success("✅ Consumption AR fetched successfully")
    except:
        print(f"❌ Failed Consumption AR Data")
        cat_df = pd.DataFrame(columns=[
            "Sl. No.","State Name","Year","Category of Plastic","Material type","Pre Consumer Waste Plastic Quantity (TPA)",
            "Pre Consumer Waste Recycled Plastic %","Pre Consumer Waste Recycle Consumption","Post Consumer Waste Plastic Quantity (TPA)",
            "Post Consumer Waste Recycled Plastic %","Post Consumer Waste Recycle Consumption","Export Quantity Plastic Quantity (TPA)",
            "Export Quantity Recycled Plastic %","Export Quantity Recycle Consumption",'Total Consumption','Type_of_entity','entity_name','email_id'
        ])
        pass


#---------------------------------Annual Report Part------------------------------------------------------------------
    # Initialize DataFrames early to ensure they're defined
    Annual_report_Data_df = pd.DataFrame()
    Compliance_status_Data_df = pd.DataFrame()
    Next_year_target_Data_df = pd.DataFrame()

    try:
        st.info("📅 Fetching Annual Report Data...")

        driver.get('https://eprplastic.cpcb.gov.in/#/epr/annual-report-filing')
        time.sleep(3)
        driver.refresh()
        time.sleep(3)

        # Get session info
        entity_type = st.session_state.get('entity_type', '')
        entity_name = st.session_state.get('entity_name', '')
        email_id = st.session_state.get('email_id', '')

        # ------------------ 1️⃣ Annual Report Data ------------------
        try:
            thead_path = '/html/body/app-root/app-epr//div/div[1]/div[1]/div[2]/div[2]/div[2]//div[1]//div[1]/table/thead[2]/tr'
            tbody_path = '/html/body/app-root/app-epr/app-annual-report-filing/div/div[1]/div[1]/div[2]/div[2]/div[2]/kl-simple-table-with-pagination/div[1]/div/div[1]/table/tbody'

            headers = [th.text.strip() for th in driver.find_elements(By.XPATH, thead_path + '/th')]
            rows = driver.find_elements(By.XPATH, tbody_path + '/tr')
            data = []
            for row in rows:
                cols = [td.text.strip() for td in row.find_elements(By.TAG_NAME, 'td')]
                data.append(cols)
            Annual_report_Data_df = pd.DataFrame(data, columns=headers)
            st.success("✅ Successfully fetched Annual Report Data")
        except Exception as e:
            st.error(f"❌ Error fetching Annual Report Data: {e}")

        # ------------------ 2️⃣ Compliance Status Data ------------------
        try:
            thead_path = '/html/body/app-root/app-epr/app-annual-report-filing/div/div[1]/div[1]/div[2]/div[3]/div[2]/table/thead/tr/th'
            tbody_path = '/html/body/app-root/app-epr/app-annual-report-filing/div/div[1]/div[1]/div[2]/div[3]/div[2]/table/tbody'

            headers = [th.text.strip() for th in driver.find_elements(By.XPATH, thead_path)]
            rows = driver.find_elements(By.XPATH, tbody_path + '/tr')
            data = []
            for row in rows:
                cols = [td.text.strip() for td in row.find_elements(By.TAG_NAME, 'td')]
                data.append(cols)
            Compliance_status_Data_df = pd.DataFrame(data, columns=headers)
            st.success("✅ Successfully fetched Compliance Status Data")
        except Exception as e:
            st.error(f"❌ Error fetching Compliance Status Data: {e}")

        # ------------------ 3️⃣ Next Year Target Data ------------------
        try:
            thead_path = '/html/body/app-root/app-epr/app-annual-report-filing/div/div[1]/div[2]/div[2]/div[1]/div[2]/kl-simple-table-with-pagination/div[1]/div/div[1]/table/thead[2]/tr'
            tbody_path = '/html/body/app-root/app-epr/app-annual-report-filing/div/div[1]/div[2]/div[2]/div[1]/div[2]/kl-simple-table-with-pagination/div[1]/div/div[1]/table/tbody'

            headers = [th.text.strip() for th in driver.find_elements(By.XPATH, thead_path + '/th')]
            rows = driver.find_elements(By.XPATH, tbody_path + '/tr')
            data = []
            for row in rows:
                cols = [td.text.strip() for td in row.find_elements(By.TAG_NAME, 'td')]
                data.append(cols)
            Next_year_target_Data_df = pd.DataFrame(data, columns=headers)
            st.success("✅ Successfully fetched Next Year Target Data")
        except Exception as e:
            st.error(f"❌ Error fetching Next Year Target Data: {e}")

        # ------------------ 📝 Process 'category' column for all DFs ------------------
        def convert_to_roman(num_str):
            mapping = {'1': 'I', '2': 'II', '3': 'III', '4': 'IV'}
            return mapping.get(num_str.strip(), num_str.strip())

        def clean_text(text):
            return re.sub(r'[\\/\-_,]', '', text).strip()

        def process_category(df):
            if 'Category' in df.columns:
                new_category = []
                new_rec_eol = []

                for val in df['Category']:
                    val_clean = clean_text(val)
                    match = re.search(r'Cat\s*(\d+|[IVX]+)', val_clean, re.IGNORECASE)
                    if match:
                        num_part = match.group(1)
                        if num_part.isdigit():
                            roman = convert_to_roman(num_part)
                        else:
                            roman = num_part.upper()
                        base_cat = f"Cat {roman}"
                        rest = val_clean.replace(match.group(0), '').strip()
                        new_category.append(base_cat)
                        new_rec_eol.append(rest)
                    else:
                        new_category.append(val_clean)
                        new_rec_eol.append('')

                idx = df.columns.get_loc('Category') + 1
                df['Category'] = new_category
                df.insert(idx, 'Rec_Eol', new_rec_eol)

        for df in [Annual_report_Data_df, Compliance_status_Data_df, Next_year_target_Data_df]:
            try:
                process_category(df)

            except Exception as e:
                st.error(f"❌ Error processing 'category' column: {e}")

        for df in [Annual_report_Data_df, Compliance_status_Data_df, Next_year_target_Data_df]:
            try:
                if df.columns[0] == '' or 'Unnamed' in df.columns[0]:
                    df.drop(df.columns[0], axis=1, inplace=True)

                # Add extra columns
                df["Type_of_entity"] = entity_type
                df["entity_name"] = entity_name
                df["email_id"] = email_id

            except Exception as e:
                st.error(f"❌ Error processing DataFrame: {e}")


    except Exception as e:
        st.error(f"❌ Overall error during Annual Report Data fetching: {e}")
    
# --------------------------------SAVING ALL SCRAPE DATA IN A SINGLE EXCEL FILE-----------------------------
    dfs = {
        'Sales Data': df_sales,
        'Procurement Data': material_procurement_df,
        'Credit1 nested': df_wallet_credit,
        'Debit1 nested': df_wallet_debit,
        'Credit Transactions': Credit_Transactions_df,
        'Debit Transactions': Debit_Transactions_df,
        'Certificate Generations': Certificate_Generations_df,
        'Filing Transactions': Filing_Transactions_df,
        'Target Data' : Target_df,
        'Annual_report_Data': Annual_report_Data_df,
        'Compliance_status_Data': Compliance_status_Data_df,
        'Next_year_target_Data': Next_year_target_Data_df,
        'Consumption Data': consumption_regn_df,
        'Annual Consumption Data': annual_consumption_df,
        'StateWise Consumption Data': cat_df 
    }
    
    # Get timestamp
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    
    # File name with timestamp
    file_name = f"EPR_Website_Scrape_{timestamp}.xlsx"
    
    # Write each DataFrame to its own sheet
    with pd.ExcelWriter(file_name, engine='xlsxwriter') as writer:
        for sheet_name, df in dfs.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    st.success(f"Excel file '{file_name}' saved successfully!")

    time.sleep(50000)
# --------------------------------------------------------------------------------

# --- Streamlit UI ---
st.title("📊 EPR Dashboard Scraper")

# --- Input Credentials ---
with st.form("login_form"):
    mail = st.text_input("Enter your username/email:")
    password = st.text_input("Enter your password:", type="password")
    submitted = st.form_submit_button("Submit Credentials")

# --- Initialize Browser ---
def initialize_browser():
    global driver
    driver = st.session_state.get("driver", None)
    if driver is None:
        options = Options()
        options.add_experimental_option("detach", True)
        driver = webdriver.Edge(options=options)
        driver.maximize_window()
        driver.implicitly_wait(15)
        st.session_state.driver = driver
    return driver

# --- Open Browser and Login ---
def open_browser_and_login():
    global driver
    driver = initialize_browser()

    st.warning("🚀 Browser is launching... Please log in manually including CAPTCHA and OTP.")
    driver.get('https://eprplastic.cpcb.gov.in/#/plastic/home')

    # --- Fill login form automatically ---
    try:
        action = ActionChains(driver)
        username_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="user_name"]'))
        )
        password_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="password_pass"]'))
        )

        action.click(username_input).perform()
        username_input.send_keys(mail)
        time.sleep(1)
        action.click(password_input).perform()
        password_input.send_keys(password)
    except Exception as e:
        st.warning(f"⚠️ Unable to auto-fill credentials: {e}")

    st.info("🕒 Waiting for login... You have 10 minutes to complete login.")
    WebDriverWait(driver, 600).until(
        EC.presence_of_element_located((By.XPATH, '//span[@class="account-name"]'))
    )
    st.success("✅ Login detected.")

    # --- Fetch user details ---
    email_id = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (By.XPATH, '//tbody[@id="ScrollableSimpleTableBody"]//span[contains(text(),"@")]')
        )
    ).text

    time.sleep(2)
    driver.get("https://eprplastic.cpcb.gov.in/#/epr/pibo-dashboard-view")

    entity_type = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (By.XPATH, '//p[text()="User Type"]/following::span[1]')
        )
    ).text

    entity_name = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (By.XPATH, '//p[text()="Company Name"]/following::span[1]')
        )
    ).text

    # --- Save values to session_state ---
    st.session_state["email_id"] = email_id
    st.session_state["entity_name"] = entity_name
    st.session_state["entity_type"] = entity_type
    st.session_state["is_logged_in"] = True

    st.info(f"📧 Logged in as: {email_id}")
    st.info(f"🏢 Entity Name: {entity_name}")
    st.info(f"👤 Entity Type: {entity_type}")

# --- Scrape Trigger Function ---
def start_scraping():
    global driver
    driver = st.session_state.get("driver", None)
    if not driver:
        st.warning("❗ Please open the browser and log in before scraping.")
        return

    if st.session_state.get("is_logged_in"):
        email_id = st.session_state["email_id"]
        entity_name = st.session_state["entity_name"]
        entity_type = st.session_state["entity_type"]

        st.info(f"📧 Logged in as: {email_id}")
        st.info(f"🏢 Entity Name: {entity_name}")
        st.info(f"👤 Entity Type: {entity_type}")

        # Call your scraping logic here (you already have it in your scrape function)
        scrape()  # This will use the stored user info as needed
    else:
        st.warning("🔒 You are not logged in. Please open the browser and log in first.")

# --- Button Actions ---
if st.button("Open Browser"):
    if not mail or not password:
        st.warning("⚠️ Please enter both email and password above before launching the browser.")
    else:
        try:
            open_browser_and_login()
        except Exception as e:
            st.error(f"❌ Browser error: {e}")
            st.warning("🧭 Browser will remain open. Please check it manually.")

if st.button("Start Scraping"):
    start_scraping()
