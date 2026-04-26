<template>
  <div class="ai-settings-page">
    <section class="settings-hero">
      <div>
        <h2 class="settings-title">AI 设置</h2>
        <p class="settings-subtitle">统一管理 AI 厂商、API、模型和语音转写配置。保存后 AI 助手会直接读取这里的设置。</p>
      </div>
      <div class="settings-hero-actions">
        <el-button type="primary" :loading="saving" @click="saveSettings">保存设置</el-button>
        <el-button :loading="testingChat" @click="testChatConnection">测试对话</el-button>
        <el-button :loading="testingTranscription" @click="testTranscriptionConfig">检查转写</el-button>
      </div>
    </section>

    <el-form
      ref="settingsFormRef"
      :model="settings"
      :rules="rules"
      label-position="top"
      class="settings-form"
    >
      <div class="settings-grid">
        <el-card shadow="never" class="settings-card">
          <template #header>
            <div class="card-header">主对话配置</div>
          </template>

          <el-form-item label="AI 厂商" prop="provider">
            <el-select v-model="settings.provider" placeholder="请选择厂商">
              <el-option label="OpenAI" value="openai" />
              <el-option label="DeepSeek" value="deepseek" />
              <el-option label="千问 / 百炼" value="qwen" />
              <el-option label="豆包 / 火山方舟" value="doubao" />
              <el-option label="自定义兼容接口" value="custom" />
            </el-select>
          </el-form-item>

          <el-form-item label="模型" prop="model">
            <el-input v-model="settings.model" placeholder="例如：gpt-4o-mini / deepseek-chat / qwen-plus" />
          </el-form-item>

          <el-form-item label="API Key" prop="api_key">
            <el-input v-model="settings.api_key" type="password" show-password placeholder="请输入 AI API Key" />
          </el-form-item>

          <el-form-item label="Base URL">
            <el-input v-model="settings.base_url" placeholder="留空则使用厂商默认兼容地址" />
          </el-form-item>

          <el-form-item label="Chat Completions URL">
            <el-input v-model="settings.chat_completions_url" placeholder="留空则自动拼接 /chat/completions" />
          </el-form-item>

          <div class="setting-hint">
            DeepSeek 和千问都按 OpenAI 兼容接口调用；如果你有代理或私有网关，也可以直接填自定义 URL。
          </div>
        </el-card>

        <el-card shadow="never" class="settings-card">
          <template #header>
            <div class="card-header">语音转写配置</div>
          </template>

          <el-alert
            type="info"
            :closable="false"
            show-icon
            class="transcription-alert"
            title="如果你看到“当前 AI 提供商未配置语音转写能力”，就在这里填写。"
            description="做法是：先把“配置模式”切到“单独配置”，然后填写转写厂商、转写模型、转写 API Key 和转写 URL。填完后点“检查转写”即可。"
          />

          <el-form-item label="配置模式" prop="transcription_mode">
            <el-radio-group v-model="settings.transcription_mode">
              <el-radio label="inherit">跟随主配置</el-radio>
              <el-radio label="separate">单独配置</el-radio>
            </el-radio-group>
          </el-form-item>

          <template v-if="settings.transcription_mode === 'separate'">
            <el-form-item label="转写厂商" prop="transcription_provider">
              <el-select v-model="settings.transcription_provider" placeholder="请选择转写厂商">
                <el-option label="OpenAI" value="openai" />
                <el-option label="DeepSeek" value="deepseek" />
                <el-option label="千问 / 百炼" value="qwen" />
                <el-option label="豆包 / 火山方舟" value="doubao" />
                <el-option label="自定义兼容接口" value="custom" />
              </el-select>
            </el-form-item>

            <el-form-item label="转写模型" prop="transcription_model">
              <el-input v-model="settings.transcription_model" placeholder="例如：gpt-4o-transcribe" />
            </el-form-item>

            <el-form-item label="转写 API Key" prop="transcription_api_key">
              <el-input v-model="settings.transcription_api_key" type="password" show-password placeholder="请输入转写 API Key" />
            </el-form-item>

            <el-form-item label="转写 URL" prop="transcription_url">
              <el-input v-model="settings.transcription_url" placeholder="例如：https://api.openai.com/v1/audio/transcriptions" />
            </el-form-item>
          </template>

          <div class="setting-hint">
            如果聊天厂商不支持语音转写，建议这里单独配置一套稳定的转写服务。
          </div>
        </el-card>
      </div>

    </el-form>

    <el-card shadow="never" class="settings-card status-card">
      <template #header>
        <div class="card-header">连接状态</div>
      </template>

      <div class="status-block">
        <div class="status-label">对话测试</div>
        <div class="status-value">{{ chatStatus }}</div>
      </div>

      <div class="status-block">
        <div class="status-label">转写检查</div>
        <div class="status-value">{{ transcriptionStatus }}</div>
      </div>

      <div v-if="settings.updated_at" class="status-footnote">最近保存时间：{{ settings.updated_at }}</div>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { aiAssistantApi } from '../api'

