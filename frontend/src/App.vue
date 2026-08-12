<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from './api'

const nav = ['Dashboard', 'New Case', 'Case Detail', 'Evidence', 'Reviews', 'Work Orders', 'Video Screening', 'System Status']
const page = ref('Dashboard')
const nodes = ['N1', 'N2', 'N3']
const surfaces = ['front', 'left', 'right', 'top']
const surfaceNames = { front: '正面', left: '左侧', right: '右侧', top: '顶部' }
const files = reactive(Object.fromEntries(nodes.map(n => [n, Object.fromEntries(surfaces.map(s => [s, null]))])))
const previews = reactive(Object.fromEntries(nodes.map(n => [n, Object.fromEntries(surfaces.map(s => [s, '']))])))
const mode = ref('multi')
const caseName = ref('比赛现场匿名多表面演示')
const caseId = ref('')
const currentCase = ref(null)
const result = ref(null)
const reviews = ref([])
const orders = ref([])
const dashboard = ref(null)
const trends = ref(null)
const health = ref(null)
const model = ref(null)
const warmup = ref(null)
const message = ref('系统准备中')
const busy = ref(false)
const logisticsFile = ref(null)
const logisticsFormat = ref('json')
const videoFile = ref(null)
const videoResult = ref(null)

const reviewForm = reactive({ node_from: 'N1', node_to: 'N2', surface: 'left', review_class: 'D05', review_status: 'CONFIRMED', reviewer_alias: 'MEMBER-C', review_note: '', supersedes_review_id: null })
const orderForm = reactive({ title: '首次异常区间人工复核', assigned_alias: 'MEMBER-C', actor_alias: 'DEMO-OPERATOR', note: '比赛演示工单' })
const eventForm = reactive({ event_type: 'STATE_CHANGE', actor_alias: 'MEMBER-C', new_state: 'IN_REVIEW', note: '' })

const shownSurfaces = computed(() => mode.value === 'simple' ? ['front'] : surfaces)
const ready = computed(() => nodes.every(n => shownSurfaces.value.some(s => files[n][s])))

onMounted(refreshSystem)

async function refreshSystem() {
  try {
    [health.value, model.value, warmup.value, dashboard.value, trends.value] = await Promise.all([
      api.health(), api.modelInfo(), api.warmup(), api.dashboardSummary(), api.dashboardTrends(),
    ])
    message.value = 'Competition RC v1.0 已就绪'
  } catch (error) { message.value = error.message }
}

async function selectPage(name) {
  page.value = name
  if (name === 'Dashboard') await refreshDashboard()
  if (caseId.value && ['Case Detail', 'Evidence', 'Reviews', 'Work Orders'].includes(name)) await refreshCase()
}

async function refreshDashboard() {
  try { [dashboard.value, trends.value] = await Promise.all([api.dashboardSummary(), api.dashboardTrends()]) } catch (error) { message.value = error.message }
}

async function refreshCase() {
  if (!caseId.value) return
  try {
    [currentCase.value, reviews.value, orders.value] = await Promise.all([
      api.getCase(caseId.value), api.reviews(caseId.value).then(x => x.reviews), api.workOrders(caseId.value).then(x => x.work_orders),
    ])
  } catch (error) { message.value = error.message }
}

function chooseImage(node, surface, event) {
  const file = event.target.files?.[0]; if (!file) return
  files[node][surface] = file
  if (previews[node][surface]) URL.revokeObjectURL(previews[node][surface])
  previews[node][surface] = URL.createObjectURL(file)
}

