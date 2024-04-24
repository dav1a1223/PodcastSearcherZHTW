import azure.functions as func
import requests
from azure.storage.blob import BlobServiceClient, BlobBlock, BlobServiceClient, BlobSasPermissions, generate_blob_sas
import os
import json
import feedparser
from dateutil import parser
import base64
import logging
from azure.storage.queue import QueueClient, BinaryBase64EncodePolicy
from datetime import datetime, timedelta
import http.client
import urllib.parse
from urllib.parse import unquote
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
import jieba

'''
import azure.cognitiveservices.speech as speechsdk
import tempfile
from pydub import AudioSegment
'''
import http.client
import base64
'''
from concurrent.futures import ThreadPoolExecutor, as_completed
'''
import urllib.request
import urllib.parse
import urllib.error



app = func.FunctionApp()

# 下載並轉換 url
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
def get_downloaded_status(blob_service_client, container_name, prefix):
    try:
        blob_name = f"{prefix}.json"

        container_client = blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob=blob_name)

        download_status_json = blob_client.download_blob().readall()
        if not download_status_json:
            logging.info(f"Status file {blob_name} is empty.")
            return {}  # 返回一个空字典，因为没有内容可解析
        else:
            download_status = json.loads(download_status_json)
    except Exception as e:
        logging.error(f"Failed to download or parse the status file {blob_name}: {e}")
        download_status = {}
    
    return download_status

def update_downloaded_status(blob_service_client, container_name, title, new_status, latest_guid):
    try:
        blob_name = f"{extract_prefix(title)}.json"
        container_client = blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_name)

        try:
            current_status = json.loads(blob_client.download_blob().content_as_text())
        except Exception as e:
            logging.error(f"Failed to download existing status file {blob_name}: {e}")
            return 

        if latest_guid != "":
            current_status["latest_guid"] = latest_guid
        if title in current_status:
            current_status[title]['status'] = new_status
        else:
            logging.error(f"Episode title {title} not found in the status file.")
            return 

        blob_client.upload_blob(json.dumps(current_status), overwrite=True)
        logging.info(f"Successfully updated the status for episode {title} to {new_status} in {blob_name}.")
    except Exception as e:
        logging.error(f"Failed to update the download status in Blob Storage for {blob_name}: {e}")



def upload_text_to_blob(container_name, text_blob_name, text, connection_string):
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client(container_name)
    blob_client = container_client.get_blob_client(blob=text_blob_name)
    if text:  # 確保不要再給我簡體中文了!!!!!
            text_bytes = text.encode('utf-8')
            blob_client.upload_blob(text_bytes, overwrite=True)
            logging.info(f"Text uploaded to Blob Storage with name: {text_blob_name}")
    else:
            logging.warning(f"Attempted to upload empty text to Blob Storage with name: {text_blob_name}")
def generate_sas_url(account_name, account_key, container_name, blob_name):

    # 設定 BlobSasPermissions
    permissions = BlobSasPermissions(read=True, write=True)
    logging.info("generate SAS")
    # 設定 SAS 有效期限
    sas_expiry = datetime.utcnow() + timedelta(hours=1)  # 1小時後過期

    # 生成 SAS token
    sas_token = generate_blob_sas(account_name=account_name,
                               container_name=container_name,
                               blob_name=blob_name,
                               account_key=account_key,
                               permission=permissions,
                               expiry=sas_expiry)

    # 拼接 Blob URL with SAS
    blob_url_with_sas = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"
    logging.info(f"SAS：{blob_url_with_sas}")
    return blob_url_with_sas


rss_feeds = [
    {"url": "https://feeds.soundon.fm/podcasts/adf29720-e93b-4856-a09e-b73544147ec4.xml", "prefix": "【好味小姐】"}
]

