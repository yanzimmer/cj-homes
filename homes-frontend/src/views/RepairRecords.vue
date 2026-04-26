<template>
  <div>
  <div class="repair-records-container">
    <div class="page-header">
      <div class="header-operations">
        <el-input
          class="search-input"
          v-model="searchQuery"
          placeholder="搜索房间号/维修类型"
          clearable
          @clear="handleSearchClear"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button class="toolbar-btn" type="primary" @click="openAddDialog">添加维修记录</el-button>
        <el-button class="toolbar-btn" type="success" @click="linkDialogVisible = true">填写链接</el-button>
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
        <el-upload
          action=""
          :auto-upload="false"
          :show-file-list="false"
          accept=".xlsx, .xls"
          :on-change="handleImportFile"
        >
          <el-button class="toolbar-btn" type="warning">导入</el-button>
        </el-upload>
      </div>
    </div>

    <div class="table-panel">
      <el-table 
        class="records-table"
        :data="records" 
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
      <el-table-column label="图片" width="100">
        <template #default="scope">
          <el-image lazy loading="lazy"
            v-if="getRepairImages(scope.row).length > 0"
            class="table-image-thumb"
            :src="toImageUrl(getRepairImages(scope.row)[0])"
            :preview-src-list="getRepairImages(scope.row).map((v) => toImageUrl(v))"
            fit="cover"
            preview-teleported
          />
          <span v-else>-</span>
        </template>
      </el-table-column>
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
      <el-table-column prop="amount" label="金额" width="100" sortable="custom">
        <template #default="scope">
          {{ scope.row.amount ? `¥${scope.row.amount}` : '-' }}
        </template>
      </el-table-column>
      <el-table-column label="领用库存" min-width="180" show-overflow-tooltip>
        <template #default="scope">
          <div v-if="(scope.row.inventory_usages || []).length > 0" class="inventory-usage-summary">
            <el-tag
              v-for="(usage, index) in scope.row.inventory_usages.slice(0, 2)"
              :key="`summary-${scope.row.id}-${index}`"
              size="small"
              type="warning"
              effect="plain"
            >
              {{ usage.item_name || '物品' }} x {{ usage.quantity }}{{ usage.unit || '' }}
            </el-tag>
            <span v-if="scope.row.inventory_usages.length > 2" class="inventory-more-text">
              +{{ scope.row.inventory_usages.length - 2 }} 项
            </span>
          </div>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="repair_person" label="维修人员" width="100"></el-table-column>
      <el-table-column prop="remarks" label="备注" min-width="140" show-overflow-tooltip></el-table-column>
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
    </div>

    <div class="pagination-container">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="totalRecords"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
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
          <el-input v-model="recordForm.description" type="textarea" :rows="3" placeholder="请输入问题描述" />
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
        <el-form-item label="金额">
          <el-input-number v-model="recordForm.amount" :min="0" :precision="2" :step="10" style="width: 100%" />
        </el-form-item>
        <el-form-item label="支付人员">
          <el-input v-model="recordForm.payment_person" placeholder="请输入支付人员姓名" />
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
          <el-form-item label="维修人员">
            <el-input v-model="recordForm.repair_person" placeholder="请输入维修人员姓名" />
          </el-form-item>
        </template>
        <el-form-item label="使用库存" class="full-span">
          <div class="inventory-usage-wrap">
            <div
              v-for="(usage, index) in recordForm.inventory_usages"
              :key="`usage-${index}`"
              class="inventory-usage-row"
            >
              <el-select v-model="usage.warehouse_item_id" placeholder="选择库存物品" style="width: 100%">
                <el-option
                  v-for="item in inventoryOptions"
                  :key="item.id"
                  :label="`${item.item_name}${item.specification ? ` / ${item.specification}` : ''} / 库存 ${item.quantity}${item.unit || ''}`"
                  :value="item.id"
                />
              </el-select>
              <el-input-number v-model="usage.quantity" :min="1" :precision="2" style="width: 140px" />
              <el-button type="danger" plain @click="removeInventoryUsage(index)">删除</el-button>
            </div>
            <el-button type="primary" plain @click="addInventoryUsage">添加库存领用</el-button>
          </div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="recordForm.remarks" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
        <el-form-item label="维修前图片">
          <el-upload
            action=""
            :auto-upload="false"
            :show-file-list="false"
            accept="image/*"
            multiple
            :limit="30"
            :on-change="(file) => handleRepairImageChange('before', file)"
          >
            <el-button type="primary" plain>选择图片(最多30张)</el-button>
          </el-upload>
          <el-button
            v-if="recordForm.repair_images_before.length > 0"
            style="margin-left: 8px"
            type="danger"
            plain
            @click="clearAllFormImages('before')"
          >
            全部删除图片
          </el-button>
          <div class="upload-progress-text" v-if="uploadingRepairImages">上传进度 {{ uploadProgress }}%</div>
          <div class="upload-progress-text">已选 {{ recordForm.repair_images_before.length }} / 30</div>
          <div v-if="recordForm.repair_images_before.length > 0" class="repair-image-preview-wrap">
            <div v-for="(img, index) in recordForm.repair_images_before" :key="`${img}-${index}`" class="repair-image-box">
              <el-image lazy loading="lazy"
                class="repair-image-thumb"
                :src="toImageUrl(img)"
                :preview-src-list="recordForm.repair_images_before.map((v) => toImageUrl(v))"
                fit="cover"
                preview-teleported
              />
              <el-button size="small" type="danger" plain @click="removeFormImage('before', index)">删除</el-button>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="维修后图片">
          <el-upload
            action=""
            :auto-upload="false"
            :show-file-list="false"
            accept="image/*"
            multiple
            :limit="30"
            :on-change="(file) => handleRepairImageChange('after', file)"
          >
            <el-button type="primary" plain>选择图片(最多30张)</el-button>
          </el-upload>
          <el-button
            v-if="recordForm.repair_images_after.length > 0"
            style="margin-left: 8px"
            type="danger"
            plain
            @click="clearAllFormImages('after')"
          >
            全部删除图片
          </el-button>
          <div class="upload-progress-text">已选 {{ recordForm.repair_images_after.length }} / 30</div>
          <div v-if="recordForm.repair_images_after.length > 0" class="repair-image-preview-wrap">
            <div v-for="(img, index) in recordForm.repair_images_after" :key="`${img}-${index}`" class="repair-image-box">
              <el-image lazy loading="lazy"
                class="repair-image-thumb"
                :src="toImageUrl(img)"
                :preview-src-list="recordForm.repair_images_after.map((v) => toImageUrl(v))"
                fit="cover"
                preview-teleported
              />
              <el-button size="small" type="danger" plain @click="removeFormImage('after', index)">删除</el-button>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="支付截图">
          <el-upload
            action=""
            :auto-upload="false"
            :show-file-list="false"
            accept="image/*"
            multiple
            :limit="30"
            :on-change="(file) => handleRepairImageChange('payment', file)"
          >
            <el-button type="primary" plain>选择图片(最多30张)</el-button>
          </el-upload>
          <el-button
            v-if="recordForm.payment_images.length > 0"
            style="margin-left: 8px"
            type="danger"
            plain
            @click="clearAllFormImages('payment')"
          >
            全部删除图片
          </el-button>
          <div class="upload-progress-text">已选 {{ recordForm.payment_images.length }} / 30</div>
          <div v-if="recordForm.payment_images.length > 0" class="repair-image-preview-wrap">
            <div v-for="(img, index) in recordForm.payment_images" :key="`${img}-${index}`" class="repair-image-box">
              <el-image lazy loading="lazy"
                class="repair-image-thumb"
                :src="toImageUrl(img)"
                :preview-src-list="recordForm.payment_images.map((v) => toImageUrl(v))"
                fit="cover"
                preview-teleported
              />
              <el-button size="small" type="danger" plain @click="removeFormImage('payment', index)">删除</el-button>
            </div>
          </div>
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
        <el-descriptions-item label="金额">{{ currentRecord.amount ? `¥${currentRecord.amount}` : '-' }}</el-descriptions-item>
        <el-descriptions-item label="维修人员">{{ currentRecord.repair_person || '-' }}</el-descriptions-item>
        <el-descriptions-item label="支付人员">{{ currentRecord.payment_person || '-' }}</el-descriptions-item>
        <el-descriptions-item label="使用库存" :span="2">
          <div v-if="(currentRecord.inventory_usages || []).length > 0" class="inventory-usage-detail">
            <div v-for="(usage, index) in currentRecord.inventory_usages" :key="`detail-usage-${index}`" class="inventory-usage-card">
              <div class="inventory-usage-name">
                {{ usage.item_name || '未命名物品' }}
                <span v-if="usage.specification"> / {{ usage.specification }}</span>
              </div>
              <div class="inventory-usage-meta">
                <el-tag size="small" type="warning" effect="plain">领用 {{ usage.quantity }}{{ usage.unit || '' }}</el-tag>
                <span v-if="usage.location" class="inventory-location">位置：{{ usage.location }}</span>
              </div>
            </div>
          </div>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ currentRecord.remarks || '-' }}</el-descriptions-item>
        <el-descriptions-item label="维修前图片" :span="2">
          <div v-if="getRepairImagesBefore(currentRecord).length > 0" class="detail-image-list">
            <el-image lazy loading="lazy"
              v-for="(img, index) in getRepairImagesBefore(currentRecord)"
              :key="`before-${img}-${index}`"
              class="detail-image-thumb"
              :src="toImageUrl(img)"
              :preview-src-list="getRepairImagesBefore(currentRecord).map((v) => toImageUrl(v))"
              fit="cover"
              preview-teleported
            />
          </div>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="维修后图片" :span="2">
          <div v-if="getRepairImagesAfter(currentRecord).length > 0" class="detail-image-list">
            <el-image lazy loading="lazy"
              v-for="(img, index) in getRepairImagesAfter(currentRecord)"
              :key="`after-${img}-${index}`"
              class="detail-image-thumb"
              :src="toImageUrl(img)"
              :preview-src-list="getRepairImagesAfter(currentRecord).map((v) => toImageUrl(v))"
              fit="cover"
              preview-teleported
            />
          </div>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="支付截图" :span="2">
          <div v-if="getRepairPaymentImages(currentRecord).length > 0" class="detail-image-list">
            <el-image lazy loading="lazy"
              v-for="(img, index) in getRepairPaymentImages(currentRecord)"
              :key="`payment-${img}-${index}`"
              class="detail-image-thumb"
              :src="toImageUrl(img)"
              :preview-src-list="getRepairPaymentImages(currentRecord).map((v) => toImageUrl(v))"
              fit="cover"
              preview-teleported
            />
          </div>
          <span v-else>-</span>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>

  <!-- 隐藏打印区域：用于 PDF 截图导出 -->
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
          <th>金额</th>
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
          <td>{{ r.amount }}</td>
          <td>{{ r.repair_person }}</td>
          <td>{{ r.remarks }}</td>
        </tr>
      </tbody>
    </table>
  </div>
  </div>

  <BusinessPublicLinkDialog
    v-model="linkDialogVisible"
    business-type="repair"
    title="维修填写链接"
    business-label="维修记录"
  />
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { repairRecordsApi, roomsApi } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Filter } from '@element-plus/icons-vue'
import * as XLSX from 'xlsx'
import { Document, Packer, Paragraph, TextRun, Table as DocxTable, TableRow, TableCell } from 'docx'
import { saveAs } from 'file-saver'
import jsPDF from 'jspdf'
import 'jspdf-autotable'
import html2canvas from 'html2canvas'
import { uploadFileByChunks } from '../utils/chunkUploader'
import { consumeAiDraft } from '../utils/aiDrafts'
import BusinessPublicLinkDialog from '../components/BusinessPublicLinkDialog.vue'

