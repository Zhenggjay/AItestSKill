<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { Search, ShieldAlert, PlayCircle, Loader2, Table, ShieldAlert as AlertIcon, FileJson, Code } from 'lucide-vue-next';

interface Props {
  projectId: number | null;
  domainUrl: string;
  token: string;
}

const props = defineProps<Props>();

// Specs data
const endpoints = ref<any[]>([]);
const activeEndpointIndex = ref<number>(0);
const searchQuery = ref('');
const currentPage = ref(1);

// Playground Request details
const editableBody = ref('');
const isRequesting = ref(false);
const responseLog = ref('等待请求执行 ...');
const successStatus = ref<boolean | null>(null);
const responseTime = ref<number | null>(null);

const activeEndpoint = computed(() => {
  if (endpoints.value.length === 0) return null;
  return endpoints.value[activeEndpointIndex.value] || endpoints.value[0];
});

// Fetch APIs specs for selected project
async function fetchSpecs() {
  if (props.projectId === null) return;
  try {
    const res = await fetch(`/api/specs?project_id=${props.projectId}`);
    const json = await res.json();
    if (json.success) {
      endpoints.value = json.data;
      activeEndpointIndex.value = 0;
      currentPage.value = 1;
    } else {
      endpoints.value = [];
    }
  } catch (err) {
    console.error('Failed to fetch api specs', err);
    endpoints.value = [];
  }
}

// Watchers
watch(() => props.projectId, () => {
  fetchSpecs();
});

watch(activeEndpoint, (newVal) => {
  if (newVal) {
    const example = newVal.req_example || newVal.reqExample || newVal.body_template || newVal.bodyTemplate;
    if (example) {
      if (typeof example === 'object') {
        editableBody.value = JSON.stringify(example, null, 2);
      } else {
        editableBody.value = example;
      }
    } else {
      editableBody.value = '';
    }
    responseLog.value = '等待请求执行 ...';
    successStatus.value = null;
    responseTime.value = null;
  } else {
    editableBody.value = '';
  }
}, { immediate: true });

onMounted(() => {
  fetchSpecs();
});

// Search filter
const filteredEndpoints = computed(() => {
  if (!searchQuery.value.trim()) return endpoints.value;
  const query = searchQuery.value.toLowerCase();
  return endpoints.value.filter(
    (e) =>
      (e.api_name || e.name || '').toLowerCase().includes(query) ||
      (e.path || '').toLowerCase().includes(query)
  );
});

// Front-end Pagination
const itemsPerPage = 6;
const totalPages = computed(() => Math.ceil(filteredEndpoints.value.length / itemsPerPage) || 1);
const paginatedEndpoints = computed(() => {
  const start = (currentPage.value - 1) * itemsPerPage;
  return filteredEndpoints.value.slice(start, start + itemsPerPage);
});

// Auto-fallback reset page on searching
watch(searchQuery, () => {
  currentPage.value = 1;
});

// Select API endpoint
function selectEndpoint(api: any) {
  const originalIdx = endpoints.value.findIndex(e => e.path === api.path && e.method === api.method);
  if (originalIdx !== -1) {
    activeEndpointIndex.value = originalIdx;
  }
}

// Execute single request via FastAPI backend playground
async function handleSendRequest() {
  if (!activeEndpoint.value) return;
  
  isRequesting.value = true;
  responseLog.value = '⚡ 正在向网关通道发送请求包...';
  successStatus.value = null;
  responseTime.value = null;

  try {
    // Validate JSON structure
    let parsedBody = {};
    if (editableBody.value.trim()) {
      parsedBody = JSON.parse(editableBody.value);
    }
    
    // Create case object for FastAPI single run
    // Mapping Vue data schema into FastAPI model
    const testCase = {
      api_name: activeEndpoint.value.api_name || activeEndpoint.value.name,
      method: activeEndpoint.value.method,
      api_path: activeEndpoint.value.path,
      headers: (activeEndpoint.value.headers || []).reduce((acc: any, curr: any) => {
        acc[curr.name] = curr.value || '';
        return acc;
      }, {}),
      body_template: editableBody.value,
      case_type: 'happy_path',
      expected_code: 200,
      assertions: [
        {"type": "status_code", "expect": 200}
      ]
    };

    const startTime = Date.now();
    const res = await fetch('/api/run-case', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        case: testCase,
        base_url: props.domainUrl,
        token: props.token
      })
    });

    const json = await res.json();
    responseTime.value = Date.now() - startTime;

    if (res.ok && json.success) {
      const data = json.data;
      successStatus.value = data.status === 'SUCCESS';
      responseLog.value = JSON.stringify(data.response_body, null, 2);
    } else {
      successStatus.value = false;
      responseLog.value = `请求异常:\n${JSON.stringify(json, null, 2)}`;
    }
  } catch (err: any) {
    successStatus.value = false;
    responseLog.value = `客户端异常:\n[报错详情]: ${err.message}\n\n*请确保请求 BODY 满足标准的 JSON 规范*`;
  } finally {
    isRequesting.value = false;
  }
}
</script>

