<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { Layers, CalendarClock, Code } from 'lucide-vue-next';
import Header from './components/Header.vue';
import CaseManager from './components/CaseManager.vue';
import ApiContract from './components/ApiContract.vue';
import HistoryReports from './components/HistoryReports.vue';

// App tabs
type TabType = 'case_run' | 'api_list' | 'history';
const activeTab = ref<TabType>('case_run');

// State definitions
const projects = ref<any[]>([]);
const envs = ref<any[]>([]);
const activeProjectId = ref<number | null>(null);
const activeEnvId = ref<number | null>(null);

const activeProjectName = ref('');
const activeEnvironmentName = ref('');
const domainUrl = ref('');
const token = ref('');

// Fetch list of projects from DB
async function fetchProjects() {
  try {
    const res = await fetch('/api/projects');
    const json = await res.json();
    if (json.success) {
      projects.value = json.data;
      if (projects.value.length > 0 && activeProjectId.value === null) {
        activeProjectId.value = projects.value[0].id;
      }
    }
  } catch (err) {
    console.error('Failed to fetch projects', err);
  }
}

// Fetch list of envs from DB
async function fetchEnvs() {
  try {
    const res = await fetch('/api/envs');
    const json = await res.json();
    if (json.success) {
      envs.value = json.data;
      if (envs.value.length > 0 && activeEnvId.value === null) {
        activeEnvId.value = envs.value[0].id;
      }
    }
  } catch (err) {
    console.error('Failed to fetch environments', err);
  }
}

// Monitor active project ID changes
watch(activeProjectId, (newId) => {
  if (newId !== null) {
    const proj = projects.value.find(p => p.id === newId);
    if (proj) {
      activeProjectName.value = proj.name;
      token.value = proj.token || '';
    }
  }
});

// Monitor active environment ID changes
watch(activeEnvId, (newId) => {
  if (newId !== null) {
    const env = envs.value.find(e => e.id === newId);
    if (env) {
      activeEnvironmentName.value = env.name;
      domainUrl.value = env.base_url;
    }
  }
});

onMounted(() => {
  fetchProjects();
  fetchEnvs();
});

// Reload callback after saving projects or environments
function handleReloadProjects(selectedId?: number) {
  fetchProjects().then(() => {
    if (selectedId !== undefined) {
      activeProjectId.value = selectedId;
    }
  });
}

function handleReloadEnvs(selectedId?: number) {
  fetchEnvs().then(() => {
    if (selectedId !== undefined) {
      activeEnvId.value = selectedId;
    }
  });
}
</script>

<template>
  <main class="min-h-screen bg-slate-50/70 py-6 px-4 md:px-8 font-sans antialiased text-slate-800">
    <div class="max-w-[1600px] mx-auto space-y-6">
      <!-- Unified Header Control Panel -->
      <Header
        :projects="projects"
        :envs="envs"
        v-model:activeProjectId="activeProjectId"
        v-model:activeEnvId="activeEnvId"
        v-model:domainUrl="domainUrl"
        v-model:token="token"
        @reload-projects="handleReloadProjects"
        @reload-envs="handleReloadEnvs"
      />

      <!-- Tab Selectors -->
      <div class="border-b border-slate-200 flex gap-1 bg-white p-1 rounded-xl shadow-xs max-w-md">
        <!-- TAB 1: 接口清单规约 -->
        <button
          id="tab-api-list"
          @click="activeTab = 'api_list'"
          :class="[
            'flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs font-semibold cursor-pointer transition-all',
            activeTab === 'api_list'
              ? 'bg-violet-600 text-white shadow-sm font-bold'
              : 'text-slate-500 hover:text-slate-800 hover:bg-slate-50'
          ]"
        >
          <Code class="w-4 h-4" />
          <span>接口清单规约</span>
        </button>

        <!-- TAB 2: 用例执行管理 -->
        <button
          id="tab-case-run"
          @click="activeTab = 'case_run'"
          :class="[
            'flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs font-semibold cursor-pointer transition-all',
            activeTab === 'case_run'
              ? 'bg-violet-600 text-white shadow-sm font-bold'
              : 'text-slate-500 hover:text-slate-800 hover:bg-slate-50'
          ]"
        >
          <Layers class="w-4 h-4" />
          <span>用例执行管理</span>
        </button>

        <!-- TAB 3: 历史报告 -->
        <button
          id="tab-reports"
          @click="activeTab = 'history'"
          :class="[
            'flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs font-semibold cursor-pointer transition-all',
            activeTab === 'history'
              ? 'bg-violet-600 text-white shadow-sm font-bold'
              : 'text-slate-500 hover:text-slate-800 hover:bg-slate-50'
          ]"
        >
          <CalendarClock class="w-4 h-4" />
          <span>历史报告</span>
        </button>
      </div>

      <!-- Tab Viewports -->
      <div class="mt-6">
        <div v-if="activeTab === 'api_list'">
          <ApiContract
            :projectId="activeProjectId"
            :domainUrl="domainUrl"
            :token="token"
          />
        </div>

        <div v-if="activeTab === 'case_run'">
          <CaseManager
            :projectId="activeProjectId"
            :domainUrl="domainUrl"
            :token="token"
            :projectName="activeProjectName"
            :environmentName="activeEnvironmentName"
            :envId="activeEnvId"
            @run-complete="activeTab = 'history'"
          />
        </div>

        <div v-if="activeTab === 'history'">
          <HistoryReports
            :projectId="activeProjectId"
          />
        </div>
      </div>
    </div>
  </main>
</template>

<style>
/* Custom styled styling to match the original designs */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: rgba(148, 163, 184, 0.05);
}
::-webkit-scrollbar-thumb {
  background: rgba(124, 58, 237, 0.2);
  border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(124, 58, 237, 0.4);
}
</style>