const loading = ref(false)
const linkDialogVisible = ref(false)

// 缂佺繝鎱ㄧ拋鏉跨秿閸掓銆?
const records = ref([])

// 閹靛綊鍣洪柅澶嬪
const multipleSelection = ref([])
const tableRef = ref(null)
// 閼奉亪鈧倸绨茬悰銊︾壐閺堚偓婢堆囩彯鎼达讣绱欓崘鍛啇鐏忔垶妞傛稉宥呭繁閸掕埖鎷哄陇顫嬮崣锝忕礆
const calcTableMaxHeight = () => Math.max(window.innerHeight - 220, 320)
const tableMaxHeight = ref(calcTableMaxHeight())
const handleResize = () => { tableMaxHeight.value = calcTableMaxHeight() }

// 閸掑棝銆夐惄绋垮彠
const currentPage = ref(1)
const pageSize = ref(10)
const showPrintArea = ref(false)
const printAreaRef = ref(null)

const searchQuery = ref('')
const typeFilter = ref('all')
const statusFilter = ref('all')
const sortBy = ref({ prop: 'report_date', order: 'descending' })

const dialogVisible = ref(false)
const detailDialogVisible = ref(false)
const isEdit = ref(false)
const recordFormRef = ref(null)
const repairImageFilesBefore = ref([])
const repairImageFilesAfter = ref([])
const repairPaymentImageFiles = ref([])
const uploadingRepairImages = ref(false)
const uploadProgress = ref(0)
const MAX_REPAIR_IMAGES = 30
const inventoryOptions = ref([])

