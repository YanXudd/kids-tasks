// ============================================================
// 儿童任务打卡 - 前端业务逻辑 (Alpine.js)
// ============================================================

function kidsApp() {
  return {
    // ============ 全局状态 ============
    token: localStorage.getItem('kt_token') || null,
    user: null,
    family: null,
    loading: false,
    globalLoading: false,
    authMode: 'login',
    currentTab: 'today',

    // 表单
    loginForm: { username: '', password: '' },
    regForm: {
      username: '', password: '',
      role: 'child', avatar_emoji: '🧒', invite_code: '',
    },
    redeemMultiplier: 1.0,

    // 数据
    todayTasks: [],
    selectedTaskIds: [],
    allTasks: [],
    pendingCheckins: [],
    products: [],
    orders: [],
    pendingOrders: [],
    confirmedOrders: [],
    transactions: [],
    pointsBalance: null,
    pointsStats: { total_earned: 0, total_spent: 0, total_deducted: 0 },
    stats: {},
    trendRange: 'week',
    familyMembers: [],
    balanceBumpKey: 0,

    // 弹窗
    showFamilyInfo: false,
    showSettings: false,
    taskForm: { open: false, id: null, name: '', emoji: '⭐', points: 5, points_mode: 'reward', repeat_type: 'daily', repeat_config: [], assigned_to: [], category: '' },
    productForm: { open: false, id: null, name: '', price: 10, stock: 1, quantity: 1, unit: '', category: '', image_url: '', preview: '', file: null },
    activeCategory: '',
    activeTaskCategory: '',
    imagePreview: { open: false, src: '' },
    cropModal: { open: false },
    _cropper: null,
    confirmDialog: { open: false, message: '', _resolve: null },
    clearSoldoutForm: { open: false, password: '' },
    pwdForm: { old_password: '', new_password: '', confirm_password: '' },
    dragState: { active: false, taskId: null, startY: 0, currentY: 0, el: null, listType: '' },
    sortMode: false,
    penaltyFolded: true,   // 审核页减分任务默认折叠

    // 视图切换（家长端）
    viewMode: 'parent', // 'parent' 或 'child'
    viewAsChildId: null, // 当前查看的儿童 ID
    childPickerOpen: false, // 多儿童选择弹窗
    toasts: [],
    _toastId: 1,

    // ============ 初始化 ============
    async init() {
      if (this.token) {
        try {
          const r = await this.api('GET', '/api/auth/me');
          this.user = r.user;
          this.family = r.family;
          this.setDefaultTab();
          await this.refreshAll();
          // 加载家庭设置（倍率）
          if (this.user.role === 'parent') {
            await this.loadMultiplier();
          }
        } catch (e) {
          this.logout();
        }
      }
    },

    setDefaultTab() {
      this.currentTab = this.user.role === 'child' ? 'today' : 'ptasks';
    },

    // ============ 网络请求 ============
    async api(method, url, body = null, isForm = false) {
      const headers = {};
      if (this.token) headers['Authorization'] = 'Bearer ' + this.token;
      const opts = { method, headers };
      if (body) {
        if (isForm) {
          opts.body = body;
        } else {
          headers['Content-Type'] = 'application/json';
          opts.body = JSON.stringify(body);
        }
      }
      const res = await fetch(url, opts);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.error || `请求失败 (${res.status})`);
      }
      return data;
    },

    // ============ 登录 / 注册 ============
    async doLogin() {
      if (!this.loginForm.username || !this.loginForm.password) {
        return this.toast('请输入用户名和密码', 'error');
      }
      this.loading = true;
      try {
        const r = await this.api('POST', '/api/auth/login', this.loginForm);
        this.token = r.token;
        localStorage.setItem('kt_token', r.token);
        this.user = r.user;
        this.family = r.family;
        this.setDefaultTab();
        await this.refreshAll();
        this.toast('登录成功 🎉', 'success');
      } catch (e) {
        this.toast(e.message, 'error');
      } finally {
        this.loading = false;
      }
    },

    async doRegister() {
      const f = this.regForm;
      if (!f.username || !f.password) {
        return this.toast('请填写完整', 'error');
      }
      if (f.role === 'child' && !f.invite_code.trim()) {
        return this.toast('请输入家庭邀请码', 'error');
      }
      this.loading = true;
      try {
        const r = await this.api('POST', '/api/auth/register', f);
        this.token = r.token;
        localStorage.setItem('kt_token', r.token);
        this.user = r.user;
        this.family = r.family;
        this.setDefaultTab();
        await this.refreshAll();
        this.toast('注册成功 🎉', 'success');
        if (f.role === 'parent') {
          setTimeout(() => { this.showFamilyInfo = true; }, 500);
        }
      } catch (e) {
        this.toast(e.message, 'error');
      } finally {
        this.loading = false;
      }
    },

    logout() {
      this.token = null;
      localStorage.removeItem('kt_token');
      this.user = null;
      this.family = null;
      this.toast('再见 👋', 'info');
    },

    // ============ Tab 切换 ============
    async switchTab(tab) {
      this.currentTab = tab;
      await this.refreshForTab();
    },
    // ============ 视图切换（家长 ↔ 儿童） ============
    get children() {
      return this.familyMembers.filter(m => m.role === 'child');
    },

    async switchToParent() {
      this.viewMode = 'parent';
      this.viewAsChildId = null;
      this.currentTab = 'ptasks';
      await this.refreshAll();
    },

    async switchToChild(childId) {
      this.viewMode = 'child';
      this.viewAsChildId = childId;
      this.currentTab = 'today';
      await this.refreshAll();
    },

    async toggleViewMode() {
      const kids = this.children;
      if (kids.length === 0) {
        this.toast('还没有小朋友哦', 'info');
        return;
      }
      if (this.viewMode === 'parent') {
        if (kids.length === 1) {
          await this.switchToChild(kids[0].id);
        } else {
          this.childPickerOpen = true;
        }
      } else {
        await this.switchToParent();
      }
    },
    async pickChild(childId) {
      this.childPickerOpen = false;
      await this.switchToChild(childId);
    },

    // ============ 数据刷新 ============
    async refreshAll() {
      await this.refreshForTab();
      if (this.user?.role === 'child') {
        await this.fetchBalance();
      } else if (this.viewMode === 'child' && this.viewAsChildId) {
        await this.fetchBalance();
      }
      if (this.user?.role === 'parent') {
        await this.fetchFamilyMembers();
        // 家长端：加载审核角标数据
        if (this.viewMode === 'parent') {
          await this.fetchPendingCheckins();
          await this.fetchConfirmedOrders();
        }
      }
    },

    async refreshForTab() {
      const t = this.currentTab;
      try {
        // 儿童视图模式下的 tab
        if (t === 'today' && (this.user.role === 'child' || this.viewMode === 'child')) {
          await this.fetchTodayTasks();
        } else if (t === 'points' && (this.user.role === 'child' || this.viewMode === 'child')) {
          await this.fetchBalance();
          await this.fetchTransactions();
        } else if (t === 'shop' && (this.user.role === 'child' || this.viewMode === 'child')) {
          await this.fetchProducts();
          await this.fetchBalance();
        } else if (t === 'orders' && (this.user.role === 'child' || this.viewMode === 'child')) {
          await this.fetchOrders();
        } else if (t === 'ptasks') {
          await this.fetchAllTasks();
        } else if (t === 'approve') {
          await this.fetchAllTasks();
          await this.fetchPendingCheckins();
          await this.fetchConfirmedOrders();
        } else if (t === 'pproducts') {
          await this.fetchProducts();
        } else if (t === 'porders') {
          await this.fetchPendingOrders();
        } else if (t === 'stats') {
          await this.fetchStats();
        }
      } catch (e) {
        this.toast(e.message, 'error');
      }
    },

    // ============ 数据拉取 ============
    async fetchTodayTasks() {
      const params = new URLSearchParams();
      if (this.user?.role === 'parent' && this.viewMode === 'child' && this.viewAsChildId) {
        params.set('child_id', this.viewAsChildId);
      }
      const qs = params.toString();
      const r = await this.api('GET', '/api/checkins/today' + (qs ? '?' + qs : ''));
      this.todayTasks = r.tasks || [];
      this.selectedTaskIds = [];
    },
    async fetchAllTasks() {
      this.allTasks = await this.api('GET', '/api/tasks');
    },
    rewardTasks(list) {
      return (list || []).filter(t => Number(t.points) >= 0);
    },
    penaltyTasks(list) {
      return (list || []).filter(t => Number(t.points) < 0);
    },
    rewardCheckins(list) {
      return (list || []).filter(c => Number(c.points) >= 0);
    },
    penaltyCheckins(list) {
      return (list || []).filter(c => Number(c.points) < 0);
    },
    getCategories() {
      const cats = [...new Set(this.products.map(p => p.category).filter(c => c))];
      return cats.sort();
    },
    filteredProducts() {
      if (!this.activeCategory) return this.products;
      return this.products.filter(p => p.category === this.activeCategory);
    },
    getTaskCategories() {
      const cats = [...new Set(this.allTasks.map(t => t.category).filter(c => c))];
      return cats.sort();
    },
    filteredAllTasks() {
      if (!this.activeTaskCategory) return this.allTasks;
      return this.allTasks.filter(t => t.category === this.activeTaskCategory);
    },
    filteredTodayTasks() {
      if (!this.activeTaskCategory) return this.todayTasks;
      return this.todayTasks.filter(t => t.category === this.activeTaskCategory);
    },
    async fetchPendingCheckins() {
      this.pendingCheckins = await this.api('GET', '/api/checkins/pending');
    },
    async resetTodayCheckins() {
      const total = this.pendingCheckins.length;
      const rewardCount = this.rewardCheckins(this.pendingCheckins).length;
      const penaltyCount = this.penaltyCheckins(this.pendingCheckins).length;
      let detail = `今日共有 ${total} 条待审核记录`;
      if (rewardCount > 0) detail += `\n✅ 打卡 ${rewardCount} 条`;
      if (penaltyCount > 0) detail += `\n🧨 减分 ${penaltyCount} 条`;
      detail += `\n\n重置后将清除今日所有打卡记录，确认重置？`;
      if (!await this.showConfirm(detail)) return;
      try {
        const r = await this.api('POST', '/api/checkins/reset-today');
        this.toast(r.message || '已重置今日任务', 'success');
        await this.fetchPendingCheckins();
        await this.fetchTodayTasks();
        await this.fetchStats();
      } catch (e) {
        this.toast(e.message, 'error');
      }
    },
    async fetchProducts() {
      this.products = await this.api('GET', '/api/products');
    },
    async fetchOrders() {
      const params = new URLSearchParams();
      if (this.user?.role === 'parent' && this.viewMode === 'child' && this.viewAsChildId) {
        params.set('child_id', this.viewAsChildId);
      }
      const qs = params.toString();
      const all = await this.api('GET', '/api/orders/history' + (qs ? '?' + qs : ''));
      this.orders = all.filter(o => o.status !== 'rejected');
    },
    async fetchPendingOrders() {
      this.pendingOrders = await this.api('GET', '/api/orders/pending');
    },
    async fetchConfirmedOrders() {
      this.confirmedOrders = await this.api('GET', '/api/orders/confirmed');
    },
    async fetchTransactions() {
      const params = new URLSearchParams();
      if (this.user?.role === 'parent' && this.viewMode === 'child' && this.viewAsChildId) {
        params.set('child_id', this.viewAsChildId);
      }
      const qs = params.toString();
      this.transactions = await this.api('GET', '/api/points/transactions' + (qs ? '?' + qs : ''));
    },
    async fetchBalance() {
      if (this.user.role === 'child') {
        const r = await this.api('GET', '/api/points/balance');
        this.pointsBalance = r.balance;
        this.pointsStats = r;
      } else if (this.viewMode === 'child' && this.viewAsChildId) {
        // 家长查看特定儿童余额
        const r = await this.api('GET', '/api/points/balance');
        const kids = r.children || [];
        const child = kids.find(c => c.child_id === this.viewAsChildId);
        if (child) {
          this.pointsBalance = child.balance;
          this.pointsStats = child;
        }
      }
    },
    async fetchStats() {
      const r = this.trendRange || 'week';
      this.stats = await this.api('GET', '/api/stats/overview?range=' + r);
    },
    async switchTrendRange(r) {
      this.trendRange = r;
      await this.fetchStats();
      this.$nextTick(() => {
        const el = document.querySelector('.overflow-x-auto.no-scrollbar');
        if (el) el.scrollLeft = el.scrollWidth;
      });
    },
    async fetchFamilyMembers() {
      try {
        this.familyMembers = await this.api('GET', '/api/family/members');
      } catch (e) { /* ignore */ }
    },

    // ============ 打卡（儿童端） ============
    toggleTaskCheck(t) {
      if (t.checkin_status === 'pending' || t.checkin_status === 'confirmed') return;
      // rejected tasks can be re-selected
      const idx = this.selectedTaskIds.indexOf(t.id);
      if (idx >= 0) this.selectedTaskIds.splice(idx, 1);
      else this.selectedTaskIds.push(t.id);
    },

    async submitCheckins() {
      if (!this.selectedTaskIds.length) return;
      this.loading = true;
      try {
        const body = { task_ids: this.selectedTaskIds };
        // 家长代打卡时传 child_id
        if (this.user?.role === 'parent' && this.viewMode === 'child' && this.viewAsChildId) {
          body.child_id = this.viewAsChildId;
        }
        const r = await this.api('POST', '/api/checkins/submit', body);
        this.toast(`打卡成功！等家长确认就能拿到积分啦 🎉`, 'success');
        this.dropCoins(8);
        this.selectedTaskIds = [];
        await this.fetchTodayTasks();
      } catch (e) {
        this.toast(e.message, 'error');
      } finally {
        this.loading = false;
      }
    },

    // ============ 任务管理（家长端） ============
    openTaskForm(t) {
      if (t) {
        this.taskForm = { open: true, id: t.id, name: t.name, emoji: t.emoji, points: t.points, points_mode: t.points >= 0 ? 'reward' : 'penalty', repeat_type: t.repeat_type || 'daily', repeat_config: Array.isArray(t.repeat_config) ? [...t.repeat_config] : [], assigned_to: Array.isArray(t.assigned_to) ? [...t.assigned_to] : [], category: t.category || '' };
      } else {
        this.taskForm = { open: true, id: null, name: '', emoji: '⭐', points: 5, points_mode: 'reward', repeat_type: 'daily', repeat_config: [], assigned_to: [], category: '' };
      }
      // 确保 familyMembers 已加载
      if (this.familyMembers.length === 0) this.fetchFamilyMembers();
    },
    setTaskPointsMode(mode) {
      this.taskForm.points_mode = mode;
      const v = Math.abs(parseInt(this.taskForm.points || 0, 10) || 0);
      if (mode === 'penalty') {
        this.taskForm.points = v === 0 ? -1 : -v;
        if (!this.taskForm.emoji || this.taskForm.emoji === '⭐') this.taskForm.emoji = '🧨';
      } else {
        this.taskForm.points = v === 0 ? 1 : v;
        if (this.taskForm.emoji === '🧨') this.taskForm.emoji = '⭐';
      }
    },
    // 切换 repeat_config 中的值（用于每周/每月选日子）
    toggleRepeatVal(val) {
      const cfg = this.taskForm.repeat_config;
      const idx = cfg.indexOf(val);
      if (idx >= 0) cfg.splice(idx, 1);
      else cfg.push(val);
      cfg.sort((a, b) => a - b);
    },
    // 添加固定日期
    addFixedDate(e) {
      const d = e.target.value;
      if (d && !this.taskForm.repeat_config.includes(d)) {
        this.taskForm.repeat_config.push(d);
        this.taskForm.repeat_config.sort();
      }
      e.target.value = '';
    },
    // 移除固定日期
    removeFixedDate(d) {
      const cfg = this.taskForm.repeat_config;
      const idx = cfg.indexOf(d);
      if (idx >= 0) cfg.splice(idx, 1);
    },
    // 切换任务分配给哪个小朋友
    toggleChildAssign(childId) {
      const at = this.taskForm.assigned_to;
      const idx = at.indexOf(childId);
      if (idx >= 0) at.splice(idx, 1);
      else at.push(childId);
    },
    // 加减分
    adjustPointsForm: { open: false, child_id: null, child_name: '', amount: 1, reason: '' },
    openAdjustPoints(child) {
      this.adjustPointsForm = { open: true, child_id: child.id, child_name: child.username || child.child_name, amount: 1, reason: '' };
    },
    async submitAdjustPoints() {
      const f = this.adjustPointsForm;
      if (!f.reason.trim()) return this.toast('请填写原因', 'error');
      try {
        const r = await this.api('POST', '/api/points/adjust', { child_id: f.child_id, amount: f.amount, reason: f.reason });
        this.toast(r.message, 'success');
        this.adjustPointsForm.open = false;
        await this.fetchStats();
      } catch (e) { this.toast(e.message, 'error'); }
    },
    async saveTask() {
      const f = this.taskForm;
      if (!f.name || f.points === '' || f.points === null || f.points === undefined) {
        return this.toast('请填写名称和积分', 'error');
      }
      f.points = parseInt(f.points, 10);
      if (Number.isNaN(f.points) || f.points === 0) {
        return this.toast('积分不能为 0', 'error');
      }
      try {
        if (f.id) {
          await this.api('PUT', `/api/tasks/${f.id}`, f);
          this.toast('保存成功 ✓', 'success');
        } else {
          await this.api('POST', '/api/tasks', f);
          this.toast('任务已添加 ✨', 'success');
        }
        this.taskForm.open = false;
        await this.fetchAllTasks();
      } catch (e) {
        this.toast(e.message, 'error');
      }
    },
    async deleteTask(t) {
      if (!await this.showConfirm(`确定删除任务 ${t.emoji} ${t.name} 吗？`)) return;
      try {
        await this.api('DELETE', `/api/tasks/${t.id}`);
        this.toast('已删除', 'info');
        await this.fetchAllTasks();
      } catch (e) {
        this.toast(e.message, 'error');
      }
    },

    // ============ 家长主动执行减分 ============
    async applyPenalty(task, child) {
      if (!await this.showConfirm(`确定对 ${child.avatar_emoji} ${child.username} 执行「${task.emoji} ${task.name}」减 ${Math.abs(task.points)} 分吗？`)) return;
      try {
        const r = await this.api('POST', '/api/checkins/apply-penalty', { task_id: task.id, child_id: child.id });
        this.toast(`已对 ${child.username} 扣 ${Math.abs(task.points)} 分 ✅`, 'success');
        await this.fetchStats();
      } catch (e) { this.toast(e.message, 'error'); }
    },

    // ============ 打卡审核 ============
    async confirmCheckin(c) {
      try {
        await this.api('POST', `/api/checkins/${c.id}/confirm`);
        const amountText = c.points >= 0 ? `+${c.points}` : `-${Math.abs(c.points)}`;
        this.toast(`已确认！🎉 ${amountText} 积分`, 'success');
        await this.fetchPendingCheckins();
      } catch (e) { this.toast(e.message, 'error'); }
    },
    async rejectCheckin(c) {
      try {
        await this.api('POST', `/api/checkins/${c.id}/reject`);
        this.toast('已拒绝', 'info');
        await this.fetchPendingCheckins();
      } catch (e) { this.toast(e.message, 'error'); }
    },

    // ============ 任务拖拽排序 ============
    dragStart(e, taskId, listType) {
      const touch = e.touches[0];
      const el = e.target.closest('.task-drag-item');
      this.dragState = { active: true, taskId, startY: touch.clientY, currentY: touch.clientY, el, listType };
      el.style.zIndex = '50';
      el.style.opacity = '0.8';
      el.style.transition = 'none';
    },
    dragMove(e) {
      if (!this.dragState.active) return;
      e.preventDefault();
      const touch = e.touches[0];
      this.dragState.currentY = touch.clientY;
      const dy = this.dragState.currentY - this.dragState.startY;
      this.dragState.el.style.transform = `translateY(${dy}px)`;

      const items = this.dragState.el.parentElement.querySelectorAll('.task-drag-item');
      items.forEach(item => {
        if (item === this.dragState.el) return;
        const rect = item.getBoundingClientRect();
        const midY = rect.top + rect.height / 2;
        if (touch.clientY < midY && item.previousElementSibling === this.dragState.el) {
          item.parentNode.insertBefore(this.dragState.el, item);
          this.dragState.startY = touch.clientY;
          this.dragState.el.style.transform = 'translateY(0)';
        } else if (touch.clientY > midY && item.nextElementSibling === this.dragState.el) {
          item.parentNode.insertBefore(this.dragState.el, item.nextElementSibling);
          this.dragState.startY = touch.clientY;
          this.dragState.el.style.transform = 'translateY(0)';
        }
      });
    },
    async dragEnd() {
      if (!this.dragState.active) return;
      const el = this.dragState.el;
      el.style.transform = '';
      el.style.opacity = '';
      el.style.zIndex = '';
      el.style.transition = '';

      const container = el.parentElement;
      const ids = [...container.querySelectorAll('.task-drag-item')].map(item => parseInt(item.dataset.taskId));
      this.dragState = { active: false, taskId: null, startY: 0, currentY: 0, el: null, listType: '' };

      try {
        await this.api('PUT', '/api/tasks/sort', { task_ids: ids });
        await this.fetchAllTasks();
      } catch (e) {
        this.toast('排序保存失败', 'error');
      }
    },

    async moveTask(taskId, direction) {
      const tasks = this.allTasks;
      const idx = tasks.findIndex(t => t.id === taskId);
      if (idx === -1) return;
      const task = tasks[idx];

      const sameType = tasks.filter(t => (t.points >= 0) === (task.points >= 0));
      const typeIdx = sameType.findIndex(t => t.id === taskId);

      if (direction === 'up' && typeIdx === 0) return;
      if (direction === 'down' && typeIdx === sameType.length - 1) return;

      const targetIdx = direction === 'up' ? typeIdx - 1 : typeIdx + 1;
      const temp = sameType[typeIdx];
      sameType[typeIdx] = sameType[targetIdx];
      sameType[targetIdx] = temp;

      const rewardTasks = tasks.filter(t => t.points >= 0);
      const penaltyTasks = tasks.filter(t => t.points < 0);
      const newReward = task.points >= 0 ? sameType : rewardTasks;
      const newPenalty = task.points < 0 ? sameType : penaltyTasks;
      const allIds = [...newReward, ...newPenalty].map(t => t.id);

      try {
        await this.api('PUT', '/api/tasks/sort', { task_ids: allIds });
        await this.fetchAllTasks();
      } catch (e) {
        this.toast('排序保存失败', 'error');
      }
    },

    async moveTaskToEdge(taskId, direction) {
      const tasks = this.allTasks;
      const idx = tasks.findIndex(t => t.id === taskId);
      if (idx === -1) return;
      const task = tasks[idx];

      const sameType = tasks.filter(t => (t.points >= 0) === (task.points >= 0));
      const typeIdx = sameType.findIndex(t => t.id === taskId);

      if (direction === 'top' && typeIdx === 0) return;
      if (direction === 'bottom' && typeIdx === sameType.length - 1) return;

      const [removed] = sameType.splice(typeIdx, 1);
      if (direction === 'top') {
        sameType.unshift(removed);
      } else {
        sameType.push(removed);
      }

      const rewardTasks = tasks.filter(t => t.points >= 0);
      const penaltyTasks = tasks.filter(t => t.points < 0);
      const newReward = task.points >= 0 ? sameType : rewardTasks;
      const newPenalty = task.points < 0 ? sameType : penaltyTasks;
      const allIds = [...newReward, ...newPenalty].map(t => t.id);

      try {
        await this.api('PUT', '/api/tasks/sort', { task_ids: allIds });
        await this.fetchAllTasks();
      } catch (e) {
        this.toast('排序保存失败', 'error');
      }
    },

    // ============ 商品管理 ============
    openProductForm(p) {
      if (p) {
        this.productForm = { open: true, id: p.id, name: p.name, price: p.price, stock: p.stock, quantity: p.quantity || 1, unit: p.unit || '', category: p.category || '', image_url: p.image_url, preview: '', file: null };
      } else {
        this.productForm = { open: true, id: null, name: '', price: 10, stock: 1, quantity: 1, unit: '', category: '', image_url: '', preview: '', file: null };
      }
    },
    onProductImage(e) {
      const file = e.target.files?.[0];
      if (!file) return;
      e.target.value = ''; // 重置 input，允许重复选择同一文件
      const reader = new FileReader();
      reader.onload = (ev) => {
        this._pendingImageFile = file;
        this._cropSrc = ev.target.result;
        this.cropModal.open = true;
        this.$nextTick(() => {
          const img = this.$refs.cropImage;
          if (!img) return;
          img.src = this._cropSrc;
          if (this._cropper) { this._cropper.destroy(); this._cropper = null; }
          this._cropper = new Cropper(img, {
            aspectRatio: 1,
            viewMode: 1,
            autoCropArea: 1,
            responsive: true,
            guides: true,
          });
        });
      };
      reader.readAsDataURL(file);
    },
    confirmCrop() {
      if (!this._cropper) return;
      this._cropper.getCroppedCanvas({ width: 480, height: 480 }).toBlob((blob) => {
        const croppedFile = new File([blob], this._pendingImageFile?.name || 'cropped.webp', { type: 'image/webp' });
        this.productForm.file = croppedFile;
        this.productForm.preview = URL.createObjectURL(blob);
        this.cropModal.open = false;
        this._cropper.destroy();
        this._cropper = null;
      }, 'image/webp', 0.8);
    },
    cancelCrop() {
      this.cropModal.open = false;
      if (this._cropper) { this._cropper.destroy(); this._cropper = null; }
    },
    previewImage(src) {
      if (src) { this.imagePreview.src = src; this.imagePreview.open = true; }
    },
    async saveProduct() {
      const f = this.productForm;
      if (!f.name || !f.price) {
        return this.toast('请填写名称和价格', 'error');
      }
      try {
        const form = new FormData();
        form.append('name', f.name);
        form.append('price', f.price);
        form.append('stock', f.stock);
        form.append('quantity', f.quantity || 1);
        form.append('unit', f.unit || '');
        form.append('category', f.category || '');
        if (f.file) form.append('image', f.file);

        if (f.id) {
          await this.api('PUT', `/api/products/${f.id}`, form, true);
          this.toast('保存成功 ✓', 'success');
        } else {
          await this.api('POST', '/api/products', form, true);
          this.toast('商品已上架 ✨', 'success');
        }
        this.productForm.open = false;
        await this.fetchProducts();
      } catch (e) {
        this.toast(e.message, 'error');
      }
    },
    async clearSoldout() {
      const f = this.clearSoldoutForm;
      if (!f.password) return this.toast('请输入密码', 'error');
      try {
        const r = await this.api('POST', '/api/products/clear-soldout', { password: f.password });
        this.toast(`已清除 ${r.count} 个售罄商品`, 'success');
        f.open = false; f.password = '';
        await this.fetchProducts();
      } catch(e) { this.toast(e.message || '清除失败', 'error'); }
    },
    async deleteProduct(p) {
      if (!await this.showConfirm(`确定下架商品「${p.name}」吗？`)) return;
      try {
        await this.api('DELETE', `/api/products/${p.id}`);
        this.toast('已下架', 'info');
        await this.fetchProducts();
      } catch (e) {
        this.toast(e.message, 'error');
      }
    },

    // ============ 购买 ============
    async buyProduct(p, evt) {
      if (p.stock === 0) {
        return this.toast('该商品已售罄 😅', 'error');
      }
      const actualPrice = p.actual_price || p.price;
      if (this.pointsBalance < actualPrice) {
        return this.toast('积分不足哦 😅', 'error');
      }
      if (!await this.showConfirm(`用 ${actualPrice} 积分兑换「${p.name}」吗？`)) return;
      (async () => {
        try {
          const body = { product_id: p.id };
          if (this.user?.role === 'parent' && this.viewMode === 'child' && this.viewAsChildId) {
            body.child_id = this.viewAsChildId;
          }
          const r = await this.api('POST', '/api/orders/create', body);
          this.toast('兑换成功 ✨', 'success');
          // 星星飞散动画
          this.scatterStars(evt?.target);
          if (r.balance !== undefined) {
            this.pointsBalance = r.balance;
          } else {
            await this.fetchBalance();
          }
          await this.fetchProducts();
        } catch (e) {
          this.toast(e.message, 'error');
        }
      })();
    },

    async confirmOrder(o) {
      try {
        await this.api('POST', `/api/orders/${o.id}/confirm`);
        this.toast(`已确认兑换 🎁`, 'success');
        await this.fetchPendingOrders();
      } catch (e) { this.toast(e.message, 'error'); }
    },
    async rejectOrder(o) {
      try {
        await this.api('POST', `/api/orders/${o.id}/reject`);
        this.toast('已拒绝', 'info');
        await this.fetchPendingOrders();
      } catch (e) { this.toast(e.message, 'error'); }
    },
    async markPurchased(o) {
      if (o.purchased) return;
      if (!await this.showConfirm(`确认「${o.product_name}」已兑现？`)) return;
      try {
        await this.api('POST', `/api/orders/${o.id}/purchased`);
        o.purchased = true;
        this.toast('已标记为兑现 ✓', 'success');
      } catch (e) { this.toast(e.message, 'error'); }
    },
    async cancelOrder(o) {
      if (o.purchased) return;
      if (!await this.showConfirm(`确认撤回「${o.product_name}」？\n积分 ${o.points_cost} 分将退还`)) return;
      try {
        const r = await this.api('POST', `/api/orders/${o.id}/cancel`);
        this.pointsBalance = r.balance;
        this.toast('已撤回，积分已退还 ✓', 'success');
        await this.fetchOrders();
        await this.fetchConfirmedOrders();
      } catch (e) { this.toast(e.message, 'error'); }
    },
    // 检测环境
    _isMobile() {
      return /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
    },
    _isWeChat() {
      return /MicroMessenger/i.test(navigator.userAgent);
    },
    _openAppOrWeb(appUrl, webUrl) {
      if (this._isWeChat()) {
        this.toast('请点击右上角 ··· 选择「在浏览器中打开」再操作', 'info');
        return;
      }
      if (this._isMobile()) {
        let opened = false;
        const onHide = () => {
          opened = true;
          document.removeEventListener('visibilitychange', onHide);
          document.removeEventListener('pagehide', onHide);
        };
        document.addEventListener('visibilitychange', onHide);
        document.addEventListener('pagehide', onHide);

        // 直接跳转 deep link
        window.location.href = appUrl;

        setTimeout(() => {
          document.removeEventListener('visibilitychange', onHide);
          document.removeEventListener('pagehide', onHide);
          if (!opened) {
            this.toast('未检测到对应 APP，请先安装后再试', 'error');
          }
        }, 2000);
      } else {
        window.open(webUrl, '_blank');
      }
    },
    openTB(name) {
      const q = encodeURIComponent(name);
      const h5Url = encodeURIComponent(`https://s.taobao.com/search?q=${q}`);
      this._openAppOrWeb(
        `tbopen://m.taobao.com/tbopen/index.html?action=ali.open.nav&module=h5&source=auto&h5Url=${h5Url}`,
        `https://s.taobao.com/search?q=${q}`
      );
    },

    // ============ 修改密码 ============
    async changePassword() {
      const f = this.pwdForm;
      if (!f.old_password || !f.new_password) {
        return this.toast('请填写完整', 'error');
      }
      if (f.new_password.length < 4) {
        return this.toast('新密码至少4位', 'error');
      }
      if (f.new_password !== f.confirm_password) {
        return this.toast('两次新密码不一致', 'error');
      }
      this.loading = true;
      try {
        const r = await this.api('POST', '/api/auth/change-password', f);
        this.toast(r.message, 'success');
        this.pwdForm = { old_password: '', new_password: '', confirm_password: '' };
        this.showSettings = false;
      } catch (e) {
        this.toast(e.message, 'error');
      } finally {
        this.loading = false;
      }
    },

    // ============ 积分倍率设置 ============
    async loadMultiplier() {
      try {
        const r = await this.api('GET', '/api/family/settings');
        this.redeemMultiplier = r.redeem_multiplier || 1.0;
      } catch (e) {
        console.error('加载倍率失败:', e);
      }
    },
    async saveMultiplier() {
      if (this.redeemMultiplier < 0.1 || this.redeemMultiplier > 10) {
        return this.toast('倍率范围 0.1 ~ 10', 'error');
      }
      this.loading = true;
      try {
        const r = await this.api('PUT', '/api/family/settings', {
          redeem_multiplier: this.redeemMultiplier
        });
        this.redeemMultiplier = r.redeem_multiplier;
        this.toast('倍率已保存 ✓', 'success');
      } catch (e) {
        this.toast(e.message, 'error');
      } finally {
        this.loading = false;
      }
    },

    // ============ 自定义确认弹窗 ============
    showConfirm(message) {
      return new Promise((resolve) => {
        this.confirmDialog = { open: true, message, _resolve: resolve };
      });
    },
    confirmOk() {
      this.confirmDialog.open = false;
      this.confirmDialog._resolve?.(true);
    },
    confirmCancel() {
      this.confirmDialog.open = false;
      this.confirmDialog._resolve?.(false);
    },

    // ============ Toast ============
    toast(message, type = 'info') {
      const id = this._toastId++;
      this.toasts.push({ id, message, type });
      setTimeout(() => {
        this.toasts = this.toasts.filter(t => t.id !== id);
      }, 2400);
    },

    // ============ 动画：金币掉落 ============
    dropCoins(count = 8) {
      for (let i = 0; i < count; i++) {
        const c = document.createElement('div');
        c.className = 'coin';
        c.textContent = ['🪙','💰','⭐','✨'][Math.floor(Math.random()*4)];
        c.style.left = (10 + Math.random() * 80) + 'vw';
        c.style.animationDelay = (Math.random() * 0.6) + 's';
        c.style.fontSize = (28 + Math.random()*24) + 'px';
        document.body.appendChild(c);
        setTimeout(() => c.remove(), 2400);
      }
      // 数字跳动
      this.balanceBumpKey++;
    },

    // ============ 动画：星星飞散 ============
    scatterStars(srcEl) {
      const rect = srcEl?.getBoundingClientRect?.();
      const x0 = rect ? rect.left + rect.width / 2 : window.innerWidth / 2;
      const y0 = rect ? rect.top + rect.height / 2 : window.innerHeight / 2;
      for (let i = 0; i < 12; i++) {
        const s = document.createElement('div');
        s.className = 'star';
        s.textContent = ['⭐','✨','💫','🌟'][Math.floor(Math.random()*4)];
        s.style.left = x0 + 'px';
        s.style.top = y0 + 'px';
        const angle = (Math.PI * 2 * i) / 12 + Math.random() * 0.3;
        const dist = 80 + Math.random() * 120;
        s.style.setProperty('--tx', Math.cos(angle) * dist + 'px');
        s.style.setProperty('--ty', Math.sin(angle) * dist + 'px');
        document.body.appendChild(s);
        setTimeout(() => s.remove(), 1300);
      }
    },

    // ============ 工具方法 ============
    fmtTime(iso) {
      if (!iso) return '';
      try {
        const d = new Date(iso);
        const now = new Date();
        const diff = (now - d) / 1000;
        if (diff < 60) return '刚刚';
        if (diff < 3600) return Math.floor(diff/60) + ' 分钟前';
        if (diff < 86400) return Math.floor(diff/3600) + ' 小时前';
        if (diff < 86400*7) return Math.floor(diff/86400) + ' 天前';
        return d.toLocaleDateString();
      } catch { return iso; }
    },
    repeatLabel(t) {
      const rt = t.repeat_type || 'daily';
      const rc = t.repeat_config || [];
      const weekNames = ['一','二','三','四','五','六','日'];
      if (rt === 'daily') return '📅 每日';
      if (rt === 'weekly') {
        if (rc.length === 0) return '📆 每周';
        return '📆 每周 ' + rc.map(d => '周' + weekNames[d]).join('、');
      }
      if (rt === 'monthly') {
        if (rc.length === 0) return '🗓️ 每月';
        return '🗓️ 每月 ' + rc.join('、') + '号';
      }
      if (rt === 'fixed') {
        if (rc.length === 0) return '📌 固定日子';
        return '📌 ' + rc.length + '个固定日';
      }
      return '';
    },
    statusText(s) {
      return { pending: '待确认', confirmed: '已通过', rejected: '已拒绝', cancelled: '已取消' }[s] || s;
    },
  };
}
