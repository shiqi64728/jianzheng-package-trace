<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from './api'

const nodeIds = ['N1', 'N2', 'N3']
const allSurfaces = ['front', 'left', 'right', 'top']
const surfaceLabels = { front: '正面', left: '左侧', right: '右侧', top: '顶部' }
const files = reactive(Object.fromEntries(nodeIds.map(node => [node, Object.fromEntries(allSurfaces.map(surface => [surface, null]))])))
const previews = reactive(Object.fromEntries(nodeIds.map(node => [node, Object.fromEntries(allSurfaces.map(surface => [surface, '']))])))
const mode = ref('simple')
const caseName = ref('比赛现场匿名多表面演示')
const caseId = ref('')
const result = ref(null)
const reviews = ref([])
const model = ref(null)
const warmup = ref(null)
const busy = ref(false)
const reviewing = ref(false)
const message = ref('Simple Mode 默认上传 N1/N2/N3 正面；可切换 Multi-Surface Mode。')
const reviewForm = reactive({
  node_from: 'N1', node_to: 'N2', surface: 'left', review_class: 'D05',
  review_status: 'CONFIRMED', reviewer_alias: 'DEMO-REVIEWER', review_note: '',
  supersedes_review_id: null,
})

const displayedSurfaces = computed(() => mode.value === 'simple' ? ['front'] : allSurfaces)
const ready = computed(() => nodeIds.every(node => displayedSurfaces.value.some(surface => files[node][surface])))

onMounted(async () => {
  try {
    [model.value, warmup.value] = await Promise.all([api.modelInfo(), api.warmup()])
  } catch (error) { message.value = error.message }
})

function selectFile(nodeId, surface, event) {
  const file = event.target.files?.[0]
  if (!file) return
  files[nodeId][surface] = file
  if (previews[nodeId][surface]) URL.revokeObjectURL(previews[nodeId][surface])
  previews[nodeId][surface] = URL.createObjectURL(file)
}

function captureResult(nodeId, surface) {
  return result.value?.nodes?.find(item => item.node_id === nodeId && item.surface === surface)
}

function incomingPair(nodeId, surface) {
  return result.value?.pair_changes?.find(item => item.current_node_id === nodeId && item.surface === surface)
}

function surfaceState(nodeId, surface) {
  const node = result.value?.analysis?.node_states?.find(item => item.node_id === nodeId)
  return node?.surface_states?.find(item => item.surface === surface)?.status || (files[nodeId][surface] ? '待分析' : 'MISSING')
}

function reviewFor(nodeId, surface) {
  return reviews.value.findLast?.(item => item.node_to === nodeId && item.surface === surface)
    || [...reviews.value].reverse().find(item => item.node_to === nodeId && item.surface === surface)
}

function initializeReview() {
  const interval = result.value?.analysis?.first_abnormal_interval
  if (interval) {
    const [from, to] = interval.split('_TO_')
    reviewForm.node_from = from
    reviewForm.node_to = to
  }
  reviewForm.surface = result.value?.analysis?.trigger_surfaces?.[0]?.surface || 'front'
}

async function runAnalysis() {
  if (!ready.value) return
  busy.value = true
  result.value = null
  reviews.value = []
  try {
    const created = await api.createCase(caseName.value)
    caseId.value = created.case_id
    for (const nodeId of nodeIds) {
      for (const surface of displayedSurfaces.value) {
        if (files[nodeId][surface]) await api.uploadNode(caseId.value, nodeId, surface, files[nodeId][surface])
      }
    }
    result.value = await api.analyze(caseId.value)
    reviews.value = result.value.reviews || []
    initializeReview()
    message.value = '多表面端到端分析完成，机器证据已写入 SQLite。'
  } catch (error) { message.value = error.message } finally { busy.value = false }
}

async function submitReview() {
  reviewing.value = true
  try {
    const created = await api.createReview(caseId.value, { ...reviewForm })
    reviews.value = (await api.reviews(caseId.value)).reviews
    reviewForm.supersedes_review_id = created.review_id
    message.value = '人工复核事件已追加；机器结果未被覆盖。再次提交将形成 supersede 审计链。'
  } catch (error) { message.value = error.message } finally { reviewing.value = false }
}
</script>

