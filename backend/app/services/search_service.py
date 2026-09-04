"""智能搜索服务"""
import requests
from typing import List, Dict
from ..core.config import settings

class SearchService:
    """搜索服务类"""
    
    def __init__(self):
        """初始化搜索服务"""
        self.search_engines = {
            "baidu": self._search_baidu,
            "bing": self._search_bing,
            "google": self._search_google
        }
    
    def search(self, query: str, engine: str = "baidu", top_k: int = 5) -> List[Dict]:
        """执行搜索
        
        Args:
            query: 搜索查询
            engine: 搜索引擎，支持 baidu, bing, google
            top_k: 返回结果数量
            
        Returns:
            搜索结果列表
        """
        if engine not in self.search_engines:
            engine = "baidu"
        
        try:
            results = self.search_engines[engine](query, top_k)
            return results
        except Exception as e:
            return [{"title": "搜索错误", "url": "", "snippet": str(e)}]
    
    def _search_baidu(self, query: str, top_k: int) -> List[Dict]:
        """使用百度搜索"""
        try:
            # 使用requests进行简单的网页搜索
            import urllib.parse
            import re
            
            # 构建搜索URL
            encoded_query = urllib.parse.quote(query)
            url = f"https://www.baidu.com/s?wd={encoded_query}"
            
            # 发送请求
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'utf-8'
            html = response.text
            
            # 简单解析搜索结果
            results = []
            
            # 提取标题和链接
            pattern = r'<h3 class="t"><a href="(.*?)" target="_blank" class="_blank">(.*?)</a></h3>'
            matches = re.findall(pattern, html, re.DOTALL)
            
            for i, (link, title) in enumerate(matches[:top_k]):
                # 清理标题
                title = re.sub('<.*?>', '', title)
                
                # 提取摘要
                snippet = ""
                snippet_pattern = r'<div class="c-abstract">(.*?)</div>'
                snippet_matches = re.findall(snippet_pattern, html, re.DOTALL)
                if i < len(snippet_matches):
                    snippet = re.sub('<.*?>', '', snippet_matches[i])[:150] + "..."
                
                results.append({
                    "title": title,
                    "url": link,
                    "snippet": snippet
                })
            
            if not results:
                return self._get_mock_results(query, top_k)
            
            return results
        except Exception as e:
            print(f"百度搜索失败: {str(e)}")
            return self._get_mock_results(query, top_k)
    
    def _search_bing(self, query: str, top_k: int) -> List[Dict]:
        """使用必应搜索"""
        try:
            # 这里使用必应搜索API，需要配置API密钥
            # 由于是演示，返回模拟数据
            return [
                {
                    "title": f"必应搜索结果 {i+1}",
                    "url": f"https://www.bing.com/search?q={query}",
                    "snippet": f"这是关于 '{query}' 的必应搜索结果 {i+1}，提供详细信息。"
                }
                for i in range(top_k)
            ]
        except Exception:
            return self._get_mock_results(query, top_k)
    
    def _search_google(self, query: str, top_k: int) -> List[Dict]:
        """使用谷歌搜索"""
        try:
            # 这里使用谷歌搜索API，需要配置API密钥
            # 由于是演示，返回模拟数据
            return [
                {
                    "title": f"谷歌搜索结果 {i+1}",
                    "url": f"https://www.google.com/search?q={query}",
                    "snippet": f"这是关于 '{query}' 的谷歌搜索结果 {i+1}，包含最新信息。"
                }
                for i in range(top_k)
            ]
        except Exception:
            return self._get_mock_results(query, top_k)
    
    def _get_mock_results(self, query: str, top_k: int) -> List[Dict]:
        """获取模拟搜索结果"""
        return [
            {
                "title": f"搜索结果 {i+1}",
                "url": f"https://example.com/search?q={query}",
                "snippet": f"这是关于 '{query}' 的搜索结果 {i+1}，提供相关信息和内容。"
            }
            for i in range(top_k)
        ]

# 实例化搜索服务
search_service = SearchService()