async function runAnalysis() {
  if (!ready.value) return
  busy.value = true
  try {
    const created = await api.createCase(caseName.value); caseId.value = created.case_id
    for (const node of nodes) for (const surface of shownSurfaces.value) if (files[node][surface]) await api.uploadNode(caseId.value, node, surface, files[node][surface])
    result.value = await api.analyze(caseId.value)
    reviewForm.surface = result.value.analysis.trigger_surfaces?.[0]?.surface || 'front'
    if (result.value.analysis.first_abnormal_interval) [reviewForm.node_from, reviewForm.node_to] = result.value.analysis.first_abnormal_interval.split('_TO_')
    await refreshCase(); await refreshDashboard(); page.value = 'Evidence'; message.value = '分析完成，证据与风险规则结果已写入 SQLite'
  } catch (error) { message.value = error.message } finally { busy.value = false }
}

async function submitReview() {
  try { await api.createReview(caseId.value, { ...reviewForm }); await refreshCase(); result.value = await api.getCase(caseId.value).then(x => ({ analysis: x.analysis?.result, risk: x.risk?.result })); message.value = '人工复核事件已追加，机器证据未覆盖' } catch (error) { message.value = error.message }
}

async function importTimeline() {
  if (!logisticsFile.value || !caseId.value) return
  try { await api.importLogistics(caseId.value, logisticsFormat.value, logisticsFile.value); await refreshCase(); message.value = '匿名结构化物流节点已导入' } catch (error) { message.value = error.message }
}

async function createOrder() {
  try { await api.createWorkOrder(caseId.value, { ...orderForm }); await refreshCase(); message.value = '工单已创建：OPEN' } catch (error) { message.value = error.message }
}

async function addOrderEvent(id) {
  try { await api.workOrderEvent(id, { ...eventForm }); await refreshCase(); message.value = '工单事件已追加' } catch (error) { message.value = error.message }
}

async function analyzeVideo() {
  if (!videoFile.value) return
  busy.value = true
  try { videoResult.value = await api.analyzeVideo(videoFile.value); message.value = 'VIDEO_DAMAGE_KEYFRAME_SCREENING 完成' } catch (error) { message.value = error.message } finally { busy.value = false }
}

const risk = computed(() => result.value?.risk || currentCase.value?.risk?.result)
const analysis = computed(() => result.value?.analysis || currentCase.value?.analysis?.result)
</script>

