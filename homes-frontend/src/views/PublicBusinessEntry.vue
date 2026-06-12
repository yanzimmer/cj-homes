<template>
  <div class="public-page">
    <div class="public-theme-toggle">
      <ThemeModeSwitch floating />
    </div>
    <div class="public-card">
      <div class="header">
        <h2>{{ currentConfig.title }}</h2>
        <p>{{ currentConfig.subtitle }}</p>
      </div>

      <div v-if="loading" class="loading-state">正在加载链接信息...</div>
      <el-alert v-else-if="error" :title="error" type="error" show-icon :closable="false" />

      <div v-else class="entry-wrap">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="entry-form">
        <template v-if="businessType === 'repair'">
          <el-form-item label="AI 输入" class="full-span">
            <div class="image-upload-row">
              <el-button type="primary" plain @click="openAiDialog">AI 输入</el-button>
              <span class="image-upload-tip">支持文字、现场照片或报修截图识别，生成后会填入下方表单。</span>
            </div>
          </el-form-item>
          <el-form-item label="维修范围" prop="scope_type">
            <el-select v-model="form.scope_type" placeholder="请选择维修范围" @change="handlePublicRepairScopeChange">
              <el-option v-for="item in REPAIR_SCOPE_OPTIONS" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="form.scope_type !== '单个房间'" label="楼栋" prop="building">
            <el-select
              v-model="form.building"
              placeholder="请选择涉及楼栋"
              multiple
              filterable
              allow-create
              default-first-option
              clearable
            >
              <el-option
                v-for="item in repairBuildingOptions"
                :key="item"
                :label="item"
                :value="item"
              />
            </el-select>
          </el-form-item>
          <el-form-item v-else label="楼栋" prop="building">
            <el-select
              v-model="form.building"
              placeholder="请选择或手动输入楼栋"
              filterable
              allow-create
              default-first-option
              clearable
              @change="handleRepairBuildingChange"
            >
              <el-option
                v-for="item in repairBuildingOptions"
                :key="item"
                :label="item"
                :value="item"
              />
            </el-select>
          </el-form-item>
          <el-form-item v-if="form.scope_type === '单个房间'" label="房间号" prop="room_no">
            <el-select
              v-model="form.room_no"
              placeholder="请选择或手动输入房间号"
              filterable
              allow-create
              default-first-option
              clearable
            >
              <el-option
                v-for="item in filteredRepairRoomOptions"
                :key="`${item.building}-${item.room_no}`"
                :label="item.room_no"
                :value="item.room_no"
              />
            </el-select>
          </el-form-item>
          <el-form-item v-else-if="form.scope_type === '多个房间'" label="多个房间号" prop="room_nos">
            <el-input v-model="form.room_nos" type="textarea" :rows="2" placeholder="请输入多个房间号，例如：B-502，B-503" />
          </el-form-item>
          <el-form-item label="维修类型" prop="repair_type">
            <el-select v-model="form.repair_type" placeholder="请选择维修类型">
              <el-option label="水电维修" value="水电维修" />
              <el-option label="家具维修" value="家具维修" />
              <el-option label="电器维修" value="电器维修" />
              <el-option label="清洁费用" value="清洁费用" />
              <el-option label="其他" value="其他" />
            </el-select>
          </el-form-item>
          <el-form-item label="问题描述" prop="description" class="full-span"><el-input v-model="form.description" type="textarea" :rows="4" /></el-form-item>
          <el-form-item label="图片" class="full-span">
            <input ref="imageInputRef" type="file" accept="image/*" multiple class="hidden-file-input" @change="handleImageChange" />
            <div class="image-upload-row">
              <el-button type="primary" plain @click="openImageDialog">选择图片(最多30张)</el-button>
              <el-button v-if="form.images.length > 0" type="danger" plain @click="clearAllImages">全部删除图片</el-button>
              <span class="image-upload-tip">支持多张图片，最多 30 张，提交时会作为维修图片保存。</span>
            </div>
            <el-progress v-if="uploading" :percentage="uploadProgress" :stroke-width="8" />
            <div class="image-upload-tip">已选：{{ form.images.length }} / 30</div>
            <div v-if="form.images.length" class="image-list">
              <div v-for="(img, index) in form.images" :key="`${img}-${index}`" class="image-item">
                <img :src="resolveImageUrl(img)" class="image-thumb" />
                <el-button size="small" type="danger" plain @click="removeImage(index)">删除</el-button>
              </div>
            </div>
          </el-form-item>
          <el-form-item label="报修日期" prop="report_date"><el-date-picker v-model="form.report_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
          <el-form-item label="报修人" prop="report_by">
            <el-select
              v-model="form.report_by"
              placeholder="请选择租户名或手动输入"
              filterable
              allow-create
              default-first-option
              clearable
            >
              <el-option
                v-for="name in tenantNameOptions"
                :key="name"
                :label="name"
                :value="name"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="状态" prop="status">
            <el-select v-model="form.status" placeholder="请选择状态">
              <el-option label="待处理" value="待处理" />
              <el-option label="处理中" value="处理中" />
              <el-option label="已完成" value="已完成" />
            </el-select>
          </el-form-item>
          <el-form-item label="维修日期"><el-date-picker v-model="form.repair_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
          <el-form-item label="金额"><el-input-number v-model="form.amount" :min="0" :precision="2" :step="10" style="width: 100%" /></el-form-item>
          <el-form-item label="使用库存" class="full-span">
            <div class="image-list">
              <div
                v-for="(usage, index) in form.inventory_usages"
                :key="`public-usage-${index}`"
                class="inventory-usage-row"
              >
                <el-select
                  v-model="usage.warehouse_item_id"
                  placeholder="输入库存物品名称后自动筛选"
                  style="width: 100%"
                  filterable
                  clearable
                  default-first-option
                  reserve-keyword="false"
                >
                  <el-option
                    v-for="item in inventoryOptions"
                    :key="item.id"
                    :label="`${item.item_name}${item.specification ? ` / ${item.specification}` : ''} / 库存 ${item.quantity}${item.unit || ''}`"
                    :value="item.id"
                  />
                </el-select>
                <el-input-number v-model="usage.quantity" :min="1" :precision="2" style="width: 140px" />
                <el-button size="small" type="danger" plain @click="removeInventoryUsage(index)">删除</el-button>
              </div>
              <el-button type="primary" plain @click="addInventoryUsage">添加库存领用</el-button>
            </div>
          </el-form-item>
          <el-form-item label="维修人员"><el-input v-model="form.repair_person" /></el-form-item>
          <el-form-item label="支付人员"><el-input v-model="form.payment_person" /></el-form-item>
          <el-form-item label="支付截图" class="full-span">
            <input ref="paymentImageInputRef" type="file" accept="image/*" multiple class="hidden-file-input" @change="handlePaymentImageChange" />
            <div class="image-upload-row">
              <el-button type="primary" plain @click="openPaymentImageDialog">选择图片(最多30张)</el-button>
              <el-button v-if="form.payment_images.length > 0" type="danger" plain @click="clearAllPaymentImages">全部删除图片</el-button>
              <span class="image-upload-tip">支持多张图片，最多 30 张，提交时会作为支付截图保存。</span>
            </div>
            <el-progress v-if="paymentUploading" :percentage="paymentUploadProgress" :stroke-width="8" />
            <div class="image-upload-tip">已选：{{ form.payment_images.length }} / 30</div>
            <div v-if="form.payment_images.length" class="image-list">
              <div v-for="(img, index) in form.payment_images" :key="`payment-${img}-${index}`" class="image-item">
                <img :src="resolveImageUrl(img)" class="image-thumb" />
                <el-button size="small" type="danger" plain @click="removePaymentImage(index)">删除</el-button>
              </div>
            </div>
          </el-form-item>
        </template>

        <template v-else-if="businessType === 'procurement'">
          <el-form-item label="AI 输入" class="full-span">
            <div class="image-upload-row">
              <el-button type="primary" plain @click="openAiDialog">AI 输入</el-button>
              <span class="image-upload-tip">支持文字、收据、发票或购物截图识别，生成后会填入下方表单。</span>
            </div>
          </el-form-item>
          <el-form-item label="录入方式" class="full-span">
            <el-radio-group v-model="form.purchase_mode">
              <el-radio label="single">单个物品</el-radio>
              <el-radio label="multi">一单多物品</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="采购渠道">
            <el-radio-group v-model="form.purchase_channel">
              <el-radio label="线下">线下</el-radio>
              <el-radio label="线上">线上</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="时间" prop="procurement_date"><el-date-picker v-model="form.procurement_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
          <template v-if="form.purchase_mode === 'single'">
            <el-form-item label="采购物品" prop="item_name"><el-input v-model="form.item_name" /></el-form-item>
            <el-form-item label="规格"><el-input v-model="form.specification" /></el-form-item>
            <el-form-item label="数量" prop="quantity"><el-input-number v-model="form.quantity" :min="1" style="width: 100%" /></el-form-item>
            <el-form-item label="单价"><el-input-number v-model="form.unit_price" :min="0" :precision="2" style="width: 100%" /></el-form-item>
            <el-form-item label="单位"><el-input v-model="form.unit" /></el-form-item>
          </template>
          <el-form-item v-else label="采购物品明细" class="full-span">
            <div class="multi-item-wrap">
              <div
                v-for="(item, index) in form.items"
                :key="`public-proc-item-${index}`"
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
              <div class="image-upload-tip">如果没有填写单价，系统才会把总金额按条目平均分摊到每个物品。</div>
            </div>
          </el-form-item>
          <el-form-item label="总金额"><el-input-number v-model="form.total_amount" :min="0" :precision="2" style="width: 100%" /></el-form-item>
          <el-form-item label="支付人员"><el-input v-model="form.payment_person" /></el-form-item>
          <el-form-item label="备注" class="full-span"><el-input v-model="form.remarks" type="textarea" :rows="3" /></el-form-item>
          <el-form-item label="图片" class="full-span">
            <input ref="imageInputRef" type="file" accept="image/*" multiple class="hidden-file-input" @change="handleImageChange" />
            <div class="image-upload-row">
              <el-button type="primary" plain @click="openImageDialog">选择图片(最多30张)</el-button>
              <el-button v-if="form.images.length > 0" type="danger" plain @click="clearAllImages">全部删除图片</el-button>
              <span class="image-upload-tip">支持多张图片，最多 30 张。</span>
            </div>
            <el-progress v-if="uploading" :percentage="uploadProgress" :stroke-width="8" />
            <div class="image-upload-tip">已选：{{ form.images.length }} / 30</div>
            <div v-if="form.images.length" class="image-list">
              <div v-for="(img, index) in form.images" :key="`${img}-${index}`" class="image-item">
                <img :src="resolveImageUrl(img)" class="image-thumb" />
                <el-button size="small" type="danger" plain @click="removeImage(index)">删除</el-button>
              </div>
            </div>
          </el-form-item>
        </template>

        <template v-else-if="businessType === 'warehouse'">
          <el-form-item label="时间"><el-date-picker v-model="form.procurement_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
          <el-form-item label="物品" prop="item_name"><el-input v-model="form.item_name" /></el-form-item>
          <el-form-item label="规格"><el-input v-model="form.specification" /></el-form-item>
          <el-form-item label="数量" prop="quantity"><el-input-number v-model="form.quantity" :min="0" :precision="2" style="width: 100%" /></el-form-item>
          <el-form-item label="单位"><el-input v-model="form.unit" /></el-form-item>
          <el-form-item label="存放位置"><el-input v-model="form.location" /></el-form-item>
          <el-form-item label="备注" class="full-span"><el-input v-model="form.remarks" type="textarea" :rows="3" /></el-form-item>
          <el-form-item label="图片" class="full-span">
            <input ref="imageInputRef" type="file" accept="image/*" multiple class="hidden-file-input" @change="handleImageChange" />
            <div class="image-upload-row">
              <el-button type="primary" plain @click="openImageDialog">选择图片(最多30张)</el-button>
              <el-button v-if="form.images.length > 0" type="danger" plain @click="clearAllImages">全部删除图片</el-button>
              <span class="image-upload-tip">支持多张图片，最多 30 张。</span>
            </div>
            <el-progress v-if="uploading" :percentage="uploadProgress" :stroke-width="8" />
            <div class="image-upload-tip">已选：{{ form.images.length }} / 30</div>
            <div v-if="form.images.length" class="image-list">
              <div v-for="(img, index) in form.images" :key="`${img}-${index}`" class="image-item">
                <img :src="resolveImageUrl(img)" class="image-thumb" />
                <el-button size="small" type="danger" plain @click="removeImage(index)">删除</el-button>
              </div>
            </div>
          </el-form-item>
        </template>

        <el-button type="primary" :loading="submitting" @click="submitForm">提交信息</el-button>
      </el-form>
      </div>

      <el-dialog
        :title="aiDialogTitle"
        v-model="aiDialog.visible"
        width="min(620px, calc(100vw - 24px))"
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
              :placeholder="aiTextPlaceholder"
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
                <div class="ai-dropzone__hint">也可以点击下面按钮选择图片，或直接粘贴截图。</div>
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
            <div class="image-upload-tip">识别图片仅用于生成表单内容，不会自动保存到下方业务图片。</div>
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
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { publicBusinessEntryApi, procurementApi, repairRecordsApi } from '../api'
import ThemeModeSwitch from '../components/ThemeModeSwitch.vue'
import { applyTheme, getPreferredTheme } from '../utils/theme'