const currentRecord = ref({})
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'
const API_ORIGIN = API_BASE.replace(/\/api\/?$/, '')

const allRooms = ref([])
const buildingOptions = ref([])
const filteredRooms = ref([])

// 鐞涖劌宕熼弫鐗堝祦
const recordForm = ref({
  building: '',
  room_no: '',
  repair_type: '',
  description: '',
  report_by: '',
  report_date: new Date().toISOString().split('T')[0],
  status: '待处理',
  repair_date: '',
  amount: null,
  repair_person: '',
  payment_person: '',
  inventory_usages: [],
  remarks: '',
  repair_images_before: [],
  repair_images_after: [],
  payment_images: [],
})

const toImageUrl = (value) => {
  if (!value) return ''
  const text = String(value)
  if (text.startsWith('http://') || text.startsWith('https://') || text.startsWith('blob:') || text.startsWith('data:')) {
    return text
  }
  if (text.startsWith('/')) return `${API_ORIGIN}${text}`
  return `${API_ORIGIN}/${text}`
}

const normalizeRepairImageList = (value) => {
  if (Array.isArray(value)) {
    return value.map(v => String(v)).filter(v => v.trim() !== '').slice(0, MAX_REPAIR_IMAGES)
  }
  const raw = value ? String(value) : ''
  if (!raw.trim()) return []
  if (raw.trim().startsWith('[')) {
    try {
      const arr = JSON.parse(raw)
      if (Array.isArray(arr)) {
        return arr.map(v => String(v)).filter(v => v.trim() !== '').slice(0, MAX_REPAIR_IMAGES)
      }
    } catch (_) {}
  }
  return [raw]
}

