<template>
  <div class="notification-config" :class="{ 'notification-config--mobile': mobileMode }">
    <div class="page-header">
      <div class="header-operations">
        <div v-if="config.last_updated && !mobileMode" class="last-updated">
          <el-icon><Timer /></el-icon>
          <span>最后更新: {{ config.last_updated }}</span>
        </div>
        <el-button class="header-action-btn" type="primary" @click="saveConfig" :loading="saving">
          <el-icon><Check /></el-icon> 保存配置
        </el-button>
        <el-button class="header-action-btn" @click="resetForm">
          <el-icon><RefreshRight /></el-icon> 重置
        </el-button>
      </div>
    </div>

    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="10" animated />
    </div>

    <div v-else-if="error" class="error-container">
      <el-alert :title="error" type="error" show-icon />
      <el-button type="primary" @click="fetchConfig" class="mt-3">
        <el-icon><Refresh /></el-icon> 重试
      </el-button>
    </div>

    <el-form 
      v-else
      ref="configForm"
      :model="config"
      label-position="top"
      :rules="rules"
      class="config-form"
    >
      <div v-if="mobileMode" class="mobile-tab-strip">
        <button
          v-for="item in mobileTabs"
          :key="item.name"
          type="button"
          class="mobile-tab-chip"
          :class="{ 'mobile-tab-chip--active': activeTab === item.name }"
          @click="activeTab = item.name"
        >
          {{ item.label }}
        </button>
      </div>

      <el-tabs v-model="activeTab" :tab-position="tabPosition" class="config-tabs">
        
        <!-- Tab 1: 基础设置 -->
        <el-tab-pane name="basic" label="基础设置">
          <template #label>
            <span class="custom-tabs-label">
              <el-icon><Setting /></el-icon>
              <span>基础设置</span>
            </span>
          </template>
          
          <el-card shadow="never" class="section-card">
            <template #header>
              <div class="card-header">
                <span>全局开关与规则</span>
              </div>
            </template>
            
            <el-row :gutter="24">
              <el-col :span="6">
                <el-form-item label="租期提前提醒天数" prop="lease_advance_days">
                  <el-input-number 
                    v-model="config.lease_advance_days" 
                    :min="0" 
                    :max="365"
                    controls-position="right"
                    style="width: 100%"
                  />
                  <div class="form-hint">首页“即将到期预警”和租期通知使用这个天数</div>
                </el-form-item>
              </el-col>

              <el-col :span="6">
                <el-form-item label="收租提前提醒天数" prop="rent_advance_days">
                  <el-input-number 
                    v-model="config.rent_advance_days" 
                    :min="0" 
                    :max="365"
                    controls-position="right"
                    style="width: 100%"
                  />
                  <div class="form-hint">首页“收租提醒”和后续收租通知使用这个天数</div>
                </el-form-item>
              </el-col>

              <el-col :span="6">
                <el-form-item label="重复提醒次数" prop="reminder_count">
                  <el-input-number 
                    v-model="config.reminder_count" 
                    :min="0" 
                    :max="5"
                    controls-position="right"
                    style="width: 100%"
                  />
                  <div class="form-hint">0表示不重复，大于0表示总共发送几次</div>
                </el-form-item>
              </el-col>

              <el-col :span="6">
                <el-form-item label="启用通知系统" prop="enabled">
                  <el-switch
                    v-model="config.enabled"
                    active-text="已启用"
                    inactive-text="已禁用"
                    inline-prompt
                    size="large"
                  />
                </el-form-item>
              </el-col>
            </el-row>
          </el-card>

          <el-card shadow="never" class="section-card mt-3">
            <template #header>
              <div class="card-header">
                <span>通知渠道选择</span>
              </div>
            </template>
            
            <el-row :gutter="24">
              <el-col :span="12">
                <el-form-item label="租户接收方式" prop="tenant_notification_methods">
                  <el-checkbox-group v-model="config.tenant_notification_methods">
                    <el-checkbox label="email" border>
                      <el-icon class="mr-1"><Message /></el-icon> 邮件
                    </el-checkbox>
                    <el-checkbox label="sms" border>
                      <el-icon class="mr-1"><ChatDotRound /></el-icon> 短信
                    </el-checkbox>
                  </el-checkbox-group>
                </el-form-item>
                <el-form-item label="租户提醒场景" prop="tenant_notification_scenes">
                  <el-checkbox-group v-model="config.tenant_notification_scenes">
                    <el-checkbox label="lease_expiry" border>即将到期预警</el-checkbox>
                    <el-checkbox label="rent_reminder" border>收租提醒</el-checkbox>
                  </el-checkbox-group>
                </el-form-item>
              </el-col>
              
              <el-col :span="12">
                <el-form-item label="房东接收方式" prop="landlord_notification_methods">
                  <el-checkbox-group v-model="config.landlord_notification_methods">
                    <el-checkbox label="email" border>
                      <el-icon class="mr-1"><Message /></el-icon> 邮件
                    </el-checkbox>
                    <el-checkbox label="sms" border>
                      <el-icon class="mr-1"><ChatDotRound /></el-icon> 短信
                    </el-checkbox>
                  </el-checkbox-group>
                </el-form-item>
                <el-form-item label="房东提醒场景" prop="landlord_notification_scenes">
                  <el-checkbox-group v-model="config.landlord_notification_scenes">
                    <el-checkbox label="lease_expiry" border>即将到期预警</el-checkbox>
                    <el-checkbox label="rent_reminder" border>收租提醒</el-checkbox>
                  </el-checkbox-group>
                </el-form-item>
              </el-col>
            </el-row>
          </el-card>
        </el-tab-pane>

        <!-- Tab 2: 邮件服务 -->
        <el-tab-pane name="email_service" label="邮件服务">
          <template #label>
            <span class="custom-tabs-label">
              <el-icon><Message /></el-icon>
              <span>邮件服务</span>
            </span>
          </template>
          
          <el-card shadow="never" class="section-card">
            <template #header>
              <div class="card-header">
                <span>SMTP 服务器配置</span>
                <el-button type="primary" size="small" @click="testEmailSending" :loading="testingEmail" plain>
                  <el-icon><Connection /></el-icon> 测试连接
                </el-button>
              </div>
            </template>
            
            <el-row :gutter="24">
              <el-col :span="12">
                <el-form-item label="SMTP 服务器地址" prop="smtp_config.server">
                  <el-input v-model="config.smtp_config.server" placeholder="例如: smtp.qq.com" />
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="端口" prop="smtp_config.port">
                  <el-input-number v-model="config.smtp_config.port" :min="1" :max="65535" controls-position="right" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="安全连接" prop="smtp_config.use_tls">
                   <el-switch v-model="config.smtp_config.use_tls" active-text="TLS/SSL" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="24">
              <el-col :span="12">
                <el-form-item label="邮箱账号" prop="smtp_config.username">
                  <el-input v-model="config.smtp_config.username" placeholder="例如: yourname@qq.com" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="授权码/密码" prop="smtp_config.password">
                  <el-input v-model="config.smtp_config.password" type="password" show-password placeholder="SMTP服务授权码" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-card>
        </el-tab-pane>

        <!-- Tab 3: 短信服务 -->
        <el-tab-pane name="sms_service" label="短信服务">
          <template #label>
            <span class="custom-tabs-label">
              <el-icon><ChatDotRound /></el-icon>
              <span>短信服务</span>
            </span>
          </template>
          
          <el-card shadow="never" class="section-card">
            <template #header>
              <div class="card-header">
                <span>腾讯云短信配置</span>
                <el-tag type="info" size="small">仅支持腾讯云</el-tag>
              </div>
            </template>
            
            <el-row :gutter="24">
              <el-col :span="12">
                <el-form-item label="SecretId" prop="sms_config.secret_id">
                  <el-input v-model="config.sms_config.secret_id" placeholder="API密钥 ID" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="SecretKey" prop="sms_config.secret_key">
                  <el-input v-model="config.sms_config.secret_key" type="password" show-password placeholder="API密钥 Key" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="24">
              <el-col :span="12">
                <el-form-item label="短信应用 ID (SDKAppID)" prop="sms_config.app_id">
                  <el-input v-model="config.sms_config.app_id" placeholder="例如: 1400xxxxxx" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="短信签名" prop="sms_config.sign_name">
                  <el-input v-model="config.sms_config.sign_name" placeholder="已审核通过的签名内容" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-card>
        </el-tab-pane>

        <!-- Tab 4: 租户通知详情 -->
        <el-tab-pane name="tenant_notify" label="租户通知">
          <template #label>
            <span class="custom-tabs-label">
              <el-icon><User /></el-icon>
              <span>租户通知</span>
            </span>
          </template>

          <div v-if="!config.tenant_notification_methods || config.tenant_notification_methods.length === 0" class="empty-tip">
            <el-empty description="未启用租户通知，请在基础设置中开启" :image-size="100" />
          </div>

          <template v-else>
            <!-- 租户邮件配置 -->
            <el-card v-if="config.tenant_notification_methods.includes('email')" shadow="never" class="section-card mb-3">
              <template #header>
                <div class="card-header">
                  <span>邮件通知模板</span>
                  <el-button type="primary" size="small" @click="testTenantEmailSending" :loading="testingTenantEmail" plain>
                     测试发送
                  </el-button>
                </div>
              </template>
              
              <el-form-item label="邮件主题" prop="tenant_email_config.subject">
                <el-input v-model="config.tenant_email_config.subject" placeholder="例如: 租期即将到期通知" />
              </el-form-item>
              
              <el-form-item label="邮件内容模板" prop="tenant_email_config.template">
                <el-input 
                  v-model="config.tenant_email_config.template" 
                  type="textarea" 
                  :rows="6"
                  placeholder="请输入邮件内容..."
                />
                <div class="template-variables">
                  <span class="label">插入变量:</span>
                  <el-tag v-for="v in tenantVars" :key="v.key" size="small" effect="plain" @click="insertVariable(v.key, 'tenant')" :title="v.desc">
                    {{ v.label }}
                  </el-tag>
                </div>
              </el-form-item>
            </el-card>

            <!-- 租户短信配置 -->
            <el-card v-if="config.tenant_notification_methods.includes('sms')" shadow="never" class="section-card">
              <template #header>
                <div class="card-header">
                  <span>短信通知模板</span>
                  <el-button type="primary" size="small" @click="testTenantSmsSending" :loading="testingTenantSms" plain>
                     测试发送
                  </el-button>
                </div>
              </template>
              
              <el-form-item label="模板 ID" prop="sms_config.tenant_template_id">
                <el-input v-model="config.sms_config.tenant_template_id" placeholder="腾讯云模板 ID" />
              </el-form-item>
              
              <el-form-item label="模板内容预览 (仅作参考)" prop="sms_config.tenant_template_text">
                <el-input 
                  v-model="config.sms_config.tenant_template_text"
                  type="textarea"
                  :rows="4"
                  ref="tenantSmsTextareaRef"
                  placeholder="请输入短信内容..."
                />
                <div class="template-variables">
                  <span class="label">插入变量:</span>
                  <el-tag v-for="v in tenantVars" :key="v.key" size="small" effect="plain" @click="insertSmsVariable(v.key, 'tenant')" :title="v.desc">
                    {{ v.label }}
                  </el-tag>
                </div>
              </el-form-item>
            </el-card>
          </template>
        </el-tab-pane>

        <!-- Tab 5: 房东通知详情 -->
        <el-tab-pane name="landlord_notify" label="房东通知">
          <template #label>
            <span class="custom-tabs-label">
              <el-icon><UserFilled /></el-icon>
              <span>房东通知</span>
            </span>
          </template>

          <div v-if="!config.landlord_notification_methods || config.landlord_notification_methods.length === 0" class="empty-tip">
            <el-empty description="未启用房东通知，请在基础设置中开启" :image-size="100" />
          </div>

          <template v-else>
            <!-- 房东邮件配置 -->
            <el-card v-if="config.landlord_notification_methods.includes('email')" shadow="never" class="section-card mb-3">
              <template #header>
                <div class="card-header">
                  <span>邮件通知模板</span>
                  <el-button type="primary" size="small" @click="testLandlordEmailSending" :loading="testingLandlordEmail" plain>
                     测试发送
                  </el-button>
                </div>
              </template>
              
              <el-form-item label="邮件主题" prop="landlord_email_config.subject">
                <el-input v-model="config.landlord_email_config.subject" placeholder="例如: 租户到期提醒" />
              </el-form-item>
              
              <el-form-item label="邮件内容模板" prop="landlord_email_config.template">
                <el-input 
                  v-model="config.landlord_email_config.template" 
                  type="textarea" 
                  :rows="6"
                  placeholder="请输入邮件内容..."
                />
                <div class="template-variables">
                  <span class="label">插入变量:</span>
                  <el-tag v-for="v in landlordVars" :key="v.key" size="small" effect="plain" @click="insertVariable(v.key, 'landlord')" :title="v.desc">
                    {{ v.label }}
                  </el-tag>
                </div>
              </el-form-item>
            </el-card>

            <!-- 房东短信配置 -->
            <el-card v-if="config.landlord_notification_methods.includes('sms')" shadow="never" class="section-card">
              <template #header>
                <div class="card-header">
                  <span>短信通知模板</span>
                  <el-button type="primary" size="small" @click="testLandlordSmsSending" :loading="testingLandlordSms" plain>
                     测试发送
                  </el-button>
                </div>
              </template>
              
              <el-form-item label="模板 ID" prop="sms_config.landlord_template_id">
                <el-input v-model="config.sms_config.landlord_template_id" placeholder="腾讯云模板 ID" />
              </el-form-item>
              
              <el-form-item label="模板内容预览 (仅作参考)" prop="sms_config.landlord_template_text">
                <el-input 
                  v-model="config.sms_config.landlord_template_text"
                  type="textarea"
                  :rows="4"
                  ref="landlordSmsTextareaRef"
                  placeholder="请输入短信内容..."
                />
                <div class="template-variables">
                  <span class="label">插入变量:</span>
                  <el-tag v-for="v in landlordVars" :key="v.key" size="small" effect="plain" @click="insertSmsVariable(v.key, 'landlord')" :title="v.desc">
                    {{ v.label }}
                  </el-tag>
                </div>
              </el-form-item>
            </el-card>
          </template>
        </el-tab-pane>

        <!-- Tab 6: 房东列表 -->
        <el-tab-pane name="landlord_list" label="房东列表">
          <template #label>
            <span class="custom-tabs-label">
              <el-icon><List /></el-icon>
              <span>房东列表</span>
            </span>
          </template>
          
          <el-card shadow="never" class="section-card">
            <template #header>
              <div class="card-header">
                <span>房东信息管理</span>
                <el-button type="primary" size="small" @click="addLandlord">
                  <el-icon><Plus /></el-icon> 添加房东
                </el-button>
              </div>
            </template>
            
            <el-alert title="列表中的第一个房东将作为合同模板中的默认甲方信息" type="info" show-icon class="mb-3" :closable="false" />
            
            <div v-if="mobileMode" class="landlord-mobile-list">
              <article v-for="(landlord, index) in landlordList" :key="`landlord-${index}`" class="landlord-mobile-card">
                <el-input v-model="landlord.name" placeholder="姓名" />
                <el-input v-model="landlord.phone" placeholder="电话" />
                <el-input v-model="landlord.email" placeholder="邮箱" />
                <el-button type="danger" plain @click="removeLandlord(index)">删除</el-button>
              </article>
            </div>

            <el-table v-else :data="config.landlords" border style="width: 100%">
              <el-table-column prop="name" label="姓名" width="180">
                <template #default="scope">
                  <el-input v-model="scope.row.name" placeholder="姓名" />
                </template>
              </el-table-column>
              <el-table-column prop="phone" label="电话" width="200">
                <template #default="scope">
                  <el-input v-model="scope.row.phone" placeholder="电话" />
                </template>
              </el-table-column>
              <el-table-column prop="email" label="邮箱">
                <template #default="scope">
                  <el-input v-model="scope.row.email" placeholder="邮箱" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="100" align="center">
                <template #default="scope">
                  <el-button type="danger" link @click="removeLandlord(scope.$index)">
                    <el-icon><Delete /></el-icon> 删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-tab-pane>

      </el-tabs>
    </el-form>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { notifyApi } from '../api/index.js'
