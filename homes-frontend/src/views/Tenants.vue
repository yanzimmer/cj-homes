<template>
  <div>
  <div class="tenants-container">
    <div class="page-header">
      <h2>租户详情</h2>
      <div class="header-operations">
        <el-input
          v-model="searchQuery"
          placeholder="搜索姓名/身份证/电话"
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
          <el-radio-button label="card">
            <el-icon><Grid /></el-icon> 卡片
          </el-radio-button>
          <el-radio-button label="group">
            <el-icon><Operation /></el-icon> 分组
          </el-radio-button>
        </el-radio-group>

        <el-button class="toolbar-btn" type="primary" @click="openAddDialog">新增</el-button>
        <el-button class="toolbar-btn" type="primary" plain @click="openAiDialog">AI 输入</el-button>
        <el-button
          class="toolbar-btn"
          type="warning"
          :disabled="selectedTenants.length === 0"
          :loading="batchCheckoutLoading"
          @click="handleBatchCheckout"
        >批量退租</el-button>
        <el-button
          class="toolbar-btn"
          type="danger"
          :disabled="selectedTenants.length === 0"
          :loading="batchDeleting"
          @click="handleBatchDelete"
        >批量删除</el-button>
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

    <div v-if="currentView === 'table'" class="table-panel">
    <el-table 
      class="tenants-table"
      ref="tenantsTableRef"
      row-key="id"
      :data="paginatedTenants" 
      v-loading="loading" 
      border 
      style="width: 100%"
      :fit="false"
      @sort-change="handleSortChange"
      @selection-change="handleSelectionChange"
      :reserve-selection="true"
    >
      <el-table-column type="selection" width="42" :selectable="rowSelectable" />
      <el-table-column prop="__sequence" label="序号" width="66" align="center" sortable="custom">
        <template #default="{ $index }">
          {{ tenantRowStart + $index + 1 }}
        </template>
      </el-table-column>
      <el-table-column prop="name" label="姓名" width="88" sortable="custom"></el-table-column>
      <el-table-column prop="gender" label="性别" width="64" sortable="custom"></el-table-column>
      <el-table-column prop="nation" label="民族" width="70" sortable="custom"></el-table-column>
      <el-table-column prop="birth_date" label="出生日期" width="110" sortable="custom"></el-table-column>
      <el-table-column prop="id_card" label="公民身份证号" width="168" sortable="custom"></el-table-column>
      <el-table-column prop="address" label="住址" min-width="160" sortable="custom" show-overflow-tooltip></el-table-column>
      <el-table-column prop="phone" label="联系电话" width="120" sortable="custom"></el-table-column>
      <el-table-column prop="emergency_contact_name" label="紧急联系人" width="104" sortable="custom"></el-table-column>
      <el-table-column prop="emergency_contact_phone" label="紧急电话" width="120" sortable="custom"></el-table-column>
      <el-table-column prop="building" label="楼栋" width="72" sortable="custom"></el-table-column>
      <el-table-column prop="room_no" label="房间号" width="92" sortable="custom"></el-table-column>
      <el-table-column prop="status" label="状态" width="82" sortable="custom">
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
      <el-table-column prop="check_in_date" label="入住日期" width="110" sortable="custom"></el-table-column>
      <el-table-column prop="check_out_date" label="退房日期" width="110" sortable="custom"></el-table-column>
      <el-table-column prop="remarks" label="备注" min-width="120" show-overflow-tooltip></el-table-column>
      <el-table-column label="操作" width="210" fixed="right">
        <template #default="scope">
          <div class="table-actions-row">
            <el-button size="small" @click="showTenantDetails(scope.row)">详情</el-button>
            <el-button size="small" type="primary" @click="openEditDialog(scope.row)">编辑</el-button>
            <el-dropdown trigger="click">
              <el-button size="small">
                更多
                <el-icon style="margin-left: 4px"><MoreFilled /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item
                    :disabled="scope.row.status === '已退租'"
                    @click="handleCheckout(scope.row)"
                  >
                    退租
                  </el-dropdown-item>
                  <el-dropdown-item
                    :disabled="scope.row.status === '在住'"
                    @click="handleDelete(scope.row)"
                  >
                    删除
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </template>
      </el-table-column>
    </el-table>
    </div>
    
    <!-- 分页控件 -->
    <div v-if="currentView === 'table' || currentView === 'card'" class="pagination-container">
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
      <div class="narrow-fields">
        <el-form :model="tenantForm" :rules="rules" ref="tenantFormRef" label-width="120px">
        <el-form-item label="身份证 OCR">
          <div class="tenant-ocr-row">
            <input
              ref="tenantIdCardFileInputRef"
              type="file"
              accept="image/*"
              capture="environment"
              class="hidden-file-input"
              @change="handleTenantIdCardFileChange"
            />
            <el-button
              type="primary"
              plain
              :loading="tenantOcrRecognizing"
              :disabled="!tenantOcrStatus.enabled"
              @click="openTenantIdCardFileDialog"
            >
              拍照/上传身份证正面识别
            </el-button>
            <span class="tenant-ocr-tip">
              <template v-if="tenantOcrStatus.configuredTotal > 0">
                剩余 {{ tenantOcrStatus.remainingCount ?? 0 }} / {{ tenantOcrStatus.configuredTotal }} 次
              </template>
              <template v-else>
                可直接识别并自动回填
              </template>
            </span>
          </div>
          <div v-if="tenantOcrStatus.reason && !tenantOcrStatus.enabled" class="tenant-ocr-message tenant-ocr-warning">
            {{ tenantOcrStatus.reason }}
          </div>
          <div v-if="tenantOcrMessage" class="tenant-ocr-message">
            {{ tenantOcrMessage }}
          </div>
        </el-form-item>
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

    <el-dialog
      title="AI 输入租户"
      v-model="aiDialog.visible"
      width="620px"
      @close="resetAiDialog"
    >
      <el-form label-width="92px">
        <el-form-item label="文字描述">
          <el-input
            v-model="aiDialog.text"
            type="textarea"
            :rows="5"
            placeholder="例如：张三，身份证号 110101199001011234，手机 13800000000，住 A栋301，今天入住。也可以上传身份证照片让本地模型识别。"
          />
        </el-form-item>
        <el-form-item label="图片识别">
          <el-upload
            action=""
            :auto-upload="false"
            :show-file-list="false"
            accept="image/*"
            multiple
            :limit="4"
            :on-change="handleAiImageChange"
          >
            <el-button type="primary" plain>选择图片</el-button>
          </el-upload>
          <el-button
            v-if="aiDialog.images.length"
            style="margin-left: 8px"
            type="danger"
            plain
            @click="clearAiImages"
          >
            清空图片
          </el-button>
          <div class="upload-progress-text">已选 {{ aiDialog.images.length }} / 4</div>
          <div v-if="aiDialog.images.length" class="ai-image-list">
            <div v-for="(item, index) in aiDialog.images" :key="item.url" class="ai-image-item">
              <el-image
                class="ai-image-thumb"
                :src="item.url"
                :preview-src-list="aiDialog.images.map(img => img.url)"
                fit="cover"
                preview-teleported
              />
              <el-button size="small" type="danger" plain @click="removeAiImage(index)">删除</el-button>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="aiDialog.visible = false">取消</el-button>
          <el-button type="primary" :loading="aiDialog.loading" @click="submitAiDraft">生成并填入</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 退租确认对话框 -->
    <el-dialog title="确认退租" v-model="checkoutDialogVisible" width="400px">
      <div class="checkout-confirm">
        <p>确定要将租户 <strong>{{ checkoutTenant.name }}</strong> 办理退租吗？</p>
        <p>公民身份证号: {{ checkoutTenant.id_card || '未填写' }}</p>
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
import { tenantsApi, roomsApi, repairRecordsApi, systemApi } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Filter, UserFilled, List, Grid, Operation, Iphone, Timer, MoreFilled } from '@element-plus/icons-vue'
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
const batchCheckoutLoading = ref(false)
const tenantIdCardFileInputRef = ref(null)
const tenantOcrRecognizing = ref(false)
const tenantOcrMessage = ref('')
const tenantOcrStatus = reactive({
  enabled: false,
  configuredTotal: 0,
  remainingCount: null,
  reason: '',
})
const aiDialog = reactive({
  visible: false,
  loading: false,
  text: '',
  images: []
})

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
const tenantRowStart = computed(() => (currentPage.value - 1) * pageSize.value)

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
      if (sortBy.value === '__sequence' || (!isNaN(aValue) && !isNaN(bValue))) {
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
    const response = await tenantsApi.checkoutTenant(checkoutTenant.value)
    
    ElMessage.success(response.data.message || '退租成功')
    checkoutDialogVisible.value = false
    await fetchTenants()
    if (currentTenant.value?.id === checkoutTenant.value?.id) {
      currentTenant.value = {
        ...currentTenant.value,
        status: '已退租',
        check_out_date: response?.data?.checkout_date || currentTenant.value.check_out_date,
      }
    }
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
  phone: '',
  emergency_contact: '',
  emergency_phone: '',
  room_no: '',
  status: '在住',
  check_in_date: new Date(),
  check_out_date: '',
  notes: ''
})

