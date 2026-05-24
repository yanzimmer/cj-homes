<template>
  <div class="public-checkin-page">
    <div class="public-theme-toggle">
      <ThemeModeSwitch floating />
    </div>
    <div class="public-checkin-card">
      <div class="header">
        <h2>自助入住登记</h2>
        <div v-if="roomDisplayLabel" class="room-summary">
          <div class="room-summary__label">当前房间号</div>
          <div class="room-summary__value">{{ roomDisplayLabel }}</div>
        </div>
      </div>

      <div v-if="loading" class="loading-state">正在加载链接信息...</div>
      <el-alert v-else-if="error" :title="error" type="error" show-icon :closable="false" />

      <div v-else class="ocr-toolbar">
        <input
          ref="idCardFileInputRef"
          type="file"
          accept="image/*"
          capture="environment"
          class="hidden-file-input"
          @change="handleIdCardFileChange"
        />
        <div class="ocr-toolbar-main">
          <span class="ocr-toolbar-tip ocr-toolbar-leading">拍照/上传身份证正面识别</span>
          <el-button
            type="primary"
            plain
            :loading="recognizingIdCard"
            :disabled="!ocrStatus.enabled"
            @click="openIdCardFileDialog"
          >
            OCR识别
          </el-button>
          <el-button type="primary" plain @click="openAiDialog">AI识别</el-button>
          <span class="ocr-toolbar-tip">
            支持手机拍照和电脑上传，识别后会自动回填，仍可手动修改。
            <template v-if="ocrStatus.max_recognitions > 0">
              剩余 {{ ocrStatus.remaining_count ?? 0 }} / {{ ocrStatus.max_recognitions }} 次。
            </template>
          </span>
          <el-button type="danger" plain @click="clearDraftManually">清空本地草稿</el-button>
        </div>
        <el-alert
          v-if="!ocrStatus.enabled && ocrStatus.reason"
          :title="ocrStatus.reason"
          type="warning"
          show-icon
          :closable="false"
          class="ocr-alert"
        />
        <el-alert
          v-if="ocrMessage"
          :title="ocrMessage"
          :type="ocrMessageType"
          show-icon
          :closable="false"
          class="ocr-alert"
        />
        <el-alert
          v-if="submissionStatus.visible"
          :title="submissionStatus.title"
          :type="submissionStatus.type"
          show-icon
          :closable="false"
          class="ocr-alert"
        />

        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="checkin-form">
        <el-form-item label="姓名" prop="name"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="性别" prop="gender">
          <el-radio-group v-model="form.gender">
            <el-radio label="男">男</el-radio>
            <el-radio label="女">女</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="民族"><el-input v-model="form.nation" /></el-form-item>
        <el-form-item label="身份证号" prop="id_card"><el-input v-model="form.id_card" /></el-form-item>
        <el-form-item label="出生日期">
          <el-input :model-value="derivedBirthDate || '身份证号正确后自动显示'" disabled />
        </el-form-item>
        <el-form-item label="住址" prop="address"><el-input v-model="form.address" /></el-form-item>
        <el-form-item label="联系电话" prop="phone"><el-input v-model="form.phone" /></el-form-item>
        <el-form-item label="紧急联系人" prop="emergency_contact_name"><el-input v-model="form.emergency_contact_name" /></el-form-item>
        <el-form-item label="紧急联系电话" prop="emergency_contact_phone"><el-input v-model="form.emergency_contact_phone" /></el-form-item>
        <el-form-item label="入住日期" prop="check_in_date"><el-date-picker v-model="form.check_in_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="退房日期" prop="check_out_date"><el-date-picker v-model="form.check_out_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remarks" type="textarea" :rows="3" /></el-form-item>
        <el-button type="primary" :loading="submitting" @click="submitForm">提交入住信息</el-button>
        </el-form>
      </div>

      <el-dialog
        title="AI识别入住信息"
        v-model="aiDialog.visible"
        width="min(640px, calc(100vw - 24px))"
        class="ai-checkin-dialog app-ai-dialog"
        modal-class="app-ai-dialog-overlay"
        @close="resetAiDialog"
      >
        <el-form label-position="top">
          <el-form-item label="文字描述">
            <el-input
              v-model="aiDialog.text"
              type="textarea"
              :rows="4"
              placeholder="例如：张三，身份证号 110101199001011234，手机 13800000000，紧急联系人李四 13900000000，今天入住。也可以拍摄身份证正面让本地模型识别。"
            />
          </el-form-item>
          <el-form-item label="拍照或上传">
            <input
              ref="aiCameraInputRef"
              type="file"
              accept="image/*"
              capture="environment"
              class="hidden-file-input"
              @change="handleAiImageInputChange"
            />
            <input
              ref="aiImageInputRef"
              type="file"
              accept="image/*"
              multiple
              class="hidden-file-input"
              @change="handleAiImageInputChange"
            />
            <div class="ai-actions">
              <el-button type="primary" plain @click="openAiCameraPicker">拍照</el-button>
              <el-button type="primary" plain @click="openAiImagePicker">上传图片</el-button>
              <el-button v-if="aiDialog.images.length" type="danger" plain @click="clearAiImages">清空图片</el-button>
            </div>
            <div class="upload-progress-text">已选 {{ aiDialog.images.length }} / 4</div>
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
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { publicSelfCheckinApi } from '../api'
import ThemeModeSwitch from '../components/ThemeModeSwitch.vue'
import { applyTheme, getPreferredTheme } from '../utils/theme'

