import logging
import os
import azure.functions as func
import requests
from azure.storage.blob import BlobServiceClient, BlobBlock
import feedparser
import uuid
import base64
import json
from dateutil import parser
from datetime import datetime



app = func.FunctionApp()

def get_downloaded_status(blob_service_client, container_name):
    try:
        container_client = blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob="downloaded_episodes_status.json")
        download_status_json = blob_client.download_blob().readall()
        download_status = json.loads(download_status_json)
    except Exception as e:
        download_status = {}
    return download_status

def update_downloaded_status(blob_service_client, container_name, download_status):
    container_client = blob_service_client.get_container_client(container_name)
    blob_client = container_client.get_blob_client(blob="downloaded_episodes_status.json")
    blob_client.upload_blob(json.dumps(download_status), overwrite=True)

def upload_rss_entity_to_blob(connection_string, container_name, blob_name, podcast_data):
    try:
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob=blob_name)
        # 分 chunk 上傳
        chunk_size = 4 * 1024 * 1024  # 4MB
        block_list = []
        size = len(podcast_data)
        start = 0
        number = 0

        while start < size:
            end = min(start + chunk_size, size)
            chunk_data = podcast_data[start:end]
            block_id = str(uuid.uuid4()).replace('-', '')
            encoded_block_id = base64.b64encode(block_id.encode()).decode()

            blob_client.stage_block(block_id=encoded_block_id, data=chunk_data)
            block_list.append(BlobBlock(block_id=encoded_block_id))

            start += chunk_size

            # 提交所有 chunks 以完成上傳
        blob_client.commit_block_list(block_list)
        print(f"Successfully uploaded '{blob_name}' to Azure Blob Storage.")
           

    except Exception as e:
        print(f"Failed to upload '{blob_name}' to Azure Blob Storage. Error: {e}")

rss_feeds = [
    {"url": "https://feeds.soundon.fm/podcasts/adf29720-e93b-4856-a09e-b73544147ec4.xml", "prefix": "【好味小姐】"}
]

@app.schedule(schedule="0 0 2 * * *", arg_name="myTimer", run_on_startup=True, use_monitor=False)
def timer_trigger(myTimer: func.TimerRequest) -> None:
    if myTimer.past_due:
        logging.info('The timer is past due!')

    # Azure Blob Storage 配置
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME")


    # 初始化 Azure Blob Storage 客户端
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    download_status = get_downloaded_status(blob_service_client, container_name)

    # 處理最新的 Podcast
    for feed_info in rss_feeds:
        rss_url = feed_info["url"]
        prefix = feed_info["prefix"]
        feed = feedparser.parse(rss_url)
        episodes_to_download = []
    
        if rss_url not in download_status:  # 第一次下載這
            episodes_to_download = feed.entries[:40]  # 下載最後40集
        else:
            latest_episode_guid = feed.entries[0].get("guid")
            if download_status[rss_url]["guid"] != latest_episode_guid:    
                episodes_to_download = feed.entries[0]

        for entry in episodes_to_download: #依次下載
            podcast_url = entry.links[0].href
        
            file_name = podcast_url.split("/")[-1]
            if 'enclosures' in entry and len(entry.enclosures) > 0:
                podcast_url = entry.enclosures[0]['href']  # 使用 enclosure  中的URL
                blob_name= f"{prefix}[{parser.parse(entry.published).strftime('%Y%m%d')}] {entry.title}.mp3"  
            else: 
                publish_date = parser.parse(entry.published)  # 使用 dateutil 解析發布日期
                formatted_date = publish_date.strftime('%Y%m%d')
                blob_name = f"{prefix}[{formatted_date}] {file_name}"
            latest_episode_guid = entry.get("guid", None)
            
        # 上傳到 Azure Blob Storage
            try:
                if(latest_episode_guid != None):
                    logging.info(f"Downloading {podcast_url} to {blob_name}...")
                    response = requests.get(podcast_url)
                    if response.status_code == 200:
                        podcast_data = response.content
                    upload_rss_entity_to_blob(connection_string, container_name, blob_name, podcast_data)
                    download_status[rss_url] = {
                        "last_downloaded": str(datetime.now()),
                        "guid": latest_episode_guid
                    }
                    update_downloaded_status(blob_service_client, container_name, download_status)
                    logging.info(f"Uploaded {blob_name} to Azure Blob Storage.")
                else:
                    logging.info(f"Skipping {blob_name} because it is not a valid podcast.")
            except Exception as e:
                logging.error(f"Failed to upload {blob_name}. Error: {e}")

    logging.info('Python timer trigger function executed.')
