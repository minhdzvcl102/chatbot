import React from 'react';
import { Edit, Trash2 } from 'lucide-react';

const UserTable = ({ users, onEditUser, onDeleteUser }) => {
    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
            <div className="overflow-x-auto">
                <table className="w-full">
                    <thead>
                        <tr className="border-b border-gray-200 bg-gray-50">
                            <th className="text-left px-6 py-3 text-sm font-medium text-gray-600">id</th>
                            <th className="text-left px-6 py-3 text-sm font-medium text-gray-600">email</th>
                            <th className="text-left px-6 py-3 text-sm font-medium text-gray-600">role</th>
                            <th className="text-left px-6 py-3 text-sm font-medium text-gray-600">action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {users.map((user) => (
                            <tr key={user.id} className="border-b border-gray-100 hover:bg-gray-50">
                                <td className="px-6 py-4 text-sm text-gray-900">{user.id}</td>
                                <td className="px-6 py-4 text-sm text-gray-900">{user.email}</td>
                                <td className="px-6 py-4">
                                    <span className={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${
                                        user.role === 1
                                        ? 'bg-green-100 text-green-800'
                                        : 'bg-red-100 text-red-800'
                                    }`}>
                                        {user.role === 1 ? 'User' : 'Admin'}
                                    </span>
                                </td>
                                <td className="px-6 py-4">
                                    <div className="flex items-center space-x-2">
                                        <button
                                            onClick={() => onEditUser(user)}
                                            className="text-gray-400 hover:text-blue-600 transition-colors"
                                        >
                                            <Edit className="w-4 h-4" />
                                        </button>
                                        <button
                                            onClick={() => onDeleteUser(user.id)}
                                            className="text-gray-400 hover:text-red-600 transition-colors"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default UserTable;