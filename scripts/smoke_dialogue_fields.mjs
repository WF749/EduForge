/**
 * 缺字段中文映射的冒烟测试（纯函数、不调模型、毫秒级）。
 *
 * 存在的理由：missing_fields 是模型自由生成的字段名，不是固定枚举。
 * 只写一张对照表必然漏，漏了的结果不是报错，而是教师看到一串英文单词
 * （"还缺：student_background、available_resources_or_lab_equipment"），
 * 而这个提示恰恰是澄清态唯一有用的信息 —— 后端 message 常常只是一句"请提供更多信息。"。
 *
 * 这里钉死：
 *   1. 实测出现过的整名必须译对；
 *   2. 整名没命中时按词兜底，模型造的新名字也要能译出个大概；
 *   3. 译不出来时原样返回，绝不编造；
 *   4. 去重、去空、保持顺序 —— 教师看到的是"还缺：X、Y、Z"。
 */
import { fieldLabel, fieldLabels } from '../frontend/src/utils/dialogueFields.js'

let pass = 0
let fail = 0

function eq(name, actual, expected) {
  const ok = actual === expected
  ok ? pass++ : fail++
  console.log(`  [${ok ? 'PASS' : 'FAIL'}] ${name}` + (ok ? '' : `  期望「${expected}」实得「${actual}」`))
}

console.log('\n=== 1. 实测出现过的整名 ===')
eq('course_name', fieldLabel('course_name'), '课程名称')
eq('grade_level', fieldLabel('grade_level'), '年级')
eq('subject_area', fieldLabel('subject_area'), '学科领域')
eq('class_duration', fieldLabel('class_duration'), '课时时长')
eq('learning_objectives', fieldLabel('learning_objectives'), '学习目标')
eq('student_background', fieldLabel('student_background'), '学生基础')
eq('available_resources_or_lab_equipment',
  fieldLabel('available_resources_or_lab_equipment'), '可用资源/实验器材')
eq('target_audience', fieldLabel('target_audience'), '教学对象')
eq('key_points', fieldLabel('key_points'), '重点')
eq('resource_type', fieldLabel('resource_type'), '资源类型')

console.log('\n=== 2. 词级兜底（模型造的新名字）===')
eq('teaching_activity_type', fieldLabel('teaching_activity_type'), '教学活动类型')
eq('assessment_method', fieldLabel('assessment_method'), '评价方法')
eq('knowledge_points', fieldLabel('knowledge_points'), '知识点')
// 连词要丢掉，否则会译出"资源或器材"这种夹英文连接词的东西
eq('resources_or_equipment 去掉 or', fieldLabel('resources_or_equipment'), '资源器材')
// 译不出的词（zzz）直接丢掉，只把译得出来的拼起来
eq('部分命中只返回译得出的部分', fieldLabel('lab_zzz_rules'), '实验规则')
eq('常见安全字段', fieldLabel('lab_safety_rules'), '实验安全规则')

console.log('\n=== 3. 译不出来就原样返回，不编造 ===')
eq('完全不认识的词', fieldLabel('zzz_qqq'), 'zzz_qqq')
eq('中文字段名原样返回', fieldLabel('教学难点'), '教学难点')
eq('空值返回空串', fieldLabel(''), '')
eq('null 返回空串', fieldLabel(null), '')
eq('undefined 返回空串', fieldLabel(undefined), '')

console.log('\n=== 4. 一组字段的整理 ===')
const one = fieldLabels(['grade_level', 'duration', 'grade_level'])
eq('去重', one.join('、'), '年级、课时时长')
eq('保持顺序', fieldLabels(['topic', 'grade_level']).join('、'), '主题、年级')
eq('过滤空值', fieldLabels(['', null, 'topic']).join('、'), '主题')
eq('非数组入参不炸', fieldLabels(null).length, 0)

console.log(`\n${'='.repeat(64)}\n通过 ${pass} 项，失败 ${fail} 项\n${'='.repeat(64)}`)
process.exit(fail ? 1 : 0)
