import { invoke } from '@tauri-apps/api/core'
import { listen, emit } from '@tauri-apps/api/event'
import { open } from '@tauri-apps/plugin-dialog'

// 类型定义
interface DeviceInfo {
  id: string
  name: string
  ip: string
  port: number
  is_paired?: boolean
}

interface TransferProgress {
  file_name: string
  total_size: number
  transferred: number
  status: 'pending' | 'transferring' | 'completed' | 'failed'
}

// 全局状态
let myDevice: DeviceInfo | null = null
let selectedDevice: DeviceInfo | null = null
let pairedDevices: DeviceInfo[] = []
let discoveredDevices: DeviceInfo[] = []

export default class App {
  private container: HTMLDivElement | null = null

  mount() {
    this.container = document.createElement('div')
    this.container.className = 'container'
    document.getElementById('app')!.appendChild(this.container)

    this.render()
    this.init()
  }

  private render() {
    if (!this.container) return

    this.container.innerHTML = `
      <!-- 侧边栏 - 设备列表 -->
      <aside class="sidebar">
        <div class="header">
          <div class="logo">
            <span class="logo-icon">📡</span>
            <span class="logo-text">FileDrop</span>
          </div>
          <div class="device-info" id="deviceInfo">正在初始化...</div>
        </div>

        <div class="device-list" id="deviceList">
          <div class="section-title">
            <span>已配对设备</span>
          </div>
          <div id="pairedDevices"></div>

          <div class="section-title" style="margin-top: 20px;">
            <span>新设备</span>
          </div>
          <div id="newDevices"></div>
        </div>
      </aside>

      <!-- 主内容区 -->
      <main class="main">
        <div class="toolbar">
          <h1 class="page-title">文件传输</h1>
          <button class="btn btn-secondary" id="settingsBtn">
            ⚙️ 设置
          </button>
        </div>

        <div id="contentArea">
          <!-- 动态内容 -->
        </div>
      </main>

      <!-- 状态栏 -->
      <div class="status-bar">
        <div class="status-text">
          <span class="status-indicator"></span>
          <span id="statusText">正在搜索设备...</span>
        </div>
        <button class="btn btn-secondary" style="padding: 6px 12px; font-size: 12px;" id="debugBtn">
          🔍 调试信息
        </button>
      </div>

      <!-- 设置弹窗 -->
      <div class="modal-overlay" id="settingsModal">
        <div class="modal">
          <div class="modal-header">
            <h3 class="modal-title">设置</h3>
            <button class="modal-close" id="closeSettings">×</button>
          </div>
          <div class="form-group">
            <label class="form-label">接收文件保存位置</label>
            <div class="form-row">
              <input type="text" class="form-input" id="savePath" readonly>
              <button class="btn btn-secondary" id="chooseFolder">浏览...</button>
            </div>
          </div>
          <button class="btn btn-primary" id="saveSettings" style="width: 100%;">
            保存设置
          </button>
        </div>
      </div>
    `

    // 绑定事件
    this.bindEvents()
  }

  private bindEvents() {
    // 设置按钮
    document.getElementById('settingsBtn')?.addEventListener('click', () => {
      this.showSettings()
    })

    // 关闭设置
    document.getElementById('closeSettings')?.addEventListener('click', () => {
      this.hideSettings()
    })

    // 选择文件夹
    document.getElementById('chooseFolder')?.addEventListener('click', () => {
      this.chooseFolder()
    })

    // 保存设置
    document.getElementById('saveSettings')?.addEventListener('click', () => {
      this.saveSettings()
    })

    // 调试按钮
    document.getElementById('debugBtn')?.addEventListener('click', () => {
      this.showDebugInfo()
    })

    // 点击模态框外部关闭
    document.getElementById('settingsModal')?.addEventListener('click', (e) => {
      if (e.target === document.getElementById('settingsModal')) {
        this.hideSettings()
      }
    })
  }

  private async init() {
    // 初始化设备信息
    await this.initDevice()

    // 开始发现设备
    await this.startDiscovery()

    // 加载设置
    await this.loadSettings()
  }

