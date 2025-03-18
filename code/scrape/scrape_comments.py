import pandas as pd
import json
import os
import sys
import re
import time

import requests

# pandas dataframe display configuration
pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 1000)

YOUTUBE_COMMENTS_AJAX_URL = 'https://www.youtube.com/comment_service_ajax'

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36'
# csv file path
FILE_PATH = '../../data/comments/{video_id}.csv'

# set parameters
# filter comments by popularity or recent, 0:False, 1:True
SORT_BY_POPULAR = 0
# default recent
SORT_BY_RECENT = 1
# set comment limit
COMMENT_LIMIT = 100

# Youtube AJAX config regexes
YT_CFG_RE = r'ytcfg\.set\s*\(\s*({.+?})\s*\)\s*;'
YT_INITIAL_DATA_RE = r'(?:window\s*\[\s*["\']ytInitialData["\']\s*\]|ytInitialData)\s*=\s*({.+?})\s*;\s*(?:var\s+meta|</script|\n)'


def regex_search(text, pattern, group=1, default=None):
    match = re.search(pattern, text)
    return match.group(group) if match else default


def ajax_request(session, endpoint, ytcfg, retries=5, sleep=20):
    url = 'https://www.youtube.com' + endpoint['commandMetadata']['webCommandMetadata']['apiUrl']

    data = {'context': ytcfg['INNERTUBE_CONTEXT'],
            'continuation': endpoint['continuationCommand']['token']}

    for _ in range(retries):
        response = session.post(url, params={'key': ytcfg['INNERTUBE_API_KEY']}, json=data)
        if response.status_code == 200:
            return response.json()
        if response.status_code in [403, 413]:
            return {}
        else:
            time.sleep(sleep)


def download_comments(YOUTUBE_VIDEO_URL, sort_by=SORT_BY_POPULAR, language=None, sleep=0.1):
    # Start request session
    session = requests.Session()
    session.headers['User-Agent'] = USER_AGENT
    response = session.get(YOUTUBE_VIDEO_URL)

    # Handle cookies
    if 'uxe=' in response.request.url:
        session.cookies.set('CONSENT', 'YES+cb', domain='.youtube.com')
        response = session.get(YOUTUBE_VIDEO_URL)

    # Get HTML response, then find AJAX Config Object
    html = response.text
    ytcfg = json.loads(regex_search(html, YT_CFG_RE, default=''))

    if not ytcfg:
        return  # Unable to extract configuration
    if language:
        ytcfg['INNERTUBE_CONTEXT']['client']['hl'] = language

    # Handle Comment Section
    data = json.loads(regex_search(html, YT_INITIAL_DATA_RE, default=''))
    section = next(search_dict(data, 'itemSectionRenderer'), None)
    renderer = next(search_dict(section, 'continuationItemRenderer'), None) if section else None
    if not renderer:
        # Comments disabled?
        return
    
    # Handle retrieve comments by 'Popularity' or 'Newest'
    sort_menu = next(search_dict(data, 'sortFilterSubMenuRenderer'), {}).get('subMenuItems', [])
    if not sort_menu:
        # No sort menu. Maybe this is a request for community posts?
        section_list = next(search_dict(data, 'sectionListRenderer'), {})
        continuations = list(search_dict(section_list, 'continuationEndpoint'))
        # Retry..
        data = ajax_request(continuations[0], ytcfg) if continuations else {}
        sort_menu = next(search_dict(data, 'sortFilterSubMenuRenderer'), {}).get('subMenuItems', [])
    if not sort_menu or sort_by >= len(sort_menu):
        raise RuntimeError('Failed to set sorting')
    
    # Make AJAX requests to retrieve comments
    continuations = [sort_menu[sort_by]['serviceEndpoint']]
    while continuations:
        continuation = continuations.pop()
        response = ajax_request(session, continuation, ytcfg)

        if not response:
            break
        if list(search_dict(response, 'externalErrorMessage')):
            raise RuntimeError('Error returned from server: ' + next(search_dict(response, 'externalErrorMessage')))

        actions = list(search_dict(response, 'reloadContinuationItemsCommand')) + \
                  list(search_dict(response, 'appendContinuationItemsAction'))

        for action in actions:
            for item in action.get('continuationItems', []):
                if action['targetId'] in ['comments-section',
                                            'engagement-panel-comments-section',
                                            'shorts-engagement-panel-comments-section']:
                    # Process continuations for comments and replies.
                    continuations[:0] = [ep for ep in search_dict(item, 'continuationEndpoint')]
                if action['targetId'].startswith('comment-replies-item') and 'continuationItemRenderer' in item:
                    # Process the 'Show more replies' button
                    continuations.append(next(search_dict(item, 'buttonRenderer'))['command'])
                    

        for comment in reversed(list(search_dict(response, 'commentEntityPayload'))):
            yield {'cid': comment['properties']['commentId'],
                   'text': comment['properties']['content']['content'],
                   'time': comment['properties']['publishedTime'],
                   'author': comment.get('author', {}).get('displayName', 'unknown'),
                   'channelId': comment['author']['channelId']
            }

        time.sleep(sleep)


