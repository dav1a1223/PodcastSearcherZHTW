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
    jieba.set_dictionary('dict.txt.big.txt')
    seg_list = jieba.lcut(text)
    
    filtered_seg_list = [word for word in seg_list if word not in stopwords and word.strip()]
    
    return filtered_seg_list

def process_files(folder_path, stopwords_file):
    # 加载停用词
    stopwords = get_stopwords(stopwords_file)

    # 遍历文件夹中的所有txt文件
    for filename in os.listdir(folder_path):
        if filename.endswith('.txt'):
            file_path = os.path.join(folder_path, filename)
            # 读取文件、处理内容、写回文件
            with open(file_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()

            with open(file_path, 'w', encoding='utf-8') as file:
                for line in lines:
                    line = line.strip()
                    if line:
                        line = line.upper()
                        seg_list = word_segmentation(line, stopwords)
                        file.write(f"{' '.join(seg_list)}\n")


process_files(r'C:\Users\USER\Podcast_Search\algorithm_test\transcrips', 'stopwords.txt')