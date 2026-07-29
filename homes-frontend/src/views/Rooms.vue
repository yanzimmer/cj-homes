<template>
  <div>
  <div class="rooms-container" :class="{ 'rooms-container--mobile': mobileMode }">
    <div class="page-header">
      <div class="page-header__title">
        <h2>房间详情</h2>
        <div v-if="mobileMode" class="mobile-room-stats">
          <div class="mobile-room-stat">
            <strong>{{ rooms.length }}</strong>
            <span>总房间</span>
          </div>
          <div class="mobile-room-stat">
            <strong>{{ occupiedRoomCount }}</strong>
            <span>已入住</span>
          </div>
          <div class="mobile-room-stat">
            <strong>{{ vacantRoomCount }}</strong>
            <span>空闲</span>
          </div>
        </div>
      </div>
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
        <el-radio-group v-if="!mobileMode" v-model="currentView" size="default" class="view-switch-group">
          <el-radio-button label="table">
            <el-icon><List /></el-icon> 列表
          </el-radio-button>
          <el-radio-button label="floor">
            <el-icon><Grid /></el-icon> 楼层
          </el-radio-button>
        </el-radio-group>

        <el-button class="toolbar-btn" type="primary" @click="openAddDialog">新增</el-button>
        <el-button
          v-if="mobileMode"
          class="toolbar-btn"
          :type="currentView === 'table' ? 'primary' : 'default'"
          :plain="currentView !== 'table'"
          @click="currentView = 'table'"
        >列表</el-button>
        <el-button
          v-if="mobileMode"
          class="toolbar-btn"
          :type="currentView === 'floor' ? 'primary' : 'default'"
          :plain="currentView !== 'floor'"
          @click="currentView = 'floor'"
        >楼层</el-button>
        <el-button v-if="!mobileMode" class="toolbar-btn" type="danger" :disabled="selectedRooms.length === 0" :loading="batchDeleting" @click="handleBatchDelete">删除</el-button>
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
      </div>

      <div v-if="mobileMode" class="mobile-secondary-controls">
        <el-select v-model="statusFilter" class="mobile-filter-select" placeholder="状态">
          <el-option label="全部状态" value="all" />
          <el-option label="空闲" value="空闲" />
          <el-option label="已入住" value="已入住" />
        </el-select>

        <el-select v-model="roomTypeFilter" class="mobile-filter-select" placeholder="类型">
          <el-option label="全部类型" value="all" />
          <el-option
            v-for="type in roomTypeOptions"
            :key="`mobile-type-${type}`"
            :label="type"
            :value="type"
          />
        </el-select>
      </div>
    </div>

    <!-- 列表视图 -->
    <div v-if="currentView === 'table'">
      <div v-if="mobileMode" class="mobile-room-list" v-loading="loading">
        <div v-if="visibleRooms.length === 0" class="empty-state">
          <el-empty description="暂无符合条件的房间" />
        </div>

        <div v-else class="mobile-room-cards">
          <article
            v-for="room in visibleRooms"
            :key="room.id"
            class="mobile-room-card"
            :class="{
              'mobile-room-card--occupied': room.status === '已入住',
              'mobile-room-card--vacant': room.status === '空闲'
            }"
          >
            <div class="mobile-room-card__top">
              <div>
                <div class="mobile-room-card__room-no">{{ room.room_display || room.room_no }}</div>
                <div class="mobile-room-card__meta">{{ room.building }}栋 · {{ room.floor || '-' }}楼 · {{ room.room_type }}</div>
              </div>
              <el-tag :type="room.status === '已入住' ? 'danger' : 'success'" effect="dark">
                {{ room.status }}
              </el-tag>
            </div>

            <div class="mobile-room-card__facts">
              <div class="mobile-room-fact">
                <span>价格</span>
                <strong>{{ formatRoomPrice(room) }}</strong>
              </div>
              <div class="mobile-room-fact">
                <span>押金</span>
                <strong>{{ Number(room.deposit || 0) }} 元</strong>
              </div>
              <div class="mobile-room-fact">
                <span>租户</span>
                <strong>{{ room.tenant_count || 0 }} 人</strong>
              </div>
              <div class="mobile-room-fact">
                <span>待收租金</span>
                <strong>¥{{ formatOutstandingAmount(room) }}</strong>
              </div>
              <div class="mobile-room-fact">
                <span>历史交租</span>
                <strong>{{ getPaidHistoryCount(room) }} 次</strong>
              </div>
            </div>

            <div v-if="room.features?.length" class="mobile-room-card__features">
              <el-tag v-for="item in room.features" :key="item" size="small" effect="plain">{{ item }}</el-tag>
            </div>

            <p v-if="room.description" class="mobile-room-card__desc">{{ room.description }}</p>

            <div class="mobile-room-card__actions">
              <el-button
                size="small"
                @click="showRoomDetails(room)"
                :disabled="room.status === '空闲' || room.tenant_count === 0"
              >
                详情
              </el-button>
              <el-button size="small" type="primary" plain @click="openEditDialog(room)">编辑</el-button>
              <el-button size="small" type="primary" @click="openSelfCheckinDialog(room)">入住登记</el-button>
              <el-button size="small" type="success" plain @click="openRentCollectionDialog(room)">缴租码</el-button>
              <el-button
                v-if="room.status === '已入住'"
                size="small"
                type="warning"
                @click="handleCheckout(room)"
              >
                退租
              </el-button>
              <el-button
                v-else
                size="small"
                type="danger"
                @click="handleDelete(room)"
              >
                删除
              </el-button>
            </div>
          </article>
        </div>
      </div>

      <div v-else class="table-panel">
      <el-table 
        class="rooms-table" 
        ref="roomsTableRef"
        :data="visibleRooms" 
        row-key="id"
        v-loading="loading" 
        border 
        style="width: 100%"
        fit
        :max-height="tableMaxHeight"
        @sort-change="handleSortChange"
        @selection-change="handleSelectionChange"
        @select="handleRowSelect"
      >
        <el-table-column type="selection" width="42" :selectable="rowSelectable"></el-table-column>
        <el-table-column prop="__sequence" label="序号" width="66" align="center" sortable="custom" show-overflow-tooltip>
          <template #default="{ $index }">
            {{ roomRowStart + $index + 1 }}
          </template>
        </el-table-column>
        <el-table-column prop="building" label="楼栋" width="70" sortable="custom" show-overflow-tooltip></el-table-column>

        <el-table-column prop="room_no" label="房间号" width="92" sortable="custom" show-overflow-tooltip></el-table-column>
        <el-table-column prop="room_type" label="类型" width="86" sortable="custom" show-overflow-tooltip>
          <template #header>
            <div style="display: flex; align-items: center;">
              <span>类型</span>
              <el-dropdown trigger="click" @command="handleTypeFilter">
                <el-button style="margin-left: 5px; padding: 2px 5px;" size="small">
                  <el-icon><Filter /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="all">全部</el-dropdown-item>
                    <el-dropdown-item
                      v-for="type in roomTypeOptions"
                      :key="`filter-${type}`"
                      :command="type"
                    >
                      {{ type }}
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="price" label="价格" width="98" sortable="custom" show-overflow-tooltip>
          <template #default="scope">
            {{ formatRoomPrice(scope.row) }}
          </template>
        </el-table-column>
        <el-table-column prop="deposit" label="押金" width="88" sortable="custom" show-overflow-tooltip>
          <template #default="scope">
            {{ scope.row.deposit }} 元
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="88" sortable="custom" show-overflow-tooltip>
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
        <el-table-column prop="tenant_count" label="租户数" width="76" sortable="custom" show-overflow-tooltip></el-table-column>
        <el-table-column label="待收租金" width="110" sortable="custom" show-overflow-tooltip>
          <template #default="scope">
            ¥{{ formatOutstandingAmount(scope.row) }}
          </template>
        </el-table-column>
        <el-table-column label="历史交租次数" width="108" sortable="custom" show-overflow-tooltip>
          <template #default="scope">
            {{ getPaidHistoryCount(scope.row) }}
          </template>
        </el-table-column>
        <el-table-column label="房间设施" min-width="120" show-overflow-tooltip>
          <template #default="scope">
            <div class="room-feature-tags">
              <el-tag v-for="item in (scope.row.features || [])" :key="item" size="small" effect="plain">{{ item }}</el-tag>
              <span v-if="!scope.row.features || scope.row.features.length === 0">-</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="120" show-overflow-tooltip></el-table-column>
        <el-table-column label="操作" min-width="380" fixed="right">
          <template #default="scope">
            <div class="room-actions-inline">
              <el-button
                size="small"
                @click="showRoomDetails(scope.row)"
                :disabled="scope.row.status === '空闲' || scope.row.tenant_count === 0"
              >
                详情
              </el-button>
              <el-button size="small" type="primary" @click="openEditDialog(scope.row)">编辑</el-button>
              <el-button size="small" type="primary" plain @click="openSelfCheckinDialog(scope.row)">入住登记</el-button>
              <el-button size="small" type="success" plain @click="openRentCollectionDialog(scope.row)">缴租码</el-button>
              <el-dropdown trigger="click">
                <el-button size="small">
                  更多
                  <el-icon style="margin-left: 4px"><MoreFilled /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item
                      :disabled="scope.row.status === '空闲' || scope.row.tenant_count === 0"
                      @click="handleCheckout(scope.row)"
                    >
                      退租
                    </el-dropdown-item>
                    <el-dropdown-item
                      :disabled="scope.row.status === '已入住'"
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
      <div class="pagination-container" :class="{ 'pagination-container--mobile': mobileMode }">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :layout="paginationLayout"
          :small="mobileMode"
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
                  <span class="value">{{ formatRoomPrice(room) }}</span>
                </div>
                <div class="info-row">
                  <span class="label">待收:</span>
                  <span class="value">¥{{ formatOutstandingAmount(room) }}</span>
                </div>
                <div class="info-row" v-if="room.tenant_count > 0">
                  <span class="label">租户:</span>
                  <span class="value">{{ room.tenant_count }}人</span>
                </div>
                <div class="info-row">
                  <span class="label">历史交租:</span>
                  <span class="value">{{ getPaidHistoryCount(room) }}次</span>
                </div>
              </div>
              <div class="room-card-actions" @click.stop>
                <el-button circle size="small" :icon="Edit" @click="openEditDialog(room)" title="编辑" />
                <el-button circle size="small" type="success" @click="openRentCollectionDialog(room)" title="缴租码">租</el-button>
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

    <!-- 添加/编辑房间抽屉 -->
    <el-drawer
      :title="dialogTitle"
      v-model="dialogVisible"
      direction="rtl"
      :size="mobileMode ? '100%' : '620px'"
    >
      <input
        ref="roomWaterQrInputRef"
        type="file"
        accept="image/*"
        multiple
        class="hidden-file-input"
        @change="handleRoomMeterQrFileChange('water', $event)"
      />
      <input
        ref="roomElectricityQrInputRef"
        type="file"
        accept="image/*"
        class="hidden-file-input"
        @change="handleRoomMeterQrFileChange('electricity', $event)"
      />
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
            <el-option
              v-for="type in roomTypeOptions"
              :key="`form-${type}`"
              :label="type"
              :value="type"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="价格" prop="price">
          <div class="price-input-row">
            <el-input-number v-model="roomForm.price" :min="0" :precision="2" :step="100"></el-input-number>
            <el-select v-model="roomForm.price_unit" placeholder="周期" class="price-unit-select">
              <el-option
                v-for="option in roomPriceUnitOptions"
                :key="option"
                :label="option"
                :value="option"
              />
            </el-select>
          </div>
        </el-form-item>
        <el-form-item label="押金" prop="deposit">
          <el-input-number v-model="roomForm.deposit" :min="0" :precision="2" :step="100"></el-input-number>
        </el-form-item>
        <el-form-item label="房间设施">
          <el-checkbox-group v-model="roomForm.features">
            <el-checkbox v-for="item in roomFeatureOptions" :key="item" :label="item">{{ item }}</el-checkbox>
          </el-checkbox-group>
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
        <el-form-item label="水二维码">
          <div class="room-meter-form-block">
            <div
              class="form-image-dropzone"
              :class="{ 'form-image-dropzone--active': roomMeterDragActive.water }"
              @dragenter.prevent="roomMeterDragActive.water = true"
              @dragover.prevent="roomMeterDragActive.water = true"
              @dragleave.prevent="roomMeterDragActive.water = false"
              @drop.prevent="handleRoomMeterQrDrop('water', $event)"
              @paste="handleRoomMeterQrPaste('water', $event)"
              tabindex="0"
            >
              <div class="form-image-dropzone__title">拖拽图片到这里</div>
              <div class="form-image-dropzone__hint">也支持直接粘贴截图</div>
            </div>
            <div class="room-meter-form-actions">
              <el-button type="primary" plain @click="openRoomMeterQrPicker('water')">选择图片</el-button>
              <span class="room-meter-form-tip">支持一次上传多张水表图片，适合套间两个水表</span>
            </div>
            <div class="room-meter-form-tip">当前已选 {{ roomForm.water_meter_imgs.length }} 张</div>
            <div v-if="roomForm.water_meter_imgs.length > 0" class="room-meter-form-preview">
              <el-image
                v-for="(img, index) in roomForm.water_meter_imgs"
                :key="`water-${img}-${index}`"
                class="room-meter-form-image"
                :src="toStaticUrl(img)"
                :preview-src-list="roomForm.water_meter_imgs.map((item) => toStaticUrl(item))"
                fit="cover"
                preview-teleported
              />
            </div>
          </div>
        </el-form-item>
        <el-form-item label="电二维码">
          <div class="room-meter-form-block">
            <div
              class="form-image-dropzone"
              :class="{ 'form-image-dropzone--active': roomMeterDragActive.electricity }"
              @dragenter.prevent="roomMeterDragActive.electricity = true"
              @dragover.prevent="roomMeterDragActive.electricity = true"
              @dragleave.prevent="roomMeterDragActive.electricity = false"
              @drop.prevent="handleRoomMeterQrDrop('electricity', $event)"
              @paste="handleRoomMeterQrPaste('electricity', $event)"
              tabindex="0"
            >
              <div class="form-image-dropzone__title">拖拽图片到这里</div>
              <div class="form-image-dropzone__hint">也支持直接粘贴截图</div>
            </div>
            <div class="room-meter-form-actions">
              <el-button type="primary" plain @click="openRoomMeterQrPicker('electricity')">选择图片</el-button>
              <span class="room-meter-form-tip">支持上传并预览电二维码图片</span>
            </div>
            <div v-if="roomForm.electricity_meter_img" class="room-meter-form-preview">
              <el-image
                class="room-meter-form-image"
                :src="toStaticUrl(roomForm.electricity_meter_img)"
                :preview-src-list="[toStaticUrl(roomForm.electricity_meter_img)]"
                fit="cover"
                preview-teleported
              />
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSubmit" :loading="submitting">确定</el-button>
        </span>
      </template>
    </el-drawer>

    <!-- 退租确认对话框 -->
    <el-dialog title="确认退租" v-model="checkoutDialogVisible" :width="mobileMode ? '92%' : '400px'">
      <div class="checkout-confirm">
        <p>确定要将房间 <strong>{{ checkoutRoom.room_display || checkoutRoom.room_no }}</strong> 退租吗？</p>
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
    <el-dialog
      title="房间详情"
      v-model="detailsDialogVisible"
      :width="mobileMode ? '96%' : '700px'"
      class="room-details-dialog"
    >
      <div v-loading="detailsLoading">
        <div class="room-info">
          <h3>房间信息</h3>
          <div v-if="mobileMode" class="room-details-mobile-section">
            <article class="room-details-mobile-card">
              <div class="room-details-mobile-grid">
                <div class="room-details-mobile-row">
                  <span class="room-details-mobile-row__label">房间号</span>
                  <strong class="room-details-mobile-row__value">{{ currentRoom.room_display || currentRoom.room_no || '-' }}</strong>
                </div>
                <div class="room-details-mobile-row">
                  <span class="room-details-mobile-row__label">楼栋</span>
                  <strong class="room-details-mobile-row__value">{{ currentRoom.building || '-' }}</strong>
                </div>
                <div class="room-details-mobile-row">
                  <span class="room-details-mobile-row__label">楼层</span>
                  <strong class="room-details-mobile-row__value">{{ currentRoom.floor || '-' }}</strong>
                </div>
                <div class="room-details-mobile-row">
                  <span class="room-details-mobile-row__label">房间类型</span>
                  <strong class="room-details-mobile-row__value">{{ currentRoom.room_type || '-' }}</strong>
                </div>
                <div class="room-details-mobile-row">
                  <span class="room-details-mobile-row__label">价格</span>
                  <strong class="room-details-mobile-row__value">{{ formatRoomPrice(currentRoom) }}</strong>
                </div>
                <div class="room-details-mobile-row">
                  <span class="room-details-mobile-row__label">押金</span>
                  <strong class="room-details-mobile-row__value">{{ currentRoom.deposit || 0 }} 元</strong>
                </div>
                <div class="room-details-mobile-row">
                  <span class="room-details-mobile-row__label">状态</span>
                  <strong class="room-details-mobile-row__value">
                    <el-tag :type="currentRoom.status === '已入住' ? 'danger' : 'success'">
                      {{ currentRoom.status || '-' }}
                    </el-tag>
                  </strong>
                </div>
                <div class="room-details-mobile-row">
                  <span class="room-details-mobile-row__label">租户数量</span>
                  <strong class="room-details-mobile-row__value">{{ currentRoom.tenant_count ?? 0 }}</strong>
                </div>
              </div>
            </article>

            <article class="room-details-mobile-card">
              <div class="room-details-mobile-subtitle">水二维码</div>
              <div v-if="getWaterMeterImages(currentRoom).length > 0" class="room-details-mobile-qr-list">
                <el-image
                  v-for="(img, index) in getWaterMeterImages(currentRoom)"
                  :key="`detail-water-mobile-${img}-${index}`"
                  class="room-details-mobile-qr-image"
                  :src="toStaticUrl(img)"
                  :preview-src-list="getWaterMeterImages(currentRoom).map((item) => toStaticUrl(item))"
                  fit="cover"
                  preview-teleported
                />
              </div>
              <div v-else class="room-details-mobile-empty">未上传</div>
            </article>

            <article class="room-details-mobile-card">
              <div class="room-details-mobile-subtitle">电二维码</div>
              <div v-if="currentRoom.electricity_meter_img" class="room-details-mobile-qr-list">
                <el-image
                  class="room-details-mobile-qr-image"
                  :src="toStaticUrl(currentRoom.electricity_meter_img)"
                  :preview-src-list="[toStaticUrl(currentRoom.electricity_meter_img)]"
                  fit="cover"
                  preview-teleported
                />
              </div>
              <div v-else class="room-details-mobile-empty">未上传</div>
            </article>

            <article class="room-details-mobile-card">
              <div class="room-details-mobile-subtitle">房间设施</div>
              <div class="room-feature-tags">
                <el-tag v-for="item in (currentRoom.features || [])" :key="item" size="small" effect="plain">{{ item }}</el-tag>
                <span v-if="!currentRoom.features || currentRoom.features.length === 0">-</span>
              </div>
            </article>
          </div>
          <el-descriptions v-else :column="2" border class="room-details-descriptions">
            <el-descriptions-item label="房间号">{{ currentRoom.room_no }}</el-descriptions-item>
            <el-descriptions-item label="楼栋">{{ currentRoom.building }}</el-descriptions-item>
            <el-descriptions-item label="楼层">{{ currentRoom.floor }}</el-descriptions-item>
            <el-descriptions-item label="房间类型">{{ currentRoom.room_type }}</el-descriptions-item>
            <el-descriptions-item label="价格">{{ formatRoomPrice(currentRoom) }}</el-descriptions-item>
            <el-descriptions-item label="押金">{{ currentRoom.deposit }} 元</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="currentRoom.status === '已入住' ? 'danger' : 'success'">
                {{ currentRoom.status }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="租户数量">{{ currentRoom.tenant_count }}</el-descriptions-item>
            <el-descriptions-item label="水二维码">
              <div v-if="getWaterMeterImages(currentRoom).length > 0" class="detail-meter-qr-list">
                <el-image
                  v-for="(img, index) in getWaterMeterImages(currentRoom)"
                  :key="`detail-water-${img}-${index}`"
                  class="detail-meter-qr-image"
                  :src="toStaticUrl(img)"
                  :preview-src-list="getWaterMeterImages(currentRoom).map((item) => toStaticUrl(item))"
                  fit="cover"
                  preview-teleported
                />
              </div>
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="电二维码">
              <div v-if="currentRoom.electricity_meter_img" class="detail-meter-qr-list">
                <el-image
                  class="detail-meter-qr-image"
                  :src="toStaticUrl(currentRoom.electricity_meter_img)"
                  :preview-src-list="[toStaticUrl(currentRoom.electricity_meter_img)]"
                  fit="cover"
                  preview-teleported
                />
              </div>
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="房间设施" :span="2">
              <div class="room-feature-tags">
                <el-tag v-for="item in (currentRoom.features || [])" :key="item" size="small" effect="plain">{{ item }}</el-tag>
                <span v-if="!currentRoom.features || currentRoom.features.length === 0">-</span>
              </div>
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="tenant-list" v-if="roomTenants.length > 0">
          <h3>入住人员</h3>
          <div v-if="mobileMode" class="room-tenant-mobile-list">
            <article v-for="tenant in roomTenants" :key="tenant.id_card || `${tenant.name}-${tenant.phone}`" class="room-tenant-mobile-card">
              <div class="room-tenant-mobile-card__header">
                <strong>{{ tenant.name || '未命名租户' }}</strong>
                <el-tag size="small" effect="plain">{{ tenant.gender || '未填' }}</el-tag>
              </div>
              <div class="room-tenant-mobile-details">
                <div class="room-tenant-mobile-row">
                  <span class="room-tenant-mobile-row__label">电话</span>
                  <strong class="room-tenant-mobile-row__value">{{ tenant.phone || '-' }}</strong>
                </div>
                <div class="room-tenant-mobile-row">
                  <span class="room-tenant-mobile-row__label">身份证号</span>
                  <strong class="room-tenant-mobile-row__value">{{ tenant.id_card || '-' }}</strong>
                </div>
                <div class="room-tenant-mobile-row">
                  <span class="room-tenant-mobile-row__label">入住日期</span>
                  <strong class="room-tenant-mobile-row__value">{{ tenant.check_in_date || '-' }}</strong>
                </div>
                <div class="room-tenant-mobile-row">
                  <span class="room-tenant-mobile-row__label">到期日期</span>
                  <strong class="room-tenant-mobile-row__value">{{ tenant.check_out_date || '-' }}</strong>
                </div>
              </div>
            </article>
          </div>
          <el-table v-else :data="roomTenants" border style="width: 100%" table-layout="auto" class="room-details-tenant-table">
            <el-table-column prop="name" label="姓名" min-width="90"></el-table-column>
            <el-table-column prop="gender" label="性别" min-width="70"></el-table-column>
            <el-table-column prop="phone" label="电话" min-width="120"></el-table-column>
            <el-table-column prop="id_card" label="身份证号" min-width="180"></el-table-column>
            <el-table-column prop="check_in_date" label="入住日期" min-width="110"></el-table-column>
            <el-table-column prop="check_out_date" label="到期日期" min-width="110"></el-table-column>
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


    <el-dialog
      title="入住登记"
      v-model="selfCheckinDialogVisible"
      :width="mobileMode ? '96%' : '820px'"
      class="self-checkin-dialog"
    >
      <div class="self-checkin-panel">
        <div class="self-checkin-toolbar">
          <div class="self-checkin-room">
            当前房间：{{ selfCheckinRoom.building }}栋 {{ selfCheckinRoom.room_no }}
          </div>
          <div class="self-checkin-toolbar-actions">
            <el-button :loading="refreshingSelfCheckin" @click="refreshSelfCheckinData">刷新</el-button>
          </div>
        </div>
        <div v-if="selfCheckinLinks.length > 0" class="self-checkin-tip">
          当前房间固定保留 1 个入住登记链接；如需换码，可以直接重建，系统会立刻补一条新的固定链接，已提交记录不会删除。
        </div>

        <div v-if="selfCheckinLinks.length > 0" class="self-checkin-links">
          <div v-for="item in selfCheckinLinks" :key="item.id" class="self-checkin-link-card">
            <div class="self-checkin-link-meta">
              <div>创建时间：{{ item.created_at }}</div>
              <div>状态：{{ item.status }}</div>
            </div>
            <div v-if="item.qrCodeDataUrl" class="self-checkin-link-qr">
              <img :src="item.qrCodeDataUrl" alt="入住二维码" class="self-checkin-qr-image" />
            </div>
            <div class="self-checkin-link-url">{{ buildSelfCheckinUrl(item.token) }}</div>
            <div class="self-checkin-link-actions">
              <el-button size="small" @click="copySelfCheckinUrl(item.token)">复制链接</el-button>
              <el-button size="small" type="primary" plain @click="openSelfCheckinUrl(item.token)">打开链接</el-button>
              <el-button
                v-if="item.status === 'active'"
                size="small"
                type="danger"
                @click="disableSelfCheckinLink(item)"
              >
                停用
              </el-button>
              <el-button
                v-else
                size="small"
                type="success"
                @click="enableSelfCheckinLink(item)"
              >
                启用
              </el-button>
              <el-button
                size="small"
                type="warning"
                plain
                @click="rebuildSelfCheckinLink(item)"
              >
                重建链接
              </el-button>
            </div>
          </div>
        </div>

        <el-divider />

        <h3>待确认提交记录</h3>
        <div v-if="mobileMode" class="self-checkin-mobile-submission-list">
          <el-empty
            v-if="selfCheckinSubmissions.length === 0"
            description="暂无待确认提交记录"
          />
          <article
            v-for="row in selfCheckinSubmissions"
            v-else
            :key="row.id"
            class="self-checkin-mobile-submission-card"
          >
            <div class="self-checkin-mobile-submission-top">
              <strong>{{ row.name || '未填写姓名' }}</strong>
              <div class="self-checkin-mobile-submission-tags">
                <el-tag :type="getSelfCheckinSubmissionStatusType(row.status)" effect="light" round>
                  {{ getSelfCheckinSubmissionStatusLabel(row.status) }}
                </el-tag>
              </div>
            </div>
            <div class="self-checkin-mobile-submission-grid">
              <div class="self-checkin-mobile-submission-item">
                <span>身份证号</span>
                <strong>{{ row.id_card || '-' }}</strong>
              </div>
              <div class="self-checkin-mobile-submission-item">
                <span>联系电话</span>
                <strong>{{ row.phone || '-' }}</strong>
              </div>
              <div class="self-checkin-mobile-submission-item">
                <span>入住日期</span>
                <strong>{{ row.check_in_date || '-' }}</strong>
              </div>
              <div class="self-checkin-mobile-submission-item">
                <span>退房日期</span>
                <strong>{{ row.check_out_date || '-' }}</strong>
              </div>
              <div class="self-checkin-mobile-submission-item">
                <span>提交时间</span>
                <strong>{{ row.submitted_at || '-' }}</strong>
              </div>
              <div
                v-if="row.reject_reason"
                class="self-checkin-mobile-submission-item self-checkin-mobile-submission-item--full"
              >
                <span>驳回原因</span>
                <strong>{{ row.reject_reason }}</strong>
              </div>
            </div>
            <div class="self-checkin-mobile-submission-actions">
              <el-button size="small" @click="openSubmissionDetail(row)">详情</el-button>
              <el-button
                size="small"
                type="primary"
                :disabled="row.status !== 'pending'"
                @click="openApproveSelfCheckinDialog(row)"
              >
                确认
              </el-button>
              <el-button
                size="small"
                type="danger"
                :disabled="row.status !== 'pending'"
                @click="rejectSelfCheckinSubmission(row)"
              >
                驳回
              </el-button>
              <el-button
                size="small"
                type="danger"
                plain
                @click="deleteSelfCheckinSubmission(row)"
              >
                删除
              </el-button>
            </div>
          </article>
        </div>
        <el-table v-else :data="selfCheckinSubmissions" border style="width: 100%">
          <el-table-column prop="name" label="姓名" min-width="100" />
          <el-table-column prop="id_card" label="身份证号" min-width="170" />
          <el-table-column prop="phone" label="联系电话" min-width="120" />
          <el-table-column prop="check_in_date" label="入住日期" width="120" />
          <el-table-column prop="check_out_date" label="退房日期" width="120" />
          <el-table-column prop="status" label="状态" width="100" />
          <el-table-column prop="submitted_at" label="提交时间" min-width="160" />
          <el-table-column prop="reject_reason" label="驳回原因" min-width="180" show-overflow-tooltip />
          <el-table-column label="操作" width="260" fixed="right">
            <template #default="{ row }">
              <div class="self-checkin-submission-actions">
                <el-button size="small" @click="openSubmissionDetail(row)">详情</el-button>
                <el-button
                  size="small"
                  type="primary"
                  :disabled="row.status !== 'pending'"
                  @click="openApproveSelfCheckinDialog(row)"
                >
                  确认
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  :disabled="row.status !== 'pending'"
                  @click="rejectSelfCheckinSubmission(row)"
                >
                  驳回
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  plain
                  @click="deleteSelfCheckinSubmission(row)"
                >
                  删除
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>

    <el-drawer v-model="submissionDetailVisible" title="入住提交详情" :size="mobileMode ? '100%' : '520px'">
      <el-descriptions v-if="submissionDetail.id" :column="1" border>
        <el-descriptions-item label="姓名">{{ submissionDetail.name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="性别">{{ submissionDetail.gender || '-' }}</el-descriptions-item>
        <el-descriptions-item label="民族">{{ submissionDetail.nation || '-' }}</el-descriptions-item>
        <el-descriptions-item label="出生日期">{{ submissionDetail.birth_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="身份证号">{{ submissionDetail.id_card || '-' }}</el-descriptions-item>
        <el-descriptions-item label="住址">{{ submissionDetail.address || '-' }}</el-descriptions-item>
        <el-descriptions-item label="联系电话">{{ submissionDetail.phone || '-' }}</el-descriptions-item>
        <el-descriptions-item label="紧急联系人">{{ submissionDetail.emergency_contact_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="紧急电话">{{ submissionDetail.emergency_contact_phone || '-' }}</el-descriptions-item>
        <el-descriptions-item label="入住日期">{{ submissionDetail.check_in_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="退房日期">{{ submissionDetail.check_out_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="提交状态">{{ submissionDetail.status || '-' }}</el-descriptions-item>
        <el-descriptions-item label="提交时间">{{ submissionDetail.submitted_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="驳回原因">{{ submissionDetail.reject_reason || '-' }}</el-descriptions-item>
        <el-descriptions-item label="备注">{{ submissionDetail.remarks || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-drawer>

    <el-dialog v-model="rejectDialogVisible" title="驳回入住提交" :width="mobileMode ? '94%' : '460px'">
      <el-alert
        title="驳回后会保留记录，用户可在记录中看到驳回原因。"
        type="warning"
        :closable="false"
        show-icon
        class="reject-dialog-alert"
      />
      <el-form label-position="top">
        <el-form-item label="驳回原因">
          <el-input
            v-model="rejectReason"
            type="textarea"
            :rows="4"
            maxlength="200"
            show-word-limit
            placeholder="请输入驳回原因"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="closeRejectDialog">取消</el-button>
          <el-button type="danger" :loading="rejectingSubmission" @click="confirmRejectSelfCheckinSubmission">
            确认驳回
          </el-button>
        </span>
      </template>
    </el-dialog>

    <el-dialog v-model="approveDialogVisible" title="确认入住提交" :width="mobileMode ? '94%' : '640px'">
      <el-alert
        :title="selfCheckinRoomTenants.length > 0 ? '当前房间已有租户，可选择新增一条，或补全现有记录。' : '当前房间暂无租户，只能新增租户。'"
        type="info"
        :closable="false"
        show-icon
        class="approve-dialog-alert"
      />
      <el-form label-position="top">
        <el-form-item label="入库方式">
          <el-radio-group v-model="approveForm.mode">
            <el-radio label="create">新增租户</el-radio>
            <el-radio label="merge" :disabled="selfCheckinRoomTenants.length === 0">补全现有租户</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="approveForm.mode === 'merge'" label="选择要补全的租户">
          <el-select
            v-model="approveForm.tenantId"
            placeholder="请选择现有租户"
            filterable
            style="width: 100%"
          >
            <el-option
              v-for="tenant in selfCheckinRoomTenants"
              :key="tenant.id"
              :label="formatSelfCheckinTenantOption(tenant)"
              :value="tenant.id"
            />
          </el-select>
          <div class="self-checkin-approve-tip">
            建议选择之前只录了姓名、电话或身份证不完整的那条租户记录。
          </div>
        </el-form-item>
      </el-form>

      <div v-if="selfCheckinRoomTenants.length > 0" class="self-checkin-existing-tenants">
        <div class="self-checkin-existing-tenants__title">当前房间现有租户</div>
        <el-table :data="selfCheckinRoomTenants" border size="small" max-height="220">
          <el-table-column prop="name" label="姓名" min-width="90" />
          <el-table-column prop="status" label="状态" width="90" />
          <el-table-column prop="phone" label="电话" min-width="120" />
          <el-table-column prop="id_card" label="身份证号" min-width="170" show-overflow-tooltip />
        </el-table>
      </div>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="closeApproveDialog">取消</el-button>
          <el-button type="primary" :loading="approvingSubmission" @click="confirmApproveSelfCheckinSubmission">
            确认入库
          </el-button>
        </span>
      </template>
    </el-dialog>

    <RentCollectionLinkDialog
      v-model="rentCollectionDialogVisible"
      :room="rentCollectionRoom"
    />
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
          <td>{{ formatRoomPrice(r) }}</td>
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
import { useRoute, useRouter } from 'vue-router'
import { roomsApi } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Filter, List, Grid, Edit, Delete, SwitchButton, MoreFilled } from '@element-plus/icons-vue'
import { DISPLAY_MODE_EVENT, getPreferredDisplayMode } from '../utils/displayMode'
import * as XLSX from 'xlsx'
import { jsPDF } from 'jspdf'
import autoTable from 'jspdf-autotable'
import { Document, Packer, Paragraph, Table as DocxTable, TableRow, TableCell, TextRun } from 'docx'
import { saveAs } from 'file-saver'
import html2canvas from 'html2canvas'
import QRCode from 'qrcode'
import RentCollectionLinkDialog from '../components/RentCollectionLinkDialog.vue'

const route = useRoute()
const router = useRouter()

// 视图切换
const currentView = ref('table') // 'table' or 'floor'
const mobileMode = ref(false)

// 数据
const rooms = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('添加房间')
const submitting = ref(false)
const roomFormRef = ref(null)
const isEdit = ref(false)
const roomWaterQrInputRef = ref(null)
const roomElectricityQrInputRef = ref(null)
const pendingRoomMeterFiles = reactive({
  water: [],
  electricity: null
})
const roomMeterDragActive = reactive({
  water: false,
  electricity: false
})
// 选择与删除相关
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
const roomTypeOptions = ['单间', '套间', '门面']
const roomPriceUnitOptions = ['月', '年']
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
const openingSelfCheckinFromRoute = ref(false)
const roomRowStart = computed(() => (currentPage.value - 1) * pageSize.value)
const occupiedRoomCount = computed(() => rooms.value.filter((room) => room.status === '已入住').length)
const vacantRoomCount = computed(() => rooms.value.filter((room) => room.status === '空闲').length)
const paginationLayout = computed(() => (
  mobileMode.value ? 'prev, pager, next' : 'total, sizes, prev, pager, next, jumper'
))
// （重复声明已移除）

// 表格高度自适应：根据窗口动态计算可视高度
const calcTableMaxHeight = () => Math.max(window.innerHeight - 260, 300)
const tableMaxHeight = ref(calcTableMaxHeight())
const handleResize = () => { tableMaxHeight.value = calcTableMaxHeight() }
const syncDisplayMode = () => {
  mobileMode.value = getPreferredDisplayMode() === 'mobile'
}

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
const roomFeatureOptions = ref([])
const selfCheckinDialogVisible = ref(false)
const selfCheckinRoom = ref({})
const selfCheckinLinks = ref([])
const selfCheckinSubmissions = ref([])
const selfCheckinRoomTenants = ref([])
const rentCollectionDialogVisible = ref(false)
const rentCollectionRoom = ref({})
const refreshingSelfCheckin = ref(false)
const roomRentSummaryMap = ref({})
const submissionDetailVisible = ref(false)
const submissionDetail = ref({})
const approveDialogVisible = ref(false)
const approvingSubmission = ref(false)
const approveTargetSubmission = ref(null)
const approveForm = reactive({
  mode: 'create',
  tenantId: null
})
const rejectDialogVisible = ref(false)
const rejectReason = ref('')
const rejectingSubmission = ref(false)
const rejectTargetSubmission = ref(null)

const roomForm = reactive({
  id: null,
  room_no: '',
  building: '',
  floor: '',
  room_type: '',
  price: 0,
  price_unit: '月',
  deposit: 0,
  features: [],
  status: '空闲',
  description: '',
  water_meter_imgs: [],
  water_meter_img: '',
  electricity_meter_img: ''
})

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'
const API_ORIGIN = API_BASE.replace(/\/api\/?$/, '')
const PUBLIC_APP_ORIGIN = (import.meta.env.VITE_PUBLIC_APP_ORIGIN || window.location.origin).replace(/\/$/, '')
const toStaticUrl = (value) => {
  const text = String(value || '').trim()
  if (!text) return ''
  if (/^https?:\/\//i.test(text) || text.startsWith('blob:') || text.startsWith('data:')) return text
  if (text.startsWith('/')) return `${API_ORIGIN}${text}`
  return `${API_ORIGIN}/${text}`
}
const getWaterMeterImages = (room) => {
  if (Array.isArray(room?.water_meter_imgs) && room.water_meter_imgs.length > 0) return room.water_meter_imgs
  const single = String(room?.water_meter_img || '').trim()
  return single ? [single] : []
}

const normalizeRoomPriceUnit = (value) => (value === '年' ? '年' : '月')

const formatRoomPrice = (room) => {
  const price = Number(room?.price || 0)
  const unit = normalizeRoomPriceUnit(room?.price_unit)
  return `${price} 元/${unit}`
}

const getRoomRentSummary = (room) => roomRentSummaryMap.value[String(room?.id || '')] || {}
const formatOutstandingAmount = (room) => formatAmount(getRoomRentSummary(room).outstanding_amount || 0)
const getPaidHistoryCount = (room) => Number(getRoomRentSummary(room).paid_history_count || 0)
const formatAmount = (value) => Number(value || 0).toFixed(2)

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
    const textIncludes = (value) => String(value || '').toLowerCase().includes(query)
    result = result.filter(room => 
      textIncludes(room.room_no) ||
      textIncludes(room.room_display) ||
      textIncludes(room.building) ||
      textIncludes(room.floor) ||
      textIncludes(room.room_type) ||
      textIncludes(room.description)
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
      if (sortBy.value === '__sequence' || sortBy.value === 'price' || sortBy.value === 'tenant_count') {
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
  price_unit: [{ required: true, message: '请选择价格周期', trigger: 'change' }],
  deposit: [{ required: true, message: '请输入押金', trigger: 'blur' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }]
}

// 生命周期
onMounted(() => {
  fetchRooms()
  fetchRoomFeatureOptions()
  syncDisplayMode()
  window.addEventListener(DISPLAY_MODE_EVENT, syncDisplayMode)
})

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener(DISPLAY_MODE_EVENT, syncDisplayMode)
  window.removeEventListener('resize', handleResize)
})

// 方法
const fetchRooms = async () => {
  loading.value = true
  try {
    const response = await roomsApi.listRooms({ fields: 'id,room_no,room_display,building,room_type,price,price_unit,deposit,description,features,status,tenant_count,water_meter_img,electricity_meter_img,has_water_meter_img,has_electricity_meter_img' })
    rooms.value = (response.data.rooms || []).map((room, index) => ({
      ...room,
      price_unit: normalizeRoomPriceUnit(room.price_unit),
      __sequence: index + 1
    }))
    await fetchRoomRentSummaries()
    if (route.query?.selfCheckinRoomId) {
      await nextTick()
      await openSelfCheckinRoomFromRoute()
    }
  } catch (error) {
    ElMessage.error('获取房间列表失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

const fetchRoomRentSummaries = async () => {
  try {
    const ids = rooms.value.map((room) => room.id).filter(Boolean)
    if (!ids.length) {
      roomRentSummaryMap.value = {}
      return
    }
    const response = await roomsApi.getRentCollectionRoomSummaries(ids)
    roomRentSummaryMap.value = response?.data?.summaries || {}
  } catch (error) {
    console.error('获取房间租金汇总失败', error)
  }
}

const clearSelfCheckinRouteQuery = () => {
  const nextQuery = { ...route.query }
  delete nextQuery.selfCheckinRoomId
  delete nextQuery.submissionId
  router.replace({ path: route.path, query: nextQuery }).catch(() => {})
}

const openSelfCheckinRoomFromRoute = async () => {
  if (openingSelfCheckinFromRoute.value) return
  const roomId = Number(route.query?.selfCheckinRoomId || 0)
  if (!roomId) return
  const targetRoom = rooms.value.find((room) => Number(room?.id || 0) === roomId)
  if (!targetRoom) return
  openingSelfCheckinFromRoute.value = true
  try {
    currentView.value = 'table'
    await nextTick()
    await openSelfCheckinDialog(targetRoom)
    clearSelfCheckinRouteQuery()
  } finally {
    openingSelfCheckinFromRoute.value = false
  }
}

const fetchRoomFeatureOptions = async () => {
  try {
    const response = await roomsApi.getFeatureOptions()
    roomFeatureOptions.value = response?.data?.options || []
  } catch (error) {
    console.error('获取房间设施选项失败', error)
  }
}

// 显示房间详情
const showRoomDetails = async (room) => {
  currentRoom.value = { ...room }
  detailsDialogVisible.value = true
  detailsLoading.value = true
  
  try {
    const [roomRes, tenantsRes] = await Promise.all([
      roomsApi.getRoom(room.id),
      roomsApi.getRoomTenants(room.room_display || room.room_no)
    ])
    currentRoom.value = {
      ...currentRoom.value,
      ...(roomRes?.data?.room || {})
    }
    roomTenants.value = tenantsRes?.data?.tenants || []
  } catch (error) {
    ElMessage.error('获取房间租户信息失败：' + error.message)
    roomTenants.value = []
  } finally {
    detailsLoading.value = false
  }
}

const openRoomMeterQrPicker = (type) => {
  if (type === 'water') {
    roomWaterQrInputRef.value?.click()
    return
  }
  roomElectricityQrInputRef.value?.click()
}

const revokeRoomMeterPreview = (value) => {
  const text = String(value || '')
  if (text.startsWith('blob:')) URL.revokeObjectURL(text)
}

const applyRoomMeterQrFiles = (type, inputFiles) => {
  const files = Array.from(inputFiles || [])
  if (!files.length) return
  for (const file of files) {
    if (!String(file.type || '').startsWith('image/')) {
      ElMessage.error('请上传图片文件')
      return
    }
  }
  if (type === 'water') {
    pendingRoomMeterFiles.water = [...pendingRoomMeterFiles.water, ...files]
    roomForm.water_meter_imgs = [
      ...(roomForm.water_meter_imgs || []),
      ...files.map((file) => URL.createObjectURL(file))
    ]
  } else {
    const file = files[0]
    pendingRoomMeterFiles.electricity = file
    revokeRoomMeterPreview(roomForm.electricity_meter_img)
    roomForm.electricity_meter_img = URL.createObjectURL(file)
  }
}

const handleRoomMeterQrFileChange = (type, event) => {
  const files = Array.from(event?.target?.files || [])
  event.target.value = ''
  applyRoomMeterQrFiles(type, files)
}

const handleRoomMeterQrDrop = (type, event) => {
  roomMeterDragActive[type] = false
  const files = Array.from(event?.dataTransfer?.files || [])
  applyRoomMeterQrFiles(type, files)
}

const handleRoomMeterQrPaste = (type, event) => {
  const clipboardItems = Array.from(event?.clipboardData?.items || [])
  const imageItems = clipboardItems.filter((item) => String(item?.type || '').startsWith('image/'))
  if (!imageItems.length) return
  event.preventDefault()
  const files = imageItems.map((item) => item.getAsFile()).filter(Boolean)
  applyRoomMeterQrFiles(type, files)
}

const normalizeSelfCheckinBuildingSegment = (room = {}) => {
  const raw = String(room?.building || '').trim()
  const cleaned = raw.replace(/栋/g, '').trim()
  const letters = cleaned.replace(/[^A-Za-z]/g, '')
  return letters.toLowerCase()
}

const normalizeSelfCheckinRoomSegment = (room = {}) => {
  const primary = String(room?.room_no || '').trim()
  const fallback = String(room?.room_display || '').trim()
  const digits = (primary || fallback).replace(/\D/g, '')
  return digits
}

const buildSelfCheckinUrl = (token, room = selfCheckinRoom.value) => {
  const buildingSegment = normalizeSelfCheckinBuildingSegment(room)
  const roomSegment = normalizeSelfCheckinRoomSegment(room)
  if (buildingSegment && roomSegment) {
    return `${PUBLIC_APP_ORIGIN}/${buildingSegment}/${roomSegment}/${token}`
  }
  return `${PUBLIC_APP_ORIGIN}/check-in/${token}`
}

const getSelfCheckinSubmissionStatusLabel = (status) => {
  if (status === 'approved') return '已确认'
  if (status === 'rejected') return '已驳回'
  if (status === 'pending') return '待确认'
  return status || '未知状态'
}

const getSelfCheckinSubmissionStatusType = (status) => {
  if (status === 'approved') return 'success'
  if (status === 'rejected') return 'danger'
  if (status === 'pending') return 'warning'
  return 'info'
}

const formatSelfCheckinTenantOption = (tenant) => {
  const name = tenant?.name || `租户#${tenant?.id || ''}`
  const status = tenant?.status || '未知状态'
  const phone = tenant?.phone ? `电话 ${tenant.phone}` : '电话未登记'
  const idCard = tenant?.id_card ? `证件 ${tenant.id_card}` : '证件未登记'
  return `${name} · ${status} · ${phone} · ${idCard}`
}

const fetchSelfCheckinData = async (room) => {
  if (!room?.id) return
  const [linksRes, submissionsRes, tenantsRes] = await Promise.all([
    roomsApi.listSelfCheckinLinks(room.id),
    roomsApi.listSelfCheckinSubmissions(room.id),
    roomsApi.getRoomTenants(room.room_display || room.room_no),
  ])
  const links = linksRes?.data?.links || []
  selfCheckinLinks.value = await Promise.all(
    links.map(async (item) => ({
      ...item,
      qrCodeDataUrl: await QRCode.toDataURL(buildSelfCheckinUrl(item.token), { width: 132, margin: 1 }),
    }))
  )
  selfCheckinSubmissions.value = submissionsRes?.data?.submissions || []
  selfCheckinRoomTenants.value = tenantsRes?.data?.tenants || []
}

const refreshSelfCheckinData = async () => {
  if (!selfCheckinRoom.value?.id) return
  refreshingSelfCheckin.value = true
  try {
    await fetchSelfCheckinData(selfCheckinRoom.value)
    ElMessage.success('入住登记记录已刷新')
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '刷新入住登记记录失败')
  } finally {
    refreshingSelfCheckin.value = false
  }
}

const openSelfCheckinDialog = async (room) => {
  selfCheckinRoom.value = room
  selfCheckinDialogVisible.value = true
  try {
    await fetchSelfCheckinData(room)
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '加载入住链接数据失败')
  }
}

const openRentCollectionDialog = (room) => {
  rentCollectionRoom.value = room
  rentCollectionDialogVisible.value = true
}

watch(rooms, async (value) => {
  if (!Array.isArray(value) || value.length === 0) return
  if (!route.query?.selfCheckinRoomId) return
  await openSelfCheckinRoomFromRoute()
})

watch(() => route.query?.selfCheckinRoomId, async (roomId) => {
  if (!roomId) return
  if (!Array.isArray(rooms.value) || rooms.value.length === 0) return
  await openSelfCheckinRoomFromRoute()
})

const copySelfCheckinUrl = async (token) => {
  try {
    await navigator.clipboard.writeText(buildSelfCheckinUrl(token))
    ElMessage.success('入住链接已复制')
  } catch (error) {
    ElMessage.error('复制失败，请手动复制')
  }
}

const openSelfCheckinUrl = (token) => {
  window.open(buildSelfCheckinUrl(token), '_blank', 'noopener,noreferrer')
}

const disableSelfCheckinLink = async (item) => {
  try {
    await ElMessageBox.confirm(
      '停用后该入住链接将无法继续提交，是否确认停用？',
      '停用入住链接',
      {
        confirmButtonText: '确认停用',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    await roomsApi.disableSelfCheckinLink(item.id)
    await fetchSelfCheckinData(selfCheckinRoom.value)
    ElMessage.success('入住链接已停用')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error?.response?.data?.error || error?.message || '停用入住链接失败')
    }
  }
}

const enableSelfCheckinLink = async (item) => {
  try {
    await roomsApi.enableSelfCheckinLink(item.id)
    await fetchSelfCheckinData(selfCheckinRoom.value)
    ElMessage.success('入住链接已启用')
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || error?.message || '启用入住链接失败')
  }
}

const rebuildSelfCheckinLink = async (item) => {
  try {
    await ElMessageBox.confirm(
      '重建后会生成一条新的固定入住登记链接，原链接将失效，但已提交的入住记录会保留，是否继续？',
      '重建入住链接',
      {
        confirmButtonText: '确认重建',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    await roomsApi.deleteSelfCheckinLink(item.id)
    await fetchSelfCheckinData(selfCheckinRoom.value)
    ElMessage.success('入住链接已重建')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error?.response?.data?.error || error?.message || '重建入住链接失败')
    }
  }
}

const openApproveSelfCheckinDialog = (row) => {
  approveTargetSubmission.value = row
  approveForm.mode = 'create'
  approveForm.tenantId = null
  approveDialogVisible.value = true
}

const closeApproveDialog = () => {
  approveDialogVisible.value = false
  approveTargetSubmission.value = null
  approveForm.mode = 'create'
  approveForm.tenantId = null
}

const confirmApproveSelfCheckinSubmission = async () => {
  const row = approveTargetSubmission.value
  if (!row?.id) return
  if (approveForm.mode === 'merge' && !approveForm.tenantId) {
    ElMessage.error('请选择要补全的现有租户')
    return
  }
  approvingSubmission.value = true
  try {
    const response = await roomsApi.approveSelfCheckinSubmission(row.id, {
      mode: approveForm.mode,
      tenant_id: approveForm.mode === 'merge' ? approveForm.tenantId : undefined,
    })
    await fetchSelfCheckinData(selfCheckinRoom.value)
    await fetchRooms()
    ElMessage.success(response?.data?.message || '已确认入租户库')
    closeApproveDialog()
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '确认入库失败')
  } finally {
    approvingSubmission.value = false
  }
}

const openSubmissionDetail = (row) => {
  submissionDetail.value = { ...row }
  submissionDetailVisible.value = true
}

const rejectSelfCheckinSubmission = (row) => {
  rejectTargetSubmission.value = row
  rejectReason.value = row?.reject_reason || ''
  rejectDialogVisible.value = true
}

const closeRejectDialog = () => {
  rejectDialogVisible.value = false
  rejectReason.value = ''
  rejectTargetSubmission.value = null
}

watch(() => approveForm.mode, (mode) => {
  if (mode !== 'merge') {
    approveForm.tenantId = null
  }
})

const confirmRejectSelfCheckinSubmission = async () => {
  const row = rejectTargetSubmission.value
  if (!row?.id) return
  if (!rejectReason.value.trim()) {
    ElMessage.error('请填写驳回原因')
    return
  }
  rejectingSubmission.value = true
  try {
    await roomsApi.rejectSelfCheckinSubmission(row.id, { reject_reason: rejectReason.value.trim() })
    await fetchSelfCheckinData(selfCheckinRoom.value)
    ElMessage.success('入住提交已驳回')
    closeRejectDialog()
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || error?.message || '驳回失败')
  } finally {
    rejectingSubmission.value = false
  }
}

const deleteSelfCheckinSubmission = async (row) => {
  try {
    await ElMessageBox.confirm(
      '确定删除这条入住提交记录吗？',
      '删除提交记录',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    await roomsApi.deleteSelfCheckinSubmission(row.id)
    await fetchSelfCheckinData(selfCheckinRoom.value)
    ElMessage.success('入住提交记录已删除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error?.response?.data?.error || error?.message || '删除提交记录失败')
    }
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
    const response = await roomsApi.checkoutRoom(checkoutRoom.value.room_display || checkoutRoom.value.room_no)
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
  roomForm.price_unit = '月'
  roomForm.deposit = 0
  roomForm.features = []
  roomForm.status = '空闲'
  roomForm.description = ''
  revokeRoomMeterPreview(roomForm.water_meter_img)
  revokeRoomMeterPreview(roomForm.electricity_meter_img)
  ;(roomForm.water_meter_imgs || []).forEach(revokeRoomMeterPreview)
  roomForm.water_meter_imgs = []
  roomForm.water_meter_img = ''
  roomForm.electricity_meter_img = ''
  pendingRoomMeterFiles.water = []
  pendingRoomMeterFiles.electricity = null
  roomMeterDragActive.water = false
  roomMeterDragActive.electricity = false
}

const openAddDialog = () => {
  resetForm()
  isEdit.value = false
  dialogTitle.value = '添加房间'
  dialogVisible.value = true
}

const openEditDialog = async (room) => {
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
  roomForm.price_unit = normalizeRoomPriceUnit(room.price_unit)
  roomForm.deposit = Number(room.deposit || 0)
  roomForm.features = Array.isArray(room.features) ? room.features : []
  roomForm.status = room.status || '空闲'
  roomForm.description = room.description || ''
  try {
    const detail = await roomsApi.getRoom(room.id)
    roomForm.price_unit = normalizeRoomPriceUnit(detail?.data?.room?.price_unit || roomForm.price_unit)
    roomForm.water_meter_imgs = detail?.data?.room?.water_meter_imgs || []
    roomForm.water_meter_img = detail?.data?.room?.water_meter_img || ''
    roomForm.electricity_meter_img = detail?.data?.room?.electricity_meter_img || ''
  } catch (error) {
    console.error('获取房间二维码详情失败', error)
  }
  dialogVisible.value = true
}

const handleSubmit = async () => {
  if (!roomFormRef.value) return
  
  await roomFormRef.value.validate(async (valid) => {
    if (valid) {
      submitting.value = true
      try {
        const payload = { ...roomForm, room_no: composedRoomNo.value }
        delete payload.water_meter_imgs
        delete payload.water_meter_img
        delete payload.electricity_meter_img
        let roomId = roomForm.id
        if (isEdit.value) {
          await roomsApi.updateRoom(roomForm.id, payload)
          roomId = roomForm.id
          ElMessage.success('房间更新成功')
        } else {
          const created = await roomsApi.addRoom(payload)
          roomId = created?.data?.id
          ElMessage.success('房间添加成功')
        }
        if (roomId && pendingRoomMeterFiles.water.length > 0) {
          for (const file of pendingRoomMeterFiles.water) {
            const res = await roomsApi.uploadRoomMeterImage(roomId, 'water', file)
            roomForm.water_meter_imgs = res?.data?.images || roomForm.water_meter_imgs
            roomForm.water_meter_img = res?.data?.images?.[0] || res?.data?.image || roomForm.water_meter_img
          }
        }
        if (roomId && pendingRoomMeterFiles.electricity) {
          const res = await roomsApi.uploadRoomMeterImage(roomId, 'electricity', pendingRoomMeterFiles.electricity)
          roomForm.electricity_meter_img = res?.data?.image || roomForm.electricity_meter_img
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

// 删除选中的空闲房间
const handleBatchDelete = async () => {
  if (!selectedRooms.value.length) {
    ElMessage.warning('请先勾选要删除的空闲房间')
    return
  }
  const count = selectedRooms.value.length
  const names = selectedRooms.value.map(r => r.room_no).join(', ')
  try {
    await ElMessageBox.confirm(`确定要删除选中的 ${count} 个房间：${names}？`, '删除', {
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
      ElMessage.success(`删除完成，成功 ${success} 个`)
    } else {
      const errMsg = failed.map(f => f.reason?.response?.data?.error || f.reason?.message || '未知错误').join('；')
      ElMessage.warning(`删除部分失败：成功 ${success} 个，失败 ${failed.length} 个。原因：${errMsg}`)
    }
    await fetchRooms()
    if (roomsTableRef.value) roomsTableRef.value.clearSelection()
    selectedRooms.value = []
  } catch (e) {
    console.error('删除异常：', e)
    ElMessage.error('删除失败')
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
    价格: formatRoomPrice(r),
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
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  color: #409EFF;
}

.view-switch-group {
  margin-right: 15px;
}

.header-operations {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.mobile-secondary-controls {
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

.mobile-filter-select {
  width: 120px;
}

.mobile-room-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.mobile-room-stat {
  min-width: 0;
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid var(--surface-border);
  background: var(--surface-muted);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.mobile-room-stat strong {
  font-size: 18px;
  color: var(--text-main);
}

.mobile-room-stat span {
  font-size: 12px;
  color: var(--text-secondary);
}

.room-feature-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

:deep(.room-details-descriptions .el-descriptions__cell) {
  white-space: normal;
  word-break: break-all;
  line-height: 1.5;
}

:deep(.room-details-tenant-table .cell) {
  white-space: normal;
  word-break: break-all;
  line-height: 1.5;
}

.room-actions-inline {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  justify-content: flex-start;
  align-content: center;
  width: 100%;
}

.room-actions-inline :deep(.el-button--small) {
  padding: 5px 8px;
  margin-left: 0;
}

.rooms-container :deep(.self-checkin-dialog) {
  border-radius: 18px;
  border: 1px solid var(--surface-border);
  background: var(--card-bg);
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.18);
  overflow: hidden;
}

.rooms-container :deep(.self-checkin-dialog .el-dialog__header) {
  margin-right: 0;
  padding: 16px 18px 14px;
  background: var(--card-bg);
  border-bottom: 1px solid var(--surface-border);
}

.rooms-container :deep(.self-checkin-dialog .el-dialog__title) {
  color: var(--text-main);
  font-size: 20px;
  font-weight: 700;
}

.rooms-container :deep(.self-checkin-dialog .el-dialog__headerbtn) {
  top: 14px;
  right: 16px;
}

.rooms-container :deep(.self-checkin-dialog .el-dialog__close) {
  color: var(--text-secondary);
}

.rooms-container :deep(.self-checkin-dialog .el-dialog__body) {
  padding: 16px 18px 18px;
  background: var(--card-bg);
}

.self-checkin-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.self-checkin-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.self-checkin-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.self-checkin-room {
  font-weight: 600;
  color: var(--text-main);
}

.self-checkin-tip {
  font-size: 13px;
  color: var(--text-secondary);
}

.self-checkin-links {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.self-checkin-link-card {
  padding: 12px;
  border: 1px solid var(--surface-border, #dbe4f0);
  border-radius: 12px;
}

.self-checkin-link-qr {
  margin: 10px 0;
}

.self-checkin-qr-image {
  width: 132px;
  height: 132px;
  display: block;
  border-radius: 10px;
  border: 1px solid var(--surface-border, #dbe4f0);
}

.self-checkin-link-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--text-secondary);
}

.self-checkin-link-url {
  margin: 8px 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  word-break: break-all;
}

.self-checkin-link-actions,
.self-checkin-submission-actions {
  display: flex;
  gap: 8px;
  flex-wrap: nowrap;
  white-space: nowrap;
}

.approve-dialog-alert,
.reject-dialog-alert {
  margin-bottom: 16px;
}

.self-checkin-approve-tip {
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.self-checkin-existing-tenants {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.self-checkin-existing-tenants__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
}

.hidden-file-input {
  display: none;
}

.table-meter-qr-image {
  width: 44px;
  height: 44px;
  border-radius: 8px;
  border: 1px solid var(--surface-border, #dbe4f0);
}

.table-meter-qr-wrap {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.table-meter-qr-count {
  font-size: 12px;
  color: var(--text-secondary);
}

.detail-meter-qr-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.detail-meter-qr-image {
  width: 64px;
  height: 64px;
  border-radius: 8px;
  border: 1px solid var(--surface-border, #dbe4f0);
}

.price-input-row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}

.price-unit-select {
  width: 110px;
  flex: 0 0 110px;
}

.room-meter-form-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.form-image-dropzone {
  width: 100%;
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

.room-meter-form-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.room-meter-form-tip {
  font-size: 12px;
  color: var(--text-secondary);
}

.room-meter-form-preview {
  display: flex;
  align-items: center;
}

.room-meter-form-image {
  width: 72px;
  height: 72px;
  border-radius: 10px;
  border: 1px solid var(--surface-border, #dbe4f0);
}

.table-panel {
  background: var(--card-bg);
  border: 1px solid var(--surface-border);
  border-radius: 16px;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
  padding: 10px 10px 16px;
}

.mobile-room-list {
  min-height: 320px;
}

.mobile-room-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mobile-room-card {
  padding: 14px;
  border: 1px solid var(--surface-border);
  border-radius: 18px;
  background: var(--card-bg);
  box-shadow: 0 14px 26px rgba(15, 23, 42, 0.08);
}

.mobile-room-card--occupied {
  border-color: rgba(245, 108, 108, 0.35);
}

.mobile-room-card--vacant {
  border-color: rgba(103, 194, 58, 0.35);
}

.mobile-room-card__top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
}

.mobile-room-card__room-no {
  font-size: 19px;
  font-weight: 700;
  color: var(--text-main);
}

.mobile-room-card__meta {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}

.mobile-room-card__facts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.mobile-room-fact {
  padding: 10px;
  border-radius: 12px;
  background: var(--surface-muted);
  border: 1px solid var(--surface-border);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mobile-room-fact span {
  font-size: 11px;
  color: var(--text-secondary);
}

.mobile-room-fact strong {
  font-size: 13px;
  color: var(--text-main);
  line-height: 1.4;
}

.mobile-room-card__features {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
}

.mobile-room-card__desc {
  margin: 12px 0 0;
  font-size: 13px;
  color: var(--text-regular);
  line-height: 1.6;
}

.mobile-room-card__actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 14px;
}

.mobile-room-card__actions :deep(.el-button) {
  width: 100%;
  min-height: 38px;
  margin-left: 0;
  border-radius: 10px;
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
  height: 42px;
  padding: 6px 4px;
}

:deep(.rooms-table .el-table__body-wrapper td.el-table__cell) {
  padding: 8px 4px;
  font-size: 13px;
}

:deep(.rooms-table .el-button--small) {
  padding: 6px 10px;
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

.rooms-container :deep(.room-details-dialog) {
  border-radius: 18px;
  border: 1px solid var(--surface-border);
  background: var(--card-bg);
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.18);
  overflow: hidden;
}

.rooms-container :deep(.room-details-dialog .el-dialog__header) {
  margin-right: 0;
  padding: 16px 18px 14px;
  background: var(--card-bg);
  border-bottom: 1px solid var(--surface-border);
}

.rooms-container :deep(.room-details-dialog .el-dialog__title) {
  color: var(--text-main);
  font-size: 20px;
  font-weight: 700;
}

.rooms-container :deep(.room-details-dialog .el-dialog__headerbtn) {
  top: 14px;
  right: 16px;
}

.rooms-container :deep(.room-details-dialog .el-dialog__close) {
  color: var(--text-secondary);
}

.rooms-container :deep(.room-details-dialog .el-dialog__body) {
  padding: 16px 18px 18px;
  background: var(--card-bg);
}

.checkout-confirm .warning {
  color: #F56C6C;
  font-weight: bold;
}

.room-info {
  margin-bottom: 20px;
}

.room-details-mobile-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.room-details-mobile-card {
  padding: 14px;
  border-radius: 16px;
  border: 1px solid var(--surface-border);
  background: var(--card-bg);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
}

.room-details-mobile-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0;
}

.room-details-mobile-row {
  padding: 12px 2px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.14);
}

.room-details-mobile-row:last-child {
  border-bottom: none;
  padding-bottom: 2px;
}

.room-details-mobile-row__label {
  flex: 0 0 72px;
  font-size: 12px;
  color: var(--text-secondary);
}

.room-details-mobile-row__value {
  flex: 1;
  text-align: right;
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-main);
  word-break: break-all;
}

.room-details-mobile-subtitle {
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
}

.room-details-mobile-qr-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.room-details-mobile-qr-image {
  width: 92px;
  height: 92px;
  border-radius: 12px;
  border: 1px solid var(--surface-border);
}

.room-details-mobile-empty {
  font-size: 13px;
  color: var(--text-secondary);
}

.tenant-list {
  margin-top: 20px;
}

.room-tenant-mobile-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.room-tenant-mobile-card {
  padding: 14px;
  border-radius: 14px;
  border: 1px solid var(--surface-border);
  background: var(--card-bg);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
}

.room-tenant-mobile-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.room-tenant-mobile-card__header strong {
  font-size: 15px;
  color: var(--text-main);
}

.room-tenant-mobile-details {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0;
  margin-top: 12px;
  border-top: 1px solid var(--surface-border);
}

.room-tenant-mobile-row {
  padding: 12px 2px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.14);
}

.room-tenant-mobile-row:last-child {
  border-bottom: none;
  padding-bottom: 2px;
}

.room-tenant-mobile-row__label {
  flex: 0 0 68px;
  font-size: 12px;
  color: var(--text-secondary);
}

.room-tenant-mobile-row__value {
  flex: 1;
  text-align: right;
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-main);
  word-break: break-all;
}

.self-checkin-mobile-submission-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 12px;
}

.self-checkin-mobile-submission-card {
  padding: 14px;
  border-radius: 14px;
  border: 1px solid var(--surface-border);
  background: var(--card-bg);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.self-checkin-mobile-submission-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.self-checkin-mobile-submission-top strong {
  font-size: 15px;
  color: var(--text-main);
}

.self-checkin-mobile-submission-tags {
  display: flex;
  align-items: center;
  gap: 8px;
}

.self-checkin-mobile-submission-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
}

.self-checkin-mobile-submission-item {
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--surface-border);
  background: var(--surface-muted);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.self-checkin-mobile-submission-item span {
  font-size: 11px;
  color: var(--text-secondary);
}

.self-checkin-mobile-submission-item strong {
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-main);
  word-break: break-all;
}

.self-checkin-mobile-submission-item--full {
  grid-column: 1 / -1;
}

.self-checkin-mobile-submission-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.self-checkin-mobile-submission-actions :deep(.el-button) {
  margin-left: 0;
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

.empty-state {
  padding: 24px 0;
}

.rooms-container--mobile {
  padding: 16px;
  border-radius: 16px;
}

.rooms-container--mobile .page-header {
  flex-direction: column;
  align-items: stretch;
  gap: 14px;
}

.rooms-container--mobile .header-operations {
  gap: 10px;
}

.rooms-container--mobile .header-operations :deep(.el-input),
.rooms-container--mobile .header-operations :deep(.el-button) {
  flex: 1 1 calc(50% - 5px);
}

.rooms-container--mobile .search-input {
  width: 100%;
}

.rooms-container--mobile .mobile-secondary-controls {
  gap: 10px;
}

.rooms-container--mobile .mobile-filter-select {
  width: calc(50% - 5px);
}

.rooms-container--mobile .mobile-room-stats {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.rooms-container--mobile .mobile-room-stat {
  padding: 10px;
}

.rooms-container--mobile .view-switch-group {
  margin-right: 0;
}

.rooms-container--mobile :deep(.view-switch-group .el-radio-button__inner) {
  width: 100%;
}

.rooms-container--mobile .price-input-row {
  flex-direction: column;
  align-items: stretch;
}

.rooms-container--mobile .price-unit-select {
  width: 100%;
  flex: none;
}

.rooms-container--mobile .self-checkin-toolbar,
.rooms-container--mobile .self-checkin-link-meta {
  flex-direction: column;
  align-items: flex-start;
}

.rooms-container--mobile :deep(.self-checkin-dialog) {
  border-radius: 18px;
}

.rooms-container--mobile :deep(.self-checkin-dialog .el-dialog__header) {
  padding: 14px 16px 12px;
}

.rooms-container--mobile :deep(.self-checkin-dialog .el-dialog__title) {
  font-size: 18px;
}

.rooms-container--mobile :deep(.self-checkin-dialog .el-dialog__body) {
  padding: 14px 16px 16px;
}

.rooms-container--mobile .self-checkin-link-actions,
.rooms-container--mobile .self-checkin-submission-actions {
  flex-wrap: wrap;
  white-space: normal;
}

.rooms-container--mobile :deep(.room-details-dialog) {
  border-radius: 18px;
}

.rooms-container--mobile :deep(.room-details-dialog .el-dialog__header) {
  padding: 14px 16px 12px;
}

.rooms-container--mobile :deep(.room-details-dialog .el-dialog__title) {
  font-size: 18px;
}

.rooms-container--mobile :deep(.room-details-dialog .el-dialog__body) {
  padding: 14px 16px 16px;
}

@media (max-width: 640px) {
  .mobile-room-card__facts {
    grid-template-columns: 1fr;
  }
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
