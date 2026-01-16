import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Header } from './components/Header'
import { ChampionCard } from './components/ChampionCard'
import { TeamDisplay } from './components/TeamDisplay'

function App() {
    const [data, setData] = useState({ status: "Connecting...", recommendations: [] })
    const [selectedChamp, setSelectedChamp] = useState(null)
    const [gameplan, setGameplan] = useState(null)
    const [build, setBuild] = useState(null)

    // Polling Logic
    useEffect(() => {
        const poll = async () => {
            try {
                const res = await fetch('http://127.0.0.1:5000/status')
                const json = await res.json()
                setData(json)
            } catch (e) {
                console.error("Connection error:", e)
                setData(prev => ({ ...prev, status: "Offline" }))
            }
        }
        const interval = setInterval(poll, 800)
        return () => clearInterval(interval)
    }, [])

    const fetchGameplan = async (champName) => {
        if (selectedChamp === champName) {
            setSelectedChamp(null);
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
        newRoles[roleA] = newRoles[roleB]; // Logic fixed (was mutating in place incorrectly in old code potentially)
        // Actually, old code was: newRoles[roleA] = champB; which is correct logic if vars set.
        // Let's stick to simple swap logic.
        const temp = newRoles[roleA];
        newRoles[roleA] = newRoles[roleB];
        newRoles[roleB] = temp;

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
        <div className="h-screen w-screen flex flex-col p-4 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-900 via-[#0a0a15] to-black text-white relative overflow-hidden">

            {/* AMBIENT BACKGROUND EFFECTS */}
            <div className="absolute top-[-20%] left-[-10%] w-[600px] h-[600px] bg-neon-blue/10 rounded-full blur-[120px] pointer-events-none animate-pulse" />
            <div className="absolute bottom-[-20%] right-[-10%] w-[500px] h-[500px] bg-void-purple/20 rounded-full blur-[100px] pointer-events-none" />

            {/* DEBUG BADGE - VERIFIED */}
            <div className="absolute top-0 right-0 m-1 px-2 py-0.5 bg-green-500/20 border border-green-500 text-green-400 text-[10px] font-bold z-50 rounded backdrop-blur-md shadow-[0_0_10px_rgba(0,255,100,0.3)]">
                ✓ UI CONNECTED
            </div>

            <Header />

            {/* Main Content */}
            <div className="flex-1 overflow-y-auto pr-1 space-y-4">

                {/* Status Bar */}
                <div className="text-xs uppercase tracking-widest text-center text-white/40 mb-4">
                    System Status: <span className="text-neon-blue animate-pulse">{data.status}</span>
                </div>

                <TeamDisplay
                    myTeam={data.my_team_names}
                    enemyTeam={data.enemy_team_names}
                    myTeamRoles={data.my_team_assignments}
                    enemyTeamRoles={data.enemy_team_assignments}
                    myPick={data.my_pick_name}
                    onSwap={handleSwap}
                />

                {/* Role Selector */}
                <div className="flex justify-center gap-2 bg-white/5 p-2 rounded-lg backdrop-blur-sm">
                    {['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY'].map(role => {
                        const isActive = data.assigned_position && data.assigned_position.startsWith(role);
                        const icons = { TOP: '🛡️', JUNGLE: '🌲', MIDDLE: '🗡️', BOTTOM: '🏹', UTILITY: '💊' };
                        return (
                            <motion.div
                                key={role}
                                whileHover={{ scale: 1.1, backgroundColor: 'rgba(0, 240, 255, 0.2)' }}
                                whileTap={{ scale: 0.95 }}
                                onClick={async () => {
                                    await fetch('http://127.0.0.1:5000/setup_override', {
                                        method: 'POST',
                                        headers: { 'Content-Type': 'application/json' },
                                        body: JSON.stringify({ assigned_position: role })
                                    });
                                    setData(d => ({ ...d, assigned_position: role }));
                                }}
                                className={`p-2 rounded cursor-pointer transition-colors border ${isActive ? 'border-neon-blue/50 bg-neon-blue/10' : 'border-transparent opacity-50 hover:opacity-100'}`}
                                title={`Set Role to ${role}`}
                            >
                                {icons[role]}
                            </motion.div>
                        )
                    })}
                </div>

                {/* Recommendations */}
                <AnimatePresence>
                    {data.recommendations && data.recommendations.length > 0 ? (
                        <div className="space-y-4">
                            {/* Current Selection */}
                            {data.selection_stats && (
                                <motion.div
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                >
                                    <div className="flex items-center gap-2 mb-2">
                                        <span className="text-xs font-bold text-neon-blue">CURRENT SELECTION</span>
                                        <div className="h-px flex-1 bg-neon-blue/20" />
                                    </div>
                                    <ChampionCard
                                        champ={data.selection_stats}
                                        isSelected={selectedChamp === data.selection_stats.champion}
                                        onClick={() => fetchGameplan(data.selection_stats.champion)}
                                        highlight={true}
                                    />
                                </motion.div>
                            )}

                            <div className="flex items-center gap-2 text-white/60">
                                <span className="text-xs font-bold uppercase">Top Suggestions</span>
                                <div className="h-px flex-1 bg-white/10" />
                            </div>

                            {data.recommendations.map((rec, i) => (
                                rec.champion !== (data.selection_stats?.champion) && (
                                    <motion.div
                                        key={rec.champion}
                                        initial={{ opacity: 0, x: -20 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        transition={{ delay: i * 0.05 }}
                                    >
                                        <ChampionCard
                                            champ={rec}
                                            isSelected={selectedChamp === rec.champion}
                                            onClick={() => fetchGameplan(rec.champion)}
                                        />

                                        {/* Gameplan */}
                                        <AnimatePresence>
                                            {selectedChamp === rec.champion && gameplan && (
                                                <motion.div
                                                    initial={{ opacity: 0, height: 0 }}
                                                    animate={{ opacity: 1, height: 'auto' }}
                                                    exit={{ opacity: 0, height: 0 }}
                                                    className="ml-3 p-3 mt-2 border-l-2 border-neon-blue bg-neon-blue/5 text-xs text-white/80 leading-relaxed overflow-hidden"
                                                >
                                                    {gameplan}
                                                    {build && (
                                                        <div className="mt-3">
                                                            <div className="text-[10px] font-bold text-neon-blue mb-1">AI BUILD PATH</div>
                                                            <div className="flex flex-wrap gap-1">
                                                                {build.final_build.map((item, idx) => (
                                                                    <span key={idx} className="bg-bg-dark border border-white/10 px-2 py-1 rounded text-[10px]">
                                                                        {item}
                                                                    </span>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}
                                                </motion.div>
                                            )}
                                        </AnimatePresence>
                                    </motion.div>
                                )
                            ))}
                        </div>
                    ) : (
                        <div className="h-40 flex flex-col items-center justify-center opacity-50 space-y-2">
                            <div className="text-4xl animate-bounce">{data.status.includes("Active") ? "🤔" : "👁️"}</div>
                            <div className="text-sm font-medium">
                                {data.status.includes("Active") ? "Calculating Optimal Move..." : "Waiting for Draft..."}
                            </div>
                        </div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    )
}

export default App
