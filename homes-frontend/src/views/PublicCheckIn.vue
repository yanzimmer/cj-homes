<template>
  <div class="public-checkin-page">
    <div class="public-checkin-card">
      <div class="header">
        <h2>自助入住登记</h2>
        <p v-if="roomInfo.room_no">房间：{{ roomInfo.building }}栋 {{ roomInfo.room_no }}</p>
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
          <el-button
            type="primary"
            plain
            :loading="recognizingIdCard"
            :disabled="!ocrStatus.enabled"
            @click="openIdCardFileDialog"
          >
            拍照/上传身份证正面识别
          </el-button>
          <span class="ocr-toolbar-tip">
            支持手机拍照和电脑上传，识别后会自动回填，仍可手动修改。
            <template v-if="ocrStatus.max_recognitions > 0">
              剩余 {{ ocrStatus.remaining_count ?? 0 }} / {{ ocrStatus.max_recognitions }} 次。
            </template>
          </span>
          <el-button text @click="clearDraftManually">清空本地草稿</el-button>
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
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { publicSelfCheckinApi } from '../api'

const route = useRoute()
const token = String(route.params.token || '')
const draftStorageKey = `public-checkin-draft:${token}`
const loading = ref(true)
const submitting = ref(false)
const error = ref('')
const formRef = ref(null)
const idCardFileInputRef = ref(null)
const recognizingIdCard = ref(false)
const ocrMessage = ref('')
const ocrMessageType = ref('success')
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
  } catch (_) {}
}

const clearLocalDraft = () => {
  try {
    localStorage.removeItem(draftStorageKey)
  } catch (_) {}
}

const clearDraftManually = () => {
  Object.keys(form).forEach((key) => {
    form[key] = key === 'gender' ? '男' : key === 'nation' ? '汉族' : ''
  })
  ocrMessage.value = ''
  ocrMessageType.value = 'success'
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

const submitForm = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      await publicSelfCheckinApi.submit(token, {
        ...form,
        birth_date: derivedBirthDate.value,
      })
      ElMessage.success('入住信息已提交，等待管理员确认')
    } catch (err) {
      ElMessage.error(err?.response?.data?.error || '提交失败')
    } finally {
      submitting.value = false
    }
  })
}

onMounted(() => {
  fetchLinkInfo()
  loadDraftFromLocal()
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
}

.public-checkin-card {
  max-width: 760px;
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
  color: var(--text-secondary);
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

.ocr-alert {
  margin-bottom: 4px;
}

.hidden-file-input {
  display: none;
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
  .checkin-form {
    grid-template-columns: 1fr;
  }
}
</style>
