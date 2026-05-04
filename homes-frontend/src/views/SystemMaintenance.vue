<template>
  <div class="system-container page-container">
    <div class="system-hero">
      <div>
        <h2 class="hero-title">系统维护中心</h2>
        <p class="hero-subtitle">统一管理备份恢复、OCR 配置、系统重置和演示数据生成</p>
      </div>
      <el-tag class="hero-tag" effect="dark">高安全操作区</el-tag>
    </div>

    <div class="system-top-grid">
      <!-- 导出数据 -->
      <div class="system-grid-item">
        <div class="card-box h-100 system-card">
          <div class="card-header">
            <el-icon class="icon"><Download /></el-icon>
            <h3>数据导出</h3>
          </div>
          <div class="card-content">
            <div class="description">
              导出系统完整数据，包含：
              <ul>
                <li>数据库所有记录（房间、租户、合同等）</li>
                <li>系统配置文件（通知设置等）</li>
                <li>所有上传的文件（身份证图片、维修图片等）</li>
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
      </div>

      <!-- 导入数据 -->
      <div class="system-grid-item">
        <div class="card-box h-100 system-card">
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
                <el-button link type="danger" @click="selectedFile = null; importUploadProgress = 0">移除</el-button>
              </div>

              <div class="action-area" v-if="selectedFile">
                <el-button type="warning" size="large" :loading="importing" @click="handleImport">
                  <el-icon class="el-icon--left"><Refresh /></el-icon>
                  立即导入备份
                </el-button>
              </div>

              <div v-if="importing || importUploadProgress > 0" class="upload-progress-wrap">
                <el-progress :percentage="importUploadProgress" :stroke-width="8" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="system-feature-section">
      <div class="system-grid-item">
        <div class="card-box h-100 system-card">
          <div class="card-header">
            <el-icon class="icon"><Setting /></el-icon>
            <h3>房间设施配置</h3>
          </div>
          <div class="card-content">
            <div class="description">
              在这里维护房间管理页可勾选的设施项，例如冰箱、热水器、沙发。保存后房间管理页会自动使用最新选项。
            </div>

            <div class="feature-editor">
              <div class="feature-input-wrap">
                <el-input
                  v-model="newRoomFeature"
                  placeholder="输入新设施项，例如：沙发"
                  @keyup.enter="addRoomFeature"
                />
                <el-button type="primary" :loading="savingRoomFeatures" @click="addRoomFeature">添加设施项</el-button>
              </div>
              <div class="feature-hint">新增或删除后会自动保存，不需要再额外点保存按钮。</div>
            </div>

            <div class="feature-tags">
              <el-tag
                v-for="item in roomFeatureOptions"
                :key="item"
                closable
                @close="removeRoomFeature(item)"
              >
                {{ item }}
              </el-tag>
            </div>
          </div>
        </div>
      </div>

      <div class="system-grid-item">
        <div class="card-box h-100 system-card">
          <div class="card-header">
            <el-icon class="icon"><Cpu /></el-icon>
            <h3>本地 AI 模型配置</h3>
          </div>
          <div class="card-content">
            <div class="description">
              设置采购管理页和维修记录页 “AI 输入” 使用的本地 Ollama 模型。4b 更稳，2b 更均衡，0.8b 更快更省内存。
            </div>

            <el-form label-position="top" class="ocr-settings-form">
              <el-form-item label="本地 AI 功能">
                <el-switch
                  v-model="aiSettings.enabled"
                  :disabled="isAiSwitching"
                  active-text="启用"
                  inactive-text="停用"
                  @change="toggleAiEnabled"
                />
              </el-form-item>
              <el-form-item label="Ollama 服务地址">
                <el-input
                  v-model="aiSettings.ollama_base_url"
                  placeholder="http://127.0.0.1:11434"
                  :disabled="isAiSwitching"
                  clearable
                />
              </el-form-item>
              <el-form-item label="采购 AI 模型">
                <el-select v-model="aiSettings.procurement_model" style="width: 100%" :disabled="isAiSwitching || !aiSettings.enabled">
                  <el-option
                    v-for="model in aiSettings.available_procurement_models"
                    :key="model"
                    :label="model"
                    :value="model"
                  />
                </el-select>
              </el-form-item>
              <div class="feature-hint">
                当前支持 qwen3.5:4b、qwen3.5:2b 和 qwen3.5:0.8b。Ollama 和后端同机时使用 http://127.0.0.1:11434；远程部署时填写 http://另一台机器IP:11434。
              </div>
              <div v-if="!isLocalOllamaEndpoint" class="feature-hint warning-text">
                当前是远程 Ollama 地址，本系统无法关闭远程机器上的模型，只能切换当前调用的模型和地址。
              </div>
              <div class="ocr-status-row">
                <el-tag :type="aiSwitchStatusTagType">
                  {{ aiSwitchStatusLabel }}
                </el-tag>
                <span class="ocr-status-text">
                  {{ aiSettings.enabled ? (aiSwitchStatus.message || '本地 AI 功能已启用') : (aiSwitchStatus.message || '本地 AI 功能已停用') }}
                </span>
              </div>
              <div v-if="aiSwitchStatus.status === 'running'" class="upload-progress-wrap">
                <el-progress :percentage="aiSwitchProgress" :indeterminate="true" :stroke-width="8" />
              </div>
              <div v-if="aiSwitchStatus.error" class="feature-hint warning-text">{{ aiSwitchStatus.error }}</div>

              <div class="action-area">
                <el-button type="primary" :loading="savingAiSettings || isAiSwitching" @click="saveAiSettings">
                  切换 AI 模型
                </el-button>
              </div>
            </el-form>
          </div>
        </div>
      </div>

      <div class="system-grid-item">
        <div class="card-box h-100 system-card">
          <div class="card-header">
            <el-icon class="icon"><Key /></el-icon>
            <h3>阿里云 OCR 配置</h3>
          </div>
          <div class="card-content">
            <div class="description">
              在这里填写阿里云 OCR 的 AccessKey，并设置身份证识别总次数上限。达到上限后，自助入住页的身份证识别按钮会自动禁用。
            </div>

            <el-form label-position="top" class="ocr-settings-form">
              <el-form-item label="AccessKey ID">
                <el-input v-model="ocrSettings.access_key_id" placeholder="请输入 ALIBABA_CLOUD_ACCESS_KEY_ID" />
              </el-form-item>
              <el-form-item label="AccessKey Secret">
                <el-input
                  v-model="ocrSettings.access_key_secret"
                  type="password"
                  show-password
                  placeholder="请输入 ALIBABA_CLOUD_ACCESS_KEY_SECRET"
                />
              </el-form-item>
              <el-form-item label="OCR Endpoint">
                <el-input v-model="ocrSettings.endpoint" placeholder="默认：ocr-api.cn-hangzhou.aliyuncs.com" />
              </el-form-item>
              <el-form-item label="身份证识别总次数上限">
                <el-input-number v-model="ocrSettings.max_recognitions" :min="0" :step="1" style="width: 100%" />
              </el-form-item>
              <div class="feature-hint">填 `0` 表示不限制次数；比如填 `10`，累计识别 10 次后按钮会自动禁用。</div>

              <div class="ocr-status-row">
                <el-tag :type="ocrSettings.enabled ? 'success' : 'warning'">
                  {{ ocrSettings.enabled ? '当前可用' : '当前不可用' }}
                </el-tag>
                <span class="ocr-status-text">
                  已使用 {{ ocrSettings.used_count || 0 }} 次
                  <template v-if="ocrSettings.max_recognitions > 0">
                    ，剩余 {{ ocrSettings.remaining_count ?? 0 }} / {{ ocrSettings.max_recognitions }} 次
                  </template>
                </span>
              </div>
              <div v-if="ocrSettings.reason" class="feature-hint">{{ ocrSettings.reason }}</div>

              <div class="action-area">
                <el-button type="primary" :loading="savingOcrSettings" @click="saveOcrSettings">
                  保存 OCR 配置
                </el-button>
              </div>
            </el-form>
          </div>
        </div>
      </div>
    </div>

    <div class="system-danger-section">
      <div class="system-grid-item">
        <div class="card-box h-100 system-card">
          <div class="card-header">
            <el-icon class="icon"><Document /></el-icon>
            <h3>系统操作日志</h3>
          </div>
          <div class="card-content">
            <div class="log-toolbar">
              <el-input
                v-model="logQuery.keyword"
                placeholder="搜索用户、路径、操作或内容"
                clearable
                @keyup.enter="fetchSystemLogs"
              />
              <el-select v-model="logQuery.module" placeholder="模块" clearable>
                <el-option label="系统" value="system" />
                <el-option label="登录" value="login" />
                <el-option label="房间" value="rooms" />
                <el-option label="租户" value="tenants" />
                <el-option label="维修" value="repair-records" />
                <el-option label="采购" value="procurements" />
                <el-option label="库存" value="warehouse" />
                <el-option label="公开链接" value="public-entry" />
              </el-select>
              <el-button type="primary" :loading="logsLoading" @click="fetchSystemLogs">查询</el-button>
            </div>

            <el-table :data="systemLogs" v-loading="logsLoading" border class="logs-table" empty-text="暂无操作日志">
              <el-table-column prop="created_at" label="时间" width="160" />
              <el-table-column prop="username" label="用户" width="100">
                <template #default="{ row }">{{ row.username || '公开/系统' }}</template>
              </el-table-column>
              <el-table-column prop="action" label="操作" width="110" />
              <el-table-column prop="module" label="模块" width="130" />
              <el-table-column prop="method" label="方法" width="78" />
              <el-table-column prop="status_code" label="状态" width="78" />
              <el-table-column prop="path" label="路径" min-width="220" show-overflow-tooltip />
              <el-table-column prop="ip_address" label="IP" width="130" />
            </el-table>

            <el-pagination
              class="logs-pagination"
              layout="total, prev, pager, next"
              :total="logPagination.total"
              :page-size="logPagination.page_size"
              :current-page="logPagination.page"
              @current-change="handleLogPageChange"
            />
          </div>
        </div>
      </div>

      <div class="system-grid-item">
        <div class="card-box danger-zone system-card danger-card">
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
            
            <div class="danger-row danger-row-divider">
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
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Download, Upload, UploadFilled, Document, Refresh, Delete, MagicStick, Setting, Key, Cpu } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { systemApi } from '../api'
import { uploadFileByChunks } from '../utils/chunkUploader'

