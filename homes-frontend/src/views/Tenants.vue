<template>
  <div>
  <div class="tenants-container">
    <div class="page-header">
      <h2>租户详情</h2>
      <div class="header-operations">
        <el-input
          v-model="searchQuery"
          placeholder="搜索姓名/身份证/电话"
          style="width: 220px; margin-right: 10px"
          clearable
          @clear="handleSearchClear"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>

        <!-- 视图切换按钮 -->
        <el-radio-group v-model="currentView" size="default" style="margin-right: 15px;">
          <el-radio-button label="table">
            <el-icon><List /></el-icon> 列表
          </el-radio-button>
          <el-radio-button label="card">
            <el-icon><Grid /></el-icon> 卡片
          </el-radio-button>
          <el-radio-button label="group">
            <el-icon><Operation /></el-icon> 分组
          </el-radio-button>
        </el-radio-group>

        <el-button type="primary" @click="openAddDialog">添加租户</el-button>
        <el-button
          style="margin-left: 10px;"
          type="danger"
          :disabled="selectedTenants.length === 0"
          :loading="batchDeleting"
          @click="handleBatchDelete"
        >批量删除</el-button>
        <el-dropdown trigger="click" @command="handleExportCommand">
          <el-button style="margin-left: 10px;" type="success">
            导出 <el-icon style="margin-left:4px"><Filter /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="excel">导出为 Excel</el-dropdown-item>
              <el-dropdown-item command="word">导出为 Word</el-dropdown-item>
              <el-dropdown-item command="pdf">导出为 PDF</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <el-table 
      v-if="currentView === 'table'"
      ref="tenantsTableRef"
      row-key="id_card"
      :data="paginatedTenants" 
      v-loading="loading" 
      border 
      style="width: 100%"
      @sort-change="handleSortChange"
      @selection-change="handleSelectionChange"
      :reserve-selection="true"
    >
      <el-table-column type="selection" width="50" :selectable="rowSelectable" />
      <el-table-column prop="id" label="ID" width="80" sortable="custom"></el-table-column>
      <el-table-column prop="name" label="姓名" width="100" sortable="custom"></el-table-column>
      <el-table-column prop="gender" label="性别" width="80" sortable="custom"></el-table-column>
      <el-table-column prop="nation" label="民族" width="80" sortable="custom"></el-table-column>
      <el-table-column prop="birth_date" label="出生日期" width="120" sortable="custom"></el-table-column>
      <el-table-column prop="id_card" label="公民身份证号" width="180" sortable="custom"></el-table-column>
      <el-table-column prop="address" label="住址" width="180" sortable="custom"></el-table-column>
      <el-table-column prop="issuing_authority" label="签发机关" width="150" sortable="custom"></el-table-column>
      <el-table-column prop="valid_from" label="有效期开始" width="120" sortable="custom"></el-table-column>
      <el-table-column prop="valid_to" label="有效期结束" width="120" sortable="custom"></el-table-column>
      <el-table-column prop="phone" label="联系电话" width="130" sortable="custom"></el-table-column>
      <el-table-column prop="emergency_contact_name" label="紧急联系人" width="120" sortable="custom"></el-table-column>
      <el-table-column prop="emergency_contact_phone" label="紧急电话" width="130" sortable="custom"></el-table-column>
      <el-table-column prop="building" label="楼栋" width="100" sortable="custom"></el-table-column>
      <el-table-column prop="room_no" label="房间号" width="100" sortable="custom"></el-table-column>
      <el-table-column prop="status" label="状态" width="100" sortable="custom">
        <template #header>
          <div style="display: flex; align-items: center;">
            <span>状态</span>
            <el-dropdown trigger="click" @command="handleStatusFilter">
              <el-button style="margin-left: 5px; padding: 2px 5px;" size="small">
                <el-icon><Filter /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="all">全部</el-dropdown-item>
                  <el-dropdown-item command="在住">在住</el-dropdown-item>
                  <el-dropdown-item command="已退租">已退租</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </template>
        <template #default="scope">
          <el-tag :type="scope.row.status === '在住' ? 'success' : 'info'">
            {{ scope.row.status || '在住' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="check_in_date" label="入住日期" width="120" sortable="custom"></el-table-column>
      <el-table-column prop="check_out_date" label="退房日期" width="120" sortable="custom"></el-table-column>
      <el-table-column label="身份证正面" width="120">
        <template #default="scope">
          <el-image 
            v-if="scope.row.front_img" 
            :src="scope.row.front_img" 
            :preview-src-list="[scope.row.front_img]"
            style="width: 80px; height: 50px;"
          ></el-image>
          <span v-else>无图片</span>
        </template>
      </el-table-column>
      <el-table-column label="身份证反面" width="120">
        <template #default="scope">
          <el-image 
            v-if="scope.row.back_img" 
            :src="scope.row.back_img" 
            :preview-src-list="[scope.row.back_img]"
            style="width: 80px; height: 50px;"
          ></el-image>
          <span v-else>无图片</span>
        </template>
      </el-table-column>
      <el-table-column prop="remarks" label="备注" width="150"></el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="scope">
          <el-button 
            size="small" 
            type="primary" 
            @click="showTenantDetails(scope.row)"
          >详情</el-button>
          <el-button size="small" @click="openEditDialog(scope.row)">编辑</el-button>
          <el-button 
            size="small" 
            type="warning" 
            @click="handleCheckout(scope.row)"
            :disabled="scope.row.status === '已退租'"
          >退租</el-button>
          <el-button 
            size="small" 
            type="danger" 
            :disabled="scope.row.status === '在住'"
            @click="handleDelete(scope.row)"
            :title="scope.row.status === '在住' ? '在租状态不可删除，请先办理退租' : ''"
          >删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    
    <!-- 分页控件 -->
    <div v-if="currentView === 'table' || currentView === 'card'" class="pagination-container" style="margin-top: 20px; display: flex; justify-content: center;">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        :total="filteredTenants.length"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>

    <!-- 卡片视图 -->
    <div v-if="currentView === 'card'" class="card-view-container" v-loading="loading">
      <div v-if="paginatedTenants.length === 0" class="empty-state">
        <el-empty description="暂无租户数据" />
      </div>
      <div v-else class="tenant-cards-grid">
        <div v-for="tenant in paginatedTenants" :key="tenant.id" class="tenant-card" @click="showTenantDetails(tenant)">
          <div class="card-status-bar" :class="tenant.status === '在住' ? 'active' : 'inactive'"></div>
          <div class="card-content">
            <div class="card-header">
              <el-avatar :size="50" :icon="UserFilled" class="card-avatar" :class="tenant.gender === '女' ? 'female' : 'male'" />
              <div class="card-main-info">
                <div class="card-name">{{ tenant.name }}</div>
                <div class="card-room">
                  <span class="building">{{ tenant.building }}栋</span>
                  <span class="room">{{ tenant.room_no }}</span>
                </div>
              </div>
            </div>
            <div class="card-details">
              <div class="detail-item">
                <el-icon><Iphone /></el-icon>
                <span>{{ tenant.phone }}</span>
              </div>
              <div class="detail-item">
                <el-icon><Timer /></el-icon>
                <span>{{ tenant.check_in_date }} 入住</span>
              </div>
            </div>
            <div class="card-actions" @click.stop>
              <el-button size="small" type="primary" link @click="showTenantDetails(tenant)">详情</el-button>
              <el-button size="small" type="primary" link @click="openEditDialog(tenant)">编辑</el-button>
              <el-button 
                size="small" 
                type="warning" 
                link 
                :disabled="tenant.status === '已退租'"
                @click="handleCheckout(tenant)"
              >退租</el-button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 分组视图 -->
    <div v-if="currentView === 'group'" class="group-view-container" v-loading="loading">
      <div v-if="groupedTenants.length === 0" class="empty-state">
        <el-empty description="暂无租户数据" />
      </div>
      <div v-else class="building-groups">
        <div v-for="group in groupedTenants" :key="group.building" class="building-group-card">
          <div class="building-header">
            <span class="building-name">{{ group.building }} 栋</span>
            <el-tag size="small" effect="plain">{{ group.count }} 人</el-tag>
          </div>
          <div class="floor-list">
            <div v-for="floor in group.floors" :key="floor.floor" class="floor-row">
              <div class="floor-label">{{ floor.floor }} 层</div>
              <div class="floor-tenants">
                <div 
                  v-for="tenant in floor.tenants" 
                  :key="tenant.id" 
                  class="mini-tenant-chip"
                  :class="tenant.status === '在住' ? 'status-active' : 'status-inactive'"
                  @click="showTenantDetails(tenant)"
                >
                  <span class="room-no">{{ tenant.room_no }}</span>
                  <span class="tenant-name">{{ tenant.name }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 租户详情对话框 -->
    <el-dialog title="租户详情" v-model="detailsDialogVisible" width="800px" custom-class="tenant-details-dialog">
      <div v-if="currentTenant.id" class="tenant-details-container">
        <!-- 头部信息 -->
        <div class="details-header">
          <div class="avatar-section">
            <el-avatar :size="64" :src="currentTenant.avatar_url || ''" :icon="UserFilled" class="user-avatar" :class="currentTenant.gender === '女' ? 'female' : 'male'"></el-avatar>
            <div class="basic-identity">
              <h3 class="tenant-name">
                {{ currentTenant.name }}
                <el-tag size="small" :type="currentTenant.status === '在住' ? 'success' : 'info'" effect="dark" class="status-tag">
                  {{ currentTenant.status || '在住' }}
                </el-tag>
              </h3>
              <p class="tenant-id">ID: {{ currentTenant.id_card }}</p>
            </div>
          </div>
          <div class="room-badge" v-if="currentTenant.room_no">
            <div class="label">当前房间</div>
            <div class="value">{{ currentTenant.building }}栋 {{ currentTenant.room_no }}</div>
          </div>
        </div>

        <el-tabs v-model="activeDetailTab" class="details-tabs">
          <el-tab-pane label="基本信息" name="basic">
            <el-descriptions :column="2" border>
              <el-descriptions-item label="姓名">{{ currentTenant.name }}</el-descriptions-item>
              <el-descriptions-item label="性别">{{ currentTenant.gender }}</el-descriptions-item>
              <el-descriptions-item label="民族">{{ currentTenant.nation }}</el-descriptions-item>
              <el-descriptions-item label="出生日期">{{ currentTenant.birth_date }}</el-descriptions-item>
              <el-descriptions-item label="联系电话">{{ currentTenant.phone }}</el-descriptions-item>
              <el-descriptions-item label="身份证号">{{ currentTenant.id_card }}</el-descriptions-item>
              <el-descriptions-item label="户籍地址" :span="2">{{ currentTenant.address }}</el-descriptions-item>
              <el-descriptions-item label="签发机关">{{ currentTenant.issuing_authority }}</el-descriptions-item>
              <el-descriptions-item label="有效期限">{{ currentTenant.valid_period || (currentTenant.valid_from + ' - ' + currentTenant.valid_to) }}</el-descriptions-item>
            </el-descriptions>
          </el-tab-pane>
          
          <el-tab-pane label="租赁信息" name="lease">
            <el-descriptions :column="2" border>
              <el-descriptions-item label="楼栋">{{ currentTenant.building }}</el-descriptions-item>
              <el-descriptions-item label="房间号">{{ currentTenant.room_no }}</el-descriptions-item>
              <el-descriptions-item label="入住日期">
                <el-tag size="small" type="success">{{ currentTenant.check_in_date }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="退房日期">
                <span v-if="currentTenant.check_out_date">{{ currentTenant.check_out_date }}</span>
                <el-tag v-else size="small" type="info">未定</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="紧急联系人">{{ currentTenant.emergency_contact_name || currentTenant.emergency_contact }}</el-descriptions-item>
              <el-descriptions-item label="紧急电话">{{ currentTenant.emergency_contact_phone || currentTenant.emergency_phone }}</el-descriptions-item>
              <el-descriptions-item label="备注" :span="2">{{ currentTenant.remarks || currentTenant.notes || '无' }}</el-descriptions-item>
            </el-descriptions>
          </el-tab-pane>

          <el-tab-pane label="关联维修" name="repairs" v-if="currentTenant.room_no">
            <div v-loading="repairsLoading">
              <el-table :data="tenantRepairs" style="width: 100%" size="small" empty-text="该房间暂无维修记录">
                <el-table-column prop="create_time" label="报修时间" width="160"></el-table-column>
                <el-table-column prop="description" label="问题描述"></el-table-column>
                <el-table-column prop="status" label="状态" width="100">
                  <template #default="scope">
                    <el-tag size="small" :type="getRepairStatusType(scope.row.status)">{{ scope.row.status }}</el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="detailsDialogVisible = false">关闭</el-button>
          <el-button type="primary" @click="openEditDialog(currentTenant); detailsDialogVisible = false">编辑信息</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 添加/编辑租户对话框 -->
    <el-dialog :title="dialogTitle" v-model="dialogVisible" width="700px" top="5vh">
      <div class="ocr-actions">
        <el-button size="large" type="primary" :loading="ocrLoadingFront" @click="triggerFrontUpload">识别身份证(正面)</el-button>
        <el-button size="large" type="success" :loading="ocrLoadingBack" @click="triggerBackUpload">识别身份证(反面)</el-button>
        <input ref="frontFileInput" type="file" accept="image/*" style="display:none" @change="onFrontFileChange" />
        <input ref="backFileInput" type="file" accept="image/*" style="display:none" @change="onBackFileChange" />
      </div>
      <div class="narrow-fields">
        <el-form :model="tenantForm" :rules="rules" ref="tenantFormRef" label-width="120px">
        <el-form-item label="姓名" prop="name">
          <el-input v-model="tenantForm.name"></el-input>
        </el-form-item>
        <el-form-item label="性别" prop="gender">
          <el-radio-group v-model="tenantForm.gender">
            <el-radio label="男">男</el-radio>
            <el-radio label="女">女</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="民族" prop="nation">
          <el-input v-model="tenantForm.nation"></el-input>
        </el-form-item>
        <el-form-item label="出生日期" prop="birth_date">
          <el-date-picker v-model="tenantForm.birth_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期"></el-date-picker>
        </el-form-item>
        <el-form-item label="公民身份证号" prop="id_card">
          <el-input v-model="tenantForm.id_card"></el-input>
        </el-form-item>
        <el-form-item label="住址" prop="address">
          <el-input v-model="tenantForm.address"></el-input>
        </el-form-item>
        <el-form-item label="签发机关" prop="issuing_authority">
          <el-input v-model="tenantForm.issuing_authority"></el-input>
        </el-form-item>
        <el-form-item label="有效期限" prop="valid_period">
          <el-input v-model="tenantForm.valid_period"></el-input>
        </el-form-item>
        <el-form-item label="联系电话" prop="phone">
          <el-input v-model="tenantForm.phone"></el-input>
        </el-form-item>
        <el-form-item label="紧急联系人" prop="emergency_contact">
          <el-input v-model="tenantForm.emergency_contact"></el-input>
        </el-form-item>
        <el-form-item label="紧急电话" prop="emergency_phone">
          <el-input v-model="tenantForm.emergency_phone"></el-input>
        </el-form-item>
        <el-form-item label="房间号" prop="room_no" v-if="!isEdit">
          <el-select v-model="tenantForm.room_no" placeholder="请选择房间">
            <el-option v-for="room in availableRooms" :key="room.room_no" :label="room.room_no" :value="room.room_no"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="入住日期" prop="check_in_date">
          <el-date-picker v-model="tenantForm.check_in_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期"></el-date-picker>
        </el-form-item>
        <el-form-item label="退房日期" prop="check_out_date">
          <el-date-picker v-model="tenantForm.check_out_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期"></el-date-picker>
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-radio-group v-model="tenantForm.status">
            <el-radio label="在住">在住</el-radio>
            <el-radio label="已退租">已退租</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="备注" prop="notes">
          <el-input v-model="tenantForm.notes" type="textarea" :rows="3"></el-input>
        </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSubmit" :loading="submitting">确定</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 退租确认对话框 -->
    <el-dialog title="确认退租" v-model="checkoutDialogVisible" width="400px">
      <div class="checkout-confirm">
        <p>确定要将租户 <strong>{{ checkoutTenant.name }}</strong> 办理退租吗？</p>
        <p>公民身份证号: {{ checkoutTenant.id_card }}</p>
        <p>房间号: {{ checkoutTenant.room_no }}</p>
        <p class="warning">注意: 退租操作不可撤销，租户状态将变更为"已退租"</p>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="checkoutDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmCheckout" :loading="checkoutLoading">确认退租</el-button>
        </span>
      </template>
    </el-dialog>
  </div>

  <!-- 隐藏打印区域：包含筛选后的租户列表，用于 PDF 截图渲染，保证中文显示正确 -->
  <div v-if="showPrintArea" ref="printAreaRef" class="print-area">
    <h2 style="text-align:center; margin-bottom: 12px;">租户列表</h2>
    <table class="print-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>姓名</th>
          <th>性别</th>
          <th>民族</th>
          <th>出生日期</th>
          <th>公民身份证号</th>
          <th>联系电话</th>
          <th>楼栋</th>
          <th>房间号</th>
          <th>状态</th>
          <th>入住日期</th>
          <th>退房日期</th>
          <th>备注</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="t in filteredTenants" :key="t.id">
          <td>{{ t.id }}</td>
          <td>{{ t.name }}</td>
          <td>{{ t.gender }}</td>
          <td>{{ t.nation }}</td>
          <td>{{ t.birth_date }}</td>
          <td>{{ t.id_card }}</td>
          <td>{{ t.phone }}</td>
          <td>{{ t.building }}</td>
          <td>{{ t.room_no }}</td>
          <td>{{ t.status }}</td>
          <td>{{ t.check_in_date }}</td>
          <td>{{ t.check_out_date }}</td>
          <td>{{ t.remarks || t.notes }}</td>
        </tr>
      </tbody>
    </table>
  </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, nextTick } from 'vue'
import { tenantsApi, roomsApi, ocrApi, repairRecordsApi } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Filter, UserFilled, List, Grid, Operation, Iphone, Timer } from '@element-plus/icons-vue'
import * as XLSX from 'xlsx'
import { jsPDF } from 'jspdf'
import { Document, Packer, Paragraph, Table as DocxTable, TableRow, TableCell, TextRun } from 'docx'
import { saveAs } from 'file-saver'
import html2canvas from 'html2canvas'

// 视图切换
const currentView = ref('table') // 'table', 'card', 'group'

// 数据
const tenants = ref([])
const availableRooms = ref([])
const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('添加租户')
const isEdit = ref(false)
const tenantFormRef = ref(null)

// 搜索、排序和筛选
const searchQuery = ref('')
const sortBy = ref('')
const sortOrder = ref('')
const statusFilter = ref('all')

// 分页相关
const currentPage = ref(1)
const pageSize = ref(20)
const showPrintArea = ref(false)
const printAreaRef = ref(null)

// 当前页数据（基于 filteredTenants 的稳定切片）
const paginatedTenants = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = currentPage.value * pageSize.value
  return filteredTenants.value.slice(start, end)
})

