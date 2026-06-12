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
        <div class="card-box h-100 system-card import-card">
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

            <div class="rollback-box">
              <div class="rollback-header">
                <div>
                  <div>系统快照</div>
                  <div class="rollback-subtitle">快照统一存放在专用文件夹，支持手动创建、导入前自动留档，以及按版本回滚。</div>
                </div>
                <el-tag :type="snapshots.length ? 'warning' : 'info'" size="small">
                  {{ snapshots.length ? `${snapshots.length} 份快照` : '暂无快照' }}
                </el-tag>
              </div>
              <div class="action-area rollback-action">
                <el-button
                  type="primary"
                  plain
                  :disabled="isSnapshotTaskRunning || importing"
                  :loading="isCreatingSnapshot"
                  @click="handleCreateSnapshot"
                >
                  <el-icon class="el-icon--left"><Document /></el-icon>
                  立即创建快照
                </el-button>
                <el-button
                  type="danger"
                  plain
                  :disabled="!selectedSnapshot || isSnapshotTaskRunning || importing"
                  :loading="isRestoringSnapshot"
                  @click="handleRollbackImport"
                >
                  <el-icon class="el-icon--left"><Refresh /></el-icon>
                  一键回滚
                </el-button>
              </div>

              <div v-if="latestSnapshot" class="rollback-meta">
                <div>最新快照：{{ latestSnapshot.created_at || '未知时间' }}</div>
                <div>来源：{{ snapshotTypeLabel(latestSnapshot) }} · {{ latestSnapshot.source_name || '未命名快照' }}</div>
                <div>大小：{{ latestSnapshot.size_text || '未知' }}</div>
              </div>

              <div v-if="snapshotTaskStatus.status !== 'idle'" class="snapshot-task-box">
                <div class="snapshot-task-head">
                  <el-tag :type="snapshotTaskStatusTagType" size="small">{{ snapshotTaskStatusLabel }}</el-tag>
                  <span class="snapshot-task-text">{{ snapshotTaskStatus.message || '正在处理快照任务' }}</span>
                </div>
                <div v-if="isSnapshotTaskRunning" class="upload-progress-wrap">
                  <el-progress :percentage="snapshotTaskStatus.progress || 0" :stroke-width="8" />
                </div>
                <div v-if="snapshotTaskStatus.error" class="feature-hint warning-text">{{ snapshotTaskStatus.error }}</div>
              </div>

              <div v-if="snapshots.length" class="snapshot-list">
                <div
                  v-for="item in snapshots"
                  :key="item.id"
                  class="snapshot-row"
                  :class="[
                    { selected: selectedSnapshotId === item.id },
                    `snapshot-row-${snapshotTypeClassName(item)}`
                  ]"
                  @click="selectedSnapshotId = item.id"
                >
                  <span class="snapshot-radio" :class="{ checked: selectedSnapshotId === item.id }"></span>
                  <span class="snapshot-row-main">
                    <span class="snapshot-row-title">
                      <el-tag size="small" :type="snapshotTypeTagType(item)" effect="plain">{{ snapshotTypeLabel(item) }}</el-tag>
                      <span class="snapshot-title-text">{{ item.source_name || '未命名快照' }}</span>
                    </span>
                    <span class="snapshot-row-subtitle">{{ item.created_at || '未知时间' }} · {{ item.size_text || '未知大小' }}</span>
                  </span>
                  <span class="snapshot-row-tools">
                    <el-button link type="danger" :disabled="isSnapshotTaskRunning || importing" @click.stop="handleDeleteSnapshot(item)">删除</el-button>
                  </span>
                </div>
              </div>
              <div v-else class="feature-hint">
                还没有可用快照。你可以先手动创建一份，后续每次导入前系统也会自动新增一份导入前快照。
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
            <el-icon class="icon"><Setting /></el-icon>
            <h3>水电费账户预设</h3>
          </div>
          <div class="card-content">
            <div class="description">
              在这里预设水费和电费的常用账户。保存后，AI 识图会优先按账户名称自动匹配。
            </div>

            <div class="utility-account-grid">
              <div class="utility-account-group">
                <div class="feature-editor">
                  <div class="feature-group-title">电费账户</div>
                  <div class="feature-input-wrap">
                    <el-input
                      v-model="newUtilityAccount.electricity"
                      placeholder="输入电费账户，例如：191-A"
                      @keyup.enter="addUtilityAccount('electricity')"
                    />
                    <el-button type="primary" :loading="savingUtilityAccounts" @click="addUtilityAccount('electricity')">添加账户</el-button>
                  </div>
                </div>
                <div class="utility-account-list">
                  <div
                    v-for="account in utilityAccountOptions.electricity"
                    :key="`electricity-${account}`"
                    class="utility-account-card"
                  >
                    <div class="utility-account-card__header">
                      <strong>{{ account }}</strong>
                      <el-button link type="danger" :disabled="savingUtilityAccounts" @click="removeUtilityAccount('electricity', account)">删除账户</el-button>
                    </div>
                  </div>
                </div>
              </div>

              <div class="utility-account-group">
                <div class="feature-editor">
                  <div class="feature-group-title">水费账户</div>
                  <div class="feature-input-wrap">
                    <el-input
                      v-model="newUtilityAccount.water"
                      placeholder="输入水费账户，例如：361-A"
                      @keyup.enter="addUtilityAccount('water')"
                    />
                    <el-button type="primary" :loading="savingUtilityAccounts" @click="addUtilityAccount('water')">添加账户</el-button>
                  </div>
                </div>
                <div class="utility-account-list">
                  <div
                    v-for="account in utilityAccountOptions.water"
                    :key="`water-${account}`"
                    class="utility-account-card"
                  >
                    <div class="utility-account-card__header">
                      <strong>{{ account }}</strong>
                      <el-button link type="danger" :disabled="savingUtilityAccounts" @click="removeUtilityAccount('water', account)">删除账户</el-button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div class="feature-hint">新增或删除后会自动保存，不需要再额外点保存按钮。</div>
          </div>
        </div>
      </div>

      <div class="system-grid-item">
        <div class="card-box h-100 system-card">
          <div class="card-header">
            <el-icon class="icon"><Cpu /></el-icon>
            <h3>AI 模式配置</h3>
          </div>
          <div class="card-content">
            <div class="description">
              为采购管理、维修记录、租户管理、自助入住和水电费的 “AI 输入” 选择使用本地 Ollama，或切换到 OpenAI 兼容 API。图片会直接交给当前本地模型识别；身份证专用识别继续使用阿里云 OCR。
            </div>
            <div class="ai-summary-row">
              <el-tag type="info" effect="plain">当前模式：{{ aiProviderLabel }}</el-tag>
              <el-tag type="success" effect="plain">当前模型：{{ aiCurrentModelLabel }}</el-tag>
              <el-tag v-if="hasPendingAiChanges" type="warning" effect="plain">有未保存改动</el-tag>
            </div>
            <div v-if="aiSettings.updated_at" class="feature-hint ai-updated-at">
              最近保存：{{ aiSettings.updated_at }}
            </div>
            <div v-if="aiTestResult" class="ai-test-result" :class="{ 'ai-test-result--ok': aiTestResult.ok, 'ai-test-result--error': !aiTestResult.ok }">
              <div class="ai-test-result__head">
                <el-tag :type="aiTestResult.ok ? 'success' : 'danger'" effect="dark">
                  {{ aiTestResult.ok ? '连接正常' : '连接失败' }}
                </el-tag>
                <span class="ai-test-result__time">测试时间：{{ aiTestResult.tested_at || '-' }}</span>
              </div>
              <div class="ai-test-result__message">{{ aiTestResult.message }}</div>
              <div v-if="aiTestResult.preview" class="ai-test-result__preview">返回预览：{{ aiTestResult.preview }}</div>
              <div v-if="aiTestResult.provider === 'ollama' && Array.isArray(aiTestResult.available_models)" class="ai-test-result__preview">
                本地模型：{{ aiTestResult.available_models.length ? aiTestResult.available_models.join('、') : '当前未发现模型' }}
              </div>
            </div>

            <el-form label-position="top" class="ocr-settings-form">
              <el-form-item label="AI 功能">
                <el-switch
                  v-model="aiSettings.enabled"
                  :disabled="isAiSwitching"
                  active-text="启用"
                  inactive-text="停用"
                  @change="toggleAiEnabled"
                />
              </el-form-item>
              <el-form-item label="接入方式">
                <el-radio-group v-model="aiSettings.provider" :disabled="isAiSwitching">
                  <el-radio-button label="ollama">本地 Ollama</el-radio-button>
                  <el-radio-button label="api">OpenAI 兼容 API</el-radio-button>
                </el-radio-group>
              </el-form-item>

              <template v-if="aiSettings.provider === 'ollama'">
                <el-form-item label="Ollama 服务地址">
                  <el-input
                    v-model="aiSettings.ollama_base_url"
                    placeholder="http://127.0.0.1:11434"
                    :disabled="isAiSwitching"
                    clearable
                  />
                </el-form-item>
                <el-form-item label="本地模型">
                  <el-select
                    v-model="aiSettings.procurement_model"
                    style="width: 100%"
                    :disabled="isAiSwitching || !aiSettings.enabled"
                  >
                    <el-option
                      v-for="model in aiSettings.available_procurement_models"
                      :key="model"
                      :label="model"
                      :value="model"
                    />
                  </el-select>
                </el-form-item>
                <div class="feature-hint">
                  图片识别请优先选择支持视觉的本地模型，例如 `qwen2.5vl:3b`。Ollama 和后端同机时使用 http://127.0.0.1:11434；远程部署时填写 http://另一台机器IP:11434。
                </div>
                <div v-if="!isLocalOllamaEndpoint" class="feature-hint warning-text">
                  当前是远程 Ollama 地址，本系统无法关闭远程机器上的模型，只能切换当前调用的模型和地址。
                </div>
              </template>

              <template v-else>
                <el-form-item label="API Base URL">
                  <el-input
                    v-model="aiSettings.base_url"
                    placeholder="https://api.deepseek.com"
                    :disabled="isAiSwitching"
                    clearable
                  />
                </el-form-item>
                <el-form-item label="API 模型">
                  <div class="ai-model-picker">
                    <el-select
                      v-model="aiSettings.model"
                      filterable
                      allow-create
                      default-first-option
                      clearable
                      style="width: 100%"
                      placeholder="先读取模型列表，或直接手动输入模型名"
                      :disabled="isAiSwitching || !aiSettings.enabled"
                      @change="handleApiModelChange"
                    >
                      <el-option
                        v-for="item in availableApiModels"
                        :key="item.id"
                        :label="item.id"
                        :value="item.id"
                      >
                        <div class="ai-model-option">
                          <span>{{ item.id }}</span>
                          <span class="ai-model-option__owner">{{ item.owned_by || 'api' }}</span>
                        </div>
                      </el-option>
                    </el-select>
                    <el-button :loading="loadingApiModels" :disabled="isAiSwitching" @click="fetchApiModels">
                      读取模型列表
                    </el-button>
                  </div>
                </el-form-item>
                <el-form-item label="API Key">
                  <el-input
                    v-model="aiSettings.api_key"
                    type="password"
                    show-password
                    placeholder="请输入 API Key"
                    :disabled="isAiSwitching || !aiSettings.enabled"
                    clearable
                  />
                </el-form-item>
                <div class="feature-hint">
                  这里适合填写 DeepSeek 这类 OpenAI 兼容 API。默认会按 `Base URL + /chat/completions` 发起请求。
                </div>
                <div v-if="apiModelsMeta.message" class="feature-hint">
                  {{ apiModelsMeta.message }}
                </div>
              </template>
              <div class="ocr-status-row">
                <el-tag :type="aiSwitchStatusTagType">
                  {{ aiSwitchStatusLabel }}
                </el-tag>
                <span class="ocr-status-text">
                  {{ aiStatusText }}
                </span>
              </div>
              <div v-if="aiSwitchStatus.status === 'running'" class="upload-progress-wrap">
                <el-progress :percentage="aiSwitchProgress" :indeterminate="true" :stroke-width="8" />
              </div>
              <div v-if="aiSwitchStatus.error" class="feature-hint warning-text">{{ aiSwitchStatus.error }}</div>

              <div class="action-area ai-action-area">
                <el-button type="primary" :loading="savingAiSettings" @click="saveAiSettings">
                  保存配置
                </el-button>
                <el-button :loading="testingAiSettings" :disabled="savingAiSettings || isAiSwitching" @click="testAiSettings">
                  测试连接
                </el-button>
              </div>
              <div class="feature-hint">
                保存配置会长期保留当前接入方式和参数；切换模型时现在会自动保存，选择本地模型后也会直接发起切换。
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
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
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
const snapshots = ref([])
const selectedSnapshotId = ref('')
const snapshotTaskStatus = ref({
  id: '',
  action: '',
  status: 'idle',
  phase: '',
  message: '未执行快照任务',
  progress: 0,
  snapshot_id: '',
  snapshot_name: '',
  started_at: '',
  finished_at: '',
  error: '',
})
const roomFeatureOptions = ref([])
const newRoomFeature = ref('')
const savingRoomFeatures = ref(false)
const utilityAccountOptions = reactive({
  electricity: [],
  water: [],
})
const newUtilityAccount = reactive({
  electricity: '',
  water: '',
})
const savingUtilityAccounts = ref(false)
const savingOcrSettings = ref(false)
const savingAiSettings = ref(false)
const testingAiSettings = ref(false)
const loadingApiModels = ref(false)
let aiSwitchPollTimer = null
let snapshotTaskPollTimer = null
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
  provider: 'ollama',
  procurement_model: 'qwen2.5vl:3b',
  ollama_base_url: 'http://127.0.0.1:11434',
  base_url: '',
  chat_completions_url: '',
  responses_url: '',
  model: '',
  api_key: '',
  available_procurement_models: ['qwen2.5vl:3b', 'qwen3.5:4b', 'qwen3.5:2b', 'qwen3.5:0.8b'],
  updated_at: '',
})
const lastSavedAiSettings = ref(null)
const aiTestResult = ref(null)
const availableApiModels = ref([])
const apiModelsMeta = reactive({
  message: '',
  tested_at: '',
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
const isApiProvider = computed(() => aiSettings.value.provider === 'api')
const getComparableAiSettings = (value = {}) => JSON.stringify({
  enabled: value?.enabled !== false,
  provider: value?.provider || 'ollama',
  procurement_model: value?.procurement_model || 'qwen2.5vl:3b',
  ollama_base_url: value?.ollama_base_url || 'http://127.0.0.1:11434',
  base_url: value?.base_url || '',
  chat_completions_url: value?.chat_completions_url || '',
  responses_url: value?.responses_url || '',
  model: value?.model || '',
  api_key: value?.api_key || '',
})
const hasPendingAiChanges = computed(() => {
  if (!lastSavedAiSettings.value) return false
  return getComparableAiSettings(aiSettings.value) !== getComparableAiSettings(lastSavedAiSettings.value)
})
const aiProviderLabel = computed(() => (isApiProvider.value ? 'OpenAI 兼容 API' : '本地 Ollama'))
const aiCurrentModelLabel = computed(() => {
  if (isApiProvider.value) return aiSettings.value.model || '未设置'
  return aiSettings.value.procurement_model || '未设置'
})
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
  if (status === 'completed' && aiSwitchStatus.value.phase === 'settings_saved') return '已保存'
  if (status === 'completed' && aiSwitchStatus.value.phase === 'api_saved') return '已保存'
  if (status === 'completed' && aiSwitchStatus.value.phase === 'enabled') return '已启用'
  if (status === 'completed' && aiSwitchStatus.value.phase === 'disabled') return '已停用'
  if (status === 'completed') return '已完成'
  if (status === 'failed') return '失败'
  return '空闲'
})
const aiStatusText = computed(() => {
  const message = String(aiSwitchStatus.value.message || '').trim()
  if (message && message !== '未执行切换') return message
  if (!aiSettings.value.enabled) return 'AI 功能已停用'
  return isApiProvider.value
    ? `当前使用 API 模型 ${aiCurrentModelLabel.value}`
    : `当前使用 Ollama 模型 ${aiCurrentModelLabel.value}`
})
const aiSwitchStatusTagType = computed(() => {
  const status = aiSwitchStatus.value.status
  if (status === 'running') return 'warning'
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'danger'
  return 'info'
})
const latestSnapshot = computed(() => snapshots.value[0] || null)
const selectedSnapshot = computed(() => snapshots.value.find(item => item.id === selectedSnapshotId.value) || null)
const isSnapshotTaskRunning = computed(() => snapshotTaskStatus.value.status === 'running')
const isCreatingSnapshot = computed(() => isSnapshotTaskRunning.value && snapshotTaskStatus.value.action === 'create')
const isRestoringSnapshot = computed(() => isSnapshotTaskRunning.value && snapshotTaskStatus.value.action === 'restore')
const snapshotTaskStatusLabel = computed(() => {
  const status = snapshotTaskStatus.value.status
  if (status === 'running') return snapshotTaskStatus.value.action === 'restore' ? '回滚中' : '创建中'
  if (status === 'completed') return '已完成'
  if (status === 'failed') return '失败'
  return '空闲'
})
const snapshotTaskStatusTagType = computed(() => {
  const status = snapshotTaskStatus.value.status
  if (status === 'running') return 'warning'
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'danger'
  return 'info'
})
const snapshotTypeLabel = (snapshot) => {
  const type = String(snapshot?.snapshot_type || '').trim()
  if (type === 'import_auto') return '导入前自动快照'
  if (type === 'legacy') return '旧版迁移快照'
  return '手动快照'
}
const snapshotTypeTagType = (snapshot) => {
  const type = String(snapshot?.snapshot_type || '').trim()
  if (type === 'import_auto') return 'warning'
  if (type === 'legacy') return 'info'
  return 'success'
}
const snapshotTypeClassName = (snapshot) => {
  const type = String(snapshot?.snapshot_type || '').trim()
  if (type === 'import_auto') return 'auto'
  if (type === 'legacy') return 'legacy'
  return 'manual'
}
const getAiActionSuccessMessage = () => {
  const phase = aiSwitchStatus.value.phase
  if (phase === 'settings_saved') return 'AI 配置已保存'
  if (phase === 'api_saved') return 'API 配置已保存'
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
  const nextValue = {
    enabled: data?.enabled !== false,
    provider: data?.provider || 'ollama',
    procurement_model: data?.procurement_model || 'qwen2.5vl:3b',
    ollama_base_url: data?.ollama_base_url || 'http://127.0.0.1:11434',
    base_url: data?.base_url || '',
    chat_completions_url: data?.chat_completions_url || '',
    responses_url: data?.responses_url || '',
    model: data?.model || '',
    api_key: data?.api_key || '',
    available_procurement_models: data?.available_procurement_models || ['qwen2.5vl:3b', 'qwen3.5:4b', 'qwen3.5:2b', 'qwen3.5:0.8b'],
    updated_at: data?.updated_at || '',
  }
  aiSettings.value = nextValue
  lastSavedAiSettings.value = { ...nextValue }
  aiTestResult.value = null
  if (nextValue.provider !== 'api') {
    availableApiModels.value = []
    apiModelsMeta.message = ''
    apiModelsMeta.tested_at = ''
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

const applySnapshotTaskStatus = (data = {}) => {
  snapshotTaskStatus.value = {
    id: data?.id || '',
    action: data?.action || '',
    status: data?.status || 'idle',
    phase: data?.phase || '',
    message: data?.message || '未执行快照任务',
    progress: Number(data?.progress || 0),
    snapshot_id: data?.snapshot_id || '',
    snapshot_name: data?.snapshot_name || '',
    started_at: data?.started_at || '',
    finished_at: data?.finished_at || '',
    error: data?.error || '',
  }
}

const stopSnapshotTaskPolling = () => {
  if (snapshotTaskPollTimer) {
    clearInterval(snapshotTaskPollTimer)
    snapshotTaskPollTimer = null
  }
}

const fetchSnapshots = async ({ silent = false } = {}) => {
  try {
    const response = await systemApi.listSnapshots()
    snapshots.value = Array.isArray(response?.data?.snapshots) ? response.data.snapshots : []
    if (!selectedSnapshotId.value || !snapshots.value.some(item => item.id === selectedSnapshotId.value)) {
      selectedSnapshotId.value = snapshots.value[0]?.id || ''
    }
  } catch (error) {
    if (!silent) {
      ElMessage.error(error?.response?.data?.error || '加载系统快照列表失败')
    }
  }
}

const pollSnapshotTaskStatus = async () => {
  try {
    const response = await systemApi.getSnapshotTaskStatus()
    applySnapshotTaskStatus(response?.data || {})
    if (snapshotTaskStatus.value.status === 'completed') {
      stopSnapshotTaskPolling()
      await fetchSnapshots({ silent: true })
      if (snapshotTaskStatus.value.snapshot_id) {
        selectedSnapshotId.value = snapshotTaskStatus.value.snapshot_id
      }
      ElMessage.success(snapshotTaskStatus.value.message || '快照任务已完成')
      if (snapshotTaskStatus.value.action === 'restore') {
        setTimeout(() => {
          window.location.reload()
        }, 1500)
      }
    } else if (snapshotTaskStatus.value.status === 'failed') {
      stopSnapshotTaskPolling()
      ElMessage.error(snapshotTaskStatus.value.error || snapshotTaskStatus.value.message || '快照任务失败')
    }
  } catch (error) {
    stopSnapshotTaskPolling()
    ElMessage.error(error?.response?.data?.error || '获取快照任务状态失败')
  }
}

const startSnapshotTaskPolling = () => {
  stopSnapshotTaskPolling()
  snapshotTaskPollTimer = setInterval(pollSnapshotTaskStatus, 1200)
}

const fetchRoomFeatureOptions = async () => {
  try {
    const response = await systemApi.getRoomFeatureOptions()
    roomFeatureOptions.value = response?.data?.options || []
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '加载房间设施配置失败')
  }
}

const applyUtilityAccountOptions = (data = {}) => {
  utilityAccountOptions.electricity = normalizeUtilityAccountEntries(data?.electricity || [])
  utilityAccountOptions.water = normalizeUtilityAccountEntries(data?.water || [])
}

const normalizeUtilityAccountEntries = (values = []) => {
  if (!Array.isArray(values)) return []
  const result = []
  values.forEach((item) => {
    const account = String(item && typeof item === 'object' && !Array.isArray(item) ? (item.account || item.subject || '') : item || '').trim()
    if (account && !result.includes(account)) {
      result.push(account)
    }
  })
  return result
}

const fetchUtilityAccountOptions = async () => {
  try {
    const response = await systemApi.getUtilityAccountOptions()
    applyUtilityAccountOptions(response?.data || {})
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '加载水电费账户预设失败')
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
    } else {
      stopAiSwitchPolling()
      savingAiSettings.value = false
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
      provider: aiSettings.value.provider,
      procurement_model: aiSettings.value.procurement_model,
      ollama_base_url: aiSettings.value.ollama_base_url,
      base_url: aiSettings.value.base_url,
      chat_completions_url: aiSettings.value.chat_completions_url,
      responses_url: aiSettings.value.responses_url,
      model: aiSettings.value.model,
      api_key: aiSettings.value.api_key,
    })
    applyAiSettingsResponse(response?.data || {})
    ElMessage.success(successMessage)
    if (aiSwitchStatus.value.status === 'running') {
      startAiSwitchPolling()
    } else {
      stopAiSwitchPolling()
      savingAiSettings.value = false
    }
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || 'AI 操作失败')
    await fetchAiSettings()
    savingAiSettings.value = false
  }
}