import { DISPLAY_MODE_EVENT, getPreferredDisplayMode } from '../utils/displayMode'
import { 
  Refresh, 
  Message, 
  ChatDotRound, 
  User, 
  Timer, 
  Check, 
  RefreshRight,
  Plus,
  Setting,
  Connection,
  UserFilled,
  List,
  Delete
} from '@element-plus/icons-vue'

const activeTab = ref('basic')
const configForm = ref(null)
const mobileMode = ref(false)
const loading = ref(true)
const saving = ref(false)
const testingEmail = ref(false)
const testingTenantSms = ref(false)
const testingLandlordSms = ref(false)
const testingLandlordEmail = ref(false)
const testingTenantEmail = ref(false)
const tenantSmsTextareaRef = ref(null)
const landlordSmsTextareaRef = ref(null)
const error = ref('')
const tabPosition = computed(() => (mobileMode.value ? 'top' : 'left'))
const landlordList = computed(() => (Array.isArray(config.landlords) ? config.landlords : []))
const mobileTabs = [
  { name: 'basic', label: '基础设置' },
  { name: 'email_service', label: '邮件服务' },
  { name: 'sms_service', label: '短信服务' },
  { name: 'tenant_notify', label: '租户通知' },
  { name: 'landlord_notify', label: '房东通知' },
  { name: 'landlord_list', label: '房东列表' }
]

