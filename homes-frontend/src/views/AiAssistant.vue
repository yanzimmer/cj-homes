<template>
  <div class="assistant-page">
    <section class="assistant-hero">
      <div>
        <h2 class="assistant-title">AI 业务录入助手</h2>
        <p class="assistant-subtitle">先选业务，再用打字或语音对话。信息齐全后，我会帮你把草稿送到对应页面继续确认保存。</p>
      </div>
      <el-tag size="large" effect="dark">{{ selectedBusiness.label }}</el-tag>
    </section>

    <section class="assistant-businesses">
      <button
        v-for="item in businessOptions"
        :key="item.type"
        type="button"
        class="business-card"
        :class="{ active: assistantType === item.type }"
        @click="switchBusiness(item.type)"
      >
        <div class="business-card-title">{{ item.label }}</div>
        <div class="business-card-desc">{{ item.description }}</div>
      </button>
    </section>

    <section class="assistant-workspace">
      <div class="assistant-history-card">
        <div class="assistant-card-header">
          <div>
            <div class="assistant-card-title">会话历史</div>
            <div class="assistant-card-note">保存在后端，可随时回来继续。</div>
          </div>
          <el-button @click="startNewSession">新会话</el-button>
        </div>

        <div class="assistant-history-list">
          <button
            v-for="item in sessions"
            :key="item.id"
            type="button"
            class="assistant-history-item"
            :class="{ active: currentSessionId === item.id }"
            @click="loadSession(item.id)"
          >
            <div class="assistant-history-main">
              <div class="assistant-history-title">{{ item.title }}</div>
              <div class="assistant-history-meta">
                <span>{{ businessLabel(item.assistant_type) }}</span>
                <span>{{ item.completed ? '已完成' : '进行中' }}</span>
              </div>
              <div class="assistant-history-preview">{{ item.last_message || '暂无消息' }}</div>
            </div>
            <el-button size="small" type="danger" text @click.stop="deleteSession(item.id)">删除</el-button>
          </button>
        </div>
      </div>

      <div class="assistant-chat-card">
        <div class="assistant-card-header">
          <div>
            <div class="assistant-card-title">{{ selectedBusiness.label }}对话</div>
            <div class="assistant-card-note">
              AI 会自动追问缺失字段，每次只问一个关键问题。
              <span v-if="currentSessionId">当前会话 ID：{{ currentSessionId }}</span>
            </div>
          </div>
          <div class="assistant-card-actions">
            <el-button @click="openSettings">AI 设置</el-button>
            <el-switch v-model="assistantAutoSpeak" inline-prompt active-text="播报" inactive-text="静音" />
            <el-button @click="resetAssistant">重置会话</el-button>
          </div>
        </div>

        <div class="assistant-message-list">
          <div
            v-for="(message, index) in messages"
            :key="`${message.role}-${index}`"
            class="assistant-message"
            :class="message.role === 'user' ? 'user' : 'assistant'"
          >
            <div class="assistant-message-role">{{ message.role === 'user' ? '你' : 'AI' }}</div>
            <div class="assistant-message-content">{{ message.content }}</div>
          </div>
        </div>

        <el-input
          v-model="inputText"
          type="textarea"
          :rows="4"
          resize="none"
          :placeholder="selectedBusiness.placeholder"
          @keydown.enter.exact.prevent="sendMessage()"
        />

        <div class="assistant-upload-row">
          <el-upload
            action="#"
            :auto-upload="false"
            :show-file-list="false"
            accept="image/*"
            multiple
            :limit="4"
            :on-change="handleImageUpload"
          >
            <el-button>上传图片</el-button>
          </el-upload>
          <span class="assistant-upload-tip">支持最多 4 张图片。租户场景可直接上传身份证照片让 AI 提取信息。</span>
        </div>

        <div v-if="uploadedImages.length" class="assistant-image-list">
          <div v-for="item in uploadedImages" :key="item.id" class="assistant-image-card">
            <img :src="item.dataUrl" :alt="item.name" class="assistant-image-thumb" />
            <div class="assistant-image-name">{{ item.name }}</div>
            <el-button size="small" type="danger" plain @click="removeImage(item.id)">删除</el-button>
          </div>
        </div>

        <div class="assistant-toolbar">
          <el-button type="primary" :loading="assistantLoading" @click="sendMessage()">发送</el-button>
          <el-button
            :type="recording ? 'danger' : 'success'"
            :loading="transcribing"
            :disabled="!voiceSupported || assistantLoading"
            @click="toggleRecording"
          >
            {{ recording ? '结束录音' : '语音输入' }}
          </el-button>
          <el-button :disabled="!uploadedImages.length || assistantLoading" @click="sendMessage('请根据我上传的图片提取并整理信息。')">
            识别图片
          </el-button>
          <el-button type="warning" :disabled="!canGenerate" :loading="generating" @click="generateDirectly">直接生成</el-button>
        </div>

        <div class="assistant-status">
          <span v-if="!voiceSupported">当前浏览器不支持录音，仍可继续文字对话。</span>
          <span v-else-if="recording">录音中，结束后会自动转写并发给 AI。</span>
          <span v-else-if="transcribing">正在转写语音，请稍候。</span>
          <span v-else-if="canGenerate">当前信息已经齐全，可以直接生成业务数据。</span>
          <span v-else>你也可以直接说：“A栋301，新租户小杨，男，电话...”</span>
        </div>
      </div>

      <div class="assistant-summary-card">
        <div class="assistant-card-header">
          <div>
            <div class="assistant-card-title">结构化草稿</div>
            <div class="assistant-card-note">这里展示 AI 当前已整理出的字段。</div>
          </div>
          <el-tag :type="canGenerate ? 'success' : 'info'">{{ missingFields.length ? `还缺 ${missingFields.length} 项` : '可直接生成' }}</el-tag>
        </div>

        <div class="summary-list">
          <div v-for="item in selectedBusiness.fields" :key="item.key" class="summary-row">
            <div class="summary-label">{{ item.label }}</div>
            <div class="summary-value">{{ renderSummaryValue(currentForm[item.key]) }}</div>
          </div>
        </div>

        <div v-if="missingFields.length" class="summary-missing">
          <span>当前还缺：</span>
          <el-tag v-for="field in missingFields" :key="field" size="small" type="warning">{{ mapFieldLabel(field) }}</el-tag>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { aiAssistantApi, roomsApi, tenantsApi, movesApi, repairRecordsApi, procurementApi, warehouseApi, contractTemplatesApi } from '../api'
