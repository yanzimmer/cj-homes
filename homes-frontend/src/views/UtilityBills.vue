<template>
  <div class="utility-bills-container page-container" :class="{ 'utility-bills-container--mobile': mobileMode }">
    <div class="page-header">
      <div class="page-header__title">
        <h2>水电费</h2>
        <div v-if="mobileMode" class="utility-mobile-stats">
          <div class="utility-mobile-stat">
            <strong>{{ selectedYear }}</strong>
            <span>统计年份</span>
          </div>
          <div class="utility-mobile-stat">
            <strong>¥{{ formatAmount(totalAnnualAmount) }}</strong>
            <span>年度总额</span>
          </div>
        </div>
      </div>
      <div class="header-operations">
        <el-input-number
          v-model="selectedYear"
          :min="2000"
          :max="2100"
          controls-position="right"
          class="year-input"
          @change="handleYearChange"
        />
        <el-button type="primary" plain @click="openAiDialog">AI 输入</el-button>
        <el-button v-if="!mobileMode" type="success" plain :loading="exporting" @click="handleExportExcel">导出 Excel</el-button>
      </div>
    </div>

    <div
      v-for="section in utilitySections"
      :key="section.type"
      class="table-panel utility-panel"
    >
      <div class="utility-panel__header">
        <div>
          <h3>{{ section.label }}</h3>
          <p>
            年度合计 ¥{{ formatAmount(section.summary.annualTotal) }}，共 {{ section.summary.subjectCount }} 个账户。
          </p>
        </div>
        <el-button type="primary" plain @click="openBillDialog(section.type)">新增{{ section.label }}</el-button>
      </div>

      <div v-if="mobileMode" class="utility-mobile-list">
        <div v-if="section.summary.subjects.length === 0" class="utility-mobile-empty">
          <el-empty description="暂无账单" :image-size="40" />
        </div>
        <article v-for="subject in section.summary.subjects" :key="`${section.type}-${subject.account}`" class="utility-mobile-card">
          <div class="utility-mobile-card__top">
            <div>
              <div class="utility-mobile-card__account">{{ subject.account || '未命名账户' }}</div>
              <div class="utility-mobile-card__meta">
                共 {{ subject.recordCount || 0 }} 条 · 年度合计 ¥{{ formatAmount(subject.totalAmount || 0) }}
              </div>
            </div>
          </div>

          <div v-if="getSubjectMonthRecords(subject).length > 0" class="utility-mobile-months">
            <button
              v-for="record in getSubjectMonthRecords(subject)"
              :key="`${subject.account}-${record.month}`"
              type="button"
              class="utility-mobile-month"
              @click="openBillDialog(section.type, subject.account, Number(record.month), record)"
            >
              <div class="utility-mobile-month__header">
                <strong>{{ record.month }}月</strong>
                <span>¥{{ formatAmount(record.amount) }}</span>
              </div>
              <div class="utility-mobile-month__meta">
                <span>{{ record.payer || '未填写缴费人' }}</span>
                <span>{{ parseBillImages(record).length }} 张图</span>
              </div>
            </button>
          </div>
          <div v-else class="utility-mobile-empty-text">该账户本年度暂无账单记录</div>
        </article>
      </div>

      <el-table
        v-else
        :key="`${section.type}-${tableRenderKey}`"
        v-loading="loading"
        :data="section.rows"
        border
        class="utility-table"
        :row-class-name="getTableRowClassName"
        empty-text="暂无账单"
      >
        <el-table-column prop="account" label="账户" fixed="left" min-width="140" />
        <el-table-column
          v-for="month in months"
          :key="`${section.type}-${month}`"
          :label="`${month}月`"
          min-width="120"
          align="center"
        >
          <template #header>
            <div class="table-month-header">
              <span>{{ month }}月</span>
              <small>¥{{ formatAmount(section.summary.monthlyTotals[String(month)] || 0) }}</small>
            </div>
          </template>
          <template #default="{ row }">
            <span
              v-if="row.rowType === 'subject' && getBillRecord(row, month)"
              class="utility-amount-text"
              @click="openBillDialog(section.type, row.account, month, getBillRecord(row, month))"
            >
              {{ formatBillAmount(getBillRecord(row, month)) }}
            </span>
            <span v-else-if="row.rowType === 'note'">
              {{ getRowNoteText(row, month) }}
            </span>
            <div v-else-if="row.rowType === 'images'" class="utility-image-cell">
              <div v-if="getRowImages(row, month).length > 0" class="utility-image-list">
                <el-image
                  v-for="(img, index) in getRowImages(row, month)"
                  :key="`${img}-${index}`"
                  class="utility-image-thumb"
                  :src="toImageUrl(img)"
                  :preview-src-list="getRowImages(row, month).map((item) => toImageUrl(item))"
                  fit="cover"
                  preview-teleported
                />
              </div>
              <span v-else>-</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="合计" min-width="120" align="right" fixed="right">
          <template #default="{ row }">
            <span v-if="row.rowType === 'subject'">
              {{ formatBillAmount({ amount: row.totalAmount || 0 }) }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-drawer
      v-model="billDialog.visible"
      :title="billDialog.isEdit ? '编辑账单' : '录入账单'"
      direction="rtl"
      :size="mobileMode ? '100%' : '560px'"
      @closed="resetBillForm"
    >
      <el-form
        ref="billFormRef"
        :model="billForm"
        :rules="billRules"
        label-width="96px"
      >
        <el-form-item label="费用类型" prop="utility_type">
          <el-select v-model="billForm.utility_type" :disabled="Boolean(billDialog.lockedUtilityType)" style="width: 100%">
            <el-option label="电费" value="electricity" />
            <el-option label="水费" value="water" />
          </el-select>
        </el-form-item>
        <el-form-item label="账户" prop="account">
          <el-select
            v-model="billForm.account"
            filterable
            allow-create
            default-first-option
            clearable
            style="width: 100%"
            placeholder="可搜索或直接输入账户"
          >
            <el-option
              v-for="item in currentAccountOptions"
              :key="`${billForm.utility_type}-${item}`"
              :label="item"
              :value="item"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="billForm.ai_recognition_hint" label="识别提示">
          <div class="utility-ai-recognition-hint">{{ billForm.ai_recognition_hint }}</div>
        </el-form-item>
        <el-form-item label="年份" prop="year">
          <el-input-number v-model="billForm.year" :min="2000" :max="2100" style="width: 100%" />
        </el-form-item>
        <el-form-item label="月份" prop="month">
          <el-select v-model="billForm.month" style="width: 100%">
            <el-option v-for="month in months" :key="month" :label="`${month}月`" :value="month" />
          </el-select>
        </el-form-item>
        <el-form-item label="金额" prop="amount">
          <el-input-number
            v-model="billForm.amount"
            :min="0"
            :precision="2"
            style="width: 100%"
            placeholder="请输入金额"
          />
        </el-form-item>
        <el-form-item label="缴费人">
          <el-input v-model="billForm.payer" placeholder="例如：姑妈交、黎从交" />
        </el-form-item>
        <el-form-item label="账单图片" class="bill-image-field">
          <div class="bill-image-uploader">
            <div
              class="form-image-dropzone"
              :class="{ 'form-image-dropzone--active': billImageDragActive }"
              @dragenter.prevent="billImageDragActive = true"
              @dragover.prevent="billImageDragActive = true"
              @dragleave.prevent="billImageDragActive = false"
              @drop.prevent="handleBillImageDrop"
              @paste="handleBillImagePaste"
              tabindex="0"
            >
              <div class="form-image-dropzone__title">拖拽图片到这里</div>
              <div class="form-image-dropzone__hint">也支持直接粘贴截图</div>
            </div>
            <div class="bill-image-actions">
              <el-upload
                action=""
                :auto-upload="false"
                :show-file-list="false"
                accept="image/*"
                multiple
                :limit="20"
                :on-change="handleBillImageChange"
              >
                <el-button type="primary" plain>选择图片(最多20张)</el-button>
              </el-upload>
              <el-button
                v-if="billForm.bill_images.length > 0"
                type="danger"
                plain
                @click="clearAllBillImages"
              >
                全部删除图片
              </el-button>
            </div>
            <div class="upload-progress-text" v-if="uploadingImages">上传进度 {{ uploadProgress }}%</div>
            <div class="upload-progress-text">已选 {{ billForm.bill_images.length }} / 20</div>
            <div v-if="billForm.bill_images.length > 0" class="bill-image-preview-wrap">
              <div v-for="(img, index) in billForm.bill_images" :key="`${img}-${index}`" class="bill-image-box">
                <el-image
                  class="bill-image-thumb"
                  :src="toImageUrl(img)"
                  :preview-src-list="billForm.bill_images.map((v) => toImageUrl(v))"
                  fit="cover"
                  preview-teleported
                />
                <el-button size="small" type="danger" plain @click="removeBillImage(index)">删除</el-button>
              </div>
            </div>
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="dialog-footer">
          <el-button v-if="billDialog.isEdit" type="danger" plain @click="handleDeleteBill">删除</el-button>
          <span class="dialog-footer__spacer" />
          <el-button @click="billDialog.visible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="handleSubmitBill">保存</el-button>
        </div>
      </template>
    </el-drawer>

    <el-dialog
      title="AI 输入水电费"
      v-model="aiDialog.visible"
      :width="mobileMode ? '96%' : '620px'"
      class="app-ai-dialog"
      modal-class="app-ai-dialog-overlay"
      @close="resetAiDialog"
    >
      <el-form label-width="92px">
        <el-form-item label="文字描述">
          <el-input
            v-model="aiDialog.text"
            type="textarea"
            :rows="5"
            placeholder="例如：6 月 A-201 电费 128 元，黎从缴费。也可以直接上传微信/支付宝缴费截图、账单截图让 AI 识别。"
            @paste="handleAiPaste"
          />
        </el-form-item>
        <el-form-item label="图片识别">
          <div class="ai-upload-panel">
            <div
              class="ai-dropzone"
              :class="{ 'ai-dropzone--active': aiDialog.dragActive }"
              @dragenter.prevent="aiDialog.dragActive = true"
              @dragover.prevent="aiDialog.dragActive = true"
              @dragleave.prevent="aiDialog.dragActive = false"
              @drop.prevent="handleAiDrop"
              @paste="handleAiPaste"
              tabindex="0"
            >
              <div class="ai-dropzone__title">拖拽图片到这里识别</div>
              <div class="ai-dropzone__hint">也可以点击下面按钮选择图片，或直接粘贴截图。识别后会自动带到账单图片。</div>
            </div>
            <div class="ai-upload-actions">
              <el-upload
                action=""
                :auto-upload="false"
                :show-file-list="false"
                accept="image/*"
                multiple
                :limit="4"
                :on-change="handleAiImageChange"
              >
                <el-button type="primary" plain>选择图片</el-button>
              </el-upload>
              <el-button
                v-if="aiDialog.images.length"
                type="danger"
                plain
                @click="clearAiImages"
              >
                清空图片
              </el-button>
            </div>
          </div>
          <div class="upload-progress-text">已选 {{ aiDialog.images.length }} / 4</div>
          <div v-if="aiDialog.images.length" class="ai-image-list">
            <div v-for="(item, index) in aiDialog.images" :key="item.url" class="ai-image-item">
              <el-image
                class="ai-image-thumb"
                :src="item.url"
                :preview-src-list="aiDialog.images.map(img => img.url)"
                fit="cover"
                preview-teleported
              />
              <el-button size="small" type="danger" plain @click="removeAiImage(index)">删除</el-button>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="aiDialog.visible = false">取消</el-button>
          <el-button type="primary" :loading="aiDialog.loading" @click="submitAiDraft">生成并填入</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as XLSX from 'xlsx'
import { utilityBillsApi } from '../api'
import { uploadFileByChunks } from '../utils/chunkUploader'
import { DISPLAY_MODE_EVENT, getPreferredDisplayMode } from '../utils/displayMode'

const months = Array.from({ length: 12 }, (_, index) => index + 1)
const currentYear = new Date().getFullYear()
const mobileMode = ref(false)

const sectionMeta = [
  { type: 'electricity', label: '电费' },
  { type: 'water', label: '水费' },
]

const createEmptySummary = (type) => ({
  type,
  label: getUtilityLabel(type),
  annualTotal: 0,
  subjectCount: 0,
  monthlyTotals: Object.fromEntries(months.map((month) => [String(month), 0])),
  subjects: [],
  records: [],
})

const createInitialPayload = (year = currentYear) => ({
  year,
  months: [...months],
  availableYears: [year],
  summaries: {
    electricity: createEmptySummary('electricity'),
    water: createEmptySummary('water'),
  },
})

const loading = ref(false)
const exporting = ref(false)
const submitting = ref(false)
const uploadingImages = ref(false)
const uploadProgress = ref(0)
const billImageDragActive = ref(false)
const tableRenderKey = ref(0)
const selectedYear = ref(currentYear)
const summaryPayload = ref(createInitialPayload(currentYear))
const billFormRef = ref(null)
const billImageFiles = ref([])
const aiDialog = reactive({
  visible: false,
  loading: false,
  text: '',
  images: [],
  dragActive: false,
})
const accountOptions = reactive({
  electricity: [],
  water: [],
})
const MAX_UTILITY_IMAGES = 20

const billDialog = reactive({
  visible: false,
  isEdit: false,
  lockedUtilityType: '',
})

const billForm = reactive({
  id: null,
  utility_type: 'electricity',
  account: '',
  year: currentYear,
  month: 1,
  amount: null,
  payer: '',
  bill_images: [],
  ai_recognition_hint: '',
})

const billRules = {
  utility_type: [{ required: true, message: '请选择费用类型', trigger: 'change' }],
  account: [{ required: true, message: '请填写账户', trigger: 'blur' }],
  year: [{ required: true, message: '请填写年份', trigger: 'change' }],
  month: [{ required: true, message: '请选择月份', trigger: 'change' }],
  amount: [
    {
      validator: (_rule, value, callback) => {
        if (value === null || value === undefined || value === '') {
          callback(new Error('请填写金额'))
          return
        }
        if (Number(value) < 0) {
          callback(new Error('金额不能小于 0'))
          return
        }
        callback()
      },
      trigger: 'change',
    },
  ],
}

const utilitySections = computed(() =>
  sectionMeta.map((section) => ({
    ...section,
    summary: summaryPayload.value.summaries?.[section.type] || createEmptySummary(section.type),
    rows: buildDisplayRows(summaryPayload.value.summaries?.[section.type] || createEmptySummary(section.type)),
  })),
)
const currentAccountOptions = computed(() => {
  const presetOptions = Array.isArray(accountOptions[billForm.utility_type]) ? accountOptions[billForm.utility_type] : []
  const summary = summaryPayload.value.summaries?.[billForm.utility_type] || createEmptySummary(billForm.utility_type)
  const existingAccounts = (summary?.subjects || [])
    .map((item) => String(item?.account || item?.subject || '').trim())
    .filter((item) => item)
  return [...new Set([...presetOptions, ...existingAccounts])]
})
const totalAnnualAmount = computed(() => (
  Number(summaryPayload.value.summaries?.electricity?.annualTotal || 0)
  + Number(summaryPayload.value.summaries?.water?.annualTotal || 0)
))

const syncDisplayMode = () => {
  mobileMode.value = getPreferredDisplayMode() === 'mobile'
}

function getUtilityLabel(type) {
  return type === 'water' ? '水费' : '电费'
}

function formatAmount(value) {
  return Number(value || 0).toFixed(2)
}

function formatBillAmount(record) {
  if (!record) return ''
  return `¥${formatAmount(record.amount)}`
}

function applyAccountOptions(data = {}) {
  accountOptions.electricity = Array.isArray(data?.electricity) ? data.electricity : []
  accountOptions.water = Array.isArray(data?.water) ? data.water : []
}

function toImageUrl(value) {
  if (!value) return ''
  const text = String(value)
  if (text.startsWith('http://') || text.startsWith('https://') || text.startsWith('blob:') || text.startsWith('data:')) {
    return text
  }
  return text
}

function parseBillImages(record) {
  if (record?.bill_images && Array.isArray(record.bill_images)) {
    return record.bill_images
      .map((item) => String(item || '').trim())
      .filter((item) => item)
      .slice(0, MAX_UTILITY_IMAGES)
  }
  const raw = record?.bill_image ? String(record.bill_image) : ''
  return raw.trim() ? [raw.trim()] : []
}

function getBillRecord(row, month) {
  return row?.months?.[String(month)] || null
}

function getMonthlyNoteText(summary, month, field) {
  const monthKey = String(month)
  const values = []
  ;(summary?.records || []).forEach((record) => {
    if (String(record.month) !== monthKey) return
    const value = String(record?.[field] || '').trim()
    if (!value || values.includes(value)) return
    values.push(value)
  })
  return values.length > 0 ? values.join('；') : '-'
}

function getRowNoteText(row, month) {
  const value = row?.months?.[String(month)]?.[row.noteField] || ''
  return String(value).trim() || '-'
}

function getRowImages(row, month) {
  return parseBillImages(row?.months?.[String(month)] || null)
}

function buildDisplayRows(summary) {
  const rows = []
  ;(summary?.subjects || []).forEach((subject) => {
    rows.push({
      ...subject,
      rowType: 'subject',
    })
    rows.push({
      rowType: 'note',
      account: '缴费人',
      noteField: 'payer',
      months: subject.months || {},
      totalAmount: '',
    })
    rows.push({
      rowType: 'images',
      account: '图片',
      months: subject.months || {},
      totalAmount: '',
    })
  })
  return rows
}

function getSubjectMonthRecords(subject) {
  return months
    .map((month) => subject?.months?.[String(month)] || null)
    .filter((record) => record && (record.amount !== null && record.amount !== undefined && record.amount !== ''))
}

function buildSummaryExportRows(summary) {
  const headers = ['账户', ...months.map((month) => `${month}月`), '合计']
  const rows = []

  ;(summary?.subjects || []).forEach((subject) => {
    const monthCells = months.map((month) => {
      const record = subject?.months?.[String(month)] || null
      return record ? Number(record.amount || 0) : ''
    })
    rows.push([subject.account || '', ...monthCells, Number(subject.totalAmount || 0)])
    rows.push([
      '缴费人',
      ...months.map((month) => String(subject?.months?.[String(month)]?.payer || '').trim() || '-'),
      '',
    ])
    rows.push([
      '图片',
      ...months.map((month) => {
        const record = subject?.months?.[String(month)] || null
        const imageCount = parseBillImages(record).length
        return imageCount > 0 ? `${imageCount}张` : '-'
      }),
      '',
    ])
  })

  return [headers, ...rows]
}

function getTableRowClassName({ row }) {
  return row?.rowType === 'note' ? 'utility-note-table-row' : ''
}

function buildDetailExportRows() {
  const records = [
    ...(summaryPayload.value.summaries?.electricity?.records || []),
    ...(summaryPayload.value.summaries?.water?.records || []),
  ]
  const headers = ['费用类型', '账户', '年份', '月份', '金额', '缴费人', '图片数', '备注', '创建时间', '更新时间']
  const rows = records.map((record) => ([
    record.utility_label || getUtilityLabel(record.utility_type),
    record.account || record.subject || '',
    record.year || '',
    record.month || '',
    Number(record.amount || 0),
    record.payer || '',
    parseBillImages(record).length,
    record.remarks || '',
    record.created_at || '',
    record.updated_at || '',
  ]))
  return [headers, ...rows]
}

function buildWorksheet(rows) {
  const worksheet = XLSX.utils.aoa_to_sheet(rows)
  const columnWidths = rows.reduce((result, row) => {
    row.forEach((cell, index) => {
      const content = String(cell ?? '')
      result[index] = Math.max(result[index] || 10, Math.min(content.length + 2, 28))
    })
    return result
  }, [])
  worksheet['!cols'] = columnWidths.map((width) => ({ wch: width }))
  return worksheet
}

function handleExportExcel() {
  exporting.value = true
  try {
    const workbook = XLSX.utils.book_new()
    const electricitySummary = summaryPayload.value.summaries?.electricity || createEmptySummary('electricity')
    const waterSummary = summaryPayload.value.summaries?.water || createEmptySummary('water')

    XLSX.utils.book_append_sheet(workbook, buildWorksheet(buildSummaryExportRows(electricitySummary)), '电费汇总')
    XLSX.utils.book_append_sheet(workbook, buildWorksheet(buildSummaryExportRows(waterSummary)), '水费汇总')
    XLSX.utils.book_append_sheet(workbook, buildWorksheet(buildDetailExportRows()), '账单明细')

    XLSX.writeFile(workbook, `水电费_${selectedYear.value}.xlsx`)
    ElMessage.success('Excel 导出完成')
  } catch (error) {
    console.error('导出 Excel 失败', error)
    ElMessage.error('导出 Excel 失败')
  } finally {
    exporting.value = false
  }
}

async function loadSummary() {
  loading.value = true
  try {
    const { data } = await utilityBillsApi.getSummary(selectedYear.value)
    applyAccountOptions(data?.accountOptions || {})
    summaryPayload.value = {
      ...createInitialPayload(selectedYear.value),
      ...data,
      summaries: {
        electricity: {
          ...createEmptySummary('electricity'),
          ...(data?.summaries?.electricity || {}),
        },
        water: {
          ...createEmptySummary('water'),
          ...(data?.summaries?.water || {}),
        },
      },
    }
    tableRenderKey.value += 1
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '加载水电费数据失败')
  } finally {
    loading.value = false
  }
}

