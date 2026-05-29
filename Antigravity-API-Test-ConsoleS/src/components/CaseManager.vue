<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue';
import { Play, Square, CheckSquare, Layers, Eye, X, Copy, Check, RefreshCw, StopCircle, Terminal, Download, PieChart, Loader2, CheckCircle2, XCircle, Search } from 'lucide-vue-next';

interface Props {
  projectId: number | null;
  domainUrl: string;
  token: string;
  projectName: string;
  environmentName: string;
  envId: number | null;
}

const props = defineProps<Props>();
const emit = defineEmits(['run-complete']);

// Cases List state
const cases = ref<any[]>([]);
const selectedCaseIds = ref<string[]>([]);
const activeCategory = ref<'all' | 'happy_path' | 'field_validation' | 'type_mismatch' | 'boundary'>('all');
const searchQuery = ref('');
const isRunning = ref(false);
const currentRunningIndex = ref<number>(-1);
const activeRunningCaseId = ref<string | null>(null);

// Terminal logging
interface LogEntry {
  timestamp: string;
  level: 'INFO' | 'WARN' | 'ERROR' | 'SUCCESS';
  message: string;
}
const logs = ref<LogEntry[]>([
  {
    timestamp: new Date().toLocaleTimeString(),
    level: 'INFO',
    message: '测试控制台就绪。请选择用例并点击“开始批量执行”启动流式监控。'
  }
]);

// Popup details modal
const detailCase = ref<any | null>(null);
const copiedId = ref<string | null>(null);

// Batch stream controllers
let activeReader: ReadableStreamDefaultReader<Uint8Array> | null = null;

// Metric states during batch run
const batchSuccessCount = ref(0);
const batchFailCount = ref(0);
const batchDurations = ref<number[]>([]);

// Fetch cases dynamically
async function fetchCases() {
  if (props.projectId === null) return;
  try {
    const res = await fetch(`/api/cases?project_id=${props.projectId}`);
    const json = await res.json();
    if (json.success) {
      cases.value = json.data.map((c: any) => ({
        ...c,
        status: 'idle',
        duration: undefined
      }));
      // Auto pre-select all cases initially
      selectedCaseIds.value = cases.value.map(c => c.case_id);
    } else {
      cases.value = [];
      selectedCaseIds.value = [];
    }
  } catch (err) {
    console.error('Failed to fetch cases', err);
    cases.value = [];
    selectedCaseIds.value = [];
  }
}

// Watchers
watch(() => props.projectId, () => {
  fetchCases();
  handleReset();
});

onMounted(() => {
  fetchCases();
});

// Category filtering
const filteredCases = computed(() => {
  let result = cases.value;
  
  // Category filtering
  if (activeCategory.value !== 'all') {
    if (activeCategory.value === 'field_validation') {
      result = result.filter(c => c.case_type === 'missing_param' || c.case_type === 'invalid_param');
    } else {
      result = result.filter(c => c.case_type === activeCategory.value);
    }
  }
  
  // Fuzzy text search filtering
  const query = searchQuery.value.trim().toLowerCase();
  if (query) {
    result = result.filter(c => 
      c.case_id.toLowerCase().includes(query) ||
      (c.api_path && c.api_path.toLowerCase().includes(query)) ||
      (c.api_name && c.api_name.toLowerCase().includes(query)) ||
      (c.description && c.description.toLowerCase().includes(query))
    );
  }
  
  return result;
});

// Selector controls
function handleSelectCase(id: string) {
  if (isRunning.value) return;
  if (selectedCaseIds.value.includes(id)) {
    selectedCaseIds.value = selectedCaseIds.value.filter(cid => cid !== id);
  } else {
    selectedCaseIds.value.push(id);
  }
}

function handleSelectAll() {
  if (isRunning.value) return;
  const filteredIds = filteredCases.value.map(c => c.case_id);
  const allSelected = filteredIds.every(id => selectedCaseIds.value.includes(id));

  if (allSelected) {
    selectedCaseIds.value = selectedCaseIds.value.filter(id => !filteredIds.includes(id));
  } else {
    selectedCaseIds.value = Array.from(new Set([...selectedCaseIds.value, ...filteredIds]));
  }
}

// Reset state
function handleReset() {
  if (isRunning.value) return;
  cases.value.forEach(c => {
    c.status = 'idle';
    c.duration = undefined;
  });
  batchSuccessCount.value = 0;
  batchFailCount.value = 0;
  batchDurations.value = [];
  logs.value = [
    {
      timestamp: new Date().toLocaleTimeString(),
      level: 'INFO',
      message: '工作空间已重置，测试用例执行结果已清空。'
    }
  ];
}

// Calculation metrics
const totalSelected = computed(() => selectedCaseIds.value.length);
const executedCount = computed(() => batchSuccessCount.value + batchFailCount.value);
const passRate = computed(() => {
  if (executedCount.value === 0) return 0;
  return parseFloat(((batchSuccessCount.value / executedCount.value) * 100).toFixed(1));
});
const avgDuration = computed(() => {
  if (batchDurations.value.length === 0) return 0;
  const total = batchDurations.value.reduce((acc, curr) => acc + curr, 0);
  return Math.round(total / batchDurations.value.length);
});
const progressPercentage = computed(() => {
  if (totalSelected.value === 0) return 0;
  return Math.min(100, Math.round((executedCount.value / totalSelected.value) * 100));
});