def get_stopwords(file):
    stopword_list = []
    with open(file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            stopword_list.append(line)
    return stopword_list

def word_segmentation(text, stopwords):
    seg_list = jieba.lcut(text)
    filtered_seg_list = []
    for word in seg_list:
        if word not in stopwords and word.strip():
            filtered_seg_list.append(word)
    return filtered_seg_list

def extract_prefix(blob_name):

    start = blob_name.find('【') + 1 
    end = blob_name.find('】')      

    if start > 0 and end > start:
        return blob_name[start:end]  
    else:
        return ""


@app.schedule(schedule="0 0 2 * * *", arg_name="myTimer", run_on_startup=False, use_monitor=False)
def timer_trigger(myTimer: func.TimerRequest, context: func.Context) -> None:
    if myTimer.past_due:
        logging.info('The timer is past due!')

    # Azure Blob Storage 配置
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME")
    function_directory = context.function_directory
    
    # 初始化 Azure Blob Storage 客户端
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
   
    queue_client = QueueClient.from_connection_string(conn_str=os.getenv("AZURE_STORAGE_CONNECTION_STRING"), queue_name="podcast-queue")
    queue_client.message_encode_policy = BinaryBase64EncodePolicy()
    
    latest_episode_guid = None
   
    # 處理最新的 Podcast
    for feed_info in rss_feeds:
        rss_url = feed_info["url"]
        prefix = feed_info["prefix"]
        feed = feedparser.parse(rss_url) 
        blob_name_prefix = f"{extract_prefix(prefix)}.json"
        container_client = blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob=blob_name_prefix)
        download_status = get_downloaded_status(blob_client, container_name, blob_name_prefix)
        if not download_status:  # 第一次下載這
            episodes_batches = feed.entries[20:25]   # 下載 10 集
        else:
            latest_guid = feed.entries[0].get("guid")
            if download_status["latest_guid"] != latest_guid:    \
                # 只下載最新的一集
                podcast_url = feed.entries[0].enclosures[0]["href"]
                blob_name = f"{prefix}[{parser.parse(feed.entries[0].published).strftime('%Y%m%d')}] {feed.entries[0].title}.mp3" 
                logging.info(f"Downloading {podcast_url} to {blob_name}...")
                upload_rss_entity_to_blob(connection_string, "audiofiles", blob_name, podcast_url)

        logging.info(f"Episodes batches to process: {len(episodes_batches)}")
        if episodes_batches:
            latest_guid = episodes_batches[0].get("guid")
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
        status = {}
        status["latest_guid"] = latest_guid 
        for entry in feed.entries:
            try:
                encode_title = entry.title.encode('utf-8')
                status[encode_title] = {
                    "guid": entry.id,
                    "status": "not_downloaded"
                }
            except UnicodeEncodeError as e:
                logging.error(f"Error encoding title {entry.title}: {e}")
            except UnicodeDecodeError as e:
                logging.error(f"Error decoding title {entry.title}: {e}")
    
        serialized_data = json.dumps(status)
        blob_client.upload_blob(serialized_data, overwrite=True)
        logging.info("Data uploaded to blob successfully.")

    logging.info('Python timer trigger function executed.')

@app.queue_trigger(arg_name="azqueue", queue_name="podcast-queue",
                               connection="podcastzhtw") 
def queue_trigger(azqueue: func.QueueMessage):
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    
      # 將解碼後的 bytes 轉換為 JSON 字符串
    message = json.loads(azqueue.get_body().decode('utf-8'))
    rss_url = message['url']
    prefix = message['prefix'] 
    episodes_guids = message['episodes_guids']
    feed = feedparser.parse(rss_url)
    entries_dict = {entry.get('guid'): entry for entry in feed.entries}
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    for guid in episodes_guids:
        logging.info(f"Found entry for guid: {guid}")
        entry = entries_dict.get(guid)
        if entry:
            podcast_url = entry.enclosures[0]["href"]
            blob_name = f"{prefix}[{parser.parse(entry.published).strftime('%Y%m%d')}] {entry.title}.mp3" 
            try:
                response = requests.get(podcast_url, stream=True)  # 使用 stream 参数確保不會立即下載所有
                if response.status_code == 200:
                    logging.info(f"Downloading {podcast_url} to {blob_name}...")
                    
                    upload_rss_entity_to_blob(connection_string,"audiofiles", blob_name, podcast_url)
                  
                    logging.info(f"Uploaded {blob_name} to Azure Blob Storage.")
                else:
                    logging.info(f"Skipping {blob_name} because it is not a valid podcast.") 
                    print(f"Successfully uploaded '{blob_name}' to Azure Blob Storage in chunks.")
            except Exception as e:
                 print(f"Failed to download and upload in chunks. Error: {e}")



@app.blob_trigger(arg_name="myblob", path="audiofiles",
                               connection="podcastzhtw_STORAGE") 
