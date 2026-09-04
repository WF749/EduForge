"""测试LLM调用是否正常工作"""
import sys
sys.path.insert(0, 'e:\\MultimodalAI-TeachingAgent\\backend')

from app.services.llm.service import llm_service

def test_llm_call():
    """测试LLM调用"""
    print("=== 测试LLM服务 ===")
    
    # 获取当前激活的提供商
    active_provider = llm_service.get_active_provider()
    print(f"当前激活的提供商: {active_provider}")
    
    # 获取配置
    config = llm_service.get_config(active_provider)
    print(f"配置信息: {config}")
    
    # 测试简单的LLM调用
    print("\n=== 测试LLM对话 ===")
    try:
        response = llm_service.chat_completions("你好，请简要介绍一下你自己", [])
        print(f"LLM响应: {response[:300]}...")
        print("✓ LLM调用成功!")
    except Exception as e:
        print(f"✗ LLM调用失败: {e}")

if __name__ == "__main__":
    test_llm_call()