<template>
  <div class="shell">
    <aside><div class="brand"><b>件证</b><span>Competition RC v1.0</span></div>
      <nav><button v-for="item in nav" :key="item" :class="{ active: page === item }" @click="selectPage(item)">{{ item }}</button></nav>
      <div class="boundary">AI 自动：D02 / D03<br>开放集 + 人工：D01 / D04 / D05<br>法律责任：不支持自动认定</div>
    </aside>
    <main>
      <header><div><p class="eyebrow">CONTINUOUS APPEARANCE EVIDENCE</p><h1>{{ page }}</h1></div><div class="system-chip"><b>{{ health?.status || 'connecting' }}</b><span>{{ health?.pipeline_version }}</span><small>{{ model?.model_version }}</small></div></header>
      <div class="notice">{{ message }}</div>

      <section v-if="page === 'Dashboard'" class="page">
        <div class="metrics">
          <article><span>案例</span><b>{{ dashboard?.case_count ?? '—' }}</b></article><article><span>异常案例</span><b>{{ dashboard?.abnormal_case_count ?? '—' }}</b></article>
          <article><span>待复核</span><b>{{ dashboard?.review_pending_count ?? '—' }}</b></article><article><span>工单</span><b>{{ dashboard?.work_order_count ?? '—' }}</b></article>
          <article><span>已解决工单</span><b>{{ dashboard?.resolved_work_order_count ?? '—' }}</b></article><article><span>平均分析耗时</span><b>{{ dashboard?.average_analyze_time_ms ?? '—' }} ms</b></article>
        </div>
        <div class="cards two"><article class="panel"><h2>风险等级分布</h2><div v-for="(value,key) in dashboard?.risk_level_distribution" :key="key" class="bar"><span>{{ key }}</span><i :style="{width: `${Math.min(100,value*16)}%`}"></i><b>{{ value }}</b></div><p>来源：{{ dashboard?.source }}</p></article>
          <article class="panel"><h2>最近趋势</h2><div class="trend"><span v-for="item in trends?.cases" :key="item.date" :title="item.date" :style="{height:`${20+item.count*12}px`}">{{ item.count }}</span></div><p>按 SQLite created_at 日聚合</p></article></div>
      </section>

      <section v-if="page === 'New Case'" class="page panel">
        <div class="row"><label>匿名案例名称<input v-model="caseName"></label><div class="seg"><button :class="{on:mode==='simple'}" @click="mode='simple'">Simple</button><button :class="{on:mode==='multi'}" @click="mode='multi'">Multi-Surface</button></div><button class="primary" :disabled="!ready || busy" @click="runAnalysis">{{ busy ? '分析中…' : '创建并分析' }}</button></div>
        <div class="matrix"><div class="matrix-head">Node × Surface</div><div v-for="node in nodes" :key="node" class="matrix-row"><b>{{ node }}</b><label v-for="surface in shownSurfaces" :key="surface" class="drop"><img v-if="previews[node][surface]" :src="previews[node][surface]"><span v-else>{{ surfaceNames[surface] }}<small>{{ surface }}</small></span><input type="file" accept="image/jpeg,image/png,image/webp" @change="chooseImage(node,surface,$event)"></label></div></div>
      </section>

      <section v-if="page === 'Case Detail'" class="page cards two"><article class="panel"><h2>当前案例</h2><dl><dt>Case ID</dt><dd>{{ caseId || '尚未选择' }}</dd><dt>状态</dt><dd>{{ currentCase?.status }}</dd><dt>采集数</dt><dd>{{ currentCase?.nodes?.length || 0 }}</dd><dt>Pipeline</dt><dd>{{ currentCase?.pipeline_version }}</dd></dl></article>
        <article class="panel"><h2>结构化物流时间线</h2><div class="row compact"><select v-model="logisticsFormat"><option>json</option><option>csv</option></select><input type="file" accept=".json,.csv" @change="logisticsFile=$event.target.files?.[0]"><button @click="importTimeline">导入</button></div><ol><li v-for="n in currentCase?.logistics_nodes" :key="n.node_id"><b>{{ n.node_id }} · {{ n.node_type }}</b> {{ n.event_time }} / {{ n.location_alias }}</li></ol></article></section>

      <section v-if="page === 'Evidence'" class="page cards two"><article class="panel verdict"><span>首次异常区间</span><b>{{ analysis?.first_abnormal_interval || analysis?.conclusion_code || '尚未分析' }}</b><p>技术证据等级 {{ analysis?.evidence_level || '—' }}</p><ul><li v-for="item in analysis?.trigger_surfaces" :key="item.surface">{{ item.surface }} · {{ item.reason }}</li></ul><a v-if="caseId" :href="api.reportUrl(caseId)" target="_blank">打开 Evidence Report v1.0</a></article>
        <article class="panel risk"><span>规则风险辅助分</span><b>{{ risk?.risk_score ?? '—' }}</b><strong>{{ risk?.risk_level }}</strong><p>不是法律责任结论 · 人工复核 {{ risk?.manual_review_required ? '必需' : '建议' }}</p><div v-for="part in risk?.score_breakdown" :key="part.component" class="score-line"><span>{{ part.component }}</span><b>{{ part.points }}/{{ part.max_points }}</b></div></article></section>

      <section v-if="page === 'Reviews'" class="page panel"><h2>人工复核（append-only）</h2><p>D01/D04/D05 是开放集变化后的人工类别，不是 AI 自动分类。</p><div class="form-grid"><label>起点<input v-model="reviewForm.node_from"></label><label>终点<input v-model="reviewForm.node_to"></label><label>表面<select v-model="reviewForm.surface"><option v-for="s in surfaces" :key="s">{{ s }}</option></select></label><label>类别<select v-model="reviewForm.review_class"><option>D01</option><option>D02</option><option>D03</option><option>D04</option><option>D05</option><option>NORMAL_VARIATION</option><option>UNSURE</option></select></label><label>状态<select v-model="reviewForm.review_status"><option>CONFIRMED</option><option>REJECTED</option><option>UNSURE</option></select></label><label>匿名复核人<select v-model="reviewForm.reviewer_alias"><option>MEMBER-A</option><option>MEMBER-B</option><option>MEMBER-C</option><option>DEMO-REVIEWER</option></select></label></div><button class="primary" :disabled="!caseId" @click="submitReview">追加复核事件</button><div class="event" v-for="r in reviews" :key="r.review_id"><b>{{ r.review_class }} / {{ r.review_status }}</b><span>{{ r.node_from }}→{{ r.node_to }}.{{ r.surface }} · {{ r.reviewer_alias }}</span><code>{{ r.review_payload_sha256 }}</code></div></section>

      <section v-if="page === 'Work Orders'" class="page panel"><h2>工单闭环</h2><div class="row"><input v-model="orderForm.title"><select v-model="orderForm.assigned_alias"><option>MEMBER-A</option><option>MEMBER-B</option><option>MEMBER-C</option><option>DEMO-OPERATOR</option></select><button class="primary" :disabled="!caseId" @click="createOrder">创建 OPEN 工单</button></div><article v-for="order in orders" :key="order.work_order_id" class="work-order"><div><b>{{ order.title }}</b><span>{{ order.current_state }} · {{ order.assigned_alias }}</span></div><div class="row compact"><select v-model="eventForm.event_type"><option>STATE_CHANGE</option><option>NOTE</option><option>EVIDENCE_REQUEST</option><option>ASSIGN</option><option>RESOLVE</option></select><select v-model="eventForm.new_state"><option>IN_REVIEW</option><option>NEEDS_MORE_EVIDENCE</option><option>CONFIRMED</option><option>REJECTED</option><option>RESOLVED</option></select><input v-model="eventForm.note" placeholder="备注"><button @click="addOrderEvent(order.work_order_id)">追加事件</button></div><ol><li v-for="e in order.events" :key="e.event_id">{{ e.event_type }} · {{ e.previous_state || '—' }}→{{ e.current_state }} · {{ e.actor_alias }}</li></ol></article></section>

      <section v-if="page === 'Video Screening'" class="page panel"><h2>VIDEO_DAMAGE_KEYFRAME_SCREENING</h2><p>仅筛查 MP4 中 D02/D03 损伤关键帧，不是抛扔、违规动作或行为识别。</p><div class="row"><input type="file" accept="video/mp4" @change="videoFile=$event.target.files?.[0]"><button class="primary" :disabled="!videoFile || busy" @click="analyzeVideo">筛查视频</button></div><div v-if="videoResult" class="metrics"><article><span>采样帧</span><b>{{ videoResult.sampled_frame_count }}</b></article><article><span>异常帧</span><b>{{ videoResult.abnormal_frame_count }}</b></article><article><span>时长</span><b>{{ videoResult.video_metadata.duration_seconds }}s</b></article></div><div class="keyframes"><figure v-for="k in videoResult?.top_abnormal_keyframes" :key="k.filename"><img :src="api.assetUrl(k.url)"><figcaption>#{{ k.rank }} · {{ k.timestamp_seconds }}s · {{ k.detection_count }} detections</figcaption></figure></div></section>

      <section v-if="page === 'System Status'" class="page cards two"><article class="panel"><h2>运行状态</h2><pre>{{ JSON.stringify(health, null, 2) }}</pre></article><article class="panel"><h2>活动模型</h2><pre>{{ JSON.stringify(model, null, 2) }}</pre><p>Warmup：{{ warmup?.loaded ? 'loaded' : 'lazy/fallback' }}</p></article></section>
    </main>
  </div>
</template>