// 批量删除相关状态
const tenantsTableRef = ref(null)
const selectedTenants = ref([])
const batchDeleting = ref(false)

// 处理页面大小变化
const handleSizeChange = (size) => {
  pageSize.value = size
  currentPage.value = 1
}

// 处理当前页变化
const handleCurrentChange = (page) => {
  currentPage.value = page
}

// 过滤和排序后的租户列表
const filteredTenants = computed(() => {
  let result = [...tenants.value]
  
  // 应用状态筛选
  if (statusFilter.value !== 'all') {
    result = result.filter(tenant => tenant.status === statusFilter.value)
  }
  
  // 应用搜索
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(tenant => 
      (tenant.name && tenant.name.toLowerCase().includes(query)) ||
      (tenant.id_card && tenant.id_card.toLowerCase().includes(query)) ||
      (tenant.phone && tenant.phone.toLowerCase().includes(query))
    )
  }
  
  // 应用排序
  if (sortBy.value) {
    result.sort((a, b) => {
      let aValue = a[sortBy.value]
      let bValue = b[sortBy.value]
      
      // 处理可能的空值
      if (aValue === undefined || aValue === null) aValue = ''
      if (bValue === undefined || bValue === null) bValue = ''
      
      // 数字类型的排序
      if (!isNaN(aValue) && !isNaN(bValue)) {
        return sortOrder.value === 'ascending' ? aValue - bValue : bValue - aValue
      }
      
      // 字符串类型的排序
      return sortOrder.value === 'ascending' 
        ? String(aValue).localeCompare(String(bValue)) 
        : String(bValue).localeCompare(String(aValue))
    })
  }
  
  return result
})

