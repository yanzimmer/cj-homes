<template>
  <div>
  <div class="rooms-container">
    <div class="page-header">
      <h2>房间详情</h2>
      <div class="header-operations">
        <el-input
          v-model="searchQuery"
          placeholder="搜索房间号/楼层/类型"
          class="search-input"
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
          <el-radio-button label="floor">
            <el-icon><Grid /></el-icon> 楼层
          </el-radio-button>
        </el-radio-group>

        <el-button class="toolbar-btn" type="primary" @click="openAddDialog">添加房间</el-button>
        <el-button class="toolbar-btn" type="danger" :disabled="selectedRooms.length === 0" :loading="batchDeleting" @click="handleBatchDelete">批量删除</el-button>
        <el-dropdown trigger="click" @command="handleExportCommand">
          <el-button class="toolbar-btn" type="success">
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

    <!-- 列表视图 -->
    <div v-if="currentView === 'table'">
      <div class="table-panel">
      <el-table 
        class="rooms-table" 
        ref="roomsTableRef"
        :data="visibleRooms" 
        row-key="id"
        v-loading="loading" 
        border 
        style="width: 100%"
        :max-height="tableMaxHeight"
        @sort-change="handleSortChange"
        @selection-change="handleSelectionChange"
        @select="handleRowSelect"
      >
        <el-table-column type="selection" width="50" :selectable="rowSelectable"></el-table-column>
        <el-table-column prop="id" label="ID" min-width="80" sortable="custom" show-overflow-tooltip></el-table-column>
        <el-table-column prop="building" label="楼栋" min-width="100" sortable="custom" show-overflow-tooltip></el-table-column>

        <el-table-column prop="room_no" label="房间号" min-width="120" sortable="custom" show-overflow-tooltip></el-table-column>
        <el-table-column prop="room_type" label="房间类型" min-width="120" sortable="custom" show-overflow-tooltip>
          <template #header>
            <div style="display: flex; align-items: center;">
              <span>房间类型</span>
              <el-dropdown trigger="click" @command="handleTypeFilter">
                <el-button style="margin-left: 5px; padding: 2px 5px;" size="small">
                  <el-icon><Filter /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="all">全部</el-dropdown-item>
                    <el-dropdown-item command="单间">单间</el-dropdown-item>
                    <el-dropdown-item command="套间">套间</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="price" label="价格" min-width="120" sortable="custom" show-overflow-tooltip>
          <template #default="scope">
            {{ scope.row.price }} 元/月
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" min-width="100" sortable="custom" show-overflow-tooltip>
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
                    <el-dropdown-item command="空闲">空闲</el-dropdown-item>
                    <el-dropdown-item command="已入住">已入住</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
          <template #default="scope">
            <el-tag :type="scope.row.status === '已入住' ? 'danger' : 'success'">
              {{ scope.row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="tenant_count" label="租户数量" min-width="100" sortable="custom" show-overflow-tooltip></el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip></el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="scope">
            <el-button 
              size="small" 
              type="primary" 
              @click="showRoomDetails(scope.row)"
              :disabled="scope.row.status === '空闲' || scope.row.tenant_count === 0">
              详情
            </el-button>
            <el-button size="small" @click="openEditDialog(scope.row)">编辑</el-button>
            <el-button 
              size="small" 
              type="warning" 
              @click="handleCheckout(scope.row)"
              :disabled="scope.row.status === '空闲' || scope.row.tenant_count === 0">
              退租
            </el-button>
            <el-button 
              size="small" 
              type="danger" 
              :disabled="scope.row.status === '已入住'"
              :title="scope.row.status === '已入住' ? '房间有在住租户不可删除，请先办理退租' : ''"
              @click="handleDelete(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      </div>
      
      <!-- 分页控件 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="filteredRooms.length"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </div>

    <!-- 楼层分组视图 -->
    <div v-else class="floor-view-container" v-loading="loading">
      <div v-if="groupedRooms.length === 0" class="empty-state">
        <el-empty description="暂无房间数据" />
      </div>
      
      <div v-else v-for="buildingGroup in groupedRooms" :key="buildingGroup.buildingName" class="building-section">
        <h3 class="building-title">{{ buildingGroup.buildingName }} 栋</h3>
        <div v-for="floorGroup in buildingGroup.floors" :key="floorGroup.floorName" class="floor-row">
          <div class="floor-label">{{ floorGroup.floorName }} 楼</div>
          <div class="rooms-grid">
            <div 
              v-for="room in floorGroup.rooms" 
              :key="room.id" 
              class="room-card"
              :class="{ 
                'is-occupied': room.status === '已入住',
                'is-vacant': room.status === '空闲'
              }"
              @click="showRoomDetails(room)"
            >
              <div class="room-card-header">
                <span class="room-no">{{ room.room_no }}</span>
                <el-tag size="small" :type="room.status === '已入住' ? 'danger' : 'success'" effect="dark">
                  {{ room.status }}
                </el-tag>
              </div>
              <div class="room-card-body">
                <div class="info-row">
                  <span class="label">类型:</span>
                  <span class="value">{{ room.room_type }}</span>
                </div>
                <div class="info-row">
                  <span class="label">价格:</span>
                  <span class="value">¥{{ room.price }}</span>
                </div>
                <div class="info-row" v-if="room.tenant_count > 0">
                  <span class="label">租户:</span>
                  <span class="value">{{ room.tenant_count }}人</span>
                </div>
              </div>
              <div class="room-card-actions" @click.stop>
                <el-button circle size="small" :icon="Edit" @click="openEditDialog(room)" title="编辑" />
                <el-button 
                  circle 
                  size="small" 
                  type="warning" 
                  :disabled="room.status === '空闲'" 
                  @click="handleCheckout(room)" 
                  title="退租"
                >
                  <el-icon><SwitchButton /></el-icon>
                </el-button>
                <el-button 
                  circle 
                  size="small" 
                  type="danger" 
                  :disabled="room.status === '已入住'"
                  :icon="Delete" 
                  @click="handleDelete(room)" 
                  title="删除" 
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 添加/编辑房间对话框 -->
    <el-dialog :title="dialogTitle" v-model="dialogVisible" width="500px">
      <el-form :model="roomForm" :rules="rules" ref="roomFormRef" label-width="100px">
        <el-form-item label="房间号" prop="room_no">
          <el-input v-model="roomForm.room_no" placeholder="例如：401"></el-input>
          <div style="margin-top: 6px; font-size: 12px; color: #666;">
            合成房间号：{{ composedRoomNo }}
          </div>
        </el-form-item>
        <el-form-item label="楼栋" prop="building">
          <el-select v-model="roomForm.building" placeholder="请选择楼栋" style="width: 100%">
            <el-option v-for="b in buildingOptions" :key="b" :label="b" :value="b" />
          </el-select>
        </el-form-item>
        <el-form-item label="楼层" prop="floor">
          <el-input v-model="roomForm.floor" readonly></el-input>
        </el-form-item>
        <el-form-item label="房间类型" prop="room_type">
          <el-select v-model="roomForm.room_type" placeholder="请选择房间类型" style="width: 100%">
            <el-option label="单间" value="单间"></el-option>
            <el-option label="套间" value="套间"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="价格" prop="price">
          <el-input-number v-model="roomForm.price" :min="0" :precision="2" :step="100"></el-input-number>
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="roomForm.status" placeholder="请选择状态" style="width: 100%">
            <el-option label="空闲" value="空闲"></el-option>
            <el-option label="已租" value="已租"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="roomForm.description" type="textarea" :rows="3"></el-input>
        </el-form-item>
      </el-form>
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
        <p>确定要将房间 <strong>{{ checkoutRoom.room_no }}</strong> 退租吗？</p>
        <p>该操作将会将房间内所有租户 ({{ checkoutRoom.tenant_count }} 人) 标记为已退租。</p>
        <p class="warning">此操作不可撤销！</p>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="checkoutDialogVisible = false">取消</el-button>
          <el-button type="warning" @click="confirmCheckout" :loading="checkoutLoading">确认退租</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 房间详情对话框 -->
    <el-dialog title="房间详情" v-model="detailsDialogVisible" width="700px">
      <div v-loading="detailsLoading">
        <div class="room-info">
          <h3>房间信息</h3>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="房间号">{{ currentRoom.room_no }}</el-descriptions-item>
            <el-descriptions-item label="楼栋">{{ currentRoom.building }}</el-descriptions-item>
            <el-descriptions-item label="楼层">{{ currentRoom.floor }}</el-descriptions-item>
            <el-descriptions-item label="房间类型">{{ currentRoom.room_type }}</el-descriptions-item>
            <el-descriptions-item label="价格">{{ currentRoom.price }} 元/月</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="currentRoom.status === '已入住' ? 'danger' : 'success'">
                {{ currentRoom.status }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="租户数量">{{ currentRoom.tenant_count }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="tenant-list" v-if="roomTenants.length > 0">
          <h3>入住人员</h3>
          <el-table :data="roomTenants" border style="width: 100%">
            <el-table-column prop="name" label="姓名" width="100"></el-table-column>
            <el-table-column prop="gender" label="性别" width="80"></el-table-column>
            <el-table-column prop="phone" label="电话" width="120"></el-table-column>
            <el-table-column prop="id_card" label="身份证号" width="180"></el-table-column>
            <el-table-column prop="check_in_date" label="入住日期" width="120"></el-table-column>
            <el-table-column prop="check_out_date" label="到期日期" width="120"></el-table-column>
          </el-table>
        </div>
        <div v-else class="no-tenants">
          <el-empty description="暂无入住人员"></el-empty>
        </div>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="detailsDialogVisible = false">关闭</el-button>
        </span>
      </template>
    </el-dialog>
  </div>

  <!-- 隐藏打印区域：包含完整的筛选后房间列表，用于 PDF 截图渲染，保证中文显示正确 -->
  <div v-if="showPrintArea" ref="printAreaRef" class="print-area">
    <h2 style="text-align:center; margin-bottom: 12px;">房间列表</h2>
    <table class="print-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>房间号</th>
          <th>楼栋</th>
          <th>楼层</th>
          <th>房间类型</th>
          <th>价格</th>
          <th>状态</th>
          <th>租户数量</th>
          <th>描述</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in filteredRooms" :key="r.id">
          <td>{{ r.id }}</td>
          <td>{{ r.room_no }}</td>
          <td>{{ r.building }}</td>
          <td>{{ r.floor }}</td>
          <td>{{ r.room_type }}</td>
          <td>{{ r.price }}</td>
          <td>{{ r.status }}</td>
          <td>{{ r.tenant_count }}</td>
          <td>{{ r.description }}</td>
        </tr>
      </tbody>
    </table>
  </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed, nextTick, watch } from 'vue'
import { roomsApi } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Filter, List, Grid, Edit, Delete, SwitchButton } from '@element-plus/icons-vue'
import * as XLSX from 'xlsx'
import { jsPDF } from 'jspdf'
import autoTable from 'jspdf-autotable'
import { Document, Packer, Paragraph, Table as DocxTable, TableRow, TableCell, TextRun } from 'docx'
import { saveAs } from 'file-saver'
import html2canvas from 'html2canvas'

// 视图切换
const currentView = ref('table') // 'table' or 'floor'

// 数据
const rooms = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('添加房间')
const submitting = ref(false)
const roomFormRef = ref(null)
const isEdit = ref(false)
// 批量选择与删除相关
const roomsTableRef = ref(null)
const selectedRooms = ref([])
const batchDeleting = ref(false)

// 排序、搜索和筛选相关// 搜索、排序和筛选
const searchQuery = ref('')
const sortBy = ref('')
const sortOrder = ref('')
const roomTypeFilter = ref('all')
const statusFilter = ref('all')

// 楼栋选项（A-Z）与合成房间号预览
const buildingOptions = Array.from({ length: 26 }, (_, i) => String.fromCharCode(65 + i))
const composedRoomNo = computed(() => {
  const letter = (roomForm.building || '').toUpperCase()
  const digits = String(roomForm.room_no || '').replace(/\D/g, '')
  return letter && digits ? `${letter}-${digits}` : digits
})

// 分页相关
const currentPage = ref(1)
const pageSize = ref(20)
const showPrintArea = ref(false)
const printAreaRef = ref(null)
// （重复声明已移除）

// 表格高度自适应：根据窗口动态计算可视高度
const calcTableMaxHeight = () => Math.max(window.innerHeight - 260, 300)
const tableMaxHeight = ref(calcTableMaxHeight())
const handleResize = () => { tableMaxHeight.value = calcTableMaxHeight() }

// 处理页面大小变化
const handleSizeChange = (size) => {
  pageSize.value = size
  currentPage.value = 1
}

// 处理当前页变化
const handleCurrentChange = (page) => {
  currentPage.value = page
}

// 过滤和排序后的房间列表退租相关
const checkoutDialogVisible = ref(false)
const checkoutLoading = ref(false)
const checkoutRoom = ref({})

// 详情相关
const detailsDialogVisible = ref(false)
const detailsLoading = ref(false)
const currentRoom = ref({})
const roomTenants = ref([])

const roomForm = reactive({
  id: null,
  room_no: '',
  building: '',
  floor: '',
  room_type: '',
  price: 0,
  status: '空闲',
  description: ''
})

// 根据房间号自动填充楼层（例如 401 -> 4楼；1001 -> 10楼）
watch(() => roomForm.room_no, (val) => {
  const digits = String(val || '').replace(/\D/g, '')
  // 保持房间号为纯数字
  if (digits !== val) roomForm.room_no = digits
  if (digits.length >= 3) {
    const num = parseInt(digits, 10)
    roomForm.floor = String(Math.floor(num / 100))
  } else {
    roomForm.floor = ''
  }
})

// 解析已有房间号（如 A-401）
const parseCombinedRoomNo = (s) => {
  const str = String(s || '')
  const m = str.match(/^([A-Za-z])[\-_]?(\d+)$/)
  if (m) return { building: m[1].toUpperCase(), number: m[2] }
  return { building: '', number: str.replace(/\D/g, '') }
}

// 过滤和排序后的房间列表
const filteredRooms = computed(() => {
  let result = [...rooms.value]
  
  // 应用搜索过滤
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(room => 
      room.room_no.toLowerCase().includes(query) ||
      room.floor.toLowerCase().includes(query) ||
      room.room_type.toLowerCase().includes(query) ||
      (room.description && room.description.toLowerCase().includes(query))
    )
  }
  
  // 应用房间类型过滤
  if (roomTypeFilter.value !== 'all') {
    result = result.filter(room => room.room_type === roomTypeFilter.value)
  }
  
  // 应用状态过滤
  if (statusFilter.value !== 'all') {
    result = result.filter(room => room.status === statusFilter.value)
  }
  
  // 应用排序
  if (sortBy.value) {
    result.sort((a, b) => {
      let aValue = a[sortBy.value]
      let bValue = b[sortBy.value]
      
      // 处理数字类型
      if (sortBy.value === 'price' || sortBy.value === 'tenant_count') {
        aValue = Number(aValue)
        bValue = Number(bValue)
      }
      
      if (aValue < bValue) return sortOrder.value === 'ascending' ? -1 : 1
      if (aValue > bValue) return sortOrder.value === 'ascending' ? 1 : -1
      return 0
    })
  }
  
  return result
})