const route = useRoute()
const token = String(route.params.token || '')
const draftStorageKey = `public-checkin-draft:${token}`
const loading = ref(true)
const submitting = ref(false)
const error = ref('')
const formRef = ref(null)
const idCardFileInputRef = ref(null)
const aiCameraInputRef = ref(null)
const aiImageInputRef = ref(null)
const recognizingIdCard = ref(false)
const ocrMessage = ref('')
const ocrMessageType = ref('success')
const aiDialog = reactive({
  visible: false,
  loading: false,
  text: '',
  images: [],
})
const ocrStatus = reactive({
  configured: false,
  enabled: false,
  used_count: 0,
  max_recognitions: 0,
  remaining_count: null,
  reason: '',
})
const roomInfo = reactive({
  room_no: '',
  building: '',
})
const submissionStatus = reactive({
  visible: false,
  title: '',
  type: 'info',
  submission_id: null,
  status: '',
  reject_reason: '',
})

const form = reactive({
  name: '',
  gender: '男',
  nation: '汉族',
  id_card: '',
  address: '',
  phone: '',
  emergency_contact_name: '',
  emergency_contact_phone: '',
  check_in_date: '',
  check_out_date: '',
  remarks: '',
})

const idCardPattern = /^\d{17}[\dXx]$/
const phonePattern = /^1[3-9]\d{9}$/

const deriveBirthDateFromIdCard = (value) => {
  const raw = String(value || '').trim()
  if (!idCardPattern.test(raw)) return ''
  const year = raw.slice(6, 10)
  const month = raw.slice(10, 12)
  const day = raw.slice(12, 14)
  const date = `${year}-${month}-${day}`
  const localDate = new Date(Number(year), Number(month) - 1, Number(day))
  if (Number.isNaN(localDate.getTime())) return ''
  const isSameDate =
    localDate.getFullYear() === Number(year) &&
    localDate.getMonth() + 1 === Number(month) &&
    localDate.getDate() === Number(day)
  return isSameDate ? date : ''
}

const derivedBirthDate = computed(() => deriveBirthDateFromIdCard(form.id_card))
const roomDisplayLabel = computed(() => {
  const roomNo = String(roomInfo.room_no || '').trim()
  const building = String(roomInfo.building || '').trim()
  if (!roomNo) return ''
  if (roomNo.includes('-')) return roomNo
  if (building) return `${building}-${roomNo}`
  return roomNo
})

const validateIdCard = (_, value, callback) => {
  const raw = String(value || '').trim()
  if (!raw) {
    callback(new Error('请输入身份证号'))
    return
  }
  if (!idCardPattern.test(raw) || !deriveBirthDateFromIdCard(raw)) {
    callback(new Error('请输入正确的身份证号'))
    return
  }
  callback()
}

const validatePhone = (_, value, callback) => {
  const raw = String(value || '').trim()
  if (!raw) {
    callback(new Error('请输入手机号'))
    return
  }
  if (!phonePattern.test(raw)) {
    callback(new Error('请输入正确的手机号'))
    return
  }
  callback()
}

const validateCheckOutDate = (_, value, callback) => {
  if (!value) {
    callback(new Error('请选择退房日期'))
    return
  }
  if (form.check_in_date && value <= form.check_in_date) {
    callback(new Error('退房日期必须晚于入住日期'))
    return
  }
  callback()
}

