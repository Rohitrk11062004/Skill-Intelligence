import api from './client';

export const updateMyProfile = async (payload = {}) => {
  const res = await api.patch('/users/me', payload);
  return res.data;
};

export const getMyPreferences = async () => {
  const res = await api.get('/users/me/preferences');
  return res.data;
};

export const updateMyPreferences = async (payload = {}) => {
  const res = await api.patch('/users/me/preferences', payload);
  return res.data;
};

export const changeMyPassword = async ({ currentPassword, newPassword }) => {
  await api.post('/users/me/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  });
  return true;
};

export const getMyResumes = async () => {
  const res = await api.get('/users/me/resumes');
  return res.data;
};

export const getMySkillTrend = async () => {
  const res = await api.get('/users/me/skill-trend');
  return res.data;
};

