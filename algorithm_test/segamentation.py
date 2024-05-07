import jieba
import os
def get_stopwords(file):
    stopword_list = []
    with open(file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            stopword_list.append(line)
    return stopword_list
def word_segmentation(text, stopwords):
    print(text)
   
    seg_list = jieba.lcut_for_search(text)
    print(seg_list)
    seg_list = [word for word in seg_list if word not in stopwords and word.strip()]
    return seg_list

def process_files(folder_path, stopwords_file):
    # 加载停用词
    stopwords = get_stopwords(stopwords_file)
    jieba.set_dictionary('dict.txt.big.txt')
    
    # 遍历文件夹中的所有txt文件
    filename = "EP130 你這個騙子嗚嗚嗚嗚嗚嗚嗚嗚嗚嗚嗚嗚嗚嗚嗚嗚嗚.txt"
    if filename.endswith('.txt'):
        file_path = os.path.join(folder_path, filename)
        # 读取文件、处理内容、写回文件
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        with open(file_path, 'w', encoding='utf-8') as file:
            for line in lines:
                line = line.strip().upper()  # 先去除空白，转大写
                if line:
                    seg_list = word_segmentation(line, stopwords)
                    file.write(f"{' '.join(seg_list)}\n")  # 词与词之间加空格


process_files(r'C:\Users\USER\Podcast_Search\algorithm_test\transcrips', 'stopwords.txt')