const parseLegacyRepairImages = (record) => {
  if (!record) return []
  if (record?.repair_images && Array.isArray(record.repair_images)) {
    return normalizeRepairImageList(record.repair_images)
  }
  return normalizeRepairImageList(record?.repair_image || '')
}

const parseRepairImagesByType = (record, type = 'before') => {
  if (!record) return []
  const key = type === 'after' ? 'repair_images_after' : 'repair_images_before'
  const singleKey = type === 'after' ? 'repair_image_after' : 'repair_image_before'
  const typedImages = normalizeRepairImageList(record?.[key] ?? record?.[singleKey] ?? [])
  if (typedImages.length > 0) return typedImages
  if (type === 'before') return parseLegacyRepairImages(record)
  return []
}

const getRepairImagesBefore = (record) => parseRepairImagesByType(record, 'before')
const getRepairImagesAfter = (record) => parseRepairImagesByType(record, 'after')
const getRepairPaymentImages = (record) => parseRepairImagesByType(record, 'payment')
const getRepairImages = (record) => {
  const merged = [...getRepairImagesBefore(record), ...getRepairImagesAfter(record)]
  return [...new Set(merged)].slice(0, MAX_REPAIR_IMAGES)
}

// 鐞涖劌宕熸宀冪槈鐟欏嫬鍨?
const rules = {
  building: [{ required: true, message: '请选择楼栋', trigger: 'change' }],
  room_no: [{ required: true, message: '请选择房间号', trigger: 'change' }],
  repair_type: [{ required: true, message: '请选择维修类型', trigger: 'change' }],
  description: [{ required: true, message: '请输入问题描述', trigger: 'blur' }],
  report_by: [{ required: true, message: '请输入报修人姓名', trigger: 'blur' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }]
}

// 鏉╁洦鎶ら崥搴ｆ畱鐠佹澘缍嶉崚妤勩€?
const totalRecords = ref(0)
const filteredRecords = computed(() => records.value)

// 閼惧嘲褰囬悩鑸碘偓浣割嚠鎼存梻娈戦弽鍥╊劮缁鐎?
const getStatusType = (status) => {
  switch (status) {
    case '待处理': return 'warning'
    case '处理中': return 'primary'
    case '已完成': return 'success'
    default: return 'info'
  }
}

// 閸旂姾娴囩紒缈犳叏鐠佹澘缍嶉弫鐗堝祦
const loadRecords = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      fields: 'id,building,room_no,repair_type,description,report_date,report_by,status,repair_date,repair_cost,amount,repair_person,payment_person,remarks,inventory_usages,repair_images_before,repair_images_after,repair_image_before,repair_image_after,repair_images,repair_image,payment_images,payment_image'
    }
    if (searchQuery.value.trim()) params.q = searchQuery.value.trim()
    if (typeFilter.value !== 'all') params.repair_type = typeFilter.value
    if (statusFilter.value !== 'all') params.status = statusFilter.value
    if (sortBy.value?.prop) {
      params.sort_by = sortBy.value.prop
      params.sort_order = sortBy.value.order === 'ascending' ? 'asc' : 'desc'
    }

    const response = await repairRecordsApi.listRepairRecords(params)
    records.value = response?.data?.repair_records || []
    const total = Number(response?.data?.pagination?.total ?? response?.data?.total ?? records.value.length)
    totalRecords.value = Number.isFinite(total) ? total : records.value.length
  } catch (error) {
    console.error('加载维修记录失败', error)
    ElMessage.error('加载维修记录失败')
  } finally {
    loading.value = false
  }
}

// 閹兼粎鍌ㄥ〒鍛存珟
const handleSearchClear = () => {
  searchQuery.value = ''
  currentPage.value = 1
  loadRecords()
}

const handleTypeFilter = (command) => {
  typeFilter.value = command
  currentPage.value = 1
  loadRecords()
}

const handleStatusFilter = (command) => {
  statusFilter.value = command
  currentPage.value = 1
  loadRecords()
}

// 閹烘帒绨崣妯哄
const handleSortChange = ({ prop, order }) => {
  sortBy.value = { prop, order }
  currentPage.value = 1
  loadRecords()
}

// 閸掑棝銆夐崣妯哄
const handlePageChange = (page) => {
  currentPage.value = page
  loadRecords()
}

const handleSizeChange = (size) => {
  pageSize.value = size
  currentPage.value = 1
  loadRecords()
}

// 闁瀚ㄩ崣妯哄
const handleSelectionChange = (val) => {
  multipleSelection.value = val
}