const syncDisplayMode = () => {
  mobileMode.value = getPreferredDisplayMode() === 'mobile'
}

// 变量定义，方便模板使用
const tenantVars = [
  { key: 'tenant_name', label: '{tenant_name}', desc: '租户姓名' },
  { key: 'building', label: '{building}', desc: '楼栋名称' },
  { key: 'room_no', label: '{room_no}', desc: '房间号' },
  { key: 'expiry_date', label: '{expiry_date}', desc: '到期日期' },
  { key: 'rent_amount', label: '{rent_amount}', desc: '租金金额' },
  { key: 'contact_phone', label: '{contact_phone}', desc: '联系电话' }
]

const landlordVars = [
  { key: 'landlord_name', label: '{landlord_name}', desc: '房东姓名' },
  { key: 'tenant_name', label: '{tenant_name}', desc: '租户姓名' },
  { key: 'building', label: '{building}', desc: '楼栋名称' },
  { key: 'room_no', label: '{room_no}', desc: '房间号' },
  { key: 'expiry_date', label: '{expiry_date}', desc: '到期日期' },
  { key: 'rent_amount', label: '{rent_amount}', desc: '租金金额' },
  { key: 'contact_phone', label: '{contact_phone}', desc: '联系电话' }
]

const config = reactive({
  enabled: true,
  advance_days: 7,
  lease_advance_days: 7,
  rent_advance_days: 7,
  reminder_count: 1,
  tenant_notification_methods: ['email'],
  landlord_notification_methods: ['email'],
  tenant_notification_scenes: ['lease_expiry'],
  landlord_notification_scenes: ['lease_expiry'],
  smtp_config: {
    server: '',
    port: 587,
    use_tls: true,
    username: '',
    password: ''
  },
  sms_config: {
    secret_id: '',
    secret_key: '',
    app_id: '',
    sign_name: '',
    tenant_template_id: '',
    landlord_template_id: '',
    tenant_template_text: '',
    landlord_template_text: ''
  },
  tenant_email_config: {
    sender: '',
    subject: '',
    template: '',
    recipients: []
  },
  landlord_email_config: {
    sender: '',
    subject: '',
    template: '',
    recipients: []
  },
  landlords: [],
  last_updated: ''
})

