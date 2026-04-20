<template>
  <div class="page-container">
    <div class="page-header">
      <h2>采购管理</h2>
      <div class="header-operations">
        <el-input
          class="search-input"
          v-model="searchQuery"
          placeholder="搜索维修项目或备注"
          clearable
          @clear="handleSearch"
          @keyup.enter="handleSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button class="toolbar-btn" type="primary" @click="handleSearch">搜索</el-button>
        <el-button class="toolbar-btn" type="primary" @click="openDialog('add')">新增采购</el-button>
        <el-dropdown trigger="click" @command="handleExportCommand">
          <el-button class="toolbar-btn" type="success">
            导出 <el-icon style="margin-left:4px"><Filter /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="excel">导出为 Excel</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-upload
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
      <el-table
        class="procurement-table"
        v-loading="loading"
        :data="procurements"
        border
        style="width: 100%"
        stripe
      >
      <el-table-column prop="id" label="序号" width="80" align="center" />
      <el-table-column prop="procurement_date" label="时间" width="120" sortable />
      <el-table-column prop="item_name" label="维修项目" min-width="150" />
      <el-table-column prop="specification" label="规格" width="120" />
      <el-table-column prop="quantity" label="数量" width="100" align="center" />
      <el-table-column prop="unit_price" label="单价" width="100" align="right">
        <template #default="{ row }">
          ¥{{ Number(row.unit_price || 0).toFixed(2) }}
        </template>
      </el-table-column>
      <el-table-column prop="unit" label="单位" width="90" align="center" />
      <el-table-column prop="total_amount" label="总金额" width="120" align="right">
        <template #default="{ row }">
          ¥{{ row.total_amount }}
        </template>
      </el-table-column>
      <el-table-column prop="remarks" label="备注" min-width="180" show-overflow-tooltip />
      <el-table-column label="图片" width="100" align="center">
        <template #default="{ row }">
          <el-image lazy loading="lazy"
            v-if="getProcurementImages(row).length > 0"
            class="table-image-thumb"
            :src="toImageUrl(getProcurementImages(row)[0])"
            :preview-src-list="getProcurementImages(row).map((v) => toImageUrl(v))"
            fit="cover"
            preview-teleported
          />
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right" align="center">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDialog('edit', row)">编辑</el-button>
          <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
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
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      :title="dialog.title"
      v-model="dialog.visible"
      width="500px"
      @close="resetForm"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
      >
        <el-form-item label="时间" prop="procurement_date">
          <el-date-picker
            v-model="form.procurement_date"
            type="date"
            placeholder="选择日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="维修项目" prop="item_name">
          <el-input v-model="form.item_name" placeholder="请输入维修项目名称" />
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
        <el-form-item label="总金额" prop="total_amount">
          <el-input-number 
            v-model="form.total_amount" 
            :min="0" 
            :precision="2" 
            style="width: 100%"
            placeholder="请输入总金额"
          />
        </el-form-item>
        <el-form-item label="备注" prop="remarks">
          <el-input
            v-model="form.remarks"
            type="textarea"
            :rows="3"
            placeholder="请输入备注信息"
          />
        </el-form-item>
        <el-form-item label="图片">
          <el-upload
            action=""
            :auto-upload="false"
            :show-file-list="false"
            accept="image/*"
            multiple
            :limit="20"
            :on-change="handleProcurementImageChange"
          >
            <el-button type="primary" plain>选择图片(最多20张)</el-button>
          </el-upload>
          <div class="upload-progress-text" v-if="uploadingProcurementImages">上传进度 {{ uploadProgress }}%</div>
          <div class="upload-progress-text">已选 {{ form.procurement_images.length }} / 20</div>
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
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { procurementApi } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Filter } from '@element-plus/icons-vue'
import * as XLSX from 'xlsx'
import { uploadFileByChunks } from '../utils/chunkUploader'

// 状态定义
const loading = ref(false)
const procurements = ref([])
const searchQuery = ref('')
const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const dialog = reactive({
  visible: false,
  title: '新增采购',
  type: 'add', // 'add' or 'edit'
  submitting: false
})
const procurementImageFiles = ref([])
const uploadingProcurementImages = ref(false)
const uploadProgress = ref(0)
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:5000/api'
const API_ORIGIN = API_BASE.replace(/\/api\/?$/, '')

const formRef = ref(null)
const form = reactive({
  id: null,
  procurement_date: '',
  item_name: '',
  specification: '',
  quantity: 1,
  unit_price: 0,
  unit: '',
  total_amount: 0,
  remarks: '',
  procurement_images: []
})

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
    return record.procurement_images.map(v => String(v)).filter(v => v.trim() !== '').slice(0, 20)
  }
  const raw = record?.procurement_image ? String(record.procurement_image) : ''
  if (!raw.trim()) return []
  if (raw.trim().startsWith('[')) {
    try {
      const arr = JSON.parse(raw)
      if (Array.isArray(arr)) {
        return arr.map(v => String(v)).filter(v => v.trim() !== '').slice(0, 20)
      }
    } catch (_) {}
  }
  return [raw]
}

const getProcurementImages = (record) => parseProcurementImages(record)

