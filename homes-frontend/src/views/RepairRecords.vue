<template>
  <div>
  <div class="repair-records-container">
    <div class="page-header">
      <h2>维修详情</h2>
      <div class="header-operations">
        <el-input
          v-model="searchQuery"
          placeholder="搜索房间号/维修类型"
          style="width: 220px; margin-right: 10px"
          clearable
          @clear="handleSearchClear"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" @click="openAddDialog">添加维修记录</el-button>
        <el-button type="danger" style="margin-left: 10px;" :disabled="multipleSelection.length === 0" @click="confirmBatchDelete">批量删除</el-button>
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
      :data="pagedRecords" 
      v-loading="loading" 
      border 
      :max-height="tableMaxHeight"
      style="width: 100%"
      @sort-change="handleSortChange"
      @selection-change="handleSelectionChange"
      row-key="id"
      :reserve-selection="true"
      ref="tableRef"
      fit
    >
      <el-table-column type="selection" width="55"></el-table-column>
      <el-table-column prop="id" label="ID" width="80" sortable="custom"></el-table-column>
      <el-table-column prop="building" label="楼栋" width="100" sortable="custom"></el-table-column>
      <el-table-column prop="room_no" label="房间号" width="100" sortable="custom"></el-table-column>
      <el-table-column prop="repair_type" label="维修类型" width="120" sortable="custom">
        <template #header>
          <div style="display: flex; align-items: center;">
            <span>维修类型</span>
            <el-dropdown trigger="click" @command="handleTypeFilter">
              <el-button style="margin-left: 5px; padding: 2px 5px;" size="small">
                <el-icon><Filter /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="all">全部</el-dropdown-item>
                  <el-dropdown-item command="水电维修">水电维修</el-dropdown-item>
                  <el-dropdown-item command="家具维修">家具维修</el-dropdown-item>
                  <el-dropdown-item command="电器维修">电器维修</el-dropdown-item>
                  <el-dropdown-item command="其他">其他</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="问题描述" min-width="120" show-overflow-tooltip></el-table-column>
      <el-table-column prop="report_date" label="报修日期" width="120" sortable="custom"></el-table-column>
      <el-table-column prop="report_by" label="报修人" width="100"></el-table-column>
      <el-table-column prop="status" label="状态" width="100" sortable="custom">
        <template #default="scope">
          <el-tag :type="getStatusType(scope.row.status)">{{ scope.row.status }}</el-tag>
        </template>
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
                  <el-dropdown-item command="待处理">待处理</el-dropdown-item>
                  <el-dropdown-item command="处理中">处理中</el-dropdown-item>
                  <el-dropdown-item command="已完成">已完成</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="repair_date" label="维修日期" width="120" sortable="custom"></el-table-column>
      <el-table-column prop="repair_cost" label="维修费用" width="100" sortable="custom">
        <template #default="scope">
          {{ scope.row.repair_cost ? `¥${scope.row.repair_cost}` : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="repair_person" label="维修人员" width="100"></el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="scope">
          <div class="operation-buttons">
            <el-button size="small" type="primary" @click="viewRecord(scope.row)">查看</el-button>
            <el-button size="small"  @click="editRecord(scope.row)">编辑</el-button>
            <el-button size="small" type="danger" @click="confirmDelete(scope.row)">删除</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-container">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="filteredRecords.length"
        layout="total, prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>

    <!-- 添加/编辑维修记录对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑维修记录' : '添加维修记录'"
      width="50%"
    >
      <el-form :model="recordForm" label-width="100px" :rules="rules" ref="recordFormRef">
        <el-form-item label="楼栋" prop="building">
          <el-select v-model="recordForm.building" placeholder="请选择楼栋" style="width: 100%" @change="handleBuildingChange">
            <el-option 
              v-for="building in buildingOptions" 
              :key="building" 
              :label="building" 
              :value="building" 
            />
          </el-select>
        </el-form-item>
        <el-form-item label="房间号" prop="room_no">
          <el-select v-model="recordForm.room_no" placeholder="请选择房间号" style="width: 100%">
            <el-option 
              v-for="room in filteredRooms" 
              :key="room.room_no" 
              :label="room.room_no" 
              :value="room.room_no" 
            />
          </el-select>
        </el-form-item>
        <el-form-item label="维修类型" prop="repair_type">
          <el-select v-model="recordForm.repair_type" placeholder="请选择维修类型" style="width: 100%">
            <el-option label="水电维修" value="水电维修" />
            <el-option label="家具维修" value="家具维修" />
            <el-option label="电器维修" value="电器维修" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item label="问题描述" prop="description">
          <el-input v-model="recordForm.description" type="textarea" :rows="3" placeholder="请描述维修问题" />
        </el-form-item>
        <el-form-item label="报修人" prop="report_by">
          <el-input v-model="recordForm.report_by" placeholder="请输入报修人姓名" />
        </el-form-item>
        <el-form-item label="报修日期" prop="report_date">
          <el-date-picker
            v-model="recordForm.report_date"
            type="date"
            placeholder="选择日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="recordForm.status" placeholder="请选择状态" style="width: 100%">
            <el-option label="待处理" value="待处理" />
            <el-option label="处理中" value="处理中" />
            <el-option label="已完成" value="已完成" />
          </el-select>
        </el-form-item>
        <template v-if="recordForm.status === '已完成' || recordForm.status === '处理中'">
          <el-form-item label="维修日期">
            <el-date-picker
              v-model="recordForm.repair_date"
              type="date"
              placeholder="选择日期"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="维修费用">
            <el-input-number v-model="recordForm.repair_cost" :min="0" :precision="2" :step="10" style="width: 100%" />
          </el-form-item>
          <el-form-item label="维修人员">
            <el-input v-model="recordForm.repair_person" placeholder="请输入维修人员姓名" />
          </el-form-item>
        </template>
        <el-form-item label="备注">
          <el-input v-model="recordForm.remarks" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitForm">确认</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 查看维修记录详情对话框 -->
    <el-dialog
      v-model="detailDialogVisible"
      title="维修记录详情"
      width="50%"
    >
      <el-descriptions :column="2" border>
        <el-descriptions-item label="ID">{{ currentRecord.id }}</el-descriptions-item>
        <el-descriptions-item label="楼栋">{{ currentRecord.building }}</el-descriptions-item>
        <el-descriptions-item label="房间号">{{ currentRecord.room_no }}</el-descriptions-item>
        <el-descriptions-item label="维修类型">{{ currentRecord.repair_type }}</el-descriptions-item>
        <el-descriptions-item label="问题描述" :span="2">{{ currentRecord.description }}</el-descriptions-item>
        <el-descriptions-item label="报修人">{{ currentRecord.report_by }}</el-descriptions-item>
        <el-descriptions-item label="报修日期">{{ currentRecord.report_date }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentRecord.status)">{{ currentRecord.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="维修日期">{{ currentRecord.repair_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="维修费用">{{ currentRecord.repair_cost ? `¥${currentRecord.repair_cost}` : '-' }}</el-descriptions-item>
        <el-descriptions-item label="维修人员">{{ currentRecord.repair_person || '-' }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ currentRecord.remarks || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>

  <!-- 隐藏打印区域：筛选后的维修记录列表，用于 PDF 截图渲染 -->
  <div v-if="showPrintArea" ref="printAreaRef" class="print-area">
    <h2 style="text-align:center; margin-bottom: 12px;">维修记录</h2>
    <table class="print-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>楼栋</th>
          <th>房间号</th>
          <th>维修类型</th>
          <th>问题描述</th>
          <th>报修日期</th>
          <th>报修人</th>
          <th>状态</th>
          <th>维修日期</th>
          <th>维修费用</th>
          <th>维修人员</th>
          <th>备注</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in filteredRecords" :key="r.id">
          <td>{{ r.id }}</td>
          <td>{{ r.building }}</td>
          <td>{{ r.room_no }}</td>
          <td>{{ r.repair_type }}</td>
          <td>{{ r.description }}</td>
          <td>{{ r.report_date }}</td>
          <td>{{ r.report_by }}</td>
          <td>{{ r.status }}</td>
          <td>{{ r.repair_date }}</td>
          <td>{{ r.repair_cost }}</td>
          <td>{{ r.repair_person }}</td>
          <td>{{ r.remarks }}</td>
        </tr>
      </tbody>
    </table>
  </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Filter } from '@element-plus/icons-vue'
import { repairRecordsApi } from '../api/repairRecords'
import { roomsApi } from '../api'
import * as XLSX from 'xlsx'
import { jsPDF } from 'jspdf'
import { Document, Packer, Paragraph, Table as DocxTable, TableRow, TableCell, TextRun } from 'docx'
import { saveAs } from 'file-saver'
import html2canvas from 'html2canvas'

// 数据加载状态
const loading = ref(false)

// 维修记录列表
const records = ref([])

// 批量选择
const multipleSelection = ref([])
const tableRef = ref(null)
// 自适应表格最大高度（内容少时不强制撑满视口）
const calcTableMaxHeight = () => Math.max(window.innerHeight - 220, 320)
const tableMaxHeight = ref(calcTableMaxHeight())
const handleResize = () => { tableMaxHeight.value = calcTableMaxHeight() }

// 分页相关
const currentPage = ref(1)
const pageSize = ref(10)
const showPrintArea = ref(false)
const printAreaRef = ref(null)

// 搜索和筛选
const searchQuery = ref('')
const typeFilter = ref('all')
const statusFilter = ref('all')
const sortBy = ref({ prop: 'report_date', order: 'descending' })

// 对话框控制
const dialogVisible = ref(false)
const detailDialogVisible = ref(false)
const isEdit = ref(false)
const recordFormRef = ref(null)

// 当前操作的记录
const currentRecord = ref({})

// 房间和楼栋数据
const allRooms = ref([])
const buildingOptions = ref([])
const filteredRooms = ref([])

// 表单数据
const recordForm = ref({
  building: '',
  room_no: '',
  repair_type: '',
  description: '',
  report_by: '',
  report_date: new Date().toISOString().split('T')[0],
  status: '待处理',
  repair_date: '',
  repair_cost: null,
  repair_person: '',
  remarks: ''
})

// 表单验证规则
const rules = {
  building: [{ required: true, message: '请选择楼栋', trigger: 'change' }],
  room_no: [{ required: true, message: '请选择房间号', trigger: 'change' }],
  repair_type: [{ required: true, message: '请选择维修类型', trigger: 'change' }],
  description: [{ required: true, message: '请描述维修问题', trigger: 'blur' }],
  report_by: [{ required: true, message: '请输入报修人姓名', trigger: 'blur' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }]
}

// 过滤后的记录列表
const filteredRecords = computed(() => {
  let result = records.value

  // 搜索过滤
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(record => 
      record.room_no.toLowerCase().includes(query) ||
      record.repair_type.toLowerCase().includes(query) ||
      record.description.toLowerCase().includes(query) ||
      record.report_by.toLowerCase().includes(query)
    )
  }

  // 类型过滤
  if (typeFilter.value !== 'all') {
    result = result.filter(record => record.repair_type === typeFilter.value)
  }

  // 状态过滤
  if (statusFilter.value !== 'all') {
    result = result.filter(record => record.status === statusFilter.value)
  }

  // 排序
  if (sortBy.value.prop) {
    const prop = sortBy.value.prop
    const isDesc = sortBy.value.order === 'descending'
    result = [...result].sort((a, b) => {
      if (a[prop] === b[prop]) return 0
      if (a[prop] === null || a[prop] === undefined) return isDesc ? -1 : 1
      if (b[prop] === null || b[prop] === undefined) return isDesc ? 1 : -1
      return isDesc 
        ? (a[prop] > b[prop] ? -1 : 1)
        : (a[prop] < b[prop] ? -1 : 1)
    })
  }

  return result
})

// 当前页数据（稳定引用供表格选择使用）
const pagedRecords = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = currentPage.value * pageSize.value
  return filteredRecords.value.slice(start, end)
})
// 当过滤结果或每页大小变化导致总页数变少时，自动回退页码避免出现空页
watch([filteredRecords, pageSize], () => {
  const total = filteredRecords.value.length
  const maxPage = Math.max(1, Math.ceil(total / pageSize.value))
  if (currentPage.value > maxPage) currentPage.value = maxPage
})
// 搜索变更时回到第一页，提升体验
watch(searchQuery, () => { currentPage.value = 1 })

