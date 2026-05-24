<template>
  <div class="templates-container" :class="{ 'templates-container--mobile': mobileMode }">
    <div class="page-header">
      <div class="page-header__title">
        <h2>合同模板</h2>
        <div v-if="mobileMode" class="template-mobile-stats">
          <div class="template-mobile-stat">
            <strong>{{ templates.length }}</strong>
            <span>模板总数</span>
          </div>
        </div>
      </div>
      <div class="header-operations">
        <el-input
          class="search-input"
          v-model="searchQuery"
          placeholder="搜索名称/说明"
          clearable
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>

        <!-- 视图切换 -->
        <el-radio-group v-model="currentView" size="default" class="view-switch">
          <el-radio-button v-if="!mobileMode" label="table">
            <el-icon><List /></el-icon> 列表
          </el-radio-button>
          <el-radio-button label="grid">
            <el-icon><Grid /></el-icon> 网格
          </el-radio-button>
          <el-radio-button label="timeline">
            <el-icon><Timer /></el-icon> 时间轴
          </el-radio-button>
        </el-radio-group>

        <el-button class="toolbar-btn" type="primary" @click="openAddDialog">新增</el-button>
        <el-button
          v-if="!mobileMode"
          class="toolbar-btn"
          type="danger"
          :disabled="multipleSelection.length === 0"
          @click="confirmBatchDelete"
        >删除</el-button>
      </div>
    </div>

    <el-table
      class="templates-table"
      v-if="currentView === 'table'"
      :data="pagedTemplates"
      v-loading="loading"
      border
      style="width: 100%"
      :max-height="tableMaxHeight"
      @selection-change="handleSelectionChange"
      @sort-change="handleSortChange"
      row-key="id"
      :reserve-selection="true"
      ref="templatesTableRef"
    >
      <el-table-column type="selection" width="42" />
      <el-table-column prop="__sequence" label="序号" width="66" align="center" sortable="custom" show-overflow-tooltip>
        <template #default="{ $index }">
          {{ contractTemplateRowStart + $index + 1 }}
        </template>
      </el-table-column>
      <el-table-column prop="name" label="合同名称" min-width="140" sortable="custom" show-overflow-tooltip />
      <el-table-column prop="description" label="合同说明" min-width="180" sortable="custom" show-overflow-tooltip />
      <el-table-column prop="updated_at" label="更新时间" width="150" sortable="custom" show-overflow-tooltip />
      <el-table-column label="操作" width="170" fixed="right">
        <template #default="scope">
          <div class="table-actions-row">
            <el-button size="small" @click="openEditDialog(scope.row.id)">编辑</el-button>
            <el-dropdown trigger="click">
              <el-button size="small">
                更多
                <el-icon style="margin-left: 4px"><MoreFilled /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="openPreview(scope.row.id)">预览</el-dropdown-item>
                  <el-dropdown-item @click="openPrintPage(scope.row.id)">打印</el-dropdown-item>
                  <el-dropdown-item @click="exportPdfById(scope.row.id)">导出PDF</el-dropdown-item>
                  <el-dropdown-item @click="exportHTMLById(scope.row.id)">导出HTML</el-dropdown-item>
                  <el-dropdown-item @click="exportDocById(scope.row.id)">导出Word(.doc)</el-dropdown-item>
                  <el-dropdown-item @click="handleDelete(scope.row.id)">删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="currentView === 'table' || currentView === 'grid'" class="pagination-container" :class="{ 'pagination-container--mobile': mobileMode }">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="filteredTemplates.length"
        :layout="paginationLayout"
        :small="mobileMode"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>

    <!-- 网格视图 -->
    <div v-if="currentView === 'grid'" class="grid-view-container" v-loading="loading">
      <div v-if="pagedTemplates.length === 0" class="empty-state">
        <el-empty description="暂无合同模板" />
      </div>
      <div v-else class="templates-grid">
        <div v-for="tpl in pagedTemplates" :key="tpl.id" class="template-card">
          <div class="card-preview" @click="openPreview(tpl.id)">
            <div class="preview-icon">
              <el-icon><Document /></el-icon>
            </div>
            <div class="preview-overlay">
              <el-button type="primary" size="small" :icon="View" circle @click.stop="openPreview(tpl.id)" title="预览" />
              <el-button type="warning" size="small" :icon="Edit" circle @click.stop="openEditDialog(tpl.id)" title="编辑" />
              <el-button type="danger" size="small" :icon="Delete" circle @click.stop="handleDelete(tpl.id)" title="删除" />
            </div>
          </div>
          <div class="card-info">
            <h3 class="tpl-name" :title="tpl.name">{{ tpl.name }}</h3>
            <p class="tpl-desc" :title="tpl.description">{{ tpl.description || '暂无说明' }}</p>
            <div class="tpl-meta">
              <span>ID: {{ tpl.id }}</span>
              <span>{{ tpl.updated_at ? tpl.updated_at.split(' ')[0] : '' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 时间轴视图 -->
    <div v-if="currentView === 'timeline'" class="timeline-view-container" v-loading="loading">
      <div v-if="filteredTemplates.length === 0" class="empty-state">
        <el-empty description="暂无合同数据" />
      </div>
      <div v-else class="timeline-wrapper">
        <el-timeline>
          <el-timeline-item
            v-for="(group, date) in groupedTemplatesByDate"
            :key="date"
            :timestamp="date"
            placement="top"
            type="primary"
            size="large"
          >
            <div class="timeline-group-content">
              <div v-for="tpl in group" :key="tpl.id" class="timeline-card" @click="openEditDialog(tpl.id)">
                <div class="timeline-card-header">
                  <span class="tpl-name">{{ tpl.name }}</span>
                  <el-tag size="small" effect="plain">{{ tpl.id }}</el-tag>
                </div>
                <div class="timeline-card-body">
                  <p class="desc">{{ tpl.description || '无说明' }}</p>
                  <div class="actions">
                    <el-button type="primary" link size="small" @click.stop="openPreview(tpl.id)">预览</el-button>
                    <el-button type="primary" link size="small" @click.stop="openPrintPage(tpl.id)">打印</el-button>
                    <el-button type="danger" link size="small" @click.stop="handleDelete(tpl.id)">删除</el-button>
                  </div>
                </div>
              </div>
            </div>
          </el-timeline-item>
        </el-timeline>
      </div>
    </div>

    <!-- 新增/编辑合同抽屉 -->
    <el-drawer
      :title="dialogTitle"
      v-model="dialogVisible"
      direction="rtl"
      :size="mobileMode ? '100%' : '760px'"
    >
      <div class="narrow-fields">
        <el-form :model="tplForm" :rules="rules" ref="formRef" label-width="120px">
          <el-form-item label="合同名称" prop="name">
            <el-autocomplete
              v-model="tplForm.name"
              :fetch-suggestions="querySearchTenantSimple"
              placeholder="输入姓名可自动匹配租户（例如：王）"
              trigger-on-focus
              @select="handleSelectTemplateName"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="默认甲方" prop="default_landlord">
            <el-select 
              v-model="tplForm.default_landlord" 
              placeholder="请选择默认房东（可选）" 
              filterable 
              allow-create 
              default-first-option
              style="width: 100%"
            >
              <el-option
                v-for="item in landlordOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="合同说明" prop="description">
            <el-input v-model="tplForm.description" style="width: 100%" />
          </el-form-item>
          <el-form-item label="合同内容" prop="content_html">
            <el-alert
              title="占位符语法：{{name}}、{{gender}}、{{room_no}} 等。可粘贴HTML。"
              type="info"
              show-icon
              style="margin-bottom: 8px" />
            <el-input v-model="tplForm.content_html" type="textarea" :rows="16" placeholder="输入或粘贴合同HTML合同" />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
        </span>
      </template>
    </el-drawer>

    <!-- 预览/打印对话框 -->
    <el-dialog title="预览与导出" v-model="previewVisible" :width="mobileMode ? '96%' : '980px'" top="2vh">
      <div class="preview-toolbar">
        <el-form inline label-width="100px">
          <el-form-item label="甲方(出租方)">
            <el-select 
              v-model="vars.landlord" 
              placeholder="请选择或输入房东" 
              filterable 
              allow-create 
              default-first-option
              style="width: 160px"
            >
              <el-option
                v-for="item in landlordOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="姓名">
            <el-autocomplete
              v-model="vars.name"
              :fetch-suggestions="querySearchTenant"
              placeholder="输入姓名筛选"
              @select="handleTenantSelect"
              style="width: 140px"
            />
          </el-form-item>
          <el-form-item label="性别" style="width: 180px"><el-input v-model="vars.gender" /></el-form-item>
          <el-form-item label="民族" style="width: 180px"><el-input v-model="vars.nation" /></el-form-item>
          <el-form-item label="身份证"><el-input v-model="vars.id_card" style="width: 200px" /></el-form-item>
          <el-form-item label="住址"><el-input v-model="vars.address" style="width: 300px" /></el-form-item>
          <el-form-item label="房间号" style="width: 200px"><el-input v-model="vars.room_no" /></el-form-item>
          <el-form-item label="开始日期" style="width: 240px"><el-input v-model="vars.start_date" /></el-form-item>
          <el-form-item label="结束日期" style="width: 240px"><el-input v-model="vars.end_date" /></el-form-item>
          <el-form-item label="租金" style="width: 180px"><el-input v-model="vars.rent" /></el-form-item>
          <el-form-item label="押金" style="width: 180px"><el-input v-model="vars.deposit" /></el-form-item>
        </el-form>
        <div class="actions">
          <el-button type="primary" @click="renderPreview">更新预览</el-button>
          <el-button type="success" @click="saveContract">保存为合同</el-button>
        </div>
      </div>
      <div class="preview-area">
        <div ref="printAreaRef" class="print-area" v-html="renderedHtml"></div>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="previewVisible = false">关闭</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 隐藏打印区域：用于 PDF 导出，避免打开预览或打印对话框 -->
    <div v-if="showPdfArea" ref="pdfAreaRef" class="pdf-print-area" v-html="renderedHtml"></div>
    </div>
  </template>

<script setup>
import { ref, onMounted, onUnmounted, onBeforeUnmount, watch, nextTick, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { contractTemplatesApi, tenantsApi, roomsApi, contractsApi, notifyApi } from '../api/index'
import { jsPDF } from 'jspdf'
import html2canvas from 'html2canvas'
import { List, Grid, Timer, Document, Printer, Edit, Delete, Search, View, MoreFilled } from '@element-plus/icons-vue'
import { DISPLAY_MODE_EVENT, getPreferredDisplayMode } from '../utils/displayMode'

const currentView = ref('table') // 'table', 'grid', 'timeline'
const mobileMode = ref(false)
const templates = ref([])
const loading = ref(false)
// 表格高度随窗口自适应
const calcTableMaxHeight = () => Math.max(window.innerHeight - 260, 300)
const tableMaxHeight = ref(calcTableMaxHeight())
const handleResize = () => { tableMaxHeight.value = calcTableMaxHeight() }

const dialogVisible = ref(false)
const dialogTitle = ref('新增合同')
const saving = ref(false)
const formRef = ref(null)
const currentId = ref(null)
// 当前预览关联的合同ID（存在则更新，不存在则创建）
const currentContractId = ref(null)

const tplForm = ref({ name: '', description: '', content_html: '', default_landlord: '' })
const rules = {
  name: [{ required: true, message: '请输入合同名称', trigger: 'blur' }],
  content_html: [{ required: true, message: '请输入合同内容', trigger: 'blur' }]
}

const previewVisible = ref(false)
const printAreaRef = ref(null)
const renderedHtml = ref('')
const showPdfArea = ref(false)
const pdfAreaRef = ref(null)
const vars = ref({
  landlord: '李房东', // 默认甲方
  name: '张三',
  gender: '男',
  nation: '汉',
  id_card: '123456199001018888',
  address: '某省某市某区某街道',
  room_no: 'A-101',
  start_date: '2025-01-01',
  end_date: '2025-12-31',
  rent: '1800',
  deposit: '1800' // 默认押金
})

const landlordOptions = ref([])
const tenantOptions = ref([])
const loadTenantOptions = async () => {
  try {
    const { data } = await tenantsApi.listTenants()
    tenantOptions.value = data.tenants || []
  } catch (e) {
    console.error('加载租户选项失败', e)
  }
}

const querySearchTenant = (queryString, cb) => {
  const list = (tenantOptions.value || []).map(t => ({
    value: t.name,
    data: t
  }))
  const results = queryString
    ? list.filter(item => item.value && item.value.includes(queryString))
    : list
  cb(results.slice(0, 50))
}

// 用于合同名称输入框的简化联想：优先按“姓氏开头”匹配
const querySearchTenantSimple = (queryString, cb) => {
  const list = (tenantOptions.value || [])
    .map(t => ({ value: t.name || '', data: t }))
    .filter(item => item.value)
  const q = (queryString || '').trim()
  let results = list
  if (q) {
    const starts = list.filter(item => item.value.startsWith(q))
    results = starts.length ? starts : list.filter(item => item.value.includes(q))
  }
  cb(results.slice(0, 50))
}

// 监听新增/编辑表单中的默认房东变化，实时更新模板内容的 {{landlord}}
watch(() => tplForm.value.default_landlord, (newVal) => {
  if (newVal && tplForm.value.content_html) {
    // 简单替换：如果模板里已经是 {{landlord}} 则不动；如果是下划线则尝试替换（可选优化）
    // 这里我们不仅更新表单数据，还可以在保存时将这个值作为默认值存入
  }
})

const handleSelectTemplateName = (item) => {
  const name = item?.value || ''
  if (name) tplForm.value.name = name
}

const handleTenantSelect = async (item) => {
  const t = item?.data
  if (!t) return
  vars.value.name = t.name || ''
  vars.value.gender = t.gender || ''
  vars.value.nation = t.nation || vars.value.nation
  vars.value.id_card = t.id_card || ''
  vars.value.address = t.address || ''
  vars.value.room_no = t.room_no || ''
  vars.value.start_date = t.check_in_date || ''
  vars.value.end_date = t.check_out_date || ''
  try {
    const { data: roomsData } = await roomsApi.listRooms()
    const r = (roomsData.rooms || []).find(x => x.room_no === vars.value.room_no)
    if (r && r.price != null) {
      vars.value.rent = String(r.price)
      // 默认押金等于一个月租金
      vars.value.deposit = String(r.price)
    }
  } catch (_) {}
}


watch(() => vars.value.name, async (name) => {
  if (!name) return
  const t = (tenantOptions.value || []).find(x => x.name === name)
  if (!t) return
  vars.value.gender = t.gender || ''
  vars.value.nation = t.nation || vars.value.nation
  vars.value.id_card = t.id_card || ''
  vars.value.address = t.address || ''
  vars.value.room_no = t.room_no || ''
  vars.value.start_date = t.check_in_date || ''
  vars.value.end_date = t.check_out_date || ''
  try {
    const { data: roomsData } = await roomsApi.listRooms()
    const r = (roomsData.rooms || []).find(x => x.room_no === vars.value.room_no)
    if (r && r.price != null) {
      vars.value.rent = String(r.price)
      // 默认押金等于一个月租金
      vars.value.deposit = String(r.price)
    }
  } catch (_) {}
  ElMessage.success('已根据租户姓名自动填充信息')
})

// 合同名称变化时，自动同步到预览的姓名并更新预览
watch(() => tplForm.value.name, async (newName) => {
  vars.value.name = newName || ''
  if (previewVisible.value && currentId.value) {
    await renderPreview()
  }
})

const fetchTemplates = async () => {
  loading.value = true
  try {
    const { data } = await contractTemplatesApi.listTemplates()
    templates.value = (data.templates || []).map((item, index) => ({
      ...item,
      __sequence: index + 1
    }))
  } catch (e) {
    ElMessage.error('加载合同列表失败')
    console.error(e)
  } finally {
    loading.value = false
  }
}

// 搜索与过滤
const searchQuery = ref('')
const filteredTemplates = computed(() => {
  const q = (searchQuery.value || '').trim()
  if (!q) return templates.value
  try {
    return (templates.value || []).filter(t => {
      const name = (t.name || '').toLowerCase()
      const desc = (t.description || '').toLowerCase()
      const idStr = String(t.id || '')
      const qq = q.toLowerCase()
      return name.includes(qq) || desc.includes(qq) || idStr.includes(qq)
    })
  } catch (_) {
    return templates.value || []
  }
})

// 按日期分组（时间轴视图使用）
const groupedTemplatesByDate = computed(() => {
  const groups = {}
  const list = filteredTemplates.value || []
  list.forEach(t => {
    // 取日期部分 YYYY-MM-DD
    const date = t.updated_at ? t.updated_at.split(' ')[0] : '未知日期'
    if (!groups[date]) groups[date] = []
    groups[date].push(t)
  })
  // 按日期降序排序
  const sortedDates = Object.keys(groups).sort((a, b) => b.localeCompare(a))
  const result = {}
  sortedDates.forEach(d => {
    result[d] = groups[d]
  })
  return result
})

// 分页
const currentPage = ref(1)
const pageSize = ref(20)
const contractTemplateRowStart = computed(() => (currentPage.value - 1) * pageSize.value)
const paginationLayout = computed(() => (
  mobileMode.value ? 'prev, pager, next' : 'total, sizes, prev, pager, next, jumper'
))
const sortBy = ref('')
const sortOrder = ref('')
const pagedTemplates = computed(() => {
  let list = [...(filteredTemplates.value || [])]
  if (sortBy.value) {
    list.sort((a, b) => {
      let aValue = a[sortBy.value]
      let bValue = b[sortBy.value]
      if (aValue === undefined || aValue === null) aValue = ''
      if (bValue === undefined || bValue === null) bValue = ''
      if (sortBy.value === '__sequence' || (!isNaN(aValue) && !isNaN(bValue))) {
        return sortOrder.value === 'ascending' ? Number(aValue) - Number(bValue) : Number(bValue) - Number(aValue)
      }
      return sortOrder.value === 'ascending'
        ? String(aValue).localeCompare(String(bValue))
        : String(bValue).localeCompare(String(aValue))
    })
  }
  const start = (currentPage.value - 1) * pageSize.value
  const end = currentPage.value * pageSize.value
  return list.slice(start, end)
})

const syncDisplayMode = () => {
  const isMobile = getPreferredDisplayMode() === 'mobile'
  mobileMode.value = isMobile
  if (isMobile && currentView.value === 'table') {
    currentView.value = 'grid'
  }
}

const handleSortChange = ({ prop, order }) => {
  sortBy.value = prop || ''
  sortOrder.value = order || ''
}

const handleSizeChange = (size) => {
  pageSize.value = size
  currentPage.value = 1
}

const handleCurrentChange = (page) => {
  currentPage.value = page
}

// 当搜索或数据变化导致总页数变少时，回退到最后一页
watch([filteredTemplates, pageSize], () => {
  const total = filteredTemplates.value.length
  const maxPage = Math.max(1, Math.ceil(total / pageSize.value))
  if (currentPage.value > maxPage) currentPage.value = maxPage
})
// 搜索时重置到第一页，提升体验
watch(searchQuery, () => { currentPage.value = 1 })

// 表格选择与删除
const templatesTableRef = ref(null)
const multipleSelection = ref([])
const handleSelectionChange = (val) => {
  multipleSelection.value = Array.isArray(val) ? val : []
}

const confirmBatchDelete = async () => {
  const ids = (multipleSelection.value || []).map(x => x.id)
  if (!ids.length) {
    ElMessage.warning('请先选择要删除的合同')
    return
  }
  const names = (multipleSelection.value || []).map(x => x.name).filter(Boolean)
  const count = ids.length
  const previewNames = names.slice(0, 6).join('、') + (names.length > 6 ? ' 等' : '')
  try {
    await ElMessageBox.confirm(
      `确定删除以下 ${count} 个合同吗？${previewNames}。删除后将同时删除关联合同，且不可撤销。`,
      '提示',
      {
        type: 'warning',
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        closeOnClickModal: false,
        closeOnPressEscape: true
      }
    )
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error('操作中断：确认框异常')
    console.error('Batch delete confirm error:', e)
    return
  }

  const { ok, fail, errors } = await batchDeleteTemplates(ids)
  if (ok) ElMessage.success(`删除完成：成功 ${ok} 条`)
  if (fail) {
    const msg = errors.map(err => `ID ${err.id}: ${err.message}`).join('\n')
    ElMessage.error(`失败 ${fail} 条\n${msg}`)
  }
  await fetchTemplates()
  multipleSelection.value = []
  try { templatesTableRef.value?.clearSelection?.() } catch (_) {}
}

const batchDeleteTemplates = async (ids) => {
  let ok = 0, fail = 0
  const errors = []
  const sleep = (ms) => new Promise(r => setTimeout(r, ms))
  for (const id of ids) {
    try {
      await contractTemplatesApi.deleteTemplate(id)
      ok += 1
      await sleep(50) // 避免 SQLite 写锁冲突
    } catch (e) {
      fail += 1
      const message = e?.response?.data?.error || e?.message || '删除失败'
      errors.push({ id, message })
      await sleep(50)
    }
  }
  return { ok, fail, errors }
}

const openAddDialog = () => {
  currentId.value = null
  currentContractId.value = null
  dialogTitle.value = '新增合同'
  // 加载默认房东
  let defaultLandlord = ''
  if (landlordOptions.value.length > 0) {
    defaultLandlord = landlordOptions.value[0].value
  }
  
  tplForm.value = { 
    name: '', 
    description: '', 
    content_html: defaultSample(),
    default_landlord: defaultLandlord 
  }
  // 预加载租户列表，便于在合同名称中联想选择租户姓名
  loadTenantOptions()
  dialogVisible.value = true
}

const openEditDialog = async (id) => {
  try {
    const { data } = await contractTemplatesApi.getTemplate(id)
    const t = data.template
    currentId.value = id
    dialogTitle.value = '编辑合同'
    
    // 尝试从 content_html 中提取或推断房东（如果有相关逻辑），或者保持为空
    // 这里简单处理，编辑时不强制覆盖房东选择，除非后端有字段存储
    tplForm.value = {
      name: t.name,
      description: t.description || '',
      content_html: t.content_html || '',
      default_landlord: '' // 编辑模式暂不自动填充，避免覆盖用户可能的手动修改
    }
    dialogVisible.value = true
  } catch (e) {
    ElMessage.error('加载合同失败')
  }
}

const handleSave = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    saving.value = true
    try {
      // 如果用户选择了默认房东，且模板内容包含 {{landlord}}，
      // 我们可以在保存前不做替换（保留占位符灵活性），
      // 但在“新增”时，我们可以将这个默认房东值传递给预览/生成逻辑（如果后端支持）。
      // 目前后端只存 content_html，所以这里的 default_landlord 主要是辅助生成的。
      // 如果用户希望"硬编码"房东进模板，可以在 content_html 里直接改。
      // 这里我们保持 content_html 原样，default_landlord 仅作为 UI 辅助。
      
      if (currentId.value) {
        await contractTemplatesApi.updateTemplate(currentId.value, { ...tplForm.value })
        ElMessage.success('合同更新成功')
      } else {
        const resp = await contractTemplatesApi.addTemplate({ ...tplForm.value })
        ElMessage.success('合同创建成功')
        // 使用后端返回的新模板ID，立即保存一次合同记录
        const newId = resp?.data?.id
        if (newId) {
          currentId.value = newId
          // 如果新增时选了房东，更新 vars 中的房东，以便立即预览/保存合同
          if (tplForm.value.default_landlord) {
            vars.value.landlord = tplForm.value.default_landlord
          }
          try {
            await saveContract()
          } catch (e) {
            console.error('自动保存新合同失败：', e)
          }
        }
      }
      dialogVisible.value = false
      fetchTemplates()
    } catch (e) {
      ElMessage.error('保存合同失败')
      console.error(e)
    } finally {
      saving.value = false
    }
  })
}

