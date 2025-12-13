import React, { useState } from 'react';

export function TeamDisplay({ myTeam, enemyTeam, myTeamRoles, enemyTeamRoles, myPick, onSwap }) {
    // If backend hasn't resolved yet, fallback to list logic (or just wait)
    // But we prefer the role view.

    // Selection state for swapping: { side: 'my' | 'enemy', role: 'TOP' }
    const [selection, setSelection] = useState(null);

    const roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"];
    const roleIcons = { "TOP": "🛡️", "JUNGLE": "🌲", "MIDDLE": "🗡️", "BOTTOM": "🏹", "UTILITY": "💊" };

    const handleSlotClick = (side, role) => {
        if (!onSwap) return;

        if (selection && selection.side === side) {
            // Swap!
            if (selection.role !== role) {
                onSwap(side, selection.role, role);
            }
            setSelection(null); // Clear after swap or if clicked same
        } else {
            // Select
            setSelection({ side, role });
        }
    };

    const renderTeam = (side, assignments, teamList) => {
        const isMyTeam = side === 'my';
        // Merge assignments with list (if assignment missing, we might want to show it in 'Bench'?)
        // For now, simplify: we show the 5 slots. If empty, show Empty.

        return (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {roles.map((role, i) => {
                    const champName = assignments ? assignments[role] : (teamList ? teamList[i] : null);
                    const isSelected = selection && selection.side === side && selection.role === role;

                    return (
                        <div
                            key={role}
                            onClick={() => handleSlotClick(side, role)}
                            className="glass-panel slide-in"
                            style={{
                                animationDelay: `${i * 0.05}s`,
                                padding: '8px 10px', fontSize: '13px', borderRadius: '6px',
                                display: 'flex', alignItems: 'center', justifyContent: isMyTeam ? 'flex-start' : 'flex-end', gap: '8px',
                                border: isSelected ? '1px solid var(--primary)' : '1px solid transparent',
                                borderLeft: isMyTeam ? (champName === myPick ? '4px solid #ffffff' : '2px solid var(--success)') : undefined,
                                borderRight: !isMyTeam ? '2px solid var(--accent)' : undefined,
                                background: isSelected ? 'rgba(0, 240, 255, 0.15)' : 'var(--bg-panel)',
                                boxShadow: isSelected ? '0 0 10px rgba(0,240,255,0.2)' : 'none',
                                cursor: 'pointer',
                                transition: 'all 0.2s ease',
                                minHeight: '34px'
                            }}
                        >
                            {isMyTeam && <span style={{ opacity: 0.7, fontSize: '11px', width: '18px' }}>{roleIcons[role]}</span>}

                            <span style={{
                                fontWeight: champName === myPick ? 'bold' : (champName === "Picking..." ? 'normal' : '500'),
                                color: champName === "Picking..." ? 'var(--text-dim)' : (champName ? 'var(--text-main)' : 'var(--text-dim)'),
                                textShadow: champName === myPick ? '0 0 10px rgba(255,255,255,0.5)' : 'none',
                                fontStyle: champName === "Picking..." ? 'italic' : 'normal',
                                animation: champName === "Picking..." ? 'pulse-glow 2s infinite' : 'none'
                            }}>
                                {champName || "Waiting..."}
                            </span>

                            {!isMyTeam && <span style={{ opacity: 0.7, fontSize: '11px', width: '18px', textAlign: 'right' }}>{roleIcons[role]}</span>}
                        </div>
                    );
                })}
            </div>
        );
    };

    return (
        <div style={{ marginBottom: '16px' }}>
            {/* Headers */}
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '10px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '1px' }}>
                <span style={{ color: 'var(--success)' }}>Your Team</span>
                <div style={{ fontSize: '9px', opacity: 0.7 }}>Click to Swap Lanes</div>
                <span style={{ color: 'var(--accent)' }}>Enemy Team</span>
            </div>

            {/* Teams Grid */}
            <div style={{ display: 'flex', gap: '8px' }}>
                {renderTeam('my', myTeamRoles, myTeam)}

                {/* VS Divider */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-dim)', fontSize: '10px', fontWeight: 'bold', width: '20px' }}>
                    VS
                </div>

                {renderTeam('enemy', enemyTeamRoles, enemyTeam)}
            </div>
        </div>
    );
}
