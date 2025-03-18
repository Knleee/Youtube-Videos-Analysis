import scrapetube
import json
import numpy as np

# functions
def to_minutes(time_str='1:00:00'):
      '''Turn a youtube time string to seconds'''
      time = time_str.split(':')
      match len(time):
            case 1: # time_str only has seconds
                  return int(time[0])
            case 2: # time_str has minutes & seconds
                  return int(time[0])*60 + int(time[1])
            case 3: # time_str has hour, minutes & seconds
                  return int(time[0])*3600 + int(time[1])*60 + int(time[2])
            case _:
                  return 0

# get query
query = 'take note'

# scrape youtube search
response = scrapetube.get_search(query="travel vlog", limit=5)

# write response videos to json file
if response:
        # Write JSON response to a file
        with open("scraped_json.json", "w", encoding="utf-8") as json_file:
            videos = []
            for item in response:
                title = item['title']['runs'][0]['text']
                length = to_minutes(item['lengthText']['simpleText'])
                temp = {
                    'videoId': item['videoId'],
                    'title': title, 
                    'length_in_seconds': length,
                    'length_text':item['lengthText']['simpleText'], 
                    'views':   int(item['viewCountText']['simpleText'].split(' ')[0].replace(',',''))
                }
                videos.append(temp)
            json.dump(videos, json_file, indent=4)  # Pretty-print with indentation

        print("JSON response saved to response.json")
else:
        print(f"Error: nodata")