import { mapRouteToAssistantType } from '../utils/aiDrafts'

const LAST_ASSISTANT_TYPE_KEY = 'homes:last-ai-assistant-type'

const router = useRouter()
const route = useRoute()

const businessOptions = [
  {
    type: 'tenant',
    label: '租户录入',
    description: '适合新增租户、补齐身份证号、电话、入住退房日期等。',
    placeholder: '例如：A栋301，小杨，男，身份证330..., 电话138..., 今天入住，明年6月底到期。',
    fields: [
      { key: 'building', label: '楼栋' },
      { key: 'room_no', label: '房间号' },
      { key: 'name', label: '姓名' },
      { key: 'gender', label: '性别' },
      { key: 'nation', label: '民族' },
      { key: 'birth_date', label: '出生日期' },
      { key: 'id_card', label: '身份证号' },
      { key: 'phone', label: '联系电话' },
      { key: 'emergency_contact', label: '紧急联系人' },
      { key: 'emergency_phone', label: '紧急电话' },
      { key: 'check_in_date', label: '入住日期' },
      { key: 'check_out_date', label: '退房日期' },
      { key: 'address', label: '住址' },
      { key: 'notes', label: '备注' },
    ],
  },
  {
    type: 'room',
    label: '房间录入',
    description: '适合新增房间、快速说出楼栋、房号、房型和价格。',
    placeholder: '例如：新增 A栋 401，单间，月租 1200，有独立卫浴。',
    fields: [
      { key: 'building', label: '楼栋' },
      { key: 'room_no', label: '房间号' },
      { key: 'room_type', label: '房间类型' },
      { key: 'price', label: '价格' },
      { key: 'deposit', label: '押金' },
      { key: 'status', label: '状态' },
      { key: 'description', label: '描述' },
    ],
  },
  {
    type: 'repair',
    label: '维修录入',
    description: '适合报修登记，自动追问房间、类型、报修人等信息。',
    placeholder: '例如：A栋301 空调不制冷，张阿姨报修，今天登记。',
    fields: [
      { key: 'building', label: '楼栋' },
      { key: 'room_no', label: '房间号' },
      { key: 'repair_type', label: '维修类型' },
      { key: 'description', label: '问题描述' },
      { key: 'report_by', label: '报修人' },
      { key: 'report_date', label: '报修日期' },
      { key: 'status', label: '状态' },
      { key: 'repair_date', label: '维修日期' },
      { key: 'repair_cost', label: '维修费用' },
      { key: 'repair_person', label: '维修人员' },
      { key: 'remarks', label: '备注' },
    ],
  },
  {
    type: 'procurement',
    label: '采购录入',
    description: '适合快速录入采购项目、数量、单价和总价。',
    placeholder: '例如：今天买了灯泡 20 个，单价 8 元，总共 160 元。',
    fields: [
      { key: 'procurement_date', label: '采购日期' },
      { key: 'item_name', label: '采购项目' },
      { key: 'specification', label: '规格' },
      { key: 'quantity', label: '数量' },
      { key: 'unit_price', label: '单价' },
      { key: 'unit', label: '单位' },
      { key: 'total_amount', label: '总金额' },
      { key: 'remarks', label: '备注' },
    ],
  },
  {
    type: 'warehouse',
    label: '库存物资录入',
    description: '适合新增库存物资，支持名称、数量、位置等字段。',
    placeholder: '例如：新增角阀 12 个，放在 A库 1层，分类水电材料。',
    fields: [
      { key: 'item_name', label: '物资名称' },
      { key: 'category', label: '分类' },
      { key: 'quantity', label: '库存数量' },
      { key: 'unit', label: '单位' },
      { key: 'location', label: '存放位置' },
      { key: 'remarks', label: '备注' },
    ],
  },
  {
    type: 'move',
    label: '搬迁录入',
    description: '适合租户搬迁或整间搬迁登记。',
    placeholder: '例如：把小杨从 A301 搬到 A305，原因是换到朝南房间。',
    fields: [
      { key: 'move_type', label: '搬迁方式' },
      { key: 'tenant_name', label: '租户姓名' },
      { key: 'from_room', label: '原房间' },
      { key: 'from_room_whole', label: '整间搬迁原房间' },
      { key: 'to_room', label: '新房间' },
      { key: 'reason', label: '搬迁原因' },
    ],
  },
  {
    type: 'contract_template',
    label: '合同模板草稿',
    description: '适合让 AI 生成合同模板标题、说明和 HTML 内容。',
    placeholder: '例如：帮我生成一份标准房屋租赁合同模板，默认甲方是李房东。',
    fields: [
      { key: 'name', label: '合同名称' },
      { key: 'description', label: '合同说明' },
      { key: 'default_landlord', label: '默认甲方' },
      { key: 'content_html', label: '合同内容' },
    ],
  },
]

