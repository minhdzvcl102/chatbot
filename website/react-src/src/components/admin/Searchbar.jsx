import React from 'react';
import { Search, Plus } from 'lucide-react';

const SearchBar = ({ searchTerm, onSearchChange, onAddUser }) => {
    return (
        <div className="flex items-center justify-between mb-6">
            <div className="relative flex-1 max-w-md">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                <input
                    type="text"
                    placeholder="Search User..."
                    value={searchTerm}
                    onChange={(e) => onSearchChange(e.target.value)}
                    className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
            </div>
            <button
                onClick={onAddUser}
                className="ml-4 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
            >
                <Plus className="w-4 h-4" />
                <span>Add User</span>
            </button>
        </div>
    );
};

export default SearchBar;