const BUSINESS_CONFIGS = {
  repair: { title: '维修记录填写', subtitle: '通过公开填写链接快速提交维修记录。' },
  procurement: { title: '采购记录填写', subtitle: '通过公开填写链接快速提交采购信息。' },
  warehouse: { title: '库存物资填写', subtitle: '通过公开填写链接快速提交库存信息。' },
}

const route = useRoute()
const businessType = String(route.params.businessType || '').trim().toLowerCase()
const token = String(route.params.token || '')
const currentConfig = computed(() => BUSINESS_CONFIGS[businessType] || { title: '公开填写', subtitle: '' })
const aiDialogTitle = computed(() => {
  if (businessType === 'repair') return 'AI 输入维修'
  if (businessType === 'warehouse') return 'AI 输入库存'
  return 'AI 输入采购'
})
const aiTextPlaceholder = computed(() => {
  if (businessType === 'repair') {
    return '例如：A栋 301 洗手间漏水，张三报修，今天待处理。也可以上传现场照片、报修截图或支付截图让 AI 识别。'
  }
  if (businessType === 'warehouse') {
    return '例如：今天入库 12 个 LED 灯泡，放在 A 栋工具间。也可以上传清单、截图或现场照片让 AI 识别。'
  }
  return '例如：今天线下买了 10 个 LED 灯泡，12W，单价 8.5 元，王会计付款。也可以上传收据、发票或购物截图让 AI 识别。'
})

