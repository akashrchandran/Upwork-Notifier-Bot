import json
import logging
import os
import sqlite3
from datetime import datetime
from re import findall

import feedparser
import requests
import tzlocal
from bs4 import BeautifulSoup

# Get the absolute path of the script file
script_dir = os.path.dirname(os.path.abspath(__file__))
processed_jobs_file = os.path.join(script_dir, 'processed_jobs.json')
configs_file = os.path.join(script_dir, 'config.json')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename=f'{script_dir}/upwork_scraper.log'
)
logger = logging.getLogger(__name__)

# Load configurations from config.json file
logger.debug('Reading config file')
with open(configs_file, 'r') as f:
    config = json.load(f)

logger.debug('Creating connection to the SQLite database')
# Create a connection to the SQLite database
db_file = os.path.join(script_dir, 'upwork_jobs.db')
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# Create the jobs table if it doesn't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS jobs (
        job_id TEXT PRIMARY KEY,
        title TEXT,
        category TEXT,
        rate TEXT,
        summary TEXT,
        link TEXT,
        posted_on TEXT,
        country TEXT,
        skills TEXT
    );
''')

tgBotToken = config['tgBotToken']
feed_urls = config['feed_url']
bot_url = f'https://api.telegram.org/bot{tgBotToken}/'
chat_id = config['chat_id']

# Set your local timezone
local_tz = tzlocal.get_localzone()

# Fetch new jobs from the RSS feed and send notifications to Telegram
logger.debug('Fetching jobs from the RSS feed')
for feed_url in feed_urls:
    # Parse the RSS feed
    feed = feedparser.parse(feed_url)

    # Loop through the entries in the feed (most recent first)
    for entry in reversed(feed.entries):
        # Check if this job has already been processed
        job_id = findall(r'(?<=_)%([a-zA-Z0-9]+)', entry.link)[0]
        cursor.execute('SELECT * FROM jobs WHERE job_id = ?', (job_id,))
        if cursor.fetchone():
            continue
        logger.debug('New job was found')

        # Convert the published time to your local timezone
        published_time = datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %z')
        published_time = published_time.astimezone(local_tz)

        # Calculate the relative time since the job was published
        now = datetime.now(local_tz)
        relative_time = now - published_time
        if relative_time.days > 1:
            relative_time = f"{relative_time.days} days"
        else:
            total_seconds = relative_time.total_seconds()
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            relative_time = f"{hours}h {minutes}m"

        posted_on = f'{relative_time} ago ({published_time.strftime("%Y-%m-%d %H:%M")})'

        # Parse the RSS entry
        soup = BeautifulSoup(entry.content[0]['value'], 'html.parser')

        # Get payment type
        budget = soup.find('b', string='Budget')
        hourly_rate = soup.find('b', string='Hourly Range')
        try:
            rate = budget.find_next_sibling(string=True) if budget else hourly_rate.find_next_sibling(string=True)
            rate = rate.replace(":", "").replace("\n", "").strip()
            rate = (
                f'Budget {rate}'
                if budget
                else f'Hourly {rate}'
                if hourly_rate
                else 'N/A'
            )
        except Exception as e:
            logger.debug(f'Rate is not available for {entry.link.strip()}: {e}')
            rate = 'N/A'

        # Get job category
        category = soup.find('b', string='Category').find_next_sibling(string=True).replace(":", "").strip().replace(" ", "_").replace("-", "_").replace("/", "_").replace("&", "and")

        # Get customer country
        country = soup.find('b', string='Country').find_next_sibling(string=True).replace(":", "").strip()

        # Get required skill and format them as hashtags
        try:
            skills = soup.find('b', string='Skills').find_next_sibling(string=True).replace(":", "").strip()
        except Exception as e:
            skills='N/A'
        try:
            skills_hashtags = " ".join(["#" + word.strip().replace(" ", "_").replace("-", "_").replace("/", "_").replace("&", "and") for word in skills.split(", ")[:10]]).strip()
        except Exception as e:
            skills_hashtags = "N/A"
        # Get the 1st sentence of the summary
        summary = (entry.summary.split('.')[0] + ".").replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n").replace("<br >", "\n").replace('\n\n', '\n')

        # Build the message to send to Telegram
        message = f'<b>{entry.title.replace(" - Upwork", "")}</b>' \
                  f'\n<b>#{category}</b>' \
                  f'\n💲 {rate}' \
                  f'\n\n📄 {summary}' \
                  f'\n🔗 {entry.link.strip()}' \
                  f'\n\n🕑 {posted_on}' \
                  f'\n🌍 {country}' \
                  f'\n\n{skills_hashtags}'

        # Send the message to Telegram
        payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
        try:
            r = requests.post(f'{bot_url}sendMessage', json=payload)
            r.raise_for_status()
            logger.debug('Message sent successfully')
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending message to Telegram: {e}")
            continue
        # Add the job ID to the list of processed jobs
        logger.debug(f'Saving job {job_id} to db')
        cursor.execute("INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (job_id, entry.title, category, rate, summary, entry.link, entry.published, country, skills))

# Save the processed jobs to db
conn.commit()
conn.close()