const applyTenantOcrStatus = (ocr = {}) => {
  tenantOcrStatus.enabled = Boolean(ocr.enabled)
  tenantOcrStatus.configuredTotal = Number(ocr.max_recognitions || ocr.configuredTotal || 0)
  tenantOcrStatus.remainingCount = ocr.remaining_count ?? ocr.remainingCount ?? null
  tenantOcrStatus.reason = ocr.reason || ''
}

const applyTenantRecognizedFields = (fields = {}) => {
  if (fields.name) tenantForm.name = fields.name
  if (fields.gender === '男' || fields.gender === '女') tenantForm.gender = fields.gender
  if (fields.nation) tenantForm.nation = fields.nation
  if (fields.birth_date) tenantForm.birth_date = fields.birth_date
  if (fields.id_card) tenantForm.id_card = fields.id_card
  if (fields.address) tenantForm.address = fields.address
}

const normalizeBuildingCode = (value) => String(value || '').trim().replace(/栋/g, '')

const normalizeRoomDigits = (value) => String(value || '').replace(/\D/g, '')

const resolveAiRoomNo = (draft = {}) => {
  const roomText = String(draft.room_no || '').trim()
  const building = normalizeBuildingCode(draft.building)
  const roomDigits = normalizeRoomDigits(roomText)
  if (!roomText) return ''

  const exact = availableRooms.value.find(room => String(room.room_no || '') === roomText)
  if (exact) return exact.room_no

  const candidates = new Set([roomText])
  if (building && roomDigits) {
    candidates.add(`${building}-${roomDigits}`)
    candidates.add(`${building}${roomDigits}`)
  }
  const candidateMatch = availableRooms.value.find(room => candidates.has(String(room.room_no || '')))
  if (candidateMatch) return candidateMatch.room_no

  const roomByBuilding = availableRooms.value.find(room => {
    const itemBuilding = normalizeBuildingCode(room.building)
    const itemDigits = normalizeRoomDigits(room.room_no)
    return building && itemBuilding === building && roomDigits && itemDigits.endsWith(roomDigits)
  })
  return roomByBuilding?.room_no || roomText
}

