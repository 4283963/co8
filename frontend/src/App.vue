<template>
  <div class="app">
    <header class="app-header">
      <h1 class="app-title">🎛️ Multi-Track Audio Editor</h1>
      <p class="app-subtitle">精简版多轨音频剪辑工具</p>
    </header>

    <div class="timeline-ruler">
      <div class="ruler-marks">
        <span v-for="t in rulerMarks" :key="t" :style="{ left: (t / timelineDuration) * 100 + '%' }" class="ruler-mark">
          {{ formatTime(t) }}
        </span>
      </div>
    </div>

    <div class="tracks-area">
      <AudioTrack
        label="Track 1"
        :trackData="tracks[0]"
        :progress="progress"
        :isPlaying="isPlaying"
        :timeOffset="trackOffsets[0]"
        :maxDuration="timelineDuration"
        @upload="(f) => handleUpload(0, f)"
        @offsetChange="(v) => handleOffsetChange(0, v)"
      />
      <AudioTrack
        label="Track 2"
        :trackData="tracks[1]"
        :progress="progress"
        :isPlaying="isPlaying"
        :timeOffset="trackOffsets[1]"
        :maxDuration="timelineDuration"
        @upload="(f) => handleUpload(1, f)"
        @offsetChange="(v) => handleOffsetChange(1, v)"
      />
    </div>

    <div class="transport-controls">
      <button class="btn btn-play" :disabled="!canPlay" @click="togglePlay">
        <svg v-if="!isPlaying" viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
          <polygon points="5,3 19,12 5,21"/>
        </svg>
        <svg v-else viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
          <rect x="6" y="4" width="4" height="16"/>
          <rect x="14" y="4" width="4" height="16"/>
        </svg>
        {{ isPlaying ? '暂停' : '播放' }}
      </button>
      <button class="btn btn-stop" :disabled="!isPlaying && progress === 0" @click="stopPlayback">
        <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
          <rect x="4" y="4" width="16" height="16" rx="2"/>
        </svg>
        停止
      </button>
      <div class="time-display">
        {{ formatTime(currentTime) }} / {{ formatTime(timelineDuration) }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
import AudioTrack from './components/AudioTrack.vue'

const API_BASE = '/api'

const tracks = ref([null, null])
const audioBuffers = ref([null, null])
const trackOffsets = ref([0, 0])
const isPlaying = ref(false)
const progress = ref(0)
const currentTime = ref(0)

let audioCtx = null
let sourceNodes = [null, null]
let playStartTime = 0
let playOffset = 0
let animFrameId = null

const timelineDuration = computed(() => {
  let max = 0
  for (let i = 0; i < 2; i++) {
    const dur = tracks.value[i]?.duration || 0
    const offset = trackOffsets.value[i] || 0
    const end = offset + dur
    if (end > max) max = end
  }
  return max
})

const rulerMarks = computed(() => {
  const dur = timelineDuration.value
  if (dur <= 0) return []
  const step = dur <= 10 ? 1 : dur <= 60 ? 5 : 10
  const marks = []
  for (let t = 0; t <= dur; t += step) marks.push(t)
  return marks
})

const canPlay = computed(() => tracks.value.some(t => t !== null))

function formatTime(sec) {
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  const ms = Math.floor((sec % 1) * 10)
  return `${m}:${s.toString().padStart(2, '0')}.${ms}`
}

function handleOffsetChange(trackIndex, newOffset) {
  trackOffsets.value[trackIndex] = Math.max(0, newOffset)
}

async function handleUpload(trackIndex, file) {
  stopPlayback()

  const formData = new FormData()
  formData.append('file', file)

  try {
    const res = await fetch(`${API_BASE}/upload`, { method: 'POST', body: formData })
    if (!res.ok) throw new Error('Upload failed')
    const data = await res.json()
    tracks.value[trackIndex] = data
    trackOffsets.value[trackIndex] = 0

    const audioRes = await fetch(`${API_BASE}/audio/${data.id}`)
    const arrayBuf = await audioRes.arrayBuffer()

    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)()
    const decoded = await audioCtx.decodeAudioData(arrayBuf)
    audioBuffers.value[trackIndex] = decoded
  } catch (err) {
    console.error('Upload error:', err)
    alert('音频上传失败，请重试')
  }
}