const assistantType = ref('tenant')
const inputText = ref('')
const messages = ref([])
const currentForm = ref({})
const completionDraft = ref(null)
const missingFields = ref([])
const assistantLoading = ref(false)
const assistantAutoSpeak = ref(true)
const uploadedImages = ref([])
const recording = ref(false)
const transcribing = ref(false)
const availableRooms = ref([])
const sessions = ref([])
const currentSessionId = ref(null)
const generating = ref(false)

const voiceSupported = typeof window !== 'undefined'
  && typeof MediaRecorder !== 'undefined'
  && !!navigator.mediaDevices?.getUserMedia

let mediaRecorder = null
let mediaStream = null
let audioChunks = []

const selectedBusiness = computed(() => businessOptions.find(item => item.type === assistantType.value) || businessOptions[0])
const canGenerate = computed(() => {
  if (missingFields.value.length > 0) return false
  const form = currentForm.value || {}
  return Object.keys(form).some((key) => {
    const value = form[key]
    if (value === null || value === undefined) return false
    if (typeof value === 'string') return value.trim() !== ''
    if (Array.isArray(value)) return value.length > 0
    return true
  })
})

const buildInitialMessages = () => ([
  {
    role: 'assistant',
    content: `现在开始处理“${selectedBusiness.value.label}”。你直接用自然语言描述，我会自动追问缺失字段。`
  }
])

