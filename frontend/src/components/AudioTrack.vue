<template>
  <div class="audio-track">
    <div class="track-header">
      <span class="track-label">{{ label }}</span>
      <span v-if="trackData" class="track-info">
        {{ trackData.filename }} · {{ trackData.duration.toFixed(2) }}s · {{ trackData.sample_rate }}Hz
        <span v-if="trackData.tempo" class="tempo-badge">{{ trackData.tempo.toFixed(0) }} BPM</span>
        <span v-if="timeOffset > 0" class="offset-badge">+{{ timeOffset.toFixed(2) }}s 延迟</span>
      </span>
      <span v-if="trackData" class="drag-hint">← 拖拽波形调整偏移 →</span>
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

    <div v-else class="waveform-container" :class="{ dragging: isDragging }">
      <canvas
        ref="waveformCanvas"
        class="waveform-canvas"
        @mousedown="onMouseDown"
      ></canvas>
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
  timeOffset: { type: Number, default: 0 },
  maxDuration: { type: Number, default: 0 },
})

const emit = defineEmits(['upload', 'offsetChange'])

const fileInput = ref(null)
const waveformCanvas = ref(null)
const isDragging = ref(false)

let dragStartX = 0
let dragStartOffset = 0
let canvasWidthCache = 0

let beatIndex = 0
let flashIntensity = 0
let flashRafId = null

function onFileChange(e) {
  const file = e.target.files[0]
  if (file) emit('upload', file)
}

function onDrop(e) {
  const file = e.dataTransfer.files[0]
  if (file) emit('upload', file)
}

function onMouseDown(e) {
  if (!props.trackData) return
  isDragging.value = true
  dragStartX = e.clientX
  dragStartOffset = props.timeOffset
  e.preventDefault()
}

function onMouseMove(e) {
  if (!isDragging.value) return
  const canvas = waveformCanvas.value
  if (!canvas) return
  const containerWidth = canvas.parentElement.clientWidth
  if (containerWidth <= 0 || props.maxDuration <= 0) return
  const deltaX = e.clientX - dragStartX
  const deltaTime = (deltaX / containerWidth) * props.maxDuration
  const newOffset = Math.max(0, dragStartOffset + deltaTime)
  emit('offsetChange', newOffset)
}

function onMouseUp() {
  if (!isDragging.value) return
  isDragging.value = false
}

function triggerBeatFlash() {
  flashIntensity = 1
  startFlashDecay()
}

function startFlashDecay() {
  if (flashRafId) return
  const decay = () => {
    flashIntensity *= 0.85
    if (flashIntensity < 0.01) {
      flashIntensity = 0
      flashRafId = null
      drawWaveform()
      return
    }
    drawWaveform()
    flashRafId = requestAnimationFrame(decay)
  }
  flashRafId = requestAnimationFrame(decay)
}

function stopFlashDecay() {
  if (flashRafId) {
    cancelAnimationFrame(flashRafId)
    flashRafId = null
  }
}

