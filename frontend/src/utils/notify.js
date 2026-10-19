import { ElMessage, ElMessageBox } from 'element-plus'

/**
 * 反馈统一出口。
 *
 * 为什么要包一层：提示散落在各页面时，同一个"删除成功"会有三种措辞、
 * 有的用 Toast 有的用弹窗，教师无法形成预期。这里钉死四种结果的措辞与载体：
 *   成功 → 短 Toast；失败 → 长停留 Toast（要来得及读完）；
 *   警告 → 橙 Toast；危险操作 → 二次确认弹窗（不直接执行）。
 */

export function notifySuccess(text) {
  ElMessage({ type: 'success', message: text, duration: 2400, showClose: false })
}

/** 失败的停留时间更长：教师需要读完这句才知道下一步该干嘛 */
export function notifyError(text) {
  ElMessage({ type: 'error', message: text, duration: 5000, showClose: true })
}

export function notifyWarn(text) {
  ElMessage({ type: 'warning', message: text, duration: 4000, showClose: true })
}

export function notifyInfo(text) {
  ElMessage({ type: 'info', message: text, duration: 3000, showClose: false })
}

/**
 * 危险操作二次确认。
 *
 * `danger` 为真时用红色确认按钮，并要求把**后果**写进 `consequence`
 * —— 只写"确定删除吗？"等于没提示，教师不知道连带着会没掉什么。
 */
export async function confirmDanger({
  title = '确认执行？',
  consequence = '',
  confirmText = '确认删除',
  cancelText = '再想想',
  danger = true
} = {}) {
  const html = consequence
    ? `<div style="font-size:14px;line-height:1.7">${consequence}</div>`
    : ''
  try {
    await ElMessageBox.confirm(html, title, {
      confirmButtonText: confirmText,
      cancelButtonText: cancelText,
      type: 'warning',
      dangerouslyUseHTMLString: true,
      confirmButtonClass: danger ? 'el-button--danger' : ''
    })
    return true
  } catch {
    return false
  }
}
