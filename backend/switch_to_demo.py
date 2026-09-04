import sqlite3

# 连接数据库（使用backend目录下的数据库）
conn = sqlite3.connect("llm_config.db")
cursor = conn.cursor()

# 先禁用所有提供商
cursor.execute("UPDATE llm_config SET is_active = 0")

# 启用演示模式
cursor.execute('UPDATE llm_config SET is_active = 1 WHERE provider = "demo"')

conn.commit()
conn.close()

print("已成功切换到演示模式")