import api from './client';

export const getDashboardStats = async () => {
  const response = await api.get('/users/me/dashboard');
  return response.data;
};
