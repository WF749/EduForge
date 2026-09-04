"""业务代码替换示例"""

# 示例1: 智能对话功能的LLM调用
from .llm_service import llm_service

def chat_example():
    """智能对话示例"""
    # 旧代码（硬编码通义千问）
    # from .llm_service import llm_service
    # llm_service.set_provider("dashscope")
    # response = llm_service.chat("你好")
    
    # 新代码（使用统一LLM服务）
    response = llm_service.chat("你好")
    print(f"对话响应: {response}")

# 示例2: 教案生成功能的LLM调用
from .llm_lesson_plan_all_stages import LessonPlanGenerator

def lesson_plan_example():
    """教案生成示例"""
    generator = LessonPlanGenerator()
    
    # 生成教案
    lesson_plan = generator.generate_full_lesson_plan(
        level="普通高等院校",
        subject="计算机科学与技术",
        grade="本科三年级",
        topic="Python数据结构与算法",
        duration=45,
        requirements="重点讲解链表和二叉树的基本操作"
    )
    
    print("教案生成成功")
    print(f"教案标题: {lesson_plan.get('教案基本信息', {}).get('课题', '未知')}")

# 示例3: 课件生成功能的LLM调用
def courseware_example():
    """课件生成示例"""
    # 旧代码（硬编码通义千问）
    # from .llm_service import llm_service
    # llm_service.set_provider("dashscope")
    # prompt = "生成一个关于Python基础的课件"
    # response = llm_service.chat(prompt)
    
    # 新代码（使用统一LLM服务）
    prompt = "生成一个关于Python基础的课件"
    response = llm_service.chat(prompt)
    print(f"课件生成响应: {response[:100]}...")

# 示例4: 深度思考功能的LLM调用
def deep_thinking_example():
    """深度思考示例"""
    # 旧代码（硬编码通义千问）
    # from .llm_service import llm_service
    # llm_service.set_provider("dashscope")
    # response = llm_service.deep_thinking("如何设计一个有效的教学方案")
    
    # 新代码（使用统一LLM服务）
    response = llm_service.deep_thinking("如何设计一个有效的教学方案")
    print(f"深度思考响应: {response[:100]}...")

if __name__ == "__main__":
    print("=== 智能对话示例 ===")
    chat_example()
    print("\n=== 教案生成示例 ===")
    lesson_plan_example()
    print("\n=== 课件生成示例 ===")
    courseware_example()
    print("\n=== 深度思考示例 ===")
    deep_thinking_example()