const exporting = ref(false)
const importing = ref(false)
const resetting = ref(false)
const seeding = ref(false)
const selectedFile = ref(null)
const importUploadProgress = ref(0)
const roomFeatureOptions = ref([])
const newRoomFeature = ref('')
const savingRoomFeatures = ref(false)
const savingOcrSettings = ref(false)
const savingAiSettings = ref(false)
const logsLoading = ref(false)
const systemLogs = ref([])
const logQuery = ref({
  keyword: '',
  module: '',
})
const logPagination = ref({
  page: 1,
  page_size: 20,
  total: 0,
})
let aiSwitchPollTimer = null
const ocrSettings = ref({
  access_key_id: '',
  access_key_secret: '',
  endpoint: 'ocr-api.cn-hangzhou.aliyuncs.com',
  max_recognitions: 0,
  used_count: 0,
  remaining_count: null,
  enabled: false,
  reason: '',
})
const aiSettings = ref({
  enabled: true,
  procurement_model: 'qwen3.5:4b',
  ollama_base_url: 'http://127.0.0.1:11434',
  available_procurement_models: ['qwen3.5:4b', 'qwen3.5:2b', 'qwen3.5:0.8b'],
  updated_at: '',
})
const aiSwitchStatus = ref({
  status: 'idle',
  phase: '',
  message: '未执行切换',
  from_model: '',
  to_model: '',
  started_at: '',
  finished_at: '',
  error: '',
})
const isAiSwitching = computed(() => aiSwitchStatus.value.status === 'running')
const isLocalOllamaEndpoint = computed(() => {
  const raw = String(aiSettings.value.ollama_base_url || '').trim().toLowerCase()
  if (!raw) return true
  try {
    const value = raw.includes('://') ? raw : `http://${raw}`
    const host = new URL(value).hostname.toLowerCase()
    return ['', 'localhost', '127.0.0.1', '::1'].includes(host)
  } catch (_) {
    return false
  }
})
const aiSwitchProgress = computed(() => {
  if (aiSwitchStatus.value.phase === 'stopping_old') return 35
  if (aiSwitchStatus.value.phase === 'starting_new') return 75
  if (aiSwitchStatus.value.phase === 'completed') return 100
  return isAiSwitching.value ? 20 : 0
})
const aiSwitchStatusLabel = computed(() => {
  const status = aiSwitchStatus.value.status
  if (status === 'running') return '切换中'
  if (status === 'completed') return '已完成'
  if (status === 'failed') return '失败'
  return '空闲'
})
const aiSwitchStatusTagType = computed(() => {
  const status = aiSwitchStatus.value.status
  if (status === 'running') return 'warning'
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'danger'
  return 'info'
})
const getAiActionSuccessMessage = () => {
  const phase = aiSwitchStatus.value.phase
  if (phase === 'disabled') return 'AI 功能已停用'
  if (phase === 'enabled') return 'AI 功能已启用'
  return 'AI 模型切换完成'
}
const getAiActionFailureMessage = () => {
  const phase = aiSwitchStatus.value.phase
  if (phase === 'disabled') return 'AI 功能停用失败'
  if (phase === 'enabled') return 'AI 功能启用失败'
  return 'AI 模型切换失败'
}