const PROVIDER_PRESETS = {
  openai: {
    base_url: 'https://api.openai.com/v1',
    model: 'gpt-4o-mini',
    transcription_url: 'https://api.openai.com/v1/audio/transcriptions',
    transcription_model: 'gpt-4o-transcribe',
  },
  deepseek: {
    base_url: 'https://api.deepseek.com/v1',
    model: 'deepseek-chat',
    transcription_url: '',
    transcription_model: '',
  },
  qwen: {
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    model: 'qwen-plus',
    transcription_url: '',
    transcription_model: '',
  },
  doubao: {
    base_url: 'https://ark.cn-beijing.volces.com/api/v3',
    model: 'doubao-seed-2-0-pro-260215',
    transcription_url: '',
    transcription_model: '',
  },
  custom: {
    base_url: '',
    model: '',
    transcription_url: '',
    transcription_model: '',
  },
}

const settingsFormRef = ref(null)
const loading = ref(false)
const saving = ref(false)
const testingChat = ref(false)
const testingTranscription = ref(false)
const chatStatus = ref('尚未测试')
const transcriptionStatus = ref('尚未测试')

const settings = reactive({
  provider: 'openai',
  base_url: '',
  chat_completions_url: '',
  model: '',
  api_key: '',
  transcription_mode: 'inherit',
  transcription_provider: '',
  transcription_url: '',
  transcription_model: '',
  transcription_api_key: '',
  updated_at: '',
})

const rules = {
  provider: [{ required: true, message: '请选择 AI 厂商', trigger: 'change' }],
  model: [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
  api_key: [{ required: true, message: '请输入 API Key', trigger: 'blur' }],
}

const applyProviderPreset = (provider, scope = 'chat') => {
  const preset = PROVIDER_PRESETS[provider] || PROVIDER_PRESETS.custom
  if (scope === 'chat') {
    if (!settings.base_url) settings.base_url = preset.base_url
    if (!settings.model) settings.model = preset.model
  } else {
    if (!settings.transcription_url) settings.transcription_url = preset.transcription_url
    if (!settings.transcription_model) settings.transcription_model = preset.transcription_model
  }
}

const applySettings = (data = {}) => {
  settings.provider = data.provider || 'openai'
  settings.base_url = data.base_url || ''
  settings.chat_completions_url = data.chat_completions_url || ''
  settings.model = data.model || ''
  settings.api_key = data.api_key || ''
  settings.transcription_mode = data.transcription_mode || 'inherit'
  settings.transcription_provider = data.transcription_provider || ''
  settings.transcription_url = data.transcription_url || ''
  settings.transcription_model = data.transcription_model || ''
  settings.transcription_api_key = data.transcription_api_key || ''
  settings.updated_at = data.updated_at || ''
}

const fetchSettings = async () => {
  loading.value = true
  try {
    const response = await aiAssistantApi.getSettings()
    applySettings(response?.data || {})
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '加载 AI 设置失败')
  } finally {
    loading.value = false
  }
}

const saveSettings = async () => {
  if (!settingsFormRef.value) return
  await settingsFormRef.value.validate(async (valid) => {
    if (!valid) return
    saving.value = true
    try {
      const response = await aiAssistantApi.updateSettings({ ...settings })
      applySettings(response?.data || {})
      ElMessage.success('AI 设置已保存')
    } catch (error) {
      ElMessage.error(error?.response?.data?.error || '保存 AI 设置失败')
    } finally {
      saving.value = false
    }
  })
}