const loading = ref(true)
const submitting = ref(false)
const error = ref('')
const formRef = ref(null)
const imageInputRef = ref(null)
const paymentImageInputRef = ref(null)
const uploading = ref(false)
const uploadProgress = ref(0)
const paymentUploading = ref(false)
const paymentUploadProgress = ref(0)
const inventoryOptions = ref([])
const repairRoomOptions = ref([])
const tenantNameOptions = ref([])
const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/api\/?$/, '')
const MAX_PUBLIC_IMAGES = 30
const REPAIR_SCOPE_OPTIONS = ['单个房间', '多个房间', '公共区域', '整层', '整栋', '楼栋']
const aiDialog = reactive({
  visible: false,
  loading: false,
  text: '',
  images: [],
  dragActive: false,
})

const parsePublicBuildingModel = (value, scopeType) => {
  if (scopeType !== '单个房间') {
    if (Array.isArray(value)) return value.map(v => String(v || '').trim()).filter(Boolean)
    return String(value || '').split(/[，,、;\s]+/).map(v => v.trim()).filter(Boolean)
  }
  if (Array.isArray(value)) return String(value[0] || '').trim()
  return String(value || '').trim()
}
const serializePublicBuildingModel = (value, scopeType) => {
  if (scopeType !== '单个房间') {
    const items = Array.isArray(value) ? value : parsePublicBuildingModel(value, scopeType)
    return items.map(v => String(v || '').trim()).filter(Boolean).join('，')
  }
  return Array.isArray(value) ? String(value[0] || '').trim() : String(value || '').trim()
}

