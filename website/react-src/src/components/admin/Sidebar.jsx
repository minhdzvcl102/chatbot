import React from 'react';
import { LayoutDashboard, User } from 'lucide-react';

const Sidebar = ({ activeItem, onItemClick }) => {
    const menuItems = [
        { id: 'dashboard', icon: LayoutDashboard, label: 'Dashboard' },
        { id: 'user', icon: User, label: 'User' }
    ];

    return (
        <div className="w-64 bg-white border-r border-gray-200 h-full">
            <div className="p-4">
                {menuItems.map((item) => (
                    <button
                        key={item.id}
                        onClick={() => onItemClick(item.id)}
                        className={`w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-left transition-colors ${
                            activeItem === item.id
                            ? 'bg-gray-100 text-gray-900 font-medium'
                            : 'text-gray-600 hover:bg-gray-50'
                        }`}
                    >
                        <item.icon className="w-5 h-5" />
                        <span>{item.label}</span>
                    </button>
                ))}
            </div>
        </div>
    );
};

export default Sidebar;