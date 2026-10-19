"""LLM抽象基类"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any, Generator

class LLMProviderBase(ABC):
    """LLM提供商抽象基类"""
    
    @abstractmethod
    def test_connection(self, api_key: str, base_url: Optional[str] = None) -> Dict[str, Any]:
        """测试连接与密钥有效性
        
        Args:
            api_key: API密钥
            base_url: 基础URL（可选）
            
        Returns:
            Dict: 包含成功/失败状态和错误信息的字典
        """
        pass
    
    @abstractmethod
    def list_models(self, api_key: str, base_url: Optional[str] = None) -> List[Dict[str, str]]:
        """获取可用模型列表
        
        Args:
            api_key: API密钥
            base_url: 基础URL（可选）
            
        Returns:
            List[Dict]: 模型列表，每个模型包含name和description
        """
        pass
    
    @abstractmethod
    def chat_completions(
        self,
        prompt: str,
        history: List[Dict],
        temperature: float = 0.7,
        api_key: str = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """统一的对话生成方法
        
        Args:
            prompt: 提示词
            history: 对话历史
            temperature: 温度参数
            api_key: API密钥
            base_url: 基础URL（可选）
            
        Returns:
            str: 生成的文本内容
        """
        pass
    
    @abstractmethod
    def get_embeddings(
        self,
        text: str,
        api_key: str = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> List[float]:
        """获取文本嵌入向量
        
        Args:
            text: 要嵌入的文本
            api_key: API密钥
            base_url: 基础URL（可选）
            
        Returns:
            List[float]: 文本的嵌入向量
        """
        pass
    
    def stream_chat_completions(
        self,
        prompt: str,
        history: List[Dict],
        temperature: float = 0.7,
        api_key: str = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """流式对话生成方法
        
        Args:
            prompt: 提示词
            history: 对话历史
            temperature: 温度参数
            api_key: API密钥
            base_url: 基础URL（可选）
            
        Yields:
            str: 生成的文本片段
        """
        # 默认实现，子类可重写
        full_response = self.chat_completions(prompt, history, temperature, api_key, base_url, model)
        yield full_response


def sampling_kwargs(temperature: Optional[float]) -> Dict[str, Any]:
    """把温度拼进请求体；模型不接受时**整个字段都不发**。

    发 `temperature: null` 会被厂商拒绝（400）—— 那等于把"这个模型不支持该参数"
    变成了一次调用失败。不发才是让厂商用自己的默认行为。

    用法（函数关键字参数与字典字面量都适用）：
        client.chat.completions.create(model=m, messages=msgs, **sampling_kwargs(t))
        data = {"model": m, "messages": msgs, **sampling_kwargs(t)}
    """
    return {} if temperature is None else {"temperature": temperature}