// 分组视图数据
const groupedTenants = computed(() => {
  const groups = {}
  // 使用筛选后的数据
  filteredTenants.value.forEach(t => {
    const b = t.building || '未分类'
    // 简单推导楼层：取房间号前几位（去除后两位）
    let f = '其他'
    const digits = (t.room_no || '').replace(/\D/g, '')
    if (digits.length >= 3) {
      f = String(Math.floor(parseInt(digits) / 100))
    }
    
    if (!groups[b]) groups[b] = {}
    if (!groups[b][f]) groups[b][f] = []
    groups[b][f].push(t)
  })
  
  // 转换为数组结构
  return Object.keys(groups)
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
    .map(bKey => {
      const floorsObj = groups[bKey]
      const floorsArr = Object.keys(floorsObj)
        .sort((a, b) => parseInt(a) - parseInt(b))
        .map(fKey => ({
          floor: fKey,
          tenants: floorsObj[fKey].sort((x, y) => (x.room_no || '').localeCompare(y.room_no || '', undefined, { numeric: true }))
        }))
      
      const count = floorsArr.reduce((sum, f) => sum + f.tenants.length, 0)
      
      return {
        building: bKey,
        floors: floorsArr,
        count
      }
    })
})

// 退租相关数据
const checkoutDialogVisible = ref(false)
const checkoutLoading = ref(false)
const checkoutTenant = ref({})

