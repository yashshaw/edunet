import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import time
import re
from datetime import datetime, timedelta
from fake_useragent import UserAgent

# Function to interpret natural language command
def interpret_command(command):
    result = {
        'title': None,
        'location': None,
        'number_of_jobs': 10,
        'days_filter': None
    }
    # Number of jobs
    num_match = re.search(r"(\d+)\s*(jobs)?", command)
    if num_match:
        result['number_of_jobs'] = int(num_match.group(1))
    # Title keywords
    title_match = re.search(r"\d+\s+(.*?)\s+jobs?", command, re.IGNORECASE)
    if title_match:
        result['title'] = title_match.group(1)
    # Location
    loc_match = re.search(r"(?:in|at|near)\s+([A-Za-z ]+?)(?:\s+posted|$)", command, re.IGNORECASE)
    if loc_match:
        result['location'] = loc_match.group(1).strip()
    # Days filter
    days_match = re.search(r"last\s+(\d+)\s+days", command, re.IGNORECASE)
    if days_match:
        result['days_filter'] = int(days_match.group(1))
    
    return result

# Hardcoded fallback if interactive input fails
try:
    command = input("Enter command: ")
except OSError:
    print("Interactive input not supported. Using default command.")
    command = "Scrape 20 Python developer jobs in Kolkata posted in the last 7 days"

params = interpret_command(command)

# Use fallback values if needed
try:
    title = params['title'] or input("Enter job title: ")
    location = params['location'] or input("Enter job location: ")
except OSError:
    print("Interactive input not supported. Using fallback values.")
    title = params['title'] or "Python developer"
    location = params['location'] or "Kolkata"

number_of_jobs = params['number_of_jobs']
days_filter = params['days_filter']

ua = UserAgent()
headers = {"User-Agent": ua.random}
start = 0
list_per_page = 10
job_list = []

while start < number_of_jobs:
    id_list = []
    post_times = []
    try:
        url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={title}&location={location}&start={start}"
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch jobs list: {e}")
        break

    soup = BeautifulSoup(res.text, 'html.parser')
    cards = soup.find_all('li')
    if not cards:
        print("No job postings found or blocked by LinkedIn.")
        break

    for card in cards:
        time_tag = card.find('time', class_='job-search-card__listdate')
        post_times.append(time_tag.get('datetime') if time_tag else None)
        base = card.find('div', class_='base-card')
        if base and base.has_attr('data-entity-urn'):
            jid = base['data-entity-urn'].split(':')[-1]
            id_list.append(jid)
        if len(id_list) >= number_of_jobs:
            break

    for idx, jid in enumerate(id_list):
        try:
            url2 = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{jid}"
            r2 = requests.get(url2, headers=headers, timeout=10)
            r2.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch job ID {jid}: {e}")
            continue

        s2 = BeautifulSoup(r2.text, 'html.parser')
        post = {
            'JOB_TITLE': None,
            'COMPANY_NAME': None,
            'JOB_ID': jid,
            'JOB_POSTED_TIME': post_times[idx] if idx < len(post_times) else None
        }
        h2 = s2.find('h2')
        post['JOB_TITLE'] = h2.text.strip() if h2 else None
        comp = s2.find('a', class_='topcard__org-name-link')
        post['COMPANY_NAME'] = comp.text.strip() if comp else None
        job_list.append(post)
        time.sleep(1)
        if len(job_list) >= number_of_jobs:
            break

    start += list_per_page

# Save to DataFrame
if not job_list:
    print("No job data to save.")
else:
    df = pd.DataFrame(job_list)
    if days_filter:
        df['JOB_POSTED_TIME'] = pd.to_datetime(df['JOB_POSTED_TIME'], errors='coerce')
        cutoff = datetime.today() - timedelta(days=days_filter)
        df = df[df['JOB_POSTED_TIME'] >= cutoff]

    file = f"{title.replace(' ', '_')}_jobs.csv"
    idx = 0
    while os.path.exists(file):
        idx += 1
        file = f"{title.replace(' ', '_')}_jobs_{idx}.csv"
    df.to_csv(file, index=False)
    print(f"Saved {len(df)} jobs to {file}")