const rules = {
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  gender: [{ required: true, message: '请选择性别', trigger: 'change' }],
  id_card: [{ validator: validateIdCard, trigger: 'blur' }],
  address: [{ required: true, message: '请输入住址', trigger: 'blur' }],
  phone: [{ validator: validatePhone, trigger: 'blur' }],
  emergency_contact_name: [{ required: true, message: '请输入紧急联系人', trigger: 'blur' }],
  emergency_contact_phone: [{ validator: validatePhone, trigger: 'blur' }],
  check_in_date: [{ required: true, message: '请选择入住日期', trigger: 'change' }],
  check_out_date: [{ validator: validateCheckOutDate, trigger: 'change' }],
}

const saveDraftToLocal = () => {
  try {
    localStorage.setItem(
      draftStorageKey,
      JSON.stringify({
        form: { ...form },
        ocrMessage: ocrMessage.value,
        ocrMessageType: ocrMessageType.value,
        submission: {
          submission_id: submissionStatus.submission_id,
          status: submissionStatus.status,
          reject_reason: submissionStatus.reject_reason,
          id_card: form.id_card,
        },
        savedAt: Date.now(),
      })
    )
  } catch (_) {}
}

const loadDraftFromLocal = () => {
  try {
    const raw = localStorage.getItem(draftStorageKey)
    if (!raw) return
    const data = JSON.parse(raw)
    const draftForm = data?.form || {}
    Object.keys(form).forEach((key) => {
      if (draftForm[key] !== undefined && draftForm[key] !== null) {
        form[key] = draftForm[key]
      }
    })
    if (data?.ocrMessage) {
      ocrMessage.value = String(data.ocrMessage)
      ocrMessageType.value = data?.ocrMessageType || 'success'
    }
    if (data?.submission?.submission_id) {
      submissionStatus.submission_id = Number(data.submission.submission_id)
      submissionStatus.status = String(data.submission.status || '')
      submissionStatus.reject_reason = String(data.submission.reject_reason || '')
    }
  } catch (_) {}
}

const clearLocalDraft = () => {
  try {
    localStorage.removeItem(draftStorageKey)
  } catch (_) {}
}

const applySubmissionStatus = (submission = {}) => {
  const status = String(submission.status || '').trim()
  submissionStatus.submission_id = submission.id ?? submissionStatus.submission_id
  submissionStatus.status = status
  submissionStatus.reject_reason = String(submission.reject_reason || '')
  if (status === 'approved') {
    submissionStatus.visible = true
    submissionStatus.type = 'success'
    submissionStatus.title = '你的入住登记已通过管理员确认。'
    return
  }
  if (status === 'rejected') {
    submissionStatus.visible = true
    submissionStatus.type = 'error'
    submissionStatus.title = submissionStatus.reject_reason
      ? `你的入住登记已被驳回：${submissionStatus.reject_reason}`
      : '你的入住登记已被驳回，请联系管理员。'
    return
  }
    if (status === 'pending') {
      submissionStatus.visible = true
      submissionStatus.type = 'info'
      submissionStatus.title = '你的入住登记已提交，正在等待管理员确认。'
      return
    }
  submissionStatus.visible = false
  submissionStatus.title = ''
  submissionStatus.type = 'info'
}

const clearDraftManually = () => {
  Object.keys(form).forEach((key) => {
    form[key] = key === 'gender' ? '男' : key === 'nation' ? '汉族' : ''
  })
  ocrMessage.value = ''
  ocrMessageType.value = 'success'
  submissionStatus.visible = false
  submissionStatus.title = ''
  submissionStatus.type = 'info'
  submissionStatus.submission_id = null
  submissionStatus.status = ''
  submissionStatus.reject_reason = ''
  clearLocalDraft()
  ElMessage.success('本地草稿已清空')
}

const fetchLinkInfo = async () => {
  loading.value = true
  try {
    const response = await publicSelfCheckinApi.getForm(token)
    const room = response?.data?.room || {}
    const ocr = response?.data?.ocr || {}
    roomInfo.room_no = room.room_no || ''
    roomInfo.building = room.building || ''
    ocrStatus.configured = Boolean(ocr.configured)
    ocrStatus.enabled = Boolean(ocr.enabled)
    ocrStatus.used_count = Number(ocr.used_count || 0)
    ocrStatus.max_recognitions = Number(ocr.max_recognitions || 0)
    ocrStatus.remaining_count = ocr.remaining_count ?? null
    ocrStatus.reason = ocr.reason || ''
  } catch (err) {
    error.value = err?.response?.data?.error || '入住链接无效或已失效'
  } finally {
    loading.value = false
  }
}

