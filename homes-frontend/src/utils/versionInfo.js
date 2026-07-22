export const frontendVersionInfo = Object.freeze({
  name: 'homes-frontend',
  version: typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : '1.1.0',
  commit: typeof __APP_COMMIT__ !== 'undefined' ? __APP_COMMIT__ : 'unknown',
  buildTime: typeof __APP_BUILD_TIME__ !== 'undefined' ? __APP_BUILD_TIME__ : '',
})

export const currentReleaseNotes = Object.freeze({
  version: '1.1.0',
  releasedAt: '2026-07-22',
  notes: [
    '修复收租台账里大额实收自动冲抵的显示错误，当前账期保留实收，后续自动冲抵账期显示实收 0。',
    '修复台账重建后自动冲抵月份被错误写回实收=应收的问题。',
    '修复跨年冲抵时缺失账期会跳过 2027 年 1 月、2 月等中间月份的错位问题，现会先补齐账期再按顺序冲抵。',
    '修复公开房租缴费页勾选多个待缴账期后本次支付金额不联动的问题，并改为只读展示。',
    '恢复收租台账图片凭证的查看、上传、删除能力，并修复编辑时旧图片被后台重复合并的问题。',
  ],
})

export const formatVersionText = (version, fallback = '未知') => {
  const text = String(version || '').trim()
  return text ? `v${text}` : fallback
}