// Terminal scrolling hook
const terminalContainer = ref<HTMLDivElement | null>(null);
function addLog(level: 'INFO' | 'WARN' | 'ERROR' | 'SUCCESS', message: string) {
  logs.value.push({
    timestamp: new Date().toLocaleTimeString(),
    level,
    message
  });
  nextTick(() => {
    if (terminalContainer.value) {
      terminalContainer.value.scrollTop = terminalContainer.value.scrollHeight;
    }
  });
}

// Execute Batch sequential run using backend SSE Stream
async function handleStartBatchExecution() {
  if (selectedCaseIds.value.length === 0) {
    alert('请在左侧列表中至少勾选一个测试用例！');
    return;
  }

  isRunning.value = true;
  batchSuccessCount.value = 0;
  batchFailCount.value = 0;
  batchDurations.value = [];
  logs.value = [];
  currentRunningIndex.value = 0;

  addLog('INFO', `📡 批量自动化流水线启动，正在建立 SSE 长连接流监视后台...`);
  addLog('INFO', `📁 目标配置：项目 = [${props.projectName}]，环境 = [${props.environmentName}]`);
  addLog('INFO', `🔗 基础接口网关地址: ${props.domainUrl}`);
  addLog('INFO', `🔑 身份授权 Token: ${props.token ? '●●●●●●●●' : '未设置(默认匿名回归)'}`);
  addLog('INFO', `⚙️ 已规划并发/顺序执行队列, 共计 ${selectedCaseIds.value.length} 个测试用例`);
  addLog('INFO', `----------------- PIPELINE START -----------------`);

  // Reset statuses inside cases array to idle
  cases.value.forEach(c => {
    if (selectedCaseIds.value.includes(c.case_id)) {
      c.status = 'idle';
      c.duration = undefined;
    }
  });

  try {
    const response = await fetch('/api/run-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: props.projectId,
        case_ids: selectedCaseIds.value,
        base_url: props.domainUrl,
        token: props.token,
        env_id: props.envId
      })
    });

    if (!response.body) {
      addLog('ERROR', '❌ 无法解析 SSE 数据管道，数据流体为空！');
      isRunning.value = false;
      return;
    }

    activeReader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (isRunning.value) {
      const { value, done } = await activeReader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split('\n\n');
      buffer = chunks.pop() || ''; // Keep the last incomplete chunk in the buffer

      for (const chunk of chunks) {
        if (chunk.startsWith('data: ')) {
          const dataStr = chunk.slice(6).trim();
          if (!dataStr) continue;

          try {
            const parsed = JSON.parse(dataStr);
            if (parsed.type === 'log') {
              let logLevel: 'INFO' | 'WARN' | 'ERROR' | 'SUCCESS' = 'INFO';
              if (parsed.message.includes('[SUCCESS]') || parsed.message.includes('✅')) logLevel = 'SUCCESS';
              if (parsed.message.includes('[FAIL]') || parsed.message.includes('❌')) logLevel = 'ERROR';
              if (parsed.message.includes('[WARNING]') || parsed.message.includes('⚠️')) logLevel = 'WARN';
              addLog(logLevel, parsed.message);
            } else if (parsed.type === 'progress') {
              const caseId = parsed.case_id;
              const status = parsed.status === 'SUCCESS' ? 'success' : 'fail';
              const elapsed = parsed.elapsed;

              // Update state in lists
              const idxInCases = cases.value.findIndex(c => c.case_id === caseId);
              if (idxInCases !== -1) {
                cases.value[idxInCases].status = status;
                cases.value[idxInCases].duration = Math.round(elapsed);
              }

              if (status === 'success') batchSuccessCount.value++;
              else batchFailCount.value++;
              batchDurations.value.push(elapsed);
            } else if (parsed.type === 'complete') {
              addLog('SUCCESS', `🎉 批量自动化回归测试全部完毕！本次流水线运行结束。`);
              emit('run-complete');
            } else if (parsed.type === 'error') {
              addLog('ERROR', `❌ 运行时异常: ${parsed.message}`);
            }
          } catch (err) {
            console.error('Failed to parse SSE data block:', chunk, err);
          }
        }
      }
    }
  } catch (err: any) {
    addLog('ERROR', `❌ 数据管道通信中断/异常: ${err.message}`);
  } finally {
    isRunning.value = false;
    currentRunningIndex.value = -1;
    activeRunningCaseId.value = null;
  }
}

function handleStopExecution() {
  if (activeReader) {
    activeReader.cancel();
    activeReader = null;
  }
  isRunning.value = false;
  currentRunningIndex.value = -1;
  activeRunningCaseId.value = null;
  
  // Set running cases back to idle
  cases.value.forEach(c => {
    if (c.status === 'running') c.status = 'idle';
  });

  addLog('WARN', '⚠️ 用户手动干预，批量自动化回归测试流水线已终止。');
}

// Helpers for rendering categories badge
function renderCategoryLabel(cat: string) {
  switch (cat) {
    case 'happy_path': return '正向数据';
    case 'missing_param': return '缺失参数';
    case 'invalid_param': return '必填空值';
    case 'field_validation': return '必填与完整性';
    case 'type_mismatch': return '数据类型异常';
    case 'boundary': return '边界值校验';
    default: return cat;
  }
}