const fetchSubmissionStatus = async () => {
  const submissionId = Number(submissionStatus.submission_id || 0)
  const idCard = String(form.id_card || '').trim()
  if (!submissionId || !idCard) return
  try {
    const response = await publicSelfCheckinApi.getSubmissionStatus(token, {
      submission_id: submissionId,
      id_card: idCard,
    })
    applySubmissionStatus(response?.data?.submission || {})
    saveDraftToLocal()
  } catch (_) {}
}

const openIdCardFileDialog = () => {
  if (recognizingIdCard.value) return
  idCardFileInputRef.value?.click()
}

const applyRecognizedFields = (fields = {}) => {
  if (fields.name) form.name = fields.name
  if (fields.gender === '男' || fields.gender === '女') form.gender = fields.gender
  if (fields.nation) form.nation = fields.nation
  if (fields.id_card) form.id_card = fields.id_card
  if (fields.address) form.address = fields.address
}

const applyAiDraftFields = (draft = {}) => {
  if (draft.name) form.name = String(draft.name)
  if (draft.gender === '男' || draft.gender === '女') form.gender = draft.gender
  if (draft.nation) form.nation = String(draft.nation)
  if (draft.id_card) form.id_card = String(draft.id_card).toUpperCase()
  if (draft.address) form.address = String(draft.address)
  if (draft.phone) form.phone = String(draft.phone)
  if (draft.emergency_contact_name) form.emergency_contact_name = String(draft.emergency_contact_name)
  if (draft.emergency_contact_phone) form.emergency_contact_phone = String(draft.emergency_contact_phone)
  if (draft.check_in_date) form.check_in_date = String(draft.check_in_date)
  if (draft.check_out_date) form.check_out_date = String(draft.check_out_date)
  if (draft.remarks) form.remarks = String(draft.remarks)
}

const applyOcrStatus = (ocr = {}) => {
  ocrStatus.configured = Boolean(ocr.configured)
  ocrStatus.enabled = Boolean(ocr.enabled)
  ocrStatus.used_count = Number(ocr.used_count || 0)
  ocrStatus.max_recognitions = Number(ocr.max_recognitions || 0)
  ocrStatus.remaining_count = ocr.remaining_count ?? null
  ocrStatus.reason = ocr.reason || ''
}

const handleIdCardFileChange = async (event) => {
  const file = event?.target?.files?.[0]
  event.target.value = ''
  if (!file) return
  if (!file.type.startsWith('image/')) {
    ElMessage.error('请上传图片文件')
    return
  }
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.error('身份证图片不能超过 10MB')
    return
  }
  recognizingIdCard.value = true
  ocrMessage.value = ''
  try {
    const response = await publicSelfCheckinApi.recognizeIdCard(token, file)
    const result = response?.data || {}
    applyRecognizedFields(result.fields || {})
    applyOcrStatus(result.ocr || {})
    const hints = Array.isArray(result.hints) ? result.hints.filter(Boolean) : []
    ocrMessageType.value = hints.length ? 'warning' : 'success'
    ocrMessage.value = hints.length ? `识别成功，${hints.join(' ')}` : '识别成功，已自动回填身份证信息。'
    ElMessage.success('身份证识别成功')
  } catch (err) {
    ocrMessageType.value = 'error'
    ocrMessage.value = err?.response?.data?.error || '身份证识别失败'
    ElMessage.error(ocrMessage.value)
  } finally {
    recognizingIdCard.value = false
  }
}

const revokeAiImageUrls = () => {
  aiDialog.images.forEach((item) => {
    if (String(item?.url || '').startsWith('blob:')) URL.revokeObjectURL(item.url)
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

const openAiImagePicker = () => {
  aiImageInputRef.value?.click()
}

const openAiCameraPicker = () => {
  aiCameraInputRef.value?.click()
}

const handleAiImageInputChange = (event) => {
  const files = Array.from(event?.target?.files || [])
  event.target.value = ''
  files.forEach(file => addAiImageFile(file))
}

const removeAiImage = (index) => {
  const item = aiDialog.images[index]
  if (!item) return
  if (String(item.url || '').startsWith('blob:')) URL.revokeObjectURL(item.url)
  aiDialog.images.splice(index, 1)
}

const clearAiImages = () => {
  revokeAiImageUrls()
  aiDialog.images = []
}

const submitAiDraft = async () => {
  if (!aiDialog.text.trim() && aiDialog.images.length === 0) {
    ElMessage.warning('请先输入文字、拍照或上传图片')
    return
  }
  aiDialog.loading = true
  try {
    const formData = new FormData()
    formData.append('text', aiDialog.text.trim())
    aiDialog.images.forEach((item) => {
      formData.append('images', item.file)
    })
    const response = await publicSelfCheckinApi.createAiDraft(token, formData)
    applyAiDraftFields(response?.data?.draft || {})
    aiDialog.visible = false
    ocrMessageType.value = 'success'
    ocrMessage.value = 'AI 已生成入住信息并回填，请确认后再提交。'
    ElMessage.success('AI 信息已填入表单')
  } catch (err) {
    ElMessage.error(err?.response?.data?.error || err?.message || 'AI识别失败')
  } finally {
    aiDialog.loading = false
  }
}

const submitForm = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      const response = await publicSelfCheckinApi.submit(token, {
        ...form,
        birth_date: derivedBirthDate.value,
      })
      submissionStatus.submission_id = response?.data?.submission_id || null
      applySubmissionStatus({
        id: response?.data?.submission_id || null,
        status: 'pending',
        reject_reason: '',
      })
      saveDraftToLocal()
      ElMessage.success('入住信息已提交，等待管理员确认')
    } catch (err) {
      ElMessage.error(err?.response?.data?.error || '提交失败')
    } finally {
      submitting.value = false
    }
  })
}

