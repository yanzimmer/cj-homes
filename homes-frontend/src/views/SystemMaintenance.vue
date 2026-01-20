<template>
  <div class="system-container page-container">
    <div class="page-header">
      <h2>系统维护</h2>
      <span class="subtitle">数据备份与迁移</span>
    </div>

    <el-row :gutter="24">
      <!-- 导出数据 -->
      <el-col :span="12" :xs="24">
        <div class="card-box h-100">
          <div class="card-header">
            <el-icon class="icon"><Download /></el-icon>
            <h3>数据导出</h3>
          </div>
          <div class="card-content">
            <div class="description">
              导出系统完整数据，包含：
              <ul>
                <li>数据库所有记录（房间、租户、合同等）</li>
                <li>系统配置文件（通知设置、OCR设置）</li>
                <li>所有上传的文件（身份证图片等）</li>
              </ul>
            </div>
            <div class="action-area">
              <el-button type="primary" size="large" :loading="exporting" @click="handleExport">
                <el-icon class="el-icon--left"><Download /></el-icon>
                立即导出备份 (.zip)
              </el-button>
            </div>
          </div>
        </div>
      </el-col>

      <!-- 导入数据 -->
      <el-col :span="12" :xs="24">
        <div class="card-box h-100">
          <div class="card-header">
            <el-icon class="icon"><Upload /></el-icon>
            <h3>数据导入</h3>
          </div>
          <div class="card-content">
            <div class="description">
              从备份文件恢复系统数据。
              <span class="warning-text">注意：导入将覆盖当前系统的所有数据！请谨慎操作。</span>
            </div>
            
            <div class="upload-area">
              <el-upload
                class="upload-demo"
                drag
                action="#"
                :auto-upload="false"
                :on-change="handleFileChange"
                :show-file-list="false"
                accept=".zip"
              >
                <el-icon class="el-icon--upload"><upload-filled /></el-icon>
                <div class="el-upload__text">
                  将备份文件拖到此处，或 <em>点击上传</em>
                </div>
                <template #tip>
                  <div class="el-upload__tip">
                    只能上传 .zip 格式的备份文件
                  </div>
                </template>
              </el-upload>

              <div v-if="selectedFile" class="selected-file">
                <el-icon><Document /></el-icon>
                <span>{{ selectedFile.name }}</span>
                <el-button link type="danger" @click="selectedFile = null">移除</el-button>
              </div>

              <div class="action-area" v-if="selectedFile">
                <el-button type="warning" size="large" :loading="importing" @click="handleImport">
                  <el-icon class="el-icon--left"><Refresh /></el-icon>
                  确认恢复数据
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </el-col>

      <!-- 系统重置 -->
      <el-col :span="24" class="mt-4">
        <div class="card-box danger-zone">
          <div class="card-header">
            <el-icon class="icon danger"><Delete /></el-icon>
            <h3>危险区域</h3>
          </div>
          <div class="card-content">
            <div class="danger-row">
              <div class="danger-info">
                <h4>重置系统数据</h4>
                <p>将删除所有房间、租户、合同、维修记录及上传文件，仅保留管理员账号。此操作不可撤销！</p>
              </div>
              <el-button type="danger" @click="handleReset" :loading="resetting">
                重置系统
              </el-button>
            </div>
            
            <div class="danger-row" style="border-top: 1px solid var(--el-border-color-light); margin-top: 16px; padding-top: 16px;">
              <div class="danger-info">
                <h4>生成模拟演示数据</h4>
                <p>在清空状态下，自动生成一套包含房间、租户、合同和维修记录的演示数据。</p>
              </div>
              <el-button type="success" @click="handleSeed" :loading="seeding">
                <el-icon class="el-icon--left"><MagicStick /></el-icon>
                生成数据
              </el-button>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Download, Upload, UploadFilled, Document, Refresh, Delete, MagicStick } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { systemApi } from '../api'

const exporting = ref(false)
const importing = ref(false)
const resetting = ref(false)
const seeding = ref(false)
const selectedFile = ref(null)

const handleExport = async () => {
  try {
    exporting.value = true
    const response = await systemApi.exportData()
    
    // Create download link
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    // Try to get filename from headers or default
    const contentDisposition = response.headers['content-disposition']
    let filename = 'homes_backup.zip'
    if (contentDisposition) {
      const match = contentDisposition.match(/filename=(.+)/)
      if (match) filename = match[1]
    }
    link.setAttribute('download', filename)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    
    ElMessage.success('导出成功')
  } catch (error) {
    console.error(error)
    ElMessage.error('导出失败: ' + (error.response?.data?.error || error.message))
  } finally {
    exporting.value = false
  }
}

