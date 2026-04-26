<template>
  <div>
  <div class="moves-container">
    <div class="page-header">
      <div class="header-operations">
        <el-input
          class="search-input"
          v-model="searchQuery"
          placeholder="搜索租户/房间/日期/原因"
          clearable
          @clear="handleSearchClear"
        />
        <el-button class="toolbar-btn" type="primary" @click="openMoveDialog">新增搬迁</el-button>
        <el-button class="toolbar-btn" type="danger" :disabled="multipleSelection.length === 0" @click="confirmBatchDelete">批量删除</el-button>
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

    <el-tabs v-model="activeTab">
      <el-tab-pane label="搬迁详情" name="records">
        <el-table
          class="moves-table"
          :data="paginatedMoves"
          v-loading="loading"
          border
          style="width: 100%"
          :max-height="tableMaxHeight"
          @selection-change="handleSelectionChange"
          @sort-change="handleSortChange"
          row-key="id"
          :reserve-selection="true"
          ref="tableRef"
        >
          <el-table-column type="selection" width="55"></el-table-column>
          <el-table-column prop="tenant_name" label="租户姓名" min-width="120" sortable="custom" show-overflow-tooltip></el-table-column>
          <el-table-column prop="from_room" label="原房间" min-width="110" sortable="custom" show-overflow-tooltip></el-table-column>
          <el-table-column prop="to_room" label="新房间" min-width="110" sortable="custom" show-overflow-tooltip></el-table-column>
          <el-table-column prop="move_date" label="搬迁日期" min-width="130" sortable="custom" show-overflow-tooltip></el-table-column>
          <el-table-column prop="reason" label="搬迁原因" min-width="240" sortable="custom" show-overflow-tooltip></el-table-column>
          <el-table-column label="操作" min-width="120" fixed="right">
            <template #default="scope">
              <el-button size="small" type="danger" @click="confirmDelete(scope.row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        
        <div class="pagination-container">
          <el-pagination
            v-model:current-page="currentPage"
            :page-size="pageSize"
            :total="filteredMoves.length"
            layout="total, prev, pager, next"
            @current-change="handlePageChange"
          />
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 搬迁对话框 -->
    <el-dialog title="租户搬迁" v-model="moveDialogVisible" width="500px">
      <el-form :model="moveForm" :rules="moveRules" ref="moveFormRef" label-width="100px">
        <!-- 搬迁方式选择 -->
        <el-form-item label="搬迁方式" prop="move_type">
          <el-radio-group v-model="moveForm.move_type" @change="handleMoveTypeChange">
            <el-radio :label="1">选择租户搬迁</el-radio>
            <el-radio :label="2">整间搬迁</el-radio>
          </el-radio-group>
        </el-form-item>
        
        <!-- 选择租户搬迁 -->
        <template v-if="moveForm.move_type === 1">
          <el-form-item label="租户" prop="tenant_id">
            <el-select v-model="moveForm.tenant_id" placeholder="请选择租户" style="width: 100%" @change="handleTenantChange">
              <el-option 
                v-for="(tenant, index) in tenants" 
                :key="index" 
                :label="`${tenant.name || '未命名租户'} - ${tenant.id_card || '无身份证'} - ${tenant.phone || '无手机号'}`" 
                :value="tenant.id || ''">
              </el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="原房间" prop="from_room">
            <el-input v-model="moveForm.from_room" disabled></el-input>
          </el-form-item>
        </template>
        
        <!-- 整间搬迁 -->
        <template v-if="moveForm.move_type === 2">
          <el-form-item label="原房间" prop="from_room_whole">
            <el-select v-model="moveForm.from_room_whole" placeholder="请选择原房间" style="width: 100%">
              <el-option 
                v-for="(room, index) in allRooms" 
                :key="index" 
                :label="room.room_no || ''" 
                :value="room.room_no || ''">
              </el-option>
            </el-select>
          </el-form-item>
        </template>
        
        <el-form-item label="新房间" prop="to_room">
          <el-select v-model="moveForm.to_room" placeholder="请选择新房间" style="width: 100%">
            <template v-if="availableRooms.length > 0">
              <el-option 
                v-for="(room, index) in availableRooms" 
                :key="index" 
                :label="room.room_no || ''" 
                :value="room.room_no || ''">
              </el-option>
            </template>
          </el-select>
        </el-form-item>
        <el-form-item label="搬迁原因" prop="reason">
          <el-input v-model="moveForm.reason" type="textarea" :rows="3"></el-input>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="moveDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleMoveSubmit" :loading="submitting">确定</el-button>
        </span>
      </template>
    </el-dialog>
  </div>

  <!-- 隐藏打印区域：搬迁记录列表，用于 PDF 截图渲染，保证中文显示正确 -->
  <div v-if="showPrintArea" ref="printAreaRef" class="print-area">
    <h2 style="text-align:center; margin-bottom: 12px;">搬迁记录</h2>
    <table class="print-table">
      <thead>
        <tr>
          <th>租户姓名</th>
          <th>原房间</th>
          <th>新房间</th>
          <th>搬迁日期</th>
          <th>搬迁原因</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="m in moves" :key="m.id || m.tenant_name + m.move_date">
          <td>{{ m.tenant_name }}</td>
          <td>{{ m.from_room }}</td>
          <td>{{ m.to_room }}</td>
          <td>{{ m.move_date }}</td>
          <td>{{ m.reason }}</td>
        </tr>
      </tbody>
    </table>
  </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { movesApi, tenantsApi, roomsApi } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as XLSX from 'xlsx'