// 当前页可见数据（分页后）
const visibleRooms = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = currentPage.value * pageSize.value
  return filteredRooms.value.slice(start, end)
})

// 楼层分组数据
const groupedRooms = computed(() => {
  const groups = {}
  // 使用筛选后的数据，以便在楼层视图中也能搜索过滤
  filteredRooms.value.forEach(room => {
    const b = room.building || '未分类'
    const f = room.floor || '其他'
    if (!groups[b]) groups[b] = {}
    if (!groups[b][f]) groups[b][f] = []
    groups[b][f].push(room)
  })
  
  // 转换为数组以保证渲染顺序（使用自然排序）
  return Object.keys(groups)
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
    .map(bKey => {
      const floors = Object.keys(groups[bKey])
        .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
        .map(fKey => ({
          floorName: fKey,
          rooms: groups[bKey][fKey]
        }))
      return {
        buildingName: bKey,
        floors: floors
      }
    })
})

// 处理排序变化
const handleSortChange = ({ prop, order }) => {
  sortBy.value = prop
  sortOrder.value = order
}
// 仅空闲房间可勾选；全选只会选中空闲房间
const rowSelectable = (row) => row.status === '空闲'
const handleSelectionChange = (val) => {
  selectedRooms.value = val
  console.log('当前选中房间：', val.map(r => ({ id: r.id, room_no: r.room_no, status: r.status })))
}
const handleRowSelect = (selection, row) => {
  console.log('单行选择变化：', { room_no: row.room_no, status: row.status }, '当前选择数：', selection.length)
}
// 使用 Element Plus 内置全选逻辑并结合 :selectable，避免事件与内置行为冲突