const form = reactive({
  scope_type: '单个房间',
  building: '',
  room_no: '',
  room_nos: '',
  repair_type: '',
  report_by: '',
  report_date: new Date().toISOString().slice(0, 10),
  status: '待处理',
  repair_date: '',
  amount: null,
  repair_person: '',
  payment_person: '',
  inventory_usages: [],
  description: '',
  remarks: '',
  payment_images: [],
  purchase_mode: 'single',
  purchase_channel: '线下',
  procurement_date: new Date().toISOString().slice(0, 10),
  item_name: '',
  specification: '',
  quantity: 1,
  unit_price: 0,
  unit: '',
  total_amount: 0,
  items: [],
  location: '',
  images: [],
})

const validatePublicRepairBuilding = (_rule, value, callback) => {
  if (form.scope_type === '单个房间') {
    if (!String(value || '').trim()) return callback(new Error('请输入或选择楼栋'))
  }
  if (form.scope_type !== '单个房间') {
    const items = Array.isArray(value) ? value.filter(Boolean) : []
    if (!items.length) return callback(new Error('请选择楼栋'))
  }
  callback()
}
const validatePublicRepairRoomNo = (_rule, value, callback) => {
  if (form.scope_type === '单个房间' && !String(value || '').trim()) {
    return callback(new Error('请输入或选择房间号'))
  }
  callback()
}
const validatePublicRepairRoomNos = (_rule, value, callback) => {
  if (form.scope_type === '多个房间' && !String(value || '').trim()) {
    return callback(new Error('请输入多个房间号'))
  }
  callback()
}
const rulesMap = {
  repair: {
    scope_type: [{ required: true, message: '请选择维修范围', trigger: 'change' }],
    building: [{ validator: validatePublicRepairBuilding, trigger: ['change', 'blur'] }],
    room_no: [{ validator: validatePublicRepairRoomNo, trigger: ['change', 'blur'] }],
    room_nos: [{ validator: validatePublicRepairRoomNos, trigger: ['change', 'blur'] }],
    repair_type: [{ required: true, message: '请选择维修类型', trigger: 'change' }],
    report_by: [{ required: true, message: '请输入报修人', trigger: 'blur' }],
    report_date: [{ required: true, message: '请选择报修日期', trigger: 'change' }],
    status: [{ required: true, message: '请选择状态', trigger: 'change' }],
    description: [{ required: true, message: '请输入问题描述', trigger: 'blur' }],
  },
  procurement: {
    procurement_date: [{ required: true, message: '请选择时间', trigger: 'change' }],
    item_name: [{ required: true, message: '请输入采购物品', trigger: 'blur' }],
    quantity: [{ required: true, message: '请输入数量', trigger: 'change' }],
  },
  warehouse: {
    item_name: [{ required: true, message: '请输入物品', trigger: 'blur' }],
    quantity: [{ required: true, message: '请输入数量', trigger: 'change' }],
  },
}

