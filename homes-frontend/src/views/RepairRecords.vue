<template>
  <div>
  <div class="repair-records-container" :class="{ 'repair-records-container--mobile': mobileMode }">
    <div class="page-header">
      <div v-if="mobileMode" class="repair-mobile-overview">
        <div class="repair-mobile-stat">
          <strong>{{ totalRecords }}</strong>
          <span>维修记录</span>
        </div>
        <div class="repair-mobile-stat">
          <strong>{{ pendingRepairCount }}</strong>
          <span>待跟进</span>
        </div>
      </div>
      <div class="header-operations">
        <el-input
          class="search-input"
          v-model="searchQuery"
          placeholder="搜索房间号或维修类型"
          clearable
          @clear="handleSearchClear"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button class="toolbar-btn" type="primary" @click="openAddDialog">新增</el-button>
        <el-button class="toolbar-btn" type="primary" plain @click="openAiDialog">AI 输入</el-button>
        <el-button class="toolbar-btn" type="success" @click="linkDialogVisible = true">链接</el-button>
        <el-button v-if="!mobileMode" class="toolbar-btn" type="danger" :disabled="multipleSelection.length === 0" @click="confirmBatchDelete">删除</el-button>
        <el-dropdown v-if="!mobileMode" trigger="click" @command="handleExportCommand">
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
          v-if="!mobileMode"
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
      <div v-if="mobileMode" class="repair-mobile-list" v-loading="loading">
        <el-empty v-if="records.length === 0" description="暂无维修记录" :image-size="48" />
        <article v-for="record in records" :key="record.id" class="repair-mobile-card">
          <div class="repair-mobile-card__header">
            <div>
              <div class="repair-mobile-card__title">
                {{ record.room_no || record.room_nos || record.building || '未定位房间' }}
              </div>
              <div class="repair-mobile-card__meta">
                {{ record.scope_type || '单个房间' }} · {{ record.repair_type || '其他' }}
              </div>
            </div>
            <el-tag :type="getStatusType(record.status)">{{ record.status }}</el-tag>
          </div>

          <div class="repair-mobile-card__desc">{{ record.description || '未填写问题描述' }}</div>

          <div class="repair-mobile-card__grid">
            <div>
              <strong>{{ record.report_date || '-' }}</strong>
              <span>报修日期</span>
            </div>
            <div>
              <strong>{{ record.report_by || '-' }}</strong>
              <span>报修人</span>
            </div>
            <div>
              <strong>{{ record.repair_person || '-' }}</strong>
              <span>维修人员</span>
            </div>
            <div>
              <strong>{{ record.amount ? `¥${record.amount}` : '-' }}</strong>
              <span>金额</span>
            </div>
          </div>

          <div class="repair-mobile-card__actions">
            <el-button size="small" type="primary" @click="viewRecord(record)">查看</el-button>
            <el-button size="small" @click="editRecord(record)">编辑</el-button>
            <el-button size="small" type="danger" plain @click="confirmDelete(record)">删除</el-button>
          </div>
        </article>
      </div>

      <el-table 
        v-else
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
      <el-table-column label="序号" width="80" align="center">
        <template #default="{ $index }">
          {{ repairRowStart + $index + 1 }}
        </template>
      </el-table-column>
      <el-table-column prop="scope_type" label="维修范围" width="110" sortable="custom"></el-table-column>
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
                  <el-dropdown-item command="清洁费用">清洁费用</el-dropdown-item>
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
      <el-table-column prop="payment_person" label="支付人员" width="120"></el-table-column>
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

    <!-- 添加/编辑维修记录抽屉 -->
    <el-drawer
      v-model="dialogVisible"
      :title="isEdit ? '编辑维修记录' : '添加维修记录'"
      direction="rtl"
      :size="mobileMode ? '100%' : '720px'"
    >
      <el-form :model="recordForm" label-width="100px" :rules="rules" ref="recordFormRef">
        <el-form-item label="维修范围" prop="scope_type">
          <el-select v-model="recordForm.scope_type" placeholder="请选择维修范围" style="width: 100%" @change="handleScopeTypeChange">
            <el-option v-for="item in REPAIR_SCOPE_OPTIONS" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="recordForm.scope_type !== '单个房间'" label="楼栋" prop="building">
          <el-select
            v-model="recordForm.building"
            placeholder="请选择涉及楼栋"
            style="width: 100%"
            multiple
            filterable
            allow-create
            default-first-option
            clearable
          >
            <el-option
              v-for="building in buildingOptions"
              :key="building"
              :label="building"
              :value="building"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-else label="楼栋" prop="building">
          <el-select
            v-model="recordForm.building"
            placeholder="请选择或手动输入楼栋"
            style="width: 100%"
            filterable
            allow-create
            default-first-option
            clearable
            @change="handleBuildingChange"
          >
            <el-option 
              v-for="building in buildingOptions" 
              :key="building" 
              :label="building" 
              :value="building" 
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="recordForm.scope_type === '单个房间'" label="房间号" prop="room_no">
          <el-select
            v-model="recordForm.room_no"
            placeholder="请选择或手动输入房间号"
            style="width: 100%"
            filterable
            allow-create
            default-first-option
            clearable
          >
            <el-option 
              v-for="room in filteredRooms" 
              :key="room.room_no" 
              :label="room.room_no" 
              :value="room.room_no" 
            />
          </el-select>
        </el-form-item>
        <el-form-item v-else-if="recordForm.scope_type === '多个房间'" label="多个房间号" prop="room_nos">
          <el-input
            v-model="recordForm.room_nos"
            type="textarea"
            :rows="2"
            placeholder="请输入多个房间号，例如：B-502，B-503"
          />
        </el-form-item>
        <el-form-item label="维修类型" prop="repair_type">
          <el-select v-model="recordForm.repair_type" placeholder="请选择维修类型" style="width: 100%">
            <el-option label="水电维修" value="水电维修" />
            <el-option label="家具维修" value="家具维修" />
            <el-option label="电器维修" value="电器维修" />
            <el-option label="清洁费用" value="清洁费用" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item label="问题描述" prop="description">
          <el-input v-model="recordForm.description" type="textarea" :rows="3" placeholder="请输入问题描述" />
        </el-form-item>
        <el-form-item label="报修人" prop="report_by">
          <el-select
            v-model="recordForm.report_by"
            placeholder="请选择租户名或手动输入"
            style="width: 100%"
            filterable
            allow-create
            default-first-option
            clearable
          >
            <el-option
              v-for="name in tenantNameOptions"
              :key="name"
              :label="name"
              :value="name"
            />
          </el-select>
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
              <el-select
                v-model="usage.warehouse_item_id"
                placeholder="输入库存物品名称后自动筛选"
                style="width: 100%"
                filterable
                clearable
                default-first-option
                reserve-keyword="false"
              >
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
        <el-form-item label="维修前图片" class="repair-image-field">
          <div class="repair-image-uploader">
            <div
              class="form-image-dropzone"
              :class="{ 'form-image-dropzone--active': repairImageDragActive.before }"
              @dragenter.prevent="repairImageDragActive.before = true"
              @dragover.prevent="repairImageDragActive.before = true"
              @dragleave.prevent="repairImageDragActive.before = false"
              @drop.prevent="handleRepairImageDrop('before', $event)"
              @paste="handleRepairImagePaste('before', $event)"
              tabindex="0"
            >
              <div class="form-image-dropzone__title">拖拽图片到这里</div>
              <div class="form-image-dropzone__hint">也支持直接粘贴截图</div>
            </div>
            <div class="repair-image-actions">
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
                type="danger"
                plain
                @click="clearAllFormImages('before')"
              >
                全部删除图片
              </el-button>
            </div>
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
          </div>
        </el-form-item>
        <el-form-item label="维修后图片" class="repair-image-field">
          <div class="repair-image-uploader">
            <div
              class="form-image-dropzone"
              :class="{ 'form-image-dropzone--active': repairImageDragActive.after }"
              @dragenter.prevent="repairImageDragActive.after = true"
              @dragover.prevent="repairImageDragActive.after = true"
              @dragleave.prevent="repairImageDragActive.after = false"
              @drop.prevent="handleRepairImageDrop('after', $event)"
              @paste="handleRepairImagePaste('after', $event)"
              tabindex="0"
            >
              <div class="form-image-dropzone__title">拖拽图片到这里</div>
              <div class="form-image-dropzone__hint">也支持直接粘贴截图</div>
            </div>
            <div class="repair-image-actions">
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
                type="danger"
                plain
                @click="clearAllFormImages('after')"
              >
                全部删除图片
              </el-button>
            </div>
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
          </div>
        </el-form-item>
        <el-form-item label="支付截图" class="repair-image-field">
          <div class="repair-image-uploader">
            <div
              class="form-image-dropzone"
              :class="{ 'form-image-dropzone--active': repairImageDragActive.payment }"
              @dragenter.prevent="repairImageDragActive.payment = true"
              @dragover.prevent="repairImageDragActive.payment = true"
              @dragleave.prevent="repairImageDragActive.payment = false"
              @drop.prevent="handleRepairImageDrop('payment', $event)"
              @paste="handleRepairImagePaste('payment', $event)"
              tabindex="0"
            >
              <div class="form-image-dropzone__title">拖拽图片到这里</div>
              <div class="form-image-dropzone__hint">也支持直接粘贴截图</div>
            </div>
            <div class="repair-image-actions">
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
                type="danger"
                plain
                @click="clearAllFormImages('payment')"
              >
                全部删除图片
              </el-button>
            </div>
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
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitForm">确认</el-button>
        </span>
      </template>
    </el-drawer>

    <!-- 查看维修记录详情对话框 -->
    <el-dialog
      v-model="detailDialogVisible"
      title="维修记录详情"
      :fullscreen="mobileMode"
      :width="mobileMode ? undefined : '50%'"
    >
            <el-descriptions :column="mobileMode ? 1 : 2" border>
        <el-descriptions-item label="ID">{{ currentRecord.id }}</el-descriptions-item>
        <el-descriptions-item label="维修范围">{{ currentRecord.scope_type || '单个房间' }}</el-descriptions-item>
        <el-descriptions-item label="楼栋">{{ currentRecord.building }}</el-descriptions-item>
        <el-descriptions-item label="房间号">{{ currentRecord.room_no }}</el-descriptions-item>
        <el-descriptions-item label="多个房间号">{{ currentRecord.room_nos || '-' }}</el-descriptions-item>
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

    <el-dialog
      title="AI 输入维修"
      v-model="aiDialog.visible"
      :width="mobileMode ? '96%' : '620px'"
      class="app-ai-dialog"
      modal-class="app-ai-dialog-overlay"
      @close="resetAiDialog"
    >
      <el-form label-width="92px">
        <el-form-item label="文字描述">
          <el-input
            v-model="aiDialog.text"
            type="textarea"
            :rows="5"
            placeholder="例如：A栋 301 洗手间漏水，张三报修，今天待处理。也可以上传现场照片、报修截图或支付截图让 AI 识别。"
            @paste="handleAiPaste"
          />
        </el-form-item>
        <el-form-item label="图片识别">
          <div class="ai-upload-panel">
            <div
              class="ai-dropzone"
              :class="{ 'ai-dropzone--active': aiDialog.dragActive }"
              @dragenter.prevent="aiDialog.dragActive = true"
              @dragover.prevent="aiDialog.dragActive = true"
              @dragleave.prevent="aiDialog.dragActive = false"
              @drop.prevent="handleAiDrop"
              @paste="handleAiPaste"
              tabindex="0"
            >
              <div class="ai-dropzone__title">拖拽图片到这里识别</div>
              <div class="ai-dropzone__hint">也可以点击下面按钮选择图片，或直接粘贴截图。识别后会自动带入维修前图片。</div>
            </div>
            <div class="ai-upload-actions">
              <el-upload
                action=""
                :auto-upload="false"
                :show-file-list="false"
                accept="image/*"
                multiple
                :limit="20"
                :on-change="handleAiImageChange"
              >
                <el-button type="primary" plain>选择图片</el-button>
              </el-upload>
              <el-button
                v-if="aiDialog.images.length"
                type="danger"
                plain
                @click="clearAiImages"
              >
                清空图片
              </el-button>
            </div>
          </div>
          <div class="upload-progress-text">已选 {{ aiDialog.images.length }} / 20</div>
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
  </div>

  <!-- 隐藏打印区域：用于 PDF 截图导出 -->
  <div v-if="showPrintArea" ref="printAreaRef" class="print-area">
    <h2 style="text-align:center; margin-bottom: 12px;">维修记录</h2>
    <table class="print-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>维修范围</th>
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
          <td>{{ r.scope_type || '单个房间' }}</td>
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
import { repairRecordsApi, roomsApi, tenantsApi } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Filter } from '@element-plus/icons-vue'
import * as XLSX from 'xlsx'
import { Document, Packer, Paragraph, TextRun, Table as DocxTable, TableRow, TableCell } from 'docx'
import { saveAs } from 'file-saver'
import jsPDF from 'jspdf'
import 'jspdf-autotable'
import html2canvas from 'html2canvas'
import { uploadFileByChunks } from '../utils/chunkUploader'
import BusinessPublicLinkDialog from '../components/BusinessPublicLinkDialog.vue'
import { DISPLAY_MODE_EVENT, getPreferredDisplayMode } from '../utils/displayMode'

