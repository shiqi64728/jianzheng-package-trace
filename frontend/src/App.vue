<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from './api'

const files = reactive({ N1: null, N2: null, N3: null })
const previews = reactive({ N1: '', N2: '', N3: '' })
const caseName = ref('比赛现场匿名演示')
const caseId = ref('')
const result = ref(null)
const model = ref(null)
const busy = ref(false)
const message = ref('请依次选择 N1、N2、N3 包裹外观图片。')
const nodeIds = ['N1', 'N2', 'N3']

onMounted(async () => {
  try { model.value = await api.modelInfo() } catch (error) { message.value = error.message }
})

function selectFile(nodeId, event) {
  const file = event.target.files?.[0]
  if (!file) return
  files[nodeId] = file
  if (previews[nodeId]) URL.revokeObjectURL(previews[nodeId])
  previews[nodeId] = URL.createObjectURL(file)
}

const ready = computed(() => nodeIds.every((node) => files[node]))

function nodeResult(nodeId) {
  return result.value?.nodes?.find((node) => node.node_id === nodeId)
}

function nodeState(nodeId) {
  return result.value?.analysis?.node_states?.find((node) => node.node_id === nodeId)?.status || '待分析'
}

async function runAnalysis() {
  if (!ready.value) return
  busy.value = true
  result.value = null
  try {
    const created = await api.createCase(caseName.value)
    caseId.value = created.case_id
    for (const nodeId of nodeIds) await api.uploadNode(caseId.value, nodeId, files[nodeId])
    result.value = await api.analyze(caseId.value)
    message.value = '端到端分析完成，证据已写入 SQLite。'
  } catch (error) {
    message.value = error.message
  } finally { busy.value = false }
}
</script>

<template>
  <main>
    <header class="masthead">
      <div><p class="eyebrow">JIANZHENG · COMPETITION MVP v0.1</p>
      <h1>件证</h1><h2>连续外观数字指纹与异常节点定位</h2></div>
      <div class="model-chip"><span>活动模型</span><strong>{{ model?.model_version || '连接中' }}</strong>
        <small>{{ model?.runtime || '—' }} · {{ model?.imgsz || '—' }}px</small></div>
    </header>

    <section class="workspace">
      <aside class="panel setup">
        <p class="section-no">01 / CASE</p><h3>创建分析案例</h3>
        <label>匿名案例名称<input v-model="caseName" maxlength="120" /></label>
        <div class="support"><h4>识别边界</h4>
          <p><b>D01</b><span>待扩展</span></p><p class="active"><b>D02</b><span>模型支持 · 表面凹陷</span></p>
          <p class="active"><b>D03</b><span>模型支持 · 纸箱破口</span></p><p><b>D04</b><span>待审核 / 待扩展</span></p>
          <p><b>D05</b><span>待扩展</span></p></div>
        <p class="status">{{ message }}</p>
        <button :disabled="!ready || busy" @click="runAnalysis">{{ busy ? '正在分析…' : '开始完整分析' }}</button>
      </aside>

      <section class="panel captures"><p class="section-no">02 / SEQUENCE</p><h3>N1 / N2 / N3 节点图片</h3>
        <div class="node-grid"><article v-for="nodeId in nodeIds" :key="nodeId" class="node-card">
          <div class="node-head"><b>{{ nodeId }}</b><span>{{ nodeState(nodeId) }}</span></div>
          <label class="image-drop">
            <img v-if="previews[nodeId]" :src="previews[nodeId]" :alt="nodeId" />
            <span v-else>选择 {{ nodeId }} 图片</span>
            <input type="file" accept="image/jpeg,image/png,image/webp" @change="selectFile(nodeId, $event)" />
            <i v-for="(box, index) in (nodeResult(nodeId)?.detections || [])" :key="index" class="box"
              :style="{left: `${box.bbox_normalized[0]*100}%`,top:`${box.bbox_normalized[1]*100}%`,width:`${(box.bbox_normalized[2]-box.bbox_normalized[0])*100}%`,height:`${(box.bbox_normalized[3]-box.bbox_normalized[1])*100}%`}">
              <em>{{ box.class_code }} {{ box.confidence.toFixed(2) }}</em></i>
          </label>
          <p>检测数量 <strong>{{ nodeResult(nodeId)?.detections?.length || 0 }}</strong></p>
          <p>最高置信度 <strong>{{ Math.max(0, ...(nodeResult(nodeId)?.detections || []).map(x=>x.confidence)).toFixed(3) }}</strong></p>
        </article></div>
        <div v-if="result" class="pairs"><article v-for="pair in result.pair_changes" :key="pair.current_node_id">
          <h4>{{ pair.reference_node_id }} → {{ pair.current_node_id }}</h4>
          <p><span>Registration</span><b>{{ pair.registration_status }}</b></p>
          <p><span>Change score</span><b>{{ pair.change_score.toFixed(3) }}</b></p>
          <p><span>Change area</span><b>{{ (pair.changed_pixel_ratio*100).toFixed(2) }}%</b></p>
          <small>{{ pair.changed_region_count }} 个变化区域；未命中D02/D03者统一为 UNKNOWN_VISUAL_CHANGE</small>
        </article></div>
      </section>

      <aside class="panel conclusion"><p class="section-no">03 / EVIDENCE</p><h3>分析结果</h3>
        <div v-if="result" class="verdict"><span>首次异常区间</span>
          <strong>{{ result.analysis.first_abnormal_interval || result.analysis.conclusion_code }}</strong>
          <p>{{ result.analysis.explanation }}</p><div class="grade">技术证据等级 <b>{{ result.analysis.evidence_level }}</b></div>
          <dl><dt>已知损伤</dt><dd>{{ result.nodes.flatMap(n=>n.detections).map(x=>`${x.class_code} ${x.class_name}`).join('、') || '未检测到D02/D03' }}</dd>
          <dt>视觉变化</dt><dd>{{ result.pair_changes.some(x=>x.is_significant) ? '检测到明显外观变化' : '未达到变化阈值' }}</dd></dl>
          <a :href="api.reportUrl(caseId)" target="_blank">打开 HTML 证据报告 ↗</a></div>
        <div v-else class="empty-result"><div class="pulse"></div><p>完成三节点上传后，系统将在此展示首次异常区间与技术证据等级。</p></div>
      </aside>
    </section>
    <footer>系统输出为计算机视觉辅助分析结果，用于异常定位与责任辅助判断，不直接构成法律责任结论。</footer>
  </main>
</template>
