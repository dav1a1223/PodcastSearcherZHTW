import azure.functions as func
import requests
from azure.storage.blob import BlobServiceClient, BlobBlock, BlobServiceClient, BlobSasPermissions, generate_blob_sas
from azure.cosmos import CosmosClient
import collections
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
import re
import time
import http.client
import base64
import urllib.request
import urllib.parse
import urllib.error


app = func.FunctionApp()

# 下載並轉換 url
def upload_rss_entity_to_blob(connection_string, container_name, blob_name, podcast_url):
    logging.info(f"Starting upload for {blob_name}")
    try:
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob=blob_name)

        response = requests.get(podcast_url, stream=True)
        if response.status_code == 200:
            logging.info(f"Starting to download {podcast_url}")
            block_list = []
            index = 0
            for chunk in response.iter_content(chunk_size=4 * 1024 * 1024):
                if chunk:
                    block_id = base64.b64encode(f"block-{index}".encode()).decode()
                    blob_client.stage_block(block_id, chunk)
                    block_list.append(BlobBlock(block_id))
                    index += 1
            blob_client.commit_block_list(block_list)
            queue_client = QueueClient.from_connection_string(connection_string, queue_name="blob-queue")         
            queue_client.message_encode_policy = BinaryBase64EncodePolicy()
            message = {"blob_name": blob_name, "container_name": container_name}
            logging.info(f"Sending message to queue for {blob_name}")
            message_bytes = json.dumps(message).encode('utf-8')
            encoded_message = base64.b64encode(message_bytes).decode('utf-8')
            queue_client.send_message(encoded_message)
            logging.info(f"Message sent to queue for {blob_name}")
    
        else:
            logging.error(f"Failed to download podcast from URL '{podcast_url}'. HTTP status code: {response.status_code}")
    except Exception as e:
        logging.error(f"Failed to upload '{blob_name}' to Azure Blob Storage. Error: {e}")

def get_downloaded_status(connection_string, container_name, prefix):
    try:
        blob_name = f"{prefix}.json"
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob=blob_name)
        download_status = {}
        download_status_json = blob_client.download_blob().readall()
        if not download_status_json:
            logging.info(f"Status file {blob_name} is empty.")

        else:
            download_status = json.loads(download_status_json)
            logging.info(f"download_status successed")
 
    except Exception as e:
        logging.error(f"Failed to download or parse the status file {blob_name}: {e}")

    return download_status
    
    
def update_downloaded_status(connection_string, container_name, title, new_status, latest_guid):
    try:
        blob_name = f"{extract_prefix(title)}.json"
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_name)
        download_status_json = blob_client.download_blob().readall()
        title = extract_title(title).replace('.mp3', '')
        logging.info(f"remove_mp3 title：{title}")
        try:
            current_status = json.loads(download_status_json)
        except Exception as e:
            logging.error(f"Failed to download existing status file {blob_name}: {e}")
            raise

        if title not in current_status:
            current_status['latest_guid'] = latest_guid
            current_status[title] = {'guid': latest_guid, 'status': new_status}
            logging.info(f"Added new title {title} with status {new_status}.")
        else:
            current_status[title]['status'] = new_status

        blob_client.upload_blob(json.dumps(current_status, ensure_ascii=False, indent=4), overwrite=True)
       
        logging.info(f"Successfully updated the status for episode {title} to {new_status} in {blob_name}.")
    except Exception as e:
        logging.error(f"Failed to update the download status in Blob Storage for {blob_name}: {e}")
        raise
        
def check_not_downloaded_episodes(status, entries):
    download_entry = []
    for entry in entries:
        try:
            entry_status = status[entry.title]['status']
            logging.info(f"Checking status for {entry.title}: {entry_status}")
            if entry_status == 'not_downloaded':
                download_entry.append(entry)
        except KeyError as e:
            logging.error(f"Error accessing status for {entry.title}: {e}")
        except Exception as e:
            logging.error(f"Unexpected error while checking entries: {e}")

    return download_entry


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

