<template>
  <div class="public-rent-page">
    <div class="public-theme-toggle">
      <ThemeModeSwitch floating />
    </div>
    <div class="public-rent-card">
      <div class="public-rent-header">
        <div>
          <h2>房租缴费</h2>
          <p>扫码后可查看当前房间待缴房租、历史缴租次数，并生成微信或支付宝支付订单。</p>
        </div>
        <div v-if="roomHeaderLabel" class="public-rent-room">{{ roomHeaderLabel }}</div>
      </div>

      <div v-if="loading" class="loading-state">正在加载缴租信息...</div>
      <el-alert v-else-if="error" :title="error" type="error" show-icon :closable="false" />

      <div v-else class="public-rent-content">
        <div class="public-rent-stats">
          <div class="public-rent-stat">
            <strong>¥{{ formatAmount(overview?.stats?.outstanding_amount) }}</strong>
            <span>当前待收</span>
          </div>
          <div class="public-rent-stat">
            <strong>{{ overview?.stats?.unpaid_period_count || 0 }}</strong>
            <span>未缴期数</span>
          </div>
          <div class="public-rent-stat">
            <strong>{{ overview?.stats?.paid_history_count || 0 }}</strong>
            <span>历史缴租次数</span>
          </div>
          <div class="public-rent-stat">
            <strong>{{ overview?.stats?.latest_paid_at || '-' }}</strong>
            <span>最近缴租</span>
          </div>
        </div>

        <div class="public-rent-form">
          <div class="public-rent-focus-grid">
            <section class="public-rent-form__card public-rent-form__card--amount public-rent-form__card--single">
              <div class="public-rent-section-label">本次支付金额</div>
              <div class="payment-amount-display">
                <strong>¥{{ formatAmount(paymentAmount) }}</strong>
                <span>根据当前勾选账期自动汇总</span>
              </div>
            </section>
          </div>
          <section class="public-rent-form__full">
            <div class="public-rent-section-label">待缴账期</div>
            <el-checkbox-group v-model="selectedPeriodStarts" class="period-check-list">
              <el-checkbox
                v-for="item in tenantOutstandingPeriods"
                :key="item.period_start"
                :label="item.period_start"
              >
                {{ item.period_label || `${item.period_start} ~ ${item.period_end}` }} · 待缴 ¥{{ formatAmount(item.outstanding_amount) }}
              </el-checkbox>
            </el-checkbox-group>
            <div class="period-tip">不勾选时，系统会自动按最早未缴账期开始分配。</div>
          </section>
        </div>

        <div class="provider-actions">
          <el-button
            type="success"
            :loading="creatingProvider === 'wechat'"
            :disabled="!providers.wechat.enabled"
            @click="createOrder('wechat')"
          >
            生成微信支付码
          </el-button>
          <el-button
            type="primary"
            :loading="creatingProvider === 'alipay'"
            :disabled="!providers.alipay.enabled"
            @click="createOrder('alipay')"
          >
            生成支付宝支付码
          </el-button>
        </div>

        <div class="provider-hints">
          <div v-if="!providers.wechat.enabled" class="provider-hint">{{ providers.wechat.reason || '微信支付当前不可用' }}</div>
          <div v-if="!providers.alipay.enabled" class="provider-hint">{{ providers.alipay.reason || '支付宝当前不可用' }}</div>
        </div>

        <div v-if="currentOrder" class="order-panel">
          <div class="order-panel__head">
            <div>
              <div class="order-panel__title">{{ currentOrder.provider_label }}订单</div>
              <div class="order-panel__meta">订单号：{{ currentOrder.out_trade_no }}</div>
              <div class="order-panel__meta">账期：{{ currentOrder.period_summary || '-' }}</div>
            </div>
            <el-tag :type="orderStatusType">{{ orderStatusLabel }}</el-tag>
          </div>
          <div class="order-panel__amount">¥{{ formatAmount(currentOrder.amount) }}</div>
          <div v-if="orderQrCodeDataUrl" class="order-panel__qr">
            <img :src="orderQrCodeDataUrl" alt="支付二维码" class="order-panel__qr-image" />
          </div>
          <div v-if="currentOrder.provider_code_url" class="order-panel__tip">
            当前已生成支付二维码。如果你正在手机上打开本页，建议用另一台设备扫描该支付码完成支付。
          </div>
          <div v-if="currentOrder.status === 'paid'" class="order-panel__success">
            支付成功，系统已自动入账。
          </div>
          <div class="order-panel__actions">
            <el-button :loading="refreshingOrder" @click="refreshOrder">刷新订单状态</el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import QRCode from 'qrcode'