// 租户详情相关
const detailsDialogVisible = ref(false)
const activeDetailTab = ref('basic')
const currentTenant = ref({})
const tenantRepairs = ref([])
const repairsLoading = ref(false)

const showTenantDetails = async (tenant) => {
  currentTenant.value = { ...tenant }
  activeDetailTab.value = 'basic'
  detailsDialogVisible.value = true
  
  // 如果有房间号，获取该房间的维修记录作为参考
  if (tenant.room_no) {
    repairsLoading.value = true
    try {
      const res = await repairRecordsApi.getRoomRepairRecords(tenant.room_no)
      tenantRepairs.value = res.data.repair_records || []
    } catch (e) {
      console.error('获取维修记录失败', e)
      tenantRepairs.value = []
    } finally {
      repairsLoading.value = false
    }
  } else {
    tenantRepairs.value = []
  }
}

const getRepairStatusType = (status) => {
  const map = {
    '待处理': 'danger',
    '处理中': 'warning',
    '已完成': 'success'
  }
  return map[status] || 'info'
}

// 处理退租按钮点击
const handleCheckout = (tenant) => {
  checkoutTenant.value = tenant
  checkoutDialogVisible.value = true
}

// 确认退租
const confirmCheckout = async () => {
  try {
    checkoutLoading.value = true
    const response = await tenantsApi.checkoutTenant(checkoutTenant.value.id_card)
    
    ElMessage.success(response.data.message || '退租成功')
    checkoutDialogVisible.value = false
    fetchTenants() // 刷新租户列表
  } catch (error) {
    ElMessage.error('退租失败: ' + (error.response?.data?.error || error.message))
  } finally {
    checkoutLoading.value = false
  }
}

