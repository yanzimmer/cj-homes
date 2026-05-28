<template>
  <div class="home-container page-container">
    <div class="home-hero">
      <div>
        <h2 class="hero-title">运营总览</h2>
        <p class="hero-subtitle">实时查看房间、租户、维修、OCR 和到期预警数据</p>
      </div>
      <el-tag effect="dark" class="hero-date">{{ todayLabel }}</el-tag>
    </div>

    <div class="alert-panel">
      <div class="section-header">
        <div class="header-left">
          <el-icon class="warning-icon"><Warning /></el-icon>
          <h3 class="section-title">即将到期预警</h3>
          <el-tag type="danger" size="small" v-if="stats.expiring.count > 0">{{ stats.expiring.count }} 人即将到期</el-tag>
        </div>
        <div class="header-right">
          <span class="advance-days-info">租期提前提醒：{{ leaseAdvanceDays }} 天</span>
        </div>
      </div>

      <div v-if="mobileMode" class="expiring-mobile-list" v-loading="loading.expiring">
        <div v-if="expiringMobileList.length === 0" class="expiring-mobile-empty">
          <el-empty description="暂无即将到期的租户" :image-size="42" />
        </div>
        <article
          v-for="item in expiringMobileList"
          :key="`${item.room_no}-${item.name}-${item.check_out_date}`"
          class="expiring-mobile-card"
          :class="{
            'expiring-mobile-card--urgent': item.days_remaining <= 3,
            'expiring-mobile-card--expired': item.days_remaining < 0
          }"
        >
          <div class="expiring-mobile-card__top">
            <div>
              <div class="expiring-mobile-card__name">{{ item.name || '未登记租户' }}</div>
              <div class="expiring-mobile-card__meta">
                <el-tag size="small" effect="plain">{{ item.room_no || '-' }}</el-tag>
                <span>{{ item.phone || '未登记电话' }}</span>
              </div>
            </div>
            <div class="expiring-mobile-card__status">
              <el-tag v-if="item.isPreview" size="small" type="info" effect="plain">示例</el-tag>
              <el-tag :type="getRemainingDaysTagType(item.days_remaining)">
                {{ getRemainingDaysText(item.days_remaining) }}
              </el-tag>
            </div>
          </div>
          <div class="expiring-mobile-card__bottom">
            <span>到期日期：{{ item.check_out_date || '-' }}</span>
            <el-tag type="success" size="small">在住</el-tag>
          </div>
        </article>
      </div>

      <el-table 
        v-else
        v-loading="loading.expiring" 
        :data="stats.expiring.list" 
        style="width: 100%" 
        :row-class-name="tableRowClassName"
        empty-text="暂无即将到期的租户"
      >
        <el-table-column prop="name" label="租户姓名" width="120">
          <template #default="scope">
            <span class="tenant-name">{{ scope.row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="room_no" label="房间号" width="120">
          <template #default="scope">
            <el-tag size="small" effect="plain">{{ scope.row.room_no }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="phone" label="联系电话" width="150" />
        <el-table-column prop="check_out_date" label="到期日期" width="150" sortable />
        <el-table-column label="剩余天数" width="150" sortable :sort-method="(a, b) => a.days_remaining - b.days_remaining">
          <template #default="scope">
            <el-tag :type="getRemainingDaysTagType(scope.row.days_remaining)">
              {{ getRemainingDaysText(scope.row.days_remaining) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" min-width="120">
          <template #default>
            <el-tag type="success" size="small">在住</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="alert-panel">
      <div class="section-header">
        <div class="header-left">
          <el-icon class="warning-icon warning-icon--rent"><Coin /></el-icon>
          <h3 class="section-title">收租提醒</h3>
          <el-tag type="danger" size="small" v-if="stats.rentReminder.overdueCount > 0">
            {{ stats.rentReminder.overdueCount }} 条已逾期
          </el-tag>
          <el-tag type="warning" size="small" v-if="stats.rentReminder.upcomingCount > 0">
            {{ stats.rentReminder.upcomingCount }} 条即将到期
          </el-tag>
        </div>
        <div class="header-right">
          <span class="advance-days-info">收租提前提醒：{{ rentAdvanceDays }} 天</span>
        </div>
      </div>

      <div v-if="mobileMode" class="rent-reminder-mobile-list" v-loading="loading.rentReminder">
        <div v-if="stats.rentReminder.list.length === 0" class="rent-reminder-mobile-empty">
          <el-empty description="暂无需要提醒的收租记录" :image-size="42" />
        </div>
        <article
          v-for="item in stats.rentReminder.list"
          :key="item.id"
          class="rent-reminder-mobile-card"
          :class="{
            'rent-reminder-mobile-card--overdue': item.reminderType === 'overdue',
            'rent-reminder-mobile-card--upcoming': item.reminderType !== 'overdue'
          }"
        >
          <div class="rent-reminder-mobile-card__top">
            <div>
              <div class="rent-reminder-mobile-card__name">{{ item.tenantName || '未登记租户' }}</div>
              <div class="rent-reminder-mobile-card__meta">
                <el-tag size="small" effect="plain">{{ item.roomDisplay || '-' }}</el-tag>
                <span>{{ item.status || '未交' }}</span>
              </div>
            </div>
            <el-tag :type="getRentReminderTagType(item)">
              {{ getRentReminderText(item) }}
            </el-tag>
          </div>
          <div class="rent-reminder-mobile-card__bottom">
            <span>应缴日期：{{ item.dueDate || '-' }}</span>
            <strong>待收 ¥{{ Number(item.outstandingAmount || 0).toFixed(2) }}</strong>
          </div>
        </article>
      </div>

      <el-table
        v-else
        v-loading="loading.rentReminder"
        :data="stats.rentReminder.list"
        style="width: 100%"
        :row-class-name="rentReminderRowClassName"
        empty-text="暂无需要提醒的收租记录"
      >
        <el-table-column prop="tenantName" label="租户" min-width="120" />
        <el-table-column prop="roomDisplay" label="房间" width="120">
          <template #default="scope">
            <el-tag size="small" effect="plain">{{ scope.row.roomDisplay || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="账期" min-width="220">
          <template #default="scope">
            {{ scope.row.periodStart || '-' }} 至 {{ scope.row.periodEnd || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="dueDate" label="应缴日期" width="130" sortable />
        <el-table-column label="待收金额" width="130">
          <template #default="scope">
            <span class="rent-reminder-amount">¥{{ Number(scope.row.outstandingAmount || 0).toFixed(2) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="缴费状态" width="120" />
        <el-table-column label="提醒状态" width="130">
          <template #default="scope">
            <el-tag :type="getRentReminderTagType(scope.row)">
              {{ getRentReminderText(scope.row) }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="alert-panel">
      <div class="section-header">
        <div class="header-left">
          <el-icon class="warning-icon warning-icon--primary"><House /></el-icon>
          <h3 class="section-title">待确认入住提交</h3>
          <el-tag type="warning" size="small" v-if="stats.selfCheckin.pendingCount > 0">
            {{ stats.selfCheckin.pendingCount }} 条待确认
          </el-tag>
        </div>
      </div>

      <div v-if="mobileMode" class="submission-mobile-list" v-loading="loading.selfCheckin">
        <div v-if="stats.selfCheckin.list.length === 0" class="submission-mobile-empty">
          <el-empty description="暂无待确认入住提交" :image-size="42" />
        </div>
        <article
          v-for="item in stats.selfCheckin.list"
          v-else
          :key="item.id"
          class="submission-mobile-card"
        >
          <div class="submission-mobile-card__top">
            <div>
              <div class="submission-mobile-card__name">{{ item.name || '未填写姓名' }}</div>
              <div class="submission-mobile-card__meta">
                <el-tag size="small" effect="plain">{{ item.roomNo || '-' }}</el-tag>
                <span>{{ item.phone || '未登记电话' }}</span>
              </div>
            </div>
            <el-tag type="warning">待确认</el-tag>
          </div>
          <div class="submission-mobile-card__bottom">
            <span>入住：{{ item.checkInDate || '-' }}</span>
            <span>提交：{{ item.submittedAt || '-' }}</span>
          </div>
        </article>
      </div>

      <el-table
        v-else
        v-loading="loading.selfCheckin"
        :data="stats.selfCheckin.list"
        style="width: 100%"
        empty-text="暂无待确认入住提交"
      >
        <el-table-column prop="roomNo" label="房间号" width="120">
          <template #default="scope">
            <el-tag size="small" effect="plain">{{ scope.row.roomNo || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="姓名" min-width="120" />
        <el-table-column prop="phone" label="联系电话" min-width="140" />
        <el-table-column prop="checkInDate" label="入住日期" width="120" />
        <el-table-column prop="checkOutDate" label="退房日期" width="120" />
        <el-table-column prop="submittedAt" label="提交时间" min-width="170" />
        <el-table-column label="状态" width="100">
          <template #default>
            <el-tag type="warning">待确认</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="overview-grid">
      <div class="stat-card-wrapper overview-card">
          <div class="stat-header">
            <div class="icon-box icon-primary">
              <el-icon><House /></el-icon>
            </div>
            <div class="stat-title">房间统计</div>
          </div>
          <div v-loading="loading.rooms" class="stat-body">
            <div class="main-value">{{ stats.rooms.total }} <span class="unit">间</span></div>
            <div class="sub-stats">
              <div class="sub-item">
                <span class="label">已入住</span>
                <span class="value success">{{ stats.rooms.occupied }}</span>
              </div>
              <div class="sub-item">
                <span class="label">空闲</span>
                <span class="value warning">{{ stats.rooms.vacant }}</span>
              </div>
            </div>
            <div class="progress-area">
              <div class="progress-label">
                <span>入住率</span>
                <span>{{ stats.rooms.occupancyRate }}%</span>
              </div>
              <el-progress 
                :percentage="stats.rooms.occupancyRate" 
                :show-text="false"
                :color="getProgressColor(stats.rooms.occupancyRate)"
                :stroke-width="8"
              />
            </div>
          </div>
      </div>

      <!-- 租户统计卡片 -->
      <div class="stat-card-wrapper overview-card">
          <div class="stat-header">
            <div class="icon-box icon-success">
              <el-icon><User /></el-icon>
            </div>
            <div class="stat-title">租户统计</div>
          </div>
          <div v-loading="loading.tenants" class="stat-body">
            <div class="main-value">{{ stats.tenants.total }} <span class="unit">人</span></div>
            <div class="sub-stats">
              <div class="sub-item">
                <span class="label">在住</span>
                <span class="value success">{{ stats.tenants.active }}</span>
              </div>
              <div class="sub-item">
                <span class="label">已退租</span>
                <span class="value info">{{ stats.tenants.inactive }}</span>
              </div>
            </div>
            <div class="progress-area">
              <div class="progress-label">
                <span>平均租期</span>
                <span>{{ stats.tenants.averageLeaseDays || 0 }} 天</span>
              </div>
              <el-progress 
                :percentage="stats.tenants.activeRate" 
                :show-text="false"
                :color="getProgressColor(stats.tenants.activeRate)"
                :stroke-width="8"
              />
            </div>
          </div>
      </div>

      <!-- 维修记录统计卡片 -->
      <div class="stat-card-wrapper overview-card">
          <div class="stat-header">
            <div class="icon-box icon-warning">
              <el-icon><Tools /></el-icon>
            </div>
            <div class="stat-title">维修统计</div>
          </div>
          <div v-loading="loading.repairs" class="stat-body">
            <div class="main-value">{{ stats.repairs.total }} <span class="unit">次</span></div>
            <div class="sub-stats">
              <div class="sub-item">
                <span class="label">待处理</span>
                <span class="value danger">{{ stats.repairs.pending }}</span>
              </div>
              <div class="sub-item">
                <span class="label">总金额</span>
                <span class="value primary">¥{{ Number(stats.repairs.totalAmount || 0).toFixed(2) }}</span>
              </div>
            </div>
            <div class="progress-area">
              <div class="progress-label">
                <span>处理率</span>
                <span>{{ stats.repairs.completionRate }}%</span>
              </div>
              <el-progress 
                :percentage="stats.repairs.completionRate" 
                :show-text="false"
                status="success"
                :stroke-width="8"
              />
            </div>
            <div class="monthly-stats">
              <div class="monthly-title">按月统计</div>
              <div v-if="stats.repairs.monthly.length" class="monthly-list">
                <div v-for="item in stats.repairs.monthly.slice(0, 4)" :key="item.month" class="monthly-row">
                  <span class="month">{{ formatMonthLabel(item.month) }}</span>
                  <span>{{ item.total }} 次</span>
                  <strong>¥{{ Number(item.totalAmount || 0).toFixed(2) }}</strong>
                </div>
              </div>
              <el-empty v-else description="暂无月度数据" :image-size="42" />
            </div>
          </div>
      </div>

      <div class="stat-card-wrapper overview-card">
          <div class="stat-header">
            <div class="icon-box icon-procurement">
              <el-icon><Tools /></el-icon>
            </div>
            <div class="stat-title">采购统计</div>
          </div>
          <div v-loading="loading.procurements" class="stat-body">
            <div class="main-value">¥{{ Number(stats.procurements.totalAmount || 0).toFixed(2) }}</div>
            <div class="sub-stats">
              <div class="sub-item">
                <span class="label">记录数</span>
                <span class="value info">{{ stats.procurements.total }}</span>
              </div>
              <div class="sub-item">
                <span class="label">总金额</span>
                <span class="value primary">¥{{ Number(stats.procurements.totalAmount || 0).toFixed(2) }}</span>
              </div>
            </div>
            <div class="progress-area">
              <div class="progress-label">
                <span>采购总金额</span>
                <span>累计支出</span>
              </div>
              <div class="ocr-status-line">用于展示采购记录累计金额</div>
            </div>
            <div class="monthly-stats">
              <div class="monthly-title">按月统计</div>
              <div v-if="stats.procurements.monthly.length" class="monthly-list">
                <div v-for="item in stats.procurements.monthly.slice(0, 4)" :key="item.month" class="monthly-row">
                  <span class="month">{{ formatMonthLabel(item.month) }}</span>
                  <span>{{ item.total }} 条</span>
                  <strong>¥{{ Number(item.totalAmount || 0).toFixed(2) }}</strong>
                </div>
              </div>
              <el-empty v-else description="暂无月度数据" :image-size="42" />
            </div>
          </div>
      </div>

      <div class="stat-card-wrapper overview-card">
          <div class="stat-header">
            <div class="icon-box icon-utility">
              <el-icon><Coin /></el-icon>
            </div>
            <div class="stat-title">水电费</div>
          </div>
          <div v-loading="loading.utilityBills" class="stat-body">
            <div class="main-value">¥{{ Number(stats.utilityBills.totalAmount || 0).toFixed(2) }}</div>
            <div class="sub-stats">
              <div class="sub-item">
                <span class="label">电费</span>
                <span class="value warning">¥{{ Number(stats.utilityBills.electricityTotal || 0).toFixed(2) }}</span>
              </div>
              <div class="sub-item">
                <span class="label">水费</span>
                <span class="value primary">¥{{ Number(stats.utilityBills.waterTotal || 0).toFixed(2) }}</span>
              </div>
            </div>
            <div class="progress-area">
              <div class="progress-label">
                <span>统计年份</span>
                <span>{{ stats.utilityBills.year || new Date().getFullYear() }} 年</span>
              </div>
              <div class="ocr-status-line">共 {{ stats.utilityBills.recordCount || 0 }} 条月度账单记录</div>
            </div>
            <div class="monthly-stats">
              <div class="monthly-title">按月统计</div>
              <div v-if="stats.utilityBills.monthly.length" class="monthly-list">
                <div v-for="item in stats.utilityBills.monthly.slice(0, 4)" :key="item.month" class="monthly-row">
                  <span class="month">{{ formatMonthLabel(item.month) }}</span>
                  <span>{{ Number(item.electricityAmount || 0).toFixed(2) }} / {{ Number(item.waterAmount || 0).toFixed(2) }}</span>
                  <strong>¥{{ Number(item.totalAmount || 0).toFixed(2) }}</strong>
                </div>
              </div>
              <el-empty v-else description="暂无月度数据" :image-size="42" />
            </div>
          </div>
      </div>

      <div class="stat-card-wrapper overview-card">
          <div class="stat-header">
            <div class="icon-box icon-rent-ledger">
              <el-icon><Coin /></el-icon>
            </div>
            <div class="stat-title">收租台账</div>
          </div>
          <div v-loading="loading.rentLedger" class="stat-body">
            <div class="main-value">¥{{ Number(stats.rentLedger.dueTotal || 0).toFixed(2) }}</div>
            <div class="sub-stats">
              <div class="sub-item">
                <span class="label">已收</span>
                <span class="value success">¥{{ Number(stats.rentLedger.actualTotal || 0).toFixed(2) }}</span>
              </div>
              <div class="sub-item">
                <span class="label">待收</span>
                <span class="value danger">¥{{ Number(stats.rentLedger.outstandingTotal || 0).toFixed(2) }}</span>
              </div>
            </div>
            <div class="progress-area">
              <div class="progress-label">
                <span>已交 / 总期次</span>
                <span>{{ stats.rentLedger.paidPeriods || 0 }} / {{ stats.rentLedger.totalPeriods || 0 }}</span>
              </div>
              <el-progress
                :percentage="stats.rentLedger.collectionRate || 0"
                :show-text="false"
                :color="getProgressColor(stats.rentLedger.collectionRate || 0)"
                :stroke-width="8"
              />
            </div>
            <div class="monthly-stats">
              <div class="monthly-title">按月统计</div>
              <div v-if="stats.rentLedger.monthly.length" class="monthly-list">
                <div v-for="item in stats.rentLedger.monthly.slice(0, 4)" :key="item.month" class="monthly-row">
                  <span class="month">{{ formatMonthLabel(item.month) }}</span>
                  <span>{{ item.paidPeriods || 0 }} / {{ item.totalPeriods || 0 }} 期</span>
                  <strong>¥{{ Number(item.outstandingAmount || 0).toFixed(2) }}</strong>
                </div>
              </div>
              <el-empty v-else description="暂无月度数据" :image-size="42" />
            </div>
          </div>
      </div>

      <div class="stat-card-wrapper overview-card">
          <div class="stat-header">
            <div class="icon-box icon-info">
              <el-icon><InfoFilled /></el-icon>
            </div>
            <div class="stat-title">OCR 识别统计</div>
          </div>
          <div v-loading="loading.ocr" class="stat-body">
            <div class="main-value">{{ stats.ocr.usedCount }} <span class="unit">次</span></div>
            <div class="sub-stats">
              <div class="sub-item">
                <span class="label">剩余</span>
                <span class="value info">{{ stats.ocr.configuredTotal > 0 ? (stats.ocr.remainingCount ?? 0) : '不限' }}</span>
              </div>
              <div class="sub-item">
                <span class="label">个人设置总次数</span>
                <span class="value primary">{{ stats.ocr.configuredTotal > 0 ? stats.ocr.configuredTotal : '不限' }}</span>
              </div>
            </div>
            <div class="progress-area">
              <div class="progress-label">
                <span>阿里云默认免费额度</span>
                <span>{{ stats.ocr.aliyunFreeQuota }} 次/月</span>
              </div>
              <div class="ocr-status-line">{{ stats.ocr.reason || (stats.ocr.enabled ? '当前可识别' : '当前不可识别') }}</div>
            </div>
          </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, onBeforeUnmount } from 'vue'
import { dashboardApi } from '../api'
import { ElMessage, ElNotification } from 'element-plus'
import { House, User, Tools, InfoFilled, Warning, Coin } from '@element-plus/icons-vue'
import { DISPLAY_MODE_EVENT, getPreferredDisplayMode } from '../utils/displayMode'

// 加载状态
const loading = reactive({
  rooms: true,
  tenants: true,
  repairs: true,
  expiring: true,
  rentReminder: true,
  ocr: true,
  procurements: true,
  utilityBills: true,
  rentLedger: true,
  selfCheckin: true
})

// 预警天数配置
const leaseAdvanceDays = ref(7)
const rentAdvanceDays = ref(7)
const mobileMode = ref(false)
const latestSeenSubmissionId = ref(null)
let dashboardRefreshTimer = null
const todayLabel = computed(() => {
  const now = new Date()
  return now.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
})

const syncDisplayMode = () => {
  mobileMode.value = getPreferredDisplayMode() === 'mobile'
}

const expiringMobileList = computed(() => {
  if (stats.expiring.list.length > 0) return stats.expiring.list
  if (!mobileMode.value || !import.meta.env.DEV) return []
  return [{
    name: '示例租户',
    room_no: 'A-302',
    phone: '138****5678',
    check_out_date: '2026-05-27',
    days_remaining: 3,
    isPreview: true,
  }]
})

// 统计数据
const stats = reactive({
  rooms: {
    total: 0,
    occupied: 0,
    vacant: 0,
    occupancyRate: 0
  },
  tenants: {
    total: 0,
    active: 0,
    inactive: 0,
    activeRate: 0,
    averageLeaseDays: 0
  },
  repairs: {
    total: 0,
    pending: 0,
    inProgress: 0,
    completed: 0,
    totalAmount: 0,
    completionRate: 0,
    monthly: []
  },
  procurements: {
    total: 0,
    totalAmount: 0,
    monthly: []
  },
  selfCheckin: {
    pendingCount: 0,
    latestSubmissionId: null,
    list: []
  },
  rentLedger: {
    year: new Date().getFullYear(),
    recordCount: 0,
    totalPeriods: 0,
    paidPeriods: 0,
    partialPeriods: 0,
    unpaidPeriods: 0,
    dueTotal: 0,
    actualTotal: 0,
    outstandingTotal: 0,
    collectionRate: 0,
    monthly: []
  },
  rentReminder: {
    count: 0,
    overdueCount: 0,
    upcomingCount: 0,
    list: []
  },
  utilityBills: {
    year: new Date().getFullYear(),
    totalAmount: 0,
    electricityTotal: 0,
    waterTotal: 0,
    recordCount: 0,
    monthly: []
  },
  expiring: {
    count: 0,
    list: []
  },
  ocr: {
    usedCount: 0,
    remainingCount: 0,
    configuredTotal: 0,
    aliyunFreeQuota: 200,
    enabled: false,
    configured: false,
    reason: '',
  }
})

// 格式化百分比
const percentageFormat = (percentage) => {
  return percentage.toFixed(0) + '%'
}

// 根据百分比获取进度条颜色
const getProgressColor = (percentage) => {
  return '#409EFF' // 统一使用蓝色
}

const formatMonthLabel = (month) => {
  const text = String(month || '')
  const match = text.match(/^(\d{4})-(\d{2})/)
  if (!match) return text || '-'
  return `${match[1]}年${Number(match[2])}月`
}

// 表格行样式
const tableRowClassName = ({ row }) => {
  if (row.days_remaining < 0) {
    return 'expired-row'
  } else if (row.days_remaining <= 3) {
    return 'urgent-row'
  }
  return 'warning-row'
}

const rentReminderRowClassName = ({ row }) => {
  if (row.reminderType === 'overdue') {
    return 'rent-overdue-row'
  }
  return 'rent-upcoming-row'
}

// 获取剩余天数标签类型
const getRemainingDaysTagType = (days) => {
  if (days < 0) return 'danger'
  if (days <= 3) return 'warning'
  return 'info'
}

// 获取剩余天数文本
const getRemainingDaysText = (days) => {
  if (days < 0) return `已过期 ${Math.abs(days)} 天`
  if (days === 0) return '今天到期'
  return `剩余 ${days} 天`
}

const getRentReminderTagType = (item) => {
  return item?.reminderType === 'overdue' ? 'danger' : 'warning'
}

const getRentReminderText = (item) => {
  const days = Number(item?.daysUntilDue || 0)
  if (days < 0) return `逾期 ${Math.abs(days)} 天`
  if (days === 0) return '今天应缴'
  return `${days} 天后应缴`
}

const syncLoadingState = (value) => {
  loading.rooms = value
  loading.tenants = value
  loading.repairs = value
  loading.expiring = value
  loading.rentReminder = value
  loading.ocr = value
  loading.procurements = value
  loading.rentLedger = value
  loading.utilityBills = value
  loading.selfCheckin = value
}

const fetchDashboardStats = async ({ silent = false } = {}) => {
  if (!silent) {
    syncLoadingState(true)
  }
  try {
    const { data } = await dashboardApi.getStats()
    leaseAdvanceDays.value = Number(data?.lease_advance_days ?? data?.advance_days ?? 7)
    rentAdvanceDays.value = Number(data?.rent_advance_days ?? data?.advance_days ?? 7)

    Object.assign(stats.rooms, data?.rooms || {})
    Object.assign(stats.tenants, data?.tenants || {})
    Object.assign(stats.repairs, data?.repairs || {})
    Object.assign(stats.procurements, data?.procurements || {})
    Object.assign(stats.selfCheckin, data?.selfCheckin || { pendingCount: 0, latestSubmissionId: null, list: [] })
    Object.assign(stats.rentLedger, data?.rentLedger || {})
    Object.assign(stats.rentReminder, data?.rentReminder || { count: 0, overdueCount: 0, upcomingCount: 0, list: [] })
    Object.assign(stats.utilityBills, data?.utilityBills || {})
    Object.assign(stats.expiring, data?.expiring || { count: 0, list: [] })
    Object.assign(stats.ocr, data?.ocr || {})

    const latestSubmissionId = data?.selfCheckin?.latestSubmissionId ?? null
    if (latestSeenSubmissionId.value === null) {
      latestSeenSubmissionId.value = latestSubmissionId
    } else if (
      latestSubmissionId &&
      latestSeenSubmissionId.value &&
      Number(latestSubmissionId) > Number(latestSeenSubmissionId.value)
    ) {
      latestSeenSubmissionId.value = latestSubmissionId
      ElNotification({
        title: '有新的待确认入住提交',
        message: `当前共有 ${Number(data?.selfCheckin?.pendingCount || 0)} 条待确认记录，请及时处理。`,
        type: 'warning',
        duration: 4500,
      })
    } else if (latestSubmissionId && !latestSeenSubmissionId.value) {
      latestSeenSubmissionId.value = latestSubmissionId
    }
  } catch (error) {
    console.error('获取首页统计失败:', error)
    if (!silent) {
      ElMessage.error('获取首页统计失败')
    }
  } finally {
    if (!silent) {
      syncLoadingState(false)
    }
  }
}

// 页面加载时获取所有统计数据
onMounted(() => {
  syncDisplayMode()
  window.addEventListener(DISPLAY_MODE_EVENT, syncDisplayMode)
  fetchDashboardStats()
  dashboardRefreshTimer = window.setInterval(() => {
    fetchDashboardStats({ silent: true })
  }, 60000)
})

onBeforeUnmount(() => {
  window.removeEventListener(DISPLAY_MODE_EVENT, syncDisplayMode)
  if (dashboardRefreshTimer) {
    window.clearInterval(dashboardRefreshTimer)
  }
})
</script>

<style scoped>
.page-header {
  margin-bottom: 24px;
}
.page-header h2 {
  margin: 0 0 8px 0;
  font-size: 24px;
  color: var(--text-main);
  font-weight: 600;
}
.subtitle {
  color: var(--text-secondary);
  font-size: 14px;
}

.home-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.home-hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 20px;
  border-radius: 16px;
  background: linear-gradient(135deg, #2563eb 0%, #14b8a6 100%);
  color: #ffffff;
  box-shadow: 0 16px 36px rgba(37, 99, 235, 0.22);
}

.hero-title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
}

.hero-subtitle {
  margin: 6px 0 0;
  font-size: 14px;
  opacity: 0.92;
}

.hero-date {
  border: none;
  background: rgba(255, 255, 255, 0.16);
  color: #ffffff;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  column-gap: 16px;
  row-gap: 16px;
}

.overview-card {
  margin: 0;
  background: linear-gradient(180deg, var(--card-bg) 0%, var(--surface-muted) 100%);
  border: 1px solid var(--surface-border);
  border-radius: 16px;
  box-shadow: 0 14px 30px rgba(15, 23, 42, 0.08);
  padding: 20px;
}

.alert-panel {
  margin: 0;
  background: var(--card-bg);
  border: 1px solid var(--surface-border);
  border-radius: 16px;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
  padding: 20px;
  position: relative;
  z-index: 0;
}

.expiring-mobile-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.expiring-mobile-empty {
  padding: 8px 0;
}

.submission-mobile-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.submission-mobile-empty {
  padding: 8px 0;
}

.rent-reminder-mobile-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.rent-reminder-mobile-empty {
  padding: 8px 0;
}

.expiring-mobile-card {
  padding: 14px;
  border-radius: 14px;
  border: 1px solid var(--surface-border);
  background: var(--card-bg);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
}

.expiring-mobile-card--urgent {
  border-color: rgba(230, 162, 60, 0.45);
}

.expiring-mobile-card--expired {
  border-color: rgba(245, 108, 108, 0.45);
}

.expiring-mobile-card__top,
.expiring-mobile-card__bottom {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.expiring-mobile-card__status {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.expiring-mobile-card__bottom {
  margin-top: 10px;
  align-items: center;
  font-size: 12px;
  color: var(--text-secondary);
}

.expiring-mobile-card__name {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-main);
}

.expiring-mobile-card__meta {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--text-secondary);
}

.rent-reminder-mobile-card {
  padding: 14px;
  border-radius: 14px;
  border: 1px solid var(--surface-border);
  background: var(--card-bg);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
}

.rent-reminder-mobile-card--overdue {
  border-color: rgba(245, 108, 108, 0.4);
  background: linear-gradient(180deg, var(--card-bg) 0%, rgba(245, 108, 108, 0.06) 100%);
}

.rent-reminder-mobile-card--upcoming {
  border-color: rgba(230, 162, 60, 0.38);
  background: linear-gradient(180deg, var(--card-bg) 0%, rgba(230, 162, 60, 0.06) 100%);
}

.rent-reminder-mobile-card__top,
.rent-reminder-mobile-card__bottom {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.rent-reminder-mobile-card__bottom {
  margin-top: 10px;
  align-items: center;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--text-secondary);
}

.rent-reminder-mobile-card__name {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-main);
}

.rent-reminder-mobile-card__meta {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--text-secondary);
}

.rent-reminder-amount {
  color: var(--el-color-danger);
  font-weight: 700;
}

.submission-mobile-card {
  padding: 14px;
  border-radius: 14px;
  border: 1px solid rgba(230, 162, 60, 0.38);
  background: linear-gradient(180deg, var(--card-bg) 0%, rgba(230, 162, 60, 0.06) 100%);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
}

.submission-mobile-card__top,
.submission-mobile-card__bottom {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.submission-mobile-card__bottom {
  margin-top: 10px;
  align-items: center;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--text-secondary);
}

.submission-mobile-card__actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.submission-mobile-card__name {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-main);
}

.submission-mobile-card__meta {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--text-secondary);
}

html.dark .overview-card,
html.dark .alert-panel {
  border-color: var(--surface-border);
}

@media (max-width: 1200px) {
  .overview-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .overview-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .home-container {
    gap: 16px;
  }

  .home-hero {
    align-items: flex-start;
    flex-direction: column;
    gap: 10px;
  }

  .overview-card {
    padding: 18px;
  }

  .section-header {
    align-items: flex-start;
    flex-direction: column;
    gap: 8px;
  }

  .header-left {
    flex-wrap: wrap;
  }
}

.alert-panel :deep(.el-table) {
  background: var(--card-bg);
  border-radius: 12px;
}

.stat-card-wrapper {
  height: auto;
}

.stat-header {
  display: flex;
  align-items: center;
  margin-bottom: 18px;
}

.icon-box {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  margin-right: 16px;
}

.icon-primary {
  background-color: rgba(64, 158, 255, 0.1);
  color: var(--el-color-primary);
}
.icon-success {
  background-color: rgba(103, 194, 58, 0.1);
  color: var(--el-color-success);
}
.icon-warning {
  background-color: rgba(230, 162, 60, 0.1);
  color: var(--el-color-warning);
}
.icon-info {
  background-color: rgba(59, 130, 246, 0.1);
  color: var(--el-color-info);
}
.icon-procurement {
  background-color: rgba(16, 185, 129, 0.1);
  color: #10b981;
}
.icon-utility {
  background-color: rgba(245, 158, 11, 0.12);
  color: #f59e0b;
}
.icon-rent-ledger {
  background-color: rgba(37, 99, 235, 0.1);
  color: var(--el-color-primary);
}

.stat-title {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-main);
}

.stat-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.main-value {
  font-size: 34px;
  font-weight: 700;
  color: var(--text-main);
  line-height: 1.2;
  margin-bottom: 0;
}
.unit {
  font-size: 14px;
  font-weight: normal;
  color: var(--text-secondary);
  margin-left: 4px;
}

.sub-stats {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0;
  padding: 14px;
  background-color: var(--surface-muted);
  border-radius: 12px;
  border: 1px solid var(--surface-border);
}

.sub-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.sub-item .label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.sub-item .value {
  font-size: 16px;
  font-weight: 600;
}

.value.success { color: var(--el-color-success); }
.value.warning { color: var(--el-color-warning); }
.value.danger { color: var(--el-color-danger); }
.value.info { color: var(--el-color-info); }
.value.primary { color: var(--el-color-primary); }

.progress-area {
  margin-top: 0;
  padding-top: 0;
}

.progress-label {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.ocr-status-line {
  font-size: 13px;
  color: var(--text-secondary);
}

.monthly-stats {
  border-top: 1px solid var(--surface-border);
  padding-top: 12px;
}

.monthly-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
  margin-bottom: 8px;
}

.monthly-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.monthly-row {
  display: grid;
  grid-template-columns: minmax(76px, 1fr) auto auto;
  gap: 8px;
  align-items: center;
  min-height: 28px;
  font-size: 12px;
  color: var(--text-secondary);
}

.monthly-row .month {
  color: var(--text-main);
  font-weight: 500;
}

.monthly-row strong {
  color: var(--el-color-primary);
  font-weight: 700;
  text-align: right;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--surface-border);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.warning-icon {
  font-size: 18px;
  color: var(--el-color-danger);
  background: rgba(245, 108, 108, 0.12);
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.warning-icon--primary {
  color: var(--el-color-primary);
  background: rgba(37, 99, 235, 0.12);
}

.warning-icon--rent {
  color: #f59e0b;
  background: rgba(245, 158, 11, 0.14);
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-main);
  margin: 0;
}

.advance-days-info {
  font-size: 13px;
  color: var(--text-secondary);
}

.tenant-name {
  font-weight: 600;
  color: var(--text-main);
}

/* 表格行高亮样式 */
:deep(.el-table .warning-row) {
  --el-table-tr-bg-color: var(--el-color-warning-light-9);
}

:deep(.el-table .urgent-row) {
  --el-table-tr-bg-color: var(--el-color-danger-light-9);
}

:deep(.el-table .expired-row) {
  --el-table-tr-bg-color: var(--el-color-danger-light-9);
  color: var(--el-color-danger);
}

:deep(.el-table .rent-overdue-row) {
  --el-table-tr-bg-color: var(--el-color-danger-light-9);
}

:deep(.el-table .rent-upcoming-row) {
  --el-table-tr-bg-color: var(--el-color-warning-light-9);
}

</style>