const applyTenantAiDraftToForm = (draft = {}) => {
  openAddDialog()
  tenantForm.name = String(draft.name || '')
  tenantForm.gender = draft.gender === '女' ? '女' : '男'
  tenantForm.nation = String(draft.nation || '汉族')
  tenantForm.birth_date = String(draft.birth_date || '')
  tenantForm.id_card = String(draft.id_card || '')
  tenantForm.address = String(draft.address || '')
  tenantForm.phone = String(draft.phone || '')
  tenantForm.emergency_contact = String(draft.emergency_contact_name || draft.emergency_contact || '')
  tenantForm.emergency_phone = String(draft.emergency_contact_phone || draft.emergency_phone || '')
  tenantForm.room_no = resolveAiRoomNo(draft)
  tenantForm.status = draft.status === '已退租' ? '已退租' : '在住'
  tenantForm.check_in_date = String(draft.check_in_date || new Date().toISOString().split('T')[0])
  tenantForm.check_out_date = String(draft.check_out_date || '')
  tenantForm.notes = String(draft.remarks || draft.notes || '')
  nextTick(() => {
    tenantFormRef.value?.clearValidate?.()
  })
}

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
onMounted(async () => {
  fetchTenants()
  await fetchAvailableRooms()
})

// 方法
// 处理排序变化
const handleSortChange = (column) => {
  sortBy.value = column.prop
  sortOrder.value = column.order
}

