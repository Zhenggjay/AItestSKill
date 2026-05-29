<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { Database, Activity, Percent, Clock, FileSpreadsheet, BarChart3, Calendar, ShieldCheck, ShieldAlert, ChevronRight } from 'lucide-vue-next';

interface Props {
  projectId: number | null;
}

const props = defineProps<Props>();

// History reports list
const reports = ref<any[]>([]);
const activeReportId = ref<number | null>(null);

// Selected report full details from backend
const selectedReport = ref<any | null>(null);
const selectedResult = ref<any | null>(null);
const isLoadingDetails = ref(false);

// Fetch reports summaries
async function fetchReports() {
  if (props.projectId === null) return;
  try {
    const res = await fetch(`/api/reports?project_id=${props.projectId}`);
    const json = await res.json();
    if (json.success) {
      reports.value = json.data;
      if (reports.value.length > 0) {
        // Auto select the first report initially
        viewReportDetail(reports.value[0].id);
      } else {
        activeReportId.value = null;
        selectedReport.value = null;
        selectedResult.value = null;
      }
    } else {
      reports.value = [];
    }
  } catch (err) {
    console.error('Failed to fetch reports list', err);
    reports.value = [];
  }
}

// Watch project changes
watch(() => props.projectId, () => {
  fetchReports();
});

onMounted(() => {
  fetchReports();
});

// Fetch detailed diagnostic reports by ID
async function viewReportDetail(reportId: number) {
  activeReportId.value = reportId;
  isLoadingDetails.value = true;
  selectedReport.value = null;
  selectedResult.value = null;
  
  try {
    const res = await fetch(`/api/reports/${reportId}`);
    const json = await res.json();
    if (res.ok && json.success) {
      selectedReport.value = json.data;
      // Auto select the first test case result in details view
      if (selectedReport.value.results && selectedReport.value.results.length > 0) {
        selectedResult.value = selectedReport.value.results[0];
      }
    }
  } catch (err) {
    console.error('Failed to fetch report details', err);
  } finally {
    isLoadingDetails.value = false;
  }
}

// Calculated aggregations for Bento Cards
const totalRuns = computed(() => reports.value.length);
const bestPassRate = computed(() => {
  if (reports.value.length === 0) return 0;
  const rates = reports.value.map(r => r.pass_rate || 0);
  return parseFloat(Math.max(...rates).toFixed(1));
});
const historicAvgDuration = computed(() => {
  if (reports.value.length === 0) return 0;
  const durs = reports.value.map(r => r.avg_response_time || 0);
  const total = durs.reduce((acc, curr) => acc + curr, 0);
  return Math.round(total / reports.value.length);
});

// JSON formatting helper
function safeJsonFormat(val: any) {
  if (val === null || val === undefined) return '';
  if (typeof val === 'object') return JSON.stringify(val, null, 2);
  try {
    const parsed = JSON.parse(val);
    return JSON.stringify(parsed, null, 2);
  } catch (e) {
    return String(val);
  }
}
</script>

