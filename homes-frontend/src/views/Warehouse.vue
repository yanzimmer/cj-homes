<template>
  <div class="page-container">
    <div class="page-header">
      <div class="header-operations">
        <el-input
          class="search-input"
          v-model="searchQuery"
          placeholder="搜索物品/规格/位置/备注"
          clearable
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button class="toolbar-btn" type="primary" @click="handleSearch">搜索</el-button>
        <el-button class="toolbar-btn" type="primary" @click="openDialog('add')">新增</el-button>
        <el-button class="toolbar-btn" type="success" @click="linkDialogVisible = true">链接</el-button>
        <el-button class="toolbar-btn" type="danger" :disabled="selectedItems.length === 0" @click="handleBatchDelete">删除</el-button>
      </div>
    </div>

    <div class="table-panel">
      <el-table class="warehouse-table" :data="items" v-loading="loading" border style="width: 100%" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="55" />
        <el-table-column label="序号" width="80" align="center">
          <template #default="{ $index }">
            {{ warehouseRowStart + $index + 1 }}
          </template>
        </el-table-column>
        <el-table-column prop="procurement_date" label="时间" width="120" />
        <el-table-column prop="item_name" label="物品" min-width="150" show-overflow-tooltip />
        <el-table-column prop="specification" label="规格" width="120" show-overflow-tooltip />
        <el-table-column prop="quantity" label="数量" width="120" align="center" />
        <el-table-column prop="unit" label="单位" width="90" align="center" />
        <el-table-column prop="location" label="存放位置" width="160" show-overflow-tooltip />
        <el-table-column label="图片" width="90" align="center">
          <template #default="{ row }">
            <el-image lazy loading="lazy"
              v-if="getImages(row).length > 0"
              style="width: 40px; height: 40px"
              :src="resolveImageUrl(getImages(row)[0])"
              :preview-src-list="getImages(row).map((v) => resolveImageUrl(v))"
              fit="cover"
              preview-teleported
            />
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="remarks" label="备注" min-width="180" show-overflow-tooltip />
        <el-table-column prop="updated_at" label="更新时间" width="170" />
        <el-table-column label="操作" width="170" fixed="right" align="center">
          <template #default="{ row }">
            <div class="table-actions-row">
              <el-button size="small" type="primary" @click="openDialog('edit', row)">编辑</el-button>
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
    <div class="pagination-container">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>
    <el-drawer
      :title="dialog.title"
      v-model="dialog.visible"
      direction="rtl"
      size="520px"
      @close="resetForm"
    >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
      <el-form-item label="时间" prop="procurement_date">
        <el-date-picker
          v-model="form.procurement_date"
          type="date"
          placeholder="选择日期"
          value-format="YYYY-MM-DD"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="物品" prop="item_name">
        <el-input v-model="form.item_name" placeholder="请输入物品" />
      </el-form-item>
      <el-form-item label="规格" prop="specification">
        <el-input v-model="form.specification" placeholder="请输入规格型号" />
      </el-form-item>
      <el-form-item label="数量" prop="quantity">
        <el-input-number v-model="form.quantity" :min="0" :precision="2" style="width: 100%" />
      </el-form-item>
      <el-form-item label="单位" prop="unit">
        <el-input v-model="form.unit" placeholder="如：个/米/箱" />
      </el-form-item>
      <el-form-item label="存放位置" prop="location">
        <el-input v-model="form.location" placeholder="如：A库-货架1层" />
      </el-form-item>
      <el-form-item label="图片" prop="images">
        <div class="image-upload-row">
          <el-upload
            class="image-uploader"
            action="#"
            :show-file-list="false"
            :auto-upload="false"
            accept="image/*"
            multiple
            :limit="30"
            :on-change="handleImageUpload"
          >
            <div class="image-upload-card">
              <img loading="lazy" v-if="form.images.length > 0" :src="resolveImageUrl(form.images[0])" class="image-preview" />
              <div v-else class="image-placeholder">
                <el-icon class="image-placeholder-icon"><Plus /></el-icon>
                <span>点击上传</span>
              </div>
            </div>
          </el-upload>
          <div class="image-upload-actions">
            <el-button v-if="form.images.length > 0" type="danger" plain @click="clearImages">全部删除图片</el-button>
            <span class="image-upload-tip">支持 JPG/PNG/WEBP，最多 30 张，建议单张小于 2MB</span>
            <span class="image-upload-tip">已选：{{ form.images.length }} / 30</span>
            <el-progress
              v-if="imageUploading"
              :percentage="imageUploadProgress"
              :stroke-width="6"
            />
          </div>
        </div>
        <div v-if="form.images.length > 0" class="image-list">
          <div v-for="(img, index) in form.images" :key="`${img}-${index}`" class="image-list-item">
            <img loading="lazy" :src="resolveImageUrl(img)" class="image-list-thumb" />
            <el-button size="small" type="danger" plain @click="removeImage(index)">删除</el-button>
          </div>
        </div>
      </el-form-item>
      <el-form-item label="备注" prop="remarks">
        <el-input v-model="form.remarks" type="textarea" :rows="3" />
      </el-form-item>
    </el-form>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="dialog.submitting" @click="submitForm">确定</el-button>
      </span>
    </template>
    </el-drawer>

    <BusinessPublicLinkDialog
      v-model="linkDialogVisible"
      business-type="warehouse"
      title="库存填写链接"
      business-label="库存管理"
    />
  </div>