const loading = ref(false)
const linkDialogVisible = ref(false)
const mobileMode = ref(false)

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
const repairRowStart = computed(() => (currentPage.value - 1) * pageSize.value)

const searchQuery = ref('')
const typeFilter = ref('all')
const statusFilter = ref('all')
const sortBy = ref({ prop: 'report_date', order: 'descending' })

const dialogVisible = ref(false)
const detailDialogVisible = ref(false)
const isEdit = ref(false)
const recordFormRef = ref(null)
const aiDialog = reactive({
  visible: false,
  loading: false,
  text: '',
  images: [],
  dragActive: false
})
const repairImageFilesBefore = ref([])
const repairImageFilesAfter = ref([])
const repairPaymentImageFiles = ref([])
const repairImageDragActive = reactive({
  before: false,
  after: false,
  payment: false,
})
const uploadingRepairImages = ref(false)
const uploadProgress = ref(0)
const MAX_REPAIR_IMAGES = 30
const inventoryOptions = ref([])
const tenantNameOptions = ref([])
const formatReportByOption = (building, roomNo, name) => {
  const buildingText = String(building || '').trim()
  const roomText = String(roomNo || '').trim()
  const nameText = String(name || '').trim()
  if (!nameText) return ''
  let roomPart = roomText
  if (buildingText && roomText) {
    const normalizedRoom = roomText.replace('栋', '').replaceAll('_', '-')
    const prefixes = [`${buildingText}-`, `${buildingText}栋-`, buildingText]
    for (const prefix of prefixes) {
      if (normalizedRoom.startsWith(prefix)) {
        roomPart = normalizedRoom.slice(prefix.length).replace(/^-+/, '')
        break
      }
    }
  }
  if (buildingText && roomPart) return `${buildingText}-${roomPart}-${nameText}`
  if (roomText) return `${roomText}-${nameText}`
  return nameText
}

