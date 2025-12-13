import { useState, useEffect } from 'react'
import './styles/theme.css'
import { Header } from './components/Header'
import { WinProbability } from './components/WinProbability'
import { ChampionCard } from './components/ChampionCard'
import { TeamDisplay } from './components/TeamDisplay'

function App() {
    const [data, setData] = useState({ status: "Connecting...", recommendations: [] })
    const [winProb, setWinProb] = useState(null)
    const [selectedChamp, setSelectedChamp] = useState(null)
    const [gameplan, setGameplan] = useState(null)
    const [build, setBuild] = useState(null)

    // Polling Logic
    useEffect(() => {
        const poll = async () => {
            try {
                // Status & Recommendations
                const res = await fetch('http://127.0.0.1:5000/status')
                const json = await res.json()
                setData(json)

                // Predictions
                const res2 = await fetch('http://127.0.0.1:5000/predict')
                const json2 = await res2.json()
                setWinProb(json2)

            } catch (e) {
                console.error("Connection error:", e)
                setData(prev => ({ ...prev, status: "Offline (Retrying...)" }))
            }
        }

        const interval = setInterval(poll, 800)
        return () => clearInterval(interval)
    }, [])

    const fetchGameplan = async (champName) => {
        if (selectedChamp === champName) {
            setSelectedChamp(null); // Toggle off
            return;
        }
        setSelectedChamp(champName)
        try {
            const res = await fetch(`http://127.0.0.1:5000/gameplan?champion=${champName}`)
            const json = await res.json()
            setGameplan(json.gameplan)
            setBuild(json.build)
        } catch (e) {
            console.error(e)
        }
    }

    const handleSwap = async (teamSide, roleA, roleB) => {
        const currentRoles = teamSide === 'my' ? data.my_team_assignments : data.enemy_team_assignments;
        const newRoles = { ...currentRoles };
        const champA = newRoles[roleA];
        const champB = newRoles[roleB];
        newRoles[roleA] = champB;
        newRoles[roleB] = champA;

        try {
            await fetch('http://127.0.0.1:5000/setup_override', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    [teamSide === 'my' ? 'my_team_roles' : 'enemy_team_roles']: newRoles
                })
            });
            setData(prev => ({
                ...prev,
                [teamSide === 'my' ? 'my_team_assignments' : 'enemy_team_assignments']: newRoles
            }));
        } catch (e) { console.error(e); }
    };

    return (
        <div style={{
            height: '100vh',
            display: 'flex',
            flexDirection: 'column',
            padding: '10px',
            background: 'linear-gradient(to bottom, rgba(5,5,10,0.95), rgba(5,5,10,0.85))'
        }}>
            <Header />

            {/* Main Content Area */}
            <div style={{ flex: 1, overflowY: 'auto', paddingRight: '4px' }}>

                {/* Status Bar */}
                <div style={{
                    fontSize: '10px', textTransform: 'uppercase', letterSpacing: '2px',
                    color: 'var(--text-dim)', marginBottom: '16px', textAlign: 'center'
                }}>
                    System Status: <span style={{ color: 'var(--primary)' }}>{data.status}</span>
                </div>

                {/* Team Display */}
                <TeamDisplay
                    myTeam={data.my_team_names}
                    enemyTeam={data.enemy_team_names}
                    myTeamRoles={data.my_team_assignments}
                    enemyTeamRoles={data.enemy_team_assignments}
                    myPick={data.my_pick_name}
                    onSwap={handleSwap}
                />

                {/* Manual Role Selector */}
                <div style={{ display: 'flex', justifyContent: 'center', gap: '8px', margin: '8px 0', padding: '4px', background: 'rgba(0,0,0,0.3)', borderRadius: '8px' }}>
                    {['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY'].map(role => {
                        const isActive = data.assigned_position === role || (data.assigned_position && data.assigned_position.startsWith(role));
                        const icons = { TOP: '🛡️', JUNGLE: '🌲', MIDDLE: '🗡️', BOTTOM: '🏹', UTILITY: '💊' };
                        return (
                            <div
                                key={role}
                                onClick={async () => {
                                    /* Reuse override endpoint */
                                    await fetch('http://127.0.0.1:5000/setup_override', {
                                        method: 'POST',
                                        headers: { 'Content-Type': 'application/json' },
                                        body: JSON.stringify({ assigned_position: role })
                                    });
                                    setData(d => ({ ...d, assigned_position: role }));
                                }}
                                style={{
                                    padding: '4px 8px', borderRadius: '4px', cursor: 'pointer', fontSize: '14px',
                                    border: isActive ? '1px solid var(--primary)' : '1px solid transparent',
                                    background: isActive ? 'rgba(0, 240, 255, 0.1)' : 'transparent',
                                    opacity: isActive ? 1 : 0.5,
                                    transition: 'all 0.2s'
                                }}
                                title={`Set Role to ${role}`}
                            >
                                {icons[role]}
                            </div>
                        )
                    })}
                </div>

                {/* Live Prediction REMOVED as per user request */}
                {/* {winProb && <WinProbability data={winProb} />} */}

                {/* Recommendations List */}
                {data.recommendations && data.recommendations.length > 0 && (
                    <>
                        {/* 1. CURRENT SELECTION (User Request) */}
                        {data.selection_stats && (
                            <div style={{ marginBottom: '16px' }}>
                                <div style={{
                                    fontSize: '12px', fontWeight: 'bold', marginBottom: '8px',
                                    color: 'var(--primary)', display: 'flex', alignItems: 'center', gap: '8px'
                                }}>
                                    <span>CURRENT SELECTION</span>
                                    <div style={{ flex: 1, height: '1px', background: 'var(--primary)', opacity: 0.5 }} />
                                </div>
                                <ChampionCard
                                    champ={data.selection_stats}
                                    isSelected={selectedChamp === data.selection_stats.champion}
                                    onClick={() => fetchGameplan(data.selection_stats.champion)}
                                    highlight={true} // New prop for visual emphasis
                                />
                            </div>
                        )}

                        <div style={{
                            fontSize: '12px', fontWeight: 'bold', marginBottom: '8px',
                            color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '8px'
                        }}>
                            <span>top suggestions</span>
                            <div style={{ flex: 1, height: '1px', background: 'var(--glass-border)' }} />
                        </div>

                        {data.recommendations.map((rec) => (
                            // Don't show again if it's the current selection
                            rec.champion !== (data.selection_stats?.champion) && (
                                <div key={rec.champion}>
                                    <ChampionCard
                                        champ={rec}
                                        isSelected={selectedChamp === rec.champion}
                                        onClick={() => fetchGameplan(rec.champion)}
                                    />

                                    {/* Expanded Gameplan View */}
                                    {selectedChamp === rec.champion && gameplan && (
                                        <div className="slide-in" style={{
                                            marginLeft: '12px', padding: '12px',
                                            borderLeft: '2px solid var(--primary)',
                                            background: 'rgba(0, 240, 255, 0.02)',
                                            marginBottom: '12px'
                                        }}>
                                            <div style={{ fontSize: '11px', lineHeight: '1.6', color: 'var(--text-dim)' }}>
                                                {gameplan}
                                            </div>

                                            {/* Build Path */}
                                            {build && (
                                                <div style={{ marginTop: '12px' }}>
                                                    <div style={{ fontSize: '10px', color: 'var(--accent)', fontWeight: 'bold', marginBottom: '4px' }}>
                                                        SOTA AI BUILD
                                                    </div>
                                                    <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                                                        {build.final_build.map((item, i) => (
                                                            <div key={i} style={{
                                                                background: 'var(--bg-dark)',
                                                                border: '1px solid var(--glass-border)',
                                                                padding: '4px 8px', borderRadius: '4px',
                                                                fontSize: '10px'
                                                            }}>
                                                                {item}
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            )
                        ))}
                    </>
                )}

                {(!data.recommendations || data.recommendations.length === 0) && (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '200px', opacity: 0.5 }}>
                        <div style={{ fontSize: '30px', marginBottom: '10px' }}>
                            {data.status.includes("Active") ? "🤔" : "👁️"}
                        </div>
                        <div style={{ textAlign: 'center' }}>
                            {data.status.includes("Active") ? "Thinking... (Or No Valid Champs)" : "Waiting for Draft..."}
                        </div>
                        {data.status.includes("Active") && (
                            <div style={{ fontSize: '10px', marginTop: '8px', color: 'var(--text-dim)' }}>
                                Role: {data.assigned_position || "Detecting..."}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    )
}

export default App
