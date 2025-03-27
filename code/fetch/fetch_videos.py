import os

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
import csv

scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]

def youtube_API_setup():
# Disable OAuthlib's HTTPS verification when running locally.
    # *DO NOT* leave this option enabled in production.
    clients_secret_path = '/Users/lukasvm/UTK /Spring 25/DATA 304/Final Project/secrets/client_secret.json'
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    api_service_name = "youtube"
    api_version = "v3"
    client_secrets_file = clients_secret_path 

    # Get credentials and create an API client
    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
        client_secrets_file, scopes)
    credentials = flow.run_local_server(port=8080)
    youtube = googleapiclient.discovery.build(
        api_service_name, api_version, credentials=credentials)
    
    return youtube

def json_csv(json_response, file_path = '../../data/videos/youtube_videos.csv'):
    # Load JSON data
    data = json_response

    # Define CSV file name
    csv_filename = file_path

    # Extract relevant data
    items = json_response.get("items", [])
    extracted_data = []

    for item in items:
        snippet = item['snippet']
        statistics = item['statistics']
        contentDetails = item['contentDetails']
        topicDetails = item.get('topicDetails')
        print(contentDetails, topicDetails)
        extracted_data.append({
            'video_id': item['id'],
            'published_at': snippet['publishedAt'],
            'channel_id': snippet['channelId'],
            'title': snippet['title'],
            'description': snippet['description'],
            'channel_title': snippet['channelTitle'],
            'tags': ', '.join(snippet.get('tags',[])),
            'category_id': snippet['categoryId'],
            'view_count': statistics['viewCount'],
            'like_count': statistics['likeCount'],
            'favorite_count': statistics['favoriteCount'],
            'comment_count': statistics['commentCount'],
            'duration': contentDetails['duration'],
            'topic': ','.join(topicDetails.get('topicCategories',[]))
        })

    # Write data to CSV
    with open(csv_filename, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = [
            'video_id',
            'published_at',
            'channel_id',
            'title',
            'description',
            'channel_title',
            'tags',
            'category_id',
            'view_count',
            'like_count',
            'favorite_count',
            'comment_count',
            'duration',
            'topic'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()  # Write column headers
        writer.writerows(extracted_data)  # Write data rows

    print(f"CSV file '{csv_filename}' has been created successfully!")

def fetch_videos(query='python', limit=10, save_path='{query}'):
    CSV_FILE_PATH = save_path.format(query=query)

    # Set up youtube API connection and authentication
    youtube =youtube_API_setup()

    # Search Youtube videos with query
    search_request = youtube.search().list(
        part="snippet",
        maxResults=limit,
        q=query
    )
    search_response = search_request.execute()

    # Get videos_ids from search_response
    ids =[]
    for item in search_response.get("items", []):
        if item["id"].get("videoId", "N/A"):
            ids.append(item["id"].get("videoId", "N/A"))
    
    # Make Request to get videos snippet & stats
    video_request = youtube.videos().list(
        part="statistics,snippet,contentDetails,topicDetails",
        id=','.join(ids)
    )
    videos_response = video_request.execute()
    # Save results
    if videos_response:
        # Write JSON to CSV
        json_csv(videos_response, file_path=CSV_FILE_PATH)
    else:
        print(f"Error: nodata")

    return ids

if __name__ == '__main__':
    fetch_videos(query='prank')