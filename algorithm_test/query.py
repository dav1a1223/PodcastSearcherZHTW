import json
import jieba
import re
class TextProcessor:
    def __init__(self, stopwords_file="stopwords.txt"):
        self.stopwords = self.get_stopwords(stopwords_file)

    def get_stopwords(self, file):
        stopword_list = []
        with open(file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                stopword_list.append(line)
        return stopword_list

    def word_segmentation(self, text, need_remove_stopwords=True):
        seg_list = jieba.lcut(text)
        if need_remove_stopwords:
            seg_list = [word for word in seg_list if word not in self.stopwords and word.strip()]
        return seg_list
    
def generate_results_json(queries, processor, top_ns):

    results = {
        "tf-idf": [],
        "bm25": []
    }
    
    with open('bm25.json', 'r', encoding='utf-8') as f:
            bm25_data = json.load(f)
    
    with open('tf_idf.json', 'r', encoding='utf-8') as f:
            tf_idf_data = json.load(f)
    # 循环处理每个查询
    queries = [
    {"type": "transcripts", "data": queries['transcripts']},
    {"type": "timecode", "data": queries['timecode']},
    {"type": "dcard", "data": queries['dcard']}
]
    for query in queries:
        tf_idf_results = {}
        bm25_results = {}
        query_type = query["type"]
        query_data = query["data"]
        query_name = query_type  

        for top_n in top_ns:
            print(f"Processing {query_type} for top {top_n}")
            tf_idf_accuracy = calculate_accuracy(tf_idf_data, query_data, query_tf_idf_document, processor, top_n)
            bm25_accuracy = calculate_accuracy(bm25_data, query_data, query_bm25_document, processor, top_n)
            tf_idf_results[f"P{top_n}"] = tf_idf_accuracy
            bm25_results[f"P{top_n}"] = bm25_accuracy

        results["tf-idf"].append({
            "query": query_name,
            **tf_idf_results
        })
        results["bm25"].append({
            "query": query_name,
            **bm25_results
        })

    save_accuracies_to_json(results)

def extract_ep_numbers(document_ids):
    pattern = r"EP(\d+)"
    extracted_numbers = [re.search(pattern, doc_id).group(1) if re.search(pattern, doc_id) else None for doc_id in document_ids]
    return extracted_numbers
    
def load_query_data(file_path):
    queries = []
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            parts = line.strip().split('\t')
            if len(parts) == 2:
                queries.append((eval(parts[0]), parts[1]))  
    return queries

def calculate_accuracy(data, queries, query_function, processor, top_n):
    correct_predictions = 0
    for query_terms, correct_doc_id in queries:
        predicted_doc_ids = query_function(data, processor, ' '.join(query_terms), top_n=top_n)
        if predicted_doc_ids is None:
            cleaned_predicted_doc_ids = []
        else:
            cleaned_predicted_doc_ids = extract_ep_numbers(predicted_doc_ids)
        if correct_doc_id in cleaned_predicted_doc_ids:
            correct_predictions += 1
    
    accuracy = correct_predictions / len(queries)
    print(f"Top {top_n} accuracy: {accuracy}")
    return accuracy



def query_tf_idf_document(data, processor, sentence, top_n):
    terms = processor.word_segmentation(sentence)
    tf_idf_data  = data

    doc_scores_sum = {}
    query_results = {}

    for term in terms:
        if term in tf_idf_data:
            scores = tf_idf_data[term]['scores']
            query_results[term] = scores  
            for score_info in scores:
                doc_id = score_info['document_id']
                score = float(score_info['score'])
                if doc_id in doc_scores_sum:
                    doc_scores_sum[doc_id] += score
                else:
                    doc_scores_sum[doc_id] = score
    #print("該 term 的各文檔分數：")
    #print(json.dumps(query_results, ensure_ascii=False, indent=4))
    top_docs = sorted(doc_scores_sum.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return [doc[0] for doc in top_docs]


def query_tf_idf_document_all_terms(processor, sentence, top_n):
    terms = processor.word_segmentation(sentence)
    try:
        with open('tf_idf.json', 'r', encoding='utf-8') as f:
            tf_idf_data = json.load(f)
    except FileNotFoundError:
        print("未找到tf-idf.json文件。")
        return None

    doc_scores_sum = {}
    term_count = {}
    query_results = {}

    for term in terms:
        if term in tf_idf_data:
            scores = tf_idf_data[term]['scores']
            query_results[term] = scores
            for score_info in scores:
                doc_id = score_info['document_id']
                score = float(score_info['score'])
                if doc_id in doc_scores_sum:
                    doc_scores_sum[doc_id] += score
                    term_count[doc_id] += 1  
                else:
                    doc_scores_sum[doc_id] = score
                    term_count[doc_id] = 1

   
    top_docs = sorted(term_count.keys(), key=lambda x: (-term_count[x], -doc_scores_sum[x]))
    #print("该 term 的各文檔分數：")
    #print(json.dumps(query_results, ensure_ascii=False, indent=4))
    return [doc[0] for doc in top_docs]


def query_bm25_document(data, processor, sentence, top_n):
    terms = processor.word_segmentation(sentence)
    

    
    doc_scores_sum = {}
    query_results = {}

    for term in terms:
        if term in data:
            scores = data[term]['scores']
            query_results[term] = scores
            for score_info in scores:
                doc_id = score_info['document_id']
                score = float(score_info['score'])
                if doc_id in doc_scores_sum:
                    doc_scores_sum[doc_id] += score
                else:
                    doc_scores_sum[doc_id] = score
    
    top_docs = sorted(doc_scores_sum.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return [doc[0] for doc in top_docs]

try:
    with open('bm25.json', 'r', encoding='utf-8') as f:
        bm25_data = json.load(f)
except FileNotFoundError:
    print("未找到bm25.json文件。")

def save_accuracies_to_json(accuracies, filename="precision.json"):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(accuracies, f, ensure_ascii=False, indent=4)

processor = TextProcessor("stopwords.txt")
#user_input = input("請輸入想要查詢的句子：")
#terms = processor.word_segmentation(user_input)
#print("處理後的 query：", terms)
queries = load_query_data("transcripts.txt")
queries = {
    "transcripts": load_query_data("transcripts.txt"),
    "timecode": load_query_data("timecode.txt"),
    "dcard": load_query_data("dcard.txt")
}
top_ns = [1, 3, 5]

# 生成和保存结果
generate_results_json(queries, processor, top_ns)