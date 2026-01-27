import React from 'react';
import * as Icons from 'lucide-react';

interface IconRendererProps {
    iconName: string;
    className?: string;
    size?: number | string;
}

export const IconRender = ({ iconName, className = "", size = 24 }: IconRendererProps) => {
    // Normalize icon name (e.g. "search" -> "Search")
    const normalizedName = iconName.charAt(0).toUpperCase() + iconName.slice(1);

    // Use "Bot" as fallback for agents, "FileText" for generic documents
    const safeName = normalizedName || 'Bot';

    // @ts-ignore - Dynamic access to Lucide icons
    const IconComponent = Icons[safeName] || Icons[iconName] || Icons.Bot;

    // Handle specific emoji-to-Lucide mappings if legacy data persists
    if (iconName === '🔍') return <Icons.Search className={className} size={size} />;
    if (iconName === '✅') return <Icons.CheckCircle className={className} size={size} />;
    if (iconName === '📑') return <Icons.FileText className={className} size={size} />;
    if (iconName === '🔎') return <Icons.Search className={className} size={size} />;
    if (iconName === '⚠️') return <Icons.AlertTriangle className={className} size={size} />;
    if (iconName === '📊') return <Icons.BarChart3 className={className} size={size} />;
    if (iconName === '💰') return <Icons.DollarSign className={className} size={size} />;
    if (iconName === '⏰') return <Icons.Clock className={className} size={size} />;
    if (iconName === '🧮') return <Icons.Calculator className={className} size={size} />;
    if (iconName === '📈') return <Icons.TrendingUp className={className} size={size} />;
    if (iconName === '🤖') return <Icons.Bot className={className} size={size} />;
    if (iconName === '📥') return <Icons.Inbox className={className} size={size} />;
    if (iconName === '📅') return <Icons.Calendar className={className} size={size} />;
    if (iconName === '🗓️') return <Icons.CalendarRange className={className} size={size} />;
    if (iconName === '🔧') return <Icons.Wrench className={className} size={size} />;
    if (iconName === '🗄️') return <Icons.Database className={className} size={size} />;
    if (iconName === '🔀') return <Icons.GitMerge className={className} size={size} />;
    if (iconName === '📤') return <Icons.Upload className={className} size={size} />;
    if (iconName === '🥧') return <Icons.PieChart className={className} size={size} />;
    if (iconName === '📉') return <Icons.TrendingDown className={className} size={size} />;
    if (iconName === '🕸️') return <Icons.Radar className={className} size={size} />;
    if (iconName === '⭕') return <Icons.CircleDot className={className} size={size} />;
    if (iconName === '🗺️') return <Icons.LayoutGrid className={className} size={size} />;

    if (!IconComponent) {
        return <Icons.HelpCircle className={className} size={size} />;
    }

    return <IconComponent className={className} size={size} />;
};