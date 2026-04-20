import { uploadApi } from '../api'
import { optimizeImageForUpload } from './imageUploadOptimizer'

const DEFAULT_CHUNK_SIZE = 1024 * 1024
const DEFAULT_MAX_RETRIES = 3
const DEFAULT_RETRY_DELAY = 800
const DEFAULT_MAX_IMAGE_DIMENSION = 1920
const DEFAULT_IMAGE_QUALITY = 0.82
const DEFAULT_MAX_CONCURRENT_UPLOADS = 3

const ENV_UPLOAD_CONCURRENCY = Number(import.meta.env.VITE_UPLOAD_MAX_CONCURRENCY || DEFAULT_MAX_CONCURRENT_UPLOADS)
const MAX_CONCURRENT_UPLOADS = Math.max(2, Math.min(3, Number.isFinite(ENV_UPLOAD_CONCURRENCY) ? Math.floor(ENV_UPLOAD_CONCURRENCY) : DEFAULT_MAX_CONCURRENT_UPLOADS))

let activeUploadTasks = 0
const uploadTaskQueue = []

const acquireUploadSlot = () =>
  new Promise((resolve) => {
    if (activeUploadTasks < MAX_CONCURRENT_UPLOADS) {
      activeUploadTasks += 1
      resolve()
      return
    }
    uploadTaskQueue.push(() => {
      activeUploadTasks += 1
      resolve()
    })
  })

const releaseUploadSlot = () => {
  activeUploadTasks = Math.max(0, activeUploadTasks - 1)
  const next = uploadTaskQueue.shift()
  if (typeof next === 'function') next()
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

const toNumber = (value, fallback) => {
  const n = Number(value)
  return Number.isFinite(n) && n > 0 ? n : fallback
}

const makeResumeKey = (file, category, subDir) => {
  const name = String(file?.name || 'unknown')
  const size = Number(file?.size || 0)
  const modified = Number(file?.lastModified || 0)
  return `chunk_upload:${category}:${subDir}:${name}:${size}:${modified}`
}

const calcChunkBytes = (index, totalChunks, totalSize, chunkSize) => {
  if (index < totalChunks - 1) return chunkSize
  const rest = totalSize - chunkSize * (totalChunks - 1)
  return rest > 0 ? rest : chunkSize
}

const estimateUploadedBytes = (uploadedChunks, totalChunks, totalSize, chunkSize) => {
  let bytes = 0
  for (const idx of uploadedChunks) {
    bytes += calcChunkBytes(idx, totalChunks, totalSize, chunkSize)
  }
  return Math.min(bytes, totalSize)
}

const emitProgress = (onProgress, loaded, total) => {
  if (!onProgress) return
  const safeTotal = Math.max(1, Number(total || 0))
  const safeLoaded = Math.max(0, Math.min(Number(loaded || 0), safeTotal))
  const percent = Math.min(100, Math.floor((safeLoaded * 100) / safeTotal))
  onProgress(percent, safeLoaded, safeTotal)
}

const tryGetResumeUpload = async (resumeKey) => {
  if (!resumeKey) return null
  let uploadId = ''
  try {
    uploadId = localStorage.getItem(resumeKey) || ''
  } catch (_) {
    uploadId = ''
  }
  if (!uploadId) return null
  try {
    const statusResp = await uploadApi.getChunkUploadStatus(uploadId)
    return {
      uploadId,
      status: statusResp?.data || {},
    }
  } catch (_) {
    try {
      localStorage.removeItem(resumeKey)
    } catch (__){ }
    return null
  }
}

const initUpload = async (file, options, totalChunks) => {
  const payload = {
    filename: file.name,
    total_size: file.size,
    chunk_size: options.chunkSize,
    total_chunks: totalChunks,
    category: options.category,
    sub_dir: options.subDir,
    mime_type: file.type || '',
  }
  const initResp = await uploadApi.initChunkUpload(payload)
  return initResp?.data || {}
}

const uploadChunkWithRetry = async ({ uploadId, file, index, totalChunks, maxRetries, retryDelay, onProgress, loadedBytes, totalSize, chunkSize }) => {
  const start = index * chunkSize
  const end = Math.min(start + chunkSize, totalSize)
  const chunkBlob = file.slice(start, end)
  const chunkBytes = end - start
  let lastError = null

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      await uploadApi.uploadChunk(uploadId, chunkBlob, index, totalChunks, (evt) => {
        const chunkLoaded = Math.min(chunkBytes, Number(evt?.loaded || 0))
        emitProgress(onProgress, loadedBytes + chunkLoaded, totalSize)
      })
      return chunkBytes
    } catch (error) {
      lastError = error
      if (attempt >= maxRetries) break
      const waitMs = retryDelay * Math.pow(2, attempt)
      await sleep(waitMs)
    }
  }

  throw lastError || new Error('分片上传失败')
}