// 处理房间类型筛选
const handleTypeFilter = (command) => {
  roomTypeFilter.value = command
}

// 处理状态筛选
const handleStatusFilter = (command) => {
  statusFilter.value = command
}

// 处理搜索清除
const handleSearchClear = () => {
  searchQuery.value = ''
}

const rules = {
  room_no: [{ required: true, message: '请输入房间号', trigger: 'blur' }],
  building: [{ required: true, message: '请选择楼栋', trigger: 'change' }],
  floor: [{ required: true, message: '请输入楼层', trigger: 'blur' }],
  room_type: [{ required: true, message: '请选择房间类型', trigger: 'change' }],
  price: [{ required: true, message: '请输入价格', trigger: 'blur' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }]
}

// 生命周期
onMounted(() => {
  fetchRooms()
})

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})

// 方法
const fetchRooms = async () => {
  loading.value = true
  try {
    const response = await roomsApi.listRooms({ fields: 'id,room_no,room_display,building,room_type,price,deposit,description,status,tenant_count,has_water_meter_img,has_electricity_meter_img' })
    rooms.value = response.data.rooms || []
  } catch (error) {
    ElMessage.error('获取房间列表失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// 显示房间详情
const showRoomDetails = async (room) => {
  currentRoom.value = room
  detailsDialogVisible.value = true
  detailsLoading.value = true
  
  try {
    const response = await roomsApi.getRoomTenants(room.room_no)
    roomTenants.value = response.data.tenants || []
  } catch (error) {
    ElMessage.error('获取房间租户信息失败：' + error.message)
    roomTenants.value = []
  } finally {
    detailsLoading.value = false
  }
}

// 处理退租
const handleCheckout = (room) => {
  checkoutRoom.value = room
  checkoutDialogVisible.value = true
}

// 确认退租
const confirmCheckout = async () => {
  checkoutLoading.value = true
  try {
    const response = await roomsApi.checkoutRoom(checkoutRoom.value.room_no)
    ElMessage.success('房间退租成功')
    checkoutDialogVisible.value = false
    fetchRooms() // 刷新房间列表
  } catch (error) {
    console.error('退租失败:', error)
    ElMessage.error(error.response?.data?.error || '退租失败')
  } finally {
    checkoutLoading.value = false
  }
}

const resetForm = () => {
  if (roomFormRef.value) {
    roomFormRef.value.resetFields()
  }
  roomForm.id = null
  roomForm.room_no = ''
  roomForm.building = ''
  roomForm.floor = ''
  roomForm.room_type = ''
  roomForm.price = 0
  roomForm.status = '空闲'
  roomForm.description = ''
}

const openAddDialog = () => {
  resetForm()
  isEdit.value = false
  dialogTitle.value = '添加房间'
  dialogVisible.value = true
}

const openEditDialog = (room) => {
  resetForm()
  isEdit.value = true
  dialogTitle.value = '编辑房间'
  // 解析已有房间号，填充楼栋与数字部分
  const parsed = parseCombinedRoomNo(room.room_no)
  roomForm.id = room.id
  roomForm.room_no = parsed.number
  roomForm.building = room.building || parsed.building
  // 自动推导楼层（优先数字部分推导，其次保留原值）
  if (parsed.number && parsed.number.length >= 3) {
    roomForm.floor = String(Math.floor(parseInt(parsed.number, 10) / 100))
  } else {
    roomForm.floor = room.floor || ''
  }
  roomForm.room_type = room.room_type
  roomForm.price = room.price
  roomForm.status = room.status || '空闲'
  roomForm.description = room.description || ''
  dialogVisible.value = true
}

const handleSubmit = async () => {
  if (!roomFormRef.value) return
  
  await roomFormRef.value.validate(async (valid) => {
    if (valid) {
      submitting.value = true
      try {
        const payload = { ...roomForm, room_no: composedRoomNo.value }
        if (isEdit.value) {
          await roomsApi.updateRoom(roomForm.id, payload)
          ElMessage.success('房间更新成功')
        } else {
          await roomsApi.addRoom(payload)
          ElMessage.success('房间添加成功')
        }
        dialogVisible.value = false
        fetchRooms()
      } catch (error) {
        ElMessage.error(isEdit.value ? '更新房间失败' : '添加房间失败')
        console.error(error)
      } finally {
        submitting.value = false
      }
    }
  })
}

const handleDelete = (room) => {
  if (room?.status === '已入住') {
    ElMessage.warning('在住状态不可删除，请先办理退租')
    return
  }
  ElMessageBox.confirm(`确定要删除房间 ${room.room_no} 吗？`, '警告', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await roomsApi.deleteRoom(room.id)
      ElMessage.success('房间删除成功')
      fetchRooms()
    } catch (error) {
      ElMessage.error('删除房间失败')
      console.error(error)
    }
  }).catch(() => {})
}

// 批量删除选中的空闲房间
const handleBatchDelete = async () => {
  if (!selectedRooms.value.length) {
    ElMessage.warning('请先勾选要删除的空闲房间')
    return
  }
  const count = selectedRooms.value.length
  const names = selectedRooms.value.map(r => r.room_no).join(', ')
  try {
    await ElMessageBox.confirm(`确定要删除选中的 ${count} 个房间：${names}？`, '批量删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch { return }

  batchDeleting.value = true
  try {
    const results = await Promise.allSettled(selectedRooms.value.map(r => roomsApi.deleteRoom(r.id)))
    const success = results.filter(r => r.status === 'fulfilled').length
    const failed = results.filter(r => r.status === 'rejected')
    if (!failed.length) {
      ElMessage.success(`批量删除完成，成功 ${success} 个`)
    } else {
      const errMsg = failed.map(f => f.reason?.response?.data?.error || f.reason?.message || '未知错误').join('；')
      ElMessage.warning(`批量删除部分失败：成功 ${success} 个，失败 ${failed.length} 个。原因：${errMsg}`)
    }
    await fetchRooms()
    if (roomsTableRef.value) roomsTableRef.value.clearSelection()
    selectedRooms.value = []
  } catch (e) {
    console.error('批量删除异常：', e)
    ElMessage.error('批量删除失败')
  } finally {
    batchDeleting.value = false
  }
}

// 导出处理
const handleExportCommand = (cmd) => {
  if (cmd === 'excel') exportToExcel()
  else if (cmd === 'word') exportToWord()
  else if (cmd === 'pdf') exportToPDF()
}

const getExportRows = () => {
  const list = filteredRooms.value
  return list.map(r => ({
    ID: r.id ?? '',
    房间号: r.room_no ?? '',
    楼栋: r.building ?? '',
    楼层: r.floor ?? '',
    房间类型: r.room_type ?? '',
    价格: r.price ?? '',
    状态: r.status ?? '',
    租户数量: r.tenant_count ?? '',
    描述: r.description ?? ''
  }))
}

const exportToExcel = () => {
  try {
    const rows = getExportRows()
    const ws = XLSX.utils.json_to_sheet(rows)
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, '房间列表')
    XLSX.writeFile(wb, `房间列表_${new Date().toLocaleDateString()}.xlsx`)
    ElMessage.success('Excel 导出完成')
  } catch (e) {
    console.error('导出 Excel 失败', e)
    ElMessage.error('导出 Excel 失败')
  }
}

const exportToWord = async () => {
  try {
    const rows = getExportRows()
    const headerCells = ['ID','房间号','楼栋','楼层','房间类型','价格','状态','租户数量','描述'].map(text =>
      new TableCell({ children: [new Paragraph({ children: [new TextRun(String(text))] })] })
    )
    const tableRows = [
      new TableRow({ children: headerCells }),
      ...rows.map(r => new TableRow({
        children: [
          new TableCell({ children: [new Paragraph(String(r.ID))] }),
          new TableCell({ children: [new Paragraph(String(r['房间号']))] }),
          new TableCell({ children: [new Paragraph(String(r['楼栋']))] }),
          new TableCell({ children: [new Paragraph(String(r['楼层']))] }),
          new TableCell({ children: [new Paragraph(String(r['房间类型']))] }),
          new TableCell({ children: [new Paragraph(String(r['价格']))] }),
          new TableCell({ children: [new Paragraph(String(r['状态']))] }),
          new TableCell({ children: [new Paragraph(String(r['租户数量']))] }),
          new TableCell({ children: [new Paragraph(String(r['描述']))] })
        ]
      }))
    ]
    const doc = new Document({
      sections: [{
        children: [
          new Paragraph({ children: [new TextRun({ text: '房间列表', bold: true })] }),
          new DocxTable({ rows: tableRows })
        ]
      }]
    })
    const blob = await Packer.toBlob(doc)
    saveAs(blob, `房间列表_${new Date().toLocaleDateString()}.docx`)
    ElMessage.success('Word 导出完成')
  } catch (e) {
    console.error('导出 Word 失败', e)
    ElMessage.error('导出 Word 失败')
  }
}

const exportToPDF = async () => {
  try {
    // 展示隐藏打印区域，确保 DOM 渲染完成后截图
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

    pdf.save(`房间列表_${new Date().toLocaleDateString()}.pdf`)
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
.rooms-container {
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

.header-operations {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.search-input {
  width: 220px;
}

.toolbar-btn {
  margin-left: 0 !important;
}

.table-panel {
  background: var(--card-bg);
  border: 1px solid var(--surface-border);
  border-radius: 16px;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
  padding: 10px 10px 16px;
}

.pagination-container {
  margin-top: 16px;
  display: flex;
  justify-content: center;
  padding-top: 12px;
  border-top: 1px solid var(--surface-border);
}

:deep(.rooms-table) {
  --el-table-header-bg-color: var(--surface-muted);
  --el-table-tr-bg-color: var(--card-bg);
  --el-table-row-hover-bg-color: rgba(37, 99, 235, 0.06);
  --el-table-border-color: var(--surface-border);
  border-radius: 12px;
  overflow: hidden;
}

:deep(.rooms-table .el-table__header-wrapper th.el-table__cell) {
  font-weight: 700;
  color: var(--text-main);
  height: 48px;
}

:deep(.rooms-table .el-table__body-wrapper td.el-table__cell) {
  padding: 12px 0;
}

:deep(.rooms-table .el-table__fixed-right::before),
:deep(.rooms-table .el-table__fixed::before) {
  background-color: transparent;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.checkout-confirm .warning {
  color: #F56C6C;
  font-weight: bold;
}

.room-info {
  margin-bottom: 20px;
}

.tenant-list {
  margin-top: 20px;
}

.no-tenants {
  margin-top: 20px;
  text-align: center;
}

/* 楼层分组视图样式 */
.floor-view-container {
  padding: 10px 0;
}

.building-section {
  margin-bottom: 30px;
}

.building-title {
  font-size: 18px;
  color: #303133;
  border-left: 4px solid #409EFF;
  padding-left: 10px;
  margin-bottom: 15px;
}

.floor-row {
  display: flex;
  margin-bottom: 15px;
  align-items: flex-start;
}

.floor-label {
  width: 60px;
  font-weight: bold;
  color: var(--text-regular);
  padding-top: 15px;
  flex-shrink: 0;
}

.rooms-grid {
  flex: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 15px;
}

.room-card {
  width: 180px;
  background: var(--card-bg);
  border-radius: 8px;
  border: 1px solid var(--el-border-color-light, #e4e7ed);
  transition: all 0.3s;
  cursor: pointer;
  position: relative;
  overflow: hidden;
}

.room-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.room-card.is-occupied {
  border-top: 3px solid #F56C6C;
}

.room-card.is-vacant {
  border-top: 3px solid #67C23A;
}

.room-card-header {
  padding: 10px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--el-border-color-light, #f0f0f0);
  background: var(--el-fill-color-light, #fafafa);
}

.room-no {
  font-size: 16px;
  font-weight: bold;
  color: var(--text-main);
}

.room-card-body {
  padding: 12px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  margin-bottom: 6px;
  color: var(--text-regular);
}

.info-row .value {
  font-weight: 500;
  color: var(--text-main);
}

.room-card-actions {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: var(--el-bg-color-overlay);
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  opacity: 0;
  transition: opacity 0.2s;
}

.room-card:hover .room-card-actions {
  opacity: 1;
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
</style>