const tenantForm = reactive({
  id: null,
  name: '',
  gender: '男',
  nation: '汉族',
  birth_date: '',
  id_card: '',
  address: '',
  issuing_authority: '',
  valid_period: '',
  id_card_image: '',
  front_img: '',
  back_img: '',
  phone: '',
  emergency_contact: '',
  emergency_phone: '',
  room_no: '',
  status: '在住',
  check_in_date: new Date(),
  check_out_date: '',
  notes: ''
})

const rules = {
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  gender: [{ required: true, message: '请选择性别', trigger: 'change' }],
  id_card: [{ required: true, message: '请输入公民身份证号', trigger: 'blur' }],
  phone: [{ required: true, message: '请输入联系电话', trigger: 'blur' }],
  room_no: [{ required: true, message: '请选择房间', trigger: 'change' }],
  check_in_date: [{ required: true, message: '请选择入住日期', trigger: 'change' }],
  check_out_date: [{ required: true, message: '请选择退房日期', trigger: 'change' }]
}

// 生命周期
onMounted(() => {
  fetchTenants()
  fetchAvailableRooms()
})

// 方法
// 处理排序变化
const handleSortChange = (column) => {
  sortBy.value = column.prop
  sortOrder.value = column.order
}

// 仅允许“已退租”的租户可被选中进行批量删除
const rowSelectable = (row) => {
  const s = String(row.status || '').trim()
  return s === '已退租'
}

// 监听选择变化
const handleSelectionChange = (selection) => {
  console.log('[Tenants] selection changed:', selection.map(s => s.id_card))
  selectedTenants.value = selection
}

// 处理状态筛选
const handleStatusFilter = (command) => {
  statusFilter.value = command
}

// 清除搜索
const handleSearchClear = () => {
  searchQuery.value = ''
}

