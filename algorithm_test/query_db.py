from azure.cosmos import CosmosClient, exceptions
import json
import math
import pandas as pd
import os
import jieba

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

def batch_query_cosmos_db(terms, container):
    quoted_words = [f"'{word}'" for word in terms]  

    formatted_terms = ", ".join(quoted_words) 
    query = f"SELECT VALUE c FROM c WHERE c.keyword IN ({formatted_terms})" 
    
    print(f"Querying with terms: {formatted_terms}")  
    
    try:
        items = list(container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        return items
    except exceptions.CosmosHttpResponseError as e:
        print(f"Error querying Cosmos DB: {str(e)}")
        return []

def batch_fetch_document(doc_ids, length_container):
    quoted_words = [f"'{word}'" for word in doc_ids] 

    formatted_docs = ", ".join(quoted_words)
    query = f"SELECT c.doc_id, c.length, c.url FROM c WHERE c.doc_id IN ({formatted_docs})"
    query_N = "SELECT c.total, c.avgdl FROM c WHERE c.doc_id = 'whole'"
    try:
        items = list(length_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        items_N = list(length_container.query_items(
            query=query_N,
            enable_cross_partition_query=True
        ))

        docs_details = {}
        for item in items:
            docs_details[item['doc_id']] = {
                'length': item['length'],
                'url': item['url']
            }
        print(docs_details)
        if items_N:
            total_value = items_N[0]['total'] if 'total' in items_N[0] else None
            avgdl_value = items_N[0]['avgdl'] if 'avgdl' in items_N[0] else None
        else:
            total_value, avgdl_value = None, None
        
        return docs_details, total_value, avgdl_value

    except exceptions.CosmosHttpResponseError as e:
        print(f"Error fetching documents: {str(e)}")
        return {}, None, None



def process_query(query, keyword_container, length_container, stopwords, k1 = 1.5, b = 0.5):
    jieba.set_dictionary('dict.txt.big.txt')
    terms = query.split()    

    terms_set = set(terms)

    for term in terms:
        segmented_terms = word_segmentation(term, stopwords)
        terms_set.update(segmented_terms)  
    
    cosmos_results = batch_query_cosmos_db(list(terms_set), keyword_container)
    doc_ids = {doc['document_id'] for result in cosmos_results for doc in result['documents']}
    docs_details, total, avgdl = batch_fetch_document(doc_ids, length_container)

    data = []
    for result in cosmos_results:
        for doc in result['documents']:
            data.append({
                'document_id': doc['document_id'],
                'term': result['id'], 
                'freq': doc['freq']
            })
  
    df = pd.DataFrame(data)

    df_term_counts = df.groupby('term')['document_id'].nunique().reset_index(name='df')
    df = df.merge(df_term_counts, on='term', how='left')

    df['idf'] = df['df'].apply(lambda x: math.log((total - x + 0.5) / (x + 0.5) + 1))

    df['length'] = df['document_id'].map(lambda x: docs_details.get(x, {}).get('length', avgdl))
    df['norm_factor'] = df['length'].apply(lambda l: k1 * (1 - b + b * (l / avgdl)))
    df['score'] = (df['freq'] * (k1 + 1) / (df['freq'] + df['norm_factor'])) * df['idf']
    df_scores = df.groupby('document_id')['score'].sum().reset_index()

    df_terms = df.groupby('document_id').apply(lambda x: {term['term']: {'freq': term['freq']} for index, term in x.iterrows()}).reset_index(name='terms')
    top_docs = df_scores.merge(df_terms, on='document_id', how='left').sort_values(by='score', ascending=False).head(5)
    
    output = {
        "query": query,
        "documents": [
            {
                "document_id": row['document_id'],
                "url": docs_details.get(row['document_id'], {}).get('url', 'URL not available'),
                "terms": row['terms']
            } for index, row in top_docs.iterrows()
        ]
    }

    return output

connection_string = os.getenv("COSMOS_DB_CONNECTION_STRING")
client = CosmosClient.from_connection_string(conn_str=connection_string)

database_name = 'Score'
keyword_container =  client.get_database_client(database_name).get_container_client('bm25-score')
length_container =  client.get_database_client(database_name).get_container_client('documents')

stopwords = get_stopwords('stopwords.txt')
user_query = "錄 開始 今天"
resulting_terms = process_query(user_query, keyword_container, length_container, stopwords)
print(json.dumps(resulting_terms, ensure_ascii=False, indent=4))