let searchDebounceTimer = null
watch(searchQuery, () => {
  currentPage.value = 1
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer)
  searchDebounceTimer = setTimeout(() => {
    loadRecords()
  }, 300)
})

// 閸旂姾娴囬幋鍧楁？閺佺増宓?
const loadRooms = async () => {
  try {
    const response = await roomsApi.listRooms({ fields: 'id,room_no,building,status' })
    allRooms.value = response.data.rooms || []
    
    // 閹绘劕褰囬幍鈧張澶夌瑝閸氬瞼娈戞ゼ鏍?
    const buildings = new Set(allRooms.value.map(room => room.building).filter(Boolean))
    buildingOptions.value = Array.from(buildings)
  } catch (error) {
    console.error('加载房间数据失败', error)
    ElMessage.error('加载房间数据失败')
  }
}

const loadInventoryOptions = async () => {
  try {
    const response = await repairRecordsApi.listInventoryOptions()
    inventoryOptions.value = response?.data?.items || []
  } catch (error) {
    console.error('加载库存选项失败', error)
  }
}

const handleBuildingChange = (building) => {
  recordForm.value.room_no = '' // 濞撳懐鈹栭幋鍧楁？闁瀚?
  filteredRooms.value = allRooms.value.filter(room => room.building === building)
}

const openAddDialog = () => {
  isEdit.value = false
  for (const item of repairImageFilesBefore.value) {
    if (String(item?.url || '').startsWith('blob:')) URL.revokeObjectURL(item.url)
  }
  for (const item of repairImageFilesAfter.value) {
    if (String(item?.url || '').startsWith('blob:')) URL.revokeObjectURL(item.url)
  }
  for (const item of repairPaymentImageFiles.value) {
    if (String(item?.url || '').startsWith('blob:')) URL.revokeObjectURL(item.url)
  }
  repairImageFilesBefore.value = []
  repairImageFilesAfter.value = []
  repairPaymentImageFiles.value = []
  uploadingRepairImages.value = false
  uploadProgress.value = 0
  recordForm.value = {
    building: '',
    room_no: '',
    repair_type: '',
    description: '',
    report_by: '',
    report_date: new Date().toISOString().split('T')[0],
    status: '待处理',
    repair_date: '',
    amount: null,
    repair_person: '',
    payment_person: '',
    inventory_usages: [],
    remarks: '',
    repair_images_before: [],
    repair_images_after: [],
    payment_images: []
  }
  filteredRooms.value = []
  dialogVisible.value = true
}

const applyRepairDraft = () => {
  const draft = consumeAiDraft('repair')
  if (!draft) return
  openAddDialog()
  if (draft.building) {
    recordForm.value.building = String(draft.building)
    filteredRooms.value = allRooms.value.filter(room => room.building === recordForm.value.building)
  }
  if (draft.room_no) recordForm.value.room_no = String(draft.room_no)
  if (draft.repair_type) recordForm.value.repair_type = String(draft.repair_type)
  if (draft.description) recordForm.value.description = String(draft.description)
  if (draft.report_by) recordForm.value.report_by = String(draft.report_by)
  if (draft.report_date) recordForm.value.report_date = String(draft.report_date)
  if (draft.status) recordForm.value.status = String(draft.status)
  if (draft.repair_date) recordForm.value.repair_date = String(draft.repair_date)
  if (draft.amount !== undefined && draft.amount !== null && draft.amount !== '') {
    recordForm.value.amount = Number(draft.amount)
  } else if (draft.repair_cost !== undefined && draft.repair_cost !== null && draft.repair_cost !== '') {
    recordForm.value.amount = Number(draft.repair_cost)
  }
  if (draft.repair_person) recordForm.value.repair_person = String(draft.repair_person)
  if (draft.payment_person) recordForm.value.payment_person = String(draft.payment_person)
  if (Array.isArray(draft.inventory_usages)) recordForm.value.inventory_usages = draft.inventory_usages
  if (draft.remarks) recordForm.value.remarks = String(draft.remarks)
  ElMessage.success('AI 草稿已带入维修记录表单')
}

// 鏌ョ湅鐠佹澘缍嶇拠锔藉剰
const viewRecord = async (row) => {
  currentRecord.value = { ...row }
  detailDialogVisible.value = true
  try {
    const response = await repairRecordsApi.getRepairRecord(row.id)
    currentRecord.value = response?.data?.repair_record || { ...row }
  } catch (error) {
    console.error('获取维修详情失败', error)
  }
}