const applyAiSettingsResponse = (data = {}) => {
  aiSettings.value = {
    enabled: data?.enabled !== false,
    procurement_model: data?.procurement_model || 'qwen3.5:4b',
    ollama_base_url: data?.ollama_base_url || 'http://127.0.0.1:11434',
    available_procurement_models: data?.available_procurement_models || ['qwen3.5:4b', 'qwen3.5:2b', 'qwen3.5:0.8b'],
    updated_at: data?.updated_at || '',
  }
  if (data?.switch_status) {
    aiSwitchStatus.value = {
      status: data.switch_status.status || 'idle',
      phase: data.switch_status.phase || '',
      message: data.switch_status.message || '',
      from_model: data.switch_status.from_model || '',
      to_model: data.switch_status.to_model || '',
      started_at: data.switch_status.started_at || '',
      finished_at: data.switch_status.finished_at || '',
      error: data.switch_status.error || '',
    }
  }
}

const stopAiSwitchPolling = () => {
  if (aiSwitchPollTimer) {
    clearInterval(aiSwitchPollTimer)
    aiSwitchPollTimer = null
  }
}

const pollAiSwitchStatus = async () => {
  try {
    const response = await systemApi.getAiSwitchStatus()
    applyAiSettingsResponse(response?.data || {})
    if (aiSwitchStatus.value.status === 'completed') {
      stopAiSwitchPolling()
      savingAiSettings.value = false
      ElMessage.success(getAiActionSuccessMessage())
    } else if (aiSwitchStatus.value.status === 'failed') {
      stopAiSwitchPolling()
      savingAiSettings.value = false
      ElMessage.error(aiSwitchStatus.value.error || getAiActionFailureMessage())
    }
  } catch (error) {
    stopAiSwitchPolling()
    savingAiSettings.value = false
    ElMessage.error(error?.response?.data?.error || '获取 AI 模型切换状态失败')
  }
}