const rules = computed(() => rulesMap[businessType] || {})
const repairBuildingOptions = computed(() => {
  return [...new Set((repairRoomOptions.value || []).map(item => item.building).filter(Boolean))]
})
const filteredRepairRoomOptions = computed(() => {
  if (!form.building) return []
  return (repairRoomOptions.value || []).filter(item => item.building === form.building)
})

const payloadByBusiness = () => {
  if (businessType === 'repair') {
    return {
      scope_type: form.scope_type,
      building: serializePublicBuildingModel(form.building, form.scope_type),
      room_no: form.room_no,
      room_nos: form.room_nos,
      repair_type: form.repair_type,
      report_by: form.report_by,
      report_date: form.report_date,
      status: form.status,
      repair_date: form.repair_date,
      amount: form.amount,
      repair_person: form.repair_person,
      payment_person: form.payment_person,
      inventory_usages: form.inventory_usages,
      description: form.description,
      remarks: form.remarks,
      payment_images: form.payment_images,
    }
  }
  if (businessType === 'procurement') {
    const payload = {
      procurement_date: form.procurement_date,
      purchase_channel: form.purchase_channel,
      item_name: form.item_name,
      specification: form.specification,
      quantity: form.quantity,
      unit_price: form.unit_price,
      unit: form.unit,
      total_amount: form.total_amount,
      payment_person: form.payment_person,
      images: form.images,
      remarks: form.remarks,
    }
    if (form.purchase_mode === 'multi') {
      payload.items = (form.items || [])
        .map(item => ({
          item_name: String(item.item_name || '').trim(),
          specification: String(item.specification || '').trim(),
          quantity: Number(item.quantity || 0),
          unit_price: Number(item.unit_price || 0),
          unit: String(item.unit || '').trim(),
        }))
        .filter(item => item.item_name && item.quantity > 0 && item.unit)
    }
    return payload
  }
  return {
    procurement_date: form.procurement_date,
    item_name: form.item_name,
    specification: form.specification,
    quantity: form.quantity,
    unit: form.unit,
    location: form.location,
    images: form.images,
    remarks: form.remarks,
  }
}

