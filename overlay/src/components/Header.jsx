import React from 'react';
const { ipcRenderer } = window.require('electron');

export function Header() {
    return (
        <div className="glass-panel h-10 flex items-center justify-between px-4 mb-2 rounded-lg border border-white/5 drag-region">
            <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-neon-blue rounded-full shadow-[0_0_8px_rgba(0,240,255,1)]" />
                <span className="font-bold tracking-widest text-[13px] text-white">
                    VANTAGE <span className="text-neon-blue">// TITAN v3.5</span>
                </span>
            </div>

            <div className="flex gap-3 no-drag">
                <button
                    onClick={() => ipcRenderer.send('minimize-window')}
                    className="text-white/40 hover:text-white transition-colors"
                >
                    _
                </button>
                <button
                    onClick={() => ipcRenderer.send('close-window')}
                    className="text-white/40 hover:text-pink-500 transition-colors"
                >
                    ✕
                </button>
            </div>
            <style>{`
                .drag-region { -webkit-app-region: drag; }
                .no-drag { -webkit-app-region: no-drag; }
            `}</style>
        </div>
    );
}