// 获取状态对应的标签类型
const getStatusType = (status) => {
  switch (status) {
    case '待处理': return 'warning'
    case '处理中': return 'primary'
    case '已完成': return 'success'
    default: return 'info'
  }
}

// 加载维修记录数据
const loadRecords = async () => {
  loading.value = true
  try {
    const response = await repairRecordsApi.listRepairRecords()
    records.value = response.data.repair_records || []
  } catch (error) {
    console.error('加载维修记录失败', error)
    ElMessage.error('加载维修记录失败')
  } finally {
    loading.value = false
  }
}

// 搜索清除
const handleSearchClear = () => {
  searchQuery.value = ''
}

// 类型筛选
const handleTypeFilter = (command) => {
  typeFilter.value = command
}

// 状态筛选
const handleStatusFilter = (command) => {
  statusFilter.value = command
}

// 排序变化
const handleSortChange = ({ prop, order }) => {
  sortBy.value = { prop, order }
}

// 分页变化
const handlePageChange = (page) => {
  currentPage.value = page
}

// 选择变化
const handleSelectionChange = (val) => {
  multipleSelection.value = val
}

// 加载房间数据
const loadRooms = async () => {
  try {
    const response = await roomsApi.listRooms()
    allRooms.value = response.data.rooms || []
    
    // 提取所有不同的楼栋
    const buildings = new Set(allRooms.value.map(room => room.building).filter(Boolean))
    buildingOptions.value = Array.from(buildings)
  } catch (error) {
    console.error('加载房间数据失败', error)
    ElMessage.error('加载房间数据失败')
  }
}