const startAiSwitchPolling = () => {
  stopAiSwitchPolling()
  aiSwitchPollTimer = setInterval(pollAiSwitchStatus, 1500)
}

const fetchRoomFeatureOptions = async () => {
  try {
    const response = await systemApi.getRoomFeatureOptions()
    roomFeatureOptions.value = response?.data?.options || []
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '加载房间设施配置失败')
  }
}

const fetchOcrSettings = async () => {
  try {
    const response = await systemApi.getOcrSettings()
    ocrSettings.value = {
      access_key_id: response?.data?.access_key_id || '',
      access_key_secret: response?.data?.access_key_secret || '',
      endpoint: response?.data?.endpoint || 'ocr-api.cn-hangzhou.aliyuncs.com',
      max_recognitions: Number(response?.data?.max_recognitions || 0),
      used_count: Number(response?.data?.used_count || 0),
      remaining_count: response?.data?.remaining_count ?? null,
      enabled: Boolean(response?.data?.enabled),
      reason: response?.data?.reason || '',
    }
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '加载 OCR 配置失败')
  }
}

const saveOcrSettings = async () => {
  savingOcrSettings.value = true
  try {
    const response = await systemApi.updateOcrSettings({
      access_key_id: ocrSettings.value.access_key_id,
      access_key_secret: ocrSettings.value.access_key_secret,
      endpoint: ocrSettings.value.endpoint,
      max_recognitions: Number(ocrSettings.value.max_recognitions || 0),
    })
    ocrSettings.value = {
      access_key_id: response?.data?.access_key_id || '',
      access_key_secret: response?.data?.access_key_secret || '',
      endpoint: response?.data?.endpoint || 'ocr-api.cn-hangzhou.aliyuncs.com',
      max_recognitions: Number(response?.data?.max_recognitions || 0),
      used_count: Number(response?.data?.used_count || 0),
      remaining_count: response?.data?.remaining_count ?? null,
      enabled: Boolean(response?.data?.enabled),
      reason: response?.data?.reason || '',
    }
    ElMessage.success('OCR 配置已保存')
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '保存 OCR 配置失败')
  } finally {
    savingOcrSettings.value = false
  }
}