const openImageDialog = () => {
  imageInputRef.value?.click()
}

const openPaymentImageDialog = () => {
  paymentImageInputRef.value?.click()
}

const resolveImageUrl = (src) => {
  const value = String(src || '').trim()
  if (!value) return ''
  if (/^data:image\//i.test(value) || /^https?:\/\//i.test(value) || value.startsWith('blob:')) return value
  if (value.startsWith('/')) return `${apiBaseUrl}${value}`
  return `${apiBaseUrl}/${value}`
}

const handleImageChange = async (event) => {
  const files = Array.from(event?.target?.files || [])
  event.target.value = ''
  if (!files.length) return
  if (form.images.length >= MAX_PUBLIC_IMAGES) {
    ElMessage.warning(`最多上传 ${MAX_PUBLIC_IMAGES} 张图片`)
    return
  }
  if (form.images.length + files.length > MAX_PUBLIC_IMAGES) {
    ElMessage.warning(`最多上传 ${MAX_PUBLIC_IMAGES} 张图片`)
    return
  }
  for (const file of files) {
    if (!String(file.type || '').startsWith('image/')) {
      ElMessage.error('请上传图片文件')
      return
    }
  }
  uploading.value = true
  uploadProgress.value = 0
  try {
    const total = files.length
    for (let i = 0; i < total; i++) {
      const file = files[i]
      const response = await publicBusinessEntryApi.uploadImage(businessType, token, file, (evt) => {
        const totalBytes = evt?.total || 0
        const percent = totalBytes > 0 ? (evt.loaded * 100) / totalBytes : 0
        uploadProgress.value = Math.floor(((i + percent / 100) / total) * 100)
      })
      const fileUrl = String(response?.data?.file_url || '')
      if (fileUrl) form.images.push(fileUrl)
    }
    uploadProgress.value = 100
    ElMessage.success('图片上传成功')
  } catch (err) {
    ElMessage.error(err?.response?.data?.error || '图片上传失败')
  } finally {
    uploading.value = false
  }
}

const removeImage = (index) => {
  if (index < 0 || index >= form.images.length) return
  form.images.splice(index, 1)
}

const clearAllImages = () => {
  form.images = []
}

const handlePaymentImageChange = async (event) => {
  const files = Array.from(event?.target?.files || [])
  event.target.value = ''
  if (!files.length) return
  if (form.payment_images.length >= MAX_PUBLIC_IMAGES || form.payment_images.length + files.length > MAX_PUBLIC_IMAGES) {
    ElMessage.warning(`最多上传 ${MAX_PUBLIC_IMAGES} 张图片`)
    return
  }
  for (const file of files) {
    if (!String(file.type || '').startsWith('image/')) {
      ElMessage.error('请上传图片文件')
      return
    }
  }
  paymentUploading.value = true
  paymentUploadProgress.value = 0
  try {
    const total = files.length
    for (let i = 0; i < total; i++) {
      const file = files[i]
      const response = await publicBusinessEntryApi.uploadImage(businessType, token, file, (evt) => {
        const totalBytes = evt?.total || 0
        const percent = totalBytes > 0 ? (evt.loaded * 100) / totalBytes : 0
        paymentUploadProgress.value = Math.floor(((i + percent / 100) / total) * 100)
      })
      const fileUrl = String(response?.data?.file_url || '')
      if (fileUrl) form.payment_images.push(fileUrl)
    }
    paymentUploadProgress.value = 100
    ElMessage.success('支付截图上传成功')
  } catch (err) {
    ElMessage.error(err?.response?.data?.error || '支付截图上传失败')
  } finally {
    paymentUploading.value = false
  }
}

const removePaymentImage = (index) => {
  if (index < 0 || index >= form.payment_images.length) return
  form.payment_images.splice(index, 1)
}

const clearAllPaymentImages = () => {
  form.payment_images = []
}

const addInventoryUsage = () => {
  form.inventory_usages = [...(form.inventory_usages || []), { warehouse_item_id: null, quantity: 1 }]
}

const removeInventoryUsage = (index) => {
  const list = [...(form.inventory_usages || [])]
  if (index < 0 || index >= list.length) return
  list.splice(index, 1)
  form.inventory_usages = list
}

const addProcurementItem = () => {
  form.items = [...(form.items || []), { item_name: '', specification: '', quantity: 1, unit_price: 0, unit: '' }]
}

const removeProcurementItem = (index) => {
  if ((form.items || []).length <= 1) return
  const list = [...(form.items || [])]
  list.splice(index, 1)
  form.items = list
}

const todayText = () => new Date().toISOString().split('T')[0]

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
  aiDialog.dragActive = false
}