const rowSelectable = () => true

// 监听选择变化
const handleSelectionChange = (selection) => {
  console.log('[Tenants] selection changed:', selection.map(s => s.id_card))
  selectedTenants.value = selection
}

const handleBatchCheckout = async () => {
  if (!selectedTenants.value.length) return
  const activeTenants = selectedTenants.value.filter(t => String(t.status || '').trim() === '在住')
  if (!activeTenants.length) {
    ElMessage.warning('当前选中项里没有可退租的在住租户')
    return
  }

  const names = activeTenants.map(t => t.name).join('、')
  try {
    await ElMessageBox.confirm(
      `确认批量办理以下 ${activeTenants.length} 名租户退租吗？\n${names}`,
      '批量退租确认',
      {
        confirmButtonText: '确认退租',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    batchCheckoutLoading.value = true
    const failures = []
    let successCount = 0
    for (const tenant of activeTenants) {
      try {
        await tenantsApi.checkoutTenant(tenant)
        successCount++
        await new Promise(resolve => setTimeout(resolve, 50))
      } catch (error) {
        const msg = error?.response?.data?.error || error?.message || '退租失败'
        failures.push(`${tenant.name}(${tenant.id_card || '未填写身份证'})：${msg}`)
      }
    }
    await fetchTenants()
    tenantsTableRef.value?.clearSelection()
    selectedTenants.value = []

    if (successCount > 0) {
      ElMessage.success(`批量退租完成：成功 ${successCount} 人`)
    }
    if (failures.length > 0) {
      ElMessage.error(`有 ${failures.length} 人退租失败：${failures.join('；')}`)
    }
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error?.message || '批量退租失败')
    }
  } finally {
    batchCheckoutLoading.value = false
  }
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
    const response = await tenantsApi.listTenants({ fields: 'id,name,gender,nation,birth_date,id_card,address,phone,emergency_contact_name,emergency_contact_phone,check_in_date,check_out_date,room_no,building,remarks,status' })
    // 确保tenants.value是一个数组
    tenants.value = (response.data.tenants || []).map((tenant, index) => ({
      ...tenant,
      __sequence: index + 1
    }))
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
    const response = await roomsApi.listRooms({ fields: 'id,room_no,building,status,room_type,price,tenant_count' })
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
  tenantForm.phone = ''
  tenantForm.emergency_contact = ''
  tenantForm.emergency_phone = ''
  tenantForm.room_no = ''
  tenantForm.status = '在住'
  tenantForm.check_in_date = new Date()
  tenantForm.check_out_date = ''
  tenantForm.notes = ''
  tenantOcrMessage.value = ''
  tenantOcrStatus.enabled = false
  tenantOcrStatus.configuredTotal = 0
  tenantOcrStatus.remainingCount = null
  tenantOcrStatus.reason = ''
}

const openAddDialog = () => {
  resetForm()
  isEdit.value = false
  dialogTitle.value = '添加租户'
  fetchAvailableRooms()
  dialogVisible.value = true
  fetchTenantOcrStatus()
}

const openEditDialog = (tenant) => {
  resetForm()
  isEdit.value = true
  dialogTitle.value = '编辑租户'
  Object.assign(tenantForm, tenant)
  fetchAvailableRooms()
  dialogVisible.value = true
  fetchTenantOcrStatus()
}

const fetchTenantOcrStatus = async () => {
  try {
    const response = await systemApi.getOcrSettings()
    applyTenantOcrStatus(response?.data || {})
  } catch (_) {}
}

const openTenantIdCardFileDialog = () => {
  if (tenantOcrRecognizing.value) return
  tenantIdCardFileInputRef.value?.click()
}