const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm('确定删除该合同吗？', '提示', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      closeOnClickModal: false,
      closeOnPressEscape: true
    })
  } catch (e) {
    // 用户取消或关闭弹窗，不进行删除
    if (e === 'cancel' || e === 'close') return
    // 其他异常（例如弹窗组件错误）
    ElMessage.error('操作中断：确认框异常')
    console.error('Delete confirm error:', e)
    return
  }

  try {
    await contractTemplatesApi.deleteTemplate(id)
    ElMessage.success('已删除')
    await fetchTemplates()
  } catch (e) {
    // 显示后端返回的具体错误信息，便于定位问题
    const msg = e?.response?.data?.error || e?.message || '删除失败'
    ElMessage.error(msg)
    console.error('Delete API error:', e)
  }
}

const openPreview = async (id) => {
  try {
    const { data } = await contractTemplatesApi.getTemplate(id)
  const t = data.template
  currentId.value = id
  // 将合同名称同步为预览中的姓名
  vars.value.name = t?.name || vars.value.name
  // 先按最新姓名渲染预览
  const r = await contractTemplatesApi.renderTemplate(id, vars.value)
    renderedHtml.value = r.data.rendered_html || ''
    previewVisible.value = true
    loadTenantOptions()
    // 试图找到该模板的现有合同（选择最新一条）
    try {
      const resp = await contractsApi.listContracts(1, 1000)
      const items = resp?.data?.items || []
      const found = items.find(x => String(x.template_id) === String(id))
      currentContractId.value = found?.id || null
    } catch (_) {
      currentContractId.value = null
    }
  } catch (e) {
    ElMessage.error('打开预览失败')
    console.error(e)
  }
}