const rules = {
  lease_advance_days: [
    { required: true, message: '请设置租期提前提醒天数', trigger: 'blur' },
    { type: 'number', min: 0, message: '天数必须大于等于0', trigger: 'blur' }
  ],
  rent_advance_days: [
    { required: true, message: '请设置收租提前提醒天数', trigger: 'blur' },
    { type: 'number', min: 0, message: '天数必须大于等于0', trigger: 'blur' }
  ],
  reminder_count: [
    { required: true, message: '请设置重复提醒次数', trigger: 'blur' },
    { type: 'number', min: 0, message: '次数必须大于等于0', trigger: 'blur' }
  ]
}

// 插入变量到邮件模板
const insertVariable = (variable, type = 'tenant') => {
  const targetConfig = type === 'tenant' ? config.tenant_email_config : config.landlord_email_config
  if (!targetConfig.template) targetConfig.template = ''
  targetConfig.template += `{${variable}}`
}

// 插入变量到短信模板文本
const insertSmsVariable = (variable, type = 'tenant') => {
  const isTenant = type === 'tenant'
  const currentText = isTenant ? (config.sms_config.tenant_template_text || '') : (config.sms_config.landlord_template_text || '')
  
  const next = `${currentText}{${variable}}`
  if (isTenant) {
    config.sms_config.tenant_template_text = next
  } else {
    config.sms_config.landlord_template_text = next
  }
}

