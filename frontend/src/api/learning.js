import api from './client';

export const getLearningRoadmap = async (params = {}) => {
  const response = await api.get('/users/me/learning-roadmap', { params });
  return response.data;
};

export const deleteLearningPlan = async (planId) => {
  const response = await api.delete(`/users/me/learning-plan/${planId}`);
  return response.data;
};

