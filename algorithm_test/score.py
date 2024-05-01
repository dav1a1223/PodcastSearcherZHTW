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
    
    def calculate_tfidf(self, file_path='tf_idf.json'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    tfidf_scores = json.load(f)
            except FileNotFoundError:
                tfidf_scores = {}

            # Calculate document frequency (DF) for each word
            df = Counter()
            for document in self.documents:
                words = document.split()
                unique_words = set(words)
                for word in unique_words:
                    df[word] += 1

            N = len(self.documents)

            # Calculate inverse document frequency (IDF) for each word
            idf = {word: math.log((N / df[word]), 10) for word in df}

            # Initialize data structure
            word_scores = {word: {"scores": [], "highest": {"document_id": "", "score": 0}} for word in df}

            # Calculate and store TF-IDF scores for each document
            for doc_id, document in zip(self.document_ids, self.documents):
                words = document.split()
                term_freq = Counter(words)
                doc_scores = {}

                for word, freq in term_freq.items():
                    tf = freq / len(words)  # Calculate term frequency (TF)
                    tf_idf_value = tf * idf[word]  # Calculate TF-IDF
                    score_formatted = format(tf_idf_value, '.4f')  # Format TF-IDF value
                    doc_scores[word] = score_formatted  # Store formatted TF-IDF value

                    # Store in word_scores and check if it's the highest score
                    score_entry = {"document_id": doc_id, "score": score_formatted}
                    word_scores[word]["scores"].append(score_entry)
                    if float(score_formatted) > float(word_scores[word]["highest"]["score"]):
                        word_scores[word]["highest"] = score_entry

            # Save the calculated TF-IDF scores
            self.save_tf_idf(word_scores, file_path)

    def save_tf_idf(self, tfidf, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except FileNotFoundError:
            existing_data = {}

        existing_data.update(tfidf)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=4)

    def calculate_bm25(self, k1=1.25, b=0.75, file_path='bm25.json'):
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
        idf = {word: math.log((N + 1) / (df[word] + 0.5)) for word in df}

        # Calculate BM25 scores for each document
        for doc_id, document in zip(self.document_ids, self.documents):
            doc_length = doc_lengths[doc_id]
            freqs = Counter(document.split())

            for word, freq in freqs.items():
                if word not in bm25_scores:
                    bm25_scores[word] = {"scores": [], "highest": {"document_id": "", "score": 0.0}}

                if word in idf:
                    score = idf[word] * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * doc_length / avgdl))
                    score_formatted = format(score, '.4f')

                    score_entry = {"document_id": doc_id, "freq": freq, "score": score_formatted}
                    existing_entry = next((item for item in bm25_scores[word]["scores"] if item["document_id"] == doc_id), None)
                    if existing_entry:
                        existing_entry['score'] = score_formatted  # Update score
                        existing_entry['freq'] = freq  # Update frequency
                    else:
                        bm25_scores[word]["scores"].append(score_entry)  # Append new entry


                    if float(score_formatted) > float(bm25_scores[word]["highest"]["score"]):
                        bm25_scores[word]["highest"] = score_entry

        # Save the calculated BM25 scores
        self.save_bm25_scores(bm25_scores, file_path)


    def save_bm25_scores(self, bm25_scores, file_path='bm25.json'):
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(bm25_scores, f, ensure_ascii=False, indent=4)


processor = TextProcessor()
processor.process_folder("transcrips") 
processor.calculate_tfidf()
print("tf-idf 分析结果已保存至 tf-idf.json。")
processor.calculate_bm25()
print("bm25 分析结果已保存至 bm25.json。")