// Download local terminal logs
function downloadLogs() {
  const text = logs.value.map(l => `[${l.timestamp}] [${l.level}] ${l.message}`).join('\n');
  const blob = new Blob([text], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `antigravity_execution_log_${Date.now()}.log`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// Copy utils inside Modal
function copyText(val: string, id: string) {
  navigator.clipboard.writeText(val);
  copiedId.value = id;
  setTimeout(() => copiedId.value = null, 2000);
}

// Batch Case Migration logic
const showMigrationModal = ref(false);
const migrationTargetProjectId = ref<number | null>(null);
const allProjects = ref<any[]>([]);
const isMigrating = ref(false);

const availableProjects = computed(() => {
  return allProjects.value.filter(p => p.id !== props.projectId);
});

async function openMigrationModal() {
  migrationTargetProjectId.value = null;
  showMigrationModal.value = true;
  try {
    const res = await fetch('/api/projects');
    const json = await res.json();
    if (json.success) {
      allProjects.value = json.data;
    }
  } catch (err) {
    console.error('Failed to load projects for migration dropdown', err);
  }
}

function closeMigrationModal() {
  showMigrationModal.value = false;
}

async function submitMigration() {
  if (migrationTargetProjectId.value === null || selectedCaseIds.value.length === 0) return;
  isMigrating.value = true;
  try {
    const response = await fetch('/api/cases/migrate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        case_ids: selectedCaseIds.value,
        target_project_id: migrationTargetProjectId.value
      })
    });
    const result = await response.json();
    if (result.success) {
      alert(`成功迁移了 ${result.data.count} 个用例至目标项目！`);
      showMigrationModal.value = false;
      selectedCaseIds.value = [];
      await fetchCases();
    } else {
      alert(`迁移失败: ${result.detail || '未知错误'}`);
    }
  } catch (err: any) {
    alert(`网络请求出错: ${err.message}`);
  } finally {
    isMigrating.value = false;
  }
}
</script>