const currentRecord = ref({})
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'
const API_ORIGIN = API_BASE.replace(/\/api\/?$/, '')
const REPAIR_SCOPE_OPTIONS = ['单个房间', '多个房间', '公共区域', '整层', '整栋', '楼栋']

const allRooms = ref([])
const buildingOptions = ref([])
const filteredRooms = ref([])

// 鐞涖劌宕熼弫鐗堝祦
const recordForm = ref({
  scope_type: '单个房间',
  building: '',
  room_no: '',
  room_nos: '',
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
const parseBuildingModel = (value, scopeType) => {
  if (scopeType !== '单个房间') {
    if (Array.isArray(value)) return value.map(v => String(v || '').trim()).filter(Boolean)
    return String(value || '').split(/[，,、;\s]+/).map(v => v.trim()).filter(Boolean)
  }
  if (Array.isArray(value)) return String(value[0] || '').trim()
  return String(value || '').trim()
}
const serializeBuildingModel = (value, scopeType) => {
  if (scopeType !== '单个房间') {
    const items = Array.isArray(value) ? value : parseBuildingModel(value, scopeType)
    return items.map(v => String(v || '').trim()).filter(Boolean).join('，')
  }
  return Array.isArray(value) ? String(value[0] || '').trim() : String(value || '').trim()
}

const validateRepairBuilding = (_rule, value, callback) => {
  const scopeType = String(recordForm.value.scope_type || '单个房间')
  if (scopeType === '单个房间') {
    if (!String(value || '').trim()) return callback(new Error('请输入或选择楼栋'))
  }
  if (scopeType !== '单个房间') {
    const items = Array.isArray(value) ? value.filter(Boolean) : []
    if (!items.length) return callback(new Error('请选择楼栋'))
  }
  callback()
}
const validateRepairRoomNo = (_rule, value, callback) => {
  if (String(recordForm.value.scope_type || '单个房间') === '单个房间' && !String(value || '').trim()) {
    return callback(new Error('请输入或选择房间号'))
  }
  callback()
}
const validateRepairRoomNos = (_rule, value, callback) => {
  if (String(recordForm.value.scope_type || '') === '多个房间' && !String(value || '').trim()) {
    return callback(new Error('请输入多个房间号'))
  }
  callback()
}
// 鐞涖劌宕熸宀冪槈鐟欏嫬鍨?
const rules = {
  scope_type: [{ required: true, message: '请选择维修范围', trigger: 'change' }],
  building: [{ validator: validateRepairBuilding, trigger: ['change', 'blur'] }],
  room_no: [{ validator: validateRepairRoomNo, trigger: ['change', 'blur'] }],
  room_nos: [{ validator: validateRepairRoomNos, trigger: ['change', 'blur'] }],
  repair_type: [{ required: true, message: '请选择维修类型', trigger: 'change' }],
  description: [{ required: true, message: '请输入问题描述', trigger: 'blur' }],
  report_by: [{ required: true, message: '请输入报修人姓名', trigger: 'blur' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }]
}

// 鏉╁洦鎶ら崥搴ｆ畱鐠佹澘缍嶉崚妤勩€?
const totalRecords = ref(0)
const filteredRecords = computed(() => records.value)
const pendingRepairCount = computed(() => records.value.filter((item) => item?.status !== '已完成').length)
const syncDisplayMode = () => {
  mobileMode.value = getPreferredDisplayMode() === 'mobile'
}

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
      fields: 'id,building,room_no,scope_type,room_nos,repair_type,description,report_date,report_by,status,repair_date,repair_cost,amount,repair_person,payment_person,remarks,inventory_usages,repair_images_before,repair_images_after,repair_image_before,repair_image_after,repair_images,repair_image,payment_images,payment_image'
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

const loadTenantNameOptions = async () => {
  try {
    const response = await tenantsApi.listTenants({ fields: 'name,building,room_no', page_size: 500 })
    const rows = response?.data?.tenants || []
    tenantNameOptions.value = [...new Set(rows.map(item => formatReportByOption(item?.building, item?.room_no, item?.name)).filter(Boolean))]
  } catch (error) {
    console.error('加载租户姓名失败', error)
  }
}

const handleBuildingChange = (building) => {
  filteredRooms.value = allRooms.value.filter(room => room.building === building)
  if (recordForm.value.scope_type === '单个房间') {
    recordForm.value.room_no = ''
  }
}

const handleScopeTypeChange = () => {
  const scopeType = String(recordForm.value.scope_type || '单个房间')
  recordForm.value.building = parseBuildingModel(recordForm.value.building, scopeType)
  if (scopeType === '单个房间') {
    recordForm.value.room_nos = ''
  } else if (scopeType === '多个房间') {
    recordForm.value.room_no = ''
  } else {
    recordForm.value.room_no = ''
    recordForm.value.room_nos = ''
  }
  nextTick(() => {
    recordFormRef.value?.clearValidate?.(['building', 'room_no', 'room_nos'])
  })
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
  repairImageDragActive.before = false
  repairImageDragActive.after = false
  repairImageDragActive.payment = false
  uploadingRepairImages.value = false
  uploadProgress.value = 0
  recordForm.value = {
    scope_type: '单个房间',
    building: '',
    room_no: '',
    room_nos: '',
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
  repairImageDragActive.before = false
  repairImageDragActive.after = false
  repairImageDragActive.payment = false
  uploadingRepairImages.value = false
  uploadProgress.value = 0
  recordForm.value = {
    ...row,
    scope_type: row.scope_type || '单个房间',
    building: parseBuildingModel(row.building, row.scope_type || '单个房间'),
    room_nos: row.room_nos || '',
    amount: row.amount ?? row.repair_cost ?? null,
    inventory_usages: Array.isArray(row.inventory_usages) ? row.inventory_usages : [],
    repair_images_before: getRepairImagesBefore(row),
    repair_images_after: getRepairImagesAfter(row),
    payment_images: getRepairPaymentImages(row)
  }

  if (row.building && row.scope_type === '单个房间') {
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
  const raw = file?.raw || file
  if (!raw) return
  const field = getFormImageField(type)
  if ((recordForm.value[field] || []).length >= MAX_REPAIR_IMAGES) {
    ElMessage.warning(`最多上传 ${MAX_REPAIR_IMAGES} 张图片`)
    return
  }
  if (!String(raw.type || '').startsWith('image/')) {
    ElMessage.warning('请上传图片文件')
    return
  }
  if (raw.size && raw.size > 20 * 1024 * 1024) {
    ElMessage.warning('图片请控制在 20MB 以内')
    return
  }
  const url = URL.createObjectURL(raw)
  getPendingImageFiles(type).value.push({ file: raw, url })
  recordForm.value[field] = [...(recordForm.value[field] || []), url]
}

const handleRepairImageDrop = (type, event) => {
  repairImageDragActive[type] = false
  const files = Array.from(event?.dataTransfer?.files || [])
  for (const file of files) {
    handleRepairImageChange(type, file)
  }
}

const handleRepairImagePaste = (type, event) => {
  const clipboardItems = Array.from(event?.clipboardData?.items || [])
  const imageItems = clipboardItems.filter((item) => String(item?.type || '').startsWith('image/'))
  if (!imageItems.length) return
  event.preventDefault()
  for (const item of imageItems) {
    const file = item.getAsFile()
    if (file) {
      handleRepairImageChange(type, file)
    }
  }
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
  aiDialog.dragActive = false
}

const openAiDialog = () => {
  resetAiDialog()
  aiDialog.visible = true
}

const appendAiImageFile = (rawFile) => {
  if (!rawFile) return
  if (aiDialog.images.length >= 20) {
    ElMessage.warning('最多选择 20 张图片')
    return
  }
  if (!String(rawFile.type || '').startsWith('image/')) {
    ElMessage.warning('请上传图片文件')
    return
  }
  if (rawFile.size && rawFile.size > 8 * 1024 * 1024) {
    ElMessage.warning('单张图片请控制在 8MB 以内')
    return
  }
  aiDialog.images.push({
    file: rawFile,
    url: URL.createObjectURL(rawFile)
  })
}

const handleAiImageChange = (file) => {
  if (!file || !file.raw) return
  appendAiImageFile(file.raw)
}

const handleAiDrop = (event) => {
  aiDialog.dragActive = false
  const files = Array.from(event?.dataTransfer?.files || [])
  if (!files.length) return
  for (const file of files) {
    appendAiImageFile(file)
  }
}

const handleAiPaste = (event) => {
  const clipboardItems = Array.from(event?.clipboardData?.items || [])
  const imageItems = clipboardItems.filter((item) => String(item?.type || '').startsWith('image/'))
  if (!imageItems.length) return
  event.preventDefault()
  for (const item of imageItems) {
    const file = item.getAsFile()
    if (file) {
      appendAiImageFile(file)
    }
  }
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

const applyAiDraftToForm = (draft = {}, aiImages = []) => {
  openAddDialog()
  const scopeType = String(draft.scope_type || '单个房间')
  recordForm.value.scope_type = REPAIR_SCOPE_OPTIONS.includes(scopeType) ? scopeType : '单个房间'
  recordForm.value.building = parseBuildingModel(draft.building || '', recordForm.value.scope_type)
  recordForm.value.room_no = String(draft.room_no || '')
  recordForm.value.room_nos = String(draft.room_nos || '')
  recordForm.value.repair_type = String(draft.repair_type || '其他')
  recordForm.value.description = String(draft.description || '')
  recordForm.value.report_by = String(draft.report_by || '')
  recordForm.value.report_date = String(draft.report_date || new Date().toISOString().split('T')[0])
  recordForm.value.status = String(draft.status || '待处理')
  recordForm.value.repair_date = String(draft.repair_date || '')
  recordForm.value.amount = Number(draft.amount || 0)
  recordForm.value.repair_person = String(draft.repair_person || '')
  recordForm.value.payment_person = String(draft.payment_person || '')
  recordForm.value.remarks = String(draft.remarks || '')

  const copiedAiImages = aiImages
    .filter(item => item?.file)
    .slice(0, MAX_REPAIR_IMAGES)
    .map(item => ({
      file: item.file,
      url: URL.createObjectURL(item.file)
    }))

  repairImageFilesBefore.value = copiedAiImages
  recordForm.value.repair_images_before = copiedAiImages.map(item => item.url)

  if (recordForm.value.building && recordForm.value.scope_type === '单个房间') {
    filteredRooms.value = allRooms.value.filter(room => room.building === recordForm.value.building)
  }
  nextTick(() => {
    recordFormRef.value?.clearValidate?.()
  })
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
    const response = await repairRecordsApi.createAiDraft(formData)
    applyAiDraftToForm(response?.data?.draft || {}, aiDialog.images)
    aiDialog.visible = false
    ElMessage.success('AI 草稿已填入维修表单，请确认后保存')
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || error?.message || 'AI 输入失败')
  } finally {
    aiDialog.loading = false
  }
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
    `确定要删除选中的 ${multipleSelection.value.length} 条维修记录吗？`,
    '删除确认',
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
    ElMessage.success(`删除完成：成功 ${successCount} 条`)
  } else {
    ElMessage.error(`删除完成：成功 ${successCount} 条，失败 ${failures.length} 条`)
    console.warn('删除失败详情:\n' + failures.join('\n'))
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
        formData.building = serializeBuildingModel(formData.building, formData.scope_type)
        formData.amount = formData.amount === '' ? null : formData.amount
        formData.repair_cost = formData.amount
        formData.scope_type = formData.scope_type || '单个房间'
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
  syncDisplayMode()
  window.addEventListener(DISPLAY_MODE_EVENT, syncDisplayMode)
  await loadRooms()
  await loadInventoryOptions()
  await loadTenantNameOptions()
  await loadRecords()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener(DISPLAY_MODE_EVENT, syncDisplayMode)
  window.removeEventListener('resize', handleResize)
  revokeAiImageUrls()
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
    '维修范围': r.scope_type || '单个房间',
    '楼栋': r.building,
    '房间号': r.room_no,
    '多个房间号': r.room_nos,
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
    const headerCells = ['ID','维修范围','楼栋','房间号','多个房间号','维修类型','问题描述','报修日期','报修人','状态','维修日期','金额','维修人员','备注'].map(text =>
      new TableCell({ children: [new Paragraph({ children: [new TextRun(String(text))] })] })
    )
    const tableRows = [
      new TableRow({ children: headerCells }),
      ...rows.map(r => new TableRow({
        children: [
          new TableCell({ children: [new Paragraph(String(r.ID))] }),
          new TableCell({ children: [new Paragraph(String(r['维修范围']))] }),
          new TableCell({ children: [new Paragraph(String(r['楼栋']))] }),
          new TableCell({ children: [new Paragraph(String(r['房间号']))] }),
          new TableCell({ children: [new Paragraph(String(r['多个房间号']))] }),
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
          scope_type: row['维修范围类型'] || row['维修范围'] || '单个房间',
          building: row['楼栋'] || '',
          room_no: row['房间号'],
          room_nos: row['多个房间号'] || '',
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
          }
        }
        await repairRecordsApi.addRepairRecord(payload)
        successCount++
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
  background: var(--card-bg);
  border: 1px solid var(--surface-border);
  border-radius: 18px;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
}

.repair-records-container--mobile {
  padding: 16px;
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

.repair-mobile-overview {
  display: flex;
  gap: 10px;
  width: 100%;
}

.repair-mobile-stat {
  flex: 1;
  padding: 12px 14px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.12), rgba(20, 184, 166, 0.12));
  border: 1px solid rgba(37, 99, 235, 0.12);
}

.repair-mobile-stat strong {
  display: block;
  font-size: 18px;
  color: var(--text-main);
}

.repair-mobile-stat span {
  display: block;
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: 12px;
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

.repair-image-uploader {
  width: 100%;
  min-width: 0;
}

.repair-image-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
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

.form-image-dropzone {
  width: 100%;
  margin-bottom: 10px;
  padding: 14px 16px;
  border: 1px dashed var(--surface-border);
  border-radius: 12px;
  background: var(--surface-muted);
  transition: border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease;
}

.form-image-dropzone--active {
  border-color: var(--el-color-primary);
  background: rgba(37, 99, 235, 0.08);
  box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.12);
}

.form-image-dropzone__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
}

.form-image-dropzone__hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-secondary);
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

.repair-mobile-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.repair-mobile-card {
  padding: 14px;
  border-radius: 16px;
  border: 1px solid var(--surface-border);
  background: var(--card-bg);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
}

.repair-mobile-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.repair-mobile-card__title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-main);
}

.repair-mobile-card__meta,
.repair-mobile-card__desc {
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: 13px;
}

.repair-mobile-card__desc {
  line-height: 1.6;
}

.repair-mobile-card__grid {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.repair-mobile-card__grid > div {
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--surface-muted);
}

.repair-mobile-card__grid strong,
.repair-mobile-card__grid span {
  display: block;
}

.repair-mobile-card__grid strong {
  font-size: 14px;
  color: var(--text-main);
}

.repair-mobile-card__grid span {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}

.repair-mobile-card__actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.repair-mobile-card__actions :deep(.el-button) {
  flex: 1;
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
  .page-header {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }

  .search-input {
    width: 100%;
  }

  .header-operations {
    width: 100%;
  }

  .header-operations :deep(.el-input),
  .header-operations :deep(.el-button) {
    flex: 1 1 calc(50% - 5px);
  }

  .repair-mobile-card__grid {
    grid-template-columns: 1fr;
  }

  .repair-image-field :deep(.el-form-item__content) {
    min-width: 0;
  }

  .repair-image-actions {
    display: grid;
    grid-template-columns: 1fr;
    gap: 10px;
    width: 100%;
  }

  .repair-image-actions :deep(.el-upload),
  .repair-image-actions :deep(.el-button) {
    width: 100%;
    margin-left: 0;
  }

  .repair-image-preview-wrap {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
    width: 100%;
  }

  .repair-image-box {
    min-width: 0;
  }

  .repair-image-box :deep(.el-button) {
    width: 100%;
  }

  .repair-image-thumb {
    width: 100%;
    aspect-ratio: 1 / 1;
    height: auto;
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