import { publicRentCollectionApi } from '../api'
import ThemeModeSwitch from '../components/ThemeModeSwitch.vue'
import { applyTheme, getPreferredTheme } from '../utils/theme'

const route = useRoute()
const token = String(route.params.token || '')
const loading = ref(true)
const refreshingOrder = ref(false)
const creatingProvider = ref('')
const error = ref('')
const overview = ref(null)
const providers = ref({
  wechat: { enabled: false, reason: '' },
  alipay: { enabled: false, reason: '' },
})
const selectedTenantId = ref(null)
const paymentAmount = ref(null)
const selectedPeriodStarts = ref([])
const currentOrder = ref(null)
const orderQrCodeDataUrl = ref('')
let orderTimer = null

const roomLabel = computed(() => {
  const room = overview.value?.room || {}
  return String(room.room_display || room.room_no || '').trim()
})

const tenantOptions = computed(() => Array.isArray(overview.value?.tenant_options) ? overview.value.tenant_options : [])
const selectedTenantOption = computed(() => (
  tenantOptions.value.find((item) => Number(item?.id || 0) === Number(selectedTenantId.value || 0)) || tenantOptions.value[0] || null
))
const selectedTenantName = computed(() => {
  const label = String(selectedTenantOption.value?.label || '').trim()
  const room = roomLabel.value
  if (!label) return ''
  if (room && label.startsWith(room)) {
    return label.slice(room.length).replace(/^[\s·\-]+/, '').trim()
  }
  return label
})
const roomHeaderLabel = computed(() => {
  const room = roomLabel.value
  const tenantName = selectedTenantName.value
  if (room && tenantName) return `${room} · ${tenantName}`
  return room || tenantName
})

const tenantOutstandingPeriods = computed(() => {
  const periods = Array.isArray(overview.value?.outstanding_periods) ? overview.value.outstanding_periods : []
  const tenantId = Number(selectedTenantId.value || 0)
  if (!tenantId) return periods
  const stayId = Number(selectedTenantOption.value?.stay_id || 0)
  return periods.filter((item) => (
    Number(item.tenant_id || 0) === tenantId
    && (!stayId || Number(item.stay_id || 0) === stayId)
  ))
})

const orderStatusLabel = computed(() => {
  const status = String(currentOrder.value?.status || '')
  if (status === 'paid') return '已支付'
  if (status === 'closed') return '已关闭'
  if (status === 'failed') return '创建失败'
  return '待支付'
})

const orderStatusType = computed(() => {
  const status = String(currentOrder.value?.status || '')
  if (status === 'paid') return 'success'
  if (status === 'closed' || status === 'failed') return 'danger'
  return 'warning'
})

const formatAmount = (value) => Number(value || 0).toFixed(2)

const syncPaymentAmountWithSelection = () => {
  const periods = tenantOutstandingPeriods.value
  const selected = selectedPeriodStarts.value
    .map((periodStart) => periods.find((item) => item.period_start === periodStart))
    .filter(Boolean)

  if (selected.length > 0) {
    paymentAmount.value = Number(
      selected.reduce((sum, item) => sum + Number(item.outstanding_amount || 0), 0).toFixed(2)
    )
    return
  }

  const firstOutstanding = periods[0]
  paymentAmount.value = Number(firstOutstanding?.outstanding_amount || overview.value?.stats?.suggested_amount || 0)
}

const applySuggestedAmount = () => {
  const firstOutstanding = tenantOutstandingPeriods.value[0]
  selectedPeriodStarts.value = firstOutstanding?.period_start ? [firstOutstanding.period_start] : []
  syncPaymentAmountWithSelection()
}