const toggleAiEnabled = async (value) => {
  const successMessage = isApiProvider.value
    ? (value ? 'AI 功能已启用' : 'AI 功能已停用')
    : (value ? 'AI 功能启用已开始' : 'AI 功能停用已开始')
  await runAiAction(value ? 'enable' : 'disable', successMessage)
}

const saveAiSettings = async () => {
  await runAiAction('save_config', 'AI 配置已保存')
}

const fetchApiModels = async () => {
  loadingApiModels.value = true
  try {
    const response = await systemApi.listAiModels({
      provider: aiSettings.value.provider,
      base_url: aiSettings.value.base_url,
      chat_completions_url: aiSettings.value.chat_completions_url,
      model: aiSettings.value.model,
      api_key: aiSettings.value.api_key,
    })
    const models = Array.isArray(response?.data?.models) ? response.data.models : []
    availableApiModels.value = models
    apiModelsMeta.message = response?.data?.message || ''
    apiModelsMeta.tested_at = response?.data?.tested_at || ''
    if (!aiSettings.value.model && models[0]?.id) {
      aiSettings.value.model = models[0].id
    }
    ElMessage.success(apiModelsMeta.message || '模型列表获取成功')
  } catch (error) {
    availableApiModels.value = []
    apiModelsMeta.message = error?.response?.data?.message || error?.response?.data?.error || '获取模型列表失败'
    apiModelsMeta.tested_at = ''
    ElMessage.error(apiModelsMeta.message)
  } finally {
    loadingApiModels.value = false
  }
}

