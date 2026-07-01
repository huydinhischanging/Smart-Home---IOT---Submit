import { Scene3DManager } from './Scene3DManager.js'

let sceneInstance = null

export function open3DEnvironment() {
  // FIX: tránh double init khi click nhanh / race condition
  if (sceneInstance) {
    console.warn('[Scene3D] Scene already initialized')
    return
  }

  try {
    sceneInstance = new Scene3DManager()
    sceneInstance.init()
    console.log('[Scene3D] Scene initialized')
  } catch (err) {
    console.error('[Scene3D] Failed to init scene', err)
    sceneInstance = null
  }
}