const renderSummaryValue = (value) => {
  if (value === null || value === undefined || value === '') return '未填写'
  if (Array.isArray(value)) return `共 ${value.length} 条`
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

const readFileAsDataUrl = (file) => new Promise((resolve, reject) => {
  const reader = new FileReader()
  reader.onload = () => resolve(String(reader.result || ''))
  reader.onerror = () => reject(new Error('读取图片失败'))
  reader.readAsDataURL(file)
})

const mapFieldLabel = (field) => {
  return selectedBusiness.value.fields.find(item => item.key === field)?.label || field
}

const businessLabel = (type) => businessOptions.find(item => item.type === type)?.label || type

const buildContext = () => {
  if (assistantType.value === 'tenant' || assistantType.value === 'repair' || assistantType.value === 'move') {
    return {
      available_rooms: availableRooms.value,
    }
  }
  return {}
}

const speak = (text) => {
  if (!assistantAutoSpeak.value || typeof window === 'undefined' || !window.speechSynthesis) return
  const content = String(text || '').trim()
  if (!content) return
  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(content)
  utterance.lang = 'zh-CN'
  window.speechSynthesis.speak(utterance)
}

const resetAssistant = () => {
  inputText.value = ''
  currentForm.value = {}
  completionDraft.value = null
  missingFields.value = []
  messages.value = buildInitialMessages()
  uploadedImages.value = []
}

const startNewSession = () => {
  currentSessionId.value = null
  resetAssistant()
}

const stopRecordingTracks = () => {
  if (mediaStream) {
    mediaStream.getTracks().forEach(track => track.stop())
    mediaStream = null
  }
  mediaRecorder = null
  audioChunks = []
  recording.value = false
}

const sendMessage = async (forcedText = '') => {
  const safeForcedText = typeof forcedText === 'string' ? forcedText : ''
  const text = String(safeForcedText || inputText.value || '').trim()
  if ((!text && !uploadedImages.value.length) || assistantLoading.value) return

  inputText.value = ''
  const normalizedText = text || '请根据我上传的图片提取并整理信息。'
  messages.value = [...messages.value, { role: 'user', content: normalizedText }]
  assistantLoading.value = true

  try {
    const response = await aiAssistantApi.assistantChat({
      session_id: currentSessionId.value,
      assistant_type: assistantType.value,
      messages: messages.value,
      current_form: currentForm.value,
      context: buildContext(),
      input_images: uploadedImages.value.map(item => ({
        name: item.name,
        data_url: item.dataUrl,
      })),
    })
    const data = response?.data || {}
    currentSessionId.value = data.session_id || currentSessionId.value
    currentForm.value = { ...(data.current_form || currentForm.value) }
    completionDraft.value = data.completed ? { ...(data.current_form || {}) } : null
    missingFields.value = Array.isArray(data.missing_required_fields) ? data.missing_required_fields : []
    const reply = String(data.reply || '我先帮你整理了一部分信息。')
    messages.value = [...messages.value, { role: 'assistant', content: reply }]
    speak(reply)
    if (data.completed) {
      ElMessage.success('AI 已整理出可用草稿')
    }
    await fetchSessions()
  } catch (error) {
    const message = error?.response?.data?.error || error?.message || 'AI 助手暂时不可用'
    messages.value = [...messages.value, { role: 'assistant', content: message }]
    ElMessage.error(message)
  } finally {
    assistantLoading.value = false
  }
}

const transcribeAudio = async (audioBlob) => {
  transcribing.value = true
  try {
    const response = await aiAssistantApi.assistantTranscribe(audioBlob)
    const text = String(response?.data?.text || '').trim()
    if (!text) {
      ElMessage.warning('没有识别到有效语音内容')
      return
    }
    await sendMessage(text)
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || error?.message || '语音识别失败')
  } finally {
    transcribing.value = false
  }
}