const refreshOrderQr = async () => {
  const codeUrl = String(currentOrder.value?.provider_code_url || '').trim()
  if (!codeUrl) {
    orderQrCodeDataUrl.value = ''
    return
  }
  orderQrCodeDataUrl.value = await QRCode.toDataURL(codeUrl, { width: 200, margin: 1 })
}

const stopOrderPolling = () => {
  if (orderTimer) {
    window.clearInterval(orderTimer)
    orderTimer = null
  }
}

const startOrderPolling = () => {
  stopOrderPolling()
  if (!currentOrder.value || !['created', 'pending'].includes(String(currentOrder.value.status || ''))) return
  orderTimer = window.setInterval(() => {
    refreshOrder(true)
  }, 5000)
}

const fetchPage = async () => {
  loading.value = true
  try {
    const response = await publicRentCollectionApi.getPage(token)
    overview.value = response?.data?.overview || null
    providers.value = response?.data?.providers || providers.value
    const options = tenantOptions.value
    if (options.length === 1) {
      selectedTenantId.value = options[0].id
      applySuggestedAmount()
    } else if (options.length > 0 && !selectedTenantId.value) {
      selectedTenantId.value = options[0].id
      applySuggestedAmount()
    }
  } catch (err) {
    error.value = err?.response?.data?.error || '缴租链接无效或已失效'
  } finally {
    loading.value = false
  }
}

const createOrder = async (provider) => {
  if (!selectedTenantId.value) {
    ElMessage.warning('请先选择租客')
    return
  }
  if (Number(paymentAmount.value || 0) <= 0) {
    ElMessage.warning('请输入正确的支付金额')
    return
  }
  creatingProvider.value = provider
  try {
    const response = await publicRentCollectionApi.createOrder(token, {
      provider,
      tenant_id: selectedTenantId.value,
      amount: Number(paymentAmount.value || 0),
      selected_period_starts: selectedPeriodStarts.value,
    })
    currentOrder.value = response?.data?.order || null
    await refreshOrderQr()
    startOrderPolling()
    const unallocated = Number(response?.data?.unallocated_amount || 0)
    ElMessage.success(unallocated > 0 ? `支付订单已创建，另有 ${unallocated.toFixed(2)} 元暂未分配到账期` : '支付订单已创建')
  } catch (err) {
    ElMessage.error(err?.response?.data?.error || '创建支付订单失败')
  } finally {
    creatingProvider.value = ''
  }
}

const refreshOrder = async (silent = false) => {
  if (!currentOrder.value?.out_trade_no) return
  if (!silent) refreshingOrder.value = true
  try {
    const response = await publicRentCollectionApi.getOrder(token, currentOrder.value.out_trade_no)
    currentOrder.value = response?.data?.order || currentOrder.value
    await refreshOrderQr()
    if (currentOrder.value?.status === 'paid') {
      stopOrderPolling()
      if (!silent) {
        ElMessage.success('支付成功，系统已自动入账')
      }
      await fetchPage()
    } else if (!['created', 'pending'].includes(String(currentOrder.value?.status || ''))) {
      stopOrderPolling()
    }
  } catch (err) {
    if (!silent) {
      ElMessage.error(err?.response?.data?.error || '刷新订单状态失败')
    }
  } finally {
    if (!silent) refreshingOrder.value = false
  }
}

watch(selectedTenantId, () => {
  if (!selectedTenantId.value) return
  applySuggestedAmount()
})

watch(selectedPeriodStarts, () => {
  syncPaymentAmountWithSelection()
}, { deep: true })

onMounted(() => {
  applyTheme(getPreferredTheme())
  fetchPage()
})

onUnmounted(() => {
  stopOrderPolling()
})
</script>

<style scoped>
.public-rent-page {
  min-height: 100vh;
  padding: 32px 16px;
  background:
    radial-gradient(circle at top left, rgba(16, 185, 129, 0.12), transparent 32%),
    linear-gradient(180deg, var(--bg-color) 0%, var(--surface-muted) 100%);
  color: var(--text-main);
}

