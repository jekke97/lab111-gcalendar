print("Loading libraries...")
import re
import os
import time
import json
import requests
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta, timezone
from googleapiclient.discovery import build
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials

print('Acquiring secrets...')
SCOPES = ['https://www.googleapis.com/auth/calendar']
LAB111_URL = "https://www.lab111.nl/programma/listview/"
FORECAST = 14 # in days
REFRESH_TOKEN = os.environ.get("REFRESH_TOKEN","")
CLIENT_ID = os.environ.get("CLIENT_ID","")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET","")
print('Secrets acquired.')

def get_new_access_token():
    params = {
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": REFRESH_TOKEN
    }

    authorization_url = "https://oauth2.googleapis.com/token"
    r = requests.post(authorization_url, data=params)
    if r.ok:
        return r.json()['access_token']
    else:
        return None

def get_credentials():
    access_token = get_new_access_token()
    if not access_token:
        print("Unable to get new access token.")
        exit(-1)
    return Credentials(access_token)


def check_lab(result):
    return any(cal['summary'] == 'lab111' for cal in result['items'])


def create_event(show, today):
    tz       = ZoneInfo("Europe/Amsterdam").key
    starT    = [int(x) for x in show['s_time'].split(':')]
    duration = [int(x) for x in re.findall(r'\d+', show['duration'])]
    startTime= datetime(today.year, today.month, today.day, starT[0], starT[1]) + timedelta(days=show['day'])
    endTime  = startTime + timedelta(hours=duration[0], minutes=duration[1])

    event    = {
      'summary': show['name'],
      'location': show['lab'],
      'description': f"<a href={show['ticket']}>Ticket</a>" + '\n' +f"<a href={show['info']}>Description</a>",
      'start': {
        'dateTime': startTime.isoformat(),
        'timeZone': tz,
      },
      'end': {
        'dateTime': endTime.isoformat(),
        'timeZone': tz,
      }
    }
    return event


def main():
    print('Acquiring credentials...')
    service = build('calendar', 'v3', credentials=get_credentials())
    print('Credentials acquired.')
    today = datetime.now()
    ## Scraping
    soup = BeautifulSoup(requests.get(LAB111_URL).content, "lxml")
    program = []
    print('Scraping...')
    for day in range(FORECAST):
        movielist = soup.find_all('tr', class_=f'day{day}')
        movielist = movielist[1:]

        for movie in movielist:
            try:
                movie_url = re.findall('(?P<url>https?://[^\s]+")',str(movie))[1]
                movie_url = movie_url[:-1]

                shows = {
                  "s_time": movie.findAll('a')[0].text,
                  "duration": BeautifulSoup(requests.get(movie_url).content, 'lxml').find_all('ul', class_="speelduur")[0].text,
                  "name": movie.findAll('a')[1].text,
                  "day": day,
                  "lab": movie.find('span').text,
                  "ticket": str(movie.find('a', class_='button tic')).split('\"')[3],
                  "info": movie.findAll('a')[1]['href']
                }
                program.append(shows)
            except Exception as e:
                print(f"Skipping entry on day {day}: {e}")
                continue
        print(f'Day {day+1} forecasted.')
    print('Scraping done.')

    #Create calendar if needed
    calendars = service.calendarList().list().execute()
    if not check_lab(calendars):
        calendar = {
        'summary': 'lab111',
        'timeZone': 'Europe/Amsterdam',
        }
        created_calendar = service.calendars().insert(body=calendar).execute()
        calendar_id = created_calendar['id']
        print('Calendar created.')
    else:
        print('Calendar already exists.')
        for cal in calendars['items']:
            if cal['summary'] == 'lab111':
                calendar_id = cal['id']

    page_token = None
    while True:
        #find all events in the next two weeks
        events = service.events().list(calendarId=calendar_id,
                                     timeMin=(datetime.now(timezone.utc)).isoformat(),
                                     timeMax=(datetime.now(timezone.utc) + timedelta(days=FORECAST)).isoformat(),
                                     pageToken=page_token).execute()

        for event in events["items"]:
            print("Deleting events...")
            service.events().delete(calendarId=calendar_id, eventId=event['id']).execute()
        page_token = events.get('nextPageToken')
        if not page_token:
            break

    print('Adding events...')
    for show in program:
        service.events().insert(calendarId = calendar_id, body = create_event(show, today)).execute()
        time.sleep(.3)
    print('Done!')

if __name__ == '__main__':
    main()