const fetchAiSettings = async () => {
  try {
    const response = await systemApi.getAiSettings()
    applyAiSettingsResponse(response?.data || {})
    if (aiSwitchStatus.value.status === 'running') {
      savingAiSettings.value = true
      startAiSwitchPolling()
    }
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '加载 AI 模型配置失败')
  }
}

const runAiAction = async (action, successMessage) => {
  savingAiSettings.value = true
  try {
    const response = await systemApi.updateAiSettings({
      action,
      procurement_model: aiSettings.value.procurement_model,
      ollama_base_url: aiSettings.value.ollama_base_url,
    })
    applyAiSettingsResponse(response?.data || {})
    ElMessage.success(successMessage)
    startAiSwitchPolling()
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || 'AI 操作失败')
    await fetchAiSettings()
    savingAiSettings.value = false
  }
}

const toggleAiEnabled = async (value) => {
  await runAiAction(value ? 'enable' : 'disable', value ? 'AI 功能启用已开始' : 'AI 功能停用已开始')
}

const saveAiSettings = async () => {
  if (!aiSettings.value.enabled) {
    ElMessage.warning('请先启用本地 AI 功能，再切换模型')
    return
  }
  await runAiAction('switch_model', 'AI 模型切换已开始')
}

const addRoomFeature = () => {
  const text = String(newRoomFeature.value || '').trim()
  if (!text) return
  if (!roomFeatureOptions.value.includes(text)) {
    roomFeatureOptions.value = [...roomFeatureOptions.value, text]
  }
  newRoomFeature.value = ''
  saveRoomFeatures()
}

const removeRoomFeature = (item) => {
  roomFeatureOptions.value = roomFeatureOptions.value.filter(v => v !== item)
  saveRoomFeatures()
}

const saveRoomFeatures = async () => {
  savingRoomFeatures.value = true
  try {
    const response = await systemApi.updateRoomFeatureOptions({ options: roomFeatureOptions.value })
    roomFeatureOptions.value = response?.data?.options || roomFeatureOptions.value
    ElMessage.success('房间设施配置已保存')
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '保存房间设施配置失败')
  } finally {
    savingRoomFeatures.value = false
  }
}

const fetchSystemLogs = async () => {
  logsLoading.value = true
  try {
    const response = await systemApi.listLogs({
      page: logPagination.value.page,
      page_size: logPagination.value.page_size,
      keyword: logQuery.value.keyword,
      module: logQuery.value.module,
    })
    systemLogs.value = response?.data?.logs || []
    logPagination.value = {
      ...logPagination.value,
      ...(response?.data?.pagination || {}),
    }
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '加载系统日志失败')
  } finally {
    logsLoading.value = false
  }
}

const handleLogPageChange = (page) => {
  logPagination.value.page = page
  fetchSystemLogs()
}

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
    let message = error.response?.data?.error || error.message
    if (error.response?.data instanceof Blob) {
      try {
        const text = await error.response.data.text()
        const json = JSON.parse(text)
        message = json.error || message
      } catch (_) {}
    }
    ElMessage.error('导出失败: ' + message)
  } finally {
    exporting.value = false
  }
}

const handleFileChange = (file) => {
  const raw = file?.raw
  if (!raw) return
  if (raw.type !== 'application/x-zip-compressed' && !String(raw.name || '').toLowerCase().endsWith('.zip')) {
    ElMessage.warning('只能上传 .zip 格式的备份文件')
    return
  }
  selectedFile.value = raw
  importUploadProgress.value = 0
}

