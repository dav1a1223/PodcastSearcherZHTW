import azure.functions as func
import requests
from azure.storage.blob import BlobServiceClient, BlobBlock, BlobServiceClient, generate_container_sas, ContainerSasPermissions
import os
import json
import feedparser
from dateutil import parser
import base64
import logging
from azure.storage.queue import QueueClient, BinaryBase64EncodePolicy
from datetime import datetime
import azure.cognitiveservices.speech as speechsdk
import tempfile
from pydub import AudioSegment

import time
import base64
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta

AudioSegment.converter = "C:/ffmpeg/bin/ffmpeg" 


app = func.FunctionApp()
# 下載並轉換 url
def download_and_convert_audio(podcast_url):
    AudioSegment.converter = "C:/ffmpeg/bin/ffmpeg" 
    response = requests.get(podcast_url, stream=True)
    if response.status_code == 200:

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_mp3_file:
            for chunk in response.iter_content(chunk_size=1024):
                tmp_mp3_file.write(chunk)
          
            tmp_mp3_file_path = tmp_mp3_file.name

        # 使用 pydub 轉換 mp3 文件为 wav 格式
        sound = AudioSegment.from_mp3(tmp_mp3_file_path)
        sound = sound.set_frame_rate(16000).set_channels(1)
        tmp_wav_file_path = tmp_mp3_file_path.replace(".mp3", ".wav")
        sound.export(tmp_wav_file_path, format="wav")
        
        # 刪除臨時 MP3 文件
        os.unlink(tmp_mp3_file_path)
        
        return tmp_wav_file_path
    else:
        logging.warning(f"Failed to download audio. Status code: {response.status_code}, URL: {podcast_url}")
        return None

def speech_recognize_continuous_from_stream(audio_data, start_time):
    speech_config = speechsdk.SpeechConfig(subscription=os.getenv("SPEECH_KEY"), region=os.getenv("SPEECH_REGION"))
    logging.info(f"Temporary WAV file path: {audio_data}")
    speech_config.set_property(property_id=speechsdk.PropertyId.SpeechServiceConnection_LanguageIdMode, value='Continuous')
    auto_detect_source_language_config = speechsdk.languageconfig.AutoDetectSourceLanguageConfig(languages=["zh-TW"])
    audio_config = speechsdk.audio.AudioConfig(filename=audio_data)
    speech_recognizer = speechsdk.SpeechRecognizer(
    speech_config=speech_config, 
    auto_detect_source_language_config=auto_detect_source_language_config,
    audio_config=audio_config)
    all_results = []

    done = False

    def stop_cb(evt):
        print('CLOSING on {}'.format(evt))
        nonlocal done
        done = True
    def handle_final_result(evt):
        offset = evt.result.offset / 10000000  # 將100納秒轉換為秒
        # 加上片段的開始時間
        adjusted_start_time = start_time + offset

        # 格式化時間為【時:分:秒】
        start_time_formatted = str(timedelta(seconds=adjusted_start_time))[:-7]
        
        text_with_time = f"[{start_time_formatted}] {evt.result.text}"
        all_results.append(text_with_time)

    # Connect callbacks to the events fired by the speech recognizer
    speech_recognizer.recognizing.connect(lambda evt: print('RECOGNIZING: {}'.format(evt)))
    speech_recognizer.recognized.connect(lambda evt: print('RECOGNIZED: {}'.format(evt)))
    speech_recognizer.session_started.connect(lambda evt: print('SESSION STARTED: {}'.format(evt)))
    speech_recognizer.session_stopped.connect(lambda evt: print('SESSION STOPPED {}'.format(evt)))
    speech_recognizer.canceled.connect(lambda evt: print('CANCELED {}'.format(evt)))
    speech_recognizer.recognized.connect(handle_final_result)

    # stop continuous recognition on either session stopped or canceled events
    speech_recognizer.session_stopped.connect(stop_cb)
    speech_recognizer.canceled.connect(stop_cb)

    # Start continuous speech recognition
    speech_recognizer.start_continuous_recognition()
    while not done:
        time.sleep(.5)

    speech_recognizer.stop_continuous_recognition()

    logging.info(all_results)
    return all_results

