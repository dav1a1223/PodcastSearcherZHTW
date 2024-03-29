import jieba

''' Input: (str text, bool needRemoveStopwords), Output: list of string 
    
    Case study with 1 podcast transcript and 5 user queries (Dcard)
'''

def get_transcript(file):
    with open(file, 'r', encoding='utf-8') as f:
        text = f.read()
    return text

def get_stopword(file):
    stopword_list = []
    with open(file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            stopword_list.append(line)
    return stopword_list

       
def word_segmentation(text, needRemoveStopwords):
    seg_list = jieba.lcut(text)
    filtered_seg_list = []
    if needRemoveStopwords == True:
        stopword_list = get_stopword("stopwords.txt")
        # print(stopword_list)
        for word in seg_list:
            if word not in stopword_list :
                if word != ' ':
                    filtered_seg_list.append(word)
        # print(filtered_seg_list)
        print(len(seg_list))
    else:
        print(seg_list)


textfile='【好味小姐】[20230626] EP167 我小時候的第一個記憶....txt'
text = get_transcript(textfile)

word_segmentation(text, True)