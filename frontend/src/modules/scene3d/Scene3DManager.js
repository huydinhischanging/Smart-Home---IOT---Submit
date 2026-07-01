// src/modules/scene3d/Scene3DManager.js
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { House } from './objects/House.js'

export class Scene3DManager {
  constructor() {
    this.scene = null
    this.camera = null
    this.renderer = null
    this.controls = null
    this.house = null
    this._rafId = null

    // 🔧 FIX: bind resize handler 1 lần duy nhất
    this._onResize = this._onResize.bind(this)
  }

  init(container = document.body) {
    // ✅ CHỐNG INIT NHIỀU LẦN
    if (this.renderer) {
      console.warn('[Scene3D] Already initialized')
      return
    }

    /* ================= SCENE ================= */
    this.scene = new THREE.Scene()
    this.scene.background = new THREE.Color(0x111111)

    /* ================= CAMERA ================= */
    this.camera = new THREE.PerspectiveCamera(
      60,
      window.innerWidth / window.innerHeight,
      0.1,
      1000
    )
    this.camera.position.set(6, 6, 6)
    this.camera.lookAt(0, 0, 0)

    /* ================= RENDERER ================= */
    this.renderer = new THREE.WebGLRenderer({ antialias: true })
    this.renderer.setSize(window.innerWidth, window.innerHeight)
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    container.appendChild(this.renderer.domElement)

    /* ================= RESIZE ================= */
    window.addEventListener('resize', this._onResize)

    /* ================= LIGHT ================= */
    const ambient = new THREE.AmbientLight(0xffffff, 0.7)
    const directional = new THREE.DirectionalLight(0xffffff, 0.6)
    directional.position.set(5, 10, 5)
    directional.castShadow = true
    this.scene.add(ambient, directional)

    /* ================= ENVIRONMENT ================= */
    this.house = new House()
    this.scene.add(this.house.getObject3D())

    /* ================= CONTROLS ================= */
    this.controls = new OrbitControls(this.camera, this.renderer.domElement)
    this.controls.enableDamping = true
    this.controls.dampingFactor = 0.05
    this.controls.target.set(0, 1, 0)
    this.controls.update()

    /* ================= TEST OBJECT ================= */
    const cube = new THREE.Mesh(
      new THREE.BoxGeometry(),
      new THREE.MeshStandardMaterial({ color: 0x00ffcc })
    )
    cube.position.y = 0.5
    this.scene.add(cube)

    /* ================= START ================= */
    this._animate()
    console.log('[Scene3D] Initialized')
  }

  /* ================= LOOP ================= */
  _animate = () => {
    this._rafId = requestAnimationFrame(this._animate)
    this.controls?.update()
    this.renderer?.render(this.scene, this.camera)
  }

  /* ================= RESIZE ================= */
  _onResize() {
    if (!this.camera || !this.renderer) return
    this.camera.aspect = window.innerWidth / window.innerHeight
    this.camera.updateProjectionMatrix()
    this.renderer.setSize(window.innerWidth, window.innerHeight)
  }

  /* ================= CLEANUP ================= */
  destroy() {
    if (this._rafId) cancelAnimationFrame(this._rafId)

    window.removeEventListener('resize', this._onResize)

    this.controls?.dispose()
    this.renderer?.dispose()
    this.renderer?.domElement?.remove()

    this.scene = null
    this.camera = null
    this.renderer = null
    this.controls = null
    this.house = null
    this._rafId = null

    console.log('[Scene3D] Destroyed')
  }
}