  private async initDevice() {
    try {
      myDevice = await invoke<DeviceInfo>('get_device_info')
      const deviceInfoEl = document.getElementById('deviceInfo')
      if (deviceInfoEl && myDevice) {
        deviceInfoEl.textContent = `${myDevice.name} (${myDevice.id})`
      }
    } catch (e) {
      console.error('获取设备信息失败:', e)
      const deviceInfoEl = document.getElementById('deviceInfo')
      if (deviceInfoEl) {
        deviceInfoEl.textContent = '获取信息失败'
      }
    }
  }

  private async startDiscovery() {
    try {
      await this.refreshDevices()
      setInterval(() => this.refreshDevices(), 3000)
    } catch (e) {
      console.error('启动设备发现失败:', e)
    }
  }

  private async refreshDevices() {
    try {
      const devices = await invoke<DeviceInfo[]>('get_discovered_devices')
      this.updateDeviceList(devices)
    } catch (e) {
      console.error('刷新设备列表失败:', e)
    }
  }

  private updateDeviceList(devices: DeviceInfo[]) {
    pairedDevices = devices.filter(d => d.is_paired)
    discoveredDevices = devices.filter(d => !d.is_paired)

    // 更新已配对设备
    const pairedContainer = document.getElementById('pairedDevices')
    if (pairedContainer) {
      pairedContainer.innerHTML = pairedDevices.length > 0
        ? pairedDevices.map(d => this.renderDeviceItem(d, true)).join('')
        : '<div style="color: var(--text-secondary); padding: 12px;">暂无已配对设备</div>'
    }

    // 更新新设备
    const newContainer = document.getElementById('newDevices')
    if (newContainer) {
      newContainer.innerHTML = discoveredDevices.length > 0
        ? discoveredDevices.map(d => this.renderDeviceItem(d, false)).join('')
        : '<div style="color: var(--text-secondary); padding: 12px;">未发现新设备</div>'
    }

    // 绑定设备点击事件
    document.querySelectorAll('.device-item').forEach(item => {
      item.addEventListener('click', () => {
        const deviceId = (item as HTMLElement).dataset.id
        if (deviceId) {
          this.selectDevice(deviceId)
        }
      })
    })

    // 更新状态文本
    const statusText = document.getElementById('statusText')
    if (statusText) {
      const totalDevices = devices.length
      statusText.textContent = totalDevices > 0
        ? `已发现 ${totalDevices} 个设备`
        : '正在搜索设备...'
    }
  }

  private renderDeviceItem(device: DeviceInfo, isPaired: boolean): string {
    const isSelected = selectedDevice?.id === device.id
    return `
      <div class="device-item ${isPaired ? 'paired' : ''} ${isSelected ? 'selected' : ''}" data-id="${device.id}">
        <div class="device-icon">💻</div>
        <div class="device-details">
          <div class="device-name">${device.name}</div>
          <div class="device-status">${device.ip} • ${isPaired ? '已配对' : '未配对'}</div>
        </div>
        <div class="status-dot ${isPaired ? '' : 'pending'}"></div>
      </div>
    `
  }

  private selectDevice(deviceId: string) {
    const allDevices = [...pairedDevices, ...discoveredDevices]
    selectedDevice = allDevices.find(d => d.id === deviceId) || null
    this.updateDeviceList([...pairedDevices, ...discoveredDevices])
    this.showDeviceDetail()
  }

