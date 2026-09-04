"""测试PPT生成功能"""
import sys
sys.path.insert(0, 'e:\\MultimodalAI-TeachingAgent\\backend')

from app.services.ppt_content_generator import PPTContentGenerator

def test_ppt_generation():
    """测试PPT内容生成"""
    print("=== 测试PPT内容生成 ===")
    
    generator = PPTContentGenerator()
    
    # 测试生成PPT内容
    try:
        ppt_content = generator.generate_ppt_content(
            topic="Python入门教程",
            duration=45,
            audience="大学生",
            subject="计算机",
            theme_color="蓝色系",
            style_preference="专业严谨",
            key_points=["变量与数据类型", "条件语句", "循环结构", "函数定义"]
        )
        
        print(f"✓ PPT内容生成成功!")
        print(f"  - 大纲页数: {len(ppt_content['outline'])}")
        print(f"  - 详细内容页数: {len(ppt_content['detailed_content'])}")
        print(f"  - 主题: {ppt_content['metadata']['topic']}")
        print(f"  - 受众: {ppt_content['metadata']['audience']}")
        print(f"  - 时长: {ppt_content['metadata']['duration']}分钟")
        
        # 打印大纲
        print("\n=== PPT大纲 ===")
        for page in ppt_content['outline']:
            print(f"  [{page['page_num']}] {page['page_type']}: {page['core_topic']}")
            
        # 打印第一页详细内容
        print("\n=== 第一页详细内容 ===")
        if ppt_content['detailed_content']:
            first_page = ppt_content['detailed_content'][0]
            print(f"  页码: {first_page['page_num']}")
            print(f"  类型: {first_page['page_type']}")
            print(f"  标题: {first_page['core_topic']}")
            if 'main_title' in first_page:
                print(f"  主标题: {first_page['main_title']}")
            if 'subtitle' in first_page:
                print(f"  副标题: {first_page['subtitle']}")
                
    except Exception as e:
        print(f"✗ PPT生成失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_ppt_generation()