const handleFileChange = (file) => {
  if (file.raw.type !== 'application/x-zip-compressed' && !file.name.endsWith('.zip')) {
    ElMessage.warning('请选择 .zip 格式的备份文件')
    return
  }
  selectedFile.value = file.raw
}

const handleImport = () => {
  if (!selectedFile.value) return

  ElMessageBox.confirm(
    '此操作将清空当前系统的所有数据（数据库、配置、图片）并用备份数据覆盖，且不可撤销。是否确认继续？',
    '高风险操作警告',
    {
      confirmButtonText: '确认覆盖并恢复',
      cancelButtonText: '取消',
      type: 'warning',
    }
  ).then(async () => {
    try {
      importing.value = true
      await systemApi.importData(selectedFile.value)
      ElMessage.success('数据恢复成功！')
      selectedFile.value = null
      // Optional: Refresh page or logout
      setTimeout(() => {
        window.location.reload()
      }, 1500)
    } catch (error) {
      console.error(error)
      ElMessage.error('导入失败: ' + (error.response?.data?.error || error.message))
    } finally {
      importing.value = false
    }
  }).catch(() => {})
}

const handleReset = () => {
  ElMessageBox.confirm(
    '此操作将永久删除所有业务数据（房间、租户、合同等），仅保留管理员账号。确认要重置系统吗？',
    '最终警告',
    {
      confirmButtonText: '确认重置',
      cancelButtonText: '取消',
      type: 'error',
      confirmButtonClass: 'el-button--danger'
    }
  ).then(async () => {
    try {
      resetting.value = true
      await systemApi.resetSystem()
      ElMessage.success('系统已成功重置')
      setTimeout(() => {
        window.location.reload()
      }, 1500)
    } catch (error) {
      console.error(error)
      ElMessage.error('重置失败: ' + (error.response?.data?.error || error.message))
    } finally {
      resetting.value = false
    }
  }).catch(() => {})
}

const handleSeed = () => {
  ElMessageBox.confirm(
    '此操作将在数据库为空时生成一套演示数据。如果数据库已有数据，请先执行“重置系统”。',
    '生成模拟数据',
    {
      confirmButtonText: '确认生成',
      cancelButtonText: '取消',
      type: 'info'
    }
  ).then(async () => {
    try {
      seeding.value = true
      await systemApi.seedData()
      ElMessage.success('演示数据生成成功！')
      setTimeout(() => {
        window.location.reload()
      }, 1500)
    } catch (error) {
      console.error(error)
      ElMessage.error(error.response?.data?.message || '生成失败: ' + (error.response?.data?.error || error.message))
    } finally {
      seeding.value = false
    }
  }).catch(() => {})
}
</script>

<style scoped>
.page-header {
  margin-bottom: 24px;
}

.page-header h2 {
  margin: 0;
  color: var(--el-color-primary);
}

.subtitle {
  color: var(--text-secondary);
  font-size: 14px;
  margin-top: 5px;
  display: block;
}

.card-box {
  display: flex;
  flex-direction: column;
}

.h-100 {
  height: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--el-border-color-light);
}

.card-header .icon {
  font-size: 24px;
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  padding: 8px;
  border-radius: 8px;
}

.card-header .icon.danger {
  color: var(--el-color-danger);
  background: var(--el-color-danger-light-9);
}

.card-header h3 {
  margin: 0;
  font-size: 18px;
  color: var(--text-main);
}

.card-content {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.description {
  color: var(--text-regular);
  line-height: 1.6;
  margin-bottom: 24px;
}

.description ul {
  padding-left: 20px;
  margin-top: 8px;
  color: var(--text-secondary);
}

.warning-text {
  display: block;
  margin-top: 8px;
  color: var(--el-color-danger);
  font-weight: bold;
}

.action-area {
  margin-top: auto;
  text-align: center;
  padding-top: 20px;
}

.upload-area {
  margin-top: auto;
}

.selected-file {
  margin-top: 16px;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-main);
}

:deep(.el-upload-dragger) {
  background-color: var(--bg-color);
  border-color: var(--el-border-color);
}

:deep(.el-upload-dragger:hover) {
  border-color: var(--el-color-primary);
}

.mt-4 {
  margin-top: 24px;
}

.danger-zone {
  border: 1px solid var(--el-color-danger-light-5);
}

.danger-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
}

.danger-info h4 {
  margin: 0 0 8px 0;
  color: var(--text-main);
}

.danger-info p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 14px;
}
</style>