function revokeBillPreviewUrls() {
  billImageFiles.value.forEach((item) => {
    const url = String(item?.url || '')
    if (url.startsWith('blob:')) {
      URL.revokeObjectURL(url)
    }
  })
}

function revokeAiImageUrls() {
  aiDialog.images.forEach((item) => {
    if (String(item?.url || '').startsWith('blob:')) {
      URL.revokeObjectURL(item.url)
    }
  })
}

function buildBillUploadSubDir(targetId) {
  const utilityType = String(billForm.utility_type || 'utility').trim() || 'utility'
  const year = String(billForm.year || selectedYear.value || currentYear).trim() || String(currentYear)
  const safeTargetId = String(targetId || 'new').replace(/[^0-9A-Za-z_-]/g, '_')
  return `${utilityType}/${year}/bill_${safeTargetId}`
}

function handleBillImageChange(file) {
  const raw = file?.raw || file
  if (!raw) return
  if (billForm.bill_images.length >= MAX_UTILITY_IMAGES) {
    ElMessage.warning(`最多上传${MAX_UTILITY_IMAGES}张图片`)
    return
  }
  if (!String(raw.type || '').startsWith('image/')) {
    ElMessage.warning('请上传图片文件')
    return
  }
  if (raw.size && raw.size > 20 * 1024 * 1024) {
    ElMessage.warning('图片请控制在 20MB 以内')
    return
  }
  const url = URL.createObjectURL(raw)
  billImageFiles.value.push({ file: raw, url })
  billForm.bill_images.push(url)
}

