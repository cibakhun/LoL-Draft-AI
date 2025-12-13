import React from 'react';

export function WinProbability({ data }) {
    if (!data) return null;

    const isWinning = data.probability > 50;
    const color = isWinning ? 'var(--success)' : 'var(--accent)';

    return (
        <div className="slide-in glass-panel" style={{
            padding: '16px',
            borderRadius: '12px',
            marginBottom: '12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            position: 'relative',
            overflow: 'hidden'
        }}>
            {/* Background Glow */}
            <div style={{
                position: 'absolute',
                top: 0, left: 0, width: '100%', height: '100%',
                background: `radial-gradient(circle at 100% 50%, ${color}22, transparent 70%)`
            }} />

            <div>
                <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '1px' }}>
                    Win Probability
                </div>
                <div style={{ fontSize: '32px', fontWeight: 800, color: color, textShadow: `0 0 20px ${color}44` }}>
                    {data.probability}%
                </div>
            </div>

            <div style={{ textAlign: 'right', zIndex: 1 }}>
                <div style={{ fontSize: '14px', fontWeight: 600 }}>{data.text}</div>
                <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Confidence: High</div>
            </div>
        </div>
    );
}