// 根据合同ID获取合同名称；并对文件名进行安全处理
const getTemplateNameById = (id) => {
  const t = templates.value?.find?.(x => String(x.id) === String(id))
  return t?.name || '合同名称'
}

const sanitizeFilename = (name) => {
  let n = (name || '合同名称').toString().trim()
  // 替换不允许的字符：<>:"/\|?*
  n = n.replace(/[<>:"/\\|?*]/g, '_')
  // Windows 不允许以点或空格结尾
  n = n.replace(/[\.\s]+$/, '')
  // 限制长度，避免过长
  if (n.length > 80) n = n.slice(0, 80)
  return n || '合同名称'
}

// 统一日期格式：YYYY-MM-DD，用于文件名
const formatDateForFilename = () => {
  const d = new Date()
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

const openPreviewAndPrint = async (id) => {
  try {
    await openPreview(id)
    await nextTick()
    doPrint()
  } catch (e) {
    ElMessage.error('打开并打印失败')
    console.error(e)
  }
}

// 打印页面：仅显示“打印房屋租赁合同”按钮与合同内容（不额外加标题）
const openPrintPage = async (id) => {
  try {
    const r = await contractTemplatesApi.renderTemplate(id, vars.value)
    const html = r.data.rendered_html || ''
    const win = window.open('', '_blank')
    if (!win) throw new Error('无法打开打印窗口')
    const docHtml = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>&#8203;</title>
  <style>
    body { margin: 0; padding: 16px; font-family: SimSun, '宋体', Arial; background: #fff; }
    .print-area { background: #fff; color: #000; }
    @page { margin: 12mm; }
  </style>
</head>
<body>
  <div class="print-area">${html}</div>
  <script>
    window.addEventListener('load', function () {
      setTimeout(function () { window.print(); }, 50);
    });
    window.onafterprint = function () { window.close(); };
  <\/script>
</body>
</html>`
    win.document.open()
    win.document.write(docHtml)
    win.document.close()
    // 避免页眉显示 about:blank：标题置空并替换地址
    try { win.document.title = '\u200B' } catch (_) {}
    try { win.history.replaceState({}, '', '/房屋租赁合同.pdf') } catch (_) {}
  } catch (e) {
    ElMessage.error('打开打印页面失败')
    console.error(e)
  }
}

const exportPdfById = async (id) => {
  try {
    const r = await contractTemplatesApi.renderTemplate(id, vars.value)
    renderedHtml.value = r.data.rendered_html || ''
    showPdfArea.value = true
    await nextTick()
    const el = pdfAreaRef.value
    if (!el) throw new Error('PDF 区域未就绪')
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
    const baseName = sanitizeFilename(getTemplateNameById(id))
    const dateStr = formatDateForFilename()
    const fileBase = `房屋租赁合同_${baseName}_${dateStr}`
    pdf.save(`${fileBase}.pdf`)
    ElMessage.success('PDF 导出完成（中文已正确显示）')
  } catch (e) {
    console.error('导出 PDF 失败', e)
    ElMessage.error('导出 PDF 失败')
  } finally {
    showPdfArea.value = false
  }
}

const exportHTMLById = async (id) => {
  try {
    const r = await contractTemplatesApi.renderTemplate(id, vars.value)
    const html = r.data.rendered_html || ''
    const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const baseName = sanitizeFilename(getTemplateNameById(id))
    const dateStr = formatDateForFilename()
    const fileBase = `房屋租赁合同_${baseName}_${dateStr}`
    a.download = `${fileBase}.html`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('HTML 导出完成')
  } catch (e) {
    ElMessage.error('HTML 导出失败')
    console.error(e)
  }
}

const exportDocById = async (id) => {
  try {
    const r = await contractTemplatesApi.renderTemplate(id, vars.value)
    const html = r.data.rendered_html || ''
    const header = `<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>`
    const footer = `</body></html>`
    const blob = new Blob([header + html + footer], { type: 'application/msword' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const baseName = sanitizeFilename(getTemplateNameById(id))
    const dateStr = formatDateForFilename()
    const fileBase = `房屋租赁合同_${baseName}_${dateStr}`
    a.download = `${fileBase}.doc`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('Word 导出完成')
  } catch (e) {
    ElMessage.error('Word 导出失败')
    console.error(e)
  }
}

const renderPreview = async () => {
  if (!currentId.value) return
  try {
    const r = await contractTemplatesApi.renderTemplate(currentId.value, vars.value)
    renderedHtml.value = r.data.rendered_html || ''
  } catch (e) {
    ElMessage.error('渲染失败')
    console.error(e)
  }
}

const doPrint = () => {
  // 简单调用浏览器打印，用户可选择“另存为PDF”
  window.print()
}

const exportHTML = () => {
  const blob = new Blob([renderedHtml.value], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const baseName = sanitizeFilename(getTemplateNameById(currentId.value))
  const dateStr = formatDateForFilename()
  const fileBase = `房屋租赁合同_${baseName}_${dateStr}`
  a.download = `${fileBase}.html`
  a.click()
  URL.revokeObjectURL(url)
}

const exportDoc = () => {
  // 用 HTML 作为 DOC 内容，Word 可直接打开
  const header = `<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>`
  const footer = `</body></html>`
  const blob = new Blob([header + renderedHtml.value + footer], { type: 'application/msword' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const baseName = sanitizeFilename(getTemplateNameById(currentId.value))
  const dateStr = formatDateForFilename()
  const fileBase = `房屋租赁合同_${baseName}_${dateStr}`
  a.download = `${fileBase}.doc`
  a.click()
  URL.revokeObjectURL(url)
}

const saveContract = async () => {
  if (!currentId.value) {
    ElMessage.warning('请先选择并预览合同')
    return
  }
  try {
    if (currentContractId.value) {
      await contractsApi.updateContract(currentContractId.value, { ...vars.value })
      ElMessage.success('合同已更新到数据库')
    } else {
      const resp = await contractsApi.createContract(currentId.value, { ...vars.value })
      currentContractId.value = resp?.data?.id || currentContractId.value
      ElMessage.success('合同已保存到数据库')
    }
  } catch (e) {
    const msg = e?.response?.data?.message || e?.message || '保存合同失败'
    ElMessage.error(msg)
    console.error('Save contract error:', e)
  }
}

const defaultSample = () => {
  return `
  <div style="padding: 24px; font-family: SimSun, '宋体', Arial; line-height: 1.8; max-width: 800px; margin: 0 auto;">
    <h2 style="text-align:center;">房屋租赁合同</h2>
    <p>甲方（出租方）：{{landlord}}</p>
    <p>乙方（承租方）：{{name}}（性别：{{gender}}，民族：{{nation}}，身份证：{{id_card}}）</p>
    <p>住址：{{address}}</p>
    <p>租赁房屋：{{room_no}}</p>
    <p>租赁期限：自 {{start_date}} 至 {{end_date}}</p>
    <p>租金：{{rent}} 元/月，押金：{{deposit}} 元</p>
    <p>条款：双方同意遵守国家相关法律法规，具体细则见附件。</p>
    <br/>
    <p>甲方（签字/盖章）：{{landlord}}</p>
    <p>乙方（签字）：________________</p>
    <p>签约日期：______年____月____日</p>
  </div>
  `
}

const loadDefaultLandlord = async () => {
  try {
    const { data } = await notifyApi.getConfig()
    if (data && data.landlords && data.landlords.length > 0) {
      // 加载房东选项
      landlordOptions.value = data.landlords.map(l => ({
        label: l.name,
        value: l.name
      }))
      // 默认选中第一个房东，或者如果已有值则保持不变
      if (!vars.value.landlord) {
        vars.value.landlord = data.landlords[0].name
      }
    } else {
      // 如果没有配置房东，提供一个默认选项
      landlordOptions.value = [{ label: '李房东', value: '李房东' }]
      if (!vars.value.landlord) {
        vars.value.landlord = '李房东'
      }
    }
  } catch (e) {
    console.error('加载房东信息失败，使用默认值', e)
    landlordOptions.value = [{ label: '李房东', value: '李房东' }]
  }
}

onMounted(async () => {
  syncDisplayMode()
  window.addEventListener(DISPLAY_MODE_EVENT, syncDisplayMode)
  window.addEventListener('resize', handleResize)
  await fetchTemplates()
  await loadDefaultLandlord()
})
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
onBeforeUnmount(() => {
  window.removeEventListener(DISPLAY_MODE_EVENT, syncDisplayMode)
})
</script>

<style scoped>
.templates-container {
  padding: 20px;
  background: var(--card-bg);
  border: 1px solid var(--surface-border);
  border-radius: 18px;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
}

.page-header__title {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}

.page-header h2 {
  margin: 0;
  color: #409EFF;
}

.template-mobile-stats {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.template-mobile-stat {
  min-width: 96px;
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid var(--surface-border);
  background: var(--surface-muted);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.template-mobile-stat strong {
  font-size: 18px;
  color: var(--text-main);
}

.template-mobile-stat span {
  font-size: 12px;
  color: var(--text-secondary);
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

.view-switch {
  margin-right: 6px;
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

.pagination-container--mobile {
  margin-top: 14px;
  padding-top: 0;
  border-top: none;
}

:deep(.templates-table) {
  --el-table-header-bg-color: var(--surface-muted);
  --el-table-tr-bg-color: var(--card-bg);
  --el-table-row-hover-bg-color: rgba(37, 99, 235, 0.06);
  --el-table-border-color: var(--surface-border);
  border-radius: 12px;
  overflow: hidden;
}

:deep(.templates-table .el-table__header-wrapper th.el-table__cell) {
  font-weight: 700;
  color: var(--text-main);
  height: 42px;
  padding: 6px 4px;
}

:deep(.templates-table .el-table__body-wrapper td.el-table__cell) {
  padding: 8px 2px;
  font-size: 13px;
}

:deep(.templates-table .el-button--small) {
  padding: 6px 10px;
}

.table-actions-row {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: nowrap;
  white-space: nowrap;
  justify-content: center;
}

.table-actions-row > * {
  flex: 0 0 78px;
}

.table-actions-row :deep(.el-button) {
  width: 100%;
  min-width: 0;
  justify-content: center;
}

.table-actions-row :deep(.el-dropdown) {
  display: inline-flex;
  width: 100%;
}

:deep(.templates-table .el-table__fixed-right::before),
:deep(.templates-table .el-table__fixed::before) {
  background-color: transparent;
}

@media (max-width: 768px) {
  .search-input {
    width: 100%;
  }
}

.narrow-fields {
  max-width: 860px;
  margin: 0 auto;
}

.narrow-fields :deep(.el-form-item__label) {
  white-space: nowrap;
}

.narrow-fields :deep(.el-input),
.narrow-fields :deep(textarea) {
  width: 100% !important;
}

.narrow-fields .el-form-item {
  margin-bottom: 22px;
}

/* 网格视图样式 */
.grid-view-container {
  padding: 10px 0;
}
.templates-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 24px;
}
.template-card {
  background: var(--card-bg);
  border-radius: 8px;
  border: 1px solid var(--el-border-color-light, #ebeef5);
  transition: all 0.3s;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.template-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 16px rgba(0,0,0,0.1);
}
.card-preview {
  height: 160px;
  background: var(--el-fill-color-light, #f5f7fa);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  cursor: pointer;
}
.preview-icon {
  font-size: 64px;
  color: #c0c4cc;
}
.preview-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  opacity: 0;
  transition: opacity 0.3s;
}
.card-preview:hover .preview-overlay {
  opacity: 1;
}
.card-info {
  padding: 12px;
  flex: 1;
  display: flex;
  flex-direction: column;
}
.tpl-name {
  margin: 0 0 6px 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-main);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.tpl-desc {
  margin: 0 0 10px 0;
  font-size: 13px;
  color: var(--text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1;
}
.tpl-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-secondary);
  border-top: 1px solid var(--el-border-color-light, #f0f2f5);
  padding-top: 8px;
}

/* 时间轴视图样式 */
.timeline-view-container {
  padding: 20px 40px;
}
.timeline-wrapper {
  max-width: 800px;
}
.timeline-group-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.timeline-card {
  background: var(--card-bg);
  border: 1px solid var(--el-border-color-light, #ebeef5);
  border-radius: 6px;
  padding: 12px 16px;
  transition: all 0.2s;
  cursor: pointer;
}
.timeline-card:hover {
  border-color: #409EFF;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}
.timeline-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.timeline-card-header .tpl-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-main);
}
.timeline-card-body {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.timeline-card-body .desc {
  margin: 0;
  font-size: 13px;
  color: var(--text-regular);
  max-width: 70%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.timeline-card-body .actions {
  display: flex;
  gap: 8px;
}

.preview-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 10px;
}
.actions {
  display: flex;
  gap: 8px;
}
.preview-area {
  border: 1px solid var(--el-border-color-light, #e5e5e5);
  border-radius: 4px;
  padding: 12px;
  max-height: 70vh;
  overflow: auto;
  background: var(--card-bg);
}
.print-area {
  background: #fff;
  color: #000;
}
.pdf-print-area {
  position: fixed;
  left: -9999px;
  top: 0;
  width: 800px;
  background: #ffffff;
  color: #000;
  padding: 12px;
  font-family: SimSun, '宋体', Arial;
}

/* 打印样式，仅打印预览区域 */
@media print {
  body * { visibility: hidden; }
  .print-area, .print-area * { visibility: visible; }
}

.templates-container--mobile {
  padding: 16px;
  border-radius: 16px;
}

.templates-container--mobile .page-header {
  flex-direction: column;
  align-items: stretch;
  gap: 14px;
}

.templates-container--mobile .header-operations {
  gap: 10px;
}

.templates-container--mobile .search-input,
.templates-container--mobile .view-switch,
.templates-container--mobile .toolbar-btn {
  width: 100%;
}

.templates-container--mobile .view-switch {
  margin-right: 0;
}

.templates-container--mobile :deep(.view-switch .el-radio-button__inner) {
  width: 100%;
}

.templates-container--mobile .templates-grid {
  grid-template-columns: 1fr;
  gap: 14px;
}

.templates-container--mobile .card-preview {
  height: 140px;
}

.templates-container--mobile .timeline-view-container {
  padding: 8px 0;
}

.templates-container--mobile .timeline-card {
  padding: 12px;
  border-radius: 12px;
}

.templates-container--mobile .timeline-card-body {
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}

.templates-container--mobile .timeline-card-body .desc {
  max-width: none;
  white-space: normal;
}

.templates-container--mobile .preview-toolbar {
  flex-direction: column;
  gap: 12px;
}

.templates-container--mobile .preview-toolbar :deep(.el-form--inline) {
  display: flex;
  flex-direction: column;
}

.templates-container--mobile .preview-toolbar :deep(.el-form-item) {
  width: 100%;
  margin-right: 0;
}

.templates-container--mobile .preview-toolbar :deep(.el-form-item__content) {
  width: 100%;
}

.templates-container--mobile .preview-toolbar :deep(.el-input),
.templates-container--mobile .preview-toolbar :deep(.el-select),
.templates-container--mobile .preview-toolbar :deep(.el-autocomplete),
.templates-container--mobile .preview-toolbar :deep(.el-input__wrapper) {
  width: 100% !important;
}

.templates-container--mobile .actions {
  width: 100%;
  justify-content: space-between;
  flex-wrap: wrap;
}
</style>