function handleBillImageDrop(event) {
  billImageDragActive.value = false
  const files = Array.from(event?.dataTransfer?.files || [])
  for (const file of files) {
    handleBillImageChange(file)
  }
}

function handleBillImagePaste(event) {
  const clipboardItems = Array.from(event?.clipboardData?.items || [])
  const imageItems = clipboardItems.filter((item) => String(item?.type || '').startsWith('image/'))
  if (!imageItems.length) return
  event.preventDefault()
  for (const item of imageItems) {
    const file = item.getAsFile()
    if (file) {
      handleBillImageChange(file)
    }
  }
}

function removeBillImage(index) {
  if (index < 0 || index >= billForm.bill_images.length) return
  const target = billForm.bill_images[index]
  billForm.bill_images.splice(index, 1)
  billImageFiles.value = billImageFiles.value.filter(item => item.url !== target)
  if (String(target || '').startsWith('blob:')) {
    URL.revokeObjectURL(String(target))
  }
}

function clearAllBillImages() {
  billForm.bill_images.forEach((target) => {
    if (String(target || '').startsWith('blob:')) {
      URL.revokeObjectURL(String(target))
    }
  })
  billForm.bill_images = []
  billImageFiles.value = []
}

function handleYearChange() {
  selectedYear.value = Number(selectedYear.value || currentYear)
  loadSummary()
}

