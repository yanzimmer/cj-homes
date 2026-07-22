<template>
  <el-dialog
    :model-value="modelValue"
    title="房间缴租链接"
    width="min(880px, calc(100vw - 24px))"
    class="business-public-link-dialog"
    modal-class="business-public-link-overlay"
    @close="handleClose"
  >
    <div class="rent-link-panel">
      <div class="rent-link-toolbar">
        <div>
          <div class="rent-link-title">{{ roomLabel }}</div>
          <div class="rent-link-subtitle">固定房间缴租页，系统会默认给每个房间自动补齐。</div>
        </div>
        <div class="rent-link-toolbar-actions">
          <el-button :loading="loading" @click="fetchData">刷新</el-button>
        </div>
      </div>

      <div v-if="overview" class="rent-link-overview">
        <div class="rent-link-stat">
          <strong>¥{{ formatAmount(overview.stats?.outstanding_amount) }}</strong>
          <span>当前待收</span>
        </div>
        <div class="rent-link-stat">
          <strong>{{ overview.stats?.unpaid_period_count || 0 }}</strong>
          <span>未缴期数</span>
        </div>
        <div class="rent-link-stat">
          <strong>{{ overview.stats?.paid_history_count || 0 }}</strong>
          <span>历史缴租次数</span>
        </div>
        <div class="rent-link-stat">
          <strong>{{ overview.stats?.latest_paid_at || '-' }}</strong>
          <span>最近缴租</span>
        </div>
      </div>

      <div v-if="links.length" class="rent-link-tip">
        当前房间固定保留 1 个缴租链接；如需换码，可以直接重建，系统会立刻补一条新的固定链接。
      </div>

      <div v-if="links.length" class="rent-link-list">
        <div v-for="item in links" :key="item.id" class="rent-link-card">
          <div class="rent-link-meta">
            <div>创建时间：{{ item.created_at }}</div>
            <div>状态：{{ item.status }}</div>
          </div>
          <div v-if="item.qrCodeDataUrl" class="rent-link-qr">
            <img :src="item.qrCodeDataUrl" alt="缴租二维码" class="rent-link-qr-image" />
          </div>
          <div class="rent-link-url">{{ buildUrl(item.token) }}</div>
          <div class="rent-link-actions">
            <el-button size="small" @click="copyLink(item.token)">复制链接</el-button>
            <el-button size="small" type="primary" plain @click="openLink(item.token)">打开链接</el-button>
            <el-button
              v-if="item.status === 'active'"
              size="small"
              type="danger"
              @click="disableLink(item)"
            >
              停用
            </el-button>
            <el-button
              v-else
              size="small"
              type="success"
              @click="enableLink(item)"
            >
              启用
            </el-button>
            <el-button size="small" type="warning" plain @click="rebuildLink(item)">重建链接</el-button>
          </div>
        </div>
      </div>
      <el-empty v-else description="系统正在自动补齐固定缴租链接，请点刷新重试" />
    </div>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import QRCode from 'qrcode'
import { roomsApi } from '../api'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  room: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['update:modelValue'])

const loading = ref(false)
const links = ref([])
const overview = ref(null)

const PUBLIC_APP_ORIGIN = (import.meta.env.VITE_PUBLIC_APP_ORIGIN || window.location.origin).replace(/\/$/, '')

const roomLabel = computed(() => {
  const building = String(props.room?.building || '').trim()
  const roomNo = String(props.room?.room_no || props.room?.room_display || '').trim()
  if (building && roomNo && !roomNo.toUpperCase().startsWith(`${building.toUpperCase()}-`)) {
    return `${building}-${roomNo}`
  }
  return roomNo || '未选择房间'
})

const buildUrl = (token) => `${PUBLIC_APP_ORIGIN}/rent/${token}`

const formatAmount = (value) => Number(value || 0).toFixed(2)

const withQr = async (items = []) => Promise.all(items.map(async (item) => ({
  ...item,
  qrCodeDataUrl: await QRCode.toDataURL(buildUrl(item.token), { width: 144, margin: 1 }),
})))

const fetchData = async () => {
  if (!props.room?.id) return
  loading.value = true
  try {
    const response = await roomsApi.listRentCollectionLinks(props.room.id)
    links.value = await withQr(response?.data?.links || [])
    overview.value = response?.data?.overview || null
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '加载缴租链接失败')
  } finally {
    loading.value = false
  }
}

const copyLink = async (token) => {
  try {
    await navigator.clipboard.writeText(buildUrl(token))
    ElMessage.success('缴租链接已复制')
  } catch (_) {
    ElMessage.error('复制失败，请手动复制')
  }
}

const openLink = (token) => {
  window.open(buildUrl(token), '_blank', 'noopener,noreferrer')
}

const disableLink = async (item) => {
  try {
    await roomsApi.disableRentCollectionLink(item.id)
    await fetchData()
    ElMessage.success('缴租链接已停用')
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '停用缴租链接失败')
  }
}

const enableLink = async (item) => {
  try {
    await roomsApi.enableRentCollectionLink(item.id)
    await fetchData()
    ElMessage.success('缴租链接已启用')
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '启用缴租链接失败')
  }
}

const rebuildLink = async (item) => {
  try {
    await ElMessageBox.confirm('重建后会生成一条新的固定缴租链接，原链接将失效，但已有支付订单和台账不会删除，是否继续？', '重建缴租链接', {
      confirmButtonText: '确认重建',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await roomsApi.deleteRentCollectionLink(item.id)
    await fetchData()
    ElMessage.success('缴租链接已重建')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error?.response?.data?.error || '重建缴租链接失败')
    }
  }
}

const handleClose = () => emit('update:modelValue', false)

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) fetchData()
  }
)
</script>

<style scoped>
.rent-link-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.rent-link-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.rent-link-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-main);
}

.rent-link-subtitle {
  margin-top: 6px;
  color: var(--text-secondary);
  font-size: 13px;
}

.rent-link-toolbar-actions {
  display: flex;
  gap: 8px;
}

.rent-link-overview {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.rent-link-stat {
  padding: 12px;
  border-radius: 12px;
  background: var(--surface-muted);
  border: 1px solid var(--surface-border);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.rent-link-stat strong {
  font-size: 18px;
  color: var(--text-main);
}

.rent-link-stat span,
.rent-link-tip {
  color: var(--text-secondary);
  font-size: 13px;
}

.rent-link-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.rent-link-card {
  padding: 14px;
  border-radius: 14px;
  background: var(--surface-muted);
  border: 1px solid var(--surface-border);
}

.rent-link-meta {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--text-secondary);
}

.rent-link-qr {
  margin: 10px 0;
}

.rent-link-qr-image {
  width: 144px;
  height: 144px;
  display: block;
  background: #fff;
  border-radius: 10px;
  border: 1px solid var(--surface-border);
}

.rent-link-url {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  word-break: break-all;
  color: var(--text-regular);
}

.rent-link-actions {
  margin-top: 10px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

@media (max-width: 768px) {
  .rent-link-toolbar {
    flex-direction: column;
  }

  .rent-link-overview {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .rent-link-toolbar-actions {
    width: 100%;
  }
}
</style>
