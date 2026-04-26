<template>
  <div class="public-page">
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
          <el-form-item label="楼栋" prop="building">
            <el-select v-model="form.building" placeholder="请选择楼栋" @change="handleRepairBuildingChange">
              <el-option
                v-for="item in repairBuildingOptions"
                :key="item"
                :label="item"
                :value="item"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="房间号" prop="room_no">
            <el-select v-model="form.room_no" placeholder="请选择房间号">
              <el-option
                v-for="item in filteredRepairRoomOptions"
                :key="`${item.building}-${item.room_no}`"
                :label="item.room_no"
                :value="item.room_no"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="维修类型" prop="repair_type">
            <el-select v-model="form.repair_type" placeholder="请选择维修类型">
              <el-option label="水电维修" value="水电维修" />
              <el-option label="家具维修" value="家具维修" />
              <el-option label="电器维修" value="电器维修" />
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
          <el-form-item label="报修人" prop="report_by"><el-input v-model="form.report_by" /></el-form-item>
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
                <el-select v-model="usage.warehouse_item_id" placeholder="选择库存物品" style="width: 100%">
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
          <el-form-item label="时间" prop="procurement_date"><el-date-picker v-model="form.procurement_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
          <el-form-item label="采购物品" prop="item_name"><el-input v-model="form.item_name" /></el-form-item>
          <el-form-item label="规格"><el-input v-model="form.specification" /></el-form-item>
          <el-form-item label="数量" prop="quantity"><el-input-number v-model="form.quantity" :min="1" style="width: 100%" /></el-form-item>
          <el-form-item label="单价"><el-input-number v-model="form.unit_price" :min="0" :precision="2" style="width: 100%" /></el-form-item>
          <el-form-item label="单位"><el-input v-model="form.unit" /></el-form-item>
          <el-form-item label="总金额"><el-input-number v-model="form.total_amount" :min="0" :precision="2" style="width: 100%" /></el-form-item>
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
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { publicBusinessEntryApi } from '../api'

const BUSINESS_CONFIGS = {
  repair: { title: '维修记录填写', subtitle: '通过公开填写链接快速提交维修记录。' },
  procurement: { title: '采购记录填写', subtitle: '通过公开填写链接快速提交采购信息。' },
  warehouse: { title: '库存物资填写', subtitle: '通过公开填写链接快速提交库存信息。' },
}

const route = useRoute()
const businessType = String(route.params.businessType || '').trim().toLowerCase()
const token = String(route.params.token || '')
const currentConfig = computed(() => BUSINESS_CONFIGS[businessType] || { title: '公开填写', subtitle: '' })

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
const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/api\/?$/, '')
const MAX_PUBLIC_IMAGES = 30

const form = reactive({
  building: '',
  room_no: '',
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
  procurement_date: new Date().toISOString().slice(0, 10),
  item_name: '',
  specification: '',
  quantity: 1,
  unit_price: 0,
  unit: '',
  total_amount: 0,
  location: '',
  images: [],
})

const rulesMap = {
  repair: {
    building: [{ required: true, message: '请输入楼栋', trigger: 'blur' }],
    room_no: [{ required: true, message: '请输入房间号', trigger: 'blur' }],
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
      building: form.building,
      room_no: form.room_no,
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
    return {
      procurement_date: form.procurement_date,
      item_name: form.item_name,
      specification: form.specification,
      quantity: form.quantity,
      unit_price: form.unit_price,
      unit: form.unit,
      total_amount: form.total_amount,
      images: form.images,
      remarks: form.remarks,
    }
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

const handleRepairBuildingChange = () => {
  form.room_no = ''
}

const fetchFormInfo = async () => {
  loading.value = true
  try {
    const response = await publicBusinessEntryApi.getForm(businessType, token)
    inventoryOptions.value = response?.data?.inventory_options || []
    repairRoomOptions.value = response?.data?.room_options || []
  } catch (err) {
    error.value = err?.response?.data?.error || '填写链接无效或已失效'
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  form.building = ''
  form.room_no = ''
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
  form.procurement_date = new Date().toISOString().slice(0, 10)
  form.item_name = ''
  form.specification = ''
  form.quantity = 1
  form.unit_price = 0
  form.unit = ''
  form.total_amount = 0
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
  fetchFormInfo()
})
</script>

<style scoped>
.public-page {
  min-height: 100vh;
  padding: 32px 16px;
  background:
    radial-gradient(circle at top left, rgba(37, 99, 235, 0.12), transparent 32%),
    linear-gradient(180deg, var(--bg-color) 0%, var(--surface-muted) 100%);
}

.public-card {
  max-width: 820px;
  margin: 0 auto;
  padding: 24px;
  border-radius: 20px;
  background: var(--card-bg);
  border: 1px solid var(--surface-border);
  box-shadow: var(--card-shadow);
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
  .entry-form {
    grid-template-columns: 1fr;
  }
}
</style>