const handleImageUpload = async (file) => {
  const raw = file?.raw || file
  if (!raw) return
  if (!String(raw.type || '').startsWith('image/')) {
    ElMessage.warning('请上传图片文件')
    return
  }
  if (uploadedImages.value.length >= 4) {
    ElMessage.warning('最多上传 4 张图片')
    return
  }
  if (raw.size && raw.size > 8 * 1024 * 1024) {
    ElMessage.warning('单张图片请控制在 8MB 以内')
    return
  }
  try {
    const dataUrl = await readFileAsDataUrl(raw)
    if (!dataUrl.startsWith('data:image/')) {
      throw new Error('图片编码失败')
    }
    uploadedImages.value = [
      ...uploadedImages.value,
      {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        name: String(raw.name || 'image'),
        dataUrl,
      },
    ].slice(0, 4)
    ElMessage.success('图片已加入识别队列')
  } catch (error) {
    ElMessage.error(error?.message || '图片读取失败')
  }
}

const removeImage = (id) => {
  uploadedImages.value = uploadedImages.value.filter(item => item.id !== id)
}

const toggleRecording = async () => {
  if (recording.value) {
    mediaRecorder?.stop()
    return
  }
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : 'audio/webm'
    audioChunks = []
    mediaRecorder = new MediaRecorder(mediaStream, { mimeType })
    mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) audioChunks.push(event.data)
    }
    mediaRecorder.onstop = async () => {
      const blob = new Blob(audioChunks, { type: mimeType })
      stopRecordingTracks()
      if (blob.size > 0) {
        await transcribeAudio(blob)
      }
    }
    mediaRecorder.start()
    recording.value = true
  } catch (_) {
    stopRecordingTracks()
    ElMessage.error('无法启用录音，请检查浏览器麦克风权限')
  }
}

const buildTenantPayload = (form) => {
  const payload = {
    name: String(form.name || '').trim(),
    gender: String(form.gender || '').trim(),
    nation: String(form.nation || '汉族').trim(),
    birth_date: String(form.birth_date || '').trim(),
    id_card: String(form.id_card || '').trim(),
    address: String(form.address || '').trim(),
    phone: String(form.phone || '').trim(),
    emergency_contact_name: String(form.emergency_contact || '').trim(),
    emergency_contact_phone: String(form.emergency_phone || '').trim(),
    room_no: String(form.room_no || '').trim(),
    check_in_date: String(form.check_in_date || '').trim(),
    check_out_date: String(form.check_out_date || '').trim(),
    remarks: String(form.notes || '').trim(),
  }
  return payload
}

const buildRoomPayload = (form) => {
  const building = String(form.building || '').trim().toUpperCase().match(/[A-Z]/)?.[0] || ''
  const roomNo = String(form.room_no || '').replace(/\D/g, '')
  return {
    building,
    room_no: building && roomNo ? `${building}-${roomNo}` : roomNo,
    room_type: String(form.room_type || '').trim(),
    price: Number(form.price || 0),
    deposit: Number(form.deposit || 0),
    status: String(form.status || '空闲').trim(),
    description: String(form.description || '').trim(),
  }
}