import { jsPDF } from 'jspdf'
import { Document, Packer, Paragraph, Table as DocxTable, TableRow, TableCell, TextRun } from 'docx'
import { saveAs } from 'file-saver'
import html2canvas from 'html2canvas'
import { Filter } from '@element-plus/icons-vue'
import { consumeAiDraft } from '../utils/aiDrafts'

// 数据
const moves = ref([])
const tenants = ref([])
const availableRooms = ref([])
const allRooms = ref([])
const loading = ref(false)
const submitting = ref(false)
const moveDialogVisible = ref(false)
const activeTab = ref('records')
const moveFormRef = ref(null)
const showPrintArea = ref(false)
const printAreaRef = ref(null)
// 表格高度自适应
const calcTableMaxHeight = () => Math.max(window.innerHeight - 260, 300)
const tableMaxHeight = ref(calcTableMaxHeight())
const handleResize = () => { tableMaxHeight.value = calcTableMaxHeight() }

// 分页相关
const currentPage = ref(1)
const pageSize = ref(10)
// 排序相关
const sortProp = ref(null)
const sortOrder = ref(null) // 'ascending' | 'descending' | null

// 搜索相关
const searchQuery = ref('')
const filteredMoves = computed(() => {
  const q = (searchQuery.value || '').trim().toLowerCase()
  if (!q) return moves.value
  const list = Array.isArray(moves.value) ? moves.value : []
  return list.filter(m => {
    const name = String(m.tenant_name ?? '').toLowerCase()
    const from = String(m.from_room ?? '').toLowerCase()
    const to = String(m.to_room ?? '').toLowerCase()
    const date = String(m.move_date ?? '').toLowerCase()
    const reason = String(m.reason ?? '').toLowerCase()
    return (
      name.includes(q) ||
      from.includes(q) ||
      to.includes(q) ||
      date.includes(q) ||
      reason.includes(q)
    )
  })
})
const handleSearchClear = () => {
  currentPage.value = 1
}
watch(searchQuery, () => {
  currentPage.value = 1
})
const sortedMoves = computed(() => {
  if (!sortProp.value || !sortOrder.value) return filteredMoves.value
  const prop = sortProp.value
  const order = sortOrder.value
  const arr = [...filteredMoves.value]
  arr.sort((a, b) => {
    let va = a?.[prop]
    let vb = b?.[prop]
    if (prop === 'move_date') {
      const ta = new Date(va || 0).getTime() || 0
      const tb = new Date(vb || 0).getTime() || 0
      return order === 'ascending' ? ta - tb : tb - ta
    }
    if (typeof va === 'number' && typeof vb === 'number') {
      return order === 'ascending' ? va - vb : vb - va
    }
    va = String(va ?? '')
    vb = String(vb ?? '')
    return order === 'ascending' ? va.localeCompare(vb) : vb.localeCompare(va)
  })
  return arr
})
const paginatedMoves = computed(() => {
  const startIndex = (currentPage.value - 1) * pageSize.value
  const endIndex = startIndex + pageSize.value
  return sortedMoves.value.slice(startIndex, endIndex)
})
const handleSortChange = ({ prop, order }) => {
  sortProp.value = prop
  sortOrder.value = order
}

