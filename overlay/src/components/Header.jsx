import React from 'react';
const { ipcRenderer } = window.require('electron');

export function Header() {
    return (
        <div className="glass-panel" style={{
            height: '40px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 16px',
            WebkitAppRegion: 'drag', // Draggable
            marginBottom: '8px',
            borderRadius: '8px',
            border: '1px solid rgba(255,255,255,0.05)'
        }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{
                    width: '8px', height: '8px',
                    background: 'var(--primary)',
                    borderRadius: '50%',
                    boxShadow: '0 0 8px var(--primary)'
                }} />
                <span style={{ fontWeight: 700, letterSpacing: '1px', fontSize: '13px' }}>
                    HIVE<span style={{ color: 'var(--primary)' }}>MIND</span> ORACLE
                </span>
            </div>

            <div style={{ display: 'flex', gap: '12px', WebkitAppRegion: 'no-drag' }}>
                <button
                    onClick={() => ipcRenderer.send('minimize-window')}
                    style={{ background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer', fontSize: '16px' }}
                >
                    _
                </button>
                <button
                    onClick={() => ipcRenderer.send('close-window')}
                    style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: '16px' }}
                >
                    ✕
                </button>
            </div>
        </div>
    );
}