def split_audio(audio_path):
    chunk_length_ms=60000
    audio = AudioSegment.from_file(audio_path)
    chunks = math.ceil(len(audio) / chunk_length_ms)
    
    for i in range(chunks):
        start_ms = i * chunk_length_ms
        start_time = start_ms / 1000.0  # 轉換為秒
        end_ms = start_ms + chunk_length_ms
        chunk_data = audio[start_ms:end_ms]
        chunk_filename = f"chunk_{i}.wav"
        chunk_data.export(chunk_filename, format="wav")
        yield start_time, chunk_filename

def flatten_results(nested_results):
    flat_list = []
    for sublist in nested_results:
        if sublist is not None:  # 確保子列表不是 None
            for item in sublist:
                flat_list.append(item)
    return flat_list
def transcribe_concurrently(audio_chunks):
    with ThreadPoolExecutor(max_workers=len(audio_chunks)) as executor:
        future_to_chunk_info = {
            executor.submit(speech_recognize_continuous_from_stream, chunk, start_time): (start_time, chunk) 
            for start_time, chunk in audio_chunks
        }
          # 初始化一個列表來保存結果，長度與 audio_chunks_with_times 相同，並填充 None
        ordered_results = [None] * len(audio_chunks)

        for future in as_completed(future_to_chunk_info):
            start_time, chunk = future_to_chunk_info[future]  # 從字典中獲取片段和其開始時間
            try:
                result = future.result()
                # 確定片段在原始列表中的索引，並將結果放在正確的位置
                index = audio_chunks.index((start_time, chunk))
                ordered_results[index] = result
            except Exception as exc:
                logging.error(f'Chunk {chunk} generated an exception: {exc}')
            finally:
                # 處理完畢後，刪除該音頻片段文件
                os.remove(chunk)
                print(f"Deleted chunk file: {chunk}")
    flattened_results = flatten_results(ordered_results)
    return flattened_results

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

def upload_text_to_blob(container_name, text_blob_name, text, connection_string):
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client(container_name)
    blob_client = container_client.get_blob_client(blob=text_blob_name)
    if text:  # 確保文本不是空的
            text_bytes = text.encode('utf-8')
            blob_client.upload_blob(text_bytes, overwrite=True)
            logging.info(f"Text uploaded to Blob Storage with name: {text_blob_name}")
    else:
            logging.warning(f"Attempted to upload empty text to Blob Storage with name: {text_blob_name}")

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
            if download_status[rss_url]["guid"] != latest_episode_guid:    \
                # 只下載最新的一集
                podcast_url = feed.entries[0].enclosures[0]["href"]
                blob_name = f"{prefix}[{parser.parse(feed.entries[0].published).strftime('%Y%m%d')}] {feed.entries[0].title}.mp3" 
                text_blob_name = f"{prefix}[{parser.parse(feed.entries[0].published).strftime('%Y%m%d')}] {feed.entries[0].title}.txt" 
                logging.info(f"Downloading {podcast_url} to {blob_name}...")
                if latest_episode_guid:
                    # 更新下载狀態
                    download_status[rss_url] = {
                        "last_downloaded": str(datetime.now()),
                        "guid": latest_episode_guid
                     }
                    # 更新狀態
                    #update_downloaded_status(blob_service_client, container_name, download_status)
                    #upload_rss_entity_to_blob(connection_string, "audiofiles", blob_name, podcast_url)
                    
                    tmp_wav_file_path = download_and_convert_audio(podcast_url)

                    if tmp_wav_file_path:
                        audio_chunks = list(split_audio(tmp_wav_file_path))
                        results = transcribe_concurrently(audio_chunks)
                        text_to_upload = "\n".join(results)
                        logging.info(text_to_upload)
                        upload_text_to_blob(container_name, text_blob_name, text_to_upload, connection_string)
                        os.unlink(tmp_wav_file_path)
                    continue
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
                    
                    upload_rss_entity_to_blob(connection_string, container_name, blob_name, podcast_url)
                  
                    logging.info(f"Uploaded {blob_name} to Azure Blob Storage.")
                else:
                    logging.info(f"Skipping {blob_name} because it is not a valid podcast.") 
                    print(f"Successfully uploaded '{blob_name}' to Azure Blob Storage in chunks.")
            except Exception as e:
                 print(f"Failed to download and upload in chunks. Error: {e}")