function resetBillForm() {
  if (billFormRef.value) {
    billFormRef.value.clearValidate()
  }
  revokeBillPreviewUrls()
  billImageFiles.value = []
  uploadingImages.value = false
  uploadProgress.value = 0
  billImageDragActive.value = false
  billForm.id = null
  billForm.utility_type = 'electricity'
  billForm.account = ''
  billForm.year = selectedYear.value
  billForm.month = 1
  billForm.amount = null
  billForm.payer = ''
  billForm.bill_images = []
  billForm.ai_recognition_hint = ''
  billDialog.isEdit = false
  billDialog.lockedUtilityType = ''
}

function resetAiDialog() {
  revokeAiImageUrls()
  aiDialog.loading = false
  aiDialog.text = ''
  aiDialog.images = []
  aiDialog.dragActive = false
}

function openAiDialog() {
  resetAiDialog()
  aiDialog.visible = true
}

function appendAiImageFile(rawFile) {
  if (!rawFile) return
  if (aiDialog.images.length >= 4) {
    ElMessage.warning('最多选择 4 张图片')
    return
  }
  if (!String(rawFile.type || '').startsWith('image/')) {
    ElMessage.warning('请上传图片文件')
    return
  }
  if (rawFile.size && rawFile.size > 8 * 1024 * 1024) {
    ElMessage.warning('单张图片请控制在 8MB 以内')
    return
  }
  aiDialog.images.push({
    file: rawFile,
    url: URL.createObjectURL(rawFile)
  })
}