const fetchTenants = async () => {
  loading.value = true
  try {
    const response = await tenantsApi.listTenants()
    // 确保tenants.value是一个数组
    tenants.value = response.data.tenants || []
    console.log('租户数据:', tenants.value)
  } catch (error) {
    ElMessage.error('获取租户列表失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

const fetchAvailableRooms = async () => {
  try {
    const response = await roomsApi.listRooms()
    // 确保response.data.rooms是一个数组
    const roomsData = response.data.rooms || []
    console.log('房间数据:', roomsData)
    // 添加租户时显示所有房间，编辑租户时仅显示空闲房间或当前租户的房间
    availableRooms.value = isEdit.value 
      ? roomsData.filter(room => room.status === '空闲' || room.room_no === tenantForm.room_no)
      : roomsData
  } catch (error) {
    console.error('获取可用房间失败', error)
  }
}

const resetForm = () => {
  if (tenantFormRef.value) {
    tenantFormRef.value.resetFields()
  }
  tenantForm.id = null
  tenantForm.name = ''
  tenantForm.gender = '男'
  tenantForm.nation = '汉族'
  tenantForm.birth_date = ''
  tenantForm.id_card = ''
  tenantForm.address = ''
  tenantForm.issuing_authority = ''
  tenantForm.valid_period = ''
  tenantForm.id_card_image = ''
  tenantForm.front_img = ''
  tenantForm.back_img = ''
  tenantForm.phone = ''
  tenantForm.emergency_contact = ''
  tenantForm.emergency_phone = ''
  tenantForm.room_no = ''
  tenantForm.status = '在住'
  tenantForm.check_in_date = new Date()
  tenantForm.check_out_date = ''
  tenantForm.notes = ''
}

const openAddDialog = () => {
  resetForm()
  isEdit.value = false
  dialogTitle.value = '添加租户'
  fetchAvailableRooms()
  dialogVisible.value = true
}

const openEditDialog = (tenant) => {
  resetForm()
  isEdit.value = true
  dialogTitle.value = '编辑租户'
  Object.assign(tenantForm, tenant)
  fetchAvailableRooms()
  dialogVisible.value = true
}

// OCR 相关
const ocrLoadingFront = ref(false)
const ocrLoadingBack = ref(false)
const frontFileInput = ref(null)
const backFileInput = ref(null)

const triggerFrontUpload = () => frontFileInput.value && frontFileInput.value.click()
const triggerBackUpload = () => backFileInput.value && backFileInput.value.click()

// 解析 OCR 文本，尽量提取身份证字段
const parseIdCardText = (text) => {
  if (!text || typeof text !== 'string') return {}
  // 规范化空格：
  // 1) 将连续空格压缩为单个空格（便于阅读）
  const t = text.replace(/\s+/g, ' ').trim()
  // 2) 移除“中文字符之间”的空格，修复如“姓 名”“住 址”“性 别”等现象
  let ts = t.replace(/(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])/g, '')
  // 3) 常见 OCR 误识别纠正
  const fixes = [
    ['牲别', '性别'],
    ['氓族', '民族'],
    ['闵族', '民族'],
    ['民蔟', '民族'],
    ['签发机 关', '签发机关'],
    ['签 发 机 关', '签发机关'],
    ['有 效 期', '有效期'],
    ['有 效 期 限', '有效期限']
  ]
  for (const [from, to] of fixes) {
    ts = ts.replace(new RegExp(from, 'g'), to)
  }

  const out = {}

  // 姓名/性别/民族：在 ts（去除中文间空格）上匹配
  const nameMatch = ts.match(/姓名[:：]?\s*([\u4e00-\u9fa5·]{2,20})/)
  if (nameMatch) out.name = nameMatch[1]

  const genderMatch = ts.match(/性别[:：]?\s*(男|女)/)
  if (genderMatch) out.gender = genderMatch[1]

  const nationMatch = ts.match(/民族[:：]?\s*([\u4e00-\u9fa5]{1,10})/)
  if (nationMatch) out.nation = nationMatch[1]

  // 出生日期：允许数字与“年/月/日”之间存在空格
  const birthMatch = t.match(/出生[:：]?\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?/)
  if (birthMatch) {
    const y = birthMatch[1]
    const m = String(birthMatch[2]).padStart(2, '0')
    const d = String(birthMatch[3]).padStart(2, '0')
    out.birth_date = `${y}-${m}-${d}`
  }

  // 住址：允许“住址”和“公民身份号码”之间有内容，且 key 允许中文间空格（通过 ts）
  const addrMatch = ts.match(/住址[:：]?\s*(.+?)\s*公民身份号码/)
  if (addrMatch) out.address = addrMatch[1].trim()

  // 身份证号：允许 key 拆分，如“公民 身份 号码”或“身 份 证 号”（通过 ts）
  const idMatch = ts.match(/(公民身份号码|身份证号)[:：]?\s*([0-9]{15,18}[0-9Xx]?)/)
  if (idMatch) out.id_card = idMatch[2].toUpperCase()

  // 签发机关：同理在 ts 上匹配
  const issuerMatch = ts.match(/签发机关[:：]?\s*([\u4e00-\u9fa5A-Za-z()（）\-·\s]{3,})/)
  if (issuerMatch) out.issuing_authority = issuerMatch[1].trim()

  // 有效期：允许存在空格/多种连接符
  const validMatch = t.match(/有\s*效\s*期(?:限)?[:：]?\s*([\d\.\-\s年月日]+)\s*(?:至|\-|—|~|到|—{1,2}|一)\s*([\d\.\-\s年月日]+)/)
  if (validMatch) {
    const norm = (s) => s
      .replace(/年|\.|\s/g, '-')
      .replace(/月/g, '-')
      .replace(/日/g, '')
      .replace(/-+/g, '-')
      .replace(/^-/,'')
      .replace(/-$/,'')
    out.valid_period = `${norm(validMatch[1])} - ${norm(validMatch[2])}`
  }

  return out
}

// 应用 OCR 响应到表单并返回填充字段数量（支持 raw_text 与 data）
const applyOcrResponse = (payload) => {
  if (!payload) return 0
  let applied = 0

  // 解析原始文本（后端返回为 raw_text；容错 text）
  const raw = payload.raw_text || payload.text
  if (raw) {
    const parsed = parseIdCardText(raw)
    for (const [k, v] of Object.entries(parsed)) {
      if (v) {
        tenantForm[k] = v
        applied++
      }
    }
  }

  // 结构化字段（后端返回在 data；容错直接在 payload）
  const data = payload.data || payload
  const keys = ['name','gender','nation','birth_date','id_card','address','issuing_authority','valid_period']
  for (const k of keys) {
    if (data && data[k]) {
      tenantForm[k] = data[k]
      applied++
    }
  }

  // 兼容 issuer 字段映射到 issuing_authority
  if (data && data.issuer && !tenantForm.issuing_authority) {
    tenantForm.issuing_authority = data.issuer
    applied++
  }

  // 若只提供起止日期，拼成 valid_period
  if (data && !tenantForm.valid_period && data.valid_start && data.valid_end) {
    tenantForm.valid_period = `${data.valid_start} - ${data.valid_end}`
    applied++
  }

  // 图片 URL
  if (data && data.front_img) tenantForm.front_img = data.front_img
  if (data && data.back_img) tenantForm.back_img = data.back_img

  return applied
}

const onFrontFileChange = async (e) => {
  const file = e.target.files && e.target.files[0]
  if (!file) return
  ocrLoadingFront.value = true
  try {
    const resp = await ocrApi.ocrIdCard(file, 'front')
    const applied = applyOcrResponse(resp.data)
    ElMessage.success(applied > 0 ? '正面识别完成，已填充表单' : '正面识别完成（图片已保存）')
  } catch (err) {
    if (err.response?.data) {
      const applied = applyOcrResponse(err.response.data)
      if (applied > 0) {
        ElMessage.success('正面识别部分成功，已填充部分表单')
      }
    }
    const baseMsg = err.response?.data?.error || '正面识别失败'
    const extra = err.response?.data?.data ? '（图片已保存）' : ''
    ElMessage.error(baseMsg + extra)
  } finally {
    ocrLoadingFront.value = false
    e.target.value = ''
  }
}

const onBackFileChange = async (e) => {
  const file = e.target.files && e.target.files[0]
  if (!file) return
  ocrLoadingBack.value = true
  try {
    const resp = await ocrApi.ocrIdCard(file, 'back')
    const applied = applyOcrResponse(resp.data)
    ElMessage.success(applied > 0 ? '反面识别完成，已填充表单' : '反面识别完成（图片已保存）')
  } catch (err) {
    if (err.response?.data) {
      const applied = applyOcrResponse(err.response.data)
      if (applied > 0) {
        ElMessage.success('反面识别部分成功，已填充部分表单')
      }
    }
    const baseMsg = err.response?.data?.error || '反面识别失败'
    const extra = err.response?.data?.data ? '（图片已保存）' : ''
    ElMessage.error(baseMsg + extra)
  } finally {
    ocrLoadingBack.value = false
    e.target.value = ''
  }
}

const handleSubmit = async () => {
  if (!tenantFormRef.value) return
  
  await tenantFormRef.value.validate(async (valid) => {
    if (valid) {
      submitting.value = true
      try {
        // 格式化日期
        const formData = { ...tenantForm }
        if (formData.birth_date) {
          formData.birth_date = formatDate(formData.birth_date)
        }
        if (formData.check_in_date) {
          formData.check_in_date = formatDate(formData.check_in_date)
        }
        if (formData.check_out_date) {
          formData.check_out_date = formatDate(formData.check_out_date)
        }

        // 字段映射以匹配后端
        if (formData.issuing_authority) formData.issuer = formData.issuing_authority
        if (formData.valid_period) {
          const m = formData.valid_period.match(/(\d{4}-\d{1,2}-\d{1,2}).*?(\d{4}-\d{1,2}-\d{1,2})/)
          if (m) {
            formData.valid_start = m[1]
            formData.valid_end = m[2]
          }
        }
        if (formData.emergency_contact) formData.emergency_contact_name = formData.emergency_contact
        if (formData.emergency_phone) formData.emergency_contact_phone = formData.emergency_phone
        
        if (isEdit.value) {
          // 编辑时不修改房间号，从表单数据中移除room_no
          const { room_no, ...updateData } = formData
          // 确保路径参数使用到 id_card
          updateData.id_card = formData.id_card
          await tenantsApi.updateTenant(formData.id_card, updateData)
          ElMessage.success('租户更新成功')
        } else {
          await tenantsApi.addTenant(formData)
          // 若新增选择了“已退租”，追加更新状态
          if (formData.status && formData.status !== '在住') {
            await tenantsApi.updateTenant(formData.id_card, { id_card: formData.id_card, status: formData.status })
          }
          ElMessage.success('租户添加成功')
        }
        dialogVisible.value = false
        fetchTenants()
      } catch (error) {
        ElMessage.error(isEdit.value ? '更新租户失败' : '添加租户失败')
        console.error(error)
      } finally {
        submitting.value = false
      }
    }
  })
}

const handleDelete = (tenant) => {
  if (tenant?.status === '在住') {
    ElMessage.warning('在租状态不可删除，请先办理退租')
    return
  }
  ElMessageBox.confirm('确定要删除这个租户吗？', '警告', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await tenantsApi.deleteTenant(tenant.id_card)
      ElMessage.success('租户删除成功')
      fetchTenants()
    } catch (error) {
      const msg = error?.response?.data?.error || error?.message || '删除租户失败'
      ElMessage.error(msg)
      console.error(error)
    }
  }).catch(() => {})
}

