import * as THREE from 'three'

export class House {
  constructor() {
    this.group = new THREE.Group()

    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(10, 10),
      new THREE.MeshStandardMaterial({ color: 0x222222 })
    )
    floor.rotation.x = -Math.PI / 2
    this.group.add(floor)
  }

  getObject3D() {
    return this.group
  }
}