function handleAiImageChange(file) {
  if (!file || !file.raw) return
  appendAiImageFile(file.raw)
}

function handleAiDrop(event) {
  aiDialog.dragActive = false
  const files = Array.from(event?.dataTransfer?.files || [])
  if (!files.length) return
  for (const file of files) {
    appendAiImageFile(file)
  }
}

function handleAiPaste(event) {
  const clipboardItems = Array.from(event?.clipboardData?.items || [])
  const imageItems = clipboardItems.filter((item) => String(item?.type || '').startsWith('image/'))
  if (!imageItems.length) return
  event.preventDefault()
  for (const item of imageItems) {
    const file = item.getAsFile()
    if (file) {
      appendAiImageFile(file)
    }
  }
}

function removeAiImage(index) {
  const item = aiDialog.images[index]
  if (!item) return
  if (String(item.url || '').startsWith('blob:')) {
    URL.revokeObjectURL(item.url)
  }
  aiDialog.images.splice(index, 1)
}

function clearAiImages() {
  revokeAiImageUrls()
  aiDialog.images = []
}

function openBillDialog(utilityType, account = '', month = 1, record = null) {
  resetBillForm()
  const targetUtilityType = utilityType || 'electricity'
  billForm.utility_type = targetUtilityType
  billDialog.lockedUtilityType = targetUtilityType
  billForm.account = account || ''
  billForm.year = selectedYear.value
  billForm.month = month || 1
  if (record) {
    billDialog.isEdit = true
    billForm.id = record.id
    billForm.utility_type = record.utility_type
    billDialog.lockedUtilityType = record.utility_type || targetUtilityType
    billForm.account = record.account || record.subject
    billForm.year = record.year
    billForm.month = record.month
    billForm.amount = Number(record.amount || 0)
    billForm.payer = record.payer || ''
    billForm.bill_images = parseBillImages(record)
  }
  billDialog.visible = true
}