function togglePlay() {
  if (isPlaying.value) {
    pausePlayback()
  } else {
    startPlayback()
  }
}

function startPlayback() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)()
  if (audioCtx.state === 'suspended') audioCtx.resume()

  sourceNodes = [null, null]
  const globalOffset = playOffset

  for (let i = 0; i < 2; i++) {
    const buf = audioBuffers.value[i]
    if (!buf) continue

    const trackOffset = trackOffsets.value[i]
    const trackDuration = tracks.value[i]?.duration || 0
    const trackEndGlobal = trackOffset + trackDuration

    if (globalOffset >= trackEndGlobal) continue

    const source = audioCtx.createBufferSource()
    source.buffer = buf
    source.connect(audioCtx.destination)
    sourceNodes[i] = source

    if (globalOffset <= trackOffset) {
      const delay = trackOffset - globalOffset
      source.start(audioCtx.currentTime + delay, 0)
    } else {
      const audioOffset = globalOffset - trackOffset
      source.start(0, audioOffset)
    }

    source.onended = () => {
      if (sourceNodes[i] === source) {
        sourceNodes[i] = null
      }
      if (sourceNodes.every(s => s === null) && isPlaying.value) {
        stopPlayback()
      }
    }
  }

  playStartTime = audioCtx.currentTime - globalOffset
  isPlaying.value = true
  tickProgress()
}

function pausePlayback() {
  playOffset = audioCtx.currentTime - playStartTime
  isPlaying.value = false

  for (let i = 0; i < 2; i++) {
    if (sourceNodes[i]) {
      sourceNodes[i].onended = null
      sourceNodes[i].stop()
      sourceNodes[i] = null
    }
  }

  if (animFrameId) cancelAnimationFrame(animFrameId)
}

function stopPlayback() {
  isPlaying.value = false
  progress.value = 0
  currentTime.value = 0
  playOffset = 0

  for (let i = 0; i < 2; i++) {
    if (sourceNodes[i]) {
      sourceNodes[i].onended = null
      sourceNodes[i].stop()
      sourceNodes[i] = null
    }
  }

  if (animFrameId) cancelAnimationFrame(animFrameId)
}

function tickProgress() {
  if (!isPlaying.value) return

  const elapsed = audioCtx.currentTime - playStartTime
  const dur = timelineDuration.value

  currentTime.value = Math.min(elapsed, dur)
  progress.value = dur > 0 ? Math.min(elapsed / dur, 1) : 0

  if (elapsed >= dur) {
    stopPlayback()
    return
  }

  animFrameId = requestAnimationFrame(tickProgress)
}

onUnmounted(() => {
  stopPlayback()
  if (audioCtx) audioCtx.close()
})
</script>

<style scoped>
.app {
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  color: #e0e0e0;
}

.app-header {
  text-align: center;
  margin-bottom: 24px;
}

.app-title {
  font-size: 28px;
  font-weight: 800;
  margin: 0 0 4px;
  background: linear-gradient(135deg, #14ffec, #0d7377);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.app-subtitle {
  margin: 0;
  font-size: 14px;
  color: #667788;
}

.timeline-ruler {
  position: relative;
  height: 28px;
  background: #1a1a2e;
  border-radius: 6px 6px 0 0;
  border: 1px solid #0d7377;
  border-bottom: none;
  overflow: hidden;
  margin-bottom: 0;
}

.ruler-marks {
  position: relative;
  height: 100%;
}

.ruler-mark {
  position: absolute;
  top: 4px;
  font-size: 10px;
  color: #667788;
  transform: translateX(-50%);
}

.tracks-area {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.transport-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  background: #1a1a2e;
  border-radius: 0 0 8px 8px;
  border: 1px solid #0d7377;
  border-top: none;
}

.btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 24px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  color: #fff;
}

.btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-play {
  background: linear-gradient(135deg, #0d7377, #14ffec);
  color: #1a1a2e;
}

.btn-play:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 15px rgba(20, 255, 236, 0.3);
}

.btn-stop {
  background: linear-gradient(135deg, #ff2e63, #d4163c);
}

.btn-stop:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow:0 4px 15px rgba(255, 46, 99, 0.3);
}

.time-display {
  margin-left: auto;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 18px;
  font-weight: 700;
  color: #14ffec;
  letter-spacing: 1px;
}
</style>