const handleApiModelChange = async (value) => {
  if (!value) return
  const successMessage = aiSettings.value.enabled ? 'API 模型已切换' : 'API 模型已保存'
  await runAiAction('save_config', successMessage)
}

const testAiSettings = async () => {
  testingAiSettings.value = true
  try {
    const response = await systemApi.testAiSettings({
      provider: aiSettings.value.provider,
      procurement_model: aiSettings.value.procurement_model,
      ollama_base_url: aiSettings.value.ollama_base_url,
      base_url: aiSettings.value.base_url,
      chat_completions_url: aiSettings.value.chat_completions_url,
      responses_url: aiSettings.value.responses_url,
      model: aiSettings.value.model,
      api_key: aiSettings.value.api_key,
    })
    aiTestResult.value = response?.data || null
    if (aiTestResult.value?.ok) {
      ElMessage.success(aiTestResult.value.message || '连接测试成功')
    } else {
      ElMessage.error(aiTestResult.value?.message || '连接测试失败')
    }
  } catch (error) {
    aiTestResult.value = {
      ok: false,
      provider: aiSettings.value.provider,
      tested_at: new Date().toLocaleString(),
      message: error?.response?.data?.error || '连接测试失败',
    }
    ElMessage.error(aiTestResult.value.message)
  } finally {
    testingAiSettings.value = false
  }
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

const addUtilityAccount = (type) => {
  if (!['electricity', 'water'].includes(type)) return
  const text = String(newUtilityAccount[type] || '').trim()
  if (!text) return
  if (!utilityAccountOptions[type].includes(text)) {
    utilityAccountOptions[type] = [...utilityAccountOptions[type], text]
  }
  newUtilityAccount[type] = ''
  saveUtilityAccountOptions()
}

const removeUtilityAccount = (type, item) => {
  if (!['electricity', 'water'].includes(type)) return
  utilityAccountOptions[type] = utilityAccountOptions[type].filter(v => v !== item)
  saveUtilityAccountOptions()
}

const saveUtilityAccountOptions = async () => {
  savingUtilityAccounts.value = true
  try {
    const response = await systemApi.updateUtilityAccountOptions({
      electricity: utilityAccountOptions.electricity,
      water: utilityAccountOptions.water,
    })
    applyUtilityAccountOptions(response?.data || {})
    ElMessage.success('水电费账户预设已保存')
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '保存水电费账户预设失败')
  } finally {
    savingUtilityAccounts.value = false
  }
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
      await systemApi.importData({
        file_url: fileUrl,
        source_name: selectedFile.value?.name || '',
      })
      importUploadProgress.value = 100
      await fetchSnapshots({ silent: true })
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

const handleCreateSnapshot = async () => {
  try {
    const response = await systemApi.createSnapshot()
    applySnapshotTaskStatus(response?.data || {})
    startSnapshotTaskPolling()
    ElMessage.success('系统快照创建已开始')
  } catch (error) {
    console.error(error)
    ElMessage.error(error?.response?.data?.error || '创建快照失败')
  }
}

const handleRollbackImport = () => {
  if (!selectedSnapshot.value) {
    ElMessage.warning('当前没有可回滚的系统快照')
    return
  }

  ElMessageBox.confirm(
    `此操作将把系统恢复到所选快照“${selectedSnapshot.value.source_name || selectedSnapshot.value.created_at || selectedSnapshot.value.id}”对应的状态，当前数据会被覆盖。是否确认回滚？`,
    '确认回滚快照',
    {
      confirmButtonText: '确认回滚',
      cancelButtonText: '取消',
      type: 'warning',
      confirmButtonClass: 'el-button--danger'
    }
  ).then(async () => {
    try {
      const response = await systemApi.restoreSnapshot(selectedSnapshot.value.id)
      applySnapshotTaskStatus(response?.data || {})
      startSnapshotTaskPolling()
      ElMessage.success('快照回滚已开始')
    } catch (error) {
      console.error(error)
      ElMessage.error('回滚失败: ' + (error.response?.data?.error || error.message))
    }
  }).catch(() => {})
}

const handleDeleteSnapshot = async (snapshot) => {
  if (!snapshot?.id) return
  ElMessageBox.confirm(
    `确认删除快照“${snapshot.source_name || snapshot.created_at || snapshot.id}”？删除后无法恢复。`,
    '删除快照',
    {
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
      type: 'warning',
      confirmButtonClass: 'el-button--danger'
    }
  ).then(async () => {
    try {
      await systemApi.deleteSnapshot(snapshot.id)
      await fetchSnapshots({ silent: true })
      ElMessage.success('快照已删除')
    } catch (error) {
      console.error(error)
      ElMessage.error(error?.response?.data?.error || '删除快照失败')
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
  fetchSnapshots({ silent: true })
  systemApi.getSnapshotTaskStatus().then((response) => {
    applySnapshotTaskStatus(response?.data || {})
    if (snapshotTaskStatus.value.status === 'running') {
      startSnapshotTaskPolling()
    }
  }).catch(() => {})
  fetchRoomFeatureOptions()
  fetchUtilityAccountOptions()
  fetchOcrSettings()
  fetchAiSettings()
})

onBeforeUnmount(() => {
  stopAiSwitchPolling()
  stopSnapshotTaskPolling()
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

.ai-summary-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: -4px 0 12px;
}

.ai-updated-at {
  margin-top: -6px;
  margin-bottom: 14px;
}

.ai-test-result {
  margin: 0 0 14px;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid var(--surface-border);
  background: var(--surface-muted);
}

.ai-test-result--ok {
  border-color: rgba(34, 197, 94, 0.28);
  background: rgba(34, 197, 94, 0.08);
}

.ai-test-result--error {
  border-color: rgba(239, 68, 68, 0.24);
  background: rgba(239, 68, 68, 0.08);
}

.ai-test-result__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.ai-test-result__time {
  font-size: 12px;
  color: var(--text-secondary);
}

.ai-test-result__message {
  margin-top: 10px;
  font-size: 13px;
  color: var(--text-main);
  line-height: 1.6;
}

.ai-test-result__preview {
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
  word-break: break-word;
}

.ai-model-picker {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
}

.ai-model-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.ai-model-option__owner {
  color: var(--text-secondary);
  font-size: 12px;
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

.ai-action-area {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.upload-area {
  margin-top: 0;
  width: 100%;
  min-width: 0;
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

.rollback-box {
  margin-top: 18px;
  padding: 14px 16px;
  border: 1px dashed var(--surface-border, var(--el-border-color));
  border-radius: 12px;
  background: var(--surface-muted, var(--el-fill-color-lighter));
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow: hidden;
}

.rollback-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--text-main);
  font-weight: 700;
}

.rollback-subtitle {
  margin-top: 4px;
  font-size: 12px;
  font-weight: 400;
  color: var(--text-secondary);
  line-height: 1.5;
}

.rollback-meta {
  margin-top: 10px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.rollback-action {
  margin-top: 14px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.snapshot-task-box {
  margin-top: 14px;
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--card-bg, #fff);
  border: 1px solid var(--surface-border, var(--el-border-color-light));
}

.snapshot-task-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.snapshot-task-text {
  font-size: 13px;
  color: var(--text-secondary);
}

.snapshot-list {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 320px;
  overflow: auto;
  min-width: 0;
}

.snapshot-row {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid var(--surface-border, var(--el-border-color-light));
  background: var(--card-bg, #fff);
  color: inherit;
  cursor: pointer;
  text-align: left;
  box-sizing: border-box;
  min-width: 0;
  overflow: hidden;
}

.snapshot-row.selected {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.15);
}

.snapshot-row-auto {
  background: rgba(245, 158, 11, 0.08);
  border-color: rgba(245, 158, 11, 0.28);
}

.snapshot-row-manual {
  background: rgba(34, 197, 94, 0.06);
}

.snapshot-row-legacy {
  background: rgba(148, 163, 184, 0.08);
}

.snapshot-radio {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid var(--el-border-color);
  flex: 0 0 auto;
}

.snapshot-radio.checked {
  border-color: var(--el-color-primary);
  background: radial-gradient(circle at center, var(--el-color-primary) 0 45%, transparent 46%);
}

.snapshot-row-main {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
}

.snapshot-row-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-main);
  font-size: 14px;
  font-weight: 600;
  min-width: 0;
}

.snapshot-title-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.snapshot-row-subtitle {
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.snapshot-row-tools {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
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

.system-top-grid .import-card .card-content {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 16px;
  min-width: 0;
}

.system-top-grid .description {
  margin-bottom: 0;
}

.system-top-grid .action-area,
.system-top-grid .upload-area {
  width: min(420px, 100%);
}

.system-top-grid .import-card .upload-area,
.system-top-grid .import-card .action-area,
.system-top-grid .import-card .rollback-box {
  width: 100%;
  max-width: none;
}

.system-top-grid .import-card .card-content > * {
  min-width: 0;
}

@media (max-width: 768px) {
  .system-top-grid .card-content {
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

.utility-account-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  margin-top: 12px;
}

.utility-account-group {
  padding: 14px;
  border: 1px solid var(--surface-border);
  border-radius: 14px;
  background: var(--surface-muted);
}

.utility-account-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 14px;
}

.utility-account-card {
  padding: 12px;
  border: 1px solid var(--surface-border);
  border-radius: 12px;
  background: var(--card-bg, #fff);
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.04);
}

.utility-account-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.utility-account-alias-row {
  margin-top: 10px;
}

.utility-account-empty-text {
  font-size: 12px;
  color: var(--text-secondary);
}

.feature-tags--compact {
  margin-top: 10px;
  padding-top: 10px;
}

.feature-group-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-main);
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
  .utility-account-grid {
    grid-template-columns: 1fr;
  }

  .utility-account-card__header {
    align-items: flex-start;
    flex-direction: column;
  }

  .danger-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
}
</style>