const buildRepairPayload = (form) => ({
  building: String(form.building || '').trim(),
  room_no: String(form.room_no || '').trim(),
  repair_type: String(form.repair_type || '').trim(),
  description: String(form.description || '').trim(),
  report_by: String(form.report_by || '').trim(),
  report_date: String(form.report_date || '').trim(),
  status: String(form.status || '待处理').trim(),
  repair_date: String(form.repair_date || '').trim(),
  repair_cost: form.repair_cost === '' || form.repair_cost === null || form.repair_cost === undefined ? null : Number(form.repair_cost),
  repair_person: String(form.repair_person || '').trim(),
  remarks: String(form.remarks || '').trim(),
})

const buildProcurementPayload = (form) => ({
  procurement_date: String(form.procurement_date || '').trim(),
  item_name: String(form.item_name || '').trim(),
  specification: String(form.specification || '').trim(),
  quantity: Number(form.quantity || 0),
  unit_price: Number(form.unit_price || 0),
  unit: String(form.unit || '').trim(),
  total_amount: Number(form.total_amount || 0),
  remarks: String(form.remarks || '').trim(),
})

const buildWarehousePayload = (form) => ({
  item_name: String(form.item_name || '').trim(),
  category: String(form.category || '').trim(),
  quantity: Number(form.quantity || 0),
  unit: String(form.unit || '').trim(),
  location: String(form.location || '').trim(),
  remarks: String(form.remarks || '').trim(),
})

const buildMovePayload = (form) => ({
  move_type: Number(form.move_type || 1),
  tenant_id: form.tenant_id ? Number(form.tenant_id) : undefined,
  from_room: String(form.from_room || '').trim(),
  from_room_whole: String(form.from_room_whole || '').trim(),
  to_room: String(form.to_room || '').trim(),
  reason: String(form.reason || '').trim(),
})

const buildContractTemplatePayload = (form) => ({
  name: String(form.name || '').trim(),
  description: String(form.description || '').trim(),
  content_html: String(form.content_html || '').trim(),
  default_landlord: String(form.default_landlord || '').trim(),
})

const resolveMovePayload = (form) => {
  const payload = buildMovePayload(form)
  if (payload.move_type === 1) {
    delete payload.from_room_whole
  } else {
    delete payload.tenant_id
    payload.from_room = payload.from_room_whole
    delete payload.from_room_whole
  }
  return payload
}

const generateDirectly = async () => {
  if (!canGenerate.value || generating.value) return
  generating.value = true
  try {
    const form = currentForm.value || {}
    if (assistantType.value === 'tenant') {
      await tenantsApi.addTenant(buildTenantPayload(form))
      ElMessage.success('租户已直接创建')
    } else if (assistantType.value === 'room') {
      await roomsApi.addRoom(buildRoomPayload(form))
      ElMessage.success('房间已直接创建')
    } else if (assistantType.value === 'repair') {
      await repairRecordsApi.addRepairRecord(buildRepairPayload(form))
      ElMessage.success('维修记录已直接创建')
    } else if (assistantType.value === 'procurement') {
      await procurementApi.createProcurement(buildProcurementPayload(form))
      ElMessage.success('采购记录已直接创建')
    } else if (assistantType.value === 'warehouse') {
      await warehouseApi.createItem(buildWarehousePayload(form))
      ElMessage.success('库存物资已直接创建')
    } else if (assistantType.value === 'move') {
      const payload = resolveMovePayload(form)
      if (payload.move_type === 1 && !payload.tenant_id) {
        throw new Error('当前还缺少租户 ID，建议继续补充租户姓名或从搬迁页手动确认。')
      }
      await movesApi.moveTenant(payload)
      ElMessage.success('搬迁记录已直接创建')
    } else if (assistantType.value === 'contract_template') {
      await contractTemplatesApi.addTemplate(buildContractTemplatePayload(form))
      ElMessage.success('合同模板已直接创建')
    }
    completionDraft.value = null
    currentForm.value = {}
    missingFields.value = []
    inputText.value = ''
    uploadedImages.value = []
    messages.value = buildInitialMessages()
    await fetchSessions()
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || error?.message || '直接生成失败')
  } finally {
    generating.value = false
  }
}