const rules = {
  procurement_date: [{ required: true, message: '?????', trigger: 'change' }],
  item_name: [{ required: true, message: '?????????', trigger: 'blur' }],
  quantity: [{ required: true, message: '?????', trigger: 'blur' }],
  unit_price: [{ required: true, message: '?????', trigger: 'blur' }],
  unit: [{ required: true, message: '?????', trigger: 'blur' }],
  total_amount: [{ required: true, message: '??????', trigger: 'blur' }]
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

// 获取数据
const fetchProcurements = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      search: searchQuery.value,
      fields: 'id,procurement_date,item_name,specification,quantity,unit_price,unit,total_amount,remarks,procurement_images,procurement_image,created_at,updated_at'
    }
    const res = await procurementApi.listProcurements(params)
    procurements.value = res.data.procurements
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

// 打开对话框
const openDialog = (type, row = null) => {
  dialog.type = type
  dialog.title = type === 'add' ? '????' : '????'
  dialog.visible = true

  revokeProcurementPreviewUrls()
  procurementImageFiles.value = []
  uploadingProcurementImages.value = false
  uploadProgress.value = 0
  if (type === 'edit' && row) {
    Object.assign(form, { ...row, procurement_images: parseProcurementImages(row) })
  } else {
    const today = new Date().toISOString().split('T')[0]
    Object.assign(form, {
      id: null,
      procurement_date: today,
      item_name: '',
      specification: '',
      quantity: 1,
      unit_price: 0,
      unit: '',
      total_amount: 0,
      remarks: '',
      procurement_images: []
    })
  }
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

const handleProcurementImageChange = (file) => {
  if (!file || !file.raw) return
  if (form.procurement_images.length >= 20) {
    ElMessage.warning('????20???')
    return
  }
  if (!String(file.raw.type || '').startsWith('image/')) {
    ElMessage.warning('???????')
    return
  }
  if (file.raw.size && file.raw.size > 20 * 1024 * 1024) {
    ElMessage.warning('???????? 20MB ??')
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

// 提交表单
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
        quantity: Number(form.quantity || 0),
        unit_price: Number(form.unit_price || 0),
        unit: form.unit,
        total_amount: Number(form.total_amount || 0),
        remarks: form.remarks,
        procurement_images: (form.procurement_images || []).filter(v => typeof v === 'string' && !v.startsWith('blob:')).slice(0, 20)
      }

      let targetId = form.id
      if (dialog.type === 'add') {
        const created = await procurementApi.createProcurement(payload)
        targetId = created?.data?.id
        ElMessage.success('????')
      } else {
        await procurementApi.updateProcurement(form.id, payload)
        ElMessage.success('????')
      }

      if (targetId && procurementImageFiles.value.length > 0) {
        uploadingProcurementImages.value = true
        uploadProgress.value = 0
        const uploadedUrls = []
        const total = procurementImageFiles.value.length

        for (let i = 0; i < total; i++) {
          const item = procurementImageFiles.value[i]
          const result = await uploadFileByChunks(item.file, {
            category: 'procurements',
            subDir: buildProcurementUploadSubDir(targetId),
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
            throw new Error('????????????')
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

        await procurementApi.updateProcurement(targetId, { procurement_images: finalImages })
        form.procurement_images = finalImages
        uploadProgress.value = 100
      }

      procurementImageFiles.value = []
      uploadingProcurementImages.value = false
      uploadProgress.value = 0
      dialog.visible = false
      fetchProcurements()
    } catch (error) {
      console.error(error)
      ElMessage.error(dialog.type === 'add' ? '????' : '????')
    } finally {
      dialog.submitting = false
    }
  })
}

// 删除
const handleDelete = (row) => {
  ElMessageBox.confirm(
    `确定要删除该条采购记录吗？（项目：${row.item_name}）`,
    '警告',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await procurementApi.deleteProcurement(row.id)
      ElMessage.success('删除成功')
      fetchProcurements()
    } catch (error) {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

// 导出 Excel
const handleExportCommand = (cmd) => {
  if (cmd === 'excel') {
    try {
      const rows = procurements.value.map(p => ({
        序号: p.id,
        时间: p.procurement_date,
        维修项目: p.item_name,
        规格: p.specification,
        数量: p.quantity,
        单价: p.unit_price,
        单位: p.unit,
        总金额: p.total_amount,
        备注: p.remarks,
        图片: getProcurementImages(p).join(',')
      }))
      const ws = XLSX.utils.json_to_sheet(rows)
      const wb = XLSX.utils.book_new()
      XLSX.utils.book_append_sheet(wb, ws, '采购记录')
      XLSX.writeFile(wb, `采购记录_${new Date().toLocaleDateString()}.xlsx`)
      ElMessage.success('导出成功')
    } catch (e) {
      console.error(e)
      ElMessage.error('导出失败')
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
          item_name: row['采购项目'] || row['维修项目'] || '',
          specification: row['规格'] || '',
          quantity: Number(row['数量'] || 1),
          unit_price: Number(row['单价'] || 0),
          unit: row['单位'] || '',
          total_amount: Number(row['总金额'] || 0),
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
  fetchProcurements()
})
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  margin-bottom: 18px;
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

.table-image-thumb {
  width: 40px;
  height: 40px;
  border-radius: 6px;
}

.upload-progress-text {
  margin-top: 8px;
  color: #64748b;
  font-size: 12px;
}

.image-preview-wrap {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
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
  .search-input {
    width: 100%;
  }
}
</style>