  private showDeviceDetail() {
    const contentArea = document.getElementById('contentArea')
    if (!contentArea) return

    if (!selectedDevice) {
      contentArea.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">📡</div>
          <h3>选择一个设备开始传输</h3>
          <p>从左侧列表选择一个设备，开始传输文件</p>
        </div>
      `
      return
    }

    const isPaired = selectedDevice.is_paired || false

    contentArea.innerHTML = `
      <div class="device-card">
        <div class="device-card-header">
          <div class="device-card-icon">💻</div>
          <div class="device-card-info">
            <h2>${selectedDevice.name}</h2>
            <p>${selectedDevice.ip}:${selectedDevice.port} • ${isPaired ? '已配对' : '未配对'}</p>
          </div>
        </div>
        <div class="device-actions">
          ${!isPaired ? `
            <button class="btn btn-primary" id="pairBtn">
              🔒 配对设备
            </button>
          ` : ''}
          <button class="btn btn-primary" ${!isPaired ? 'disabled' : ''} id="sendFileBtn">
            📤 发送文件
          </button>
        </div>
      </div>

      <div class="transfer-zone" id="transferZone">
        <div class="transfer-icon">📁</div>
        <div class="transfer-text">
          <strong>${isPaired ? '点击或拖放文件到此处' : '请先配对设备'}</strong>
          ${isPaired ? '支持任意类型文件，单次最大 1GB' : '配对后即可传输文件'}
        </div>
      </div>
    `

    // 绑定事件
    document.getElementById('pairBtn')?.addEventListener('click', () => {
      this.pairDevice()
    })

    document.getElementById('sendFileBtn')?.addEventListener('click', () => {
      this.selectFile()
    })

    const transferZone = document.getElementById('transferZone')
    if (transferZone) {
      transferZone.addEventListener('click', () => {
        if (isPaired) {
          this.selectFile()
        }
      })

      transferZone.addEventListener('dragover', (e) => {
        e.preventDefault()
        transferZone.classList.add('drag-over')
      })

      transferZone.addEventListener('dragleave', () => {
        transferZone.classList.remove('drag-over')
      })

      transferZone.addEventListener('drop', (e) => {
        e.preventDefault()
        transferZone.classList.remove('drag-over')
        if (isPaired) {
          this.selectFile()
        }
      })
    }
  }

  private async pairDevice() {
    if (!selectedDevice) return

    try {
      await invoke('send_pair_request', { deviceId: selectedDevice.id })
      await invoke('accept_pair', { deviceId: selectedDevice.id, deviceName: selectedDevice.name })
      alert(`已与 ${selectedDevice.name} 配对成功！`)
      await this.refreshDevices()
    } catch (e) {
      alert('配对失败: ' + e)
    }
  }

  private async selectFile() {
    if (!selectedDevice) return

    try {
      const path = await invoke<string | null>('select_file')
      if (path) {
        await this.sendFile(path)
      }
    } catch (e) {
      console.error('选择文件失败:', e)
    }
  }

  private async sendFile(filePath: string) {
    if (!selectedDevice) return

    try {
      const statusText = document.getElementById('statusText')
      if (statusText) {
        statusText.textContent = '正在发送文件...'
      }

      await invoke('send_file', {
        deviceId: selectedDevice.id,
        filePath: filePath
      })

      alert('文件发送成功！')
      if (statusText) {
        statusText.textContent = '就绪'
      }
    } catch (e) {
      alert('发送失败: ' + e)
      const statusText = document.getElementById('statusText')
      if (statusText) {
        statusText.textContent = '发送失败'
      }
    }
  }

  private showSettings() {
    const modal = document.getElementById('settingsModal')
    if (modal) {
      modal.classList.add('active')
    }
  }

  private hideSettings() {
    const modal = document.getElementById('settingsModal')
    if (modal) {
      modal.classList.remove('active')
    }
  }

  private async chooseFolder() {
    try {
      const path = await invoke<string | null>('select_folder')
      if (path) {
        const savePathInput = document.getElementById('savePath') as HTMLInputElement
        if (savePathInput) {
          savePathInput.value = path
        }
      }
    } catch (e) {
      console.error('选择文件夹失败:', e)
    }
  }

  private async saveSettings() {
    const savePathInput = document.getElementById('savePath') as HTMLInputElement
    const path = savePathInput?.value
    if (path) {
      try {
        await invoke('set_save_path', { path })
        alert('设置已保存')
        this.hideSettings()
      } catch (e) {
        alert('保存失败: ' + e)
      }
    }
  }

  private async loadSettings() {
    try {
      const path = await invoke<string>('get_save_path')
      const savePathInput = document.getElementById('savePath') as HTMLInputElement
      if (savePathInput) {
        savePathInput.value = path
      }
    } catch (e) {
      console.error('加载设置失败:', e)
    }
  }

  private async showDebugInfo() {
    try {
      const info = await invoke<DeviceInfo>('get_device_info')
      const path = await invoke<string>('get_save_path')
      alert(`调试信息:

设备名称: ${info.name}
设备 ID: ${info.id}
本机 IP: ${info.ip || '获取中...'}
服务端口: ${info.port}

保存路径: ${path}

如果无法发现设备，请检查:
1. 两台设备在同一 WiFi 网络
2. 防火墙允许端口 ${info.port}
3. 路由器未禁用 mDNS/Bonjour`)
    } catch (e) {
      alert('获取信息失败: ' + e)
    }
  }
}