// 处理楼栋变化，过滤房间列表
const handleBuildingChange = (building) => {
  recordForm.value.room_no = '' // 清空房间选择
  filteredRooms.value = allRooms.value.filter(room => room.building === building)
}

// 打开添加对话框
const openAddDialog = () => {
  isEdit.value = false
  recordForm.value = {
    building: '',
    room_no: '',
    repair_type: '',
    description: '',
    report_by: '',
    report_date: new Date().toISOString().split('T')[0],
    status: '待处理',
    repair_date: '',
    repair_cost: null,
    repair_person: '',
    remarks: ''
  }
  filteredRooms.value = [] // 清空过滤的房间列表
  dialogVisible.value = true
}

// 查看记录详情
const viewRecord = (row) => {
  currentRecord.value = { ...row }
  detailDialogVisible.value = true
}

// 编辑记录
const editRecord = (row) => {
  isEdit.value = true
  recordForm.value = { ...row }
  
  // 根据当前楼栋过滤房间列表
  if (row.building) {
    filteredRooms.value = allRooms.value.filter(room => room.building === row.building)
  }
  
  dialogVisible.value = true
}

// 确认删除
const confirmDelete = (row) => {
  ElMessageBox.confirm(
    `确定要删除房间 ${row.room_no} 的维修记录吗？`,
    '删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(() => {
    deleteRecord(row.id)
  }).catch(() => {})
}