// 缂栬緫鐠佹澘缍?
const editRecord = (row) => {
  isEdit.value = true
  for (const item of repairImageFilesBefore.value) {
    if (String(item?.url || '').startsWith('blob:')) URL.revokeObjectURL(item.url)
  }
  for (const item of repairImageFilesAfter.value) {
    if (String(item?.url || '').startsWith('blob:')) URL.revokeObjectURL(item.url)
  }
  for (const item of repairPaymentImageFiles.value) {
    if (String(item?.url || '').startsWith('blob:')) URL.revokeObjectURL(item.url)
  }
  repairImageFilesBefore.value = []
  repairImageFilesAfter.value = []
  repairPaymentImageFiles.value = []
  uploadingRepairImages.value = false
  uploadProgress.value = 0
  recordForm.value = {
    ...row,
    amount: row.amount ?? row.repair_cost ?? null,
    inventory_usages: Array.isArray(row.inventory_usages) ? row.inventory_usages : [],
    repair_images_before: getRepairImagesBefore(row),
    repair_images_after: getRepairImagesAfter(row),
    payment_images: getRepairPaymentImages(row)
  }

  if (row.building) {
    filteredRooms.value = allRooms.value.filter(room => room.building === row.building)
  }

  dialogVisible.value = true
}

const getFormImageField = (type) => {
  if (type === 'after') return 'repair_images_after'
  if (type === 'payment') return 'payment_images'
  return 'repair_images_before'
}
const getPendingImageFiles = (type) => {
  if (type === 'after') return repairImageFilesAfter
  if (type === 'payment') return repairPaymentImageFiles
  return repairImageFilesBefore
}

const safeUploadPart = (value, fallback = 'unknown') => {
  const clean = String(value || '').trim().replace(/[^0-9A-Za-z_-]/g, '_').replace(/_+/g, '_').replace(/^_+|_+$/g, '')
  return clean || fallback
}

const buildRepairUploadSubDir = (imageType, formData, targetId) => {
  const building = safeUploadPart(formData?.building, 'building')
  const roomNo = safeUploadPart(formData?.room_no, 'room')
  const recordPart = safeUploadPart(targetId, 'new')
  const phase = imageType === 'after' ? 'after' : 'before'
  return `${phase}/${building}_${roomNo}/record_${recordPart}`
}

const handleRepairImageChange = (type, file) => {
  if (!file || !file.raw) return
  const field = getFormImageField(type)
  if ((recordForm.value[field] || []).length >= MAX_REPAIR_IMAGES) {
    ElMessage.warning(`最多上传 ${MAX_REPAIR_IMAGES} 张图片`)
    return
  }
  if (!String(file.raw.type || '').startsWith('image/')) {
    ElMessage.warning('请上传图片文件')
    return
  }
  if (file.raw.size && file.raw.size > 20 * 1024 * 1024) {
    ElMessage.warning('图片请控制在 20MB 以内')
    return
  }
  const url = URL.createObjectURL(file.raw)
  getPendingImageFiles(type).value.push({ file: file.raw, url })
  recordForm.value[field] = [...(recordForm.value[field] || []), url]
}

const addInventoryUsage = () => {
  recordForm.value.inventory_usages = [...(recordForm.value.inventory_usages || []), { warehouse_item_id: null, quantity: 1 }]
}

const removeInventoryUsage = (index) => {
  const list = [...(recordForm.value.inventory_usages || [])]
  if (index < 0 || index >= list.length) return
  list.splice(index, 1)
  recordForm.value.inventory_usages = list
}

const removeFormImage = (type, index) => {
  const field = getFormImageField(type)
  const list = recordForm.value[field] || []
  if (index < 0 || index >= list.length) return
  const target = list[index]
  list.splice(index, 1)
  recordForm.value[field] = [...list]
  getPendingImageFiles(type).value = getPendingImageFiles(type).value.filter(item => item.url !== target)
  if (String(target || '').startsWith('blob:')) {
    URL.revokeObjectURL(String(target))
  }
}

const clearAllFormImages = (type) => {
  const field = getFormImageField(type)
  const list = [...(recordForm.value[field] || [])]
  list.forEach((target) => {
    if (String(target || '').startsWith('blob:')) {
      URL.revokeObjectURL(String(target))
    }
  })
  recordForm.value[field] = []
  getPendingImageFiles(type).value = []
}

// 纭鍒犻櫎
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

// 鎵归噺鍒犻櫎纭
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

// 鍒犻櫎鐠佹澘缍?
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

