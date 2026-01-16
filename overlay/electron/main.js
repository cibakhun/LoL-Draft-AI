const { app, BrowserWindow, screen, ipcMain } = require('electron')
const path = require('path')

function createWindow() {
    const { width, height } = screen.getPrimaryDisplay().workAreaSize

    const win = new BrowserWindow({
        width: 400,
        height: 600,
        x: width - 420,
        y: 100,
        frame: false, // Transparent / Custom frame
        transparent: true,
        alwaysOnTop: true,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false // For simplified IPC in this prototype
        }
    })

    // IPC Listeners for Custom Title Bar
    ipcMain.on('minimize-window', () => {
        win.minimize()
    })

    ipcMain.on('close-window', () => {
        win.close()
    })

    // In dev, load vite server. In prod, load built file.
    // For this "Turbo" run, we assume user will run 'npm run dev' which serves on 5173
    // OR we build.
    // We will try to load localhost:5173 first.

    // Dev Mode: Load from Vite Server for reliability
    // Retry connection logic in case Vite is still starting
    // Dev Mode: Load from Vite Server for reliability
    // Retry connection logic in case Vite is still starting
    const loadDevServer = () => {
        win.loadURL('http://localhost:5179').then(() => {
            // Clear Cache to ensure fresh UI
            win.webContents.session.clearCache().then(() => console.log("Cache Cleared"));
        }).catch((e) => {
            console.log("Vite server (5179) not ready, retrying in 1s...");
            setTimeout(loadDevServer, 1000);
        });
    };
    loadDevServer();

    // Optional: Open DevTools
    // win.webContents.openDevTools()
}

app.whenReady().then(() => {
    createWindow()

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow()
        }
    })
})

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit()
    }
})