const handleTenantIdCardFileChange = async (event) => {
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
  tenantOcrRecognizing.value = true
  tenantOcrMessage.value = ''
  try {
    const response = await tenantsApi.recognizeIdCard(file)
    const result = response?.data || {}
    applyTenantRecognizedFields(result.fields || {})
    applyTenantOcrStatus(result.ocr || {})
    tenantOcrMessage.value = '识别成功，已自动回填身份证信息。'
    ElMessage.success('身份证识别成功')
  } catch (error) {
    tenantOcrMessage.value = error?.response?.data?.error || '身份证识别失败'
    ElMessage.error(tenantOcrMessage.value)
  } finally {
    tenantOcrRecognizing.value = false
  }
}

const revokeAiImageUrls = () => {
  aiDialog.images.forEach((item) => {
    if (String(item?.url || '').startsWith('blob:')) {
      URL.revokeObjectURL(item.url)
    }
  })
}

const resetAiDialog = () => {
  revokeAiImageUrls()
  aiDialog.loading = false
  aiDialog.text = ''
  aiDialog.images = []
}

const openAiDialog = () => {
  resetAiDialog()
  aiDialog.visible = true
}

const handleAiImageChange = (file) => {
  if (!file || !file.raw) return
  if (aiDialog.images.length >= 4) {
    ElMessage.warning('最多选择 4 张图片')
    return
  }
  if (!String(file.raw.type || '').startsWith('image/')) {
    ElMessage.warning('请上传图片文件')
    return
  }
  if (file.raw.size && file.raw.size > 8 * 1024 * 1024) {
    ElMessage.warning('单张图片请控制在 8MB 以内')
    return
  }
  aiDialog.images.push({
    file: file.raw,
    url: URL.createObjectURL(file.raw)
  })
}

const removeAiImage = (index) => {
  const item = aiDialog.images[index]
  if (!item) return
  if (String(item.url || '').startsWith('blob:')) {
    URL.revokeObjectURL(item.url)
  }
  aiDialog.images.splice(index, 1)
}

const clearAiImages = () => {
  revokeAiImageUrls()
  aiDialog.images = []
}

const submitAiDraft = async () => {
  if (!aiDialog.text.trim() && aiDialog.images.length === 0) {
    ElMessage.warning('请先输入文字或选择图片')
    return
  }
  aiDialog.loading = true
  try {
    const formData = new FormData()
    formData.append('text', aiDialog.text.trim())
    aiDialog.images.forEach((item) => {
      formData.append('images', item.file)
    })
    const response = await tenantsApi.createAiDraft(formData)
    applyTenantAiDraftToForm(response?.data?.draft || {})
    aiDialog.visible = false
    ElMessage.success('AI 草稿已填入租户表单，请确认后保存')
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || error?.message || 'AI 输入失败')
  } finally {
    aiDialog.loading = false
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
      if (String(t.status || '').trim() === '在住') {
        failures.push({ tenant: t, msg: '在住状态不可删除，请先办理退租' })
        continue
      }
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

:deep(.tenants-table) {
  --el-table-header-bg-color: var(--surface-muted);
  --el-table-tr-bg-color: var(--card-bg);
  --el-table-row-hover-bg-color: rgba(37, 99, 235, 0.06);
  --el-table-border-color: var(--surface-border);
  border-radius: 12px;
  overflow: hidden;
}

:deep(.tenants-table .el-table__header-wrapper th.el-table__cell) {
  font-weight: 700;
  color: var(--text-main);
  height: 42px;
  padding: 6px 4px;
}

:deep(.tenants-table .el-table__body-wrapper td.el-table__cell) {
  padding: 8px 4px;
  font-size: 13px;
}

:deep(.tenants-table .el-button--small) {
  padding: 6px 10px;
}

:deep(.tenants-table .el-table__fixed-right::before),
:deep(.tenants-table .el-table__fixed::before) {
  background-color: transparent;
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
.table-actions-row {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  white-space: nowrap;
  gap: 4px;
  justify-content: center;
}

.table-actions-row :deep(.el-button--small) {
  padding: 5px 8px;
}
.table-actions-row :deep(.el-button + .el-button) {
  margin-left: 0;
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

.hidden-file-input {
  display: none;
}

.tenant-ocr-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.tenant-ocr-tip {
  font-size: 12px;
  color: #909399;
}

.tenant-ocr-message {
  margin-top: 6px;
  font-size: 12px;
  color: #409eff;
}

.tenant-ocr-warning {
  color: #e6a23c;
}
</style>
