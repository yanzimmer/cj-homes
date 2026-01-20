<template>
  <div class="home-container page-container">
    <div class="page-header">
      <h2>系统概览</h2>
      <span class="subtitle">欢迎回到房屋租赁管理系统</span>
    </div>

    <el-row :gutter="24">
      <!-- 房间统计卡片 -->
      <el-col :span="8" :xs="24" :sm="12" :md="8">
        <div class="stat-card-wrapper card-box">
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
      </el-col>

      <!-- 租户统计卡片 -->
      <el-col :span="8" :xs="24" :sm="12" :md="8">
        <div class="stat-card-wrapper card-box">
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
      </el-col>

      <!-- 维修记录统计卡片 -->
      <el-col :span="8" :xs="24" :sm="12" :md="8">
        <div class="stat-card-wrapper card-box">
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
                <span class="label">已完成</span>
                <span class="value success">{{ stats.repairs.completed }}</span>
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
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 预警列表区域 -->
    <el-row :gutter="24" class="mt-4">
      <el-col :span="24">
        <div class="card-box">
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
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { roomsApi, tenantsApi, repairRecordsApi, notifyApi } from '../api'
import { ElMessage } from 'element-plus'
import { House, User, Tools, InfoFilled, Warning } from '@element-plus/icons-vue'

// 加载状态
const loading = reactive({
  rooms: true,
  tenants: true,
  repairs: true,
  expiring: true
})

// 预警天数配置
const advanceDays = ref(7)

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
    completionRate: 0
  },
  expiring: {
    count: 0,
    list: []
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

// 获取房间统计数据
const fetchRoomStats = async () => {
  loading.rooms = true
  try {
    const response = await roomsApi.listRooms()
    const rooms = response.data.rooms || []
    
    stats.rooms.total = rooms.length
    stats.rooms.occupied = rooms.filter(room => room.status === '已入住').length
    stats.rooms.vacant = rooms.filter(room => room.status === '空闲').length
    stats.rooms.occupancyRate = stats.rooms.total > 0 
      ? Math.round((stats.rooms.occupied / stats.rooms.total) * 100) 
      : 0
  } catch (error) {
    console.error('获取房间统计失败:', error)
    ElMessage.error('获取房间统计失败')
  } finally {
    loading.rooms = false
  }
}

// 获取租户统计数据
const fetchTenantStats = async () => {
  loading.tenants = true
  try {
    const response = await tenantsApi.listTenants()
    const tenants = response.data.tenants || []
    
    stats.tenants.total = tenants.length
    stats.tenants.active = tenants.filter(tenant => tenant.status === '在住').length
    stats.tenants.inactive = tenants.filter(tenant => tenant.status === '已退租').length
    stats.tenants.activeRate = stats.tenants.total > 0 
      ? Math.round((stats.tenants.active / stats.tenants.total) * 100) 
      : 0
    
    // 计算平均租期（天数）
    const tenantsWithLeaseDays = tenants.filter(tenant => tenant.check_in_date)
    if (tenantsWithLeaseDays.length > 0) {
      const totalDays = tenantsWithLeaseDays.reduce((sum, tenant) => {
        const checkInDate = new Date(tenant.check_in_date)
        const endDate = tenant.status === '已退租' && tenant.check_out_date 
          ? new Date(tenant.check_out_date) 
          : new Date() // 如果还在住，使用当前日期
        const days = Math.floor((endDate - checkInDate) / (1000 * 60 * 60 * 24))
        return sum + (days > 0 ? days : 0)
      }, 0)
      stats.tenants.averageLeaseDays = Math.round(totalDays / tenantsWithLeaseDays.length)
    } else {
      stats.tenants.averageLeaseDays = 0
    }
  } catch (error) {
    console.error('获取租户统计失败:', error)
    ElMessage.error('获取租户统计失败')
  } finally {
    loading.tenants = false
  }
}

// 获取即将到期租户
const fetchExpiringContracts = async () => {
  loading.expiring = true
  try {
    // 1. 获取通知配置
    try {
      const { data: configData } = await notifyApi.getConfig()
      if (configData && configData.advance_days) {
        advanceDays.value = parseInt(configData.advance_days)
      }
    } catch (e) {
      console.warn('获取通知配置失败，使用默认值 7 天', e)
    }

    // 2. 获取租户列表并筛选
    const response = await tenantsApi.listTenants()
    const tenants = response.data.tenants || []
    
    const now = new Date()
    // 清除时分秒，只比较日期
    now.setHours(0, 0, 0, 0)
    
    const expiringList = tenants.filter(tenant => {
      // 只检查在住租户
      if (tenant.status !== '在住' || !tenant.check_out_date) return false
      
      const endDate = new Date(tenant.check_out_date)
      endDate.setHours(0, 0, 0, 0)
      
      // 计算剩余天数
      const diffTime = endDate.getTime() - now.getTime()
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
      
      // 保存剩余天数以便展示
      tenant.days_remaining = diffDays
      
      // 筛选条件：剩余天数 <= 预警天数
      // 注意：这里也包含已经过期的（diffDays < 0）
      return diffDays <= advanceDays.value
    }).sort((a, b) => a.days_remaining - b.days_remaining) // 按剩余天数升序排序
    
    stats.expiring.list = expiringList
    stats.expiring.count = expiringList.length
    
  } catch (error) {
    console.error('获取到期预警失败:', error)
    ElMessage.error('获取到期预警失败')
  } finally {
    loading.expiring = false
  }
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

// 获取维修记录统计数据
const fetchRepairStats = async () => {
  loading.repairs = true
  try {
    const response = await repairRecordsApi.listRepairRecords()
    const repairs = response.data.repair_records || []
    
    stats.repairs.total = repairs.length
    stats.repairs.pending = repairs.filter(record => record.status === '待处理').length
    stats.repairs.inProgress = repairs.filter(record => record.status === '处理中').length
    stats.repairs.completed = repairs.filter(record => record.status === '已完成').length
    stats.repairs.completionRate = stats.repairs.total > 0 
      ? Math.round((stats.repairs.completed / stats.repairs.total) * 100) 
      : 0
  } catch (error) {
    console.error('获取维修统计失败:', error)
    ElMessage.error('获取维修统计失败')
  } finally {
    loading.repairs = false
  }
}

// 页面加载时获取所有统计数据
onMounted(() => {
  fetchRoomStats()
  fetchTenantStats()
  fetchRepairStats()
  fetchExpiringContracts()
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

.stat-card-wrapper {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.stat-header {
  display: flex;
  align-items: center;
  margin-bottom: 24px;
}

.icon-box {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
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

.stat-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-main);
}

.stat-body {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.main-value {
  font-size: 36px;
  font-weight: 700;
  color: var(--text-main);
  line-height: 1.2;
  margin-bottom: 20px;
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
  margin-bottom: 24px;
  padding: 16px;
  background-color: var(--bg-color);
  border-radius: 8px;
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

.progress-area {
  margin-top: auto;
}

.progress-label {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--el-border-color-light, #ebeef5);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.warning-icon {
  font-size: 20px;
  color: var(--el-color-danger);
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

.mt-4 {
  margin-top: 24px;
}
</style>