const openAiDialog = () => {
  resetAiDialog()
  aiDialog.visible = true
}

const addAiImageFile = (file) => {
  if (!file) return false
  if (aiDialog.images.length >= 4) {
    ElMessage.warning('最多选择 4 张图片')
    return false
  }
  if (!String(file.type || '').startsWith('image/')) {
    ElMessage.warning('请上传图片文件')
    return false
  }
  if (file.size && file.size > 8 * 1024 * 1024) {
    ElMessage.warning('单张图片请控制在 8MB 以内')
    return false
  }
  aiDialog.images.push({
    file,
    url: URL.createObjectURL(file)
  })
  return true
}

const handleAiImageChange = (file) => {
  if (!file || !file.raw) return
  addAiImageFile(file.raw)
}

const handleAiDrop = (event) => {
  aiDialog.dragActive = false
  const files = Array.from(event?.dataTransfer?.files || [])
  files.forEach(file => addAiImageFile(file))
}

const handleAiPaste = (event) => {
  const files = Array.from(event?.clipboardData?.items || [])
    .filter(item => item.kind === 'file')
    .map(item => item.getAsFile())
    .filter(Boolean)
  if (!files.length) return
  event.preventDefault()
  files.forEach(file => addAiImageFile(file))
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

const applyProcurementAiDraftToForm = (draft = {}) => {
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
    form.items = []
    if (!form.total_amount && form.quantity > 0 && form.unit_price > 0) {
      form.total_amount = Number((form.quantity * form.unit_price).toFixed(2))
    }
  }
}

const applyRepairAiDraftToForm = (draft = {}) => {
  const scopeType = String(draft.scope_type || '单个房间')
  form.scope_type = REPAIR_SCOPE_OPTIONS.includes(scopeType) ? scopeType : '单个房间'
  form.building = parsePublicBuildingModel(draft.building || '', form.scope_type)
  form.room_no = String(draft.room_no || '')
  form.room_nos = String(draft.room_nos || '')
  form.repair_type = String(draft.repair_type || '其他')
  form.description = String(draft.description || '')
  form.report_by = String(draft.report_by || '')
  form.report_date = String(draft.report_date || todayText())
  form.status = String(draft.status || '待处理')
  form.repair_date = String(draft.repair_date || '')
  form.amount = Number(draft.amount || 0)
  form.repair_person = String(draft.repair_person || '')
  form.payment_person = String(draft.payment_person || '')
  form.remarks = String(draft.remarks || '')
  formRef.value?.clearValidate?.()
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
    const response = businessType === 'repair'
      ? await repairRecordsApi.createAiDraft(formData)
      : await procurementApi.createAiDraft(formData)
    if (businessType === 'repair') {
      applyRepairAiDraftToForm(response?.data?.draft || {})
    } else {
      applyProcurementAiDraftToForm(response?.data?.draft || {})
    }
    aiDialog.visible = false
    ElMessage.success('AI 草稿已填入表单，请确认后提交')
  } catch (err) {
    ElMessage.error(err?.response?.data?.error || err?.message || 'AI 输入失败')
  } finally {
    aiDialog.loading = false
  }
}