// 添加房东
const addLandlord = () => {
  config.landlords.push({
    name: '',
    phone: '',
    email: ''
  })
}

// 删除房东
const removeLandlord = (index) => {
  config.landlords.splice(index, 1)
}

// 获取配置
const fetchConfig = async () => {
  loading.value = true
  error.value = ''
  
  try {
    const { data } = await notifyApi.getConfig()
    console.log('获取到的配置数据:', data)
    
    if (typeof data === 'object' && data !== null) {
      config.enabled = data.enabled !== undefined ? data.enabled : true
      const legacyAdvanceDays = parseInt(data.advance_days)
      config.lease_advance_days = Number.isFinite(parseInt(data.lease_advance_days))
        ? parseInt(data.lease_advance_days)
        : (Number.isFinite(legacyAdvanceDays) ? legacyAdvanceDays : 7)
      config.rent_advance_days = Number.isFinite(parseInt(data.rent_advance_days))
        ? parseInt(data.rent_advance_days)
        : (Number.isFinite(legacyAdvanceDays) ? legacyAdvanceDays : 7)
      config.advance_days = config.lease_advance_days
      config.reminder_count = parseInt(data.reminder_count) || 1
      
      // 兼容旧的 notification_methods
      if (data.tenant_notification_methods) {
        config.tenant_notification_methods = data.tenant_notification_methods
      } else if (data.notification_methods) {
        config.tenant_notification_methods = data.notification_methods
      } else {
        config.tenant_notification_methods = ['email']
      }
      
      if (data.landlord_notification_methods) {
        config.landlord_notification_methods = data.landlord_notification_methods
      } else if (data.notification_methods) {
        config.landlord_notification_methods = data.notification_methods
      } else {
        config.landlord_notification_methods = ['email']
      }

      config.tenant_notification_scenes = Array.isArray(data.tenant_notification_scenes)
        ? data.tenant_notification_scenes
        : ['lease_expiry']
      config.landlord_notification_scenes = Array.isArray(data.landlord_notification_scenes)
        ? data.landlord_notification_scenes
        : ['lease_expiry']
      
      // SMTP Config
      if (data.smtp_config) {
        Object.assign(config.smtp_config, data.smtp_config)
      }
      
      // SMS Config
      if (data.sms_config) {
        Object.assign(config.sms_config, data.sms_config)
      }
      
      // Tenant Email
      if (data.tenant_email_config) {
        Object.assign(config.tenant_email_config, data.tenant_email_config)
      } else if (data.email_config) {
        Object.assign(config.tenant_email_config, data.email_config)
      }
      
      // Landlord Email
      if (data.landlord_email_config) {
        Object.assign(config.landlord_email_config, data.landlord_email_config)
      }
      
      // Landlords
      if (data.landlords && Array.isArray(data.landlords)) {
        config.landlords = [...data.landlords]
      }
      
      config.last_updated = data.last_updated || ''
    }
  } catch (err) {
    console.error('获取配置错误:', err)
    error.value = `获取配置失败: ${err.response?.data?.error || err.message}`
  } finally {
    loading.value = false
  }
}