const batchDeleteRecords = async () => {
  if (!multipleSelection.value.length) return
  loading.value = true
  const failures = []
  let successCount = 0

  for (const row of multipleSelection.value) {
    try {
      await repairRecordsApi.deleteRepairRecord(row.id)
      successCount++
      // 鏉炶浜曞鑸垫娴犮儱鍣虹亸鎴濊嫙閸欐垵鍟撻崗銉ヮ嚠SQLite閻ㄥ嫰鏀ｇ粩鐐扮挨
      await new Promise(r => setTimeout(r, 50))
    } catch (error) {
      const msg = error?.response?.data?.message || error?.message || '删除失败'
      failures.push(`${row.room_no || ""}(ID:${row.id})：${msg}`)
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
    ElMessage.success(`批量删除完成：成功 ${successCount} 条`)
  } else {
    ElMessage.error(`批量删除完成：成功 ${successCount} 条，失败 ${failures.length} 条`)
    console.warn('批量删除失败详情:\n' + failures.join('\n'))
  }
}

// 閹绘劒姘︾悰銊ュ礋
const submitForm = async () => {
  if (!recordFormRef.value) return

  await recordFormRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        const formData = { ...recordForm.value }
        formData.amount = formData.amount === '' ? null : formData.amount
        formData.repair_cost = formData.amount
        formData.inventory_usages = (formData.inventory_usages || []).filter(item => item?.warehouse_item_id && Number(item?.quantity) > 0)
        const existingBeforeImages = (formData.repair_images_before || []).filter(v => typeof v === 'string' && !v.startsWith('blob:')).slice(0, MAX_REPAIR_IMAGES)
        const existingAfterImages = (formData.repair_images_after || []).filter(v => typeof v === 'string' && !v.startsWith('blob:')).slice(0, MAX_REPAIR_IMAGES)
        const existingPaymentImages = (formData.payment_images || []).filter(v => typeof v === 'string' && !v.startsWith('blob:')).slice(0, MAX_REPAIR_IMAGES)
        formData.repair_images_before = existingBeforeImages
        formData.repair_images_after = existingAfterImages
        formData.payment_images = existingPaymentImages
        delete formData.repair_images
        delete formData.repair_image
        delete formData.repair_image_before
        delete formData.repair_image_after

        let targetId = formData.id
        if (isEdit.value) {
          await repairRecordsApi.updateRepairRecord(formData.id, formData)
          ElMessage.success(isEdit.value ? '更新成功' : '新增成功')
        } else {
          const created = await repairRecordsApi.addRepairRecord(formData)
          targetId = created?.data?.id
          ElMessage.success(isEdit.value ? '更新成功' : '新增成功')
        }

        const pendingUploads = [
          ...repairImageFilesBefore.value.map(item => ({ ...item, imageType: 'before' })),
          ...repairImageFilesAfter.value.map(item => ({ ...item, imageType: 'after' })),
          ...repairPaymentImageFiles.value.map(item => ({ ...item, imageType: 'payment' }))
        ]

        if (targetId && pendingUploads.length > 0) {
          uploadingRepairImages.value = true
          uploadProgress.value = 0
          const uploadedBefore = []
          const uploadedAfter = []
          const uploadedPayment = []
          const total = pendingUploads.length

          for (let i = 0; i < total; i++) {
            const item = pendingUploads[i]
            const result = await uploadFileByChunks(item.file, {
              category: 'repair_records',
              subDir: buildRepairUploadSubDir(item.imageType, formData, targetId),
              chunkSize: 1024 * 1024,
              maxRetries: 3,
              retryDelay: 800,
              onProgress: (percent) => {
                const finished = i + (Number(percent || 0) / 100)
                uploadProgress.value = Math.floor((finished / total) * 100)
              },
            })
            const fileUrl = String(result?.file_url || '')
            if (!fileUrl) {
              throw new Error('上传成功但未返回图片地址')
            }
            if (item.imageType === 'after') uploadedAfter.push(fileUrl)
            else if (item.imageType === 'payment') uploadedPayment.push(fileUrl)
            else uploadedBefore.push(fileUrl)
            if (String(item.url || '').startsWith('blob:')) {
              URL.revokeObjectURL(item.url)
            }
          }

          const finalBefore = [...existingBeforeImages, ...uploadedBefore].slice(0, MAX_REPAIR_IMAGES)
          const finalAfter = [...existingAfterImages, ...uploadedAfter].slice(0, MAX_REPAIR_IMAGES)
          const finalPayment = [...existingPaymentImages, ...uploadedPayment].slice(0, MAX_REPAIR_IMAGES)
          await repairRecordsApi.updateRepairRecord(targetId, {
            repair_images_before: finalBefore,
            repair_images_after: finalAfter,
            payment_images: finalPayment,
          })
          recordForm.value.repair_images_before = finalBefore
          recordForm.value.repair_images_after = finalAfter
          recordForm.value.payment_images = finalPayment
          uploadProgress.value = 100
        }

        dialogVisible.value = false
        repairImageFilesBefore.value = []
        repairImageFilesAfter.value = []
        repairPaymentImageFiles.value = []
        uploadingRepairImages.value = false
        uploadProgress.value = 0
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

// 妞ょ敻娼伴崝鐘烘祰閺冩儼骞忛崣鏍ㄦ殶閹?& 閻╂垵鎯夌粣妤€褰涢崣妯哄
onMounted(async () => {
  await loadRooms()
  await loadInventoryOptions()
  applyRepairDraft()
  await loadRecords()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})

// 瀵煎嚭閻╃鍙?
const handleExportCommand = (cmd) => {
  if (cmd === 'excel') return exportToExcel()
  if (cmd === 'word') return exportToWord()
  if (cmd === 'pdf') return exportToPDF()
}

const getExportRows = () => {
  return filteredRecords.value.map(r => ({
    ID: r.id,
    '楼栋': r.building,
    '房间号': r.room_no,
    '维修类型': r.repair_type,
    '问题描述': r.description,
    '报修日期': r.report_date,
    '报修人': r.report_by,
    '状态': r.status,
    '维修日期': r.repair_date,
    '金额': r.amount,
    '维修人员': r.repair_person,
    '备注': r.remarks
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
    const headerCells = ['ID','楼栋','房间号','维修类型','问题描述','报修日期','报修人','状态','维修日期','金额','维修人员','备注'].map(text =>
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
          new TableCell({ children: [new Paragraph(String(r['金额']))] }),
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
    ElMessage.success('PDF 导出完成（中文已正常显示）')
  } catch (e) {
    console.error('导出 PDF 失败', e)
    ElMessage.error('导出 PDF 失败')
  } finally {
    showPrintArea.value = false
  }
}

// 瀵煎叆 Excel
const handleImportFile = async (file) => {
  const reader = new FileReader()
  reader.onload = async (e) => {
    try {
      const data = new Uint8Array(e.target.result)
      const workbook = XLSX.read(data, { type: 'array' })
      const firstSheetName = workbook.SheetNames[0]
      const worksheet = workbook.Sheets[firstSheetName]
      const results = XLSX.utils.sheet_to_json(worksheet)
      
      let successCount = 0
      for (const row of results) {
        // 閺勭姴鐨?Excel 閺佺増宓?
        const payload = {
          building: '',
          room_no: row['房间号'],
          repair_type: row['维修类型'] || '其他',
          description: row['问题描述'] || '',
          report_by: row['报修人'] || 'Excel导入',
          report_date: row['报修日期'] || new Date().toISOString().split('T')[0],
          status: row['状态'] || '待处理',
          amount: row['金额'] || row['维修费用'] || null,
          repair_person: row['维修人员'] || '',
          remarks: row['备注'] || ''
        }
        if (payload.room_no) {
           const room = allRooms.value.find(r => r.room_no == payload.room_no)
           if (room) {
             payload.building = room.building
             await repairRecordsApi.addRepairRecord(payload)
             successCount++
           } else {
              console.warn(`未找到房间号: ${payload.room_no} 的楼栋信息`)
           }
        }
      }
      ElMessage.success(`成功导入 ${successCount} 条记录`)
      loadRecords()
    } catch (error) {
      console.error('导入失败', error)
      ElMessage.error('导入失败，请检查文件格式')
    }
  }
  reader.readAsArrayBuffer(file.raw)
}
</script>

<style scoped>
.repair-records-container {
  padding: 20px;
  border-radius: 16px;
}

.page-header {
  display: flex;
  align-items: center;
  margin-bottom: 18px;
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
  width: 240px;
}

.toolbar-btn {
  margin-left: 0 !important;
}

.table-image-thumb {
  width: 40px;
  height: 40px;
  border-radius: 6px;
}

.repair-image-preview-wrap {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  width: 100%;
}

.repair-image-box {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.inventory-usage-wrap {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.inventory-usage-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 140px auto;
  gap: 10px;
  align-items: center;
}

.inventory-usage-detail {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.inventory-usage-summary {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.inventory-more-text {
  font-size: 12px;
  color: var(--text-secondary);
}

.inventory-usage-card {
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--surface-muted);
  border: 1px solid var(--surface-border);
}

.inventory-usage-name {
  font-weight: 600;
  color: var(--text-main);
}

.inventory-usage-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 6px;
}

.inventory-location {
  font-size: 12px;
  color: var(--text-secondary);
}

.upload-progress-text {
  margin-top: 8px;
  color: #64748b;
  font-size: 12px;
}

.repair-image-thumb {
  width: 92px;
  height: 92px;
  border-radius: 8px;
}

.detail-image-thumb {
  width: 120px;
  height: 120px;
  border-radius: 8px;
}

.detail-image-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
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

:deep(.records-table) {
  --el-table-header-bg-color: var(--surface-muted);
  --el-table-tr-bg-color: var(--card-bg);
  --el-table-row-hover-bg-color: rgba(37, 99, 235, 0.06);
  --el-table-border-color: var(--surface-border);
  border-radius: 12px;
  overflow: hidden;
}

:deep(.records-table .el-table__header-wrapper th.el-table__cell) {
  font-weight: 700;
  color: var(--text-main);
  height: 48px;
}

:deep(.records-table .el-table__body-wrapper td.el-table__cell) {
  padding: 12px 0;
}

:deep(.records-table .el-table__fixed-right::before),
:deep(.records-table .el-table__fixed::before) {
  background-color: transparent;
}

:deep(.records-table .el-tag) {
  border-radius: 999px;
  padding: 0 10px;
}

@media (max-width: 768px) {
  .search-input {
    width: 100%;
  }
}

/* 闂呮劘妫岄幍鎾冲祪閸栧搫鐓欓弽宄扮础閿涘苯顔旀惔锕佺窛婢堆備簰娣囨繆鐦夐幋顏勬禈濞撳懏娅?*/
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




