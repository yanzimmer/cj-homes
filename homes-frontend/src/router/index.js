import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/dashboard'
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue')
  },
  {
    path: '/:building([A-Za-z]+)/:roomNo(\\d+)/:token([A-Za-z0-9]+)',
    name: 'PublicCheckIn',
    alias: ['/check-in/:token'],
    component: () => import('../views/PublicCheckIn.vue')
  },
  {
    path: '/entry/:businessType/:token',
    name: 'PublicBusinessEntry',
    component: () => import('../views/PublicBusinessEntry.vue')
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'Home',
        component: () => import('../views/Home.vue'),
        meta: { requiresAuth: true }
      },
      {
        path: 'rooms',
        name: 'Rooms',
        component: () => import('../views/Rooms.vue'),
        meta: { requiresAuth: true }
      },
      {
        path: 'tenants',
        name: 'Tenants',
        component: () => import('../views/Tenants.vue'),
        meta: { requiresAuth: true }
      },
      {
        path: 'contract-templates',
        name: 'ContractTemplates',
        component: () => import('../views/ContractTemplates.vue'),
        meta: { requiresAuth: true }
      },
      {
        path: 'moves',
        name: 'Moves',
        component: () => import('../views/Moves.vue'),
        meta: { requiresAuth: true }
      },
      {
        path: 'procurement',
        name: 'Procurement',
        component: () => import('../views/Procurement.vue'),
        meta: { requiresAuth: true }
      },
      {
        path: 'warehouse',
        name: 'Warehouse',
        component: () => import('../views/Warehouse.vue'),
        meta: { requiresAuth: true }
      },
      {
        path: 'utility-bills',
        name: 'UtilityBills',
        component: () => import('../views/UtilityBills.vue'),
        meta: { requiresAuth: true }
      },
      {
        path: 'rent-ledger',
        name: 'RentLedger',
        component: () => import('../views/RentLedger.vue'),
        meta: { requiresAuth: true }
      },

      {
        path: 'repair-records',
        name: 'RepairRecords',
        component: () => import('../views/RepairRecords.vue'),
        meta: { requiresAuth: true }
      },
      {
        path: 'notify',
        name: 'Notify',
        component: () => import('../views/NotificationConfig.vue'),
        meta: { requiresAuth: true }
      },
      {
        path: 'system',
        name: 'System',
        component: () => import('../views/SystemMaintenance.vue'),
        meta: { requiresAuth: true }
      },
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('../views/NotFound.vue')
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  
  if (to.matched.some(record => record.meta.requiresAuth)) {
    if (!token) {
      next({ name: 'Login' })
    } else {
      next()
    }
  } else {
    next()
  }
})

export default router
