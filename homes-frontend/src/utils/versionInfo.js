const APP_RELEASE_VERSION = typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : '1.1.1'

const releaseHistory = [
  {
    version: '1.1.1',
    releasedAt: '2026-07-22',
    notes: [
      '系统维护中心改版为独立导航布局，拆分出系统快照、阿里云 OCR 配置、房间设施配置、水电费账户预设、支付收款配置、AI 模式配置、登录会话管理等独立维护页。',
      '调整 AI 模式配置开关逻辑，开启和关闭只控制前端显示状态，不再触发本地模型启停，修复停用时提示找不到 ollama 命令的问题。',
      '统一系统版本信息与升级说明的版本来源，避免前端版本、后端版本和升级说明版本显示不一致。',
      '修复腾讯云短信配置保存后刷新丢失的问题，SecretId 和 SecretKey 现在可以正常保存与回显。',
      '修复清空短信配置后又被环境变量自动补回旧值的问题，显式清空后会按空配置保存。',
      '修复租户和房东提醒场景取消勾选后刷新又恢复默认值的问题，现在支持按空场景配置保存。',
    ],
  },
  {
    version: '1.1.0',
    releasedAt: '2026-07-22',
    notes: [
      '修复收租台账里大额实收自动冲抵的显示错误，当前账期保留实收，后续自动冲抵账期显示实收 0。',
      '修复台账重建后自动冲抵月份被错误写回实收=应收的问题。',
      '修复跨年冲抵时缺失账期会跳过 2027 年 1 月、2 月等中间月份的错位问题，现会先补齐账期再按顺序冲抵。',
      '修复公开房租缴费页勾选多个待缴账期后本次支付金额不联动的问题，并改为只读展示。',
      '恢复收租台账图片凭证的查看、上传、删除能力，并修复编辑时旧图片被后台重复合并的问题。',
    ],
  },
]

export const frontendVersionInfo = Object.freeze({
  name: 'homes-frontend',
  version: APP_RELEASE_VERSION,
  commit: typeof __APP_COMMIT__ !== 'undefined' ? __APP_COMMIT__ : 'unknown',
  buildTime: typeof __APP_BUILD_TIME__ !== 'undefined' ? __APP_BUILD_TIME__ : '',
})

export const currentReleaseNotes = Object.freeze(
  releaseHistory.find((item) => item.version === APP_RELEASE_VERSION) || releaseHistory[0]
)

export const historicalReleaseNotes = Object.freeze(
  releaseHistory.filter((item) => item.version !== currentReleaseNotes.version)
)

export const formatVersionText = (version, fallback = '未知') => {
  const text = String(version || '').trim()
  return text ? `v${text}` : fallback
}