const fetchSessions = async () => {
  try {
    const response = await aiAssistantApi.listSessions()
    sessions.value = response?.data?.sessions || []
  } catch (error) {
    console.error('加载 AI 会话历史失败', error)
  }
}

const loadSession = async (id) => {
  try {
    const response = await aiAssistantApi.getSession(id)
    const session = response?.data?.session
    if (!session) return
    currentSessionId.value = session.id
    assistantType.value = session.assistant_type
    localStorage.setItem(LAST_ASSISTANT_TYPE_KEY, assistantType.value)
    await ensureBusinessContextLoaded()
    messages.value = (session.messages || []).map(item => ({
      role: item.role,
      content: item.content,
    }))
    currentForm.value = session.current_form || {}
    missingFields.value = session.missing_required_fields || []
    completionDraft.value = session.completed ? { ...(session.current_form || {}) } : null
    uploadedImages.value = []
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '加载会话失败')
  }
}

const deleteSession = async (id) => {
  try {
    await aiAssistantApi.deleteSession(id)
    if (currentSessionId.value === id) {
      startNewSession()
    }
    await fetchSessions()
    ElMessage.success('会话已删除')
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '删除会话失败')
  }
}

const openSettings = () => {
  router.push('/dashboard/ai-settings')
}

const switchBusiness = async (type) => {
  if (assistantType.value === type) return
  assistantType.value = type
  localStorage.setItem(LAST_ASSISTANT_TYPE_KEY, type)
  router.replace({ path: route.path, query: { type } })
  await ensureBusinessContextLoaded()
  resetAssistant()
}

const ensureBusinessContextLoaded = async () => {
  if (assistantType.value !== 'tenant' && assistantType.value !== 'repair' && assistantType.value !== 'move') {
    availableRooms.value = []
    return
  }
  try {
    const response = await roomsApi.listRooms({ fields: 'id,room_no,building,status,room_type,price' })
    availableRooms.value = response?.data?.rooms || []
  } catch (error) {
    console.error('加载 AI 房间上下文失败', error)
  }
}

onMounted(async () => {
  const queryType = String(route.query.type || '').trim()
  const rememberedType = String(localStorage.getItem(LAST_ASSISTANT_TYPE_KEY) || '').trim()
  assistantType.value = businessOptions.some(item => item.type === queryType)
    ? queryType
    : businessOptions.some(item => item.type === rememberedType)
      ? rememberedType
      : mapRouteToAssistantType(route.redirectedFrom?.path || '/dashboard/tenants')
  localStorage.setItem(LAST_ASSISTANT_TYPE_KEY, assistantType.value)
  await ensureBusinessContextLoaded()
  await fetchSessions()
  resetAssistant()
})

watch(() => route.query.type, async (value) => {
  const nextType = String(value || '').trim()
  if (!nextType || nextType === assistantType.value || !businessOptions.some(item => item.type === nextType)) return
  assistantType.value = nextType
  localStorage.setItem(LAST_ASSISTANT_TYPE_KEY, nextType)
  await ensureBusinessContextLoaded()
  resetAssistant()
})

onBeforeUnmount(() => {
  stopRecordingTracks()
  if (typeof window !== 'undefined' && window.speechSynthesis) {
    window.speechSynthesis.cancel()
  }
})
</script>

<style scoped>
.assistant-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.assistant-hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 22px 24px;
  border-radius: 20px;
  background:
    radial-gradient(circle at top left, rgba(250, 204, 21, 0.34), transparent 28%),
    linear-gradient(135deg, #0f172a 0%, #1d4ed8 54%, #0f766e 100%);
  color: #fff;
}

.assistant-title {
  margin: 0;
  font-size: 26px;
}

