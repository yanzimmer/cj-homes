<template>
  <el-dialog :model-value="modelValue" :title="title" width="760px" @close="handleClose">
    <div class="link-panel">
      <div class="link-toolbar">
        <div class="link-toolbar-text">
          当前业务：{{ businessLabel }}
        </div>
        <el-button
          type="primary"
          :loading="creating"
          :disabled="Boolean(link)"
          @click="createLink"
        >
          生成填写链接
        </el-button>
      </div>

      <div v-if="link" class="link-tip">
        当前业务仅保留 1 个链接。如需新链接，请先删除原链接。
      </div>

      <div v-if="link" class="link-card">
        <div class="link-meta">
          <div>创建时间：{{ link.created_at }}</div>
          <div>状态：{{ link.status }}</div>
          <div>提交次数：{{ link.submission_count || 0 }}</div>
        </div>
        <div v-if="link.qrCodeDataUrl" class="link-qr">
          <img :src="link.qrCodeDataUrl" alt="填写二维码" class="link-qr-image" />
        </div>
        <div class="link-url">{{ buildUrl(link.token) }}</div>
        <div class="link-actions">
          <el-button size="small" @click="copyLink(link.token)">复制链接</el-button>
          <el-button size="small" type="primary" plain @click="openLink(link.token)">打开链接</el-button>
          <el-button
            v-if="link.status === 'active'"
            size="small"
            type="danger"
            @click="disableLink"
          >
            停用
          </el-button>
          <el-button
            v-else
            size="small"
            type="success"
            @click="enableLink"
          >
            启用
          </el-button>
          <el-button size="small" type="danger" plain @click="deleteLink">删除</el-button>
        </div>
      </div>

      <el-empty v-else description="当前还没有填写链接" />
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import QRCode from 'qrcode'
import { businessEntryLinksApi } from '../api'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  businessType: { type: String, required: true },
  title: { type: String, required: true },
  businessLabel: { type: String, required: true },
})

const emit = defineEmits(['update:modelValue'])

const link = ref(null)
const creating = ref(false)

const PUBLIC_APP_ORIGIN = (import.meta.env.VITE_PUBLIC_APP_ORIGIN || window.location.origin).replace(/\/$/, '')
const buildUrl = (token) => `${PUBLIC_APP_ORIGIN}/entry/${props.businessType}/${token}`

const withQr = async (item) => {
  if (!item?.token) return null
  return {
    ...item,
    qrCodeDataUrl: await QRCode.toDataURL(buildUrl(item.token), { width: 132, margin: 1 }),
  }
}

const fetchLink = async () => {
  try {
    const response = await businessEntryLinksApi.getLink(props.businessType)
    link.value = await withQr(response?.data?.link || null)
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '加载填写链接失败')
  }
}

const createLink = async () => {
  creating.value = true
  try {
    const response = await businessEntryLinksApi.createLink(props.businessType)
    link.value = await withQr(response?.data?.link || null)
    ElMessage.success('填写链接已生成')
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '生成填写链接失败')
  } finally {
    creating.value = false
  }
}

const copyLink = async (token) => {
  try {
    await navigator.clipboard.writeText(buildUrl(token))
    ElMessage.success('填写链接已复制')
  } catch (_) {
    ElMessage.error('复制失败，请手动复制')
  }
}

const openLink = (token) => {
  window.open(buildUrl(token), '_blank', 'noopener,noreferrer')
}

const disableLink = async () => {
  if (!link.value?.id) return
  try {
    await businessEntryLinksApi.disableLink(link.value.id)
    await fetchLink()
    ElMessage.success('填写链接已停用')
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '停用填写链接失败')
  }
}

const enableLink = async () => {
  if (!link.value?.id) return
  try {
    await businessEntryLinksApi.enableLink(link.value.id)
    await fetchLink()
    ElMessage.success('填写链接已启用')
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '启用填写链接失败')
  }
}

const deleteLink = async () => {
  if (!link.value?.id) return
  try {
    await ElMessageBox.confirm('确定删除这个填写链接吗？', '删除填写链接', {
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await businessEntryLinksApi.deleteLink(link.value.id)
    link.value = null
    ElMessage.success('填写链接已删除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error?.response?.data?.error || '删除填写链接失败')
    }
  }
}

const handleClose = () => {
  emit('update:modelValue', false)
}

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) fetchLink()
  }
)
</script>

<style scoped>
.link-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.link-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.link-toolbar-text {
  font-weight: 600;
  color: var(--text-main);
}

.link-tip {
  font-size: 13px;
  color: var(--text-secondary);
}

.link-card {
  padding: 12px;
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  background: var(--surface-muted);
}

.link-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--text-secondary);
  flex-wrap: wrap;
}

.link-qr {
  margin: 10px 0;
}

.link-qr-image {
  width: 132px;
  height: 132px;
  display: block;
  border-radius: 8px;
  border: 1px solid var(--surface-border);
  background: #ffffff;
}

.link-url {
  margin: 8px 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  word-break: break-all;
  color: var(--text-regular);
}

.link-actions {
  display: flex;
  gap: 8px;
  flex-wrap: nowrap;
  white-space: nowrap;
}
</style>
