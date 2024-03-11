import azure.functions as func
import requests
from azure.storage.blob import BlobServiceClient, BlobBlock
import os
import json
import feedparser
from dateutil import parser
import base64
import logging
from azure.storage.queue import QueueClient, BinaryBase64EncodePolicy
from datetime import datetime
import azure.cognitiveservices.speech as speechsdk


app = func.FunctionApp()

def upload_rss_entity_to_blob(connection_string, container_name, blob_name, podcast_url):
    try:
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob=blob_name)
        
        # 使用 requests stream下载
        response = requests.get(podcast_url, stream=True)
        if response.status_code == 200:
            block_list = []
            index = 0  # 用于創建 block id
            for chunk in response.iter_content(chunk_size=4 * 1024 * 1024):  # 4MB chunk size
                if chunk:
                    block_id = base64.b64encode(f"block-{index}".encode()).decode()
                    blob_client.stage_block(block_id, chunk)
                    block_list.append(BlobBlock(block_id))
                    index += 1

            blob_client.commit_block_list(block_list)
            print(f"Successfully uploaded '{blob_name}' to Azure Blob Storage.")
        else:
            print(f"Failed to download podcast from URL '{podcast_url}'. HTTP status code: {response.status_code}")

    except Exception as e:
        print(f"Failed to upload '{blob_name}' to Azure Blob Storage. Error: {e}")
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
    
def speech_to_text_and_upload_to_blob(podcast_url, connection_string, container_name, blob_name):
    # 設置
    speech_config = speechsdk.SpeechConfig(subscription=os.environ.get('SPEECH_KEY'), region=os.environ.get('SPEECH_REGION'))
    speech_config.speech_recognition_language = "zh-TW"
    
    # 使用 podcast URL 
    audio_config = speechsdk.audio.AudioConfig(filename=podcast_url)
    
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    
    # 進行語音識別
    print("開始轉換...")
    speech_recognition_result = speech_recognizer.recognize_once_async().get()
    
    # 檢查结果
    if speech_recognition_result.reason == speechsdk.ResultReason.RecognizedSpeech:
        recognized_text = speech_recognition_result.text
        print("轉換後的文檔：", recognized_text)
        
        
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        
        # 上傳文檔到 blob
        print(f"正在上傳文檔到 Blob Storage: {container_name}/{blob_name}")
        blob_client.upload_blob(recognized_text, overwrite=True)
        print("上傳完成。")
        
    elif speech_recognition_result.reason == speechsdk.ResultReason.NoMatch:
        print("没有識別到语音。")
    elif speech_recognition_result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = speech_recognition_result.cancellation_details
        print("語音識別被取消：", cancellation_details.reason)
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            print("错误详情：", cancellation_details.error_details)

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
    queue_client = QueueClient.from_connection_string(conn_str=os.getenv("AZURE_STORAGE_CONNECTION_STRING"), queue_name="podcast-queue")
    queue_client.message_encode_policy = BinaryBase64EncodePolicy()
    download_status = get_downloaded_status(blob_service_client, container_name)
    latest_episode_guid = None
   
    # 處理最新的 Podcast
    for feed_info in rss_feeds:
        rss_url = feed_info["url"]
        prefix = feed_info["prefix"]
        feed = feedparser.parse(rss_url)
    
        if rss_url not in download_status:  # 第一次下載這
            episodes_batches = feed.entries[:40]   # 下載最新的40集
        else:
            latest_episode_guid = feed.entries[0].get("guid")
            if download_status[rss_url]["guid"] != latest_episode_guid:    
                episodes_batches = [[feed.entries[0]]]  # 只下載最新的一集
            else:
                continue
        logging.info(f"Episodes batches to process: {len(episodes_batches)}")
        if episodes_batches:
            latest_episode_guid = episodes_batches[0].get("guid")
            for batch in episodes_batches:
                message = {
                    "url": rss_url,
                    "prefix": prefix,
                    "episodes_guids":[batch.get("guid", None)] 
                }
                message_bytes = json.dumps(message).encode('utf-8')
                # 對消息進行 Base64 編碼
                encoded_message = base64.b64encode(message_bytes).decode('utf-8')
                # 發送編碼後的消息
                queue_client.send_message(encoded_message)
                logging.info(f"Sending message to queue for batch: {message}")

        if latest_episode_guid:
            # 更新下载狀態
            download_status[rss_url] = {
                "last_downloaded": str(datetime.now()),
                "guid": latest_episode_guid
        }
            # 更新狀態
            update_downloaded_status(blob_service_client, container_name, download_status)
           

    logging.info('Python timer trigger function executed.')


@app.queue_trigger(arg_name="azqueue", queue_name="podcast-queue",
                               connection="podcastzhtw") 
def queue_trigger(azqueue: func.QueueMessage):
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME")
    queue_name="podcast-queue"
    
    # 將解碼後的 bytes 轉換為 JSON 字符串
    message = json.loads(azqueue.get_body().decode('utf-8'))
    rss_url = message['url']
    prefix = message['prefix'] 
    episodes_guids = message['episodes_guids']
    feed = feedparser.parse(rss_url)
    entries_dict = {entry.get('guid'): entry for entry in feed.entries}
    for guid in episodes_guids:
        logging.info(f"Found entry for guid: {guid}")
        entry = entries_dict.get(guid)
        if entry:
            podcast_url = entry.links[0].href
            blob_name = f"{prefix}[{parser.parse(entry.published).strftime('%Y%m%d')}] {entry.title}.mp3" 
            try:
                response = requests.get(podcast_url, stream=True)  # 使用 stream 参数確保不會立即下載所有
                if response.status_code == 200:
                    logging.info(f"Downloading {podcast_url} to {blob_name}...")
                    
                    speech_to_text_and_upload_to_blob(podcast_url, connection_string, container_name, blob_name)
                  
                    logging.info(f"Uploaded {blob_name} to Azure Blob Storage.")
                else:
                    logging.info(f"Skipping {blob_name} because it is not a valid podcast.") 
                    print(f"Successfully uploaded '{blob_name}' to Azure Blob Storage in chunks.")
            except Exception as e:
                 print(f"Failed to download and upload in chunks. Error: {e}")

