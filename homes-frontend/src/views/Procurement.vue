<template>
  <div class="page-container" :class="{ 'page-container--mobile': mobileMode }">
    <div class="page-header">
      <div v-if="mobileMode" class="procurement-mobile-overview">
        <div class="procurement-mobile-stat">
          <strong>{{ pagination.total }}</strong>
          <span>采购单数</span>
        </div>
        <div class="procurement-mobile-stat">
          <strong>{{ procurements.length }}</strong>
          <span>当前页</span>
        </div>
      </div>
      <div class="header-operations">
        <el-input
          class="search-input"
          v-model="searchQuery"
          placeholder="搜索采购物品、采购单号或备注"
          clearable
          @clear="handleSearch"
          @keyup.enter="handleSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button class="toolbar-btn" type="primary" @click="handleSearch">搜索</el-button>
        <el-button class="toolbar-btn" type="primary" @click="openDialog('add')">新增</el-button>
        <el-button class="toolbar-btn" type="primary" plain @click="openAiDialog">AI 输入</el-button>
        <el-button class="toolbar-btn" type="success" @click="linkDialogVisible = true">链接</el-button>
        <el-button v-if="!mobileMode" class="toolbar-btn" type="danger" :disabled="selectedProcurements.length === 0" @click="handleBatchDelete">删除</el-button>
        <el-dropdown v-if="!mobileMode" trigger="click" @command="handleExportCommand">
          <el-button class="toolbar-btn" type="success">
            导出 <el-icon style="margin-left:4px"><Filter /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="excel">导出为 Excel</el-dropdown-item>
              <el-dropdown-item command="template">导出录入模板</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-upload
          v-if="!mobileMode"
          action=""
          :auto-upload="false"
          :show-file-list="false"
          accept=".xlsx, .xls"
          :on-change="handleImportFile"
        >
          <el-button class="toolbar-btn" type="warning">导入</el-button>
        </el-upload>
      </div>
    </div>

    <!-- 表格区域 -->
    <div class="table-panel">
      <div v-if="mobileMode" class="procurement-mobile-list" v-loading="loading">
        <el-empty v-if="procurements.length === 0" description="暂无采购记录" :image-size="48" />
        <article v-for="row in procurements" :key="row.id || row.purchase_batch_no" class="procurement-mobile-card">
          <div class="procurement-mobile-card__header">
            <div>
              <div class="procurement-mobile-card__title">{{ row.purchase_batch_no || '未生成采购单号' }}</div>
              <div class="procurement-mobile-card__meta">{{ row.procurement_date || '-' }} · {{ row.purchase_channel || '未填写渠道' }}</div>
            </div>
            <strong class="procurement-mobile-card__amount">¥{{ Number(row.total_amount || 0).toFixed(2) }}</strong>
          </div>
          <div class="procurement-mobile-card__summary">{{ row.item_summary || '未填写采购物品' }}</div>
          <div class="procurement-mobile-card__detail">
            <span>条目 {{ row.item_count || 0 }}</span>
            <span>支付 {{ row.payment_person || '未填写' }}</span>
          </div>
          <div v-if="row.remarks" class="procurement-mobile-card__remark">{{ row.remarks }}</div>
          <div class="procurement-mobile-card__actions">
            <el-button size="small" @click="openViewDialog(row)">查看</el-button>
            <el-button
              size="small"
              type="primary"
              :disabled="(row.items || []).length !== 1"
              @click="openDialog('edit', (row.items || [])[0])"
            >
              编辑
            </el-button>
            <el-button size="small" type="danger" plain @click="handleDelete(row)">删除</el-button>
          </div>
        </article>
      </div>

      <el-table
        v-else
        class="procurement-table"
        v-loading="loading"
        :data="procurements"
        border
        style="width: 100%"
        @selection-change="handleSelectionChange"
      >
      <el-table-column type="selection" width="55" />
      <el-table-column label="序号" width="80" align="center">
        <template #default="{ $index }">
          {{ procurementRowStart + $index + 1 }}
        </template>
      </el-table-column>
      <el-table-column prop="procurement_date" label="时间" width="120" sortable />
      <el-table-column prop="purchase_channel" label="采购渠道" width="100" sortable />
      <el-table-column prop="purchase_batch_no" label="采购单号" min-width="160" show-overflow-tooltip sortable />
      <el-table-column prop="item_summary" label="采购物品" min-width="180" show-overflow-tooltip />
      <el-table-column prop="item_count" label="条目数" width="90" align="center" />
      <el-table-column prop="total_amount" label="总金额" width="120" align="right" sortable>
        <template #default="{ row }">
          ¥{{ row.total_amount }}
        </template>
      </el-table-column>
      <el-table-column prop="payment_person" label="支付人员" width="120" sortable />
      <el-table-column prop="remarks" label="备注" min-width="180" show-overflow-tooltip />
      <el-table-column label="操作" width="240" fixed="right" align="center">
        <template #default="{ row }">
          <div class="table-actions-row">
            <el-button size="small" @click="openViewDialog(row)">查看</el-button>
            <el-button
              size="small"
              type="primary"
              :disabled="(row.items || []).length !== 1"
              @click="openDialog('edit', (row.items || [])[0])"
            >
              编辑
            </el-button>
            <el-dropdown trigger="click">
              <el-button size="small">
                更多
                <el-icon style="margin-left: 4px"><MoreFilled /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="handleDelete(row)">
                    <span style="color: var(--el-color-danger);">删除</span>
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </template>
      </el-table-column>
      </el-table>
    </div>

    <!-- 分页区域 -->
    <div class="pagination-container">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        :layout="mobileMode ? 'total, prev, pager, next' : 'total, sizes, prev, pager, next, jumper'"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>

    <!-- 新增/编辑抽屉 -->
    <el-drawer
      :title="dialog.title"
      v-model="dialog.visible"
      direction="rtl"
      :size="mobileMode ? '100%' : '620px'"
      @close="resetForm"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
      >
        <el-form-item label="录入方式">
          <el-radio-group v-model="form.purchase_mode">
            <el-radio label="single">单个物品</el-radio>
            <el-radio label="multi">一单多物品</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="采购渠道" prop="purchase_channel">
          <el-radio-group v-model="form.purchase_channel">
            <el-radio label="线下">线下</el-radio>
            <el-radio label="线上">线上</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="时间" prop="procurement_date">
          <el-date-picker
            v-model="form.procurement_date"
            type="date"
            placeholder="选择日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <template v-if="form.purchase_mode === 'single'">
        <el-form-item label="采购物品" prop="item_name">
          <el-input v-model="form.item_name" placeholder="请输入采购物品名称" />
        </el-form-item>
        <el-form-item label="规格" prop="specification">
          <el-input v-model="form.specification" placeholder="请输入规格型号" />
        </el-form-item>
        <el-form-item label="数量" prop="quantity">
          <el-input-number v-model="form.quantity" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="单价" prop="unit_price">
          <el-input-number 
            v-model="form.unit_price" 
            :min="0" 
            :precision="2" 
            style="width: 100%"
            placeholder="请输入单价"
          />
        </el-form-item>
        <el-form-item label="单位" prop="unit">
          <el-input v-model="form.unit" placeholder="如：个、米、箱" />
        </el-form-item>
        </template>
        <el-form-item v-else label="采购物品明细" class="full-span">
          <div class="multi-item-wrap">
            <div
              v-for="(item, index) in form.items"
              :key="`proc-item-${index}`"
              class="multi-item-row"
            >
              <el-input v-model="item.item_name" placeholder="采购物品" />
              <el-input v-model="item.specification" placeholder="规格" />
              <el-input-number v-model="item.quantity" :min="1" style="width: 120px" />
              <el-input-number v-model="item.unit_price" :min="0" :precision="2" style="width: 140px" placeholder="单价(可空)" />
              <el-input v-model="item.unit" placeholder="单位" style="width: 120px" />
              <el-button type="danger" plain @click="removeProcurementItem(index)">删除</el-button>
            </div>
            <el-button type="primary" plain @click="addProcurementItem">添加物品</el-button>
            <div class="image-upload-tip">如果没有填写单价，系统才会把总金额按条目平均分摊到每个物品，并自动同步进库存。</div>
          </div>
        </el-form-item>
        <el-form-item label="总金额" prop="total_amount">
          <el-input-number 
            v-model="form.total_amount" 
            :min="0" 
            :precision="2" 
            style="width: 100%"
            placeholder="请输入总金额"
          />
        </el-form-item>
        <el-form-item label="支付人员" prop="payment_person">
          <el-input v-model="form.payment_person" placeholder="请输入支付人员" />
        </el-form-item>
        <el-form-item label="备注" prop="remarks">
          <el-input
            v-model="form.remarks"
            type="textarea"
            :rows="3"
            placeholder="请输入备注信息"
          />
        </el-form-item>
        <el-form-item label="图片" class="procurement-image-field">
          <div class="procurement-image-uploader">
            <div class="procurement-image-actions">
              <el-upload
                action=""
                :auto-upload="false"
                :show-file-list="false"
                accept="image/*"
                multiple
                :limit="30"
                :on-change="handleProcurementImageChange"
              >
                <el-button type="primary" plain>选择图片(最多30张)</el-button>
              </el-upload>
              <el-button
                v-if="form.procurement_images.length > 0"
                class="procurement-image-clear"
                type="danger"
                plain
                @click="clearAllProcurementImages"
              >
                全部删除图片
              </el-button>
            </div>
            <div class="upload-progress-text" v-if="uploadingProcurementImages">上传进度 {{ uploadProgress }}%</div>
            <div class="upload-progress-text">已选 {{ form.procurement_images.length }} / 30</div>
            <div v-if="form.procurement_images.length > 0" class="image-preview-wrap">
              <div v-for="(img, index) in form.procurement_images" :key="`${img}-${index}`" class="image-box">
                <el-image lazy loading="lazy"
                  class="image-thumb"
                  :src="toImageUrl(img)"
                  :preview-src-list="form.procurement_images.map((v) => toImageUrl(v))"
                  fit="cover"
                  preview-teleported
                />
                <el-button size="small" type="danger" plain @click="removeFormImage(index)">删除</el-button>
              </div>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialog.visible = false">取消</el-button>
          <el-button type="primary" :loading="dialog.submitting" @click="submitForm">
            确认
          </el-button>
        </span>
      </template>
    </el-drawer>

    <el-dialog
      title="采购详情"
      v-model="viewDialog.visible"
      :fullscreen="mobileMode"
      :width="mobileMode ? undefined : '760px'"
      class="app-themed-dialog procurement-view-dialog"
      modal-class="app-themed-dialog-overlay"
    >
      <template v-if="viewDialog.row">
        <el-descriptions :column="2" border class="procurement-view-descriptions">
          <el-descriptions-item label="时间">{{ viewDialog.row.procurement_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="采购渠道">{{ viewDialog.row.purchase_channel || '-' }}</el-descriptions-item>
          <el-descriptions-item label="采购单号">{{ viewDialog.row.purchase_batch_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="支付人员">{{ viewDialog.row.payment_person || '-' }}</el-descriptions-item>
          <el-descriptions-item label="总金额">¥{{ Number(viewDialog.row.total_amount || 0).toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="条目数">{{ viewDialogItems.length }}</el-descriptions-item>
          <el-descriptions-item label="备注" :span="2">{{ viewDialog.row.remarks || '-' }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="mobileMode" class="procurement-view-mobile-list">
          <article v-for="(item, index) in viewDialogItems" :key="item.id || index" class="procurement-view-mobile-card">
            <div class="procurement-view-mobile-card__title">{{ item.item_name || '未命名物品' }}</div>
            <div class="procurement-view-mobile-card__meta">{{ item.specification || '未填写规格' }}</div>
            <div class="procurement-view-mobile-card__meta">
              {{ item.quantity || 0 }}{{ item.unit || '' }} · ¥{{ Number(item.total_amount || 0).toFixed(2) }}
            </div>
            <div v-if="getProcurementImages(item).length > 0" class="view-image-list procurement-view-mobile-images">
              <el-image
                v-for="(img, imageIndex) in getProcurementImages(item)"
                :key="`${img}-${imageIndex}`"
                class="table-image-thumb"
                :src="toImageUrl(img)"
                :preview-src-list="getProcurementImages(item).map((v) => toImageUrl(v))"
                fit="cover"
                preview-teleported
              />
            </div>
          </article>
        </div>
        <el-table v-else :data="viewDialogItems" border size="small" class="procurement-view-table">
          <el-table-column prop="item_name" label="采购物品" min-width="150" />
          <el-table-column prop="specification" label="规格" width="120" />
          <el-table-column prop="quantity" label="数量" width="90" align="center" />
          <el-table-column label="单价" width="100" align="right">
            <template #default="{ row }">¥{{ Number(row.unit_price || 0).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column prop="unit" label="单位" width="90" align="center" />
          <el-table-column label="金额" width="110" align="right">
            <template #default="{ row }">¥{{ Number(row.total_amount || 0).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column label="图片" min-width="180">
            <template #default="{ row }">
              <div v-if="getProcurementImages(row).length > 0" class="view-image-list">
                <el-image
                  v-for="(img, index) in getProcurementImages(row)"
                  :key="`${img}-${index}`"
                  class="table-image-thumb"
                  :src="toImageUrl(img)"
                  :preview-src-list="getProcurementImages(row).map((v) => toImageUrl(v))"
                  fit="cover"
                  preview-teleported
                />
              </div>
              <span v-else>-</span>
            </template>
          </el-table-column>
        </el-table>
      </template>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="viewDialog.visible = false">关闭</el-button>
        </span>
      </template>
    </el-dialog>

    <el-dialog
      title="AI 输入采购"
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
            placeholder="例如：今天线下买了 10 个 LED 灯泡，12W，单价 8.5 元，王会计付款。也可以上传收据、发票或购物截图让 AI 识别。"
          />
        </el-form-item>
        <el-form-item label="图片识别">
          <el-upload
            action=""
            :auto-upload="false"
            :show-file-list="false"
            accept="image/*"
            multiple
            :limit="20"
            :on-change="handleAiImageChange"
          >
            <el-button type="primary" plain>选择图片</el-button>
          </el-upload>
          <el-button
            v-if="aiDialog.images.length"
            style="margin-left: 8px"
            type="danger"
            plain
            @click="clearAiImages"
          >
            清空图片
          </el-button>
          <div class="upload-progress-text">已选 {{ aiDialog.images.length }} / 20</div>
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

  <BusinessPublicLinkDialog
    v-model="linkDialogVisible"
    business-type="procurement"
    title="采购填写链接"
    business-label="采购管理"
  />
</template>

<script setup>
import { computed, ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { procurementApi } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Filter, MoreFilled } from '@element-plus/icons-vue'
import * as XLSX from 'xlsx'
import { uploadFileByChunks } from '../utils/chunkUploader'
import BusinessPublicLinkDialog from '../components/BusinessPublicLinkDialog.vue'
import { DISPLAY_MODE_EVENT, getPreferredDisplayMode } from '../utils/displayMode'

// 状态定义
const loading = ref(false)
const linkDialogVisible = ref(false)
const mobileMode = ref(false)
const procurements = ref([])
const selectedProcurements = ref([])
const searchQuery = ref('')
const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})
const procurementRowStart = computed(() => (pagination.page - 1) * pagination.pageSize)
const viewDialogItems = computed(() => {
  const row = viewDialog.row
  if (!row) return []
  return Array.isArray(row.items) && row.items.length > 0 ? row.items : [row]
})
const syncDisplayMode = () => {
  mobileMode.value = getPreferredDisplayMode() === 'mobile'
}

const dialog = reactive({
  visible: false,
  title: '新增采购',
  type: 'add', // 'add' or 'edit'
  submitting: false
})
const viewDialog = reactive({
  visible: false,
  row: null
})
const aiDialog = reactive({
  visible: false,
  loading: false,
  text: '',
  images: []
})
const procurementImageFiles = ref([])
const uploadingProcurementImages = ref(false)
const uploadProgress = ref(0)
const MAX_PROCUREMENT_IMAGES = 30
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'
const API_ORIGIN = API_BASE.replace(/\/api\/?$/, '')

const formRef = ref(null)
const form = reactive({
  id: null,
  purchase_mode: 'single',
  purchase_channel: '线下',
  procurement_date: '',
  item_name: '',
  specification: '',
  quantity: 1,
  unit_price: 0,
  unit: '',
  total_amount: 0,
  payment_person: '',
  remarks: '',
  procurement_images: [],
  items: [],
})

const todayText = () => new Date().toISOString().split('T')[0]

const toImageUrl = (value) => {
  if (!value) return ''
  const text = String(value)
  if (text.startsWith('http://') || text.startsWith('https://') || text.startsWith('blob:') || text.startsWith('data:')) {
    return text
  }
  if (text.startsWith('/')) return `${API_ORIGIN}${text}`
  return `${API_ORIGIN}/${text}`
}

const parseProcurementImages = (record) => {
  if (record?.procurement_images && Array.isArray(record.procurement_images)) {
    return record.procurement_images.map(v => String(v)).filter(v => v.trim() !== '').slice(0, MAX_PROCUREMENT_IMAGES)
  }
  const raw = record?.procurement_image ? String(record.procurement_image) : ''
  if (!raw.trim()) return []
  if (raw.trim().startsWith('[')) {
    try {
      const arr = JSON.parse(raw)
      if (Array.isArray(arr)) {
        return arr.map(v => String(v)).filter(v => v.trim() !== '').slice(0, MAX_PROCUREMENT_IMAGES)
      }
    } catch (_) {}
  }
  return [raw]
}

const getProcurementImages = (record) => parseProcurementImages(record)

const rules = {
  procurement_date: [{ required: true, message: '请选择时间', trigger: 'change' }],
  purchase_channel: [{ required: true, message: '请选择采购渠道', trigger: 'change' }],
  item_name: [{ required: true, message: '请输入采购物品', trigger: 'blur' }],
  quantity: [{ required: true, message: '请输入数量', trigger: 'blur' }],
  unit_price: [{ required: true, message: '请输入单价', trigger: 'blur' }],
  unit: [{ required: true, message: '请输入单位', trigger: 'blur' }],
  total_amount: [{ required: true, message: '请输入总金额', trigger: 'blur' }]
}

const revokeProcurementPreviewUrls = () => {
  for (const item of procurementImageFiles.value) {
    const url = String(item?.url || '')
    if (url.startsWith('blob:')) {
      URL.revokeObjectURL(url)
    }
  }
}

const buildProcurementUploadSubDir = (targetId) => {
  const safe = String(targetId || 'new').replace(/[^0-9A-Za-z_-]/g, '_')
  return `record_${safe || 'new'}`
}

const resetProcurementFormForAdd = () => {
  Object.assign(form, {
    id: null,
    purchase_mode: 'single',
    purchase_channel: '线下',
    procurement_date: todayText(),
    item_name: '',
    specification: '',
    quantity: 1,
    unit_price: 0,
    unit: '',
    total_amount: 0,
    payment_person: '',
    remarks: '',
    procurement_images: [],
    items: [{ item_name: '', specification: '', quantity: 1, unit_price: 0, unit: '' }]
  })
}

// 获取数据
const fetchProcurements = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      search: searchQuery.value,
      grouped: 'order'
    }
    const res = await procurementApi.listProcurements(params)
    procurements.value = res.data.procurement_orders || []
    pagination.total = res.data.total
  } catch (error) {
    ElMessage.error('获取采购列表失败')
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  pagination.page = 1
  fetchProcurements()
}

// 分页
const handleSizeChange = (val) => {
  pagination.pageSize = val
  fetchProcurements()
}

const handleCurrentChange = (val) => {
  pagination.page = val
  fetchProcurements()
}

const handleSelectionChange = (rows) => {
  selectedProcurements.value = rows || []
}

// 打开对话框
const openDialog = (type, row = null) => {
  dialog.type = type
  dialog.title = type === 'add' ? '新增采购' : '编辑采购'
  dialog.visible = true

  revokeProcurementPreviewUrls()
  procurementImageFiles.value = []
  uploadingProcurementImages.value = false
  uploadProgress.value = 0
  if (type === 'edit' && row) {
    Object.assign(form, { ...row, purchase_mode: 'single', procurement_images: parseProcurementImages(row), items: [] })
  } else {
    resetProcurementFormForAdd()
  }
}

const openViewDialog = (row) => {
  if (!row) return
  viewDialog.row = row
  viewDialog.visible = true
}

// 重置表单
const resetForm = () => {
  if (formRef.value) {
    formRef.value.resetFields()
  }
  revokeProcurementPreviewUrls()
  procurementImageFiles.value = []
  uploadingProcurementImages.value = false
  uploadProgress.value = 0
}

const addProcurementItem = () => {
  form.items.push({ item_name: '', specification: '', quantity: 1, unit_price: 0, unit: '' })
}

const removeProcurementItem = (index) => {
  if (form.items.length <= 1) return
  form.items.splice(index, 1)
}

const handleProcurementImageChange = (file) => {
  if (!file || !file.raw) return
  if (form.procurement_images.length >= MAX_PROCUREMENT_IMAGES) {
    ElMessage.warning(`最多上传${MAX_PROCUREMENT_IMAGES}张图片`)
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
  procurementImageFiles.value.push({ file: file.raw, url })
  form.procurement_images.push(url)
}

const removeFormImage = (index) => {
  if (index < 0 || index >= form.procurement_images.length) return
  const target = form.procurement_images[index]
  form.procurement_images.splice(index, 1)

  procurementImageFiles.value = procurementImageFiles.value.filter(item => item.url !== target)
  if (String(target || '').startsWith('blob:')) {
    URL.revokeObjectURL(String(target))
  }
}

const clearAllProcurementImages = () => {
  form.procurement_images.forEach((target) => {
    if (String(target || '').startsWith('blob:')) {
      URL.revokeObjectURL(String(target))
    }
  })
  form.procurement_images = []
  procurementImageFiles.value = []
}

const revokeAiImageUrls = () => {
  aiDialog.images.forEach((item) => {
    if (String(item?.url || '').startsWith('blob:')) {
      URL.revokeObjectURL(item.url)
    }
  })
}

const resetAiDialog = () => {
  revokeAiImageUrls()
  aiDialog.loading = false
  aiDialog.text = ''
  aiDialog.images = []
}

const openAiDialog = () => {
  resetAiDialog()
  aiDialog.visible = true
}

const handleAiImageChange = (file) => {
  if (!file || !file.raw) return
  if (aiDialog.images.length >= 20) {
    ElMessage.warning('最多选择 20 张图片')
    return
  }
  if (!String(file.raw.type || '').startsWith('image/')) {
    ElMessage.warning('请上传图片文件')
    return
  }
  if (file.raw.size && file.raw.size > 8 * 1024 * 1024) {
    ElMessage.warning('单张图片请控制在 8MB 以内')
    return
  }
  aiDialog.images.push({
    file: file.raw,
    url: URL.createObjectURL(file.raw)
  })
}

const removeAiImage = (index) => {
  const item = aiDialog.images[index]
  if (!item) return
  if (String(item.url || '').startsWith('blob:')) {
    URL.revokeObjectURL(item.url)
  }
  aiDialog.images.splice(index, 1)
}

const clearAiImages = () => {
  revokeAiImageUrls()
  aiDialog.images = []
}

const applyAiDraftToForm = (draft = {}) => {
  const items = Array.isArray(draft.items) ? draft.items : []
  const normalizedItems = items
    .map(item => ({
      item_name: String(item?.item_name || '').trim(),
      specification: String(item?.specification || '').trim(),
      quantity: Number(item?.quantity || 1),
      unit_price: Number(item?.unit_price || 0),
      unit: String(item?.unit || '个').trim(),
    }))
    .filter(item => item.item_name)

  openDialog('add')
  form.purchase_channel = draft.purchase_channel === '线上' ? '线上' : '线下'
  form.procurement_date = String(draft.procurement_date || todayText())
  form.total_amount = Number(draft.total_amount || 0)
  form.payment_person = String(draft.payment_person || '')
  form.remarks = String(draft.remarks || '')

  if (normalizedItems.length > 1) {
    form.purchase_mode = 'multi'
    form.items = normalizedItems
    form.item_name = normalizedItems.map(item => item.item_name).join('、')
    form.specification = ''
    form.quantity = 1
    form.unit_price = 0
    form.unit = normalizedItems[0]?.unit || '个'
  } else {
    const item = normalizedItems[0] || {}
    form.purchase_mode = 'single'
    form.item_name = item.item_name || ''
    form.specification = item.specification || ''
    form.quantity = Number(item.quantity || 1)
    form.unit_price = Number(item.unit_price || 0)
    form.unit = item.unit || '个'
    form.items = [{ item_name: '', specification: '', quantity: 1, unit_price: 0, unit: '' }]
    if (!form.total_amount && form.quantity > 0 && form.unit_price > 0) {
      form.total_amount = Number((form.quantity * form.unit_price).toFixed(2))
    }
  }
}

const submitAiDraft = async () => {
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
    const response = await procurementApi.createAiDraft(formData)
    applyAiDraftToForm(response?.data?.draft || {})
    aiDialog.visible = false
    ElMessage.success('AI 草稿已填入采购表单，请确认后保存')
  } catch (error) {
    const message = error?.response?.data?.error || error?.message || 'AI 输入失败'
    ElMessage.error(message)
  } finally {
    aiDialog.loading = false
  }
}

// 提交表单
const submitForm = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    dialog.submitting = true
    try {
      const payload = {
        procurement_date: form.procurement_date,
        purchase_channel: form.purchase_channel,
        item_name: form.item_name,
        specification: form.specification,
        quantity: Number(form.quantity || 0),
        unit_price: Number(form.unit_price || 0),
        unit: form.unit,
        total_amount: Number(form.total_amount || 0),
        payment_person: form.payment_person,
        remarks: form.remarks,
        procurement_images: (form.procurement_images || []).filter(v => typeof v === 'string' && !v.startsWith('blob:')).slice(0, 20)
      }

      if (dialog.type === 'add' && form.purchase_mode === 'multi') {
        payload.items = (form.items || [])
          .map(item => ({
            item_name: String(item.item_name || '').trim(),
            specification: String(item.specification || '').trim(),
            quantity: Number(item.quantity || 0),
            unit_price: Number(item.unit_price || 0),
            unit: String(item.unit || '').trim(),
          }))
          .filter(item => item.item_name && item.quantity > 0 && item.unit)
        if (!payload.items.length) {
          ElMessage.error('请至少填写一条采购物品明细')
          dialog.submitting = false
          return
        }

        const calculatedTotalAmount = Number(
          payload.items
            .reduce((sum, item) => sum + (Number(item.quantity || 0) * Number(item.unit_price || 0)), 0)
            .toFixed(2)
        )
        if (calculatedTotalAmount > 0) {
          payload.total_amount = calculatedTotalAmount
          form.total_amount = calculatedTotalAmount
        }
      }

      let targetIds = form.id ? [form.id] : []
      if (dialog.type === 'add') {
        const created = await procurementApi.createProcurement(payload)
        targetIds = Array.isArray(created?.data?.ids) && created.data.ids.length > 0
          ? created.data.ids
          : [created?.data?.id].filter(Boolean)
      } else {
        await procurementApi.updateProcurement(form.id, payload)
      }

      if (targetIds.length > 0 && procurementImageFiles.value.length > 0) {
        uploadingProcurementImages.value = true
        uploadProgress.value = 0
        const uploadedUrls = []
        const total = procurementImageFiles.value.length

        for (let i = 0; i < total; i++) {
          const item = procurementImageFiles.value[i]
          const result = await uploadFileByChunks(item.file, {
            category: 'procurements',
            subDir: buildProcurementUploadSubDir(targetIds[0]),
            chunkSize: 1024 * 1024,
            maxRetries: 3,
            retryDelay: 800,
            onProgress: (percent) => {
              const finished = i + (Number(percent || 0) / 100)
              uploadProgress.value = Math.floor((finished / total) * 100)
            }
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

        const finalImages = [...payload.procurement_images, ...uploadedUrls]
          .map(v => String(v || '').trim())
          .filter(v => v)
          .slice(0, 20)

        await Promise.all(
          targetIds.map(id => procurementApi.updateProcurementImages(id, { procurement_images: finalImages }))
        )
        form.procurement_images = finalImages
        uploadProgress.value = 100
      }

      procurementImageFiles.value = []
      uploadingProcurementImages.value = false
      uploadProgress.value = 0
      dialog.visible = false
      ElMessage.success(dialog.type === 'add' ? '新增成功' : '更新成功')
      fetchProcurements()
    } catch (error) {
      console.error(error)
      const message = error?.response?.data?.error || error?.message || (dialog.type === 'add' ? '新增失败' : '更新失败')
      ElMessage.error(message)
    } finally {
      dialog.submitting = false
    }
  })
}

// 删除
const handleDelete = (row) => {
  const detailRows = Array.isArray(row?.items) && row.items.length > 0 ? row.items : [row]
  const summaryName = detailRows.length > 1
    ? `采购单 ${row.purchase_batch_no || ''}（共${detailRows.length}项）`
    : `项目：${detailRows[0]?.item_name || ''}`
  ElMessageBox.confirm(
    `确定要删除${summaryName}吗？`,
    '警告',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      for (const detail of detailRows) {
        await procurementApi.deleteProcurement(detail.id)
      }
      ElMessage.success('删除成功')
      fetchProcurements()
    } catch (error) {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

const handleBatchDelete = async () => {
  if (!selectedProcurements.value.length) return
  const deleteTargets = selectedProcurements.value.flatMap(row => Array.isArray(row?.items) && row.items.length > 0 ? row.items : [row])
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedProcurements.value.length} 个采购单吗？`,
      '删除确认',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    loading.value = true
    let successCount = 0
    const failures = []
    for (const row of deleteTargets) {
      try {
        await procurementApi.deleteProcurement(row.id)
        successCount++
      } catch (error) {
        failures.push(`${row.item_name}(ID:${row.id})`)
      }
    }
    await fetchProcurements()
    selectedProcurements.value = []
    if (failures.length === 0) {
      ElMessage.success(`删除完成：成功 ${successCount} 条`)
    } else {
      ElMessage.error(`删除完成：成功 ${successCount} 条，失败 ${failures.length} 条`)
    }
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('删除失败')
    }
  } finally {
    loading.value = false
  }
}

// 导出 Excel
const handleExportCommand = (cmd) => {
  const flatRows = procurements.value.flatMap(row => row.items || [])
  if (cmd === 'excel') {
    try {
      const headers = ['ID', '时间', '采购渠道', '采购单号', '采购物品', '规格', '数量', '单价', '单位', '总金额', '支付人员', '备注', '图片']
      const rows = flatRows.map(p => ({
        ID: p.id,
        时间: p.procurement_date,
        采购渠道: p.purchase_channel,
        采购单号: p.purchase_batch_no,
        采购物品: p.item_name,
        规格: p.specification,
        数量: p.quantity,
        单价: p.unit_price,
        单位: p.unit,
        总金额: p.total_amount,
        支付人员: p.payment_person,
        备注: p.remarks,
        图片: getProcurementImages(p).join(',')
      }))
      const ws = XLSX.utils.json_to_sheet(rows, { header: headers })
      if (rows.length === 0) {
        XLSX.utils.sheet_add_aoa(ws, [headers], { origin: 'A1' })
      }
      const wb = XLSX.utils.book_new()
      XLSX.utils.book_append_sheet(wb, ws, '采购记录')
      XLSX.writeFile(wb, `采购记录_${new Date().toLocaleDateString()}.xlsx`)
      ElMessage.success('导出成功')
    } catch (e) {
      console.error(e)
      ElMessage.error('导出失败')
    }
    return
  }

  if (cmd === 'template') {
    try {
      const headers = ['ID', '时间', '采购渠道', '采购单号', '采购物品', '规格', '数量', '单价', '单位', '总金额', '支付人员', '备注', '图片']
      const exampleRows = [
        {
          ID: '',
          时间: '2026-04-26',
          采购渠道: '线下',
          采购单号: '系统自动生成',
          采购物品: 'LED灯泡',
          规格: '12W暖白',
          数量: 6,
          单价: 10,
          单位: '盏',
          总金额: 60,
          支付人员: '王会计',
          备注: '单个物品案例',
          图片: '',
        },
        {
          ID: '',
          时间: '',
          采购渠道: '',
          采购单号: '',
          采购物品: '',
          规格: '',
          数量: '',
          单价: '',
          单位: '',
          总金额: '',
          支付人员: '',
          备注: '',
          图片: '',
        },
        {
          ID: '',
          时间: '2026-04-26',
          采购渠道: '线下',
          采购单号: '系统自动生成（同单）',
          采购物品: '电线（红色）',
          规格: '1.5平方50m',
          数量: 1,
          单价: '',
          单位: '卷',
          总金额: 256,
          支付人员: '王会计',
          备注: '一单多物品案例：与下面两条属于同一采购单',
          图片: '',
        },
        {
          ID: '',
          时间: '2026-04-26',
          采购渠道: '线下',
          采购单号: '系统自动生成（同单）',
          采购物品: '电线（蓝色）',
          规格: '1.5平方50m',
          数量: 1,
          单价: '',
          单位: '卷',
          总金额: '',
          支付人员: '王会计',
          备注: '一单多物品案例：与上面/下面条目同单',
          图片: '',
        },
        {
          ID: '',
          时间: '2026-04-26',
          采购渠道: '线下',
          采购单号: '系统自动生成（同单）',
          采购物品: '电线（地线）',
          规格: '1.5平方50m',
          数量: 1,
          单价: '',
          单位: '卷',
          总金额: '',
          支付人员: '王会计',
          备注: '一单多物品案例：与上面两条同单',
          图片: '',
        },
      ]

      const ws = XLSX.utils.json_to_sheet(exampleRows, { header: headers })
      const wb = XLSX.utils.book_new()
      XLSX.utils.book_append_sheet(wb, ws, '采购录入模板')
      XLSX.writeFile(wb, '采购录入模板_含案例.xlsx')
      ElMessage.success('模板导出成功')
    } catch (e) {
      console.error(e)
      ElMessage.error('模板导出失败')
    }
  }
}

// 导入 Excel
const handleImportFile = async (file) => {
  const reader = new FileReader()
  reader.onload = async (e) => {
    try {
      const data = new Uint8Array(e.target.result)
      const workbook = XLSX.read(data, { type: 'array' })
      const firstSheetName = workbook.SheetNames[0]
      const worksheet = workbook.Sheets[firstSheetName]
      const results = XLSX.utils.sheet_to_json(worksheet)
      
      let successCount = 0
      for (const row of results) {
        // 简单映射，假设列名匹配
        const payload = {
          procurement_date: row['采购日期'] || row['时间'] || new Date().toISOString().split('T')[0],
          purchase_channel: row['采购渠道'] || '线下',
          item_name: row['采购项目'] || row['采购物品'] || row['维修项目'] || '',
          specification: row['规格'] || '',
          quantity: Number(row['数量'] || 1),
          unit_price: Number(row['单价'] || 0),
          unit: row['单位'] || '',
          total_amount: Number(row['总金额'] || 0),
          payment_person: row['支付人员'] || '',
          remarks: row['备注'] || '',
          procurement_images: String(row['图片'] || '').trim() ? String(row['图片']).split(',').map(v => String(v).trim()).filter(v => v) : []
        }
        
        if (payload.item_name) {
          await procurementApi.createProcurement(payload)
          successCount++
        }
      }
      
      ElMessage.success(`成功导入 ${successCount} 条记录`)
      fetchProcurements()
    } catch (error) {
      console.error(error)
      ElMessage.error('导入失败，请检查文件格式')
    }
  }
  reader.readAsArrayBuffer(file.raw)
}

onMounted(() => {
  syncDisplayMode()
  window.addEventListener(DISPLAY_MODE_EVENT, syncDisplayMode)
  fetchProcurements()
})

onBeforeUnmount(() => {
  window.removeEventListener(DISPLAY_MODE_EVENT, syncDisplayMode)
})
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  margin-bottom: 18px;
}

.page-container {
  background: var(--card-bg);
  border: 1px solid var(--surface-border);
  border-radius: 18px;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
}

.page-container--mobile {
  padding: 16px;
}

.procurement-mobile-overview {
  display: flex;
  gap: 10px;
  width: 100%;
}

.procurement-mobile-stat {
  flex: 1;
  padding: 12px 14px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.12), rgba(20, 184, 166, 0.12));
  border: 1px solid rgba(37, 99, 235, 0.12);
}

.procurement-mobile-stat strong {
  display: block;
  font-size: 18px;
  color: var(--text-main);
}

.procurement-mobile-stat span {
  display: block;
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: 12px;
}

.header-operations {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.search-input {
  width: 240px;
}

.toolbar-btn {
  margin-left: 0 !important;
}

.table-panel {
  background: var(--card-bg);
  border: 1px solid var(--surface-border);
  border-radius: 16px;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
  padding: 10px 10px 16px;
}

.procurement-mobile-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.procurement-mobile-card {
  padding: 14px;
  border-radius: 16px;
  border: 1px solid var(--surface-border);
  background: var(--card-bg);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
}

.procurement-mobile-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.procurement-mobile-card__title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-main);
}

.procurement-mobile-card__meta,
.procurement-mobile-card__detail {
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: 12px;
}

.procurement-mobile-card__amount {
  color: var(--el-color-primary);
  font-size: 16px;
}

.procurement-mobile-card__summary {
  margin-top: 12px;
  color: var(--text-main);
  font-size: 14px;
  line-height: 1.6;
}

.procurement-mobile-card__detail {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.procurement-mobile-card__remark {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(148, 163, 184, 0.12);
  color: var(--text-secondary);
  font-size: 13px;
}

.procurement-mobile-card__actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.procurement-mobile-card__actions :deep(.el-button) {
  flex: 1;
}

.pagination-container {
  margin-top: 16px;
  display: flex;
  justify-content: center;
  padding-top: 12px;
  border-top: 1px solid var(--surface-border);
}

:deep(.procurement-table) {
  --el-table-header-bg-color: var(--surface-muted);
  --el-table-tr-bg-color: var(--card-bg);
  --el-table-bg-color: var(--card-bg);
  --el-fill-color-blank: var(--card-bg);
  --el-table-row-hover-bg-color: rgba(37, 99, 235, 0.06);
  --el-table-border-color: var(--surface-border);
  border-radius: 12px;
  overflow: hidden;
}

:deep(.procurement-table .el-table__header-wrapper th.el-table__cell) {
  font-weight: 700;
  color: var(--text-main);
  height: 48px;
}

:deep(.procurement-table .el-table__body-wrapper td.el-table__cell) {
  padding: 12px 0;
}

:deep(.procurement-table .el-table__expand-column),
:deep(.procurement-table .el-table__expand-column .cell),
:deep(.procurement-table .el-table__expand-icon) {
  width: 0 !important;
  min-width: 0 !important;
  padding: 0 !important;
  margin: 0 !important;
  overflow: hidden !important;
  border: none !important;
}

.table-actions-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  flex-wrap: nowrap;
  white-space: nowrap;
}

.table-image-thumb {
  width: 40px;
  height: 40px;
  border-radius: 6px;
}

.procurement-view-descriptions {
  margin-bottom: 4px;
}

.procurement-view-descriptions :deep(.el-descriptions__body) {
  background: var(--card-bg);
  color: var(--text-main);
}

.procurement-view-descriptions :deep(.el-descriptions__cell) {
  border-color: var(--surface-border) !important;
}

.procurement-view-descriptions :deep(.el-descriptions__label) {
  background: var(--surface-muted) !important;
  color: var(--text-regular);
  font-weight: 700;
}

.procurement-view-descriptions :deep(.el-descriptions__content) {
  background: var(--card-bg) !important;
  color: var(--text-main);
}

:deep(.procurement-view-table) {
  --el-table-header-bg-color: var(--surface-muted);
  --el-table-tr-bg-color: var(--card-bg);
  --el-table-bg-color: var(--card-bg);
  --el-fill-color-blank: var(--card-bg);
  --el-table-row-hover-bg-color: rgba(37, 99, 235, 0.06);
  --el-table-border-color: var(--surface-border);
  margin-top: 16px;
  width: 100%;
  border-radius: 10px;
  overflow: hidden;
}

:deep(.procurement-view-table .el-table__header-wrapper th.el-table__cell) {
  background: var(--surface-muted);
  color: var(--text-regular);
  font-weight: 700;
}

:deep(.procurement-view-table .el-table__body-wrapper td.el-table__cell) {
  background: var(--card-bg);
  color: var(--text-main);
}

.procurement-view-mobile-list {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.procurement-view-mobile-card {
  padding: 12px;
  border-radius: 12px;
  border: 1px solid var(--surface-border);
  background: var(--surface-muted);
}

.procurement-view-mobile-card__title {
  font-weight: 700;
  color: var(--text-main);
}

.procurement-view-mobile-card__meta {
  margin-top: 4px;
  font-size: 13px;
  color: var(--text-secondary);
}

.view-image-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.procurement-view-mobile-images {
  margin-top: 10px;
}

.upload-progress-text {
  margin-top: 8px;
  color: #64748b;
  font-size: 12px;
}

.procurement-image-uploader {
  width: 100%;
  min-width: 0;
}

.procurement-image-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.image-preview-wrap {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.ai-image-list {
  width: 100%;
  margin-top: 10px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.ai-image-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ai-image-thumb {
  width: 88px;
  height: 88px;
  border-radius: 8px;
  border: 1px solid var(--surface-border);
}

.full-span {
  width: 100%;
}

.multi-item-wrap {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.multi-item-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  align-items: start;
  padding: 12px;
  border: 1px solid var(--surface-border);
  border-radius: 12px;
  background: var(--surface-muted);
}

.multi-item-row :deep(.el-button) {
  width: fit-content;
}

.image-box {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.image-thumb {
  width: 92px;
  height: 92px;
  border-radius: 8px;
}

:deep(.procurement-table .el-table__fixed-right::before),
:deep(.procurement-table .el-table__fixed::before) {
  background-color: transparent;
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }

  .search-input {
    width: 100%;
  }

  .header-operations {
    width: 100%;
  }

  .header-operations :deep(.el-input),
  .header-operations :deep(.el-button) {
    flex: 1 1 calc(50% - 5px);
  }

  .procurement-image-field :deep(.el-form-item__content) {
    min-width: 0;
  }

  .procurement-image-actions {
    display: grid;
    grid-template-columns: 1fr;
    gap: 10px;
    width: 100%;
  }

  .procurement-image-actions :deep(.el-upload),
  .procurement-image-actions :deep(.el-button) {
    width: 100%;
    margin-left: 0;
  }

  .image-preview-wrap {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
    width: 100%;
  }

  .image-box {
    min-width: 0;
  }

  .image-box :deep(.el-button) {
    width: 100%;
  }

  .image-thumb {
    width: 100%;
    aspect-ratio: 1 / 1;
    height: auto;
  }
}
</style>