// 批量删除选中的租户（仅“已退租”）
const handleBatchDelete = async () => {
  if (!selectedTenants.value.length) return
  const count = selectedTenants.value.length
  const names = selectedTenants.value.map(t => t.name).join('、')
  try {
    await ElMessageBox.confirm(
      `确认批量删除以下 ${count} 名租户吗？\n${names}\n该操作不可撤销。`,
      '批量删除确认',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    batchDeleting.value = true
    const successes = []
    const failures = []
    // 顺序执行，避免 SQLite 并发写导致 database is locked
    for (const t of selectedTenants.value) {
      try {
        await tenantsApi.deleteTenant(t.id_card)
        successes.push(t)
      } catch (err) {
        const msg = err?.response?.data?.error || err?.message || '未知错误'
        failures.push({ tenant: t, msg })
      }
    }

    if (successes.length) ElMessage.success(`批量删除成功：${successes.length} 个`)
    if (failures.length) {
      const detail = failures.map(f => `${f.tenant.name}(${f.tenant.id_card})：${f.msg}`).join('；')
      ElMessage.error(`批量删除失败：${failures.length} 个。原因：${detail}`)
    }

    await fetchTenants()
    tenantsTableRef.value?.clearSelection()
    selectedTenants.value = []
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('批量删除失败：' + (error?.message || '未知错误'))
    }
  } finally {
    batchDeleting.value = false
  }
}

// 辅助函数
const formatDate = (date) => {
  if (!date) return ''
  if (typeof date === 'string') return date
  
  const d = new Date(date)
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

// 导出相关
const handleExportCommand = (cmd) => {
  if (cmd === 'excel') return exportToExcel()
  if (cmd === 'word') return exportToWord()
  if (cmd === 'pdf') return exportToPDF()
}

const getExportRows = () => {
  return filteredTenants.value.map(t => ({
    ID: t.id,
    姓名: t.name,
    性别: t.gender,
    民族: t.nation,
    出生日期: t.birth_date,
    公民身份证号: t.id_card,
    联系电话: t.phone,
    楼栋: t.building,
    房间号: t.room_no,
    状态: t.status,
    入住日期: t.check_in_date,
    退房日期: t.check_out_date,
    备注: t.remarks || t.notes || ''
  }))
}

const exportToExcel = () => {
  try {
    const rows = getExportRows()
    const ws = XLSX.utils.json_to_sheet(rows)
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, '租户列表')
    XLSX.writeFile(wb, `租户列表_${new Date().toLocaleDateString()}.xlsx`)
    ElMessage.success('Excel 导出完成')
  } catch (e) {
    console.error('导出 Excel 失败', e)
    ElMessage.error('导出 Excel 失败')
  }
}

const exportToWord = async () => {
  try {
    const rows = getExportRows()
    const headerCells = ['ID','姓名','性别','民族','出生日期','公民身份证号','联系电话','楼栋','房间号','状态','入住日期','退房日期','备注'].map(text =>
      new TableCell({ children: [new Paragraph({ children: [new TextRun(String(text))] })] })
    )
    const tableRows = [
      new TableRow({ children: headerCells }),
      ...rows.map(r => new TableRow({
        children: [
          new TableCell({ children: [new Paragraph(String(r.ID))] }),
          new TableCell({ children: [new Paragraph(String(r['姓名']))] }),
          new TableCell({ children: [new Paragraph(String(r['性别']))] }),
          new TableCell({ children: [new Paragraph(String(r['民族']))] }),
          new TableCell({ children: [new Paragraph(String(r['出生日期']))] }),
          new TableCell({ children: [new Paragraph(String(r['公民身份证号']))] }),
          new TableCell({ children: [new Paragraph(String(r['联系电话']))] }),
          new TableCell({ children: [new Paragraph(String(r['楼栋']))] }),
          new TableCell({ children: [new Paragraph(String(r['房间号']))] }),
          new TableCell({ children: [new Paragraph(String(r['状态']))] }),
          new TableCell({ children: [new Paragraph(String(r['入住日期']))] }),
          new TableCell({ children: [new Paragraph(String(r['退房日期']))] }),
          new TableCell({ children: [new Paragraph(String(r['备注']))] })
        ]
      }))
    ]
    const doc = new Document({ sections: [{ children: [ new DocxTable({ rows: tableRows }) ] }] })
    const blob = await Packer.toBlob(doc)
    saveAs(blob, `租户列表_${new Date().toLocaleDateString()}.docx`)
    ElMessage.success('Word 导出完成')
  } catch (e) {
    console.error('导出 Word 失败', e)
    ElMessage.error('导出 Word 失败')
  }
}