<template>
  <main>
    <header class="masthead">
      <div><p class="eyebrow">JIANZHENG · COMPETITION MVP v0.2</p><h1>件证</h1>
        <h2>多表面连续外观数字指纹与异常节点定位</h2></div>
      <div class="model-chip"><span>活动模型</span><strong>{{ model?.model_version || '连接中' }}</strong>
        <small>{{ model?.runtime || '—' }} · {{ model?.imgsz || '—' }}px · {{ warmup?.loaded ? '已预热' : '惰性加载' }}</small></div>
    </header>

    <section class="toolbar panel">
      <label>匿名案例名称<input v-model="caseName" maxlength="120" /></label>
      <div class="mode-switch"><button :class="{selected: mode === 'simple'}" @click="mode='simple'">Simple Mode</button>
        <button :class="{selected: mode === 'multi'}" @click="mode='multi'">Multi-Surface Mode</button></div>
      <button class="primary" :disabled="!ready || busy" @click="runAnalysis">{{ busy ? '正在分析…' : '开始完整分析' }}</button>
      <p class="status">{{ message }}</p>
    </section>

    <section class="panel"><div class="section-head"><div><p class="section-no">01 / CAPTURE MATRIX</p>
      <h3>Node × Surface Matrix</h3></div><small>Multi-Surface Mode 允许缺失单元格；只比较相邻节点的同一表面。</small></div>
      <div class="matrix-wrap"><table class="matrix"><thead><tr><th>Node</th><th v-for="surface in displayedSurfaces" :key="surface">{{ surfaceLabels[surface] }}<small>{{ surface }}</small></th></tr></thead>
        <tbody><tr v-for="nodeId in nodeIds" :key="nodeId"><th>{{ nodeId }}</th>
          <td v-for="surface in displayedSurfaces" :key="`${nodeId}-${surface}`">
            <label class="image-drop"><img v-if="previews[nodeId][surface]" :src="previews[nodeId][surface]" :alt="`${nodeId}.${surface}`" />
              <span v-else>上传<br>{{ nodeId }}.{{ surface }}</span><input type="file" accept="image/jpeg,image/png,image/webp" @change="selectFile(nodeId, surface, $event)" />
              <i v-for="(box, index) in (captureResult(nodeId, surface)?.detections || [])" :key="index" class="box"
                :style="{left:`${box.bbox_normalized[0]*100}%`,top:`${box.bbox_normalized[1]*100}%`,width:`${(box.bbox_normalized[2]-box.bbox_normalized[0])*100}%`,height:`${(box.bbox_normalized[3]-box.bbox_normalized[1])*100}%`}"><em>{{ box.class_code }} {{ box.confidence.toFixed(2) }}</em></i>
            </label>
            <div class="cell-meta"><b :class="surfaceState(nodeId,surface).toLowerCase()">{{ surfaceState(nodeId,surface) }}</b>
              <span>已知损伤 {{ captureResult(nodeId,surface)?.detections?.length || 0 }}</span>
              <span v-if="incomingPair(nodeId,surface)">变化 {{ (incomingPair(nodeId,surface).changed_pixel_ratio*100).toFixed(2) }}%</span>
              <span v-if="reviewFor(nodeId,surface)" class="reviewed">人工 {{ reviewFor(nodeId,surface).review_class }}/{{ reviewFor(nodeId,surface).review_status }}</span></div>
          </td></tr></tbody></table></div>
    </section>

    <section v-if="result" class="result-grid">
      <section class="panel"><p class="section-no">02 / MACHINE EVIDENCE</p><h3>机器分析</h3>
        <div class="verdict"><span>首次异常区间</span><strong>{{ result.analysis.first_abnormal_interval || result.analysis.conclusion_code }}</strong>
          <p>{{ result.analysis.explanation }}</p><div class="grade">技术证据等级 <b>{{ result.analysis.evidence_level }}</b></div>
          <h4>触发表面</h4><ul><li v-for="item in result.analysis.trigger_surfaces" :key="item.surface">{{ item.surface }} · {{ item.reason }} · {{ item.change_score.toFixed(3) }}</li><li v-if="!result.analysis.trigger_surfaces.length">无</li></ul>
          <a :href="api.reportUrl(caseId)" target="_blank">打开 HTML v0.2 证据报告 →</a></div>
      </section>

      <section class="panel review-panel"><p class="section-no">03 / HUMAN REVIEW</p><h3>人工复核（append-only）</h3>
        <p class="hint">D01/D04/D05 由变化发现后人工分类，不表示模型自动识别。</p>
        <div class="form-grid"><label>起点<input v-model="reviewForm.node_from" /></label><label>终点<input v-model="reviewForm.node_to" /></label>
          <label>表面<select v-model="reviewForm.surface"><option v-for="surface in allSurfaces" :key="surface">{{ surface }}</option></select></label>
          <label>复核类别<select v-model="reviewForm.review_class"><option>D01</option><option>D02</option><option>D03</option><option>D04</option><option>D05</option><option>NORMAL_VARIATION</option><option>UNSURE</option></select></label>
          <label>状态<select v-model="reviewForm.review_status"><option>CONFIRMED</option><option>REJECTED</option><option>UNSURE</option></select></label>
          <label>匿名复核人<select v-model="reviewForm.reviewer_alias"><option>MEMBER-A</option><option>MEMBER-B</option><option>MEMBER-C</option><option>DEMO-REVIEWER</option></select></label></div>
        <label>备注<textarea v-model="reviewForm.review_note" maxlength="500" placeholder="不得填写真实姓名、手机号、地址或运单号" /></label>
        <button class="primary" :disabled="reviewing" @click="submitReview">{{ reviewing ? '提交中…' : '追加复核事件' }}</button>
        <ol class="review-list"><li v-for="item in reviews" :key="item.review_id"><b>{{ item.review_class }} / {{ item.review_status }}</b>
          <span>机器：{{ item.machine_result }} · {{ item.node_from }}→{{ item.node_to }}.{{ item.surface }}</span><code>{{ item.review_payload_sha256.slice(0,16) }}…</code></li></ol>
      </section>
    </section>

    <section class="panel capabilities"><p class="section-no">04 / CAPABILITY BOUNDARY</p><h3>当前五类业务闭环</h3>
      <div><p><b>D02 / D03</b><span>活动 AI 检测器自动识别 + 变化证据</span></p>
        <p><b>D01 / D04 / D05</b><span>开放集视觉变化发现 → UNKNOWN_VISUAL_CHANGE → 人工复核分类</span></p></div>
      <small>当前不是 D01/D04/D05 的 AI 自动分类支持。</small></section>
    <footer>AI 已知异常检测 + 开放集变化检测 + 人工复核 + 多节点多表面证据融合；不直接构成法律责任结论。</footer>
  </main>
</template>