<template>
  <div class="grid grid-cols-1 xl:grid-cols-12 gap-6 items-start text-slate-800">
    <!-- LEFT COLUMN - Endpoints Index list (4 cols) -->
    <section class="xl:col-span-4 bg-white border border-slate-100 p-5 rounded-2xl shadow-xs space-y-4">
      <!-- Search header widget -->
      <div class="relative">
        <span class="absolute left-3 top-2.5 text-slate-400">
          <Search class="w-4 h-4" />
        </span>
        <input
          type="text"
          v-model="searchQuery"
          placeholder="搜索接口名称或路径..."
          class="w-full pl-9 pr-4 py-2 text-xs border border-slate-200/80 rounded-xl focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 outline-none tracking-normal text-slate-700 bg-slate-50/50"
        />
      </div>

      <!-- Endpoints Checklist List -->
      <div class="space-y-2 max-h-[480px] overflow-y-auto pr-1">
        <div
          v-for="item in paginatedEndpoints"
          :key="item.path + item.method"
          @click="selectEndpoint(item)"
          :class="[
            'p-3.5 border rounded-xl cursor-pointer transition-all space-y-1.5 select-none relative overflow-hidden',
            activeEndpoint && activeEndpoint.path === item.path && activeEndpoint.method === item.method
              ? 'bg-violet-50/50 border-violet-300 ring-2 ring-violet-500/10'
              : 'bg-white border-slate-200 hover:bg-slate-50/70 hover:border-slate-300'
          ]"
        >
          <div class="flex items-center justify-between gap-2">
            <span
              :class="[
                'px-1.5 py-0.5 text-[9px] font-bold border rounded-sm',
                item.method === 'GET' ? 'bg-emerald-50 text-emerald-600 border-emerald-100' :
                item.method === 'POST' ? 'bg-blue-50 text-blue-600 border-blue-100' :
                item.method === 'PUT' ? 'bg-amber-50 text-amber-600 border-amber-100' :
                'bg-rose-50 text-rose-600 border-rose-100'
              ]"
            >
              {{ item.method }}
            </span>
            <span class="font-mono text-[9px] font-semibold text-slate-400">
              API-KEY
            </span>
          </div>

          <h4
            :class="[
              'text-xs font-bold truncate leading-snug',
              activeEndpoint && activeEndpoint.path === item.path && activeEndpoint.method === item.method
                ? 'text-violet-700'
                : 'text-slate-700'
            ]"
          >
            {{ item.api_name || item.name }}
          </h4>

          <p class="font-mono text-[10px] text-slate-400 truncate">
            {{ item.path }}
          </p>
        </div>

        <div v-if="filteredEndpoints.length === 0" class="text-center py-10 text-slate-400 space-y-2">
          <ShieldAlert class="w-8 h-8 text-slate-300 mx-auto" />
          <p class="text-xs font-medium">未能过滤出任何符合条件的接口</p>
        </div>
      </div>

      <!-- Pagination bar -->
      <div v-if="totalPages > 1" class="flex items-center justify-center gap-1 text-slate-500 text-xs font-medium pt-2 border-t border-slate-100">
        <button
          @click="currentPage = Math.max(1, currentPage - 1)"
          :disabled="currentPage === 1"
          class="p-1 px-2.5 border border-slate-200 rounded-md hover:bg-slate-50 cursor-pointer disabled:opacity-40 disabled:pointer-events-none"
        >
          &lt;
        </button>
        
        <button
          v-for="page in totalPages"
          :key="page"
          @click="currentPage = page"
          :class="[
            'p-1 px-2.5 border rounded-md cursor-pointer transition-all',
            currentPage === page
              ? 'bg-violet-600 text-white border-violet-600 font-bold shadow-xs'
              : 'border-slate-200 hover:bg-slate-50 text-slate-600'
          ]"
        >
          {{ page }}
        </button>

        <button
          @click="currentPage = Math.min(totalPages, currentPage + 1)"
          :disabled="currentPage === totalPages"
          class="p-1 px-2.5 border border-slate-200 rounded-md hover:bg-slate-50 cursor-pointer disabled:opacity-40 disabled:pointer-events-none"
        >
          &gt;
        </button>
      </div>
    </section>

    <!-- RIGHT COLUMN - API Playground Sandbox Console (8 cols) -->
    <section class="xl:col-span-8 bg-white border border-slate-100 p-5 rounded-2xl shadow-xs space-y-5">
      <div v-if="activeEndpoint" class="space-y-5">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
          <div class="flex items-center gap-3">
            <span
              :class="[
                'px-2.5 py-1 text-xs font-black border rounded-md',
                activeEndpoint.method === 'GET' ? 'bg-emerald-50 text-emerald-600 border-emerald-100' :
                activeEndpoint.method === 'POST' ? 'bg-blue-50 text-blue-600 border-blue-100' :
                activeEndpoint.method === 'PUT' ? 'bg-amber-50 text-amber-600 border-amber-100' :
                'bg-rose-50 text-rose-600 border-rose-100'
              ]"
            >
              {{ activeEndpoint.method }}
            </span>
            <div>
              <h3 class="font-bold text-slate-800 text-sm tracking-tight flex items-center gap-1.5">
                <span>{{ activeEndpoint.api_name || activeEndpoint.name }}</span>
              </h3>
              <p class="text-slate-400 font-mono text-[11px] mt-0.5">{{ activeEndpoint.path }}</p>
            </div>
          </div>

          <button
            @click="handleSendRequest"
            :disabled="isRequesting"
            class="px-4 py-2 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 text-white rounded-xl shadow-md hover:shadow-lg transition-all text-xs font-bold flex items-center gap-2 cursor-pointer disabled:opacity-50 disabled:pointer-events-none"
          >
            <span v-if="isRequesting" class="flex items-center gap-1">
              <Loader2 class="w-3.5 h-3.5 animate-spin" />
              <span>正在执行...</span>
            </span>
            <span v-else class="flex items-center gap-1">
              <PlayCircle class="w-3.5 h-3.5 fill-current" />
              <span>发送真实请求</span>
            </span>
          </button>
        </div>

        <!-- Split subgrid: table vs editor -->
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <!-- Params Schemas Column (7 cols or 12 cols depending on method) -->
          <div :class="[
            activeEndpoint.method === 'GET' || activeEndpoint.method === 'DELETE'
              ? 'lg:col-span-12'
              : 'lg:col-span-7',
            'space-y-4'
          ]">
            <!-- Req Params table -->
            <div class="space-y-2">
              <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest flex items-center gap-1.5 select-none">
                <Table class="w-3.5 h-3.5 text-violet-500" />
                <span>请求参数 (Parameters Schema)</span>
              </span>

              <div class="border border-slate-100 rounded-xl overflow-hidden shadow-xs">
                <table class="w-full text-left border-collapse text-xs text-slate-600">
                  <thead>
                    <tr class="bg-slate-50 border-b border-slate-100 text-slate-400 font-semibold">
                      <th class="p-2.5 pl-3 w-1/4">字段名</th>
                      <th class="p-2.5 w-20">类型</th>
                      <th class="p-2.5 w-16 text-center">必填</th>
                      <th class="p-2.5 pr-3">说明</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-slate-100 font-medium bg-white">
                    <tr v-for="p in activeEndpoint.params" :key="p.name" class="hover:bg-slate-50/50">
                      <td class="p-2.5 pl-3 font-mono font-bold text-slate-700 break-all">{{ p.name }}</td>
                      <td class="p-2.5 font-mono text-slate-400 text-[11px]">{{ p.type }}</td>
                      <td class="p-2.5 text-center">
                        <span v-if="p.required" class="text-rose-500 font-bold">是</span>
                        <span v-else class="text-slate-400">否</span>
                      </td>
                      <td class="p-2.5 pr-3 text-slate-500">{{ p.desc || p.description }}</td>
                    </tr>
                    <tr v-if="!activeEndpoint.params || activeEndpoint.params.length === 0">
                      <td colspan="4" class="p-4 text-center text-slate-400 bg-slate-50/30">当前请求不需要参数 schema</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- Request headers contract table -->
            <div class="space-y-2">
              <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest flex items-center gap-1.5 select-none">
                <AlertIcon class="w-3.5 h-3.5 text-violet-500" />
                <span>请求 HEADERS 契约</span>
              </span>

              <div class="border border-slate-100 rounded-xl overflow-hidden shadow-xs">
                <table class="w-full text-left border-collapse text-xs text-slate-600">
                  <thead>
                    <tr class="bg-slate-50 border-b border-slate-100 text-slate-400 font-semibold">
                      <th class="p-2.5 pl-3 w-1/3">头部名称</th>
                      <th class="p-2.5 w-20">类型</th>
                      <th class="p-2.5 pr-3">描述</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-slate-100 font-medium bg-white">
                    <tr v-for="h in activeEndpoint.headers" :key="h.name" class="hover:bg-slate-50/50">
                      <td class="p-2.5 pl-3 font-mono font-bold text-slate-700">{{ h.name }}</td>
                      <td class="p-2.5 font-mono text-slate-400 text-[11px]">{{ h.type }}</td>
                      <td class="p-2.5 pr-3 text-slate-500">{{ h.desc || h.description }}</td>
                    </tr>
                    <tr v-if="!activeEndpoint.headers || activeEndpoint.headers.length === 0">
                      <td colspan="3" class="p-4 text-center text-slate-400 bg-slate-50/30">标准 application/json 默认头部</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <!-- JSON Body text editor (5 cols) -->
          <div v-if="activeEndpoint.method !== 'GET' && activeEndpoint.method !== 'DELETE'" class="lg:col-span-5 flex flex-col space-y-2">
            <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest flex items-center gap-1.5 select-none">
              <FileJson class="w-3.5 h-3.5 text-violet-500" />
              <span>请求 BODY (JSON)</span>
            </span>

            <textarea
              v-model="editableBody"
              class="w-full flex-grow min-h-[220px] bg-[#0e131f] text-emerald-400 p-4 rounded-xl font-mono text-[11px] leading-relaxed border border-slate-800 focus:outline-none focus:ring-2 focus:ring-violet-500/50 resize-y"
              style="tab-size: 2"
            />
          </div>
        </div>

        <!-- Realtime response logs -->
        <div class="space-y-2">
          <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest flex items-center gap-1.5 select-none">
            <Code class="w-3.5 h-3.5 text-violet-500" />
            <span>实际执行响应 (Execution Response)</span>
          </span>

          <div class="bg-[#0b0f19] text-slate-100 border border-slate-800 p-4 rounded-2xl font-mono text-[11px] leading-relaxed relative min-h-[160px] max-h-[300px] overflow-y-auto">
            <!-- Pulsing Badge status -->
            <div v-if="successStatus !== null" class="absolute top-3 right-4 flex items-center gap-1.5 text-[10px] font-semibold bg-[#121826] px-2 py-1 rounded-md border border-[#1b2336] select-none">
              <span :class="['w-2 h-2 rounded-full', successStatus ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500']" />
              <span :class="[successStatus ? 'text-emerald-400' : 'text-rose-400']">
                {{ successStatus ? 'HTTP 200 OK' : 'EXEC_ERROR' }}
              </span>
              <span v-if="responseTime !== null" class="text-slate-500 text-[9px] font-mono border-l border-slate-800 pl-1.5 ml-1">
                {{ responseTime }}ms
              </span>
            </div>

            <pre class="whitespace-pre-wrap">{{ responseLog }}</pre>
          </div>
        </div>
      </div>

      <div v-else class="text-center py-20 text-slate-400 space-y-4">
        <AlertIcon class="w-12 h-12 text-slate-200 mx-auto" />
        <p class="text-sm font-semibold">该项目暂未加载出任何有效的 API 接口规约</p>
        <p class="text-xs text-slate-400">请在项目管理中绑定有效的 .md 接口文件路径。</p>
      </div>
    </section>
  </div>
</template>