onMounted(() => {
  document.documentElement.classList.add('public-checkin-route')
  applyTheme(getPreferredTheme())
  fetchLinkInfo()
  loadDraftFromLocal()
  fetchSubmissionStatus()
  if (String(route.query.ai || '') === '1') {
    openAiDialog()
  }
})

onUnmounted(() => {
  document.documentElement.classList.remove('public-checkin-route')
})

watch(
  () => ({ ...form, ocrMessage: ocrMessage.value, ocrMessageType: ocrMessageType.value }),
  () => {
    saveDraftToLocal()
  },
  { deep: true }
)
</script>

<style scoped>
.public-checkin-page {
  min-height: 100vh;
  padding: 32px 16px;
  background:
    radial-gradient(circle at top left, rgba(37, 99, 235, 0.12), transparent 32%),
    linear-gradient(180deg, var(--bg-color) 0%, var(--surface-muted) 100%);
  color: var(--text-main);
}

.public-checkin-card {
  max-width: 760px;
  margin: 0 auto;
  padding: 24px;
  border-radius: var(--card-radius);
  background: var(--card-bg);
  border: 1px solid var(--surface-border);
  box-shadow: var(--card-shadow);
}

html.dark .public-checkin-page {
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

.room-summary {
  display: inline-flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--surface-border);
  background: var(--card-bg);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.room-summary__label {
  font-size: 12px;
  color: var(--text-secondary);
}

.room-summary__value {
  font-size: 22px;
  line-height: 1.2;
  font-weight: 700;
  color: var(--text-main);
}

.loading-state {
  color: var(--text-secondary);
}

.ocr-toolbar {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ocr-toolbar-main {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.ocr-toolbar-tip {
  color: var(--text-secondary);
  font-size: 13px;
}

.ocr-toolbar-leading {
  width: 100%;
}

.ocr-alert {
  margin-bottom: 4px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.hidden-file-input {
  display: none;
}

.ai-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.upload-progress-text {
  width: 100%;
  margin-top: 8px;
  color: var(--text-secondary);
  font-size: 13px;
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
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid var(--surface-border);
}

.checkin-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.checkin-form :deep(.el-form-item) {
  margin-bottom: 0;
}

.checkin-form > :last-child {
  grid-column: 1 / -1;
}

@media (max-width: 768px) {
  .public-checkin-page {
    padding: 64px 8px 16px;
  }

  .public-checkin-card {
    padding: 16px 12px;
  }

  .room-summary {
    width: 100%;
    box-sizing: border-box;
  }

  .room-summary__value {
    font-size: 20px;
  }

  :deep(.ai-checkin-dialog) {
    margin: 8px auto;
  }

  :deep(.ai-checkin-dialog .el-dialog__body) {
    padding: 12px 14px;
  }

  :deep(.ai-checkin-dialog .el-dialog__header),
  :deep(.ai-checkin-dialog .el-dialog__footer) {
    padding-left: 14px;
    padding-right: 14px;
  }

  .dialog-footer {
    width: 100%;
  }

  .dialog-footer .el-button {
    flex: 1;
    margin-left: 0;
  }

  .ai-actions {
    width: 100%;
  }

  .ai-actions .el-button {
    flex: 1;
    margin-left: 0;
  }

  .ai-image-thumb {
    width: 76px;
    height: 76px;
  }

  .checkin-form {
    grid-template-columns: 1fr;
  }
}
</style>
