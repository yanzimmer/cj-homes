const DEFAULT_MAX_DIMENSION = 1920
const DEFAULT_IMAGE_QUALITY = 0.82
const DEFAULT_MIN_SIZE_TO_OPTIMIZE = 120 * 1024
const DEFAULT_MIN_SAVING_RATIO = 0.97

const EXT_BY_MIME = {
  'image/avif': 'avif',
  'image/webp': 'webp',
  'image/jpeg': 'jpg',
  'image/png': 'png',
}

const isImageFile = (file) => /^image\//i.test(String(file?.type || ''))

const toNumber = (value, fallback) => {
  const n = Number(value)
  return Number.isFinite(n) && n > 0 ? n : fallback
}

const buildOutputName = (file, mimeType) => {
  const original = String(file?.name || 'upload')
  const dotIndex = original.lastIndexOf('.')
  const baseName = dotIndex > 0 ? original.slice(0, dotIndex) : original
  const ext = EXT_BY_MIME[mimeType] || 'bin'
  return `${baseName}.${ext}`
}

const loadImageResource = async (file) => {
  if (typeof createImageBitmap === 'function') {
    const bitmap = await createImageBitmap(file)
    return {
      source: bitmap,
      width: bitmap.width,
      height: bitmap.height,
      cleanup: () => {
        try {
          bitmap.close()
        } catch (_) {}
      },
    }
  }

  if (typeof window === 'undefined' || typeof Image === 'undefined' || typeof URL === 'undefined') {
    throw new Error('Unsupported runtime for image optimization')
  }

  const objectUrl = URL.createObjectURL(file)
  return await new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      resolve({
        source: img,
        width: img.naturalWidth || img.width,
        height: img.naturalHeight || img.height,
        cleanup: () => URL.revokeObjectURL(objectUrl),
      })
    }
    img.onerror = (err) => {
      URL.revokeObjectURL(objectUrl)
      reject(err || new Error('Failed to decode image'))
    }
    img.src = objectUrl
  })
}

const canvasToBlob = (canvas, mimeType, quality) =>
  new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob), mimeType, quality)
  })

const buildTargetFormats = (preferAvif) => (preferAvif ? ['image/avif', 'image/webp'] : ['image/webp'])

export const optimizeImageForUpload = async (file, options = {}) => {
  if (!file || !isImageFile(file)) return file
  if (typeof document === 'undefined') return file

  const maxDimension = Math.max(320, Math.floor(toNumber(options.maxDimension, DEFAULT_MAX_DIMENSION)))
  const quality = Math.max(0.4, Math.min(0.95, Number(options.quality ?? DEFAULT_IMAGE_QUALITY)))
  const minSizeToOptimize = Math.max(0, Math.floor(toNumber(options.minSizeToOptimize, DEFAULT_MIN_SIZE_TO_OPTIMIZE)))
  const minSavingRatio = Math.max(0.5, Math.min(1, Number(options.minSavingRatio ?? DEFAULT_MIN_SAVING_RATIO)))
  const preferAvif = options.preferAvif !== false

  if (file.size < minSizeToOptimize) return file

  let resource = null
  try {
    resource = await loadImageResource(file)
    const sourceWidth = Number(resource.width || 0)
    const sourceHeight = Number(resource.height || 0)
    if (sourceWidth <= 0 || sourceHeight <= 0) return file

    const scale = Math.min(1, maxDimension / sourceWidth, maxDimension / sourceHeight)
    const targetWidth = Math.max(1, Math.round(sourceWidth * scale))
    const targetHeight = Math.max(1, Math.round(sourceHeight * scale))
    const resized = targetWidth !== sourceWidth || targetHeight !== sourceHeight

    const canvas = document.createElement('canvas')
    canvas.width = targetWidth
    canvas.height = targetHeight
    const ctx = canvas.getContext('2d', { alpha: false })
    if (!ctx) return file

    ctx.drawImage(resource.source, 0, 0, targetWidth, targetHeight)

    let bestBlob = null
    for (const mimeType of buildTargetFormats(preferAvif)) {
      const blob = await canvasToBlob(canvas, mimeType, quality)
      if (!blob || blob.size <= 0) continue
      if (!bestBlob || blob.size < bestBlob.size) {
        bestBlob = blob
      }
    }

    if (!bestBlob) {
      const fallbackBlob = await canvasToBlob(canvas, file.type || 'image/jpeg', quality)
      if (fallbackBlob && fallbackBlob.size > 0) bestBlob = fallbackBlob
    }

    if (!bestBlob) return file

    if (!resized && bestBlob.size >= file.size * minSavingRatio) {
      return file
    }

    const outputName = buildOutputName(file, bestBlob.type || file.type)
    return new File([bestBlob], outputName, {
      type: bestBlob.type || file.type,
      lastModified: Number(file.lastModified || Date.now()),
    })
  } catch (_) {
    return file
  } finally {
    if (resource?.cleanup) resource.cleanup()
  }
}

export default optimizeImageForUpload
