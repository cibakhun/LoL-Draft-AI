import React from 'react';

export function ChampionCard({ champ, isSelected, onClick, highlight }) {
    return (
        <div
            onClick={onClick}
            className={`glass-panel slide-in`}
            style={{
                padding: '12px',
                marginBottom: '8px',
                borderRadius: '8px',
                cursor: 'pointer',
                border: highlight ? '1px solid #ffe600' : (isSelected ? '1px solid var(--primary)' : '1px solid var(--glass-border)'),
                boxShadow: highlight ? '0 0 15px rgba(255, 230, 0, 0.1)' : 'none',
                transform: (isSelected || highlight) ? 'scale(1.02)' : 'scale(1)',
                transition: 'all 0.2s ease',
                position: 'relative',
                background: highlight ? 'rgba(255, 230, 0, 0.05)' : (isSelected ? 'rgba(0, 240, 255, 0.05)' : 'var(--bg-panel)')
            }}
        >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    {/* Rank Badge */}
                    <div style={{
                        background: 'var(--bg-dark)',
                        width: '24px', height: '24px',
                        borderRadius: '6px',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontWeight: 'bold', fontSize: '12px', color: 'var(--text-dim)'
                    }}>
                        {Number(champ.score).toFixed(0)}
                    </div>
                    <div>
                        <div style={{ fontWeight: 700, fontSize: '14px' }}>{champ.champion}</div>
                    </div>
                </div>

                {/* Tier/Role Badge */}
                {champ.details && champ.details.Meta > 50 && (
                    <div style={{ fontSize: '10px', color: 'var(--success)', background: 'rgba(0,255,157,0.1)', padding: '2px 6px', borderRadius: '4px' }}>
                        S-TIER
                    </div>
                )}
            </div>

            {/* Details Chips */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '8px' }}>
                {Object.entries(champ.details || {}).map(([key, val]) => {
                    if (key === 'Meta' || key === 'Personal' || key === 'Synergy' || key === 'Counter') return null; // Skip raw stats
                    return (
                        <span key={key} style={{
                            fontSize: '10px',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            background: key.includes("Need") ? 'rgba(255, 68, 68, 0.1)' : 'rgba(0, 240, 255, 0.1)',
                            color: key.includes("Need") ? 'var(--accent)' : 'var(--primary)',
                            border: '1px solid rgba(255,255,255,0.05)'
                        }}>
                            {key}: {val}
                        </span>
                    )
                })}
            </div>
        </div>
    );
}