function applyAiDraftToBillForm(draft = {}, aiImages = []) {
  resetBillForm()
  billDialog.isEdit = false
  billDialog.lockedUtilityType = ''
  billForm.id = null
  billForm.utility_type = String(draft.utility_type || 'electricity') === 'water' ? 'water' : 'electricity'
  billForm.account = String(draft.account || '').trim()
  billForm.year = Number(draft.year || selectedYear.value || currentYear)
  billForm.month = Number(draft.month || 1)
  billForm.amount = Number(draft.amount || 0)
  billForm.payer = String(draft.payer || '').trim()
  const recognizedUserCode = String(draft.recognized_user_code || '').trim()
  const recognizedAddress = String(draft.recognized_address || '').trim()
  const matchedAccount = String(draft.matched_account || '').trim()
  const matchReason = String(draft.match_reason || '').trim()
  const knownAccounts = Array.isArray(draft.known_accounts) ? draft.known_accounts.filter(Boolean) : []

  if (matchedAccount) {
    billForm.ai_recognition_hint = matchReason || `已自动匹配到账户：${matchedAccount}`
  } else {
    const hintParts = []
    if (recognizedUserCode) {
      hintParts.push(`用户编号：${recognizedUserCode}`)
    }
    if (recognizedAddress) {
      hintParts.push(`缴费地址：${recognizedAddress}`)
    }
    if (knownAccounts.length) {
      hintParts.push(`当前可选账户：${knownAccounts.join('、')}`)
    }
    billForm.ai_recognition_hint = hintParts.join('；')
  }

  const copiedAiImages = aiImages
    .filter(item => item?.file)
    .slice(0, MAX_UTILITY_IMAGES)
    .map(item => ({
      file: item.file,
      url: URL.createObjectURL(item.file)
    }))

  billImageFiles.value = copiedAiImages
  billForm.bill_images = copiedAiImages.map(item => item.url)
  billDialog.visible = true
}