// 保存配置
const saveConfig = async () => {
  await configForm.value.validate(async (valid) => {
    if (!valid) {
      ElMessage.error('请检查表单填写是否正确')
      return
    }
    
    saving.value = true
    try {
      config.advance_days = Number(config.lease_advance_days) || 0
      const payload = { ...config }
      const { data } = await notifyApi.updateConfig(payload)
      config.last_updated = data?.last_updated || new Date().toLocaleString()
      ElMessage.success('配置保存成功')
      await fetchConfig()
    } catch (err) {
      console.error('保存配置错误:', err)
      ElMessage.error(`保存配置失败: ${err.response?.data?.error || err.message}`)
    } finally {
      saving.value = false
    }
  })
}

// 重置表单
const resetForm = () => {
  configForm.value.resetFields()
  fetchConfig()
}

// 渲染模板内容
const renderTemplate = (template, variables) => {
  if (!template || typeof template !== 'string') return ''
  return template.replace(/\{(\w+)\}/g, (_, key) => {
    const val = variables?.[key]
    return val !== undefined && val !== null ? String(val) : ''
  })
}

// 测试邮件发送
const testEmailSending = async () => {
  testingEmail.value = true
  try {
    const payload = {
      smtp_config: { ...config.smtp_config },
      sender: config.smtp_config.username,
      subject: '测试邮件',
      recipient: config.smtp_config.username,
      content: '这是一封测试邮件，用于验证SMTP配置是否正确。',
      use_ssl: Number(config.smtp_config.port) === 465
    }

    const { data } = await notifyApi.testEmail(payload)
    if (data?.success) {
      ElMessage.success(data?.message || '测试邮件发送成功')
    } else {
      throw new Error(data?.error || '测试邮件发送失败')
    }
  } catch (err) {
    ElMessage.error(`测试邮件发送失败: ${err.response?.data?.error || err.message}`)
  } finally {
    testingEmail.value = false
  }
}

// 测试房东邮件发送
const testLandlordEmailSending = async () => {
  testingLandlordEmail.value = true
  try {
    const sender = config.smtp_config.username
    const recipient = sender // 默认发给自己测试

    const vars = {
      landlord_name: config.landlords[0]?.name || '张三',
      tenant_name: '李四',
      building: 'A栋',
      room_no: '101',
      expiry_date: new Date(Date.now() + (Number(config.lease_advance_days) || 7) * 86400000).toLocaleDateString(),
      rent_amount: '2000',
      contact_phone: config.landlords[0]?.phone || '13800000000'
    }

    const content = renderTemplate(
      config.landlord_email_config.template || '房东通知：{tenant_name}的租约将于{expiry_date}到期。',
      vars
    )

    const payload = {
      smtp_config: { ...config.smtp_config },
      sender,
      subject: config.landlord_email_config.subject || '房东邮件测试',
      recipient,
      content,
      use_ssl: Number(config.smtp_config.port) === 465
    }

    const { data } = await notifyApi.testEmail(payload)
    if (data?.success) {
      ElMessage.success('房东测试邮件发送成功')
    } else {
      throw new Error(data?.error || '失败')
    }
  } catch (err) {
    ElMessage.error(`发送失败: ${err.message}`)
  } finally {
    testingLandlordEmail.value = false
  }
}

