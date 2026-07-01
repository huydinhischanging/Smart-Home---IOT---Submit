// src/modules/map/map.room-selector.js
// ==========================================
// Room double-click selector for Alfred AI chat
// Detects which room polygon was clicked and auto-selects it in chat
// ==========================================

import { setCurrentRoom } from '../companion/chat.panel.js'

export function initMapRoomSelector(canvasId = 'room-overlay-canvas') {
  const canvas = document.getElementById(canvasId)
  if (!canvas) {
    console.warn('[MapRoomSelector] Canvas not found:', canvasId)
    return
  }

  let roomsData = []

  // Update rooms when they're loaded/changed
  window.updateMapRoomSelectorData = (rooms) => {
    roomsData = rooms || []
    console.log('[MapRoomSelector] Updated rooms data:', roomsData.length, 'rooms')
  }

  canvas.addEventListener('dblclick', (event) => {
    if (!roomsData.length) {
      console.warn('[MapRoomSelector] No rooms data available')
      return
    }

    // Get canvas position and dimensions
    const rect = canvas.getBoundingClientRect()
    const canvasWidth = canvas.width
    const canvasHeight = canvas.height
    const displayWidth = rect.width
    const displayHeight = rect.height

    // Calculate scale from display size to canvas size
    const scaleX = canvasWidth / displayWidth
    const scaleY = canvasHeight / displayHeight

    // Get click position relative to canvas
    const clickX = (event.clientX - rect.left) * scaleX
    const clickY = (event.clientY - rect.top) * scaleY

    console.log('[MapRoomSelector] Double-click at canvas coords:', clickX, clickY)

    // Check which room polygon contains the click
    const clickedRoom = detectRoomAtPoint(clickX, clickY, roomsData, canvasWidth, canvasHeight)

    if (clickedRoom) {
      const roomId = clickedRoom.id || clickedRoom.room_id
      const roomName = clickedRoom.name || clickedRoom.room_name
      console.log('[MapRoomSelector] Room selected:', roomName, '(ID:', roomId, ')')
      setCurrentRoom(roomId, roomName)
    } else {
      console.log('[MapRoomSelector] No room at this location')
    }
  })
}

/**
 * Detect which room polygon contains the given point
 * Uses the same coordinate system as the map canvas
 */
function detectRoomAtPoint(x, y, rooms, canvasWidth, canvasHeight) {
  for (const room of rooms) {
    const points = room.points || []
    if (!points || points.length < 3) continue

    // Build path from room points
    const path = new Path2D()
    let isFirstPoint = true

    for (const pt of points) {
      const xPct = pt.xPct !== undefined ? pt.xPct : (pt.x || 0)
      const yPct = pt.yPct !== undefined ? pt.yPct : (pt.y || 0)

      // Convert from percentage to canvas pixels
      const px = (xPct / 100) * canvasWidth
      const py = (yPct / 100) * canvasHeight

      if (isFirstPoint) {
        path.moveTo(px, py)
        isFirstPoint = false
      } else {
        path.lineTo(px, py)
      }
    }
    path.closePath()

    // Test if point is inside polygon
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')
    if (ctx && ctx.isPointInPath(path, x, y)) {
      return room
    }
  }

  return null
}