def update_keyword(keyword, document_id, frequency, container):
    # Query to check if the keyword exists
    query = "SELECT * FROM c WHERE c.id = @keyword"
    items = list(container.query_items(
        query=query,
        parameters=[
            {"name": "@keyword", "value": keyword}
        ],
        enable_cross_partition_query=True
    ))

    if items:
        item = items[0]
        documents = item['documents']
        documents.append({
            "document_id": document_id,
            "freq": frequency
        })
        # Replace the item in the database
        container.replace_item(item, item)
    else:
        # Keyword does not exist, create new item
        new_item = {
            "id": keyword,
            "keyword": keyword,
            "documents": [{
                "document_id": document_id,
                "freq": frequency
            }]
        }
        container.create_item(body=new_item)

def read_and_match_urls(feed_url, title):
    feed = feedparser.parse(feed_url)
    title_to_url = {(entry.title): entry.enclosures[0]['href'] for entry in feed.entries if entry.enclosures}

    if title in title_to_url:
        return title_to_url[title]
    else:
        logging.info(f"{title}：URL not found")
        return "URL not found"

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
    seg_list = jieba.lcut_for_search(text)
    filtered_seg_list = [word for word in seg_list if word not in stopwords and word.strip()]
    return filtered_seg_list

def extract_prefix(blob_name):

    start = blob_name.find('【') + 1 
    end = blob_name.find('】')      

    if start > 0 and end > start:
        return blob_name[start:end]  
    else:
        return ""
    
def extract_title(full_title):
    match = re.search(r'】\s+(.+)$', full_title)
    logging.info(f"title：{full_title}")
    logging.info(f"match：{match}")
    if match:
        return match.group(1)
    else:
        return "No title found"
    
def sanitize_filename(filename):
    sanitized = re.sub(r'[\<\>:"/\\|?*]', '', filename)
    sanitized = re.sub(r'[./\\]+$', '', sanitized)
    return sanitized

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
        blob_name_prefix = extract_prefix(prefix)
        container_client = blob_service_client.get_container_client(container_name)
        download_status = get_downloaded_status(connection_string, container_name, blob_name_prefix)
        logging.info(download_status)
        if not download_status: 
            episodes_batches = feed.entries
        else: # 第一次下載這
            latest_guid = feed.entries[0].get("guid")
            logging.info(latest_guid)
               
                # 只下載最新的一集
            blob_name = f"{prefix} {feed.entries[0].title}.mp3" 
            blob_name  = sanitize_filename(blob_name)
            if download_status["latest_guid"] != latest_guid: 
                logging.info("update_downloaded_status")
                update_downloaded_status(connection_string, container_name, blob_name, "not_downloaded", latest_guid)
            time.sleep(2)
            episodes_batches = check_not_downloaded_episodes(download_status, feed.entries)
            logging.info(f"not_downloaded Episodes batches to process: {len(episodes_batches)}")

        logging.info(f"Episodes batches to process: {len(episodes_batches)}")
        if(len(episodes_batches)) > 10:
            logging.info(f"Episodes batches to process: {len(episodes_batches)}")
            return
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
            blob_name = f"{prefix} {entry.title}.mp3" 
            blob_name  = sanitize_filename(blob_name)
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



@app.queue_trigger(arg_name="myqueue", queue_name="blob-queue",
                               connection="podcastzhtw") 
