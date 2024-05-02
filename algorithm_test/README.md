【Week 9】
**Topic : improve 三個 dataset 的 Precision@1, @3, @5 metrics by 斷詞、BM25算法、等等調優**
> 運用兩種算法的Precision@1, @3, @5 的結果分別如圖，BM25有較佳結果，但仍不是很理想，我們嘗試了以下幾種方法：

**1. 調整BM25 k1, b 參數**
造成的結果差異並不是很大
**2. jieba 辭典新增繁體詞彙**
jieba 斷詞原本是用預設的lcut，但因為他是簡體中文開發，有些斷詞並不好，例如：「晚點吃飯」會斷成「晚點、吃、飯」。我們改設辭典為繁體詞庫。將 transcripts 和 dataset 都重新斷詞，但計算出來的精準度也沒有明顯提升：（
**3. 先比 term 出現個數再比 score**
在選擇哪一個集數最為對應，我們發現 query 的詞有些太日常廣泛，例如：['發現','脆','離家出走']，[離家出走]在 EP3 的分數很高，但[發現]和[脆]這兩個較不重要的字在 EP5 的分數更高，就會影響到只看 score 的結果。
結果只有 tfidf （尤其 transcripts）的 accuracy 會有較顯著提升，對於 BM25 沒有甚麼幫助，基本上沒太大影響：（
**4. 覺得有機會試試但可能不會提升太多的方法**
用 transcripts 斷詞的詞庫做為 jieba 辭典，缺點是每次有新集數就要更新詞庫，不太有效率。
> 想法

最主要的問題還是出在 user 輸入的 query，給的詞有時不夠精準，或是輸入的詞是用戶腦中想過的，和逐字稿的詞彙其實不同（例如：情侶、男女）
> 補充

1. 調整計算分數時的權重 (自己再斷詞一次)
2. dataset 的部分，transcript是用舊的斷詞 func（簡體中文）
3. [繁體詞庫txt](https://github.com/tony1966/tony1966.github.io/blob/master/test/python/jieba/dict/dict.txt.big.txt)