<template>
  <div class="space-y-6 text-slate-800">
    <!-- NO DATA FALLBACK -->
    <div v-if="reports.length === 0" class="bg-white border border-slate-100 rounded-2xl p-12 text-center max-w-lg mx-auto space-y-4 shadow-xs">
      <div class="w-16 h-16 bg-violet-50 text-violet-600 rounded-full flex items-center justify-center mx-auto">
        <Database class="w-8 h-8 animate-pulse-subtle" />
      </div>
      <h3 class="text-base font-bold text-slate-800">暂无历史报告数据</h3>
      <p class="text-slate-400 text-xs leading-relaxed">
        当前测试项目尚未运行过批量测试。请回到“用例执行管理”面板，选择用例并点击启动开始批量自动化执行！
      </p>
    </div>

    <!-- MAIN DASHBOARD VIEWPORT -->
    <div v-else class="space-y-6">
      <!-- Historical Bento Cards Aggregations Grid -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <!-- Runs card -->
        <div class="bg-white border border-slate-100 p-4 rounded-xl shadow-xs flex items-center gap-4 relative overflow-hidden">
          <div class="p-3 bg-violet-50 text-violet-600 rounded-lg">
            <Activity class="w-5 h-5" />
          </div>
          <div>
            <span class="text-[10px] font-bold text-slate-400 block uppercase select-none">累计运行批次</span>
            <span class="text-xl font-extrabold text-slate-700 font-mono">{{ totalRuns }} 次</span>
            <span class="text-[9px] text-slate-400 block font-medium">包含重置在内的完整流程</span>
          </div>
          <div class="absolute right-3 bottom-1.5 opacity-20 select-none">
            <FileSpreadsheet class="w-14 h-14 text-slate-400" />
          </div>
        </div>

        <!-- Highest Pass rate -->
        <div class="bg-white border border-slate-100 p-4 rounded-xl shadow-xs flex items-center gap-4 relative overflow-hidden">
          <div class="p-3 bg-emerald-50 text-emerald-600 rounded-lg">
            <Percent class="w-5 h-5" />
          </div>
          <div>
            <span class="text-[10px] font-bold text-slate-400 block uppercase select-none">最高通过率</span>
            <span class="text-xl font-extrabold text-emerald-600 font-mono">{{ bestPassRate }}%</span>
            <span class="text-[9px] text-emerald-500 block font-medium">最佳批次断言成功比例</span>
          </div>
          <div class="absolute right-3 bottom-0.5 opacity-15 text-emerald-600 select-none">
            <Percent class="w-14 h-14" />
          </div>
        </div>

        <!-- Latency avg -->
        <div class="bg-white border border-slate-100 p-4 rounded-xl shadow-xs flex items-center gap-4 relative overflow-hidden">
          <div class="p-3 bg-slate-50 text-slate-600 rounded-lg">
            <Clock class="w-5 h-5" />
          </div>
          <div>
            <span class="text-[10px] font-bold text-slate-400 block uppercase select-none">历史平均时延</span>
            <span class="text-xl font-extrabold text-slate-700 font-mono">{{ historicAvgDuration }} ms</span>
            <span class="text-[9px] text-slate-400 block font-medium">历史合并单例运算平均延迟</span>
          </div>
          <div class="absolute right-3 bottom-1.5 opacity-20 select-none">
            <BarChart3 class="w-14 h-14 text-slate-400" />
          </div>
        </div>
      </div>

      <!-- Left sidebar list and right details panel split layout -->
      <div class="grid grid-cols-1 xl:grid-cols-12 gap-6 items-start">
        <!-- Left indices list (5 cols) -->
        <section class="xl:col-span-5 bg-white border border-slate-100 p-5 rounded-2xl shadow-xs">
          <h3 class="font-bold text-slate-800 text-sm border-b border-slate-100 pb-3 mb-4 flex items-center gap-2 select-none">
            <FileSpreadsheet class="w-4.5 h-4.5 text-violet-500" />
            <span>历史评测报告索引清单</span>
          </h3>

          <div class="space-y-3 max-h-[460px] overflow-y-auto pr-1">
            <div
              v-for="rep in reports"
              :key="rep.id"
              @click="viewReportDetail(rep.id)"
              :class="[
                'p-4 border rounded-xl cursor-pointer transition-all space-y-2 select-none relative overflow-hidden',
                activeReportId === rep.id
                  ? 'bg-violet-50/50 border-violet-300 ring-2 ring-violet-500/10'
                  : 'bg-white border-slate-200 hover:bg-slate-50/80 hover:border-slate-300'
              ]"
            >
              <div class="flex items-center justify-between">
                <span class="font-mono text-[10px] font-bold text-violet-600 bg-violet-50 border border-violet-100 rounded-sm px-1.5 py-0.5">
                  REP-#{{ rep.id }}
                </span>
                <span class="text-[10px] font-mono text-slate-400 flex items-center gap-1">
                  <Calendar class="w-3.5 h-3.5" />
                  {{ rep.timestamp }}
                </span>
              </div>

              <div class="space-y-0.5">
                <h4 class="text-xs font-bold text-slate-700 truncate leading-relaxed">
                  项目归属: {{ rep.project_name || ('ID-' + rep.project_id) }}
                </h4>
                <p class="text-[10px] text-slate-400 font-mono truncate">BASE: {{ rep.base_url }}</p>
              </div>

              <div class="flex items-center justify-between pt-2 border-t border-slate-100 mt-2 text-[10px] font-semibold text-slate-400">
                <div>
                  通过率: 
                  <span :class="['font-bold', rep.pass_rate === 100 ? 'text-emerald-500' : 'text-violet-600']">
                    {{ rep.pass_rate.toFixed(1) }}%
                  </span>
                </div>
                <div>
                  用例: <span class="text-slate-600 font-bold font-mono">{{ rep.success_cases }}/{{ rep.total_cases }}</span>
                </div>
                <div>
                  耗时: <span class="text-slate-600 font-bold font-mono">{{ Math.round(rep.avg_response_time) }}ms</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- Right diagnosis report metrics and parameters (7 cols) -->
        <section class="xl:col-span-7 bg-white border border-slate-100 p-5 rounded-2xl shadow-xs min-h-[460px] flex flex-col justify-between overflow-hidden">
          <div v-if="isLoadingDetails" class="flex-grow flex items-center justify-center flex-col py-20 text-slate-400 space-y-2">
            <span class="animate-spin text-violet-600 font-bold text-xl">⏳</span>
            <span class="text-xs font-semibold">正在载入 SQLite 详细诊断明细...</span>
          </div>

          <div v-else-if="selectedReport" class="space-y-5 flex-grow flex flex-col justify-between">
            <!-- Summary stats card in layout -->
            <div class="border-b border-slate-100 pb-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 select-none">
              <div>
                <span class="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-widest block">当前选中报告明细</span>
                <h3 class="text-base font-extrabold text-slate-800 tracking-tight">
                  运行基地址: {{ selectedReport.summary.base_url }}
                </h3>
                <p class="text-[10px] text-slate-400 font-mono mt-0.5">
                  报告编号: REP-#{{ selectedReport.summary.id }} | 归属环境 ID: {{ selectedReport.summary.env_id || '默认' }}
                </p>
              </div>

              <!-- PassRate Ring Tag -->
              <div class="flex items-center gap-2">
                <div class="text-right">
                  <span class="text-[9px] font-bold text-slate-400 block">综合评测得分</span>
                  <span :class="['text-lg font-black font-mono', selectedReport.summary.pass_rate === 100 ? 'text-emerald-500' : 'text-violet-600']">
                    {{ selectedReport.summary.pass_rate.toFixed(1) }}%
                  </span>
                </div>
                <div :class="['p-2.5 rounded-xl border', selectedReport.summary.pass_rate === 100 ? 'bg-emerald-50 text-emerald-600 border-emerald-100' : 'bg-violet-50 text-violet-600 border-violet-100']">
                  <ShieldCheck v-if="selectedReport.summary.pass_rate === 100" class="w-5 h-5" />
                  <ShieldAlert v-else class="w-5 h-5" />
                </div>
              </div>
            </div>

            <!-- Dashboard Split Area: Left test list vs Right JSON details -->
            <div class="grid grid-cols-1 lg:grid-cols-12 gap-5 flex-grow items-stretch h-[450px] overflow-hidden">
              <!-- Left list case titles (40% width, lg 5 cols) -->
              <div class="lg:col-span-5 h-full overflow-y-auto space-y-2 pr-1.5 border-r border-slate-100">
                <span class="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-2 select-none">用例测试流水集</span>
                
                <div
                  v-for="res in selectedReport.results"
                  :key="res.id"
                  @click="selectedResult = res"
                  :class="[
                    'p-3 border rounded-xl cursor-pointer transition-all text-left space-y-1.5',
                    selectedResult && selectedResult.id === res.id
                      ? 'bg-violet-50/40 border-violet-200'
                      : 'bg-slate-50/50 border-transparent hover:border-slate-200'
                  ]"
                >
                  <div class="flex justify-between items-center select-none">
                    <span class="font-mono font-bold text-[9px] text-slate-500 bg-white ring-1 ring-slate-200 rounded px-1.5 py-0.5 shadow-2xs">
                      {{ res.case_id }}
                    </span>
                    <span
                      :class="[
                        'text-[9px] font-bold px-1.5 py-0.5 rounded border',
                        res.status === 'SUCCESS'
                          ? 'bg-emerald-50 text-emerald-600 border-emerald-100'
                          : 'bg-rose-50 text-rose-600 border-rose-100'
                      ]"
                    >
                      {{ res.status }}
                    </span>
                  </div>

                  <div class="text-xs font-bold text-slate-700 truncate">{{ res.api_name }}</div>
                  
                  <div class="text-[10px] font-mono text-slate-400 flex items-center justify-between mt-1">
                    <span class="truncate max-w-[120px] font-mono">{{ res.api_path }}</span>
                    <span class="text-amber-600 font-bold font-mono">{{ Math.round(res.response_time) }}ms</span>
                  </div>
                </div>
              </div>

              <!-- Right detail payload inspector (60% width, lg 7 cols) -->
              <div class="lg:col-span-7 h-full overflow-y-auto space-y-4 pl-1">
                <div v-if="selectedResult" class="space-y-4 text-xs">
                  <div class="border-b border-slate-100 pb-2 select-none">
                    <h4 class="font-bold text-violet-600 flex items-center gap-1">
                      <span>{{ selectedResult.case_id }}</span>
                      <ChevronRight class="w-3.5 h-3.5 text-slate-400" />
                      <span class="text-slate-800">{{ selectedResult.api_name }} 诊断底稿</span>
                    </h4>
                    <p class="text-[10px] font-mono text-slate-400 mt-0.5">{{ selectedResult.method }} {{ selectedResult.api_path }}</p>
                  </div>

                  <!-- Error Banner if failed -->
                  <div v-if="selectedResult.status !== 'SUCCESS'" class="p-3.5 bg-rose-50 border border-rose-200/50 rounded-xl text-rose-700 leading-relaxed font-semibold text-[11px]">
                    <span class="font-bold text-rose-800 block mb-1">❌ 断言校验失败详情:</span>
                    {{ selectedResult.error_message || '接口返回值匹配断言不通过/格式错误' }}
                  </div>

                  <!-- Req header and body JSON -->
                  <div class="space-y-2">
                    <span class="font-bold text-slate-700 block select-none">📬 请求细节 (Request details)</span>
                    <div class="bg-[#0b0f19] border border-slate-800 rounded-xl p-3 font-mono text-[10px] text-slate-100 space-y-3 shadow-inner">
                      <div>
                        <span class="text-indigo-400 font-bold">Headers:</span>
                        <pre class="whitespace-pre-wrap text-slate-200 mt-1 select-all font-mono">{{ safeJsonFormat(selectedResult.request_headers) }}</pre>
                      </div>
                      <div v-if="selectedResult.request_body">
                        <span class="text-indigo-400 font-bold">Body:</span>
                        <pre class="whitespace-pre-wrap text-emerald-400 mt-1 select-all font-mono">{{ safeJsonFormat(selectedResult.request_body) }}</pre>
                      </div>
                    </div>
                  </div>

                  <!-- Resp details JSON -->
                  <div class="space-y-2">
                    <span class="font-bold text-slate-700 block select-none">📬 响应细节 (Response details)</span>
                    <div class="bg-[#0b0f19] border border-slate-800 rounded-xl p-3 font-mono text-[10px] text-slate-100 space-y-3 shadow-inner">
                      <div class="flex items-center gap-1 select-none">
                        <span class="text-indigo-400 font-bold">HTTP Code:</span>
                        <span class="text-slate-100 font-black font-mono pl-1">{{ selectedResult.response_code }}</span>
                      </div>
                      <div>
                        <span class="text-indigo-400 font-bold">Response Headers:</span>
                        <pre class="whitespace-pre-wrap text-slate-200 mt-1 select-all font-mono">{{ safeJsonFormat(selectedResult.response_headers) }}</pre>
                      </div>
                      <div>
                        <span class="text-indigo-400 font-bold">Response Body:</span>
                        <pre class="whitespace-pre-wrap text-slate-100 mt-1 select-all font-mono">{{ safeJsonFormat(selectedResult.response_body) }}</pre>
                      </div>
                    </div>
                  </div>
                </div>

                <div v-else class="text-center py-20 text-slate-400 font-medium select-none flex items-center justify-center h-full">
                  请在左侧列表中点击单个用例查看诊断详情
                </div>
              </div>
            </div>
          </div>

          <div v-else class="text-center py-20 text-slate-400 font-semibold select-none flex items-center justify-center flex-grow">
            当前项目暂无任何测试历史报告。
          </div>
        </section>
      </div>
    </div>
  </div>
</template>
