import React, { useState, useEffect } from 'react';
import Header from '../components/admin/Header';
import Sidebar from '../components/admin/Sidebar';
import SearchBar from '../components/admin/SearchBar';
import UserTable from '../components/admin/UserTable';
import UserForm from '../components/admin/UserForm';
import { userServices } from '../services/usersService';

const Dashboard = () => {
    const [isFormOpen, setIsFormOpen] = useState(false);
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Load users when component mounts
    useEffect(() => {
        loadUsers();
    }, []);

    const loadUsers = async () => {
        try {
            setLoading(true);
            setError(null);
            const token = localStorage.getItem('authToken');

            if (!token) {
                setError('No authentication token found');
                return;
            }
            const id = localStorage.getItem('user.id');
            const response = await userServices.getAllUsers(token,id);
            setUsers(response.users || response); // Handle different response structures
            console.log('Users loaded:', response);
        } catch (error) {
            console.error('Error loading users:', error);
            setError(error.message);
        } finally {
            setLoading(false);
        }
    };

    const handleAddUser = (e) => {
        e.preventDefault();
        setIsFormOpen(true);
    };

    const handleFormSubmit = async (formData) => {
        try {
            setLoading(true);
            setError(null);
            const token = localStorage.getItem('authToken');

            if (!token) {
                setError('No authentication token found');
                return;
            }

            console.log('Creating user with data:', formData);

            const response = await userServices.createUser(
                formData.email,
                formData.username,
                formData.password,
                formData.role,
                token  // Add token parameter
            );

            console.log('User created successfully:', response);
            setIsFormOpen(false);

            // Reload users list after successful creation
            await loadUsers();

        } catch (error) {
            console.error('Error creating user:', error);
            setError(error.message);
        } finally {
            setLoading(false);
        }
    };

    const handleDeleteUser = async (userId) => {
        try {
            setLoading(true);
            setError(null);
            const token = localStorage.getItem('authToken');

            if (!token) {
                setError('No authentication token found');
                return;
            }

            await userServices.deleteUser(userId, token);
            console.log('User deleted successfully');

            // Reload users list after successful deletion
            await loadUsers();

        } catch (error) {
            console.error('Error deleting user:', error);
            setError(error.message);
        } finally {
            setLoading(false);
        }
    };

    const handleEditUser = async (userId, userData) => {
        try {
            setLoading(true);
            setError(null);
            const token = localStorage.getItem('authToken');

            if (!token) {
                setError('No authentication token found');
                return;
            }

            await userServices.updateUser(userId, userData, token);
            console.log('User updated successfully');

            // Reload users list after successful update
            await loadUsers();

        } catch (error) {
            console.error('Error updating user:', error);
            setError(error.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div>
            <Header title="Dashboard" userAvatar="/path-to-avatar.jpg" />
            <div className="flex">
                <Sidebar activeItem="dashboard" onItemClick={() => { }} />
                <div className="flex-1 p-6">
                    {error && (
                        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
                            {error}
                        </div>
                    )}

                    <SearchBar
                        searchTerm=""
                        onSearchChange={() => { }}
                        onAddUser={handleAddUser}
                    />

                    {loading && (
                        <div className="text-center py-4">
                            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                            <p className="mt-2">Loading...</p>
                        </div>
                    )}

                    <UserTable
                        users={users}
                        onEditUser={handleEditUser}
                        onDeleteUser={handleDeleteUser}
                    />

                    <UserForm
                        isOpen={isFormOpen}
                        onClose={() => setIsFormOpen(false)}
                        onSubmit={handleFormSubmit}
                    />
                </div>
            </div>
        </div>
    );
};

export default Dashboard;   