// 选择相关
const multipleSelection = ref([])
const tableRef = ref(null)
const handleSelectionChange = (val) => {
  multipleSelection.value = val
}

const handlePageChange = (page) => {
  currentPage.value = page
}

const moveForm = reactive({
  move_type: 1, // 默认为选择租户搬迁
  tenant_id: '',
  tenant_name: '',
  from_room: '',
  from_room_whole: '', // 整间搬迁时使用
  to_room: '',
  reason: ''
})

const moveRules = {
  move_type: [{ required: true, message: '请选择搬迁方式', trigger: 'change' }],
  tenant_id: [{ required: true, message: '请选择租户', trigger: 'change' }],
  from_room_whole: [{ required: true, message: '请选择原房间', trigger: 'change' }],
  to_room: [{ required: true, message: '请选择新房间', trigger: 'change' }]
}

// 生命周期
onMounted(async () => {
  window.addEventListener('resize', handleResize)
  await fetchMoves()
  await fetchTenants()
  await fetchAvailableRooms()
  applyMoveDraft()
})
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})

// 方法
const fetchMoves = async () => {
  loading.value = true
  try {
    const response = await movesApi.listMoves()
    // 确保数据是数组格式
    if (response.data && response.data.moves && Array.isArray(response.data.moves)) {
      moves.value = response.data.moves
    } else if (Array.isArray(response.data)) {
      moves.value = response.data
    } else {
      moves.value = []
      console.error('获取到的搬迁数据格式不正确:', response.data)
    }
  } catch (error) {
    ElMessage.error('获取搬迁记录失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

const fetchTenants = async () => {
  try {
    const response = await tenantsApi.listTenants()
    console.log('租户数据:', response.data)
    
    // 确保数据是数组格式
    if (response.data && response.data.tenants && Array.isArray(response.data.tenants)) {
      tenants.value = response.data.tenants
    } else if (Array.isArray(response.data)) {
      tenants.value = response.data
    } else {
      tenants.value = []
      console.error('获取到的租户数据格式不正确:', response.data)
    }
    
    console.log('处理后的租户数据:', tenants.value)
  } catch (error) {
    console.error('获取租户列表失败', error)
  }
}

const fetchAvailableRooms = async () => {
  try {
    const response = await roomsApi.listRooms()
    console.log('房间数据:', response.data)
    
    // 保存所有房间数据
    if (response.data && Array.isArray(response.data)) {
      allRooms.value = response.data
      availableRooms.value = response.data // 移除过滤条件，允许所有房间作为搬迁目标
    } else if (response.data && response.data.rooms && Array.isArray(response.data.rooms)) {
      allRooms.value = response.data.rooms
      availableRooms.value = response.data.rooms // 移除过滤条件，允许所有房间作为搬迁目标
    } else {
      availableRooms.value = []
      console.error('获取到的房间数据格式不正确:', response.data)
    }
    
    // 确保每个房间对象都有必要的属性
    availableRooms.value = availableRooms.value.map(room => {
      return {
        ...room,
        room_no: room.room_no || '',
        id: room.id || Math.random().toString(36).substring(2, 10)
      }
    })
    
    console.log('处理后的可用房间:', availableRooms.value)
    
    // 如果没有可用房间，添加一个测试房间以便调试
    if (availableRooms.value.length === 0) {
      console.warn('没有找到可用房间，添加测试房间')
      availableRooms.value = [
        { id: 'test1', room_no: '101', status: '空闲' },
        { id: 'test2', room_no: '102', status: '空闲' }
      ]
    }
  } catch (error) {
    console.error('获取可用房间失败', error)
  }
}

const resetMoveForm = () => {
  if (moveFormRef.value) {
    moveFormRef.value.resetFields()
  }
  moveForm.move_type = 1
  moveForm.tenant_id = ''
  moveForm.tenant_name = ''
  moveForm.from_room = ''
  moveForm.from_room_whole = ''
  moveForm.to_room = ''
  moveForm.reason = ''
}

const openMoveDialog = () => {
  resetMoveForm()
  moveDialogVisible.value = true
}

const applyMoveDraft = () => {
  const draft = consumeAiDraft('move')
  if (!draft) return
  openMoveDialog()
  moveForm.move_type = Number(draft.move_type || 1)
  if (draft.reason) moveForm.reason = String(draft.reason)
  if (draft.to_room) moveForm.to_room = String(draft.to_room)
  if (moveForm.move_type === 1) {
    const tenantName = String(draft.tenant_name || '').trim()
    const matchedTenant = (tenants.value || []).find(item => String(item.name || '').trim() === tenantName)
    if (matchedTenant) {
      moveForm.tenant_id = matchedTenant.id
      moveForm.tenant_name = matchedTenant.name
      moveForm.from_room = matchedTenant.room_no || String(draft.from_room || '')
    } else {
      moveForm.from_room = String(draft.from_room || '')
    }
  } else {
    moveForm.from_room_whole = String(draft.from_room_whole || '')
  }
  ElMessage.success('AI 草稿已带入搬迁表单')
}

const handleTenantChange = (tenantId) => {
  const tenant = tenants.value.find(t => t.id === tenantId)
  if (tenant) {
    moveForm.tenant_name = tenant.name
    moveForm.from_room = tenant.room_no || ''
    console.log('选择的租户:', tenant)
  }
}

const handleMoveTypeChange = () => {
  // 切换搬迁方式时重置相关字段
  if (moveForm.move_type === 1) {
    // 选择租户搬迁
    moveForm.from_room_whole = ''
  } else {
    // 整间搬迁
    moveForm.tenant_id = ''
    moveForm.tenant_name = ''
    moveForm.from_room = ''
  }
}

const handleMoveSubmit = async () => {
  if (!moveFormRef.value) return
  
  await moveFormRef.value.validate(async (valid) => {
    if (valid) {
      submitting.value = true
      try {
        // 根据搬迁方式构建不同的请求数据
        let moveData = {}
        
        if (moveForm.move_type === 1) {
          // 选择租户搬迁
          moveData = {
            tenant_id: moveForm.tenant_id,
            from_room: moveForm.from_room,
            to_room: moveForm.to_room,
            reason: moveForm.reason,
            move_type: 1
          }
        } else {
          // 整间搬迁
          moveData = {
            from_room: moveForm.from_room_whole,
            to_room: moveForm.to_room,
            reason: moveForm.reason,
            move_type: 2
          }
        }
        
        await movesApi.moveTenant(moveData)
        ElMessage.success('搬迁操作成功')
        moveDialogVisible.value = false
        fetchMoves()
        fetchTenants()
        fetchAvailableRooms()
      } catch (error) {
        ElMessage.error('搬迁操作失败')
        console.error(error)
      } finally {
        submitting.value = false
      }
    }
  })
}

// 单条删除确认与执行
const confirmDelete = (row) => {
  ElMessageBox.confirm(
    `确定要删除搬迁记录（租户：${row.tenant_name || '-'}，日期：${row.move_date || '-' }）吗？`,
    '删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(() => deleteMove(row.id)).catch(() => {})
}

const deleteMove = async (id) => {
  loading.value = true
  try {
    await movesApi.deleteMove(id)
    ElMessage.success('删除成功')
    await fetchMoves()
  } catch (error) {
    const msg = error?.response?.data?.error || error?.message || '删除失败'
    ElMessage.error(msg)
    console.error('删除搬迁记录失败', error)
  } finally {
    loading.value = false
  }
}

// 批量删除（顺序执行，聚合提示）
const confirmBatchDelete = () => {
  if (!multipleSelection.value.length) return
  ElMessageBox.confirm(
    `确定要批量删除选中的 ${multipleSelection.value.length} 条搬迁记录吗？`,
    '批量删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(() => batchDeleteMoves()).catch(() => {})
}

const batchDeleteMoves = async () => {
  if (!multipleSelection.value.length) return
  loading.value = true
  const failures = []
  let successCount = 0
  for (const row of multipleSelection.value) {
    try {
      await movesApi.deleteMove(row.id)
      successCount++
      await new Promise(r => setTimeout(r, 50))
    } catch (error) {
      const msg = error?.response?.data?.error || error?.message || '删除失败'
      failures.push(`${row.tenant_name || ''}(${row.id})：${msg}`)
      await new Promise(r => setTimeout(r, 50))
    }
  }
  try {
    await fetchMoves()
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

// 导出相关
const handleExportCommand = (cmd) => {
  if (cmd === 'excel') return exportToExcel()
  if (cmd === 'word') return exportToWord()
  if (cmd === 'pdf') return exportToPDF()
}

const getExportRows = () => {
  return moves.value.map(m => ({
    租户姓名: m.tenant_name,
    原房间: m.from_room,
    新房间: m.to_room,
    搬迁日期: m.move_date,
    搬迁原因: m.reason
  }))
}

const exportToExcel = () => {
  try {
    const rows = getExportRows()
    const ws = XLSX.utils.json_to_sheet(rows)
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, '搬迁记录')
    XLSX.writeFile(wb, `搬迁记录_${new Date().toLocaleDateString()}.xlsx`)
    ElMessage.success('Excel 导出完成')
  } catch (e) {
    console.error('导出 Excel 失败', e)
    ElMessage.error('导出 Excel 失败')
  }
}

const exportToWord = async () => {
  try {
    const rows = getExportRows()
    const headerCells = ['租户姓名','原房间','新房间','搬迁日期','搬迁原因'].map(text =>
      new TableCell({ children: [new Paragraph({ children: [new TextRun(String(text))] })] })
    )
    const tableRows = [
      new TableRow({ children: headerCells }),
      ...rows.map(r => new TableRow({
        children: [
          new TableCell({ children: [new Paragraph(String(r['租户姓名']))] }),
          new TableCell({ children: [new Paragraph(String(r['原房间']))] }),
          new TableCell({ children: [new Paragraph(String(r['新房间']))] }),
          new TableCell({ children: [new Paragraph(String(r['搬迁日期']))] }),
          new TableCell({ children: [new Paragraph(String(r['搬迁原因']))] })
        ]
      }))
    ]
    const doc = new Document({ sections: [{ children: [ new DocxTable({ rows: tableRows }) ] }] })
    const blob = await Packer.toBlob(doc)
    saveAs(blob, `搬迁记录_${new Date().toLocaleDateString()}.docx`)
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
    pdf.save(`搬迁记录_${new Date().toLocaleDateString()}.pdf`)
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
.moves-container {
  padding: 20px;
}

.page-header {
  display: flex;
  align-items: center;
  margin-bottom: 18px;
}

.header-operations {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.search-input {
  width: 240px;
}

.toolbar-btn {
  margin-left: 0 !important;
}

.pagination-container {
  margin-top: 16px;
  display: flex;
  justify-content: center;
  padding-top: 12px;
  border-top: 1px solid var(--surface-border);
}

:deep(.moves-table) {
  --el-table-header-bg-color: var(--surface-muted);
  --el-table-tr-bg-color: var(--card-bg);
  --el-table-row-hover-bg-color: rgba(37, 99, 235, 0.06);
  --el-table-border-color: var(--surface-border);
  border-radius: 12px;
  overflow: hidden;
}

:deep(.moves-table .el-table__header-wrapper th.el-table__cell) {
  font-weight: 700;
  color: var(--text-main);
  height: 48px;
}

:deep(.moves-table .el-table__body-wrapper td.el-table__cell) {
  padding: 12px 0;
}

:deep(.moves-table .el-table__fixed-right::before),
:deep(.moves-table .el-table__fixed::before) {
  background-color: transparent;
}

@media (max-width: 768px) {
  .search-input {
    width: 100%;
  }
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
</style>
