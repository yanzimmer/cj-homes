<template>
  <div class="rent-ledger-container page-container">
    <div class="page-header">
      <div class="header-operations">
        <el-input-number
          v-model="selectedYear"
          :min="2000"
          :max="2100"
          controls-position="right"
          class="year-input"
          @change="handleFilterChange"
        />
        <el-select v-model="selectedStatus" class="status-select" @change="handleFilterChange">
          <el-option label="全部状态" value="" />
          <el-option label="未交" value="未交" />
          <el-option label="部分已交" value="部分已交" />
          <el-option label="已交" value="已交" />
        </el-select>
        <el-button plain :loading="loading" @click="loadSummary">刷新</el-button>
      </div>
    </div>

    <div class="table-panel ledger-panel">
      <div class="ledger-panel__header">
        <div>
          <h3>收租总表</h3>
          <p>按租户汇总展示，点击“查看明细”即可查看和编辑每一期收款记录。</p>
        </div>
      </div>

      <el-table
        ref="ledgerTableRef"
        v-loading="loading"
        :data="ledgerRows"
        border
        class="ledger-table"
        row-key="tenantId"
        :expand-row-keys="expandedRowKeys"
        @expand-change="handleExpandChange"
        :header-cell-style="{ textAlign: 'center' }"
        :cell-style="{ textAlign: 'center' }"
        empty-text="当前年份暂无收租台账"
      >
        <el-table-column type="expand" width="1" class-name="expand-helper-column" label-class-name="expand-helper-column">
          <template #default="{ row }">
            <div class="period-table-wrap">
              <el-table
                :data="row.entries"
                border
                class="period-detail-table"
                :header-cell-style="{ textAlign: 'center' }"
                :cell-style="{ textAlign: 'center' }"
                empty-text="暂无期次"
              >
                <el-table-column prop="period_index" label="期次" width="72" align="center" />
                <el-table-column label="账期" min-width="240" show-overflow-tooltip>
                  <template #default="{ row: entry }">
                    {{ formatPeriodRange(entry) }}
                  </template>
                </el-table-column>
                <el-table-column label="应收" width="110" align="center">
                  <template #default="{ row: entry }">
                    ¥{{ formatAmount(entry.due_amount) }}
                  </template>
                </el-table-column>
                <el-table-column prop="status" label="状态" width="108" align="center">
                  <template #default="{ row: entry }">
                    <el-tag :type="getStatusType(entry.status)">{{ entry.status }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="实收" width="110" align="center">
                  <template #default="{ row: entry }">
                    ¥{{ formatAmount(entry.actual_amount) }}
                  </template>
                </el-table-column>
                <el-table-column prop="payment_date" label="收款日期" width="130" align="center" />
                <el-table-column prop="payment_person" label="收款人" width="110" align="center" />
                <el-table-column prop="payment_method" label="方式" width="110" align="center" />
                <el-table-column label="凭证" width="92" align="center">
                  <template #default="{ row: entry }">
                    <el-image
                      v-if="entry.payment_images && entry.payment_images.length > 0"
                      class="payment-thumb"
                      :src="toImageUrl(entry.payment_images[0])"
                      :preview-src-list="entry.payment_images.map((item) => toImageUrl(item))"
                      fit="cover"
                      preview-teleported
                    />
                    <span v-else>-</span>
                  </template>
                </el-table-column>
                <el-table-column prop="remarks" label="备注" min-width="150" show-overflow-tooltip align="center" />
                <el-table-column label="操作" width="220" fixed="right" align="center">
                  <template #default="{ row: entry }">
                    <div class="operation-buttons">
                      <el-button
                        size="small"
                        type="success"
                        plain
                        :disabled="savingEntryId === entry.id || entry.status === '已交'"
                        @click="markPaid(entry)"
                      >
                        标记已交
                      </el-button>
                      <el-button size="small" type="primary" @click="openEntryDialog(row, entry)">编辑</el-button>
                    </div>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="tenantName" label="租户" min-width="110" fixed="left" />
        <el-table-column label="明细" width="110" align="center">
          <template #default="{ row }">
            <el-button size="small" plain type="primary" @click="toggleRowDetails(row)">
              {{ isRowExpanded(row) ? '收起明细' : '查看明细' }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column prop="roomDisplay" label="房间" min-width="100" />
        <el-table-column label="租金" min-width="120">
          <template #default="{ row }">
            {{ formatRent(row) }}
          </template>
        </el-table-column>
        <el-table-column prop="leaseStart" label="租期开始" min-width="120" />
        <el-table-column prop="leaseEnd" label="租期结束" min-width="120" />
        <el-table-column label="已交" width="80" align="center">
          <template #default="{ row }">
            {{ row.stats.paidPeriods }}
          </template>
        </el-table-column>
        <el-table-column label="部分" width="80" align="center">
          <template #default="{ row }">
            {{ row.stats.partialPeriods }}
          </template>
        </el-table-column>
        <el-table-column label="未交" width="80" align="center">
          <template #default="{ row }">
            {{ row.stats.unpaidPeriods }}
          </template>
        </el-table-column>
        <el-table-column label="总期次" width="88" align="center">
          <template #default="{ row }">
            {{ row.stats.totalPeriods }}
          </template>
        </el-table-column>
        <el-table-column label="应收" min-width="110" align="right">
          <template #default="{ row }">
            ¥{{ formatAmount(row.stats.dueAmount) }}
          </template>
        </el-table-column>
        <el-table-column label="待收" min-width="110" align="right">
          <template #default="{ row }">
            <span class="outstanding-text">¥{{ formatAmount(row.stats.outstandingAmount) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-drawer
      v-model="entryDialog.visible"
      title="编辑收租记录"
      direction="rtl"
      size="560px"
      @closed="resetEntryForm"
    >
      <el-form ref="entryFormRef" :model="entryForm" :rules="entryRules" label-width="96px">
        <el-form-item label="租户">
          <el-input :model-value="entryDialog.title" disabled />
        </el-form-item>
        <el-form-item label="账期">
          <el-input :model-value="formatPeriodRange(entryForm)" disabled />
        </el-form-item>
        <el-form-item label="应收金额">
          <el-input :model-value="`¥${formatAmount(entryForm.due_amount)}`" disabled />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="entryForm.status" style="width: 100%">
            <el-option label="未交" value="未交" />
            <el-option label="部分已交" value="部分已交" />
            <el-option label="已交" value="已交" />
          </el-select>
        </el-form-item>
        <el-form-item label="实收金额" prop="actual_amount">
          <el-input-number
            v-model="entryForm.actual_amount"
            :min="0"
            :precision="2"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="收款日期">
          <el-date-picker
            v-model="entryForm.payment_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="请选择收款日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="收款人">
          <el-input v-model="entryForm.payment_person" placeholder="例如：姑妈、管理员、房东" />
        </el-form-item>
        <el-form-item label="收款方式">
          <el-select
            v-model="entryForm.payment_method"
            filterable
            allow-create
            default-first-option
            clearable
            style="width: 100%"
            placeholder="例如：微信、支付宝、现金"
          >
            <el-option label="微信" value="微信" />
            <el-option label="支付宝" value="支付宝" />
            <el-option label="现金" value="现金" />
            <el-option label="银行转账" value="银行转账" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="entryForm.remarks" type="textarea" :rows="3" placeholder="可填写补交、少交、口头约定等" />
        </el-form-item>
        <el-form-item label="收款凭证">
          <div class="payment-upload-field">
            <div class="payment-upload-actions">
              <el-upload
                action=""
                :auto-upload="false"
                :show-file-list="false"
                accept="image/*"
                multiple
                :limit="20"
                :on-change="handleEntryImageChange"
              >
                <el-button type="primary" plain>选择图片(最多20张)</el-button>
              </el-upload>
              <el-button
                v-if="entryForm.payment_images.length > 0"
                type="danger"
                plain
                @click="clearAllEntryImages"
              >
                全部删除图片
              </el-button>
            </div>
            <div class="upload-progress-text" v-if="uploadingImages">上传进度 {{ uploadProgress }}%</div>
            <div class="upload-progress-text">已选 {{ entryForm.payment_images.length }} / 20</div>
            <div v-if="entryForm.payment_images.length > 0" class="payment-image-preview-wrap">
              <div v-for="(img, index) in entryForm.payment_images" :key="`${img}-${index}`" class="payment-image-box">
                <el-image
                  class="payment-preview-thumb"
                  :src="toImageUrl(img)"
                  :preview-src-list="entryForm.payment_images.map((item) => toImageUrl(item))"
                  fit="cover"
                  preview-teleported
                />
                <el-button size="small" type="danger" plain @click="removeEntryImage(index)">删除</el-button>
              </div>
            </div>
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="entryDialog.visible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="submitEntry">保存</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { rentLedgerApi } from '../api'
import { uploadFileByChunks } from '../utils/chunkUploader'

const currentYear = new Date().getFullYear()
const MAX_PAYMENT_IMAGES = 20

const loading = ref(false)
const submitting = ref(false)
const uploadingImages = ref(false)
const uploadProgress = ref(0)
const savingEntryId = ref(null)
const ledgerTableRef = ref(null)
const expandedRowKeys = ref([])

const selectedYear = ref(currentYear)
const selectedStatus = ref('')
const summaryPayload = ref({
  year: currentYear,
  availableYears: [currentYear],
  overview: {
    tenantCount: 0,
    totalPeriods: 0,
    paidPeriods: 0,
    partialPeriods: 0,
    unpaidPeriods: 0,
    dueAmount: 0,
    actualAmount: 0,
    outstandingAmount: 0,
  },
  groups: [],
})

const entryFormRef = ref(null)
const entryImageFiles = ref([])

const entryDialog = reactive({
  visible: false,
  title: '',
})

const entryForm = reactive({
  id: null,
  tenant_id: null,
  period_label: '',
  due_amount: 0,
  status: '未交',
  actual_amount: 0,
  payment_date: '',
  payment_person: '',
  payment_method: '',
  remarks: '',
  payment_images: [],
})

const entryRules = {
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
  actual_amount: [
    {
      validator: (_rule, value, callback) => {
        if (value === null || value === undefined || value === '') {
          callback()
          return
        }
        if (Number(value) < 0) {
          callback(new Error('实收金额不能小于 0'))
          return
        }
        callback()
      },
      trigger: 'change',
    },
  ],
}

const groups = computed(() => Array.isArray(summaryPayload.value?.groups) ? summaryPayload.value.groups : [])
const ledgerRows = computed(() => groups.value)
function formatAmount(value) {
  return Number(value || 0).toFixed(2)
}

function formatRent(group) {
  const amount = formatAmount(group?.rentAmount || 0)
  const unit = String(group?.rentUnit || '月').trim() || '月'
  return `${amount} 元/${unit}`
}

function formatPeriodRange(entry) {
  const start = String(entry?.period_start || '').trim()
  const end = String(entry?.period_end || '').trim()
  if (start && end) {
    return `${start} ~ ${end}`
  }
  return start || end || '-'
}

function getStatusType(status) {
  if (status === '已交') return 'success'
  if (status === '部分已交') return 'warning'
  return 'danger'
}

function toImageUrl(value) {
  if (!value) return ''
  const text = String(value)
  if (text.startsWith('http://') || text.startsWith('https://') || text.startsWith('blob:') || text.startsWith('data:')) {
    return text
  }
  return text
}

function isRowExpanded(row) {
  return expandedRowKeys.value.includes(row.tenantId)
}

function syncExpandedRowKeys() {
  const validIds = new Set(ledgerRows.value.map((item) => item.tenantId))
  expandedRowKeys.value = expandedRowKeys.value.filter((item) => validIds.has(item))
}

function handleExpandChange(_row, expandedRows) {
  expandedRowKeys.value = expandedRows.map((item) => item.tenantId)
}

function toggleRowDetails(row) {
  const table = ledgerTableRef.value
  if (!table) return
  table.toggleRowExpansion(row, !isRowExpanded(row))
}

async function loadSummary() {
  loading.value = true
  try {
    const { data } = await rentLedgerApi.getSummary(selectedYear.value, selectedStatus.value)
    summaryPayload.value = {
      year: Number(data?.year || selectedYear.value),
      availableYears: Array.isArray(data?.availableYears) ? data.availableYears : [selectedYear.value],
      overview: data?.overview || {
        tenantCount: 0,
        totalPeriods: 0,
        paidPeriods: 0,
        partialPeriods: 0,
        unpaidPeriods: 0,
        dueAmount: 0,
        actualAmount: 0,
        outstandingAmount: 0,
      },
      groups: Array.isArray(data?.groups) ? data.groups : [],
    }
    syncExpandedRowKeys()
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '加载收租台账失败')
  } finally {
    loading.value = false
  }
}

function handleFilterChange() {
  selectedYear.value = Number(selectedYear.value || currentYear)
  loadSummary()
}

async function markPaid(entry) {
  savingEntryId.value = entry.id
  try {
    await rentLedgerApi.updateEntry(entry.id, {
      status: '已交',
      actual_amount: entry.due_amount,
      payment_date: entry.payment_date || new Date().toISOString().slice(0, 10),
      payment_person: entry.payment_person || '',
      payment_method: entry.payment_method || '',
      remarks: entry.remarks || '',
      payment_images: entry.payment_images || [],
    })
    ElMessage.success('已标记为已交')
    await loadSummary()
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '更新状态失败')
  } finally {
    savingEntryId.value = null
  }
}

function revokeEntryPreviewUrls() {
  entryImageFiles.value.forEach((item) => {
    const url = String(item?.url || '')
    if (url.startsWith('blob:')) {
      URL.revokeObjectURL(url)
    }
  })
}

function resetEntryForm() {
  entryFormRef.value?.clearValidate?.()
  revokeEntryPreviewUrls()
  entryImageFiles.value = []
  uploadingImages.value = false
  uploadProgress.value = 0
  entryForm.id = null
  entryForm.tenant_id = null
  entryForm.period_label = ''
  entryForm.due_amount = 0
  entryForm.status = '未交'
  entryForm.actual_amount = 0
  entryForm.payment_date = ''
  entryForm.payment_person = ''
  entryForm.payment_method = ''
  entryForm.remarks = ''
  entryForm.payment_images = []
  entryDialog.title = ''
}

function openEntryDialog(group, entry) {
  resetEntryForm()
  entryDialog.title = `${group.tenantName || '未命名租户'} · ${group.roomDisplay || '-'}`
  entryForm.id = entry.id
  entryForm.tenant_id = entry.tenant_id
  entryForm.period_label = entry.period_label || ''
  entryForm.due_amount = Number(entry.due_amount || 0)
  entryForm.status = entry.status || '未交'
  entryForm.actual_amount = Number(entry.actual_amount || 0)
  entryForm.payment_date = entry.payment_date || ''
  entryForm.payment_person = entry.payment_person || ''
  entryForm.payment_method = entry.payment_method || ''
  entryForm.remarks = entry.remarks || ''
  entryForm.payment_images = Array.isArray(entry.payment_images) ? [...entry.payment_images] : []
  entryDialog.visible = true
}

function handleEntryImageChange(file) {
  if (!file?.raw) return
  if (entryForm.payment_images.length >= MAX_PAYMENT_IMAGES) {
    ElMessage.warning(`最多上传${MAX_PAYMENT_IMAGES}张图片`)
    return
  }
  if (!String(file.raw.type || '').startsWith('image/')) {
    ElMessage.warning('请上传图片文件')
    return
  }
  if (file.raw.size && file.raw.size > 20 * 1024 * 1024) {
    ElMessage.warning('图片请控制在 20MB 以内')
    return
  }
  const url = URL.createObjectURL(file.raw)
  entryImageFiles.value.push({ file: file.raw, url })
  entryForm.payment_images.push(url)
}

function removeEntryImage(index) {
  if (index < 0 || index >= entryForm.payment_images.length) return
  const target = entryForm.payment_images[index]
  entryForm.payment_images.splice(index, 1)
  entryImageFiles.value = entryImageFiles.value.filter((item) => item.url !== target)
  if (String(target || '').startsWith('blob:')) {
    URL.revokeObjectURL(String(target))
  }
}

function clearAllEntryImages() {
  entryForm.payment_images.forEach((target) => {
    if (String(target || '').startsWith('blob:')) {
      URL.revokeObjectURL(String(target))
    }
  })
  entryForm.payment_images = []
  entryImageFiles.value = []
}

function buildUploadSubDir() {
  const tenantId = String(entryForm.tenant_id || 'tenant').replace(/[^0-9A-Za-z_-]/g, '_')
  const entryId = String(entryForm.id || 'entry').replace(/[^0-9A-Za-z_-]/g, '_')
  return `${selectedYear.value}/tenant_${tenantId}/entry_${entryId}`
}

async function submitEntry() {
  if (!entryFormRef.value || !entryForm.id) return
  const valid = await entryFormRef.value.validate().catch(() => false)
  if (!valid) return

  const payload = {
    status: entryForm.status,
    actual_amount: entryForm.actual_amount,
    payment_date: entryForm.payment_date,
    payment_person: entryForm.payment_person,
    payment_method: entryForm.payment_method,
    remarks: entryForm.remarks,
    payment_images: entryForm.payment_images.filter((item) => typeof item === 'string' && !item.startsWith('blob:')).slice(0, MAX_PAYMENT_IMAGES),
  }

  submitting.value = true
  try {
    await rentLedgerApi.updateEntry(entryForm.id, payload)

    if (entryImageFiles.value.length > 0) {
      uploadingImages.value = true
      uploadProgress.value = 0
      const uploadedUrls = []
      const total = entryImageFiles.value.length

      for (let index = 0; index < total; index++) {
        const item = entryImageFiles.value[index]
        const result = await uploadFileByChunks(item.file, {
          category: 'rent_ledgers',
          subDir: buildUploadSubDir(),
          chunkSize: 1024 * 1024,
          maxRetries: 3,
          retryDelay: 800,
          onProgress: (percent) => {
            const finished = index + (Number(percent || 0) / 100)
            uploadProgress.value = Math.floor((finished / total) * 100)
          },
        })
        const fileUrl = String(result?.file_url || '')
        if (!fileUrl) {
          throw new Error('上传成功但未返回图片地址')
        }
        uploadedUrls.push(fileUrl)
        if (String(item.url || '').startsWith('blob:')) {
          URL.revokeObjectURL(item.url)
        }
      }

      await rentLedgerApi.updateEntry(entryForm.id, {
        ...payload,
        payment_images: [...payload.payment_images, ...uploadedUrls].slice(0, MAX_PAYMENT_IMAGES),
      })
      uploadProgress.value = 100
    }

    entryDialog.visible = false
    ElMessage.success('收租记录已更新')
    await loadSummary()
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || error?.message || '保存收租记录失败')
  } finally {
    uploadingImages.value = false
    uploadProgress.value = 0
    submitting.value = false
  }
}

onMounted(() => {
  loadSummary()
})
</script>

<style scoped>
.rent-ledger-container {
  display: flex;
  flex-direction: column;
  gap: 18px;
  border: 1px solid var(--surface-border);
  border-radius: 18px;
  background: var(--card-bg);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: flex-end;
}

.header-operations {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.year-input {
  width: 150px;
}

.status-select {
  width: 140px;
}

.table-panel {
  background: var(--card-bg);
  border: 1px solid var(--surface-border);
  border-radius: 16px;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
  padding: 10px 10px 16px;
}

.ledger-panel {
  padding: 16px 16px 18px;
}

.ledger-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.ledger-panel__header h3 {
  margin: 0;
  font-size: 18px;
  color: var(--text-main);
}

.ledger-panel__header p {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
}

.ledger-table {
  width: 100%;
}

:deep(.ledger-table) {
  --el-table-header-bg-color: var(--surface-muted);
  --el-table-tr-bg-color: var(--card-bg);
  --el-table-bg-color: var(--card-bg);
  --el-fill-color-blank: var(--card-bg);
  --el-table-row-hover-bg-color: rgba(37, 99, 235, 0.06);
  --el-table-border-color: var(--surface-border);
  border-radius: 12px;
  overflow: hidden;
}

:deep(.ledger-table .el-table__header-wrapper th.el-table__cell),
:deep(.period-detail-table .el-table__header-wrapper th.el-table__cell) {
  font-weight: 700;
  color: var(--text-main);
  height: 48px;
}

:deep(.ledger-table .expand-helper-column),
:deep(.ledger-table .expand-helper-column .cell),
:deep(.ledger-table .expand-helper-column .el-table__expand-icon) {
  width: 0 !important;
  min-width: 0 !important;
  padding: 0 !important;
  margin: 0 !important;
  overflow: hidden !important;
  border: none !important;
}

:deep(.ledger-table .el-table__body-wrapper td.el-table__cell),
:deep(.period-detail-table .el-table__body-wrapper td.el-table__cell) {
  padding: 12px 0;
}

:deep(.ledger-table .el-table__expanded-cell) {
  background: var(--card-bg);
}

:deep(.ledger-table .el-table__fixed-right::before),
:deep(.ledger-table .el-table__fixed::before),
:deep(.period-detail-table .el-table__fixed-right::before),
:deep(.period-detail-table .el-table__fixed::before) {
  background-color: transparent;
}

.period-table-wrap {
  padding: 8px 6px 6px;
}

.period-detail-table {
  width: 100%;
}

:deep(.period-detail-table) {
  --el-table-header-bg-color: var(--surface-muted);
  --el-table-tr-bg-color: var(--card-bg);
  --el-table-bg-color: var(--card-bg);
  --el-fill-color-blank: var(--card-bg);
  --el-table-row-hover-bg-color: rgba(37, 99, 235, 0.06);
  --el-table-border-color: var(--surface-border);
  border-radius: 12px;
  overflow: hidden;
}

.payment-thumb,
.payment-preview-thumb {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.28);
}

.payment-upload-field {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  width: 100%;
}

.payment-upload-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.operation-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}

.upload-progress-text {
  margin-top: 8px;
  color: var(--text-secondary);
  font-size: 12px;
}

.payment-image-preview-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 12px;
}

.payment-image-box {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
}

.outstanding-text {
  color: #dc2626;
  font-weight: 600;
}
</style>