.assistant-subtitle {
  margin: 8px 0 0;
  max-width: 760px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.86);
}

.assistant-businesses {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 14px;
}

.business-card {
  border: 1px solid var(--surface-border, #dbe4f0);
  background: var(--card-bg, #fff);
  border-radius: 16px;
  padding: 16px;
  text-align: left;
  cursor: pointer;
  transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease;
}

.business-card:hover,
.business-card.active {
  transform: translateY(-2px);
  border-color: #2563eb;
  box-shadow: 0 14px 26px rgba(37, 99, 235, 0.12);
}

.business-card-title {
  font-weight: 700;
  color: var(--text-main, #0f172a);
}

.business-card-desc {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary, #64748b);
}

.assistant-workspace {
  display: grid;
  grid-template-columns: minmax(260px, 0.75fr) minmax(0, 1.35fr) minmax(320px, 0.85fr);
  gap: 18px;
}

.assistant-history-card,
.assistant-chat-card,
.assistant-summary-card {
  background: var(--card-bg, #fff);
  border: 1px solid var(--surface-border, #dbe4f0);
  border-radius: 18px;
  padding: 18px;
}

.assistant-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
}

.assistant-card-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-main, #0f172a);
}

.assistant-card-note {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary, #64748b);
}

.assistant-card-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.assistant-history-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 620px;
  overflow-y: auto;
}

.assistant-history-item {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  text-align: left;
  border: 1px solid var(--surface-border, #dbe4f0);
  background: transparent;
  border-radius: 14px;
  padding: 12px;
  cursor: pointer;
}

.assistant-history-item.active {
  border-color: #2563eb;
  background: rgba(37, 99, 235, 0.06);
}

.assistant-history-main {
  min-width: 0;
}

.assistant-history-title {
  font-weight: 700;
  color: var(--text-main, #0f172a);
}

.assistant-history-meta {
  display: flex;
  gap: 10px;
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-secondary, #64748b);
}

.assistant-history-preview {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary, #475569);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.assistant-message-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 220px;
  max-height: 420px;
  overflow-y: auto;
  margin-bottom: 14px;
  padding-right: 4px;
}

.assistant-message {
  max-width: 88%;
  padding: 10px 12px;
  border-radius: 14px;
}

.assistant-message.user {
  align-self: flex-end;
  background: #2563eb;
  color: #fff;
}

.assistant-message.assistant {
  align-self: flex-start;
  background: #eff6ff;
  color: #0f172a;
}

.assistant-message-role {
  margin-bottom: 4px;
  font-size: 11px;
  font-weight: 700;
  opacity: .85;
}

.assistant-message-content {
  white-space: pre-wrap;
  line-height: 1.7;
  word-break: break-word;
}

.assistant-toolbar {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 12px;
}

.assistant-upload-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.assistant-upload-tip {
  font-size: 12px;
  color: var(--text-secondary, #64748b);
}

.assistant-image-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.assistant-image-card {
  border: 1px solid var(--surface-border, #dbe4f0);
  border-radius: 12px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.92);
}

.assistant-image-thumb {
  width: 100%;
  height: 92px;
  object-fit: cover;
  border-radius: 8px;
  display: block;
}

.assistant-image-name {
  margin: 8px 0;
  font-size: 12px;
  color: var(--text-secondary, #475569);
  word-break: break-all;
}

.assistant-status {
  margin-top: 10px;
  font-size: 12px;
  color: var(--text-secondary, #64748b);
}

.summary-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.summary-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px dashed var(--surface-border, #dbe4f0);
}

.summary-label {
  flex: 0 0 110px;
  font-weight: 700;
  color: var(--text-main, #0f172a);
}

.summary-value {
  flex: 1;
  text-align: right;
  color: var(--text-secondary, #475569);
  word-break: break-word;
}

.summary-missing {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
}

@media (max-width: 1080px) {
  .assistant-workspace {
    grid-template-columns: 1fr;
  }
}
</style>