const handleRepairBuildingChange = () => {
  if (form.scope_type === '单个房间') form.room_no = ''
}

const handlePublicRepairScopeChange = () => {
  form.building = parsePublicBuildingModel(form.building, form.scope_type)
  if (form.scope_type === '单个房间') {
    form.room_nos = ''
  } else if (form.scope_type === '多个房间') {
    form.room_no = ''
  } else {
    form.room_no = ''
    form.room_nos = ''
  }
  formRef.value?.clearValidate?.(['building', 'room_no', 'room_nos'])
}

const fetchFormInfo = async () => {
  loading.value = true
  try {
    const response = await publicBusinessEntryApi.getForm(businessType, token)
    inventoryOptions.value = response?.data?.inventory_options || []
    repairRoomOptions.value = response?.data?.room_options || []
    tenantNameOptions.value = response?.data?.tenant_names || []
  } catch (err) {
    error.value = err?.response?.data?.error || '填写链接无效或已失效'
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  form.building = ''
  form.scope_type = '单个房间'
  form.room_no = ''
  form.room_nos = ''
  form.repair_type = ''
  form.report_by = ''
  form.report_date = new Date().toISOString().slice(0, 10)
  form.status = '待处理'
  form.repair_date = ''
  form.amount = null
  form.repair_person = ''
  form.payment_person = ''
  form.inventory_usages = []
  form.description = ''
  form.remarks = ''
  form.payment_images = []
  form.purchase_mode = 'single'
  form.purchase_channel = '线下'
  form.procurement_date = new Date().toISOString().slice(0, 10)
  form.item_name = ''
  form.specification = ''
  form.quantity = 1
  form.unit_price = 0
  form.unit = ''
  form.total_amount = 0
  form.items = []
  form.payment_person = ''
  form.location = ''
  form.images = []
}

const submitForm = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      await publicBusinessEntryApi.submit(businessType, token, payloadByBusiness())
      ElMessage.success('提交成功')
      resetForm()
    } catch (err) {
      ElMessage.error(err?.response?.data?.error || '提交失败')
    } finally {
      submitting.value = false
    }
  })
}

onMounted(() => {
  applyTheme(getPreferredTheme())
  fetchFormInfo()
})

onUnmounted(() => {
  revokeAiImageUrls()
})
</script>

<style scoped>
.public-page {
  min-height: 100vh;
  padding: 32px 16px;
  background:
    radial-gradient(circle at top left, rgba(37, 99, 235, 0.12), transparent 32%),
    linear-gradient(180deg, var(--bg-color) 0%, var(--surface-muted) 100%);
  color: var(--text-main);
}

.public-card {
  max-width: 820px;
  margin: 0 auto;
  padding: 24px;
  border-radius: var(--card-radius);
  background: var(--card-bg);
  border: 1px solid var(--surface-border);
  box-shadow: var(--card-shadow);
}

html.dark .public-page {
  background:
    radial-gradient(circle at top left, rgba(37, 99, 235, 0.18), transparent 32%),
    linear-gradient(180deg, var(--bg-color) 0%, var(--surface-muted) 100%);
}

.header {
  margin-bottom: 20px;
}

.header h2 {
  margin: 0 0 8px;
  color: var(--text-main);
}

.header p {
  margin: 0;
  color: var(--text-secondary);
}

.loading-state {
  color: var(--text-secondary);
}

.entry-wrap {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.entry-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.entry-form :deep(.el-form-item) {
  margin-bottom: 0;
}

.full-span {
  grid-column: 1 / -1;
}

.entry-form > :last-child {
  grid-column: 1 / -1;
}

.hidden-file-input {
  display: none;
}

.image-upload-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.image-upload-tip {
  font-size: 12px;
  color: var(--text-secondary);
}

.image-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.image-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.image-thumb {
  width: 88px;
  height: 88px;
  object-fit: cover;
  border-radius: 10px;
  border: 1px solid var(--surface-border);
}

@media (max-width: 768px) {
  .public-page {
    padding: 64px 10px 20px;
  }

  .entry-form {
    grid-template-columns: 1fr;
  }
}
</style>