def blob_trigger(myblob: func.InputStream):
    logging.info(f"Python blob trigger function processed blob"
                f"Name: {myblob.name}"
                f"Blob Size: {myblob.length} bytes")
    logging.info(myblob.name)
    blob_name = myblob.name.split('/')[-1]
    subscription_key = os.getenv("SPEECH_KEY")
    host = 'podcasttranslater.cognitiveservices.azure.com'

    headers = {
    # Request headers
    'Content-Type': 'application/json',
    'Ocp-Apim-Subscription-Key':subscription_key ,
    }

    account_name = "podcastzhtw"
    account_key = os.getenv("AZURE_STORAGE_KEY")
    container_name = "audiofiles"
    logging.info(blob_name)
    
    blob_url_with_sas = generate_sas_url(account_name, account_key, container_name, blob_name)



    text_name = blob_name.rsplit('.', 1)[0] 
    body_dict = {
        "contentUrls": [
        blob_url_with_sas
        ],

        "properties": {
            "destinationContainerUrl":"https://podcastzhtw.blob.core.windows.net/transcription?sp=racwdl&st=2024-04-23T17:10:29Z&se=2024-05-30T01:10:29Z&spr=https&sv=2022-11-02&sr=c&sig=v3Rt%2B1v99%2F9KMNsoxkkWEf95V7g5o6eKCBTOt41Hqmw%3D",
            "wordLevelTimestampsEnabled": True,
            "displayFormWordLevelTimestampsEnabled":True,
            "timeToLive":"PT12H"
        },    
        "locale": "zh-TW",
        "displayName": text_name,
    }

    # 將字典轉換為 JSON 字串
    body_json = json.dumps(body_dict)

    params = urllib.parse.urlencode({
    })

    try:
        conn = http.client.HTTPSConnection(host)
        logging.info(f"success  {blob_name}")
        conn.request("POST", "/speechtotext/v3.2-preview.2/transcriptions", body_json, headers)
        response = conn.getresponse()
        data = response.read().decode("UTF-8")
        data_json = json.loads(data)
        logging.info(f"transcription respond {data_json}")
        conn.close()

   

    except Exception as e:
        print("[Errno {0}] {1}".format(e.errno, e.strerror))

@app.blob_trigger(arg_name="myblob", path="transcription",
                               connection="podcastzhtw_STORAGE") 
def blob_trigger2(myblob: func.InputStream):
    logging.info(f"Python blob trigger2 function processed blob"
                f"Name: {myblob.name}"
                f"Blob Size: {myblob.length} bytes")
    
    blob_name = myblob.name.split('/')[-1]
    logging.info(f"blob_name：{blob_name}")

    connect_str =os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    container_name = "transcription"

    blob_service_client = BlobServiceClient.from_connection_string(connect_str)
    container_client = blob_service_client.get_container_client(container_name)
    if "report" in blob_name:
        try:
            logging.info(f"Blob {blob_name} in container {container_name} has been deleted successfully as it contains 'report'.")
            return  
        except Exception as e:
            logging.error(f"Error deleting blob with 'report': {blob_name} {e}")
            return  

    if(blob_name == "contenturl_0.json"):
        try:
            blob_content = myblob.read().decode('utf-8')
            if blob_content:
                json_content = json.loads(blob_content)
                logging.info(f"JSON content: {json_content}")
            else:
                logging.error("Read empty content from blob.")
        except Exception as e:
            logging.error(f"Failed to read or parse blob content: {e}")
  
    try:
        source_url = json_content["source"]
        title_start = source_url.find("audiofiles/") + len("audiofiles/")
        title_end = source_url.find(".mp3")
        title_encoded = source_url[title_start:title_end]
        title_decoded = unquote(title_encoded)
        logging.info(f"Episode Title: {title_decoded}")
    except KeyError as e:
        logging.error(f"Key error when processing JSON content: {e}")
        raise

    try:
        transcript = json_content["combinedRecognizedPhrases"][0]["display"]
    except (KeyError, IndexError) as e:
        logging.error(f"Error extracting transcript: {e}")
        raise

    stop_words = get_stopwords('stopwords.txt')
    filtered_words = word_segmentation(transcript, stop_words)
    filtered_text = " ".join(filtered_words)
    text = filtered_text.encode('utf-8')

 
    try:
        container_name = "database" 
        container_client = blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(f"{title_decoded}.txt")

        blob_client.upload_blob(text, blob_type="BlockBlob", overwrite=True)      
        update_downloaded_status(blob_service_client, "podcasts",  title_decoded, "Succeeded", "")
        logging.info(f"Successfully uploaded {title_decoded}.txt to container {container_name}.")

    except Exception as e:
        logging.error(f"Failed to upload blob: {e}")
        raise