function checkBeats() {
  if (!props.trackData || !props.trackData.beats || props.trackData.beats.length === 0) return
  if (!props.isPlaying) return

  const timelineDur = props.maxDuration || props.trackData.duration
  const currentGlobalTime = props.progress * timelineDur
  const beats = props.trackData.beats

  if (beatIndex > 0 && currentGlobalTime < props.timeOffset + beats[beatIndex - 1]) {
    beatIndex = 0
  }

  while (beatIndex < beats.length) {
    const beatGlobalTime = props.timeOffset + beats[beatIndex]
    if (beatGlobalTime <= currentGlobalTime) {
      triggerBeatFlash()
      beatIndex++
    } else {
      break
    }
  }
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
  canvasWidthCache = w

  const ctx = canvas.getContext('2d')
  ctx.scale(dpr, dpr)
  ctx.clearRect(0, 0, w, h)

  const waveform = props.trackData.waveform
  const trackDuration = props.trackData.duration
  const timelineDuration = props.maxDuration || trackDuration
  const centerY = h / 2
  const maxAmp = h / 2 * 0.85

  ctx.fillStyle = '#1a1a2e'
  ctx.fillRect(0, 0, w, h)

  if (flashIntensity > 0) {
    const glow = ctx.createRadialGradient(w / 2, centerY, 0, w / 2, centerY, w * 0.6)
    const alpha = flashIntensity * 0.45
    glow.addColorStop(0, `rgba(255, 0, 128, ${alpha})`)
    glow.addColorStop(0.4, `rgba(200, 0, 255, ${alpha * 0.7})`)
    glow.addColorStop(1, 'rgba(0, 0, 0, 0)')
    ctx.fillStyle = glow
    ctx.fillRect(0, 0, w, h)
  }

  ctx.save()
  ctx.beginPath()
  ctx.rect(0, 0, w, h)
  ctx.clip()

  const offsetRatio = props.timeOffset / timelineDuration
  const durationRatio = trackDuration / timelineDuration
  const trackStartX = offsetRatio * w
  const trackWidth = durationRatio * w
  const barWidth = Math.max(1, trackWidth / waveform.length)

  if (props.timeOffset > 0) {
    ctx.fillStyle = 'rgba(13, 115, 119, 0.08)'
    ctx.fillRect(0, 0, trackStartX, h)

    ctx.beginPath()
    ctx.strokeStyle = 'rgba(13, 115, 119, 0.4)'
    ctx.lineWidth = 1
    ctx.setLineDash([4, 4])
    ctx.moveTo(trackStartX, 0)
    ctx.lineTo(trackStartX, h)
    ctx.stroke()
    ctx.setLineDash([])
  }

  ctx.beginPath()
  ctx.strokeStyle = '#0d7377'
  ctx.lineWidth = 1
  ctx.moveTo(trackStartX, centerY)
  ctx.lineTo(trackStartX + trackWidth, centerY)
  ctx.stroke()

  for (let i = 0; i < waveform.length; i++) {
    const x = trackStartX + i * barWidth
    if (x + barWidth < 0 || x > w) continue
    const amp = waveform[i] * maxAmp
    const gradient = ctx.createLinearGradient(x, centerY - amp, x, centerY + amp)
    gradient.addColorStop(0, '#14ffec')
    gradient.addColorStop(0.5, '#0d7377')
    gradient.addColorStop(1, '#14ffec')
    ctx.fillStyle = gradient
    ctx.fillRect(x, centerY - amp, Math.max(1, barWidth - 0.5), amp * 2)
  }

  if (props.timeOffset > 0) {
    ctx.fillStyle = '#14ffec'
    ctx.font = '11px monospace'
    ctx.fillText(`+${props.timeOffset.toFixed(2)}s`, trackStartX + 6, 16)
  }

  ctx.restore()

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

watch(() => [props.trackData, props.progress, props.isPlaying, props.timeOffset, props.maxDuration], () => {
  checkBeats()
  nextTick(drawWaveform)
}, { deep: true })

watch(() => props.trackData, (newData) => {
  beatIndex = 0
  flashIntensity = 0
}, { deep: false })

watch(() => props.isPlaying, (playing) => {
  if (!playing) {
    stopFlashDecay()
  }
})

watch(() => props.timeOffset, () => {
  beatIndex = 0
})

onMounted(() => {
  window.addEventListener('resize', drawWaveform)
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
})

onUnmounted(() => {
  window.removeEventListener('resize', drawWaveform)
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
  stopFlashDecay()
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

.tempo-badge {
  display: inline-block;
  background: rgba(200, 0, 255, 0.2);
  color: #d400ff;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 11px;
  margin-left: 4px;
}

.offset-badge {
  display: inline-block;
  background: rgba(255, 46, 99, 0.2);
  color: #ff2e63;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 11px;
  margin-left: 4px;
}

.drag-hint {
  margin-left: auto;
  font-size: 11px;
  color: #556677;
  flex-shrink: 0;
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
  cursor: grab;
}

.waveform-container.dragging {
  cursor: grabbing;
}

.waveform-container.dragging .waveform-canvas {
  user-select: none;
}

.waveform-canvas {
  width: 100%;
  height: 100%;
  display: block;
}
</style>
