import jieba

class TextProcessor:
    def __init__(self, stopwords_file="stopwords.txt"):
        self.stopwords = self.get_stopwords(stopwords_file)

    def get_transcript(self, file):
        with open(file, 'r', encoding='utf-8') as f:
            text = f.read()
        return text

    def get_stopwords(self, file):
        stopword_list = []
        with open(file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                stopword_list.append(line)
        return stopword_list

    def word_segmentation(self, text, need_remove_stopwords):
        seg_list = jieba.lcut(text)
        filtered_seg_list = []
        if need_remove_stopwords:
            for word in seg_list:
                if word not in self.stopwords:
                    if word.strip():
                        filtered_seg_list.append(word)
            return filtered_seg_list
        else:
            return seg_list

    