.public-rent-card {
  max-width: 860px;
  margin: 0 auto;
  padding: 24px;
  border-radius: var(--card-radius);
  background: var(--card-bg);
  border: 1px solid var(--surface-border);
  box-shadow: var(--card-shadow);
}

.public-rent-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 18px;
}

.public-rent-header h2 {
  margin: 0 0 8px;
}

.public-rent-header p {
  margin: 0;
  color: var(--text-secondary);
}

.public-rent-room {
  padding: 12px 16px;
  border-radius: 999px;
  background: rgba(16, 185, 129, 0.12);
  color: #047857;
  font-size: 18px;
  font-weight: 800;
  line-height: 1.2;
}

.loading-state {
  color: var(--text-secondary);
}

.public-rent-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.public-rent-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.public-rent-stat {
  padding: 14px;
  border-radius: 14px;
  border: 1px solid var(--surface-border);
  background: var(--card-bg);
  display: flex;
  flex-direction: column;
  gap: 6px;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
}

.public-rent-stat strong {
  font-size: 20px;
}

.public-rent-stat span,
.period-tip,
.provider-hint,
.order-panel__meta,
.order-panel__tip {
  color: var(--text-secondary);
  font-size: 13px;
}

.public-rent-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.public-rent-focus-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.public-rent-section-label {
  margin-bottom: 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}

.public-rent-form__card {
  padding: 16px;
  border-radius: 16px;
  border: 1px solid var(--surface-border);
  background: var(--card-bg);
  box-shadow: 0 10px 26px rgba(15, 23, 42, 0.05);
  min-width: 0;
  box-sizing: border-box;
}

.public-rent-form__card--amount {
  justify-content: space-between;
}

.public-rent-form__card--single {
  width: 100%;
}

.public-rent-form__full {
  padding: 16px;
  border-radius: 16px;
  border: 1px solid var(--surface-border);
  background: var(--card-bg);
  min-width: 0;
  box-sizing: border-box;
}

.payment-amount-display {
  min-height: 84px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 6px;
  min-width: 0;
}

.payment-amount-display strong {
  font-size: 28px;
  line-height: 1.2;
  color: var(--text-main);
  word-break: break-word;
}

.payment-amount-display span {
  color: var(--text-secondary);
  font-size: 12px;
}

.period-check-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}

.period-check-list :deep(.el-checkbox) {
  margin-right: 0;
  min-width: 0;
  align-items: flex-start;
}

.period-check-list :deep(.el-checkbox__label) {
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
  line-height: 1.6;
  min-width: 0;
}

.provider-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.provider-hints {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.order-panel {
  padding: 18px;
  border-radius: 16px;
  background: var(--surface-muted);
  border: 1px solid var(--surface-border);
}

.order-panel__head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.order-panel__title {
  font-size: 18px;
  font-weight: 700;
}

.order-panel__amount {
  margin-top: 16px;
  font-size: 28px;
  font-weight: 800;
}

.order-panel__qr {
  margin-top: 16px;
}

.order-panel__qr-image {
  width: 200px;
  height: 200px;
  display: block;
  border-radius: 12px;
  border: 1px solid var(--surface-border);
  background: #fff;
}

.order-panel__tip,
.order-panel__success,
.order-panel__actions {
  margin-top: 14px;
}

.order-panel__success {
  color: #047857;
  font-weight: 600;
}

@media (max-width: 768px) {
  .public-rent-page {
    padding: 20px 12px;
  }

  .public-rent-card {
    padding: 18px 14px;
  }

  .public-rent-header {
    flex-direction: column;
  }

  .public-rent-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .public-rent-focus-grid {
    grid-template-columns: 1fr;
  }

  .public-rent-form__full {
    padding: 14px 12px;
  }

  .public-rent-form__card {
    padding: 14px 12px;
  }

  .payment-amount-display {
    min-height: 72px;
  }

  .payment-amount-display strong {
    font-size: 24px;
  }

  .period-check-list :deep(.el-checkbox__label) {
    padding-left: 8px;
    font-size: 13px;
  }
}
</style>
