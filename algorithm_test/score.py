import jieba
import os
from sklearn.feature_extraction.text import TfidfVectorizer
import json
from collections import Counter
import math
import numpy as np
from collections import defaultdict
import math

class TextProcessor:
    def __init__(self):
        self.documents = []
        self.document_ids = []

    def process_folder(self, folder_path):
        output_folder_path = os.path.join(os.getcwd(), 'transcrips')
        os.makedirs(output_folder_path, exist_ok=True)
        
        for filename in os.listdir(folder_path):
            if filename.endswith(".txt"):
                full_path = os.path.join(folder_path, filename)
                text = self.get_transcript(full_path)
                self.documents.append(text)
                self.document_ids.append(filename)

    def get_transcript(self, file):
        with open(file, 'r', encoding='utf-8') as f:
            text = f.read()
        return text
    
    def calculate_tfidf(self):
    # Tokenize documents
        tokenized_docs = [doc.split() for doc in self.documents]

        # Compute term frequency (TF) for each term in each document
        tf = []
        for doc in tokenized_docs:
            tf_doc = defaultdict(int)
            for term in doc:
                tf_doc[term] += 1
            tf.append(tf_doc)

        # Compute document frequency (DF) for each term
        df = defaultdict(int)
        for doc in tf:
            for term in doc:
                df[term] += 1

        # Compute inverse document frequency (IDF) for each term
        num_docs = len(tokenized_docs)
        idf = {term: math.log(num_docs / (df[term] + 1)) for term in df}

        # Compute TF-IDF scores
        tfidf = {}
        for i, doc in enumerate(tokenized_docs):
            doc_scores = []
            highest_score = {"document_id": "", "score": 0.0}
            for term in doc:
                score = tf[i][term] * idf[term]
                doc_scores.append({
                    "document_id": self.document_ids[i],
                    "score": format(score, '.4f')
                })
                if score > highest_score["score"]:
                    highest_score = {
                        "document_id": self.document_ids[i],
                        "score": score  
                    }
            for term in doc:  # 使用每個 term 作為鍵存儲 TF-IDF 分數
                if doc_scores:
                    if term not in tfidf:
                        tfidf[term] = {
                            "scores": doc_scores,
                            "highest": {
                                "document_id": highest_score["document_id"],
                                "score": format(highest_score["score"], '.4f') 
                            }
                        }
                    else:
                        tfidf[term]["scores"].extend(doc_scores)
                        if highest_score["score"] > float(tfidf[term]["highest"]["score"]):
                            tfidf[term]["highest"]["document_id"] = highest_score["document_id"]
                            tfidf[term]["highest"]["score"] = format(highest_score["score"], '.4f')
        self.save_tf_idf(tfidf)
        return tfidf


    def save_tf_idf(self, tfidf, file_path='tfidf.json'):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except FileNotFoundError:
            existing_data = {}

        existing_data.update(tfidf)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=4)
    def calculate_bm25(self, k1=1.25, b=0.75, file_path='bm25.json'):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                bm25_scores = json.load(f)
        except FileNotFoundError:
            bm25_scores = {}

        # Calculate document lengths and average document length
        doc_lengths = {doc_id: len(doc.split()) for doc_id, doc in zip(self.document_ids, self.documents)}
        avgdl = sum(doc_lengths.values()) / len(self.documents)
        N = len(self.documents)

        # Calculate document frequency (DF) for each word
        df = Counter()
        for document in self.documents:
            for word in set(document.split()):
                df[word] += 1

        # Calculate inverse document frequency (IDF) for each word
        idf = {word: math.log((N - df[word] + 0.5) / (df[word] + 0.5)) for word in df}

        # Calculate BM25 scores for each document
        for doc_id, document in zip(self.document_ids, self.documents):
            if doc_id in bm25_scores:
                doc_length = float(bm25_scores[doc_id])
                scores = bm25_scores[doc_id].get('scores', [])
                freqs = {item['word']: item['freq'] for item in scores if 'freq' in item and 'word' in item}
            else:
                doc_length = len(document.split())
                freqs = Counter(document.split())
                bm25_scores[doc_id] = doc_length 
           

            for word, freq in freqs.items():
                if word not in bm25_scores:
                    bm25_scores[word] = {"scores": [], "highest": {"document_id": "", "score": 0.0}}

                if word in idf:
                    score = idf[word] * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * doc_length / avgdl))
                    score_formatted = format(score, '.4f')

                    bm25_scores[word]["scores"].append({"document_id": doc_id, "freq": freq, "score": score_formatted})

                    if float(score_formatted) > float(bm25_scores[word]["highest"]["score"]):
                        bm25_scores[word]["highest"] = {"document_id": doc_id, "score": score_formatted}

        # Save the calculated BM25 scores
        self.save_bm25_scores(bm25_scores, file_path)

    def save_bm25_scores(self, bm25_scores, file_path='bm25.json'):
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(bm25_scores, f, ensure_ascii=False, indent=4)


processor = TextProcessor()
processor.process_folder("transcrips") 

print("tf-idf 分析结果已保存至 tf-idf.json。")
processor.calculate_bm25()