export const uploadFileByChunks = async (file, config = {}) => {
  if (!file) {
    throw new Error('文件不能为空')
  }

  await acquireUploadSlot()
  try {
    const optimizeImage = config.optimizeImage !== false
    let sourceFile = file
    if (optimizeImage && /^image\//i.test(String(file.type || ''))) {
      sourceFile = await optimizeImageForUpload(file, {
        maxDimension: toNumber(config.maxImageDimension, DEFAULT_MAX_IMAGE_DIMENSION),
        quality: Number(config.imageQuality ?? DEFAULT_IMAGE_QUALITY),
        preferAvif: config.preferAvif !== false,
      })
    }

    const options = {
      category: String(config.category || 'general'),
      subDir: String(config.subDir || ''),
      chunkSize: toNumber(config.chunkSize, DEFAULT_CHUNK_SIZE),
      maxRetries: Math.max(0, Math.floor(toNumber(config.maxRetries, DEFAULT_MAX_RETRIES))),
      retryDelay: Math.max(200, Math.floor(toNumber(config.retryDelay, DEFAULT_RETRY_DELAY))),
      onProgress: typeof config.onProgress === 'function' ? config.onProgress : null,
    }

    const totalSize = Number(sourceFile.size || 0)
    const totalChunks = Math.max(1, Math.ceil(totalSize / options.chunkSize))
    const resumeKey = makeResumeKey(sourceFile, options.category, options.subDir)

    let uploadId = ''
    let uploadedChunks = []

    const resumed = await tryGetResumeUpload(resumeKey)
    if (resumed?.uploadId) {
      uploadId = resumed.uploadId
      uploadedChunks = Array.isArray(resumed?.status?.uploaded_chunks) ? resumed.status.uploaded_chunks : []
    } else {
      const initData = await initUpload(sourceFile, options, totalChunks)
      uploadId = String(initData.upload_id || '')
      uploadedChunks = []
      if (!uploadId) {
        throw new Error('初始化分片上传失败')
      }
      try {
        localStorage.setItem(resumeKey, uploadId)
      } catch (_) {}
    }

    let loadedBytes = estimateUploadedBytes(uploadedChunks, totalChunks, totalSize, options.chunkSize)
    const uploadedSet = new Set(uploadedChunks.map((n) => Number(n)).filter((n) => Number.isInteger(n) && n >= 0 && n < totalChunks))

    emitProgress(options.onProgress, loadedBytes, totalSize)

    try {
      for (let index = 0; index < totalChunks; index++) {
        if (uploadedSet.has(index)) {
          continue
        }
        const chunkBytes = await uploadChunkWithRetry({
          uploadId,
          file: sourceFile,
          index,
          totalChunks,
          maxRetries: options.maxRetries,
          retryDelay: options.retryDelay,
          onProgress: options.onProgress,
          loadedBytes,
          totalSize,
          chunkSize: options.chunkSize,
        })
        loadedBytes += chunkBytes
        emitProgress(options.onProgress, loadedBytes, totalSize)
      }

      const completeResp = await uploadApi.completeChunkUpload(uploadId)
      try {
        localStorage.removeItem(resumeKey)
      } catch (_) {}
      emitProgress(options.onProgress, totalSize, totalSize)
      return completeResp?.data || {}
    } catch (error) {
      emitProgress(options.onProgress, loadedBytes, totalSize)
      throw error
    }
  } finally {
    releaseUploadSlot()
  }
}

export default uploadFileByChunks
