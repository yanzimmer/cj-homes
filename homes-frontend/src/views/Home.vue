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
          <span class="advance-days-info">当前预警天数：{{ advanceDays }} 天</span>
        </div>
      </div>

      <el-table 
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
import { ref, reactive, onMounted, computed } from 'vue'
import { dashboardApi } from '../api'
import { ElMessage } from 'element-plus'
import { House, User, Tools, InfoFilled, Warning } from '@element-plus/icons-vue'

// 加载状态
const loading = reactive({
  rooms: true,
  tenants: true,
  repairs: true,
  expiring: true,
  ocr: true,
  procurements: true
})

// 预警天数配置
const advanceDays = ref(7)
const todayLabel = computed(() => {
  const now = new Date()
  return now.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
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

const fetchDashboardStats = async () => {
  loading.rooms = true
  loading.tenants = true
  loading.repairs = true
  loading.expiring = true
  loading.ocr = true
  loading.procurements = true
  try {
    const { data } = await dashboardApi.getStats()
    advanceDays.value = Number(data?.advance_days || 7)

    Object.assign(stats.rooms, data?.rooms || {})
    Object.assign(stats.tenants, data?.tenants || {})
    Object.assign(stats.repairs, data?.repairs || {})
    Object.assign(stats.procurements, data?.procurements || {})
    Object.assign(stats.expiring, data?.expiring || { count: 0, list: [] })
    Object.assign(stats.ocr, data?.ocr || {})
  } catch (error) {
    console.error('获取首页统计失败:', error)
    ElMessage.error('获取首页统计失败')
  } finally {
    loading.rooms = false
    loading.tenants = false
    loading.repairs = false
    loading.expiring = false
    loading.ocr = false
    loading.procurements = false
  }
}

// 页面加载时获取所有统计数据
onMounted(() => {
  fetchDashboardStats()
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

</style>