const exportToPDF = async () => {
  try {
    showPrintArea.value = true
    await nextTick()
    const el = printAreaRef.value
    if (!el) throw new Error('打印区域未就绪')
    const canvas = await html2canvas(el, { scale: 2, useCORS: true, backgroundColor: '#ffffff' })
    const imgData = canvas.toDataURL('image/png')
    const pdf = new jsPDF('p', 'pt', 'a4')
    const pageWidth = pdf.internal.pageSize.getWidth()
    const pageHeight = pdf.internal.pageSize.getHeight()
    const imgWidth = pageWidth
    const imgHeight = canvas.height * (imgWidth / canvas.width)
    let heightLeft = imgHeight
    let position = 0
    pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight)
    heightLeft -= pageHeight
    while (heightLeft > 0) {
      position = heightLeft - imgHeight
      pdf.addPage()
      pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight)
      heightLeft -= pageHeight
    }
    pdf.save(`租户列表_${new Date().toLocaleDateString()}.pdf`)
    ElMessage.success('PDF 导出完成（中文已正确显示）')
  } catch (e) {
    console.error('导出 PDF 失败', e)
    ElMessage.error('导出 PDF 失败')
  } finally {
    showPrintArea.value = false
  }
}
</script>

<style scoped>
/* 统一收窄添加/编辑租户表单中的控件宽度 */
.ocr-actions {
  width: 100%;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-bottom: 12px;
}
.ocr-actions :deep(.el-button) {
  font-size: 14px;
  padding: 10px 16px;
}
.narrow-fields {
  max-width: 640px;
  margin: 0 auto;
}
.narrow-fields :deep(.el-input),
.narrow-fields :deep(.el-select),
.narrow-fields :deep(.el-date-editor),
.narrow-fields :deep(.el-input-number),
.narrow-fields :deep(.el-radio-group),
.narrow-fields :deep(.el-textarea) {
  width: 80% !important;
}

/* 防止标签文字换行，保持单行显示 */
.narrow-fields :deep(.el-form-item__label) {
  white-space: nowrap;
}
</style>
<style scoped>
.tenants-container {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  color: #409EFF;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

/* 隐藏打印区域样式，宽度较大以保证截图清晰 */
.print-area {
  position: fixed;
  left: -9999px;
  top: 0;
  width: 1200px;
  background: #ffffff;
  color: #333;
  padding: 12px;
  font-family: 'Arial', 'Microsoft YaHei', 'PingFang SC', 'Hiragino Sans GB', sans-serif;
}
.print-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}
.print-table th, .print-table td {
  border: 1px solid #ddd;
  padding: 6px 8px;
  font-size: 13px;
  word-break: break-all;
}
.print-table thead th {
  background: #f5f7fa;
}

/* 租户详情样式 */
.tenant-details-container {
  padding: 0 10px;
}
.details-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid #f0f2f5;
}
.avatar-section {
  display: flex;
  align-items: center;
  gap: 16px;
}
.user-avatar {
  background: #c0c4cc;
  font-size: 24px;
}
.user-avatar.male {
  background: #409EFF;
}
.user-avatar.female {
  background: #F56C6C;
}
.basic-identity .tenant-name {
  margin: 0 0 4px 0;
  font-size: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.basic-identity .tenant-id {
  margin: 0;
  color: #909399;
  font-size: 13px;
}
.room-badge {
  text-align: right;
  background: #f4f4f5;
  padding: 8px 16px;
  border-radius: 8px;
}
.room-badge .label {
  font-size: 12px;
  color: #909399;
}
.room-badge .value {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
}
.details-tabs :deep(.el-descriptions__label) {
  width: 100px;
  justify-content: flex-end;
}

/* 卡片视图样式 */
.card-view-container {
  padding: 10px 0;
}
.tenant-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}
.tenant-card {
  background: var(--card-bg);
  border-radius: 12px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
  transition: all 0.3s;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  border: 1px solid var(--el-border-color-light, #ebeef5);
}
.tenant-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 16px 0 rgba(0, 0, 0, 0.1);
}
.card-status-bar {
  height: 4px;
  width: 100%;
}
.card-status-bar.active {
  background: #67C23A;
}
.card-status-bar.inactive {
  background: #909399;
}
.card-content {
  padding: 16px;
}
.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.card-avatar {
  background: #c0c4cc;
  font-size: 20px;
  flex-shrink: 0;
}
.card-avatar.male {
  background: #409EFF;
}
.card-avatar.female {
  background: #F56C6C;
}
.card-main-info {
  flex: 1;
  overflow: hidden;
}
.card-name {
  font-size: 16px;
  font-weight: bold;
  color: var(--text-main);
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.card-room {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-regular);
}
.card-room .building {
  background: var(--el-fill-color-light);
  padding: 1px 6px;
  border-radius: 4px;
}
.card-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
  font-size: 13px;
  color: var(--text-regular);
}
.detail-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.card-actions {
  border-top: 1px solid var(--el-border-color-light, #ebeef5);
  padding-top: 12px;
  display: flex;
  justify-content: flex-end;
  gap: 4px;
}

/* 分组视图样式 */
.group-view-container {
  padding: 10px 0;
}
.building-group-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  border: 1px solid #ebeef5;
}
.building-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f0f2f5;
}
.building-name {
  font-size: 18px;
  font-weight: bold;
  color: #303133;
  border-left: 4px solid #409EFF;
  padding-left: 10px;
}
.floor-row {
  display: flex;
  align-items: flex-start;
  margin-bottom: 16px;
}
.floor-row:last-child {
  margin-bottom: 0;
}
.floor-label {
  width: 60px;
  flex-shrink: 0;
  font-weight: bold;
  color: #909399;
  padding-top: 6px;
}
.floor-tenants {
  flex: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.mini-tenant-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 16px;
  background: #f4f4f5;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}
.mini-tenant-chip:hover {
  background: #ecf5ff;
  border-color: #d9ecff;
}
.mini-tenant-chip .room-no {
  font-weight: bold;
  color: #303133;
}
.mini-tenant-chip .tenant-name {
  font-size: 13px;
  color: #606266;
}
.mini-tenant-chip.status-active {
  border-left: 3px solid #67C23A;
}
.mini-tenant-chip.status-inactive {
  border-left: 3px solid #909399;
  opacity: 0.7;
}
</style>