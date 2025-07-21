import React from 'react';

const Header = ({ title, userAvatar }) => {
    return (
        <div className="bg-white border-b border-gray-200 px-6 py-4">
            <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                    <div className="flex items-center space-x-2">
                        <div className="flex items-center gap-3">
                            <span className="text-xl font-bold text-black">
                                <img src="/inda.jpg" alt="Logo" className="h-30 w-auto" />
                            </span>
                        </div>
                    </div>
                    <h1 className="text-xl font-semibold text-gray-900 ml-8">{title}</h1>
                </div>
                <div className="w-10 h-10 bg-gray-300 rounded-full flex items-center justify-center">
                    <img src={userAvatar} alt="User" className="w-full h-full rounded-full" />
                </div>
            </div>
        </div>
    );
};

export default Header;