</template>

<script setup>
import { computed, ref, reactive, onMounted } from 'vue'
import { warehouseApi } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, MoreFilled } from '@element-plus/icons-vue'
import { uploadFileByChunks } from '../utils/chunkUploader'
import BusinessPublicLinkDialog from '../components/BusinessPublicLinkDialog.vue'

const loading = ref(false)
const linkDialogVisible = ref(false)
const items = ref([])
const selectedItems = ref([])
const searchQuery = ref('')
const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})
const warehouseRowStart = computed(() => (pagination.page - 1) * pagination.pageSize)
const formRef = ref(null)
const imageUploading = ref(false)
const imageUploadProgress = ref(0)
const MAX_WAREHOUSE_FORM_IMAGES = 30

const dialog = reactive({
  visible: false,
  title: '新增库存物资',
  type: 'add',
  submitting: false
})

const form = reactive({
  id: null,
  procurement_date: '',
  item_name: '',
  specification: '',
  quantity: 0,
  unit: '',
  location: '',
  images: [],
  remarks: ''
})

const rules = {
  item_name: [{ required: true, message: '请输入物品', trigger: 'blur' }],
  quantity: [{ required: true, message: '请输入数量', trigger: 'blur' }]
}

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/api\/?$/, '')
const resolveImageUrl = (src) => {
  const value = String(src || '').trim()
  if (!value) return ''
  if (/^data:image\//i.test(value) || /^https?:\/\//i.test(value)) return value
  if (value.startsWith('/')) return `${apiBaseUrl}${value}`
  return `${apiBaseUrl}/${value}`
}

const getImages = (data) => {
  if (Array.isArray(data?.images)) {
    return data.images.map(v => String(v)).filter(v => v.trim() !== '').slice(0, 20)
  }
  const raw = String(data?.image || '').trim()
  if (!raw) return []
  if (raw.startsWith('[')) {
    try {
      const arr = JSON.parse(raw)
      if (Array.isArray(arr)) {
        return arr.map(v => String(v)).filter(v => v.trim() !== '').slice(0, 20)
      }
    } catch (_) {}
  }
  return [raw]
}

const fetchItems = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      fields: 'id,procurement_date,item_name,specification,quantity,unit,location,image,images,remarks,updated_at,has_image'
    }
    if (searchQuery.value.trim()) params.q = searchQuery.value.trim()
    const res = await warehouseApi.listItems(params)
    items.value = res.data.items || []
    const serverTotal = Number(res?.data?.filtered_total ?? res?.data?.total ?? 0)
    pagination.total = Number.isFinite(serverTotal) ? serverTotal : 0
  } catch (error) {
    ElMessage.error('获取库存数据失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchItems()
}

const handleSizeChange = (val) => {
  pagination.pageSize = val
  pagination.page = 1
  fetchItems()
}

const handleCurrentChange = (val) => {
  pagination.page = val
  fetchItems()
}

const handleSelectionChange = (rows) => {
  selectedItems.value = rows || []
}

const resetForm = () => {
  if (formRef.value) formRef.value.resetFields()
  Object.assign(form, {
    id: null,
    procurement_date: '',
    item_name: '',
    specification: '',
    quantity: 0,
    unit: '',
    location: '',
    images: [],
    remarks: ''
  })
  imageUploading.value = false
  imageUploadProgress.value = 0
}

const openDialog = async (type, row = null) => {
  dialog.type = type
  dialog.title = type === 'add' ? '新增物品' : '编辑物品'
  resetForm()
  if (type === 'edit' && row) {
    try {
      const res = await warehouseApi.getItem(row.id)
      const target = res.data.item || row
      Object.assign(form, { ...target, images: getImages(target) })
    } catch (error) {
      ElMessage.error('获取物资详情失败')
      return
    }
  }
  dialog.visible = true
}

const handleImageUpload = async (file) => {
  const raw = file?.raw || file
  if (!raw) return
  if (form.images.length >= MAX_WAREHOUSE_FORM_IMAGES) {
    ElMessage.warning(`最多上传${MAX_WAREHOUSE_FORM_IMAGES}张图片`)
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

  imageUploading.value = true
  imageUploadProgress.value = 0
  try {
    const result = await uploadFileByChunks(raw, {
      category: 'warehouse',
      subDir: String(form.specification || 'items').trim() || 'items',
      chunkSize: 1024 * 1024,
      maxRetries: 3,
      retryDelay: 800,
      onProgress: (percent) => {
        imageUploadProgress.value = percent
      }
    })
    const fileUrl = String(result?.file_url || '')
    if (!fileUrl) {
      throw new Error('上传成功但未返回图片地址')
    }
    form.images.push(fileUrl)
    imageUploadProgress.value = 100
    ElMessage.success('图片上传成功')
  } catch (error) {
    console.error(error)
    ElMessage.error(error?.response?.data?.error || error?.message || '图片上传失败')
  } finally {
    imageUploading.value = false
  }
}

const removeImage = (index) => {
  if (index < 0 || index >= form.images.length) return
  form.images.splice(index, 1)
}

const clearImages = () => {
  form.images = []
}

const submitForm = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    dialog.submitting = true
    try {
      const payload = {
        procurement_date: form.procurement_date,
        item_name: form.item_name,
        specification: form.specification,
        quantity: form.quantity,
        unit: form.unit,
        location: form.location,
        images: getImages(form),
        remarks: form.remarks
      }
      if (dialog.type === 'add') {
        await warehouseApi.createItem(payload)
        ElMessage.success('新增成功')
      } else {
        await warehouseApi.updateItem(form.id, payload)
        ElMessage.success('更新成功')
      }
      dialog.visible = false
      fetchItems()
    } catch (error) {
      ElMessage.error(error.response?.data?.error || '保存失败')
    } finally {
      dialog.submitting = false
    }
  })
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除物资【${row.item_name}】吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '确认删除',
      cancelButtonText: '取消'
    })
    await warehouseApi.deleteItem(row.id)
    ElMessage.success('删除成功')
    fetchItems()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '删除失败')
    }
  }
}

