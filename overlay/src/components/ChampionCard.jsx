import React from 'react';
import { motion } from 'framer-motion';

export function ChampionCard({ champ, isSelected, onClick, highlight }) {
    const isSPlus = champ.score >= 95; // Rough heuristic for S-Tier if not explicitly passed

    return (
        <motion.div
            onClick={onClick}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className={`
                p-3 mb-2 rounded-lg cursor-pointer relative transition-all duration-200
                border backdrop-blur-md
                ${highlight
                    ? 'bg-yellow-400/5 border-yellow-400/50 shadow-[0_0_15px_rgba(255,230,0,0.1)]'
                    : (isSelected ? 'bg-neon-blue/5 border-neon-blue shadow-[0_0_10px_rgba(0,240,255,0.2)]' : 'bg-white/5 border-white/5 hover:border-white/20')}
            `}
        >
            <div className="flex justify-between items-center">
                <div className="flex items-center gap-3">
                    {/* Rank Badge */}
                    <div className={`
                        w-6 h-6 rounded flex items-center justify-center font-bold text-xs
                        ${isSPlus ? 'bg-yellow-400 text-black' : 'bg-black/40 text-white/60'}
                    `}>
                        {Number(champ.score).toFixed(0)}
                    </div>
                    <div>
                        <div className="font-bold text-sm text-white">{champ.champion}</div>
                    </div>
                </div>

                {/* Tags */}
                {champ.details && champ.details.Meta > 50 && (
                    <div className="text-[10px] text-green-400 bg-green-400/10 px-2 py-0.5 rounded">
                        S-TIER
                    </div>
                )}
            </div>

            {/* Details Chips */}
            <div className="flex flex-wrap gap-1.5 mt-2">
                {Object.entries(champ.details || {}).map(([key, val]) => {
                    if (key === 'Meta' || key === 'Personal' || key === 'Synergy' || key === 'Counter') return null; // Skip raw stats

                    const isWarning = key.includes("Need");
                    return (
                        <span key={key} className={`
                            text-[10px] px-1.5 py-0.5 rounded border
                            ${isWarning
                                ? 'bg-red-500/10 text-red-400 border-red-500/20'
                                : 'bg-neon-blue/10 text-neon-blue border-neon-blue/20'}
                        `}>
                            {key}: {val}
                        </span>
                    )
                })}
            </div>
        </motion.div>
    );
}