def queue_trigger2(myqueue: func.QueueMessage):
    message = json.loads(myqueue.get_body().decode('utf-8'))
    blob_name = message['blob_name']
    container_name = message['container_name']
    connect_str =os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    download_status = get_downloaded_status(connect_str, "podcasts", extract_prefix(blob_name))
    if blob_name.endswith('.mp3'):
        entry_name = blob_name.rsplit('.', 1)[0]
    entry_name = sanitize_filename(entry_name)
    extracted_name = extract_title(entry_name)
    logging.info(f"status：{download_status[extracted_name].get('status')}")
    if  extracted_name in download_status and download_status[extract_title(entry_name)].get('status') == 'Succeeded':
            logging(f"Status for '{title}' is 'Succeeded'. No further action required queue.")
            return
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
    logging.info(extracted_name)
    
    blob_url_with_sas = generate_sas_url(account_name, account_key, container_name, blob_name)



    text_name = blob_name.rsplit('.', 1)[0] 
    body_dict = {
        "contentUrls": [
        blob_url_with_sas
        ],

        "properties": {
            "destinationContainerUrl":"https://podcastzhtw.blob.core.windows.net/transcription?sp=racwdl&st=2024-04-25T01:26:52Z&se=2024-05-30T09:26:52Z&spr=https&sv=2022-11-02&sr=c&sig=LuzEwdBRDFzjCa5M4GCcHZH1CwpLgCMfYJirCo%2BsWcg%3D",
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
        logging.info("[Errno {0}] {1}".format(e.errno, e.strerror))

@app.blob_trigger(arg_name="myblob", path="transcription",
                               connection="podcastzhtw_STORAGE") 
def blob_trigger(myblob: func.InputStream):
    logging.info(f"Python blob trigger function processed blob"
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

    if "contenturl" in blob_name:
        try:
            blob_content = myblob.read().decode("UTF-8")
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
        logging.info(f"Decoded title: '{title_decoded}'")
        download_status = get_downloaded_status(connect_str, "podcasts", extract_prefix(title_decoded))
        extracted_title = extract_title(title_decoded)
        extracted_title = sanitize_filename(extracted_title)
        logging.info(f"Checking status for extracted title: {extracted_title}")
        if extracted_title in download_status:
            logging.info(f"Status for '{extracted_title}': {download_status[extracted_title].get('status')}")
        else:
            logging.warning(f"Extracted title '{extracted_title}' not found in download_status")
        
        if extracted_title in download_status:
            status = download_status[extracted_title].get('status')
            logging.info(f"Status for {extracted_title}: {status}")
            
            if status == 'Succeeded':
                logging.info(f"Status for '{extracted_title}' is 'Succeeded'. No further action required.")
                return 
        else:
            logging.warning(f"Extracted title '{extracted_title}' not found in download_status")

    except KeyError as e:
        logging.error(f"Key error when processing JSON content: {e}")
        raise

    try:
        transcript = json_content["combinedRecognizedPhrases"][0]["display"]
        logging.info(f"transcript：{transcript}")
        full_transcript = ' '.join([extracted_title, transcript])
        logging.info(f"full_transcript：{full_transcript}")
    except (KeyError, IndexError) as e:
        logging.error(f"Error extracting transcript: {e}")
        raise

    stop_words = get_stopwords('stopwords.txt')
    filtered_words = word_segmentation(full_transcript, stop_words)
    length = len(filtered_words)
    logging.info(f"Segmented and filtered words. Total words: {len(filtered_words)}")

    try:
        connection_string = os.getenv("COSMOS_DB_CONNECTION_STRING")
        client = CosmosClient.from_connection_string(connection_string)
        database_name = 'Score'
        container_word = client.get_database_client(database_name).get_container_client('bm25-score')  
        container_doc = client.get_database_client(database_name).get_container_client('documents')

        logging.info(f"Reading RSS feed URL: {rss_feeds[0]['url']}")
        url = read_and_match_urls(rss_feeds[0]["url"], extract_title(title_decoded)) 
        item_response = container_doc.read_item(item="whole", partition_key="whole")
        whole_item = item_response
        logging.info(f"Retrieved document: {whole_item}")

        total_documents = whole_item['total'] + 1
        new_avgdl = ((whole_item['avgdl'] * whole_item['total']) + length) / total_documents

        whole_item['total'] = total_documents
        whole_item['avgdl'] = new_avgdl
        logging.info(f" total_documents：{total_documents}")
        container_doc.replace_item(item=whole_item['id'], body=whole_item)

        new_item = {
                "id": extracted_title,
                "doc_id": extracted_title,
                "length": length,
                "url": url,
        }     
        container_doc.create_item(body=new_item)
        
        word_freq = collections.Counter(filtered_words)
        logging.info("Counting word frequency.")
        for word, freq in word_freq.items():
            update_keyword(word, extracted_title, freq, container_word)

        update_downloaded_status(connect_str, "podcasts",  extracted_title , "Succeeded", "")
        logging.info(f"Successfully uploaded {extracted_title}.txt to container {container_name}.")

    except Exception as e:
        logging.error(f"Failed to upload blob: {e}")
        raise