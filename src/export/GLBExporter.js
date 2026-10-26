import * as THREE from 'three';
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

export class GLBExporter {
  constructor() {
    this.exporter = new GLTFExporter();
    this.loader = new GLTFLoader();
  }

  /**
   * Exports the architectural scene to a GLB file and initiates download
   * @param {THREE.Object3D} rootGroup - The root reconstructed scene group
   * @param {string} filename - Filename for downloaded file
   * @returns {Promise<ArrayBuffer>}
   */
  async exportScene(rootGroup, filename = 'reconstructed_scene.glb') {
    return new Promise((resolve, reject) => {
      // Create export group containing geometric elements only (exclude sprites)
      const exportGroup = new THREE.Group();
      exportGroup.name = 'ReconstructedArchitecture';

      rootGroup.children.forEach(group => {
        // Only include geometric architecture layers (Walls, Floors, Doors, Windows, Rooms)
        if (group.name === 'Walls' || group.name === 'Floors' || 
            group.name === 'Doors' || group.name === 'Windows' || group.name === 'Rooms') {
          exportGroup.add(group.clone(true));
        }
      });

      const options = {
        binary: true,
        embedImages: true,
        onlyVisible: false
      };

      this.exporter.parse(
        exportGroup,
        (glbArrayBuffer) => {
          try {
            // Trigger browser download
            const blob = new Blob([glbArrayBuffer], { type: 'model/gltf-binary' });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = filename;
            link.click();
            URL.revokeObjectURL(link.href);

            resolve(glbArrayBuffer);
          } catch (err) {
            reject(err);
          }
        },
        (error) => {
          reject(error);
        },
        options
      );
    });
  }

  /**
   * Reloads and validates the exported GLB ArrayBuffer with GLTFLoader
   * @param {ArrayBuffer} glbArrayBuffer 
   * @returns {Promise<Object>} Verification details (meshCount, bounds, scene)
   */
  async verifyReloadGLB(glbArrayBuffer) {
    return new Promise((resolve, reject) => {
      this.loader.parse(
        glbArrayBuffer,
        '',
        (gltf) => {
          let meshCount = 0;
          gltf.scene.traverse(child => {
            if (child.isMesh) meshCount++;
          });

          const box = new THREE.Box3().setFromObject(gltf.scene);
          const size = new THREE.Vector3();
          box.getSize(size);

          resolve({
            success: true,
            meshCount,
            dimensions: {
              x: Number(size.x.toFixed(3)),
              y: Number(size.y.toFixed(3)),
              z: Number(size.z.toFixed(3))
            },
            gltfScene: gltf.scene
          });
        },
        (error) => {
          reject(error);
        }
      );
    });
  }
}