// 测试租户邮件发送
const testTenantEmailSending = async () => {
  testingTenantEmail.value = true
  try {
    const sender = config.smtp_config.username
    const recipient = sender

    const vars = {
      tenant_name: '李四',
      building: 'A栋',
      room_no: '101',
      expiry_date: new Date(Date.now() + (Number(config.lease_advance_days) || 7) * 86400000).toLocaleDateString(),
      rent_amount: '2000',
      contact_phone: (Array.isArray(config.landlords) && config.landlords[0]?.phone) || '13800000000'
    }

    const content = renderTemplate(
      config.tenant_email_config.template || '尊敬的租户 {tenant_name}，您的租约将于 {expiry_date} 到期。',
      vars
    )

    const payload = {
      smtp_config: { ...config.smtp_config },
      sender,
      subject: config.tenant_email_config.subject || '租户邮件测试',
      recipient,
      content,
      use_ssl: Number(config.smtp_config.port) === 465
    }

    const { data } = await notifyApi.testEmail(payload)
    if (data?.success) {
      ElMessage.success('租户测试邮件发送成功')
    } else {
      throw new Error(data?.error || '失败')
    }
  } catch (err) {
    ElMessage.error(`发送失败: ${err.message}`)
  } finally {
    testingTenantEmail.value = false
  }
}

// 测试租户短信
const testTenantSmsSending = async () => {
  testingTenantSms.value = true
  try {
    const payload = {
      sms_config: { ...config.sms_config },
      target: 'tenant',
      phone_number: '13800138000', // 测试号码，后端可能会拦截或报错，这里仅作演示
      template_params: {
        tenant_name: '李四',
        building: 'A栋',
        room_no: '101',
        expiry_date: new Date(Date.now() + (Number(config.lease_advance_days) || 7) * 86400000).toLocaleDateString()
      }
    }
    const { data } = await notifyApi.testSms(payload)
    if (data?.success) {
      ElMessage.success('租户短信测试成功')
    } else {
      throw new Error(data?.error || '失败')
    }
  } catch (err) {
    ElMessage.error(`测试失败: ${err.message}`)
  } finally {
    testingTenantSms.value = false
  }
}

// 测试房东短信
const testLandlordSmsSending = async () => {
  testingLandlordSms.value = true
  try {
    const defaultPhone = (Array.isArray(config.landlords) && config.landlords[0]?.phone) || '13800000000'
    const payload = {
      sms_config: { ...config.sms_config },
      target: 'landlord',
      phone_number: defaultPhone,
      template_params: {
        landlord_name: config.landlords[0]?.name || '张三',
        tenant_name: '李四',
        building: 'A栋',
        room_no: '101',
        expiry_date: new Date(Date.now() + (Number(config.lease_advance_days) || 7) * 86400000).toLocaleDateString(),
        rent_amount: '2000'
      }
    }
    const { data } = await notifyApi.testSms(payload)
    if (data?.success) {
      ElMessage.success('房东短信测试成功')
    } else {
      throw new Error(data?.error || '失败')
    }
  } catch (err) {
    ElMessage.error(`测试失败: ${err.message}`)
  } finally {
    testingLandlordSms.value = false
  }
}

onMounted(() => {
  syncDisplayMode()
  window.addEventListener(DISPLAY_MODE_EVENT, syncDisplayMode)
  fetchConfig()
})

onBeforeUnmount(() => {
  window.removeEventListener(DISPLAY_MODE_EVENT, syncDisplayMode)
})
</script>

<style scoped>
.notification-config {
  padding: 20px;
  height: calc(100vh - 100px);
  display: flex;
  flex-direction: column;
  background: var(--card-bg);
  border: 1px solid var(--surface-border);
  border-radius: 18px;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
}

.notification-config--mobile {
  padding: 16px;
  height: auto;
  min-height: calc(100vh - 100px);
}

.page-header {
  display: flex;
  align-items: center;
  margin-bottom: 18px;
  flex-shrink: 0;
}
.page-header h2 {
  margin: 0;
  color: #409EFF;
}
.header-operations {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.landlord-mobile-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.landlord-mobile-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border-radius: 14px;
  border: 1px solid var(--surface-border);
  background: var(--surface-muted);
}

.header-action-btn {
  margin-left: 0 !important;
}

.last-updated {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 0.85rem;
  color: #909399;
}