async function submitAiDraft() {
  if (!aiDialog.text.trim() && aiDialog.images.length === 0) {
    ElMessage.warning('请先输入文字或选择图片')
    return
  }
  aiDialog.loading = true
  try {
    const formData = new FormData()
    formData.append('text', aiDialog.text.trim())
    aiDialog.images.forEach((item) => {
      formData.append('images', item.file)
    })
    const response = await utilityBillsApi.createAiDraft(formData)
    applyAiDraftToBillForm(response?.data?.draft || {}, aiDialog.images)
    aiDialog.visible = false
    if (response?.data?.draft?.matched_account) {
      ElMessage.success('AI 草稿已填入，并已自动匹配到账户')
    } else {
      ElMessage.warning('AI 已识别图片信息，但暂未匹配到系统账户，请确认后保存')
    }
  } catch (error) {
    const message = error?.response?.data?.error || error?.message || 'AI 输入失败'
    ElMessage.error(message)
  } finally {
    aiDialog.loading = false
  }
}

async function handleSubmitBill() {
  if (!billFormRef.value) return

  const valid = await billFormRef.value.validate().catch(() => false)
  if (!valid) return

  const payload = {
    utility_type: billForm.utility_type,
    account: billForm.account,
    year: billForm.year,
    month: billForm.month,
    amount: billForm.amount,
    payer: billForm.payer,
    remarks: '',
    bill_images: (billForm.bill_images || []).filter((item) => typeof item === 'string' && !item.startsWith('blob:')).slice(0, MAX_UTILITY_IMAGES),
  }

  submitting.value = true
  try {
    let response
    if (billDialog.isEdit && billForm.id) {
      response = await utilityBillsApi.updateBill(billForm.id, payload)
    } else {
      response = await utilityBillsApi.saveBill(payload)
    }

    const targetId = response?.data?.bill?.id || billForm.id
    if (targetId && billImageFiles.value.length > 0) {
      uploadingImages.value = true
      uploadProgress.value = 0
      const uploadedUrls = []
      const total = billImageFiles.value.length

      for (let index = 0; index < total; index++) {
        const item = billImageFiles.value[index]
        const result = await uploadFileByChunks(item.file, {
          category: 'utility_bills',
          subDir: buildBillUploadSubDir(targetId),
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

      const finalImages = [...payload.bill_images, ...uploadedUrls]
        .map((item) => String(item || '').trim())
        .filter((item) => item)
        .slice(0, MAX_UTILITY_IMAGES)

      await utilityBillsApi.updateBillImages(targetId, { bill_images: finalImages })
      billForm.bill_images = finalImages
      uploadProgress.value = 100
    }

    billDialog.visible = false
    if (Number(payload.year) !== Number(selectedYear.value)) {
      selectedYear.value = Number(payload.year)
    }
    await loadSummary()
    ElMessage.success(billDialog.isEdit ? '账单已更新' : '账单已保存')
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '保存账单失败')
  } finally {
    uploadingImages.value = false
    uploadProgress.value = 0
    submitting.value = false
  }
}

async function handleDeleteBill() {
  if (!billForm.id) return
  try {
    await ElMessageBox.confirm('删除后该月份账单会被清空，是否继续？', '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    submitting.value = true
    await utilityBillsApi.deleteBill(billForm.id)
    ElMessage.success('账单已删除')
    billDialog.visible = false
    await loadSummary()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error?.response?.data?.error || '删除账单失败')
    }
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  syncDisplayMode()
  window.addEventListener(DISPLAY_MODE_EVENT, syncDisplayMode)
  loadSummary()
})

onBeforeUnmount(() => {
  window.removeEventListener(DISPLAY_MODE_EVENT, syncDisplayMode)
})
</script>

<style scoped>
.utility-bills-container {
  display: flex;
  flex-direction: column;
  gap: 18px;
  border: 1px solid var(--surface-border);
  border-radius: 18px;
  background: var(--card-bg);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
  padding: 20px;
}

.page-header__title {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page-header h2 {
  margin: 0;
  color: #409EFF;
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

.utility-mobile-stats {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.utility-mobile-stat {
  min-width: 92px;
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid var(--surface-border);
  background: var(--surface-muted);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.utility-mobile-stat strong {
  font-size: 18px;
  color: var(--text-main);
}

.utility-mobile-stat span {
  font-size: 12px;
  color: var(--text-secondary);
}

.table-panel {
  background: var(--card-bg);
  border: 1px solid var(--surface-border);
  border-radius: 16px;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
  padding: 10px 10px 16px;
}

.utility-panel {
  padding: 16px 16px 18px;
}

.utility-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.utility-panel__header h3 {
  margin: 0;
  font-size: 18px;
  color: var(--text-main);
}

.utility-panel__header p {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
}

.utility-mobile-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.utility-mobile-empty {
  padding: 10px 0;
}

.utility-mobile-card {
  padding: 14px;
  border-radius: 16px;
  border: 1px solid var(--surface-border);
  background: var(--card-bg);
  box-shadow: 0 14px 26px rgba(15, 23, 42, 0.06);
}

.utility-mobile-card__top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.utility-mobile-card__account {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-main);
}

.utility-mobile-card__meta {
  margin-top: 5px;
  font-size: 12px;
  color: var(--text-secondary);
}

.utility-mobile-months {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}

.utility-mobile-month {
  width: 100%;
  padding: 11px 12px;
  border-radius: 12px;
  border: 1px solid var(--surface-border);
  background: var(--surface-muted);
  text-align: left;
  cursor: pointer;
}

.utility-mobile-month__header,
.utility-mobile-month__meta {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}

.utility-mobile-month__header strong {
  font-size: 14px;
  color: var(--text-main);
}

.utility-mobile-month__header span,
.utility-mobile-month__meta {
  font-size: 12px;
  color: var(--text-secondary);
}

.utility-mobile-empty-text {
  margin-top: 12px;
  font-size: 13px;
  color: var(--text-secondary);
}

.table-month-header {
  display: flex;
  flex-direction: column;
  gap: 2px;
  line-height: 1.2;
}

.table-month-header small {
  color: var(--text-secondary);
  font-size: 11px;
}

.utility-amount-text {
  color: var(--text-main);
  cursor: pointer;
}

.utility-image-cell {
  display: flex;
  justify-content: center;
}

.utility-image-list {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 6px;
}

.utility-image-thumb {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: 1px solid var(--surface-border);
}

.upload-progress-text {
  margin-top: 8px;
  color: #64748b;
  font-size: 12px;
}

.bill-image-uploader {
  width: 100%;
  min-width: 0;
}

.form-image-dropzone {
  width: 100%;
  margin-bottom: 10px;
  padding: 14px 16px;
  border: 1px dashed var(--surface-border);
  border-radius: 12px;
  background: var(--surface-muted);
  transition: border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease;
}

.form-image-dropzone--active {
  border-color: var(--el-color-primary);
  background: rgba(37, 99, 235, 0.08);
  box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.12);
}

.form-image-dropzone__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
}

.form-image-dropzone__hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}

.bill-image-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.bill-image-preview-wrap {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.bill-image-box {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.bill-image-thumb {
  width: 92px;
  height: 92px;
  border-radius: 8px;
  border: 1px solid var(--surface-border);
}

.utility-ai-recognition-hint {
  width: 100%;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(59, 130, 246, 0.18);
  background: rgba(59, 130, 246, 0.08);
  color: var(--text-main);
  font-size: 13px;
  line-height: 1.6;
  white-space: normal;
  word-break: break-word;
}

:deep(.utility-table) {
  --el-table-header-bg-color: var(--surface-muted);
  --el-table-tr-bg-color: var(--card-bg);
  --el-table-bg-color: var(--card-bg);
  --el-fill-color-blank: var(--card-bg);
  --el-table-row-hover-bg-color: rgba(37, 99, 235, 0.06);
  --el-table-border-color: var(--surface-border);
  border-radius: 12px;
  overflow: hidden;
}

:deep(.utility-table .el-table__header-wrapper th.el-table__cell) {
  font-weight: 700;
  color: var(--text-main);
  height: 48px;
}

:deep(.utility-table .el-table__body-wrapper td.el-table__cell) {
  padding: 12px 0;
}

:deep(.utility-table .el-table__fixed-right::before),
:deep(.utility-table .el-table__fixed::before) {
  background-color: transparent;
}

:deep(.utility-table .utility-note-table-row) {
  --el-table-tr-bg-color: var(--card-bg);
}

:deep(.utility-table .utility-note-table-row td.el-table__cell) {
  color: var(--text-secondary);
  font-size: 12px;
}

:deep(.utility-table .utility-note-table-row td.el-table__cell:first-child) {
  color: var(--text-main);
  font-weight: 600;
}

.dialog-footer {
  display: flex;
  align-items: center;
  width: 100%;
}

.dialog-footer__spacer {
  flex: 1;
}

@media (max-width: 768px) {
  .page-header,
  .utility-panel__header {
    flex-direction: column;
    align-items: stretch;
  }

  .page-header {
    justify-content: stretch;
  }

  .year-input {
    width: 100%;
  }

  .bill-image-field :deep(.el-form-item__content) {
    min-width: 0;
  }

  .bill-image-actions {
    display: grid;
    grid-template-columns: 1fr;
    gap: 10px;
    width: 100%;
  }

  .bill-image-actions :deep(.el-upload),
  .bill-image-actions :deep(.el-button) {
    width: 100%;
    margin-left: 0;
  }

  .bill-image-preview-wrap {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
    width: 100%;
  }

  .bill-image-box {
    min-width: 0;
  }

  .bill-image-box :deep(.el-button) {
    width: 100%;
  }

  .bill-image-thumb {
    width: 100%;
    aspect-ratio: 1 / 1;
    height: auto;
  }
}

.utility-bills-container--mobile {
  padding: 16px;
  border-radius: 16px;
}

.utility-bills-container--mobile .header-operations {
  width: 100%;
}

.utility-bills-container--mobile .header-operations > * {
  width: 100%;
}

.utility-bills-container--mobile .utility-panel {
  padding: 14px;
}

.utility-bills-container--mobile .utility-panel__header {
  gap: 10px;
}
</style>
