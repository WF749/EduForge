# 大学计算机Python编程教学知识库

## 教学目标
1. 掌握Python基础语法
2. 理解程序设计基本思想
3. 能够编写简单的实用程序
4. 培养计算思维和问题解决能力

## 课程内容

### 第一章：Python入门
1. Python简介与发展历史
2. 开发环境配置（Anaconda、Pycharm、VSCode）
3. 第一个Python程序：Hello World
4. Python代码规范（PEP 8）

### 第二章：数据类型与变量
1. 整数(int)、浮点数(float)、字符串(str)
2. 布尔值(bool)和空值(None)
3. 变量命名规则
4. 类型转换

### 第三章：运算符与表达式
1. 算术运算符：+ - * / // % **
2. 比较运算符：== != > < >= <=
3. 逻辑运算符：and or not
4. 赋值运算符和复合赋值

### 第四章：控制结构
1. 条件语句：if-elif-else
2. 循环语句：for、while
3. break和continue语句
4. 嵌套循环

### 第五章：函数
1. 函数定义与调用
2. 参数传递（位置参数、关键字参数）
3. 默认参数值
4. 变量的作用域
5. 匿名函数lambda

### 第六章：数据结构
1. 列表(List)：增删改查、切片
2. 元组(Tuple)：不可变性
3. 字典(Dict)：键值对操作
4. 集合(Set)：去重、交集、并集

### 第七章：文件操作
1. 文件读取：read()、readlines()
2. 文件写入：write()、writelines()
3. with语句和上下文管理器
4. JSON文件处理

### 第八章：面向对象编程
1. 类与对象
2. 继承与多态
3. 封装与私有属性
4. 特殊方法(__init__、__str__等)

## 实用案例

### 案例1：学生成绩管理
```python
students = [
    {"name": "张三", "score": 85},
    {"name": "李四", "score": 92},
    {"name": "王五", "score": 78}
]
average = sum(s["score"] for s in students) / len(students)
print(f"平均分: {average:.2f}")
```

### 案例2：猜数字游戏
```python
import random
target = random.randint(1, 100)
while True:
    guess = int(input("请猜一个1-100的数字: "))
    if guess == target:
        print("恭喜你，猜对了！")
        break
    elif guess < target:
        print("太小了，再试一次")
    else:
        print("太大了，再试一次")
```

## 教学建议
1. 理论与实践相结合
2. 代码量是关键，多敲多练
3. 从具体问题出发引入概念
4. 鼓励学生自己调试和解决问题

## 考核方式
- 平时作业：30%
- 编程实验：30%
- 期中考试：15%
- 期末项目：25%