const testChatConnection = async () => {
  testingChat.value = true
  try {
    const response = await aiAssistantApi.testChat()
    const provider = response?.data?.provider || settings.provider
    const model = response?.data?.model || settings.model
    const reply = response?.data?.reply || '连接成功'
    chatStatus.value = `${provider} / ${model}：${reply}`
    ElMessage.success('AI 对话测试成功')
  } catch (error) {
    const message = error?.response?.data?.error || error?.message || 'AI 对话测试失败'
    chatStatus.value = `失败：${message}`
    ElMessage.error(message)
  } finally {
    testingChat.value = false
  }
}

const testTranscriptionConfig = async () => {
  testingTranscription.value = true
  try {
    const response = await aiAssistantApi.testTranscription()
    const provider = response?.data?.provider || settings.transcription_provider || settings.provider
    const model = response?.data?.model || settings.transcription_model
    const message = response?.data?.message || '配置完整'
    transcriptionStatus.value = `${provider} / ${model}：${message}`
    ElMessage.success('语音转写配置检查通过')
  } catch (error) {
    const message = error?.response?.data?.error || error?.message || '语音转写配置检查失败'
    transcriptionStatus.value = `失败：${message}`
    ElMessage.error(message)
  } finally {
    testingTranscription.value = false
  }
}

onMounted(() => {
  fetchSettings()
})

watch(() => settings.provider, (next, prev) => {
  const prevPreset = PROVIDER_PRESETS[prev] || PROVIDER_PRESETS.custom
  const nextPreset = PROVIDER_PRESETS[next] || PROVIDER_PRESETS.custom
  if (!settings.base_url || settings.base_url === prevPreset.base_url) {
    settings.base_url = nextPreset.base_url
  }
  if (!settings.model || settings.model === prevPreset.model) {
    settings.model = nextPreset.model
  }
})

watch(() => settings.transcription_provider, (next, prev) => {
  const prevPreset = PROVIDER_PRESETS[prev] || PROVIDER_PRESETS.custom
  const nextPreset = PROVIDER_PRESETS[next] || PROVIDER_PRESETS.custom
  if (!settings.transcription_url || settings.transcription_url === prevPreset.transcription_url) {
    settings.transcription_url = nextPreset.transcription_url
  }
  if (!settings.transcription_model || settings.transcription_model === prevPreset.transcription_model) {
    settings.transcription_model = nextPreset.transcription_model
  }
})

watch(() => settings.transcription_mode, (mode) => {
  if (mode === 'separate' && !settings.transcription_provider) {
    settings.transcription_provider = settings.provider
    applyProviderPreset(settings.transcription_provider, 'transcription')
  }
})
</script>

<style scoped>
.ai-settings-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.settings-hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 22px 24px;
  border-radius: 18px;
  background: linear-gradient(135deg, #0f172a 0%, #4338ca 52%, #0f766e 100%);
  color: #fff;
}

.settings-title {
  margin: 0;
  font-size: 26px;
}

.settings-subtitle {
  margin: 8px 0 0;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.86);
}

.settings-hero-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.settings-form {
  width: 100%;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
  gap: 18px;
}

.settings-card {
  border-radius: 18px;
}

.card-header {
  font-size: 16px;
  font-weight: 700;
}

.setting-hint {
  font-size: 12px;
  line-height: 1.7;
  color: var(--text-secondary, #64748b);
}

.transcription-alert {
  margin-bottom: 16px;
}

.status-card {
  max-width: 860px;
}

.status-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 0;
  border-bottom: 1px dashed var(--surface-border, #dbe4f0);
}

.status-label {
  font-weight: 700;
  color: var(--text-main, #0f172a);
}

.status-value {
  color: var(--text-secondary, #475569);
  line-height: 1.7;
  word-break: break-word;
}

.status-footnote {
  margin-top: 14px;
  font-size: 12px;
  color: var(--text-secondary, #64748b);
}
</style>