.config-form {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.mobile-tab-strip {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding: 0 2px 12px;
  margin-bottom: 2px;
  scrollbar-width: none;
}

.mobile-tab-strip::-webkit-scrollbar {
  display: none;
}

.mobile-tab-chip {
  flex: 0 0 auto;
  min-width: max-content;
  border: 1px solid var(--surface-border);
  background: var(--surface-muted);
  color: var(--text-regular);
  border-radius: 999px;
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 600;
  line-height: 1;
  transition: all 0.2s ease;
}

.mobile-tab-chip--active {
  background: var(--el-color-primary);
  border-color: var(--el-color-primary);
  color: #fff;
  box-shadow: 0 10px 22px rgba(37, 99, 235, 0.2);
}

.config-tabs {
  flex: 1;
  height: 100%;
  background-color: var(--card-bg);
  border-radius: 16px;
  border: 1px solid var(--surface-border);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
  display: flex;
  overflow: hidden;
}

:deep(.el-tabs__header) {
  background-color: var(--surface-muted);
  margin-right: 0 !important;
  border-right: 1px solid var(--surface-border);
  width: 208px;
}

:deep(.el-tabs__nav-wrap) {
  padding: 16px 0;
}

:deep(.el-tabs__nav-wrap::after) {
  display: none;
}

:deep(.el-tabs__active-bar) {
  display: none;
}

:deep(.el-tabs__item) {
  height: 50px;
  line-height: 50px;
  font-size: 14px;
  color: var(--text-regular);
  text-align: left;
  padding: 0 20px !important;
  justify-content: flex-start;
  transition: background-color 0.3s, color 0.3s;
  border-left: 3px solid transparent;
  margin-bottom: 0;
  border-bottom: 1px solid var(--surface-border);
}

:deep(.el-tabs__item:hover) {
  color: var(--el-color-primary);
  background-color: rgba(37, 99, 235, 0.06);
}

:deep(.el-tabs__item.is-active) {
  color: var(--el-color-primary);
  background-color: rgba(37, 99, 235, 0.12);
  border-left-color: var(--el-color-primary);
  font-weight: 600;
  border-right: none;
}

:deep(.el-tabs__content) {
  flex: 1;
  padding: 24px;
  height: 100%;
  overflow-y: auto;
  background-color: var(--card-bg);
}

.custom-tabs-label {
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-card {
  margin-bottom: 20px;
  border-radius: 14px;
  border: 1px solid var(--surface-border);
}

:deep(.section-card .el-card__header) {
  background: var(--surface-muted);
}

:deep(.section-card .el-card__body) {
  background: var(--card-bg);
}

:deep(.config-form .el-form-item__label) {
  color: var(--text-main);
  font-weight: 600;
}

:deep(.config-form .el-input__wrapper),
:deep(.config-form .el-textarea__inner),
:deep(.config-form .el-input-number),
:deep(.config-form .el-select__wrapper) {
  background: var(--surface-muted);
  border-color: var(--surface-border);
}

:deep(.config-form .el-input__wrapper:hover),
:deep(.config-form .el-textarea__inner:hover),
:deep(.config-form .el-select__wrapper:hover) {
  border-color: var(--el-color-primary-light-5);
}

:deep(.config-form .el-input.is-focus .el-input__wrapper),
:deep(.config-form .el-textarea.is-focus .el-textarea__inner),
:deep(.config-form .el-select.is-focus .el-select__wrapper) {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.16);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: bold;
}

.form-hint {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin-top: 5px;
}

.mr-1 {
  margin-right: 4px;
}
.mt-3 {
  margin-top: 15px;
}
.mb-3 {
  margin-bottom: 15px;
}

.template-variables {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  background-color: var(--el-fill-color-light, #f5f7fa);
  padding: 10px;
  border-radius: 4px;
}

.template-variables .label {
  font-size: 12px;
  color: var(--text-regular);
  margin-right: 5px;
}

.template-variables .el-tag {
  cursor: pointer;
  user-select: none;
}

.template-variables .el-tag:hover {
  opacity: 0.8;
}

.empty-tip {
  padding: 40px;
  text-align: center;
}

@media (max-width: 768px) {
  .page-header {
    align-items: stretch;
  }

  .header-operations {
    width: 100%;
  }

  .header-operations :deep(.el-button) {
    flex: 1 1 calc(50% - 5px);
  }

  :deep(.el-tabs__header) {
    display: none;
  }

  :deep(.el-tabs__nav-wrap) {
    padding: 0 10px;
  }

  :deep(.el-tabs__item) {
    border-left: none;
    border-bottom: 3px solid transparent;
    justify-content: center;
    min-width: 112px;
  }

  :deep(.el-tabs__item.is-active) {
    border-bottom-color: var(--el-color-primary);
  }

  :deep(.el-tabs__content) {
    padding: 16px;
  }

  .card-header {
    align-items: flex-start;
    flex-direction: column;
    gap: 10px;
  }
}
</style>