const handleBatchDelete = async () => {
  if (!selectedItems.value.length) return
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedItems.value.length} 条库存记录吗？`,
      '删除确认',
      {
        type: 'warning',
        confirmButtonText: '确定删除',
        cancelButtonText: '取消'
      }
    )
    loading.value = true
    let successCount = 0
    const failures = []
    for (const row of selectedItems.value) {
      try {
        await warehouseApi.deleteItem(row.id)
        successCount++
      } catch (error) {
        failures.push(`${row.item_name}(ID:${row.id})`)
      }
    }
    await fetchItems()
    selectedItems.value = []
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

onMounted(() => {
  fetchItems()
})
</script>

<style scoped>
.page-container {
  padding: 20px;
  background: var(--card-bg);
  border: 1px solid var(--surface-border);
  border-radius: 18px;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
}

.page-header {
  display: flex;
  align-items: center;
  margin-bottom: 18px;
}

.header-operations {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.search-input {
  width: 260px;
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

:deep(.warehouse-table) {
  --el-table-header-bg-color: var(--surface-muted);
  --el-table-tr-bg-color: var(--card-bg);
  --el-table-bg-color: var(--card-bg);
  --el-fill-color-blank: var(--card-bg);
  --el-table-row-hover-bg-color: rgba(37, 99, 235, 0.06);
  --el-table-border-color: var(--surface-border);
  border-radius: 12px;
  overflow: hidden;
}

:deep(.warehouse-table .el-table__header-wrapper th.el-table__cell) {
  font-weight: 700;
  color: var(--text-main);
  height: 48px;
}

:deep(.warehouse-table .el-table__body-wrapper td.el-table__cell) {
  padding: 12px 0;
}

.table-actions-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  flex-wrap: nowrap;
  white-space: nowrap;
}

:deep(.warehouse-table .el-button--small) {
  padding: 6px 10px;
}

.image-upload-row {
  display: flex;
  align-items: center;
  gap: 14px;
}

.image-upload-card {
  width: 120px;
  height: 120px;
  border: 1px dashed var(--surface-border);
  border-radius: 12px;
  overflow: hidden;
  background: var(--surface-muted);
  transition: border-color .2s ease;
}

.image-upload-card:hover {
  border-color: var(--brand);
}

.image-preview {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.image-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: var(--text-sub);
  font-size: 13px;
}

.image-placeholder-icon {
  font-size: 24px;
}

.image-upload-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-start;
}

.image-upload-tip {
  font-size: 12px;
  color: var(--text-sub);
}

.image-list {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.image-list-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.image-list-thumb {
  width: 88px;
  height: 88px;
  border-radius: 8px;
  object-fit: cover;
}

.pagination-container {
  margin-top: 16px;
  display: flex;
  justify-content: center;
  padding-top: 12px;
  border-top: 1px solid var(--surface-border);
}

@media (max-width: 768px) {
  .search-input {
    width: 100%;
  }
}
</style>
