import React, { useState } from 'react';
import { motion } from 'framer-motion';

export function TeamDisplay({ myTeam, enemyTeam, myTeamRoles, enemyTeamRoles, myPick, onSwap }) {
    const [selection, setSelection] = useState(null);

    const roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"];
    const roleIcons = { "TOP": "🛡️", "JUNGLE": "🌲", "MIDDLE": "🗡️", "BOTTOM": "🏹", "UTILITY": "💊" };

    const handleSlotClick = (side, role) => {
        if (!onSwap) return;

        if (selection && selection.side === side) {
            if (selection.role !== role) {
                onSwap(side, selection.role, role);
            }
            setSelection(null);
        } else {
            setSelection({ side, role });
        }
    };

    const renderTeam = (side, assignments, teamList) => {
        const isMyTeam = side === 'my';

        return (
            <div className="flex-1 flex flex-col gap-1">
                {roles.map((role, i) => {
                    const champName = assignments ? assignments[role] : (teamList ? teamList[i] : null);
                    const isSelected = selection && selection.side === side && selection.role === role;

                    return (
                        <motion.div
                            key={role}
                            initial={{ opacity: 0, x: isMyTeam ? -10 : 10 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: i * 0.05 }}
                            onClick={() => handleSlotClick(side, role)}
                            className={`
                                py-2 px-3 text-[13px] rounded-md flex items-center gap-2 cursor-pointer transition-all min-h-[34px] border
                                ${isMyTeam ? 'justify-start' : 'justify-end'}
                                ${isSelected
                                    ? 'bg-neon-blue/20 border-neon-blue shadow-[0_0_10px_rgba(0,240,255,0.2)]'
                                    : 'bg-white/5 border-transparent hover:bg-white/10'}
                                ${isMyTeam
                                    ? (champName === myPick ? 'border-l-4 border-l-white' : 'border-l-2 border-l-green-400/50')
                                    : 'border-r-2 border-r-pink-500/50'}
                            `}
                        >
                            {isMyTeam && <span className="opacity-70 text-[11px] w-5">{roleIcons[role]}</span>}

                            <span className={`
                                ${champName === myPick ? 'font-bold text-white drop-shadow-[0_0_5px_rgba(255,255,255,0.8)]' : (champName === "Picking..." ? 'italic text-white/50 animate-pulse' : 'font-medium text-gray-200')}
                            `}>
                                {champName || "Waiting..."}
                            </span>

                            {!isMyTeam && <span className="opacity-70 text-[11px] w-5 text-right">{roleIcons[role]}</span>}
                        </motion.div>
                    );
                })}
            </div>
        );
    };

    return (
        <div className="mb-4">
            {/* Headers */}
            <div className="flex justify-between mb-2 text-[10px] text-white/40 uppercase tracking-wider">
                <span className="text-green-400">Your Team</span>
                <span className="opacity-50 text-[9px]">Click to Swap</span>
                <span className="text-pink-500">Enemy Team</span>
            </div>

            {/* Teams Grid */}
            <div className="flex gap-2">
                {renderTeam('my', myTeamRoles, myTeam)}

                {/* VS Divider */}
                <div className="flex items-center justify-center text-white/20 text-[10px] font-bold w-5">
                    VS
                </div>

                {renderTeam('enemy', enemyTeamRoles, enemyTeam)}
            </div>
        </div>
    );
}
