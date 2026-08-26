const { app, BrowserWindow } = require('electron')
const fs = require('node:fs')
const path = require('node:path')

const fixtureUrl = process.env.EITAA_RTL_FIXTURE_URL || 'http://127.0.0.1:5173/?__phase9_visual_fixture=1'
const outputDir = path.resolve(__dirname, '..', '.rtl-acceptance')

app.disableHardwareAcceleration()
app.on('window-all-closed', () => {})

function wait(milliseconds) {
  return new Promise(resolve => setTimeout(resolve, milliseconds))
}

async function captureViewport(name, width, height) {
  const window = new BrowserWindow({
    show: false,
    width,
    height,
    webPreferences: {
      contextIsolation: true,
      sandbox: true,
    },
  })

  try {
    await window.loadURL(fixtureUrl)
  } catch (error) {
    // Vite's first dependency-optimization reload can cancel the initial navigation.
    if (!String(error).includes('ERR_FAILED')) throw error
    await wait(500)
  }
  await wait(1600)

  const metrics = await window.webContents.executeJavaScript(`(() => {
    const rect = element => {
      if (!element) return null
      const value = element.getBoundingClientRect()
      return {
        left: Math.round(value.left),
        right: Math.round(value.right),
        top: Math.round(value.top),
        bottom: Math.round(value.bottom),
        width: Math.round(value.width),
        height: Math.round(value.height),
      }
    }
    const main = document.querySelector('main')
    const navigation = document.querySelector('[aria-label="ناوبری اصلی برنامه"]')
    const conversations = document.querySelector('aside[aria-label="فهرست گفتگوها"]')
    const chatSection = document.querySelector('main > section')
    const firstListButton = document.querySelector('aside[aria-label="فهرست گفتگوها"] .MuiListItemButton-root')
    if (firstListButton) firstListButton.click()
    return new Promise(resolve => setTimeout(() => {
      const cards = Array.from(document.querySelectorAll('.MuiCard-root'))
      const messageCard = cards.find(card => card.querySelector('.MuiCardHeader-root')) || null
      const header = messageCard?.querySelector('.MuiCardHeader-root') || null
      const avatar = header?.querySelector('.MuiAvatar-root') || null
      const title = header?.querySelector('.MuiCardHeader-content') || null
      const action = header?.querySelector('.MuiCardHeader-action') || null
      resolve({
        viewport: { width: innerWidth, height: innerHeight },
        htmlDir: document.documentElement.dir,
        htmlDirection: getComputedStyle(document.documentElement).direction,
        mainDirection: main ? getComputedStyle(main).direction : null,
        navigation: rect(navigation),
        conversations: rect(conversations),
        chatSection: rect(chatSection),
        messageCard: rect(messageCard),
        messageHeader: rect(header),
        messageAvatar: rect(avatar),
        messageTitle: rect(title),
        messageAction: rect(action),
      })
    }, 900))
  })()`)

  const image = await window.webContents.capturePage()
  fs.mkdirSync(outputDir, { recursive: true })
  fs.writeFileSync(path.join(outputDir, `${name}.png`), image.toPNG())
  fs.writeFileSync(path.join(outputDir, `${name}.json`), `${JSON.stringify(metrics, null, 2)}\n`, 'utf8')
  window.destroy()
  return metrics
}

function assertDesktopRtl(metrics) {
  if (metrics.htmlDirection !== 'rtl' || metrics.mainDirection !== 'rtl') {
    throw new Error(`RTL direction mismatch: html=${metrics.htmlDirection}, main=${metrics.mainDirection}`)
  }
  if (!metrics.navigation || !metrics.conversations || !metrics.chatSection) {
    throw new Error('Desktop RTL surfaces were not rendered')
  }
  if (!(metrics.navigation.left > metrics.conversations.left && metrics.conversations.left > metrics.chatSection.left)) {
    throw new Error(`Desktop columns are not ordered from the right: ${JSON.stringify(metrics)}`)
  }
  if (metrics.messageAvatar && metrics.messageTitle && metrics.messageAction
      && !(metrics.messageAvatar.left > metrics.messageTitle.left && metrics.messageTitle.left > metrics.messageAction.left)) {
    throw new Error(`Message header is not ordered from the right: ${JSON.stringify(metrics)}`)
  }
}

function assertMobileRtl(metrics) {
  if (metrics.htmlDirection !== 'rtl' || metrics.mainDirection !== 'rtl') {
    throw new Error(`Mobile RTL direction mismatch: html=${metrics.htmlDirection}, main=${metrics.mainDirection}`)
  }
  if (!metrics.navigation || metrics.navigation.top < metrics.viewport.height - 80) {
    throw new Error(`Mobile navigation is not docked to the bottom: ${JSON.stringify(metrics)}`)
  }
  if (!metrics.conversations || metrics.conversations.left < metrics.viewport.width) {
    throw new Error(`Closed conversation drawer is not parked beyond the right edge: ${JSON.stringify(metrics)}`)
  }
}

app.whenReady().then(async () => {
  try {
    const desktop = await captureViewport('desktop-1280x800', 1280, 800)
    assertDesktopRtl(desktop)
    const mobile = await captureViewport('mobile-390x844', 390, 844)
    assertMobileRtl(mobile)
    const results = { desktop, mobile }
    process.stdout.write(`${JSON.stringify(results, null, 2)}\n`)
    app.exit(0)
  } catch (error) {
    process.stderr.write(`${error?.stack || error}\n`)
    app.exit(1)
  }
})