<template>
  <div class="grid grid-cols-1 xl:grid-cols-12 gap-6 items-start text-slate-800">
    <!-- LEFT MODULE - Case Suite Selections (5 cols) -->
    <section class="xl:col-span-5 bg-white border border-slate-100 p-5 rounded-2xl shadow-xs">
      <div class="flex items-center justify-between border-b border-slate-100 pb-4 mb-4">
        <div class="flex items-center gap-2 max-w-[50%]">
          <Layers class="w-5 h-5 text-violet-600 animate-pulse-subtle shrink-0" />
          <span class="font-bold text-slate-800 tracking-tight shrink-0">接口测试用例集</span>
          <span class="text-[10px] font-semibold bg-violet-50 text-violet-600 border border-violet-100 px-2 py-0.5 rounded-md truncate max-w-[120px]" :title="projectName">
            {{ projectName }}
          </span>
          <span class="px-2 py-0.5 rounded-full bg-slate-100 font-mono text-xs font-bold text-slate-500 shrink-0">
            {{ filteredCases.length }}
          </span>
        </div>

        <div class="flex items-center gap-2">
          <button
            @click="handleSelectAll"
            :disabled="isRunning"
            class="px-2.5 py-1.5 text-xs text-slate-600 hover:text-slate-800 hover:bg-slate-50 border border-slate-200 rounded-lg flex items-center gap-1.5 transition-all disabled:opacity-50 disabled:pointer-events-none cursor-pointer"
          >
            <CheckSquare v-if="filteredCases.every(c => selectedCaseIds.includes(c.case_id))" class="w-3.5 h-3.5 text-violet-600" />
            <Square v-else class="w-3.5 h-3.5" />
            <span>全选 ({{ filteredCases.length }})</span>
          </button>

          <!-- Selected counters -->
          <span class="text-xs bg-emerald-500 text-white font-bold px-2.5 py-1.5 rounded-lg flex items-center gap-1 shadow-xs">
            已选 <span class="font-mono">{{ selectedCaseIds.length }}</span>
          </span>

          <!-- Batch migrate button -->
          <button
            v-if="selectedCaseIds.length > 0 && !isRunning"
            @click="openMigrationModal"
            class="px-2.5 py-1.5 text-xs text-white bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 rounded-lg flex items-center gap-1.5 transition-all cursor-pointer shadow-xs font-semibold"
          >
            <Layers class="w-3.5 h-3.5" />
            <span>批量迁移项目</span>
          </button>
        </div>
      </div>

      <!-- Filters category tab -->
      <div class="flex gap-1 bg-slate-100/80 p-1 rounded-lg mb-4 text-xs font-medium">
        <button
          v-for="cat in (['all', 'happy_path', 'field_validation', 'type_mismatch', 'boundary'] as const)"
          :key="cat"
          @click="activeCategory = cat"
          :class="[
            'flex-grow py-1.5 text-center rounded-md transition-all cursor-pointer',
            activeCategory === cat ? 'bg-white text-slate-800 shadow-xs font-bold' : 'text-slate-500 hover:text-slate-700'
          ]"
        >
          {{ cat === 'all' ? '全部用例' : renderCategoryLabel(cat) }}
        </button>
      </div>

      <!-- Search Input Box -->
      <div class="relative mb-3.5">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索用例编号、描述、接口名称或路径..."
          class="w-full bg-slate-50 border border-slate-200 focus:border-violet-500 focus:ring-1 focus:ring-violet-500 rounded-xl pl-9 pr-8 py-2 text-xs font-medium focus:outline-none transition-all placeholder:text-slate-400 text-slate-750"
        />
        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <Search class="w-3.5 h-3.5 text-slate-450" />
        </div>
        <button
          v-if="searchQuery"
          @click="searchQuery = ''"
          class="absolute inset-y-0 right-0 pr-2.5 flex items-center text-slate-400 hover:text-slate-600 transition-colors cursor-pointer"
        >
          <X class="w-3.5 h-3.5" />
        </button>
      </div>

      <!-- Scrollable Case cards -->
      <div class="max-h-[520px] overflow-y-auto space-y-2.5 pr-2">
        <div
          v-for="item in filteredCases"
          :key="item.case_id"
          @click="handleSelectCase(item.case_id)"
          :class="[
            'flex gap-3 p-3.5 border rounded-xl cursor-pointer transition-all items-start relative select-none',
            selectedCaseIds.includes(item.case_id)
              ? 'bg-slate-50/50 border-slate-200 hover:border-slate-350'
              : 'bg-white border-slate-100 opacity-60 hover:opacity-90'
          ]"
        >
          <div class="pt-0.5 shrink-0" @click.stop>
            <input
              type="checkbox"
              v-model="selectedCaseIds"
              :value="item.case_id"
              :disabled="isRunning"
              class="w-4 h-4 text-violet-600 border-slate-300 rounded-sm focus:ring-violet-500 accent-violet-600"
            />
          </div>

          <div class="flex-1 space-y-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="font-mono text-[10px] font-bold text-violet-600 bg-violet-50 border border-violet-100 rounded-sm px-1.5 py-0.5">
                {{ item.case_id }}
              </span>
              <span class="text-[10px] font-mono font-semibold text-slate-400">
                {{ item.method }}
              </span>
              <span class="text-[10px] text-slate-400 truncate max-w-[150px] font-mono">
                {{ item.api_path }}
              </span>
            </div>

            <p class="text-slate-700 text-xs font-bold leading-relaxed truncate">
              {{ item.description }}
            </p>

            <div class="flex items-center justify-between gap-2 pt-1.5 flex-wrap">
              <div class="flex items-center gap-1.5">
                <span
                  :class="[
                    'px-2 py-0.5 text-[10px] font-semibold rounded-md border',
                    item.case_type === 'happy_path' ? 'text-emerald-700 bg-emerald-50 border-emerald-100' :
                    (item.case_type === 'missing_param' || item.case_type === 'invalid_param') ? 'text-amber-700 bg-amber-50 border-amber-100' :
                    item.case_type === 'type_mismatch' ? 'text-indigo-700 bg-indigo-50 border-indigo-100' :
                    'text-rose-700 bg-rose-50 border-rose-100'
                  ]"
                >
                  {{ renderCategoryLabel(item.case_type) }}
                </span>
                <span v-if="item.duration !== undefined" class="text-[10px] font-mono text-slate-400 bg-slate-50 border border-slate-100 px-1.5 py-0.5 rounded-md">
                  ⏱️ {{ item.duration }}ms
                </span>
              </div>
            </div>
          </div>

          <!-- Status badge column -->
          <div class="shrink-0 flex flex-col items-end gap-3.5 min-w-[95px]">
            <div class="flex items-center justify-end">
              <span v-if="item.status === 'running'" class="flex items-center gap-1 text-[10px] sm:text-xs text-amber-500 font-semibold bg-amber-50 px-2 py-0.5 rounded-lg border border-amber-100 animate-pulse">
                <Loader2 class="w-3 h-3 animate-spin" />
                运行中
              </span>
              <span v-else-if="item.status === 'success'" class="flex items-center gap-1 text-[10px] sm:text-xs text-emerald-600 font-semibold bg-emerald-50 px-2 py-0.5 rounded-lg border border-emerald-100">
                <CheckCircle2 class="w-3 h-3" />
                成功
              </span>
              <span v-else-if="item.status === 'fail'" class="flex items-center gap-1 text-[10px] sm:text-xs text-rose-600 font-semibold bg-rose-50 px-2 py-0.5 rounded-lg border border-rose-100">
                <XCircle class="w-3 h-3" />
                不通过
              </span>
              <span v-else class="text-[10px] font-semibold text-slate-400 bg-slate-50 px-2 py-0.5 rounded-lg border border-slate-100">
                待测
              </span>
            </div>

            <div class="relative group">
              <button
                @click.stop="detailCase = item"
                class="px-2.5 py-1 text-[10px] font-bold text-violet-600 bg-violet-50 hover:bg-violet-100 hover:text-violet-700 border border-violet-100 rounded-lg flex items-center gap-1 cursor-pointer transition-all shadow-2xs hover:shadow-xs hover:border-violet-200"
              >
                <Eye class="w-3 h-3" />
                <span>查看参数</span>
              </button>

              <!-- Hover Tooltip Popup Card -->
              <div class="absolute right-full top-1/2 -translate-y-1/2 mr-3 w-64 bg-[#0e131f] text-slate-200 border border-slate-800 rounded-xl p-4 shadow-xl z-20 pointer-events-none opacity-0 scale-95 group-hover:opacity-100 group-hover:scale-100 transition-all duration-200 ease-out select-none text-left font-sans">
                <!-- Pointer arrow -->
                <div class="absolute top-1/2 -translate-y-1/2 left-full w-0 h-0 border-y-[6px] border-y-transparent border-l-[6px] border-l-[#0e131f] filter drop-shadow-[1px_0_0_rgba(30,41,59,1)]"></div>
                
                <!-- Content -->
                <div class="space-y-2">
                  <div class="flex items-center justify-between border-b border-slate-800 pb-1.5 mb-1.5">
                    <span class="text-[10px] font-bold text-violet-400">简版契约参数</span>
                    <span class="font-mono text-[9px] bg-slate-800/80 px-1.5 py-0.5 text-slate-400 rounded-sm">{{ item.case_id }}</span>
                  </div>
                  
                  <div class="space-y-1 text-[11px] leading-relaxed">
                    <div class="flex items-start gap-1">
                      <span class="text-slate-500 font-bold shrink-0">接口:</span>
                      <span class="font-mono text-slate-300 break-all">{{ item.api_path }}</span>
                    </div>
                    <div class="flex items-start gap-1">
                      <span class="text-slate-500 font-bold shrink-0">方法:</span>
                      <span class="font-mono text-violet-400 font-bold">{{ item.method }}</span>
                    </div>
                    <div class="flex items-start gap-1">
                      <span class="text-slate-500 font-bold shrink-0">参数:</span>
                      <span class="text-slate-300 break-words font-medium">
                        {{ item.params && item.params.length > 0 ? item.params.map((p: any) => p.name).join(', ') : '无' }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="filteredCases.length === 0" class="text-center py-20 text-slate-400 font-medium">
          该项目下无匹配此类型的测试用例。
        </div>
      </div>
    </section>

    <!-- RIGHT MODULE - Realtime Stream, Progress, & Graphical Analysis (7 cols) -->
    <section class="xl:col-span-7 bg-white border border-slate-100 p-5 rounded-2xl shadow-xs space-y-6">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
        <div>
          <h3 class="font-bold text-slate-800 flex items-center gap-2">
            <span class="w-2.5 h-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 rounded-full animate-ping shrink-0" />
            <span>批量自动化流水线</span>
          </h3>
          <p class="text-slate-400 text-[11px] mt-0.5">正在实时监控后台用例执行过程</p>
        </div>

        <div class="flex items-center gap-2">
          <button
            @click="handleReset"
            :disabled="isRunning || executedCount === 0"
            class="p-2 border border-slate-200 hover:bg-slate-50 text-slate-600 hover:text-slate-800 rounded-xl transition-all cursor-pointer disabled:opacity-40 disabled:pointer-events-none"
            title="重置状态"
          >
            <RefreshCw class="w-4 h-4" />
          </button>

          <button
            v-if="isRunning"
            @click="handleStopExecution"
            class="px-4 py-2 bg-gradient-to-r from-rose-500 to-red-600 hover:from-rose-600 hover:to-red-700 text-white rounded-xl shadow-md hover:shadow-lg transition-all text-xs font-semibold flex items-center gap-1.5 cursor-pointer"
          >
            <StopCircle class="w-3.5 h-3.5" />
            <span>终止执行</span>
          </button>
          <button
            v-else
            @click="handleStartBatchExecution"
            class="px-4 py-2 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 text-white rounded-xl shadow-md hover:shadow-lg transition-all text-xs font-semibold flex items-center gap-1.5 cursor-pointer"
          >
            <Play class="w-3.5 h-3.5 fill-current" />
            <span>开始批量执行</span>
          </button>
        </div>
      </div>

      <!-- Metrics Cards Grid -->
      <div class="grid grid-cols-2 md:grid-cols-5 gap-3">
        <!-- Executed count -->
        <div class="bg-slate-50/75 border border-slate-100 rounded-xl p-3 text-center space-y-1">
          <span class="text-[10px] font-bold text-slate-400 block uppercase select-none">已执行 / 总数</span>
          <div class="text-lg font-black text-slate-700 font-mono">
            <span class="text-violet-600">{{ executedCount }}</span>
            <span class="text-slate-300 mx-1">/</span>
            <span>{{ totalSelected }}</span>
          </div>
          <span class="text-[9px] text-slate-400 block font-medium">用例勾选数</span>
        </div>

        <!-- Success count -->
        <div class="bg-emerald-50/40 border border-emerald-100/50 rounded-xl p-3 text-center space-y-1">
          <span class="text-[10px] font-bold text-emerald-600 block uppercase select-none">成功数</span>
          <div class="text-lg font-black text-emerald-600 font-mono">
            {{ batchSuccessCount }}
          </div>
          <span class="text-[9px] text-emerald-400 block font-medium">断言成功用例</span>
        </div>

        <!-- Fail count -->
        <div class="bg-rose-50/40 border border-rose-100/50 rounded-xl p-3 text-center space-y-1">
          <span class="text-[10px] font-bold text-rose-500 block uppercase select-none">异常数</span>
          <div class="text-lg font-black text-rose-500 font-mono">
            {{ batchFailCount }}
          </div>
          <span class="text-[9px] text-rose-400 block font-medium">失败断言用例</span>
        </div>

        <!-- Pass rate -->
        <div class="bg-blue-50/40 border border-blue-100/50 rounded-xl p-3 text-center space-y-1">
          <span class="text-[10px] font-bold text-blue-600 block uppercase select-none">通过率</span>
          <div class="text-lg font-black text-blue-600 font-mono">
            {{ passRate }}%
          </div>
          <span class="text-[9px] text-blue-400 block font-medium">校验通过比例</span>
        </div>

        <!-- Avg duration -->
        <div class="bg-slate-50/75 border border-slate-100 rounded-xl p-3 text-center space-y-1 col-span-2 md:col-span-1">
          <span class="text-[10px] font-bold text-slate-400 block uppercase select-none">平均时延</span>
          <div class="text-lg font-black text-slate-700 font-mono">
            {{ avgDuration }} <span class="text-[10px] text-slate-400 font-sans font-bold">ms</span>
          </div>
          <span class="text-[9px] text-slate-400 block font-medium">平均网络耗时</span>
        </div>
      </div>

      <!-- Progress bar -->
      <div class="space-y-1.5">
        <div class="flex justify-between items-center text-xs font-semibold text-slate-500 select-none">
          <span>流水线执行总进度</span>
          <span class="font-mono bg-slate-100 px-1.5 py-0.5 rounded-sm text-[10px] text-slate-600">
            {{ progressPercentage }}%
          </span>
        </div>
        <div class="relative w-full h-2.5 bg-slate-100 rounded-full overflow-hidden">
          <div
            :style="{ width: `${progressPercentage}%` }"
            class="absolute top-0 bottom-0 left-0 bg-gradient-to-r from-violet-500 to-indigo-600 rounded-full transition-all duration-300"
          />
        </div>
      </div>

      <!-- Bottom logs terminal and SVG passing ring chart -->
      <div class="grid grid-cols-1 md:grid-cols-12 gap-5">
        <!-- Scrolling terminal (Col 8) -->
        <div class="md:col-span-8 bg-[#0b0f19] border border-slate-800 rounded-2xl flex flex-col overflow-hidden h-[340px]">
          <!-- Window bar -->
          <div class="px-4 py-2 bg-[#121826] border-b border-[#1b2336] flex items-center justify-between text-slate-400 select-none">
            <div class="flex items-center gap-2">
              <div class="flex gap-1.5 shrink-0">
                <span class="w-2.5 h-2.5 rounded-full bg-rose-500/80" />
                <span class="w-2.5 h-2.5 rounded-full bg-amber-500/80" />
                <span class="w-2.5 h-2.5 rounded-full bg-emerald-500/80" />
              </div>
              <div class="flex items-center gap-1.5 text-[10px] font-mono text-slate-400 pl-2">
                <Terminal class="w-3.5 h-3.5" />
                <span>bash - sse_streaming.sh</span>
              </div>
            </div>
            
            <div class="flex items-center gap-2">
              <span class="bg-violet-950 text-violet-400 ring-1 ring-violet-500/30 text-[9px] font-mono font-semibold px-2 py-0.5 rounded-sm">
                FastAPI SSE Stream
              </span>
              <button
                @click="downloadLogs"
                :disabled="logs.length === 0"
                class="p-1 hover:bg-[#1f293d] rounded-sm text-slate-400 hover:text-slate-200 transition-colors disabled:opacity-30 cursor-pointer"
                title="导出终端日志"
              >
                <Download class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <!-- Log display -->
          <div ref="terminalContainer" class="p-4 flex-1 overflow-y-auto font-mono text-[11px] leading-relaxed space-y-1">
            <div v-for="(log, idx) in logs" :key="idx" class="flex items-start gap-1.5">
              <span class="text-violet-300/80 shrink-0 font-semibold font-mono">[{{ log.timestamp }}]</span>
              <span
                :class="[
                  log.level === 'SUCCESS' ? 'text-emerald-300 font-bold' :
                  log.level === 'WARN' ? 'text-amber-300 font-bold' :
                  log.level === 'ERROR' ? 'text-rose-300 font-bold bg-rose-950/40 px-1 rounded-sm border border-rose-900/30' :
                  'text-slate-100'
                ]"
              >
                {{ log.message }}
              </span>
            </div>
          </div>
        </div>

        <!-- Donut SVG Ring (Col 4) -->
        <div class="md:col-span-4 bg-slate-50/50 border border-slate-100 p-4 rounded-2xl flex flex-col items-center justify-center space-y-4">
          <span class="text-[11px] font-bold text-slate-500 flex items-center gap-1.5 uppercase tracking-wider self-start select-none">
            <PieChart class="w-3.5 h-3.5 text-violet-500" />
            <span>用例通过率</span>
          </span>

          <div class="relative flex items-center justify-center w-36 h-36">
            <svg class="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
              <!-- Background ring -->
              <circle
                cx="50"
                cy="50"
                r="38"
                class="stroke-slate-100 fill-none"
                stroke-width="8"
              />
              <!-- Success segment -->
              <circle
                v-if="passRate > 0"
                cx="50"
                cy="50"
                r="38"
                class="stroke-emerald-500 fill-none transition-all duration-500"
                stroke-width="8"
                stroke-linecap="round"
                stroke-dasharray="238.76"
                :stroke-dashoffset="238.76 - (238.76 * passRate) / 100"
              />
              <!-- Fail segment overlay -->
              <circle
                v-if="batchFailCount > 0 && executedCount > 0"
                cx="50"
                cy="50"
                r="38"
                class="stroke-rose-500 fill-none transition-all duration-500"
                stroke-width="8"
                stroke-linecap="round"
                stroke-dasharray="238.76"
                :stroke-dashoffset="238.76 - (238.76 * (batchFailCount / executedCount) * 100) / 100"
                :transform="`rotate(${3.6 * passRate} 50 50)`"
              />
            </svg>

            <div class="absolute flex flex-col items-center text-center select-none">
              <span class="text-xl font-black text-slate-700 font-mono tracking-tight leading-none">
                {{ passRate }}%
              </span>
              <span class="text-[9px] font-bold text-slate-400 mt-1">综合通过率</span>
            </div>
          </div>

          <!-- Legends -->
          <div class="w-full grid grid-cols-2 gap-2 text-[10px] font-medium pt-1 select-none">
            <div class="flex items-center gap-1.5 justify-center bg-white border border-emerald-50/50 py-1.5 px-2 rounded-lg">
              <span class="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
              <span class="text-slate-400">成功:</span>
              <span class="font-bold text-emerald-600 font-mono">{{ batchSuccessCount }}</span>
            </div>
            <div class="flex items-center gap-1.5 justify-center bg-white border border-rose-50/50 py-1.5 px-2 rounded-lg">
              <span class="w-2 h-2 rounded-full bg-rose-500 shrink-0" />
              <span class="text-slate-400">失败:</span>
              <span class="font-bold text-rose-500 font-mono">{{ batchFailCount }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- CASE PARAMETERS DETAILS MODAL (POPUP) -->
    <div v-if="detailCase" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/65 backdrop-blur-xs">
      <div class="bg-white w-full max-w-2xl rounded-2xl shadow-2xl border border-slate-100 flex flex-col max-h-[85vh] overflow-hidden">
        <!-- Modal Header -->
        <div class="p-5 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <div class="flex items-center gap-2.5">
            <span class="font-mono text-xs font-bold text-violet-600 bg-violet-50 border border-violet-100 rounded-md px-2 py-1 select-none">
              {{ detailCase.case_id }}
            </span>
            <div>
              <h4 class="text-sm font-bold text-slate-800 leading-tight">
                {{ detailCase.description }}
              </h4>
              <p class="text-[10px] text-slate-400 mt-0.5">测试用例契约与运行参数详情</p>
            </div>
          </div>
          <button @click="detailCase = null" class="p-1.5 hover:bg-slate-200/60 rounded-lg text-slate-400 hover:text-slate-600 transition-colors cursor-pointer">
            <X class="w-4.5 h-4.5" />
          </button>
        </div>

        <!-- Modal Body (Scrollable) -->
        <div class="p-6 overflow-y-auto space-y-5 text-xs text-slate-600 leading-relaxed custom-scrollbar flex-1">
          <!-- Request endpoints path -->
          <div class="space-y-1.5">
            <span class="font-bold text-slate-700 block">请求端点 (API Path)</span>
            <div class="flex items-center gap-2 bg-slate-50 border border-slate-100 p-2.5 rounded-xl font-mono text-slate-600 break-all select-all">
              <span class="px-1.5 py-0.5 rounded-sm text-[10px] font-bold text-white bg-violet-600 shrink-0">
                {{ detailCase.method }}
              </span>
              <span class="text-[11px] truncate flex-1 font-semibold text-slate-500 font-mono">
                {{ domainUrl }}{{ detailCase.api_path }}
              </span>
              <button
                @click="copyText(`${domainUrl}${detailCase.api_path}`, 'url')"
                class="p-1 text-slate-400 hover:text-violet-600 hover:bg-violet-50 rounded-md cursor-pointer transition-colors"
                title="复制URL"
              >
                <Check v-if="copiedId === 'url'" class="w-3.5 h-3.5 text-emerald-500" />
                <Copy v-else class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <!-- Assert specification explanation -->
          <div class="bg-violet-50/50 border border-violet-100/50 p-3.5 rounded-xl space-y-1">
            <span class="font-bold text-violet-800 flex items-center gap-1.5">
              🛡️ 本用例运行期待与测试断言 (Assert Specification)
            </span>
            <p class="text-slate-600 leading-relaxed pl-5 font-medium text-[11px]">
              【自动化用例断言】期待服务端响应的 HTTP 状态码为 <span class="font-mono text-violet-750 font-bold">{{ detailCase.expected_code || 200 }}</span>。
              另外将链式读取该项目先前节点的注入上下文传递参数（如 Token 与会话 Session-Id），对接口属性做完整契约解析断言验证。
            </p>
          </div>

          <!-- Request parameters tables -->
          <div class="space-y-2">
            <span class="font-bold text-slate-700 block">契约请求参数表 (Query/Body Params Schema)</span>
            <div v-if="detailCase.params && detailCase.params.length > 0" class="border border-slate-100 rounded-xl overflow-hidden bg-white">
              <table class="w-full text-left border-collapse">
                <thead>
                  <tr class="bg-slate-50 text-slate-500 font-bold border-b border-slate-100 text-[10px] uppercase">
                    <th class="px-3.5 py-2">参数名</th>
                    <th class="px-3.5 py-2">类型</th>
                    <th class="px-3.5 py-2 w-16">必填</th>
                    <th class="px-3.5 py-2">描述说明</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-50 text-[11px]">
                  <tr v-for="p in detailCase.params" :key="p.name" class="hover:bg-slate-50/50">
                    <td class="px-3.5 py-2.5 font-mono font-bold text-slate-700">{{ p.name }}</td>
                    <td class="px-3.5 py-2.5 font-mono text-slate-400 text-[10px]">{{ p.type }}</td>
                    <td class="px-3.5 py-2.5">
                      <span v-if="p.required" class="text-[9px] font-bold text-rose-600 bg-rose-50 border border-rose-100/70 px-1 py-0.5 rounded-sm">必填</span>
                      <span v-else class="text-[9px] font-medium text-slate-400 bg-slate-50 border border-slate-100 px-1 py-0.5 rounded-sm">可选</span>
                    </td>
                    <td class="px-3.5 py-2.5 text-slate-500">{{ p.desc || p.description }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else class="text-center py-5 bg-slate-50 border border-slate-100/60 rounded-xl text-slate-400 text-[11px]">
              该用例接口依赖于标准 JSON Payload 发送，无外部 Query Parameters。
            </div>
          </div>

          <!-- Payload sample view -->
          <div v-if="detailCase.body_template || detailCase.bodyTemplate" class="space-y-2">
            <div class="flex justify-between items-center">
              <span class="font-bold text-slate-700">发送负载样例 (Request Body Sample)</span>
              <button
                @click="copyText(detailCase.body_template || detailCase.bodyTemplate, 'body')"
                class="text-[10px] text-violet-600 hover:text-violet-700 flex items-center gap-1 hover:underline cursor-pointer font-bold"
              >
                <Check v-if="copiedId === 'body'" class="w-3.5 h-3.5 text-emerald-500" />
                <span v-if="copiedId === 'body'">已复制</span>
                <span v-else class="flex items-center gap-1"><Copy class="w-3 h-3" /> 复制 JSON</span>
              </button>
            </div>
            <pre class="bg-slate-900 text-slate-200 p-4 rounded-xl font-mono text-[10.5px] overflow-x-auto leading-relaxed border border-slate-950 shadow-inner max-h-[160px] whitespace-pre-wrap">{{ detailCase.body_template || detailCase.bodyTemplate }}</pre>
          </div>
        </div>

        <!-- Footer closure -->
        <div class="p-4 border-t border-slate-100 bg-slate-50 flex justify-end">
          <button @click="detailCase = null" class="px-4 py-1.5 text-xs font-semibold bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 rounded-lg shadow-2xs transition-colors cursor-pointer">
            确定 / 关闭
          </button>
        </div>
      </div>
    </div>

    <!-- BATCH CASE MIGRATION MODAL -->
    <div v-if="showMigrationModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/65 backdrop-blur-xs">
      <div class="bg-white w-full max-w-md rounded-2xl shadow-2xl border border-slate-100 flex flex-col overflow-hidden">
        <!-- Header -->
        <div class="p-5 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <div class="flex items-center gap-2">
            <Layers class="w-5 h-5 text-violet-600 animate-pulse-subtle" />
            <div>
              <h4 class="text-sm font-bold text-slate-800 leading-tight">批量迁移用例到项目</h4>
              <p class="text-[10px] text-slate-400 mt-0.5">将已选的 {{ selectedCaseIds.length }} 个用例移动至其他项目</p>
            </div>
          </div>
          <button @click="closeMigrationModal" class="p-1.5 hover:bg-slate-200/60 rounded-lg text-slate-400 hover:text-slate-600 transition-colors cursor-pointer">
            <X class="w-4.5 h-4.5" />
          </button>
        </div>

        <!-- Body -->
        <div class="p-6 space-y-4 text-xs text-slate-600">
          <div class="space-y-1.5">
            <label class="font-bold text-slate-700 block">选择目标项目</label>
            <div class="relative">
              <select
                v-model="migrationTargetProjectId"
                class="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-xs font-semibold focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-all text-slate-700 cursor-pointer appearance-none"
              >
                <option :value="null" disabled>请选择目标迁移项目...</option>
                <option
                  v-for="p in availableProjects"
                  :key="p.id"
                  :value="p.id"
                >
                  {{ p.name }} (ID: {{ p.id }})
                </option>
              </select>
              <div class="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none text-slate-400">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
              </div>
            </div>
          </div>

          <div class="bg-amber-50 border border-amber-100/60 p-3.5 rounded-xl space-y-1">
            <span class="font-bold text-amber-800 flex items-center gap-1.5">
              ⚠️ 注意事项
            </span>
            <p class="text-slate-600 leading-relaxed pl-5 font-medium text-[11px]">
              迁移后，这些用例的 `project_id` 将更新为目标项目，并且用例 ID 重新命名为 `CASE-P{目标项目ID}-xxx` 依次递增以防碰撞。迁移为立即执行且不可逆，请谨慎操作。
            </p>
          </div>
        </div>

        <!-- Footer -->
        <div class="p-4 border-t border-slate-100 bg-slate-50 flex justify-end gap-2">
          <button
            @click="closeMigrationModal"
            class="px-4 py-1.5 text-xs font-semibold bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 rounded-lg shadow-2xs transition-colors cursor-pointer"
          >
            取消
          </button>
          <button
            @click="submitMigration"
            :disabled="migrationTargetProjectId === null || isMigrating"
            class="px-4 py-1.5 text-xs font-semibold text-white bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 disabled:from-slate-300 disabled:to-slate-400 disabled:cursor-not-allowed rounded-lg shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer"
          >
            <Loader2 v-if="isMigrating" class="w-3.5 h-3.5 animate-spin" />
            <span>确认迁移</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 5px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.02);
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(99, 102, 241, 0.25);
  border-radius: 4px;
}
</style>