const buildImportSubDir = () => {
  const day = new Date().toISOString().slice(0, 10).replace(/-/g, '')
  return `system/${day}`
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
      importUploadProgress.value = 0
      const uploadResult = await uploadFileByChunks(selectedFile.value, {
        category: 'system_import',
        subDir: buildImportSubDir(),
        chunkSize: 1024 * 1024,
        maxRetries: 3,
        retryDelay: 800,
        onProgress: (percent) => {
          importUploadProgress.value = percent
        }
      })
      const fileUrl = uploadResult?.file_url
      if (!fileUrl) {
        throw new Error('上传成功但未返回 file_url')
      }
      await systemApi.importData(fileUrl)
      importUploadProgress.value = 100
      ElMessage.success('系统数据导入成功')
      selectedFile.value = null
      // Optional: Refresh page or logout
      setTimeout(() => {
        window.location.reload()
      }, 1500)
    } catch (error) {
      console.error(error)
      importUploadProgress.value = 0
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
  ).then(() => {
    ElMessageBox.prompt(
      '请输入 RESET 确认执行系统重置',
      '二次确认',
      {
        confirmButtonText: '确认重置',
        cancelButtonText: '取消',
        inputPattern: /^RESET$/,
        inputErrorMessage: '请输入大写 RESET',
        type: 'error'
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

onMounted(() => {
  fetchRoomFeatureOptions()
  fetchOcrSettings()
  fetchAiSettings()
  fetchSystemLogs()
})

onBeforeUnmount(() => {
  stopAiSwitchPolling()
})
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

.system-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.system-hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 20px;
  border-radius: 16px;
  background: linear-gradient(135deg, #2563eb 0%, #0ea5e9 100%);
  color: #fff;
  box-shadow: 0 14px 30px rgba(37, 99, 235, 0.24);
}

.hero-title {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
}

.hero-subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  opacity: 0.92;
}

.hero-tag {
  border: none;
  color: #fff;
  background: rgba(255, 255, 255, 0.16);
}

.card-box {
  display: flex;
  flex-direction: column;
  margin-bottom: 0;
  padding: 20px;
}

.system-card {
  border-radius: 16px;
  box-shadow: none;
  border: 1px solid var(--surface-border, var(--el-border-color-light));
  background: var(--card-bg, #fff);
}

.h-100 {
  height: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 14px;
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
  margin-bottom: 16px;
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
  margin-top: 0;
  text-align: left;
  padding-top: 0;
}

.upload-area {
  margin-top: 0;
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

.upload-progress-wrap {
  margin-top: 14px;
}

.log-toolbar {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) 160px auto;
  gap: 10px;
  margin-bottom: 12px;
}

.logs-table {
  width: 100%;
}

.logs-pagination {
  margin-top: 12px;
  justify-content: flex-end;
}

:deep(.el-upload-dragger) {
  background-color: var(--bg-color);
  border-color: var(--el-border-color);
}

:deep(.el-upload-dragger:hover) {
  border-color: var(--el-color-primary);
}

.system-top-grid,
.system-feature-section,
.system-danger-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.system-grid-item {
  width: 100%;
}

.system-top-grid .system-card {
  min-height: auto;
}

.system-top-grid .card-content {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 18px;
  align-items: center;
}

.system-top-grid .description {
  margin-bottom: 0;
}

.system-top-grid .action-area,
.system-top-grid .upload-area {
  width: min(420px, 100%);
}

@media (max-width: 768px) {
  .system-top-grid .card-content {
    grid-template-columns: 1fr;
  }

  .log-toolbar {
    grid-template-columns: 1fr;
  }

  .system-top-grid,
  .system-feature-section,
  .system-danger-section {
    gap: 16px;
  }
}

.danger-zone {
  border: 1px solid var(--el-color-danger-light-5);
  box-shadow: 0 12px 30px rgba(239, 68, 68, 0.12);
}

.danger-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
}

.danger-row-divider {
  border-top: 1px dashed var(--surface-border);
  margin-top: 16px;
  padding-top: 16px;
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

.feature-editor {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.feature-input-wrap {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
}

.feature-hint {
  font-size: 12px;
  color: var(--text-secondary);
}

.ocr-settings-form {
  display: flex;
  flex-direction: column;
}

.ocr-status-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 8px;
}

.ocr-status-text {
  font-size: 13px;
  color: var(--text-secondary);
}

.feature-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px dashed var(--surface-border);
}

.feature-tags :deep(.el-tag) {
  padding: 8px 12px;
  border-radius: 12px;
  font-size: 14px;
}

@media (max-width: 900px) {
  .system-hero {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
}

@media (max-width: 768px) {
  .danger-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
}
</style>