// 批量删除确认
const confirmBatchDelete = () => {
  if (!multipleSelection.value.length) return
  ElMessageBox.confirm(
    `确定要批量删除选中的 ${multipleSelection.value.length} 条维修记录吗？`,
    '批量删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(() => {
    batchDeleteRecords()
  }).catch(() => {})
}

// 删除记录
const deleteRecord = async (id) => {
  loading.value = true
  try {
    await repairRecordsApi.deleteRepairRecord(id)
    ElMessage.success('删除成功')
    loadRecords()
  } catch (error) {
    console.error('删除维修记录失败', error)
    ElMessage.error('删除维修记录失败')
  } finally {
    loading.value = false
  }
}

// 批量删除（顺序执行，聚合提示）
const batchDeleteRecords = async () => {
  if (!multipleSelection.value.length) return
  loading.value = true
  const failures = []
  let successCount = 0

  for (const row of multipleSelection.value) {
    try {
      await repairRecordsApi.deleteRepairRecord(row.id)
      successCount++
      // 轻微延时以减少并发写入对SQLite的锁竞争
      await new Promise(r => setTimeout(r, 50))
    } catch (error) {
      const msg = error?.response?.data?.message || error?.message || '删除失败'
      failures.push(`${row.room_no || ''}(ID:${row.id})：${msg}`)
      await new Promise(r => setTimeout(r, 50))
    }
  }

  try {
    await loadRecords()
  } finally {
    multipleSelection.value = []
    loading.value = false
  }

  if (failures.length === 0) {
    ElMessage.success(`批量删除完成：成功 ${successCount} 项`)
  } else {
    ElMessage.error(`批量删除完成：成功 ${successCount} 项，失败 ${failures.length} 项`)
    console.warn('批量删除失败详情：\n' + failures.join('\n'))
  }
}

