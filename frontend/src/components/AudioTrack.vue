<template>
  <div class="audio-track">
    <div class="track-header">
      <span class="track-label">{{ label }}</span>
      <span v-if="trackData" class="track-info">
        {{ trackData.filename }} · {{ trackData.duration.toFixed(2) }}s · {{ trackData.sample_rate }}Hz
      </span>
    </div>

    <div v-if="!trackData" class="upload-zone" @dragover.prevent @drop.prevent="onDrop">
      <input
        ref="fileInput"
        type="file"
        accept="audio/*"
        class="file-input"
        @change="onFileChange"
      />
      <div class="upload-content" @click="$refs.fileInput.click()">
        <svg class="upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
          <polyline points="17 8 12 3 7 8"/>
          <line x1="12" y1="3" x2="12" y2="15"/>
        </svg>
        <p class="upload-text">点击或拖拽上传 MP3 音频文件</p>
      </div>
    </div>

    <div v-else class="waveform-container">
      <canvas ref="waveformCanvas" class="waveform-canvas"></canvas>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  trackData: { type: Object, default: null },
  progress: { type: Number, default: 0 },
  isPlaying: { type: Boolean, default: false },
})

const emit = defineEmits(['upload'])

const fileInput = ref(null)
const waveformCanvas = ref(null)
let animFrameId = null

function onFileChange(e) {
  const file = e.target.files[0]
  if (file) emit('upload', file)
}

function onDrop(e) {
  const file = e.dataTransfer.files[0]
  if (file) emit('upload', file)
}

function drawWaveform() {
  const canvas = waveformCanvas.value
  if (!canvas || !props.trackData) return

  const container = canvas.parentElement
  const dpr = window.devicePixelRatio || 1
  const w = container.clientWidth
  const h = container.clientHeight
  canvas.width = w * dpr
  canvas.height = h * dpr
  canvas.style.width = w + 'px'
  canvas.style.height = h + 'px'

  const ctx = canvas.getContext('2d')
  ctx.scale(dpr, dpr)
  ctx.clearRect(0, 0, w, h)

  const waveform = props.trackData.waveform
  const centerY = h / 2
  const barWidth = Math.max(1, w / waveform.length)
  const maxAmp = h / 2 * 0.85

  ctx.fillStyle = '#1a1a2e'
  ctx.fillRect(0, 0, w, h)

  ctx.beginPath()
  ctx.strokeStyle = '#0d7377'
  ctx.lineWidth = 1
  ctx.moveTo(0, centerY)
  ctx.lineTo(w, centerY)
  ctx.stroke()

  for (let i = 0; i < waveform.length; i++) {
    const x = i * barWidth
    const amp = waveform[i] * maxAmp
    const gradient = ctx.createLinearGradient(x, centerY - amp, x, centerY + amp)
    gradient.addColorStop(0, '#14ffec')
    gradient.addColorStop(0.5, '#0d7377')
    gradient.addColorStop(1, '#14ffec')
    ctx.fillStyle = gradient
    ctx.fillRect(x, centerY - amp, Math.max(1, barWidth - 0.5), amp * 2)
  }

  if (props.isPlaying || props.progress > 0) {
    const progressX = props.progress * w
    ctx.beginPath()
    ctx.strokeStyle = '#ff2e63'
    ctx.lineWidth = 2
    ctx.moveTo(progressX, 0)
    ctx.lineTo(progressX, h)
    ctx.stroke()

    ctx.beginPath()
    ctx.fillStyle = '#ff2e63'
    ctx.arc(progressX, 4, 5, 0, Math.PI * 2)
    ctx.fill()
  }
}

watch(() => [props.trackData, props.progress, props.isPlaying], () => {
  nextTick(drawWaveform)
}, { deep: true })

onMounted(() => {
  window.addEventListener('resize', drawWaveform)
})

onUnmounted(() => {
  window.removeEventListener('resize', drawWaveform)
  if (animFrameId) cancelAnimationFrame(animFrameId)
})
</script>

<style scoped>
.audio-track {
  background: #16213e;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #0d7377;
}

.track-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: #1a1a2e;
  border-bottom: 1px solid #0d7377;
}

.track-label {
  font-weight: 700;
  font-size: 14px;
  color: #14ffec;
  min-width: 60px;
}

.track-info {
  font-size: 12px;
  color: #8899aa;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.upload-zone {
  height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s;
}

.upload-zone:hover {
  background: #1a2a4a;
}

.file-input {
  display: none;
}

.upload-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #8899aa;
}

.upload-icon {
  width: 36px;
  height: 36px;
}

.upload-text {
  font-size: 14px;
  margin: 0;
}

.waveform-container {
  height: 160px;
  position: relative;
}

.waveform-canvas {
  width: 100%;
  height: 100%;
  display: block;
}
</style>
