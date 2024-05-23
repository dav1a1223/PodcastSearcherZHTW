from azure.cosmos import CosmosClient, exceptions
import json
import math
import pandas as pd
import os
import jieba

class CosmosDBQuery:
    def __init__(self, connection_string, database_name, stopwords_file):
        self.client = CosmosClient.from_connection_string(conn_str=connection_string)
        self.keyword_container = self.client.get_database_client(database_name).get_container_client('bm25-score')
        self.length_container = self.client.get_database_client(database_name).get_container_client('documents')
        self.stopwords = self._get_stopwords(stopwords_file)
    
    def _get_stopwords(self, file):
        stopword_list = []
        with open(file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                stopword_list.append(line)
        return stopword_list
    
    def _word_segmentation(self, text):
        seg_list = jieba.lcut_for_search(text)
        return [word for word in seg_list if word not in self.stopwords and word.strip()]
    
    def _batch_query_cosmos_db(self, terms):
        quoted_words = [f"'{word}'" for word in terms]  
        formatted_terms = ", ".join(quoted_words) 
        query = f"SELECT VALUE c FROM c WHERE c.keyword IN ({formatted_terms})" 
        
        try:
            items = list(self.keyword_container.query_items(query=query, enable_cross_partition_query=True))
            return items
        except exceptions.CosmosHttpResponseError as e:
            print(f"Error querying Cosmos DB: {str(e)}")
            return []
    
    def _batch_fetch_document(self, doc_ids):
        quoted_words = [f"'{word}'" for word in doc_ids] 
        formatted_docs = ", ".join(quoted_words)
        query = f"SELECT c.doc_id, c.length, c.url FROM c WHERE c.doc_id IN ({formatted_docs})"
        query_N = "SELECT c.total, c.avgdl FROM c WHERE c.doc_id = 'whole'"
        
        try:
            items = list(self.length_container.query_items(query=query, enable_cross_partition_query=True))
            items_N = list(self.length_container.query_items(query=query_N, enable_cross_partition_query=True))

            docs_details = {}
            for item in items:
                docs_details[item['doc_id']] = {'length': item['length'], 'url': item['url']}

            total_value = items_N[0]['total'] if items_N and 'total' in items_N[0] else None
            avgdl_value = items_N[0]['avgdl'] if items_N and 'avgdl' in items_N[0] else None
            
            return docs_details, total_value, avgdl_value
        except exceptions.CosmosHttpResponseError as e:
            print(f"Error fetching documents: {str(e)}")
            return {}, None, None
    
    def process_query(self, query, k1=1.5, b=0.5):
        terms = query.split() 
        terms_map = {term: term.upper() for term in terms}   
        terms_set = set(terms)

        for term in terms:
            segmented_terms = self._word_segmentation(term)
            for seg_term in segmented_terms:
                terms_map[seg_term] = seg_term.upper() 
            terms_set.update(terms_map[seg_term] for seg_term in segmented_terms)
            
    
        cosmos_results = self._batch_query_cosmos_db(list(terms_set))
        doc_ids = {doc['document_id'] for result in cosmos_results for doc in result['documents']}
        docs_details, total, avgdl = self._batch_fetch_document(doc_ids)

        data = []
        for result in cosmos_results:
            for doc in result['documents']:
                original_term = next(key for key, val in terms_map.items() if val == result['id'])
                data.append({'document_id': doc['document_id'], 'term': original_term, 'freq': doc['freq']})
  
        df = pd.DataFrame(data)

        df_term_counts = df.groupby('term')['document_id'].nunique().reset_index(name='df')
        df = df.merge(df_term_counts, on='term', how='left')

        df['idf'] = df['df'].apply(lambda x: math.log((total - x + 0.5) / (x + 0.5) + 1))

        df['length'] = df['document_id'].map(lambda x: docs_details.get(x, {}).get('length', avgdl))
        df['norm_factor'] = df['length'].apply(lambda l: k1 * (1 - b + b * (l / avgdl)))
        df['score'] = (df['freq'] * (k1 + 1) / (df['freq'] + df['norm_factor'])) * df['idf']
        df_scores = df.groupby('document_id')['score'].sum().reset_index()

        df_terms = df.groupby('document_id').apply(lambda x: {term['term']: {'freq': term['freq']} for _, term in x.iterrows()}).reset_index(name='terms')
        top_docs = df_scores.merge(df_terms, on='document_id', how='left').sort_values(by='score', ascending=False).head(5)
    
        output = {
            "query": query,
            "documents": [{"document_id": row['document_id'], "url": docs_details.get(row['document_id'], {}).get('url', 'URL not available'), "terms": row['terms']} for _, row in top_docs.iterrows()]
        }

        return output
    