def search_dict(partial, search_key):
    stack = [partial]
    while stack:
        current_item = stack.pop()
        if isinstance(current_item, dict):
            for key, value in current_item.items():
                if key == search_key:
                    yield value
                else:
                    stack.append(value)
        elif isinstance(current_item, list):
            for value in current_item:
                stack.append(value)


def get_video_comments(url='', video_id = 'JOksXpBtOUc', file_path='{video_id}.csv'):
    df_comment = pd.DataFrame()
    try:
        if url:
            youtube_url = url
            id = url.split('=')[1]
        else:
            youtube_url = 'https://www.youtube.com/watch?v='+ video_id

        file_name = file_path.format(video_id = video_id)
        limit = COMMENT_LIMIT

        print('Downloading Youtube comments for video:', youtube_url)

        count = 0

        start_time = time.time()

        for comment in download_comments(youtube_url):
            # df_comment = df_comment.append(comment, ignore_index=True)
            df_comment = pd.concat([df_comment, pd.DataFrame([comment])], ignore_index=True)
            # comments overview
            # comment_json = json.dumps(comment, ensure_ascii=False)
            # print(comment_json)
            count += 1
            if limit and count >= limit:
                break
        # add videoId column
        df_comment['videoId'] = video_id
        print("DataFrame Shape: ", df_comment.shape, "\nComment DataFrame: ", df_comment)

        if not os.path.isfile(file_name):
            df_comment.to_csv(file_name, encoding='utf-8', index=False)
        else:  # else it exists so append without writing the header
            df_comment.to_csv(file_name, mode='a', encoding='utf-8', index=False, header=False)

        print('\n[{:.2f} seconds] Done!'.format(time.time() - start_time))

    except Exception as e:
        print('Error:', str(e))
        sys.exit(1)

    # dumping youtube comments


""" 
1. Dump comments to a csv  from a single video

"""
youtube_URL = 'https://www.youtube.com/watch?v=JOksXpBtOUc'
get_video_comments(youtube_URL, file_path=FILE_PATH)

"""
2. Dump comments to a csv by parsing links from a csv with video links

Example -
Create a csv with one column titled 'link'
a sample is given below

'ytb_video_list.csv'

link
https://www.youtube.com/watch?v=-t_uhBBDbA4
https://www.youtube.com/watch?v=75vjjRza7IU
https://www.youtube.com/watch?v=j6dmaPzOBHY
https://www.youtube.com/watch?v=Yj2efyQV1RI
https://www.youtube.com/watch?v=HV652F7U6Qs
https://www.youtube.com/watch?v=47iXEucg3eo
https://www.youtube.com/watch?v=ofHXBLEE3TQ
https://www.youtube.com/watch?v=X6lGqSfVRT8
https://www.youtube.com/watch?v=a_-z9FhGBrE
https://www.youtube.com/watch?v=wTUM_4cVlE4


"""
# df_video_list = pd.read_csv('ytb_video_list.csv')
# print(df_video_list['link'].map(lambda x: main(x)))
# print(main(pd.read_csv('ytb_video_list.csv')['link']))


"""
3. Dump to a csv from a a list with video links
"""
# ytb_video_list = ['https://www.youtube.com/watch?v=-t_uhBBDbA4',
#                   'https://www.youtube.com/watch?v=75vjjRza7IU',
#                   'https://www.youtube.com/watch?v=j6dmaPzOBHY',
#                   'https://www.youtube.com/watch?v=Yj2efyQV1RI']

# for video_link in ytb_video_list:
#     main(video_link)