// 提交表单
const submitForm = async () => {
  if (!recordFormRef.value) return
  
  await recordFormRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        const formData = { ...recordForm.value }
        
        if (isEdit.value) {
          await repairRecordsApi.updateRepairRecord(formData.id, formData)
          ElMessage.success('维修记录更新成功')
        } else {
          await repairRecordsApi.addRepairRecord(formData)
          ElMessage.success('维修记录添加成功')
        }
        
        dialogVisible.value = false
        loadRecords()
      } catch (error) {
        console.error('保存维修记录失败', error)
        ElMessage.error('保存维修记录失败')
      } finally {
        loading.value = false
      }
    }
  })
}

// 页面加载时获取数据 & 监听窗口变化
onMounted(async () => {
  await loadRooms() // 先加载房间数据
  await loadRecords() // 再加载维修记录
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})

// 导出相关
const handleExportCommand = (cmd) => {
  if (cmd === 'excel') return exportToExcel()
  if (cmd === 'word') return exportToWord()
  if (cmd === 'pdf') return exportToPDF()
}

const getExportRows = () => {
  return filteredRecords.value.map(r => ({
    ID: r.id,
    楼栋: r.building,
    房间号: r.room_no,
    维修类型: r.repair_type,
    问题描述: r.description,
    报修日期: r.report_date,
    报修人: r.report_by,
    状态: r.status,
    维修日期: r.repair_date,
    维修费用: r.repair_cost,
    维修人员: r.repair_person,
    备注: r.remarks
  }))
}

const exportToExcel = () => {
  try {
    const rows = getExportRows()
    const ws = XLSX.utils.json_to_sheet(rows)
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, '维修记录')
    XLSX.writeFile(wb, `维修记录_${new Date().toLocaleDateString()}.xlsx`)
    ElMessage.success('Excel 导出完成')
  } catch (e) {
    console.error('导出 Excel 失败', e)
    ElMessage.error('导出 Excel 失败')
  }
}

const exportToWord = async () => {
  try {
    const rows = getExportRows()
    const headerCells = ['ID','楼栋','房间号','维修类型','问题描述','报修日期','报修人','状态','维修日期','维修费用','维修人员','备注'].map(text =>
      new TableCell({ children: [new Paragraph({ children: [new TextRun(String(text))] })] })
    )
    const tableRows = [
      new TableRow({ children: headerCells }),
      ...rows.map(r => new TableRow({
        children: [
          new TableCell({ children: [new Paragraph(String(r.ID))] }),
          new TableCell({ children: [new Paragraph(String(r['楼栋']))] }),
          new TableCell({ children: [new Paragraph(String(r['房间号']))] }),
          new TableCell({ children: [new Paragraph(String(r['维修类型']))] }),
          new TableCell({ children: [new Paragraph(String(r['问题描述']))] }),
          new TableCell({ children: [new Paragraph(String(r['报修日期']))] }),
          new TableCell({ children: [new Paragraph(String(r['报修人']))] }),
          new TableCell({ children: [new Paragraph(String(r['状态']))] }),
          new TableCell({ children: [new Paragraph(String(r['维修日期']))] }),
          new TableCell({ children: [new Paragraph(String(r['维修费用']))] }),
          new TableCell({ children: [new Paragraph(String(r['维修人员']))] }),
          new TableCell({ children: [new Paragraph(String(r['备注']))] })
        ]
      }))
    ]
    const doc = new Document({ sections: [{ children: [ new DocxTable({ rows: tableRows }) ] }] })
    const blob = await Packer.toBlob(doc)
    saveAs(blob, `维修记录_${new Date().toLocaleDateString()}.docx`)
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
    pdf.save(`维修记录_${new Date().toLocaleDateString()}.pdf`)
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
.repair-records-container {
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
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: center;
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